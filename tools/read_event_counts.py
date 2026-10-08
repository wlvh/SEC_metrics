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

A position whose results ran under another closure is read into a reading of
its own rather than into this one, whose positions all compare results of one
closure:

    python3 tools/read_event_counts.py --runs-root <root> --closure sha256:<...> \
        --case <label>=<company_id>:<report_end> \
        --output docs/evidence/issue47_history/content-acceptance/<name>.json

A year whose 8-Ks only the acquisition saved is read over a root restored from
its export (``--source-root``). That root keeps the checkout's accession
materials and holds the acquired files as immutable request attempts, so a
header is read from the accession materials when they hold it and otherwise
from the root's request ledger: its latest GET of the header's URL, which must
have succeeded and whose saved bytes must have the digest the ledger recorded.
The path read is recorded beside the filing, so the test reads the same bytes
back out of the export. E01 is not counted over such a root: its keyword rule
reads every saved document of a filing, and a filing only the acquisition
saved has its primary document only.

A window that reaches a history block is read over the blocks too: each
block the window may reach is read from the ledger's latest successful copy,
and only if the block is the one its index declares - as many filings as the
index says, every one filed inside the declared range or on the day SEC leaves
after it. A block that is not is refused, not read around: a count over a
stale block is not a count of the window. The blocks read are recorded with
the position, so the test reads the same bytes back.

A filing in the window whose header cannot be read makes the position
NOT_READ, even when the count it did make happens to equal the published
value.

A successor registrant's year is counted over the window the approved policy
gives it (``catalog/zero_ai_public_projection.json``'s
``event_window_policy_by_continuity``): from the previous calendar year's
start, over the 8-Ks of every CIK the registry names for the company, because
the pinned year's events were filed partly by the predecessor. The window is
derived here from the policy and the period, not taken from the result; a
result that measured another window is refused, not compared.
"""
import argparse
import collections
import csv
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

OUT = "docs/evidence/issue47_history/content-acceptance/event-count-read.json"
EVENT_FORMS = ("8-K", "8-K/A")
from acceptance_readings import reading_cases  # noqa: E402
CASES = reading_cases("event_counts")


def _routes():
    return json.loads((REPO / "catalog/event_routes.json").read_text(encoding="utf-8"))["routes"]


def _accession_directory(cik, accession, root=REPO):
    flat = accession.replace("-", "")
    found = sorted((root / "evidence/accession_materials").glob(
        "*_" + str(int(cik)) + "_" + flat))
    return found[0] if found else None


def items_of(text):
    """The item codes an SEC header declares."""
    return sorted({line.strip() for line in re.findall(r"^<ITEMS>(.+)$", text, re.M)})


def header_items(cik, accession, root=REPO):
    """The item codes this filing's own SEC header declares, or None if unsaved."""
    directory = _accession_directory(cik, accession, root)
    headers = sorted(directory.glob("*.hdr.sgml")) if directory else []
    if not headers:
        return None
    return items_of(headers[0].read_text(encoding="utf-8", errors="replace"))


def ledger_rows(root):
    """A root's request ledger, in order."""
    with (root / "evidence/requests_log.csv").open(encoding="utf-8", newline="") as opened:
        return list(csv.DictReader(opened))


def latest_saved(*, root, rows, url):
    """``(bytes, repo_relative_path)`` of the ledger's latest GET of ``url``, or None.

    None when the ledger never asked for it or its latest request failed: a
    failed latest request is not read around. Saved bytes without the digest
    the ledger recorded stop the reading.
    """
    matching = [row for row in rows if row["source_url"] == url and row["method"] == "GET"]
    if not matching or matching[-1]["status_code"] != "200" or matching[-1]["error"]:
        return None
    data = (root / matching[-1]["repo_relative_path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != matching[-1]["content_sha256"]:
        raise SystemExit("SAVED_BYTES_DIFFER_FROM_THE_LEDGER:" + url)
    return data, matching[-1]["repo_relative_path"]


def restored_root_headers(root):
    """A header reader over a restored root: ``(cik, accession) -> (items, path or None)``."""
    from sec_urls import hdr_sgml_url
    rows = ledger_rows(root)

    def read(cik, accession):
        items = header_items(cik, accession, root)
        if items is not None:
            return items, None
        saved = latest_saved(root=root, rows=rows,
                             url=hdr_sgml_url(cik=int(cik), accession=accession))
        if saved is None:
            return None, None
        return items_of(saved[0].decode("utf-8", errors="replace")), saved[1]
    return read


def history_blocks_reached(submissions, start):
    """The index's history blocks a window starting at ``start`` may reach.

    SEC leaves one day between two blocks' declared ranges and files that
    day's filings in the older block, so a block reaches through the day after
    its declared end. A filing dated in the window by either basis was filed on
    or after ``start`` (its report date is not later than its filing date), so
    a block ending more than a day before ``start`` holds none of them.
    """
    return [item["name"] for item in submissions["filings"]["files"]
            if (date.fromisoformat(item["filingTo"]) + timedelta(days=1)).isoformat() >= start]


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


def event_window(*, company_id, period, cik, root=REPO):
    """The window this position's count measures, and the CIKs whose 8-Ks it counts.

    Returns:
        ``((start, end), [cik, ...], policy)``: the fiscal window and the period's
        own registrant, unless that registrant is the company's successor - then
        the approved successor window and every registered CIK.
    """
    with (root / "config/company_registry.csv").open(encoding="utf-8") as opened:
        rows = [row for row in csv.DictReader(opened) if row["company_id"] == company_id]
    if len(rows) != 1:
        raise SystemExit("COMPANY_NOT_REGISTERED_ONCE:" + company_id)
    roles = {str(int(entry.split(":", 1)[1])): entry.split(":", 1)[0]
             for entry in rows[0]["roles"].split(";") if entry}
    if not (rows[0]["entity_continuity_status"] == "successor_predecessor"
            and roles.get(str(int(cik))) == "successor"):
        return (period["period_start"], period["period_end"]), [str(int(cik))], "TARGET_PERIOD"
    policies = json.loads((root / "catalog/zero_ai_public_projection.json").read_text(
        encoding="utf-8"))["event_window_policy_by_continuity"]
    policy = policies["successor_predecessor"]
    if policy != "PRIOR_CALENDAR_YEAR_START_TO_TARGET_END":
        raise SystemExit("EVENT_WINDOW_POLICY_NOT_READ_HERE:" + policy)
    start = "{}-01-01".format(int(period["fiscal_year"]) - 1)
    return (start, period["period_end"]), sorted(roles, key=int), policy


def _rows(table, where):
    columns = {name: table[name] for name in ("form", "accessionNumber", "filingDate", "reportDate")}
    if len({len(values) for values in columns.values()}) != 1:
        raise SystemExit("FILING_COLUMNS_OF_UNEQUAL_LENGTH:" + where)
    return [dict(zip(columns, values)) for values in zip(*columns.values())]


def filings_in_index(submissions):
    return _rows(submissions["filings"]["recent"], "recent")


def block_filings(*, submissions, name, raw):
    """A history block's filings, refused unless it is the block its index declares.

    The index declares each block's range and number of filings. SEC leaves
    one day between two blocks' ranges and files that day's filings in the
    older block, so a filing may be dated the day after the declared end.
    """
    declared = [item for item in submissions["filings"]["files"] if item["name"] == name]
    if len(declared) != 1:
        raise SystemExit("HISTORY_BLOCK_NOT_DECLARED_ONCE:" + name)
    declared = declared[0]
    rows = _rows(json.loads(raw), name)
    last = (date.fromisoformat(declared["filingTo"]) + timedelta(days=1)).isoformat()
    if len(rows) != int(declared["filingCount"]) or any(
            not declared["filingFrom"] <= row["filingDate"] <= last for row in rows):
        raise SystemExit("HISTORY_BLOCK_IS_NOT_THE_ONE_ITS_INDEX_DECLARES:" + name)
    return rows


def unique_filings(filings):
    """One entry per accession; the same accession listed twice must say the same."""
    kept = {}
    for filing in filings:
        if kept.setdefault(filing["accessionNumber"], filing) != filing:
            raise SystemExit("A_FILING_IS_LISTED_TWICE_DIFFERENTLY:" + filing["accessionNumber"])
    return list(kept.values())


def count_window(*, filings, cik, start, end, header=None, metrics=None):
    """Per metric, per window basis; plus the filings each basis admitted.

    8-K and 8-K/A both: an amendment carrying the item is its own entry in the
    approved event list keyed by accession. ``header`` reads a filing's item
    codes and the path read, ``(None, None)`` if unsaved; by default the
    checkout's accession materials, whose path is not recorded.
    """
    header = header or (lambda cik, accession: (header_items(cik, accession), None))
    routes = {metric: route for metric, route in _routes().items()
              if metrics is None or metric in metrics}
    counts = {basis: collections.Counter() for basis in ("filing_date", "report_date")}
    seen = {basis: [] for basis in counts}
    unreadable = []
    for filing in filings:
        # Form 8-K and its amendment, as the approved event routes count them.
        # A prefix test also admitted 8-K12B and 8-K12B/A - a successor's
        # registration 8-K - which no event route reads.
        if filing["form"] not in EVENT_FORMS:
            continue
        for basis, field in (("filing_date", "filingDate"), ("report_date", "reportDate")):
            day = filing[field]
            if not day or not start <= day <= end:
                continue
            items, path = header(cik, filing["accessionNumber"])
            if items is None:
                unreadable.append(filing["accessionNumber"])
                continue
            entry = {"accession": filing["accessionNumber"], "items": items, field: day}
            if path is not None:
                entry["header"] = path
            seen[basis].append(entry)
            for metric, route in routes.items():
                if set(items) & set(route["direct_item_codes"]):
                    counts[basis][metric] += 1
                elif any(rule["item_code"] in items
                         and keyword_hit(cik, filing["accessionNumber"], rule["aliases"])
                         for rule in route["keyword_item_rules"]):
                    counts[basis][metric] += 1
    return counts, seen, sorted(set(unreadable))


def verdict(*, published, by_filing_date, by_report_date, unreadable=()):
    if published is None:
        return "NO_PUBLISHED_VALUE"
    if unreadable:
        # A count that skipped a filing it could not read is not a count of
        # the window, even when it happens to equal the published value.
        return "NOT_READ"
    agreeing = [basis for basis, count in (("filing_date", by_filing_date),
                                           ("report_date", by_report_date))
                if str(count) == str(published)]
    if len(agreeing) == 2:
        return "MATCH_BOTH_BASES"
    return "MATCH_ON_" + agreeing[0].upper() if agreeing else "DIFFERS"


def _case(text):
    """``label=company_id:report_end`` from the command line."""
    label, _, rest = text.partition("=")
    company_id, _, report_end = rest.partition(":")
    if not (label and company_id and report_end):
        raise SystemExit("CASE_NOT_LABEL_EQUALS_COMPANY_COLON_PERIOD:" + text)
    return company_id, report_end, label


def _fresh_body():
    """A new reading, described the way the default one is - its method, none of its history."""
    main = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    kept = ("record_type", "issue", "what_this_is", "both_window_bases",
            "e01_is_the_one_route_this_cannot_read", "production_authorized")
    return {**{key: main[key] for key in kept if key in main}, "same_method_as": OUT}


def _case_input(*, company_id, report_end, source_root=REPO):
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    # A restored root's saved sources are proved through its acquisition
    # checkpoint; one replay per ledger state, as a frame's plan does.
    with checkpoint_replayed_once():
        selection = resolve_period_selection(repo_root=source_root, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_annual_input(repo_root=source_root, company_id=company_id,
                                                   period_selection=selection)
    return prepared["original_input"]["table_input"]["target_period"], prepared["entity"]


def main():
    from bind_acceptance_readings import identity_for
    from sec_urls import submissions_file_url, submissions_url
    from vnext.annual_update import saved_source
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    parser.add_argument("--case", action="append", type=_case,
                        help="label=company_id:report_end; replaces the default cases")
    parser.add_argument("--output", default=OUT)
    parser.add_argument("--source-root", type=Path, default=None,
                        help="a data root holding filings the checkout does not, "
                             "such as one restored from the acquisition's export")
    arguments = parser.parse_args()
    cases = arguments.case or CASES
    if arguments.case and arguments.output == OUT:
        raise SystemExit("A_CASE_OF_ITS_OWN_IS_WRITTEN_TO_A_READING_OF_ITS_OWN")
    if arguments.source_root is not None and arguments.output == OUT:
        raise SystemExit("A_SOURCE_ROOT_READING_IS_WRITTEN_TO_A_READING_OF_ITS_OWN")
    source = REPO if arguments.source_root is None else arguments.source_root.resolve()
    header = None if arguments.source_root is None else restored_root_headers(source)
    metrics = None if arguments.source_root is None else sorted(
        metric for metric, route in _routes().items() if not route["keyword_item_rules"])
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    output = REPO / arguments.output
    previous = (json.loads(output.read_text(encoding="utf-8")) if output.exists()
                else _fresh_body())
    positions = {}
    for company_id, report_end, label in cases:
        period, cik = _case_input(company_id=company_id, report_end=report_end,
                                  source_root=source)
        (start, end), ciks, policy = event_window(company_id=company_id, period=period,
                                                  cik=cik, root=source)
        # A result that measured another window than the one derived here is
        # not a count of this one, and is not compared.
        measured = {(result["period_start"], result["period_end"])
                    for metric in sorted(_routes())
                    for result in [select_receipt(found=index.get((company_id, metric, report_end), []),
                                                  closure=arguments.closure)["result"]]
                    if result is not None and result.get("value") is not None}
        if measured - {(start, end)}:
            raise SystemExit("RESULT_WINDOW_IS_NOT_THE_DERIVED_WINDOW:" + label + ":"
                             + json.dumps(sorted(measured)))
        counts = {basis: collections.Counter() for basis in ("filing_date", "report_date")}
        seen = {basis: [] for basis in counts}
        unreadable, indexes, blocks = [], {}, {}
        for registrant in ciks:
            url = submissions_url(cik=int(registrant))
            saved = saved_source(repo_root=source, url=url)
            if saved is None:
                raise SystemExit("SUBMISSIONS_INDEX_NOT_SAVED:" + url)
            indexes[registrant] = saved["proof"]["request_repo_relative_path"]
            submissions = json.loads(saved["raw"])
            filings = filings_in_index(submissions)
            for name in history_blocks_reached(submissions, start):
                block = saved_source(repo_root=source, url=submissions_file_url(file_name=name))
                if block is None:
                    raise SystemExit("HISTORY_BLOCK_NOT_SAVED:" + label + ":" + name)
                blocks.setdefault(registrant, {})[name] = block["proof"]["request_repo_relative_path"]
                filings.extend(block_filings(submissions=submissions, name=name, raw=block["raw"]))
            each, admitted, missing = count_window(
                filings=unique_filings(filings), cik=registrant, start=start, end=end,
                header=header, metrics=metrics)
            for basis in counts:
                counts[basis].update(each[basis])
                seen[basis].extend(entry if len(ciks) == 1 else {**entry, "cik": registrant}
                                   for entry in admitted[basis])
            unreadable.extend(missing)
        unreadable = sorted(set(unreadable))
        rows = {}
        for metric in sorted(metrics or _routes()):
            result = select_receipt(found=index.get((company_id, metric, report_end), []),
                                    closure=arguments.closure)["result"]
            published = (None if result is None or result.get("value") is None
                         else str(result["value"]))
            row = {"published": published,
                   "by_filing_date": counts["filing_date"][metric],
                   "by_report_date": counts["report_date"][metric]}
            row["verdict"] = verdict(published=published, by_filing_date=row["by_filing_date"],
                                     by_report_date=row["by_report_date"],
                                     unreadable=unreadable)
            if published is not None and row["verdict"] != "NOT_READ":
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
            "submissions_index": indexes[str(int(cik))],
            "eight_ks_in_window": {basis: len(entries) for basis, entries in seen.items()},
            "headers_not_saved": unreadable, "metrics": rows, "filings": seen,
            "e01_keyword_rule_note": (
                ("E01's column is the literal alias rule over every saved document of "
                 "each 8.01 filing; it is recorded, and E01 is accepted only from "
                 "e01-eight-o-one-read.json") if metrics is None else
                ("E01 is not counted over a restored root: its keyword rule reads every "
                 "saved document of a filing, and a filing only the acquisition saved "
                 "has its primary document only"))}
        if blocks:
            positions[label]["history_blocks"] = blocks
        if len(ciks) > 1:
            positions[label].update({"window_policy": policy, "registered_ciks": ciks,
                                     "submissions_indexes": indexes})
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
    output.write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(body["result"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
