"""Build the acceptance register from the readings, so nothing is hand-written.

Eight readings, eight shapes of source locator - a document, a table row, a
window of filings - so what every entry must carry is not one field name but
the artifact that holds the full reading. That is what a reader needs to redo
it, and it is uniform across them.

What an entry binds - the filings, window, entity, unit and meaning of the
value that was read - is copied from the reading, never from a batch of
results. An earlier version pinned it from whatever results it was generated
against, keyed by directory order, so an unchanged reading regenerated against
a batch whose result had moved to another unit or scope granted the new one.
The reading now carries that identity (tools/bind_acceptance_readings.py
records it once for readings made before they did), and this generator reads
no Run at all unless asked to report correspondence.

Usage:
    python3 tools/build_acceptance_register.py
    python3 tools/build_acceptance_register.py --runs-root <flat runs root> \
        --closure sha256:<closure>    # also report which entries a batch matches
"""
import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import (COMPENSATION, CROSS, EVENTS, GOVERNANCE,  # noqa: E402
                                 HEADINGS, HEADINGS_FROM_BYTES, LODGING, READINGS, RPO,
                                 TEXT, load, positions)

REGISTER = "docs/evidence/issue47_history/accepted_result_content.json"


class RegisterError(ValueError):
    """The readings cannot produce a register without inventing something."""


STATEMENT_METHOD = (
 "the filing's own primary document, walked directly: xbrli:context parsed for "
 "period, instant and dimensional members; ix:nonFraction facts read with "
 "their scale and sign; consolidated facts only; the approved candidate chain "
 "from 02_指标定义_SEC_10公司单年指标.md followed over what that document "
 "tags; the arithmetic in Decimal at the calculator's own precision. The route "
 "resolves these from the Company Facts API instead, so this is a different "
 "source for the same facts.")
LODGING_METHOD = (
 "the filing's lodging statistics table, read without the production grid "
 "builder the route uses: the document split on <table>, the one naming the "
 "frozen scope literal 'Comparable Systemwide Properties' with a Worldwide row "
 "kept - exactly one does in each year - tags stripped, and the row's RevPAR "
 "and occupancy read off the text.")
EVENT_METHOD = (
 "8-K and 8-K/A filings in the pinned fiscal window, selected from the saved "
 "submissions index, with each one's item codes read out of its own SEC "
 "header, counted against catalog/event_routes.json's declared item codes. "
 "Counted under both the filing date and the report date; every accepted "
 "position agrees under both.")
COMMON = ("that the approved definition is the right definition for the "
          "business question, or that the filing is right. It is independent "
          "of the code, not of the reader: the same person wrote the reading "
          "and read the result.")
STATEMENT_LIMIT = ("what is established is that the concept the definition "
                   "names carries this value in this filing for this period "
                   "and that the stated arithmetic produces the published "
                   "number. It does not establish " + COMMON)
LODGING_LIMIT = ("what is established is that the row under the approved scope "
                 "carries this value. It does not establish that the scope is "
                 "the right scope, nor " + COMMON)
EVENT_LIMIT = ("what is established is that this many filings in the window "
               "carry the declared item codes. C01 is named 'CEO / CFO "
               "changes' and its approved definition asks for an event list "
               "keyed by accession, so an 8-K/A amending an earlier filing's "
               "same event is its own entry - Marriott's 2025 window has one. "
               "Whether counting filings answers the metric's name is a "
               "question about the definition. It does not establish " + COMMON)

GOVERNANCE_METHOD = {
 "C03": "the ecd:PeoTotalCompAmt fact for the target period in the pinned "
        "proxy's own inline XBRL, read directly rather than through the "
        "route's ecd reader. Accepted only where exactly one PEO total is "
        "reported for that period.",
 "C04": "the auditor named by dei:AuditorName in this year's 10-K and in the "
        "previous year's, plus any 8-K in the window carrying item 4.01. Zero "
        "means the same auditor in both years and no such filing."}
GOVERNANCE_LIMIT = {
 "C03": "what is established is that the proxy reports this PEO total for this "
        "period. It does not establish that PEO total compensation is the "
        "right signal, nor " + COMMON,
 "C04": "what is established is that the auditor named in both years is the "
        "same and no 8-K in the window reported a change. Two limits belong "
        "with that. Naming the same firm across a punctuation difference - "
        "Macy's files KPMG LLP and KPMG, LLP - uses the same normalisation "
        "the route uses, so a route too loose at that layer would not be "
        "caught here; the rule compares letter sequences, so KPMG and KPMG "
        "Advisory are not equal under it, and both exact strings are recorded. "
        "And the reading takes every dei:AuditorName fact in the document "
        "without filtering by context, entity or dimension, which is looser "
        "than the route; each document here carries exactly one name. It does "
        "not establish " + COMMON}

TEXT_METHOD = (
 "every excerpt in the set read whole, and every block the selector skipped "
 "inside the narrow scopes - Item 3 and any named note range - read with it, "
 "judged against the approved source "
 "definition. The other direction - whether a contingencies note was missed - "
 "is the unreached-note scan in docs/evidence/issue47_history/"
 "d02-content-read/unreached-notes.json. The value is named by digest because "
 "it is the whole text payload.")
TEXT_LIMIT = (
 "what is established is that this excerpt set is the set the approved source "
 "definition asks for in this filing, read in both directions. It does not "
 "establish " + COMMON)

HEADINGS_LIMIT = (
 "what is established is that this heading set is the set the approved source "
 "definition asks for in this filing, read in both directions and item by "
 "item. It does not establish " + COMMON)



def _read_from(position):
    """The reading-specific locator an entry quotes."""
    path, case, row = position["reading"], position["case"], position["slot"]
    if path == CROSS:
        return {"document": case["document"], "concepts_that_answered": case["concepts_used"]}
    if path == LODGING:
        return {"document": case["document"], "table_ordinal": case["read"]["table_ordinal"],
                "row_text": case["read"]["row_text"],
                "tables_naming_the_scope_literal": case["tables_matching_scope"]}
    if path == EVENTS:
        return {"window": case["window"],
                "eight_k_filings_in_window": case["eight_ks_in_window"]["filing_date"],
                "item_codes": [f["items"] for f in case["filings"]["filing_date"]],
                "counted_under": ["filing_date", "report_date"]}
    if path == GOVERNANCE:
        if position["metric_id"] == "C03":
            return {"proxies": row["proxies_reporting_the_target_period"]}
        return {"auditor_this_year": row["auditor_named_in_the_target_filing"],
                "auditor_last_year": row["auditor_named_in_the_previous_years_filing"],
                "eight_k_item_4_01_in_window": row["eight_k_item_4_01_in_window"]}
    if path == TEXT:
        return {"excerpts": case["excerpts"], "chars": case["chars"]}
    if path in (HEADINGS, HEADINGS_FROM_BYTES):
        return {"headings": len(case["headings_read"]), "accession": case["accession"],
                "document": case["document"], "heading_shapes": case["heading_shapes"]}
    if path == RPO:
        return case["read_from"]
    if path == COMPENSATION:
        return {"document": case["document"], "where": case["where"],
                "components": case["components"]}
    raise RegisterError("READING_SHAPE_UNKNOWN:" + path)


def _method_and_limit(position):
    path, metric = position["reading"], position["metric_id"]
    if path == CROSS:
        return STATEMENT_METHOD, STATEMENT_LIMIT
    if path == LODGING:
        return LODGING_METHOD, LODGING_LIMIT
    if path == EVENTS:
        return EVENT_METHOD, EVENT_LIMIT
    if path == GOVERNANCE:
        return GOVERNANCE_METHOD[metric], GOVERNANCE_LIMIT[metric]
    if path == TEXT:
        return TEXT_METHOD, TEXT_LIMIT
    if path in (HEADINGS, HEADINGS_FROM_BYTES):
        return HEADINGS_FROM_BYTES_METHOD, HEADINGS_LIMIT
    if path == RPO:
        return (RPO_METHOD, position["case"]["what_this_does_not_establish"])
    if path == COMPENSATION:
        return COMPENSATION_METHOD, COMPENSATION_LIMIT
    raise RegisterError("READING_SHAPE_UNKNOWN:" + path)


HEADINGS_FROM_BYTES_METHOD = (
 "Item 1A read off the filing's saved HTML by tools/read_d01_headings.py, which "
 "imports none of the route's text modules: its own block reader, runs carrying "
 "the bold, underline and italic their own styles give them, the item located "
 "by its own heading and ended by the next item's. Every heading-marked line - "
 "bold or underline, outside links, not page furniture - is compared with the "
 "published value line for line and in order, so a dropped heading and an "
 "extra line both fail it; every other visually marked block needs a recorded "
 "judgement; the cover's fiscal year end must be the period read; and each "
 "line was judged as a category or a risk-factor heading against the filing. "
 "Identical heading text is listed once at its first occurrence, which is the "
 "shape the route publishes. Its controls: against Marriott's results from "
 "before the underline repair it reports exactly the four underlined "
 "categories as read and not published in each year, and on Paramount it "
 "flags the line cut at an unbolded period.")
RPO_METHOD = ("the filing's own inline XBRL fact for remaining performance "
              "obligation at the period end, undimensioned, against the "
              "accession-instance value the route published.")
COMPENSATION_METHOD = ("the Summary Compensation Table's own CEO row, read off the "
                       "table. Its five components sum to its total, so the number "
                       "is confirmed by the table's arithmetic as well as by "
                       "matching the published value.")
COMPENSATION_LIMIT = ("that the Summary Compensation Table total is the right pay "
                      "signal, nor " + COMMON)


def _accepted(position):
    """Whether this reading's conclusion at this position is an acceptance.

    A reading that found a defect is not one, and neither is a comparison the
    reading could not complete. E01 is accepted only where the window holds no
    8.01 filing, because that is the one branch this reading cannot redo.
    """
    path, verdict = position["reading"], position["verdict"]
    if path == EVENTS:
        if verdict != "MATCH_BOTH_BASES":
            return False
        eights = sum(1 for f in position["case"]["filings"]["filing_date"]
                     if "8.01" in f["items"])
        return not (position["metric_id"] == "E01" and eights)
    return verdict == "MATCH"


def _acceptance_id(position):
    if position["reading"] == RPO:
        return "CONTENT_B12_SALESFORCE_2026"
    if position["reading"] == COMPENSATION:
        return "CONTENT_C03_PARAMOUNT_2025"
    return ("CONTENT_" + position["metric_id"] + "_"
            + position["label"].upper().replace("-", "_"))


def build_register(*, repo_root: Path):
    """The register the readings under ``repo_root`` support. Reads no Run."""
    entries, readings = [], {}
    for source in READINGS:
        body, _ = load(repo_root=repo_root, path=source)
        contributed = 0
        for position in positions(repo_root=repo_root, path=source, body=body):
            if not _accepted(position):
                continue
            identity = position["slot"].get("checked_identity")
            if not isinstance(identity, dict):
                raise RegisterError("READING_POSITION_HAS_NO_CHECKED_IDENTITY:" + source
                                    + ":" + position["label"] + ":" + position["metric_id"])
            method, limit = _method_and_limit(position)
            entries.append({
                "acceptance_id": _acceptance_id(position),
                "company_id": position["company_id"], "metric_id": position["metric_id"],
                "period_end": position["period_end"],
                "accepted_value": str(position["published"]),
                "evidence": source, "read_from": _read_from(position),
                "checked_identity": identity,
                "method": method, "what_this_does_not_establish": limit})
            contributed += 1
        raw = (repo_root / source).read_bytes()
        examined = body.get("per_position") if isinstance(body, dict) else None
        # Reported, not gated. A reading that runs to completion and finds every
        # value inconsistent contributes none, and a legitimate fall in
        # acceptances is a result this register has to be able to carry.
        readings[source] = {
            "content_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "positions_examined": len(examined) if isinstance(examined, dict) else None,
            "positions_examined_is_null_because":
                None if isinstance(examined, dict)
                else "this reading's shape carries no per_position map",
            "acceptances_contributed": contributed}
    identifiers = collections.Counter(entry["acceptance_id"] for entry in entries)
    duplicated = sorted(key for key, count in identifiers.items() if count > 1)
    if duplicated:
        raise RegisterError("ACCEPTANCE_ID_NOT_UNIQUE:" + ",".join(duplicated))
    return {
     "record_type": "INDEPENDENT_CONTENT_ACCEPTANCE_REGISTER", "schema_version": 2,
     "issue": "https://github.com/wlvh/SEC_metrics/issues/47",
     "purpose": "The third delivery layer. A frozen Run with a public row says the "
                "route computed something and the bytes are bound; it does not say "
                "the number is right. This is where a reading that did not come "
                "from the route says so, for one value at a time.",
     "acceptance_rule": "An acceptance covers a position only while the value it "
                        "names, and the identity its reading recorded, are what "
                        "that position still carries. A later Run computing "
                        "something else, from other filings, over another window "
                        "or under another unit, scope or meaning, has not been "
                        "checked. A result a defect withdraws is never accepted, "
                        "whatever is written here.",
     "generated_from": list(READINGS),
 "not_here_and_why": {
  "salesforce B03": "the accession's facts carry "
                    "DepreciationDepletionAndAmortization, first in the "
                    "approved chain; the primary document does not tag it, so "
                    "the reading followed the chain past it. The route is "
                    "right and the reading cannot confirm it.",
  "pfizer B03 and B07": "neither the primary document nor the accession's "
                        "facts carry a consolidated OperatingIncomeLoss, which "
                        "both need, so the route reconstructed it and this "
                        "reading does not.",
  "ford B07 and lumen B07": "operating income is negative, the definition says "
                            "NOT_MEANINGFUL, and the reading agrees by "
                            "producing a negative ratio where the route "
                            "published none. There is no value to accept.",
  "marriott 2023 B02 and B03": "that period's source gaps.",
  "E01 where the window holds an 8.01 filing": "E01 is the only route with a "
   "keyword branch, and reading it means reproducing the route's text scoping. "
   "A scan over every document in the accession matches 'transaction' in "
   "almost any exhibit. Six of seven windows hold an 8.01 filing, so E01 is "
   "accepted only for the one that does not.",
  "C03": "all nine are read. The four that previously read as 'no saved proxy "
         "reports the target period' were a defect in the reading, not a gap "
         "in the material: it globbed *def14a*.htm, and only one of the ten "
         "companies names its proxy that way. Earlier periods remain unread "
         "and that IS a source gap - each registrant declares 16 to 33 DEF "
         "14A filings and exactly one is on disk.",
  "C04": "all six positions that carry a value are read. The five that "
         "previously reported the previous year's 10-K as not readable were "
         "three defects in the reading: it demanded the prior primary HTML "
         "where the route reads any document of that accession carrying dei "
         "facts, it parsed the accession out of an error string it had itself "
         "truncated, and it computed the prior period end by replacing the "
         "year - which for a 52/53-week filer names a date the calendar never "
         "had. Southwest and Salesforce have no published C04 value at all.",
  "B06": "the three delivered positions all reproduce from their filings' own "
         "facts, but two of them were fitted - solved backwards from the "
         "published value - and the rule cannot be stated from the filing "
         "alone: Salesforce carries the inputs of two approved debt models "
         "that give different answers, and which applies is decided by the "
         "note structure the cascade reads. See "
         "docs/evidence/issue47_history/content-acceptance/"
         "b06-not-independently-readable.json.",
  "D02 for four of the eleven": "Pfizer's 96 excerpts, Lumen's 41, Paramount's "
    "28 and Enphase's 18 were read whole and found wrong - two, one, two and "
    "one blocks respectively - so each is a registered defect rather than an "
    "unread set. The other seven have been read in both directions and are "
    "accepted.",
  "everything else": "no reading has been made."},
 "readings": readings,
     "what_binds_an_acceptance": (
         "company, metric, period end, value, and checked_identity - the filings "
         "the value was measured from, the measured window, the entity, the unit, "
         "the scope key and the metric's meaning (spec_closure_hash). All of it is "
         "copied from the reading, which recorded it when it was made or had it "
         "bound once afterwards against the result it compared (established_by "
         "says which, and bound_from names the closure, run and result). None of "
         "it comes from the results this register happens to be generated beside, "
         "and none of it moves with unrelated repository bytes."),
     "when_an_acceptance_stops_applying": (
         "the value moves, any identity field moves, a registered defect withdraws "
         "the result, or the reading it cites is not hashed here, cannot be read, "
         "or no longer hashes to content_sha256 above - a reading that was re-run "
         "and now concludes something else must not leave the previous grant "
         "standing, and a reading this table does not name cannot be checked."),
     "acceptances": sorted(entries, key=lambda entry: entry["acceptance_id"]),
    }


def correspondence(*, repo_root: Path, register, runs_root: Path, closure: str):
    """Which entries a named batch's results match, and on what they differ.

    A report about the register and one batch, not an input to either: the
    register's content does not depend on it, and a batch that differs is a
    finding to read, not a pin to follow.
    """
    from vnext.historical_coverage import acceptance_mismatch, select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    index = index_receipts(receipts=collect_run_receipts(runs_root=runs_root)["receipts"])
    counts = collections.Counter()
    differing = []
    for entry in register["acceptances"]:
        key = (entry["company_id"], entry["metric_id"], entry["period_end"])
        selection = select_receipt(found=index.get(key, []), closure=closure)
        if selection["ambiguity"] is not None:
            counts["AMBIGUOUS:" + selection["ambiguity"]] += 1
            continue
        mismatch = acceptance_mismatch(acceptance=entry, company_id=key[0],
                                       metric_id=key[1], report_end=key[2],
                                       result=selection["result"])
        if not mismatch:
            counts["CORRESPONDS"] += 1
        else:
            counts["DIFFERS"] += 1
            differing.append({"acceptance_id": entry["acceptance_id"], "fields": mismatch})
    return {"counts": dict(sorted(counts.items())), "differing": differing}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path)
    parser.add_argument("--closure")
    arguments = parser.parse_args()
    register = build_register(repo_root=REPO)
    (REPO / REGISTER).write_text(json.dumps(register, indent=1, sort_keys=True,
                                            ensure_ascii=False) + "\n", encoding="utf-8")
    print("acceptances:", len(register["acceptances"]))
    print(collections.Counter(entry["metric_id"] for entry in register["acceptances"]))
    if arguments.runs_root is not None:
        if not arguments.closure:
            parser.error("--closure names which version's results to compare")
        print(json.dumps(correspondence(repo_root=REPO, register=register,
                                        runs_root=arguments.runs_root,
                                        closure=arguments.closure), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
