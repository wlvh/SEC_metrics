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

from acceptance_readings import (COMPENSATION, CROSS, D01_READINGS,  # noqa: E402
                                 DEBT_TO_EQUITY, E01_EIGHT_O_ONES, EVENTS, GOVERNANCE,
                                 LODGING, READINGS, RPO, TEXT, load, positions)

REGISTER = "docs/evidence/issue47_history/accepted_result_content.json"


class RegisterError(ValueError):
    """The readings cannot produce a register without inventing something."""


STATEMENT_METHOD = (
 "the filing's own primary document, walked directly by "
 "tools/read_statement_facts.py: xbrli:context parsed for period, instant and "
 "dimensional members; ix:nonFraction facts read as decimals with their scale "
 "and sign, the fixed-zero dash as zero, and duplicates kept as one fact only "
 "where they round to each other; consolidated facts only; the approved "
 "candidate chain from 02_指标定义_SEC_10公司单年指标.md followed over what "
 "that document tags; the arithmetic in Decimal at the calculator's own "
 "precision. B03 is not accepted where two names for total D&A carry "
 "different values. The route resolves these from the Company Facts API "
 "instead, so this is a different source for the same facts.")
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
E01_METHOD = (
 "the window's 1.01 and 2.01 items from each filing's own SEC header, as for "
 "the other event metrics, and every item 8.01 in the window read off the "
 "saved primary document: the item located by its own heading and ended at "
 "Item 9.01 or the signatures, the catalog's aliases matched under its own "
 "normalisation, and a recorded judgement per filing of whether the item "
 "reports a merger, acquisition or business combination the registrant is "
 "party to. Counted in the route's unit, one per matched item, under three "
 "readings of the confirmation - alias in the item, alias anywhere in the "
 "document, alias in the item that reports a transaction - and accepted only "
 "where all three give the published count.")
E01_LIMIT = (
 "what is established is that this count does not depend on which reading of "
 "'8.01 需正文关键词确认' is chosen: no 8.01 in the window changes it under "
 "any of the three. It does not establish that counting every 1.01 answers "
 "the metric's name - in these windows eleven of thirteen 1.01 items are debt "
 "agreements - nor " + COMMON)

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
    if path == DEBT_TO_EQUITY:
        return {"document": case["document"],
                "debt_rows": case["balance_sheet"]["debt_rows"],
                "equity_row": case["balance_sheet"]["equity_row"],
                "finance_leases": case["finance_leases"]}
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
    if path == E01_EIGHT_O_ONES:
        return {"window": case["window"],
                "direct_item_claims": case["direct_item_claims"],
                "eight_o_ones": [{key: entry[key] for key in (
                    "accession", "heading", "aliases_in_the_8_01_item",
                    "aliases_anywhere_in_the_primary_document", "decision")}
                    for entry in case["eight_o_ones"]],
                "counts_under_each_reading": case["counts"]}
    if path == GOVERNANCE:
        if position["metric_id"] == "C03":
            return {"proxies": row["proxies_reporting_the_target_period"]}
        return {"auditor_this_year": row["auditor_named_in_the_target_filing"],
                "auditor_last_year": row["auditor_named_in_the_previous_years_filing"],
                "eight_k_item_4_01_in_window": row["eight_k_item_4_01_in_window"]}
    if path == TEXT:
        return {"excerpts": case["excerpts"], "chars": case["chars"]}
    if path in D01_READINGS:
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
    if path == DEBT_TO_EQUITY:
        return DEBT_TO_EQUITY_METHOD, DEBT_TO_EQUITY_LIMIT
    if path == CROSS:
        return STATEMENT_METHOD, STATEMENT_LIMIT
    if path == LODGING:
        return LODGING_METHOD, LODGING_LIMIT
    if path == EVENTS:
        return EVENT_METHOD, EVENT_LIMIT
    if path == E01_EIGHT_O_ONES:
        return E01_METHOD, E01_LIMIT
    if path == GOVERNANCE:
        return GOVERNANCE_METHOD[metric], GOVERNANCE_LIMIT[metric]
    if path == TEXT:
        return TEXT_METHOD, TEXT_LIMIT
    if path in D01_READINGS:
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
DEBT_TO_EQUITY_METHOD = (
 "the filing's own balance sheet and lease note, read by tools/read_debt_to_equity.py, "
 "which imports none of the debt cascade and reads the published value only to compare: "
 "every balance sheet row whose caption names debt, borrowings or commercial paper and "
 "not a lease, each by its inline XBRL fact at the period end; finance leases added only "
 "where the filing classifies them under captions other than debt (Macy's accounts "
 "payable and long-term lease liabilities, Salesforce's accrued and other noncurrent "
 "liabilities), not where its debt table lists them (Paramount) or it states it has none "
 "(Enphase); over the parent's total stockholders' equity.")
DEBT_TO_EQUITY_LIMIT = (
 "that the balance sheet's debt rows are every borrowing the definition means - a "
 "borrowing presented under another caption would be missed by both this reading and "
 "the arithmetic it checks - nor " + "that the parent's equity rather than total equity "
 "is the right divisor where noncontrolling interests exist (Paramount), which is the "
 "approved definition's 'shareholders' equity' as read here, nor " + COMMON)
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
    reading could not complete. E01 is never accepted from the header count:
    whether an 8.01 counts depends on its text, which that reading does not
    open. The 8.01 reading accepts it only where the published count holds
    under every reading of the confirmation, so no acceptance rests on the
    reading still to be decided.
    """
    path, verdict = position["reading"], position["verdict"]
    if path == EVENTS:
        return verdict == "MATCH_BOTH_BASES" and position["metric_id"] != "E01"
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
  "salesforce B03": "read, and wrong: the D&A the chain takes is "
                    "DepreciationDepletionAndAmortization $1.2 billion, which "
                    "the filing tags on 'Depreciation and amortization of "
                    "fixed assets' - a subtotal that leaves out $1,687 million "
                    "of acquired-intangible amortization. This entry used to "
                    "say the primary document does not tag that concept and "
                    "that the route was right; the document tags it, and the "
                    "earlier reading did not find it. Registered as "
                    "B03_SALESFORCE_2026_CHAIN_TAKES_FIXED_ASSET_DEPRECIATION_"
                    "AS_TOTAL; see b03-depreciation-scope/finding.json.",
  "ford B07 and lumen B07": "operating income is negative, the definition says "
                            "NOT_MEANINGFUL, and the reading agrees by "
                            "producing a negative ratio where the route "
                            "published none. There is no value to accept.",
  "marriott 2023 B02 and B03": "that period's source gaps.",
  "E01 for Lumen, Macy's, Marriott and Pfizer": "every 8.01 in the seven "
   "windows is read (content-acceptance/e01-eight-o-one-read.json). Lumen's, "
   "Macy's and Marriott's counts hold under some readings of the definition's "
   "keyword confirmation and not others - the decision is in "
   "e01-keyword-branch/decision.json. Pfizer's is wrong under every reading: "
   "its Metsera acquisition was reported under item 8.01 and the route's 8.01 "
   "branch never reads the item. That is a registered defect.",
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
  "B06": "all four delivered values are read off their filings' balance sheets "
         "and lease notes and accepted (content-acceptance/debt-to-equity-read.json). "
         "This entry used to say two of them had been solved backwards from the "
         "published value and that Salesforce carried the inputs of two debt models "
         "with different answers; the reading now decides finance leases from where "
         "the filing itself classifies them, before it looks at the published value, "
         "and Salesforce's lease note puts them under accrued and other noncurrent "
         "liabilities - outside debt - so the definition's 'finance leases included' "
         "answers which model applies. Lumen and Marriott 2024/2025 are NOT_MEANINGFUL "
         "with no value to accept.",
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
