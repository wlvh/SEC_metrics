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
another year is set aside as read_governance_facts sets it aside.

A year two proxies report differently (c03-first-ecd-release/: Marriott
corrects its 2022 total, Macy's reports fiscal 2023 net of a clawback) is not
chosen between by this reading. The owner chose how (the c03-convention.json
decision record, answer A: a year's value is the value as first reported),
so when that record says A the year is read as its first report: the earliest
proxy's single total, which must be the filing the result names, with every
later amount recorded beside it. That value is confirmed only by the route's
own filing read with this code - the standard the latest years' C03 meet -
and the reading says so. Without the decision the year stays NOT_READ.

A first report the tags cannot reach - a proxy filed before the
pay-versus-performance table was required tags no total - is read, in that
same case only (the proxies disagree and the earliest tagged one is not the
filing the result names), off the Summary Compensation Table of the result's
own filing (table_total): the row of the person the tagged proxies name as the
year's PEO (ecd:PeoName), accepted only when its components add up to its
total, and only when that filing was filed before every tagged report.

It imports none of the route's governance modules. The published value and
the filings the result names come from a named runs root and closure.

Usage:
    python3 tools/read_c03_across_proxies.py --reading <positions.json reading> \
        --runs-root <flat runs root> --closure sha256:<closure> --output <reading path>
"""
import argparse
import csv
import hashlib
import html
import json
import re
import sys
import tarfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import (EXPORT, EXPORT_MEMBER_PREFIX, ReadingError,  # noqa: E402
                                 _export_members, accession_of_document, reading_cases)
from read_governance_facts import contexts_of, peo_totals, peo_totals_for  # noqa: E402

_CIK = re.compile(r'name="dei:EntityCentralIndexKey"[^>]*>(?:<[^>]+>)*\s*([0-9]+)')
def _decision_path():
    """The owner's C03 convention record, found by its name among the decision records.

    The decision directories are named for the day each decision was made; the
    code names the record, not the day, and there must be exactly one.
    """
    found = sorted((REPO / "docs/evidence/issue47_history").glob(
        "owner-decisions-*/c03-convention.json"))
    if len(found) != 1:
        raise SystemExit("C03_CONVENTION_DECISION_IS_NOT_ONE_FILE:" + str(len(found)))
    return str(found[0].relative_to(REPO))


DECISION = _decision_path()


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


def documents_of_filings(accessions, repo_root=REPO):
    """Every saved .htm document (the checkout's and the acquisition export's) of the named filings.

    Returns:
        ``[{"document", "sha256", "text"}]``; the document is its path relative
        to the saved data root, as saved_proxies gives it.
    """
    found, seen = [], set()

    def add(relative, data):
        digest = hashlib.sha256(data).hexdigest()
        if digest not in seen:
            seen.add(digest)
            found.append({"document": relative, "sha256": digest,
                          "text": data.decode("utf-8-sig", errors="replace")})

    wanted = set(accessions)

    def belongs(relative):
        # A document whose filing the saved material does not establish (an
        # attempt saved with two header files) cannot be shown to be one of
        # the named filings, so it is not read as one.
        try:
            return accession_of_document(repo_root=repo_root, document=relative)[0] in wanted
        except ReadingError:
            return False

    for path in sorted(repo_root.glob("evidence/accession_materials/*/*.htm")) + sorted(
            repo_root.glob("evidence/request_attempts/*/*/*.htm")):
        relative = str(path.relative_to(repo_root))
        if belongs(relative):
            add(relative, path.read_bytes())
    by_archive = defaultdict(list)
    for member, (archive, _) in _export_members(repo_root).items():
        relative = member[len(EXPORT_MEMBER_PREFIX):]
        if member.endswith(".htm") and belongs(relative):
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


def first_reported_decision(repo_root=REPO):
    """The decision record's path when it says a year is its first report, else None."""
    record = json.loads((repo_root / DECISION).read_text(encoding="utf-8"))
    return DECISION if record.get("answer_verbatim") == "A" else None


def _filed_year(accession):
    """The two-digit year an accession number carries (its filer prefix is not an order)."""
    return int(accession.split("-")[1])


_NON_NUMERIC = re.compile(r"<ix:nonNumeric([^>]*)>(.*?)</ix:nonNumeric>", re.S)
_ATTRIBUTE = re.compile(r'([a-zA-Z:\-]+)="([^"]*)"')
_DASHES = {"—", "–", "-", "--"}
# Two of the columns Item 402(c)(2) prescribes for the Summary Compensation
# Table; a proxy's other pay tables (the committee's own view of the year's
# award, say) also open with name, year, salary and total.
_STOCK_AWARDS = re.compile(r"(?i)stock\s*awards")
_ALL_OTHER = re.compile(r"(?i)all\s*other\s*compensation")


def _cell_text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def peo_names_for(proxies, key):
    """The names the tagged proxies give the year's PEO (ecd:PeoName in the year's context)."""
    names = set()
    for proxy in proxies:
        contexts = contexts_of(proxy["text"])
        for tag in _NON_NUMERIC.finditer(proxy["text"]):
            attributes = dict(_ATTRIBUTE.findall(tag.group(1)))
            if attributes.get("name") != "ecd:PeoName":
                continue
            context = contexts.get(attributes.get("contextRef"))
            if context is not None and (context["start"], context["end"]) == tuple(key):
                names.add(_cell_text(tag.group(2)))
    return names


def table_total(*, text, name, year):
    """``name``'s Summary Compensation Table total for ``year`` in a proxy that tags nothing.

    Read off the table, not the route's governance modules: the table is the
    one whose header row has the Year, Salary, Stock awards, All other
    compensation and Total columns (the last four prescribed by Item 402(c)(2);
    JPMorgan's 2022 proxy also prints the committee's own view of the year's
    award under name, year, salary and total, which is not that table); a row belongs to the person whose name opens it (a row that opens
    with a year continues the person above). The row's amounts are its cells
    after the year that are written as amounts or as a dash (a dash is zero);
    a lone "$" and a one- or two-digit footnote mark are not amounts. It is
    read only if it has one amount per component column plus the total, and
    the components add up to the total - the table's own arithmetic.

    Returns:
        ``{"total", "components", "header"}`` or ``{"refused": why}``.
    """
    found = []
    for table in re.findall(r"<table\b.*?</table>", text, re.S | re.I):
        rows = [[_cell_text(cell) for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S | re.I)]
                for row in re.findall(r"<tr\b.*?</tr>", table, re.S | re.I)]
        rows = [[cell for cell in row if cell] for row in rows]
        header = next((row for row in rows if "Year" in row
                       and any(cell.startswith("Salary") for cell in row)
                       and any(cell.startswith("Total") for cell in row)
                       and any(_STOCK_AWARDS.match(cell) for cell in row)
                       and any(_ALL_OTHER.match(cell) for cell in row)), None)
        if header is None:
            continue
        components = len(header) - header.index("Year") - 2
        person = None
        for row in rows[rows.index(header) + 1:]:
            if not row:
                continue
            if not re.fullmatch(r"(19|20)\d\d", row[0]):
                person, row = row[0], row[1:]
            if not row or row[0] != year or person is None or not person.startswith(name):
                continue
            amounts = []
            for cell in row[1:]:
                if cell == "$" or re.fullmatch(r"\d{1,2}", cell):
                    continue
                if cell in _DASHES:
                    amounts.append(Decimal(0))
                    continue
                try:
                    amounts.append(Decimal(cell.replace("$", "").replace(",", "")))
                except InvalidOperation:
                    amounts = None
                    break
            found.append({"header": header, "person": person, "amounts": amounts,
                          "components": components})
    if len(found) != 1:
        return {"refused": "THE_NAMED_PEO_HAS_" + str(len(found)) + "_ROWS_FOR_THE_YEAR"}
    row = found[0]
    if row["amounts"] is None or len(row["amounts"]) != row["components"] + 1:
        return {"refused": "THE_ROW_IS_NOT_ONE_AMOUNT_PER_COLUMN"}
    if sum(row["amounts"][:-1]) != row["amounts"][-1]:
        return {"refused": "THE_COMPONENTS_DO_NOT_ADD_UP_TO_THE_TOTAL"}
    return {"total": row["amounts"][-1], "components": [_number(v) for v in row["amounts"][:-1]],
            "header": row["header"], "person_cell": row["person"]}


def untagged_reports(*, documents, proxies, period, result_filings):
    """The first reports the tags cannot reach: the result's own proxies that tag nothing, read off their table.

    ``documents`` are saved documents ``{"document", "sha256", "text"}`` of
    the registrant. A document is read only if it belongs to a filing the
    result names, carries no PEO total tag, and the tagged proxies name one
    PEO for the year (``ecd:PeoName``); that name picks the table's row, so the
    person is identified by documents the route did not read.
    """
    names = peo_names_for(proxies, period)
    reports = []
    for document in documents:
        if "PeoTotalCompAmt" in document["text"] or "Summary Compensation Table" not in document["text"]:
            continue
        accession = accession_of_document(repo_root=REPO, document=document["document"])[0]
        if accession not in result_filings:
            continue
        report = {"document": document["document"], "sha256": document["sha256"],
                  "accession": accession, "named_by_the_result": True,
                  "read_from": "SUMMARY_COMPENSATION_TABLE",
                  "peo_names_in_the_tagged_proxies": sorted(names)}
        if len(names) != 1:
            report["refused"] = "THE_TAGGED_PROXIES_DO_NOT_NAME_ONE_PEO_FOR_THE_YEAR"
        else:
            read = table_total(text=document["text"], name=next(iter(names)), year=period[1][:4])
            if "refused" in read:
                report["refused"] = read["refused"]
            else:
                report.update({"values": [_number(read["total"])], "components": read["components"],
                               "header": read["header"], "person_cell": read["person_cell"]})
        reports.append(report)
    return reports


def read_year(*, proxies, period, result_filings, published, first_reported=None, untagged=None):
    """One position: every proxy's PEO total for ``period``, and the verdict.

    ``first_reported`` is the owner's decision record when it says a year's
    value is its first report; only then is a year the proxies disagree on read.
    ``untagged`` returns the first reports the tags cannot reach
    (untagged_reports); it is asked only when the earliest tagged proxy is not
    the filing the result names, so every other year is read as before.
    """
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
    first = {}
    if why == "PROXIES_REPORT_DIFFERENT_AMOUNTS" and first_reported is not None:
        earliest_year = min(_filed_year(r["accession"]) for r in reports)
        earliest = [r for r in reports if _filed_year(r["accession"]) == earliest_year]
        # One first report, carrying one total, which is the filing the route read.
        if (len(earliest) == 1 and len(earliest[0]["values"]) == 1
                and earliest[0]["named_by_the_result"]):
            read, why = Decimal(str(earliest[0]["values"][0])), None
            first = {"read_as": "FIRST_REPORTED", "decision": first_reported,
                     "first_report": earliest[0]["accession"],
                     "later_amounts": sorted({v for r in reports if r is not earliest[0]
                                              for v in r["values"]}),
                     "confirmed_only_by_the_filing_the_route_read": True}
        else:
            why = "FIRST_REPORT_NOT_ONE_TOTAL_IN_THE_FILING_THE_RESULT_NAMES"
            # A proxy filed before the pay-versus-performance table was
            # required tags no total, so the tags cannot reach a first report
            # there; the result's own filing is read off its table instead,
            # and only if it was filed before every tagged report.
            table = untagged() if untagged is not None else []
            before = [r for r in table if _filed_year(r["accession"]) < earliest_year]
            if table:
                first["untagged_first_reports"] = table
            if len(before) == 1 and len(before[0].get("values", ())) == 1:
                read, why = Decimal(str(before[0]["values"][0])), None
                first.update({"read_as": "FIRST_REPORTED", "decision": first_reported,
                              "first_report": before[0]["accession"],
                              "first_report_read_from": "SUMMARY_COMPENSATION_TABLE",
                              "later_amounts": sorted(amounts),
                              "confirmed_only_by_the_filing_the_route_read": True})
    return {"published": published, "read": None if read is None else str(read),
            "why_not_read": why, "proxies_reporting_the_target_period": reports, **first,
            "opened_filings_the_result_names": sorted(
                [r["accession"] for r in reports if r["named_by_the_result"]]
                + ([first["first_report"]] if first.get("first_report_read_from") else [])),
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
    decision = first_reported_decision()
    positions = {}
    for company_id, report_end, label in reading_cases(arguments.reading):
        selection = select_receipt(found=index.get((company_id, "C03", report_end), []),
                                   closure=arguments.closure)
        result = selection["result"]
        if result is None or result.get("value") is None:
            raise SystemExit("NO_PUBLISHED_RESULT:" + label)
        ciks = registered_ciks(company_id)
        period = [result["period_start"], result["period_end"]]
        registrant = [proxy for cik in ciks for proxy in proxies.get(cik, [])]
        filings = set(result.get("filings") or ())
        entry = {"company_id": company_id, "period_end": report_end, "ciks": ciks,
                 "period": period,
                 **read_year(proxies=registrant, period=period, result_filings=filings,
                             published=str(result["value"]), first_reported=decision,
                             untagged=lambda: untagged_reports(
                                 documents=documents_of_filings(filings), proxies=registrant,
                                 period=period, result_filings=filings))}
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
            "reader": "tools/read_c03_across_proxies.py", "first_reported_decision": decision,
            "proxies_read": sum(len(found) for found in proxies.values()),
            "per_position": positions, "calls": {"sec": 0, "provider": 0}}
    (REPO / arguments.output).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                         encoding="utf-8")


if __name__ == "__main__":
    main()
