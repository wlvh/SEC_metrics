"""Read E01's item 8.01 filings off their saved bytes, under each reading of its rule.

E01's approved definition counts items 1.01, 2.01 and 8.01, and says of the
last "8.01 需正文关键词确认" - an 8.01 counts once a keyword in its text
confirms it. The route matches the declared aliases against each claim's
``brief``. When the filing's hdr.sgml carries item codes - every filing in
these windows - that brief is the constant ``"8-K item 8.01 parsed from
hdr.sgml"``, which contains none of the aliases, so the branch admits no 8.01
at all. What the route publishes is the count of 1.01 and 2.01 items.

Reproducing the route's text scoping would reproduce that, so this reads each
saved primary document directly: the item 8.01 is found by the filing's own
heading ('Other Events', or Pfizer's 'Results of Other Events') and runs to
Item 9.01 or the signatures. Three readings of the confirmation are counted,
each in the route's own unit (one per matched item, as the route counts):

* ``LITERAL_IN_THE_8_01_ITEM`` - an alias occurs in the item's text, under the
  catalog's normalisation and substring match;
* ``LITERAL_ANYWHERE_IN_THE_PRIMARY_DOCUMENT`` - an alias occurs anywhere in
  the document, which lets another item's text confirm the 8.01;
* ``ALIAS_IN_THE_ITEM_AND_IT_REPORTS_A_TRANSACTION`` - an alias occurs in the
  item and a recorded judgement says the item reports a merger, acquisition or
  business combination the registrant or a subsidiary is party to.

The judgement is the part a program cannot supply and is recorded per filing
(docs/evidence/issue47_history/e01-keyword-branch/eight-o-one-judgements.json);
every 8.01 in a window needs one, and a judgement about a filing the window
does not hold fails the reading. A position MATCHes only when the published
count equals the count under every reading - the value does not depend on the
reading still to be chosen. It DIFFERS when no reading gives it, and otherwise
DEPENDS_ON_THE_CONFIRMATION_READING.

The window and its filing set are the ones event-count-read.json enumerated
from the saved submissions index, read from their SEC headers; this adds the
8.01 bodies. Zero network calls.

Usage:
    python3 tools/read_e01_eight_o_ones.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under>
"""
import argparse
import hashlib
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from bind_acceptance_readings import identity_for  # noqa: E402
from sec_urls import accession_document_url  # noqa: E402
from vnext.annual_update import saved_source  # noqa: E402
from vnext.historical_coverage import select_receipt  # noqa: E402
from vnext.historical_run_receipts import collect_run_receipts, index_receipts  # noqa: E402

EVIDENCE = "docs/evidence/issue47_history/"
WINDOWS = EVIDENCE + "content-acceptance/event-count-read.json"
JUDGEMENTS = EVIDENCE + "e01-keyword-branch/eight-o-one-judgements.json"
OUT = EVIDENCE + "content-acceptance/e01-eight-o-one-read.json"
REPORTS = "REPORTS_A_TRANSACTION_THE_REGISTRANT_IS_PARTY_TO"
DECISIONS = (REPORTS, "DOES_NOT_REPORT_A_TRANSACTION")
READINGS_OF_THE_CONFIRMATION = ("LITERAL_IN_THE_8_01_ITEM",
                                "LITERAL_ANYWHERE_IN_THE_PRIMARY_DOCUMENT",
                                "ALIAS_IN_THE_ITEM_AND_IT_REPORTS_A_TRANSACTION")
_HEADING = re.compile(r"Item\s*8\.01\b\.?\s*(?:Results\s+of\s+)?Other\s+Events\.?", re.I)
_END = re.compile(r"Item\s*9\.01\b|SIGNATURES?\b", re.I)


def _route():
    """E01's declared item codes and 8.01 aliases - catalog data, not route code."""
    catalog = json.loads((REPO / "catalog/event_routes.json").read_text(encoding="utf-8"))
    route = catalog["routes"]["E01"]
    aliases = [alias for rule in route["keyword_item_rules"] if rule["item_code"] == "8.01"
               for alias in rule["aliases"]]
    return set(route["direct_item_codes"]), aliases


def _normalise(text):
    """The catalog's normalisation: NFKC, casefold, collapse whitespace."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def visible_text(raw):
    """Tags removed, entities decoded, whitespace collapsed."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))
    return re.sub(r"\s+", " ", text)


def eight_o_one_item(text):
    """The item 8.01 as the filing heads it, to Item 9.01 or the signatures."""
    heading = _HEADING.search(text)
    if heading is None:
        return None, ""
    tail = _END.search(text, heading.end())
    return heading.group(0), text[heading.start():tail.start() if tail else len(text)]


def aliases_in(text, aliases):
    normalised = _normalise(text)
    return sorted(alias for alias in aliases if _normalise(alias) in normalised)


def _primary_documents(cik):
    """accession -> primary document name, from the saved submissions index."""
    names = {}
    paths = sorted(REPO.glob("evidence/request_attempts/*/*/CIK%010d*.json" % cik))
    paths += sorted(REPO.glob("evidence/submissions/CIK%010d*.json" % cik))
    for path in paths:
        if path.name.endswith("headers.json"):
            continue
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        for block in ([body["filings"]["recent"]] if "filings" in body else [body]):
            if "accessionNumber" in block and "primaryDocument" in block:
                names.update(zip(block["accessionNumber"], block["primaryDocument"]))
    return names


def registered_ciks():
    """company_id -> primary CIK, from the company registry."""
    import csv
    with (REPO / "config/company_registry.csv").open(encoding="utf-8") as handle:
        return {row["company_id"]: int(row["primary_cik"]) for row in csv.DictReader(handle)}


def counts_under_each_reading(*, direct, eights):
    """The route's unit: one per matched item, so a filing with a 1.01 and an
    admitted 8.01 counts twice, exactly as the route would count it."""
    return {
        "LITERAL_IN_THE_8_01_ITEM": direct + sum(
            1 for e in eights if e["aliases_in_the_8_01_item"]),
        "LITERAL_ANYWHERE_IN_THE_PRIMARY_DOCUMENT": direct + sum(
            1 for e in eights if e["aliases_anywhere_in_the_primary_document"]),
        "ALIAS_IN_THE_ITEM_AND_IT_REPORTS_A_TRANSACTION": direct + sum(
            1 for e in eights if e["aliases_in_the_8_01_item"] and e["decision"] == REPORTS)}


def verdict(*, published, counts, complete):
    """MATCH only where the value does not depend on the reading still open."""
    if not complete:
        return "READING_INCOMPLETE"
    agreeing = [name for name, count in counts.items() if str(count) == str(published)]
    if len(agreeing) == len(counts):
        return "MATCH"
    return "DIFFERS" if not agreeing else "DEPENDS_ON_THE_CONFIRMATION_READING"


def read_window(*, case, judgements, cik):
    """The window's direct items and every 8.01 read off its saved document.

    Reads saved bytes only - no result, no runs root - so what the reading
    says about each filing can be re-derived from the repository alone.
    """
    direct_codes, aliases = _route()
    documents = _primary_documents(cik)
    filings = case["filings"]["filing_date"]
    direct = [{"accession": f["accession"], "item": item} for f in filings
              for item in f["items"] if item in direct_codes]
    eights = []
    for filing in filings:
        if "8.01" not in filing["items"]:
            continue
        url = accession_document_url(cik=cik, accession=filing["accession"],
                                     document_name=documents[filing["accession"]])
        saved = saved_source(repo_root=REPO, url=url, accession=filing["accession"])
        if saved is None:
            raise SystemExit("EIGHT_O_ONE_BODY_NOT_SAVED:" + url)
        text = visible_text(saved["raw"])
        heading, item = eight_o_one_item(text)
        judged = judgements.get(filing["accession"], {})
        eights.append({
            "accession": filing["accession"], "filingDate": filing["filingDate"],
            "document": saved["proof"]["request_repo_relative_path"],
            "content_sha256": saved["proof"]["content_sha256"],
            "heading": heading, "item_chars": len(item),
            "item_sha256": "sha256:" + hashlib.sha256(item.encode("utf-8")).hexdigest(),
            "aliases_in_the_8_01_item": aliases_in(item, aliases),
            "aliases_anywhere_in_the_primary_document": aliases_in(text, aliases),
            "decision": judged.get("decision") if judged.get("decision") in DECISIONS else None,
            "judgement": judged.get("judgement"), "item": item})
    return direct, eights


def read_position(*, label, case, judgements, index, closure, ciks):
    filings = case["filings"]["filing_date"]
    direct, eights = read_window(case=case, judgements=judgements,
                                 cik=ciks[case["company_id"]])
    in_window = {e["accession"] for e in eights}
    unjudged = sorted(e["accession"] for e in eights if e["decision"] is None)
    no_heading = sorted(e["accession"] for e in eights if e["heading"] is None)
    counts = counts_under_each_reading(direct=len(direct), eights=eights)
    key = (case["company_id"], "E01", case["period_end"])
    position = {
        "reading": "E01_EIGHT_O_ONE_ITEMS_READ_FROM_THE_FILING_BYTES",
        "company_id": case["company_id"], "period_end": case["period_end"],
        "window": case["window"], "filings_in_window": sorted(f["accession"] for f in filings),
        "direct_item_claims": direct, "eight_o_ones": eights,
        "eight_o_ones_with_no_judgement": unjudged,
        "eight_o_ones_whose_heading_was_not_found": no_heading,
        "route_as_built": len(direct), "counts": counts,
        "reports_a_transaction_without_an_alias": sorted(
            e["accession"] for e in eights
            if e["decision"] == REPORTS and not e["aliases_in_the_8_01_item"])}
    selection = select_receipt(found=index.get(key, []), closure=closure)
    if selection["result"] is None:
        raise SystemExit("NO_RESULT_TO_COMPARE:" + label)
    position["published"] = str(selection["result"]["value"])
    identity, refusal = identity_for(
        position={"company_id": case["company_id"], "metric_id": "E01",
                  "period_end": case["period_end"], "published": position["published"],
                  "reading_filings": position["filings_in_window"],
                  "reading_window": case["window"], "filings_are_the_whole_set": True},
        index=index, closure=closure)
    if refusal is not None:
        raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + refusal)
    identity["established_by"] = "RECORDED_AT_READING_TIME"
    position["checked_identity"] = identity
    position["verdict"] = verdict(published=position["published"], counts=counts,
                                  complete=not unjudged and not no_heading)
    return position, in_window


def read(*, runs_roots, closure):
    receipts = []
    for root in runs_roots:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    windows = json.loads((REPO / WINDOWS).read_text(encoding="utf-8"))["per_position"]
    judgements = json.loads((REPO / JUDGEMENTS).read_text(encoding="utf-8"))["per_filing"]
    positions, seen = {}, set()
    for label, case in sorted(windows.items()):
        case = {**case, "period_end": case["window"][1]}
        positions[label], in_window = read_position(
            label=label, case=case, judgements=judgements, index=index,
            closure=closure, ciks=registered_ciks())
        seen |= in_window
    return {"record_type": "ISSUE_47_E01_EIGHT_O_ONE_READ",
            "requirement_closure_hash": closure,
            "readings_of_the_confirmation": list(READINGS_OF_THE_CONFIRMATION),
            "judgements": JUDGEMENTS, "windows_from": WINDOWS,
            "judgements_not_found_in_any_window": sorted(set(judgements) - seen),
            "per_position": positions, "calls": {"provider": 0, "paid": 0, "sec": 0}}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    arguments = parser.parse_args()
    body = read(runs_roots=arguments.runs_root, closure=arguments.closure)
    if body["judgements_not_found_in_any_window"]:
        # A judgement about a filing no window holds is about something else.
        for row in body["per_position"].values():
            row["verdict"] = "READING_INCOMPLETE"
    (REPO / OUT).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False)
                            + "\n", encoding="utf-8")
    for label, row in body["per_position"].items():
        print(label, row["verdict"], "published", row["published"], row["counts"],
              "route_as_built", row["route_as_built"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
