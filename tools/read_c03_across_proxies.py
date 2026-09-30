"""Read an older year's CEO pay (C03) from every saved proxy that reports it.

A pay-versus-performance table reports up to five years, so a year's PEO total
is reported first by the proxy after that year and again, tagged
ecd:PeoTotalCompAmt, by each later proxy. The historical route reads the year
from the first proxy after it - its tags, or for a proxy filed before the
table was required, its Summary Compensation Table. This reading takes the
year's PEO total from every saved proxy of the registrant that tags it (the
checkout's and the acquisition export's) and accepts only when each of them
reports exactly one total, they all agree, and at least one of them is a
filing the result does not name - so the value is confirmed by a document
the route did not read. A placeholder dash for a person paid as PEO in
another year is set aside as read_governance_facts sets it aside. A year two
proxies report differently is recorded with every amount, not chosen between
(c03-first-ecd-release/: Marriott corrects its 2022 total, Macy's reports
fiscal 2023 net of a clawback).

It imports none of the route's governance modules. The published value and
the filings the result names come from a named runs root and closure.

Usage:
    python3 tools/read_c03_across_proxies.py --reading <positions.json reading> \
        --runs-root <flat runs root> --closure sha256:<closure> --output <reading path>
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import tarfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import (EXPORT, EXPORT_MEMBER_PREFIX, _export_members,  # noqa: E402
                                 accession_of_document, reading_cases)
from read_governance_facts import contexts_of, peo_totals, peo_totals_for  # noqa: E402

_CIK = re.compile(r'name="dei:EntityCentralIndexKey"[^>]*>(?:<[^>]+>)*\s*([0-9]+)')


def _number(value):
    return int(value) if value == value.to_integral_value() else str(value)


def saved_proxies(repo_root=REPO):
    """Every saved document carrying PEO totals, by registrant CIK.

    Returns:
        ``{cik: [{"document", "sha256", "text"}]}``; the document is its path
        relative to the saved data root, the form accession_of_document reads.
    """
    found, seen = defaultdict(list), set()

    def add(relative, data):
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen or b"PeoTotalCompAmt" not in data:
            return
        seen.add(digest)
        text = data.decode("utf-8-sig", errors="replace")
        cik = _CIK.search(text)
        if cik is not None:
            found[str(int(cik.group(1)))].append({"document": relative, "sha256": digest,
                                                  "text": text})

    for path in sorted(repo_root.glob("evidence/accession_materials/*/*.htm")) + sorted(
            repo_root.glob("evidence/request_attempts/*/*/*.htm")):
        add(str(path.relative_to(repo_root)), path.read_bytes())
    by_archive = defaultdict(list)
    for member, (archive, _) in _export_members(repo_root).items():
        if member.endswith(".htm"):
            by_archive[archive].append(member)
    for archive, names in sorted(by_archive.items()):
        with tarfile.open(repo_root / EXPORT / archive) as opened:
            for name in sorted(names):
                add(name[len(EXPORT_MEMBER_PREFIX):], opened.extractfile(name).read())
    return found


def registered_ciks(company_id, repo_root=REPO):
    """Every CIK the registry names for the company, whatever its role."""
    with (repo_root / "config/company_registry.csv").open(encoding="utf-8") as opened:
        for row in csv.DictReader(opened):
            if row["company_id"] == company_id:
                return sorted({str(int(role.split(":", 1)[1])) for role in row["roles"].split(";")
                               if role})
    raise SystemExit("COMPANY_NOT_REGISTERED:" + company_id)


def read_year(*, proxies, period, result_filings, published):
    """One position: every proxy's PEO total for ``period``, and the verdict."""
    key, reports = tuple(period), []
    for proxy in proxies:
        kept, set_aside = peo_totals_for(peo_totals(proxy["text"], contexts_of(proxy["text"])), key)
        if not kept and not set_aside:
            continue
        accession = accession_of_document(repo_root=REPO, document=proxy["document"])[0]
        report = {"document": proxy["document"], "sha256": proxy["sha256"],
                  "accession": accession,
                  "values": [_number(v) for v in sorted({t["value"] for t in kept})],
                  "named_by_the_result": accession in result_filings}
        if set_aside:
            report["placeholders_set_aside"] = set_aside
        reports.append(report)
    reports.sort(key=lambda report: report["accession"])
    amounts = {value for report in reports for value in report["values"]}
    why = (None if reports and all(len(r["values"]) == 1 for r in reports) and len(amounts) == 1
           and any(not r["named_by_the_result"] for r in reports)
           else "NO_SAVED_PROXY_REPORTS_THE_TARGET_PERIOD" if not reports
           else "SEVERAL_PEO_TOTALS_IN_ONE_PROXY" if any(len(r["values"]) != 1 for r in reports)
           else "PROXIES_REPORT_DIFFERENT_AMOUNTS" if len(amounts) > 1
           else "ONLY_THE_FILING_THE_RESULT_NAMES_REPORTS_IT")
    read = None if why else Decimal(str(next(iter(amounts))))
    return {"published": published, "read": None if read is None else str(read),
            "why_not_read": why, "proxies_reporting_the_target_period": reports,
            "opened_filings_the_result_names": sorted(r["accession"] for r in reports
                                                      if r["named_by_the_result"]),
            "verdict": ("NO_PUBLISHED_VALUE" if published is None
                        else "NOT_READ" if read is None
                        else "MATCH" if read == Decimal(published) else "DIFFERS")}


def main():
    from bind_acceptance_readings import identity_for
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reading", required=True)
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    proxies = saved_proxies()
    positions = {}
    for company_id, report_end, label in reading_cases(arguments.reading):
        selection = select_receipt(found=index.get((company_id, "C03", report_end), []),
                                   closure=arguments.closure)
        result = selection["result"]
        if result is None or result.get("value") is None:
            raise SystemExit("NO_PUBLISHED_RESULT:" + label)
        ciks = registered_ciks(company_id)
        period = [result["period_start"], result["period_end"]]
        entry = {"company_id": company_id, "period_end": report_end, "ciks": ciks,
                 "period": period,
                 **read_year(proxies=[proxy for cik in ciks for proxy in proxies.get(cik, [])],
                             period=period,
                             result_filings=set(result.get("filings") or ()),
                             published=str(result["value"]))}
        identity, refusal = identity_for(
            position={"company_id": company_id, "metric_id": "C03", "period_end": report_end,
                      "published": entry["published"],
                      "reading_filings": entry["opened_filings_the_result_names"],
                      "reading_window": period, "filings_are_the_whole_set": False},
            index=index, closure=arguments.closure)
        if refusal is not None:
            raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + refusal)
        identity["established_by"] = "RECORDED_AT_READING_TIME"
        entry["checked_identity"] = identity
        positions[label] = entry
        print(label, entry["verdict"], entry["why_not_read"] or "", flush=True)
    body = {"record_type": "ISSUE47_C03_ACROSS_PROXIES_READING", "reading": arguments.reading,
            "requirement_closure_hash": arguments.closure,
            "reader": "tools/read_c03_across_proxies.py",
            "proxies_read": sum(len(found) for found in proxies.values()),
            "per_position": positions, "calls": {"sec": 0, "provider": 0}}
    (REPO / arguments.output).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                         encoding="utf-8")


if __name__ == "__main__":
    main()
