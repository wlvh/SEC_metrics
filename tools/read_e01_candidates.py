"""Read E01's candidate items under its content-confirmed definition, from the filings' headers.

The owner's E01 counts a merger, acquisition, disposition or business
combination announcement only once its content confirms it
(catalog/r6/E01_content_confirmed_ma_v1.json). Confirming a candidate item is a
reading of its text that this tool does not make, so the one thing it can
establish is the case that needs no confirmation: a window with no candidate
item at all, whose answer under the definition is zero. For every other window
it records how many candidates there are and accepts nothing.

The window's 8-K and 8-K/A filings come from the ledger's latest saved
submissions index, and each filing's item codes from its own SEC header, the
way tools/read_event_counts.py reads the other event metrics; the window is
counted under both the filing date and the report date, and zero is accepted
only when both give no candidate and no header in the window is missing. The
candidate item codes are the successor route's own declaration. It does not
call the route's source discovery, its claim builder or its item reader.

Usage:
    python3 tools/read_e01_candidates.py --runs-root <root> --closure sha256:<closure> \
        --case <label>=<company_id>:<report_end> [--case ...] --output <path>
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

ROUTE = "catalog/r6/E01_content_confirmed_ma_v1.json"
# The reading made over the checkout. A reading over a restored root compares
# another closure's results and is written to a file of its own.
CHECKOUT_READING = "docs/evidence/issue47_history/content-acceptance/e01-content-confirmed-read.json"


def candidate_codes():
    """The item codes the content-confirmed definition reads as candidates."""
    route = json.loads((REPO / ROUTE).read_text(encoding="utf-8"))["route"]
    codes = route["candidate_item_codes"]
    if not codes or not all(isinstance(code, str) for code in codes):
        raise SystemExit("E01_ROUTE_DECLARES_NO_CANDIDATE_ITEM_CODES")
    return sorted(codes)


def window_candidates(*, filings, cik, start, end, codes, header=None):
    """Per basis, every 8-K in the window with its item codes and the candidates among them.

    ``header`` reads a filing's item codes and the path it read, ``(None, None)``
    when unsaved; by default the checkout's accession materials, whose path is
    not recorded. Over a restored root it is ``read_event_counts.
    restored_root_headers``, which records the path, so the reading can be
    recomputed from the export without the root.
    """
    from read_event_counts import header_items
    header = header or (lambda cik, accession: (header_items(cik, accession), None))
    seen, unreadable = {"filing_date": [], "report_date": []}, set()
    for filing in filings:
        if not filing["form"].startswith("8-K"):
            continue
        for basis, field in (("filing_date", "filingDate"), ("report_date", "reportDate")):
            date = filing[field]
            if not date or not start <= date <= end:
                continue
            items, path = header(cik, filing["accessionNumber"])
            if items is None:
                unreadable.add(filing["accessionNumber"])
                continue
            seen[basis].append({"accession": filing["accessionNumber"], field: date,
                                "items": items,
                                "candidate_items": sorted(set(items) & set(codes)),
                                **({"header": path} if path is not None else {})})
    return seen, sorted(unreadable)


def main():
    from bind_acceptance_readings import identity_for
    from read_event_counts import (_case, _case_input, filings_in_index, history_blocks_reached,
                                   restored_root_headers)
    from sec_urls import submissions_url
    from vnext.annual_update import saved_source
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    parser.add_argument("--case", required=True, action="append", type=_case)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-root", type=Path, default=None,
                        help="a data root holding filings the checkout does not, "
                             "such as one restored from the acquisition's export")
    arguments = parser.parse_args()
    if arguments.source_root is not None and arguments.output == CHECKOUT_READING:
        raise SystemExit("A_SOURCE_ROOT_READING_IS_WRITTEN_TO_A_READING_OF_ITS_OWN")
    source = REPO if arguments.source_root is None else arguments.source_root.resolve()
    header = None if arguments.source_root is None else restored_root_headers(source)
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    codes = candidate_codes()
    positions = {}
    for company_id, report_end, label in arguments.case:
        period, cik = _case_input(company_id=company_id, report_end=report_end,
                                  source_root=source)
        url = submissions_url(cik=int(cik))
        saved = saved_source(repo_root=source, url=url)
        if saved is None:
            raise SystemExit("SUBMISSIONS_INDEX_NOT_SAVED:" + url)
        start, end = period["period_start"], period["period_end"]
        submissions = json.loads(saved["raw"])
        # A window a history block may reach holds filings this index's recent
        # table does not list; counting only the recent table would call it empty.
        reached = history_blocks_reached(submissions, start)
        if reached:
            raise SystemExit("WINDOW_REACHES_A_HISTORY_BLOCK:" + label + ":" + ",".join(reached))
        seen, unreadable = window_candidates(filings=filings_in_index(submissions), cik=cik,
                                             start=start, end=end, codes=codes, header=header)
        candidates = {basis: sum(len(entry["candidate_items"]) for entry in entries)
                      for basis, entries in seen.items()}
        selection = select_receipt(found=index.get((company_id, "E01", report_end), []),
                                   closure=arguments.closure)
        result = selection["result"]
        published = None if result is None or result.get("value") is None else str(result["value"])
        if published is None:
            verdict = "NO_PUBLISHED_VALUE"
        elif unreadable:
            verdict = "HEADERS_NOT_SAVED"
        elif published == "0" and candidates == {"filing_date": 0, "report_date": 0}:
            verdict = "MATCH"
        else:
            verdict = "DIFFERS"
        position = {"company_id": company_id, "period_end": report_end, "window": [start, end],
                    "submissions_index": saved["proof"]["request_repo_relative_path"],
                    "filings_in_window": [entry["accession"] for entry in seen["filing_date"]],
                    "filings": seen, "headers_not_saved": unreadable,
                    "candidate_items_by_basis": candidates, "published": published,
                    "result_reason_code": None if result is None else result.get("reason_code"),
                    "verdict": verdict}
        if published is not None:
            identity, refusal = identity_for(
                position={"company_id": company_id, "metric_id": "E01", "period_end": report_end,
                          "published": published, "reading_filings": position["filings_in_window"],
                          "reading_window": [start, end], "filings_are_the_whole_set": True},
                index=index, closure=arguments.closure)
            if refusal is not None:
                raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + refusal)
            identity["established_by"] = "RECORDED_AT_READING_TIME"
            position["checked_identity"] = identity
        positions[label] = position
        print(label, verdict, candidates, flush=True)
    body = {"record_type": "ISSUE_47_E01_CONTENT_CONFIRMED_CANDIDATE_READ",
            "reader": "tools/read_e01_candidates.py", "route": ROUTE,
            "candidate_item_codes": codes, "requirement_closure_hash": arguments.closure,
            "what_this_can_accept": ("a window with no candidate item, whose answer is zero "
                                     "under the definition; nothing where a candidate needs "
                                     "its content confirmed"),
            "per_position": positions, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (REPO / arguments.output).write_text(
        json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
