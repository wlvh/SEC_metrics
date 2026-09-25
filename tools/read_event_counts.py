"""Count the 8-K event metrics from the filings' own SEC headers.

C01 and E02-E05 are counts of 8-K filings carrying one item code; E01 adds a
keyword rule over item 8.01, which a header count cannot check and which
tools/read_e01_eight_o_ones.py reads instead. This selects the 8-K and 8-K/A
filings in the pinned fiscal window from the saved submissions index - the
ledger's latest successful copy, the one the route reads - takes each one's
item codes from its own hdr.sgml, and counts against catalog/event_routes.json.
It does not call the route's source discovery or claim builder.

The window's bounding date is not assumed: the filing date and the report
date are both counted, and a count accepted only if both agree.

It replaces a reading whose code was never committed. That copy found its
submissions index with an unsorted glob over every saved attempt - so which
copy it read depended on directory order - and took its published values from
a batch directory it named. Here the index is the ledger's, and published
values come from a named runs root and Requirement closure.

Usage:
    python3 tools/read_event_counts.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under>
"""
import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

OUT = "docs/evidence/issue47_history/content-acceptance/event-count-read.json"
CASES = [("marriott_international", "2025-12-31", "marriott-2025"),
         ("ford_motor_company", "2025-12-31", "ford-2025"),
         ("pfizer", "2025-12-31", "pfizer-2025"),
         ("lumen_technologies", "2025-12-31", "lumen-2025"),
         ("enphase_energy", "2025-12-31", "enphase-2025"),
         ("southwest_airlines", "2025-12-31", "southwest-2025"),
         ("macys", "2026-01-31", "macys-2026")]


def _routes():
    return json.loads((REPO / "catalog/event_routes.json").read_text(encoding="utf-8"))["routes"]


def _accession_directory(cik, accession):
    flat = accession.replace("-", "")
    found = sorted((REPO / "evidence/accession_materials").glob(
        "*_" + str(int(cik)) + "_" + flat))
    return found[0] if found else None


def header_items(cik, accession):
    """The item codes this filing's own SEC header declares, or None if unsaved."""
    directory = _accession_directory(cik, accession)
    headers = sorted(directory.glob("*.hdr.sgml")) if directory else []
    if not headers:
        return None
    text = headers[0].read_text(encoding="utf-8", errors="replace")
    return sorted({line.strip() for line in re.findall(r"^<ITEMS>(.+)$", text, re.M)})


def keyword_hit(cik, accession, aliases):
    """The catalog's SUBSTRING_ANY rule over every saved document of the filing.

    Kept so this reading's E01 column is what it always was - a literal reading
    over the whole document - and not used to accept E01.
    """
    directory = _accession_directory(cik, accession)
    for document in sorted(directory.glob("*.htm")) if directory else []:
        plain = re.sub(r"<[^>]+>", " ", document.read_text(encoding="utf-8-sig",
                                                           errors="replace"))
        plain = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", plain).casefold())
        if any(alias.casefold() in plain for alias in aliases):
            return True
    return False


def filings_in_index(submissions):
    recent = submissions["filings"]["recent"]
    columns = {name: recent[name] for name in
               ("form", "accessionNumber", "filingDate", "reportDate")}
    return [dict(zip(columns, values)) for values in zip(*columns.values())]


def count_window(*, filings, cik, start, end):
    """Per metric, per window basis; plus the filings each basis admitted.

    8-K and 8-K/A both: an amendment carrying the item is its own entry in the
    approved event list keyed by accession.
    """
    routes = _routes()
    counts = {basis: collections.Counter() for basis in ("filing_date", "report_date")}
    seen = {basis: [] for basis in counts}
    unreadable = []
    for filing in filings:
        if not filing["form"].startswith("8-K"):
            continue
        for basis, field in (("filing_date", "filingDate"), ("report_date", "reportDate")):
            date = filing[field]
            if not date or not start <= date <= end:
                continue
            items = header_items(cik, filing["accessionNumber"])
            if items is None:
                unreadable.append(filing["accessionNumber"])
                continue
            seen[basis].append({"accession": filing["accessionNumber"], "items": items,
                                field: date})
            for metric, route in routes.items():
                if set(items) & set(route["direct_item_codes"]):
                    counts[basis][metric] += 1
                elif any(rule["item_code"] in items
                         and keyword_hit(cik, filing["accessionNumber"], rule["aliases"])
                         for rule in route["keyword_item_rules"]):
                    counts[basis][metric] += 1
    return counts, seen, sorted(set(unreadable))


def verdict(*, published, by_filing_date, by_report_date):
    if published is None:
        return "NO_PUBLISHED_VALUE"
    agreeing = [basis for basis, count in (("filing_date", by_filing_date),
                                           ("report_date", by_report_date))
                if str(count) == str(published)]
    if len(agreeing) == 2:
        return "MATCH_BOTH_BASES"
    return "MATCH_ON_" + agreeing[0].upper() if agreeing else "DIFFERS"


def _case_input(*, company_id, report_end):
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                         report_end=report_end)
    prepared = prepare_historical_annual_input(repo_root=REPO, company_id=company_id,
                                               period_selection=selection)
    return prepared["original_input"]["table_input"]["target_period"], prepared["entity"]


def main():
    from bind_acceptance_readings import identity_for
    from sec_urls import submissions_url
    from vnext.annual_update import saved_source
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    previous = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    positions = {}
    for company_id, report_end, label in CASES:
        period, cik = _case_input(company_id=company_id, report_end=report_end)
        url = submissions_url(cik=int(cik))
        saved = saved_source(repo_root=REPO, url=url)
        if saved is None:
            raise SystemExit("SUBMISSIONS_INDEX_NOT_SAVED:" + url)
        start, end = period["period_start"], period["period_end"]
        counts, seen, unreadable = count_window(
            filings=filings_in_index(json.loads(saved["raw"])), cik=cik, start=start, end=end)
        rows = {}
        for metric in sorted(_routes()):
            result = select_receipt(found=index.get((company_id, metric, report_end), []),
                                    closure=arguments.closure)["result"]
            published = (None if result is None or result.get("value") is None
                         else str(result["value"]))
            row = {"published": published,
                   "by_filing_date": counts["filing_date"][metric],
                   "by_report_date": counts["report_date"][metric]}
            row["verdict"] = verdict(published=published, by_filing_date=row["by_filing_date"],
                                     by_report_date=row["by_report_date"])
            if published is not None:
                identity, refusal = identity_for(
                    position={"company_id": company_id, "metric_id": metric,
                              "period_end": report_end, "published": published,
                              "reading_filings": [f["accession"] for f in seen["filing_date"]],
                              "reading_window": [start, end],
                              "filings_are_the_whole_set": True},
                    index=index, closure=arguments.closure)
                if refusal is not None:
                    raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + metric + ":"
                                     + refusal)
                identity["established_by"] = "RECORDED_AT_READING_TIME"
                row["checked_identity"] = identity
            rows[metric] = row
        positions[label] = {
            "company_id": company_id, "window": [start, end],
            "submissions_index": saved["proof"]["request_repo_relative_path"],
            "eight_ks_in_window": {basis: len(entries) for basis, entries in seen.items()},
            "headers_not_saved": unreadable, "metrics": rows, "filings": seen,
            "e01_keyword_rule_note": ("E01's column is the literal alias rule over "
                                      "every saved document of each 8.01 filing; "
                                      "it is recorded, and E01 is accepted only "
                                      "from e01-eight-o-one-read.json")}
        print(label, {metric: row["verdict"] for metric, row in rows.items()}, flush=True)
    owned = {"per_position", "result", "reader", "requirement_closure_hash", "calls"}
    body = {key: value for key, value in previous.items() if key not in owned}
    verdicts = collections.Counter(row["verdict"] for position in positions.values()
                                   for metric, row in position["metrics"].items()
                                   if metric != "E01")
    body.update({"reader": "tools/read_event_counts.py",
                 "requirement_closure_hash": arguments.closure,
                 "per_position": positions,
                 "result": {"positions_compared_excluding_e01": sum(verdicts.values()),
                            **dict(sorted(verdicts.items()))},
                 "calls": {"provider": 0, "paid": 0, "sec": 0}})
    (REPO / OUT).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False)
                            + "\n", encoding="utf-8")
    print(body["result"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
