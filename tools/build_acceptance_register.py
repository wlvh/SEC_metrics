"""Build the acceptance register from the readings, so nothing is hand-written.

Three readings, three shapes of source locator - a document, a table row, a
window of filings - so what every entry must carry is not one field name but
the artifact that holds the full reading. That is what a reader needs to redo
it, and it is uniform across the three.
"""
import collections
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# The results the readings were made against. An acceptance says "this fact was
# read from the filing", and a fact is a value under a measured window, a scope
# and a unit - so the register has to carry those, and it can only get them
# from the results themselves.
RUNS_ROOT = Path(os.environ.get("ISSUE47_RUNS_ROOT",
                                "/tmp/claude-0/native/par9/flat"))
EVIDENCE = "docs/evidence/issue47_history/content-acceptance/"
CROSS = EVIDENCE + "cross-source-read.json"
LODGING = EVIDENCE + "lodging-table-read.json"
EVENTS = EVIDENCE + "event-count-read.json"
GOVERNANCE = EVIDENCE + "governance-read.json"
TEXT = EVIDENCE + "d02-both-directions-read.json"
RPO = EVIDENCE + "rpo-read.json"
COMPENSATION = EVIDENCE + "paramount-compensation-table-read.json"
HEADINGS = EVIDENCE + "d01-headings-read.json"
PERIODS = {"marriott-2025": "2025-12-31", "marriott-2024": "2024-12-31",
           "marriott-2023": "2023-12-31", "ford-2025": "2025-12-31",
           "pfizer-2025": "2025-12-31", "lumen-2025": "2025-12-31",
           "enphase-2025": "2025-12-31", "southwest-2025": "2025-12-31",
           "salesforce-2026": "2026-01-31", "macys-2026": "2026-01-31"}

def _results_by_coordinate(root):
    """Every frozen Run's METRIC_RESULT, keyed by company, metric and period.

    Raises rather than returning an empty map: a register built against no
    results would pin nothing and every acceptance would fall back to the
    loose match this is here to remove.
    """
    found = {}
    for records in sorted(Path(root).glob("run-*/records.jsonl")):
        for line in records.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("record_type") != "METRIC_RESULT":
                continue
            key = (record["company_id"], record["metric_id"], record["period_end"])
            found.setdefault(key, record)
    if not found:
        raise SystemExit("NO_RESULTS_UNDER:" + str(root)
                         + " - set ISSUE47_RUNS_ROOT to the batch this register "
                           "describes; pinning cannot be invented.")
    return found


RESULTS = _results_by_coordinate(RUNS_ROOT)
# Pinned from the result the reading was made against. The reading establishes
# the company, the metric, the measured period and the value; the unit and the
# scope key come from that result and are carried here so that a later result
# cannot inherit this acceptance by carrying the same number under a different
# scope, unit or window. They are a binding, not a second reading.
IDENTITY_FIELDS = ("period_start", "period_end", "unit", "scope_key")


def _identity(*, company_id, metric_id, period_end, reading_period=None):
    """The business fact this acceptance is about, or a refusal."""
    result = RESULTS.get((company_id, metric_id, period_end))
    if result is None:
        raise SystemExit("NO_RESULT_TO_PIN:" + "/".join(
            (company_id, metric_id, period_end)))
    missing = [field for field in IDENTITY_FIELDS if not result.get(field)]
    if missing:
        raise SystemExit("RESULT_CANNOT_BE_PINNED:" + "/".join(
            (company_id, metric_id, period_end)) + ":" + ",".join(missing))
    # Where a reading records the window it read, it has to be the window the
    # result measured. A disagreement here is not a pin to paper over.
    if reading_period and list(reading_period) != [result["period_start"],
                                                   result["period_end"]]:
        raise SystemExit("READING_AND_RESULT_DISAGREE_ON_THE_WINDOW:" + "/".join(
            (company_id, metric_id, period_end)) + ":" + str(list(reading_period))
            + " vs " + str([result["period_start"], result["period_end"]]))
    return {field: result[field] for field in IDENTITY_FIELDS}


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

entries = []
cross = json.loads((REPO / CROSS).read_text())["per_position"]
for label, case in sorted(cross.items()):
    if "error" in case:
        continue
    for metric, row in sorted(case["metrics"].items()):
        if row["verdict"] != "MATCH":
            continue
        entries.append({
            "acceptance_id": "CONTENT_" + metric + "_" + label.upper().replace("-", "_"),
            "company_id": case["company_id"], "metric_id": metric,
            "period_end": case["period_end"], "accepted_value": row["published"],
            "evidence": CROSS,
            "read_from": {"document": case["document"],
                          "concepts_that_answered": case["concepts_used"]},
            "method": STATEMENT_METHOD, "what_this_does_not_establish": STATEMENT_LIMIT})

lodging = json.loads((REPO / LODGING).read_text())
for label, case in sorted(lodging.items()):
    for metric in ("B10", "B11"):
        row = case.get(metric)
        if row is None or row["verdict"] != "MATCH":
            continue
        entries.append({
            "acceptance_id": "CONTENT_" + metric + "_" + label.upper().replace("-", "_"),
            "company_id": "marriott_international", "metric_id": metric,
            "period_end": PERIODS[label], "accepted_value": row["published"],
            "evidence": LODGING,
            "read_from": {"document": case["document"],
                          "table_ordinal": case["read"]["table_ordinal"],
                          "row_text": case["read"]["row_text"],
                          "tables_naming_the_scope_literal": case["tables_matching_scope"]},
            "method": LODGING_METHOD, "what_this_does_not_establish": LODGING_LIMIT})

events = json.loads((REPO / EVENTS).read_text())["per_position"]
for label, case in sorted(events.items()):
    if "metrics" not in case:
        continue
    eights = sum(1 for f in case["filings"]["filing_date"] if "8.01" in f["items"])
    for metric, row in sorted(case["metrics"].items()):
        if row["verdict"] != "MATCH_BOTH_BASES":
            continue
        if metric == "E01" and eights:
            continue
        entries.append({
            "acceptance_id": "CONTENT_" + metric + "_" + label.upper().replace("-", "_"),
            "company_id": case["company_id"], "metric_id": metric,
            "period_end": PERIODS[label], "accepted_value": row["published"],
            "evidence": EVENTS,
            "read_from": {"window": case["window"],
                          "eight_k_filings_in_window":
                              case["eight_ks_in_window"]["filing_date"],
                          "item_codes": [f["items"] for f in case["filings"]["filing_date"]],
                          "counted_under": ["filing_date", "report_date"]},
            "method": EVENT_METHOD, "what_this_does_not_establish": EVENT_LIMIT})

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

governance = json.loads((REPO / GOVERNANCE).read_text())["per_position"]
for label, case in sorted(governance.items()):
    for metric in ("C03", "C04"):
        row = case.get(metric)
        if row is None or row.get("verdict") != "MATCH":
            continue
        entries.append({
            "acceptance_id": "CONTENT_" + metric + "_" + label.upper().replace("-", "_"),
            "company_id": case["company_id"], "metric_id": metric,
            "period_end": PERIODS[label], "accepted_value": row["published"],
            "evidence": GOVERNANCE,
            "read_from": ({"proxies": row["proxies_reporting_the_target_period"]}
                          if metric == "C03" else
                          {"auditor_this_year": row["auditor_named_in_the_target_filing"],
                           "auditor_last_year":
                               row["auditor_named_in_the_previous_years_filing"],
                           "eight_k_item_4_01_in_window":
                               row["eight_k_item_4_01_in_window"]}),
            "method": GOVERNANCE_METHOD[metric],
            "what_this_does_not_establish": GOVERNANCE_LIMIT[metric]})

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

textual = json.loads((REPO / TEXT).read_text())["per_position"]
for label, case in sorted(textual.items()):
    entries.append({
        "acceptance_id": "CONTENT_D02_" + label.upper().replace("-", "_"),
        "company_id": case["company_id"], "metric_id": "D02",
        "period_end": case["period_end"], "accepted_value": case["value_sha256"],
        "evidence": TEXT,
        "read_from": {"excerpts": case["excerpts"], "chars": case["chars"]},
        "method": TEXT_METHOD, "what_this_does_not_establish": TEXT_LIMIT})

HEADINGS_METHOD = (
 "both directions over the located Item 1A, plus the heading list itself. "
 "Every emphasised block the selector refused is recomputed with the rule "
 "that refused it, so an unexplained refusal fails the reading; every "
 "non-furniture block the filing marks visually and the selector left is "
 "reported, so a dropped heading fails it; and the judged list must equal "
 "both what the selector returns today and the published value's own lines. "
 "The value is named by digest because it is the whole text payload.")
HEADINGS_LIMIT = (
 "what is established is that this heading set is the set the approved source "
 "definition asks for in this filing, read in both directions and item by "
 "item. It does not establish " + COMMON)

headings = json.loads((REPO / HEADINGS).read_text())["per_position"]
for label, case in sorted(headings.items()):
    # A reading that found a defect is not an acceptance, and neither is a
    # coordinate that produced no value. Both are carried in the reading so
    # that "not read" and "read and rejected" stay distinguishable there.
    if case["verdict"] != "MATCH":
        continue
    entries.append({
        "acceptance_id": "CONTENT_D01_" + label.upper().replace("-", "_"),
        "company_id": case["company_id"], "metric_id": "D01",
        "period_end": case["period_end"], "accepted_value": case["value_sha256"],
        "evidence": HEADINGS,
        "read_from": {"headings": case["headings"],
                      "accession": case["accession"]},
        "method": HEADINGS_METHOD, "what_this_does_not_establish": HEADINGS_LIMIT})

rpo = json.loads((REPO / RPO).read_text())
if rpo["verdict"] == "MATCH":
    entries.append({
        "acceptance_id": "CONTENT_B12_SALESFORCE_2026",
        "company_id": rpo["company_id"], "metric_id": rpo["metric_id"],
        "period_end": rpo["period_end"], "accepted_value": rpo["published"],
        "evidence": RPO, "read_from": rpo["read_from"],
        "method": "the filing's own inline XBRL fact for remaining performance "
                  "obligation at the period end, undimensioned, against the "
                  "accession-instance value the route published.",
        "what_this_does_not_establish": rpo["what_this_does_not_establish"]})

table = json.loads((REPO / COMPENSATION).read_text())
if table["verdict"] == "MATCH":
    entries.append({
        "acceptance_id": "CONTENT_C03_PARAMOUNT_2025",
        "company_id": table["company_id"], "metric_id": "C03",
        "period_end": table["period_end"], "accepted_value": table["published"],
        "evidence": COMPENSATION,
        "read_from": {"document": table["document"], "where": table["where"],
                      "components": table["components"]},
        "method": "the Summary Compensation Table's own CEO row, read off the "
                  "table. Its five components sum to its total, so the number "
                  "is confirmed by the table's arithmetic as well as by "
                  "matching the published value.",
        "what_this_does_not_establish":
            "that the Summary Compensation Table total is the right pay signal, "
            "nor " + COMMON})

# Pinned in one place rather than at each of the seven append sites, so an
# acceptance cannot be added without its binding.
for entry in entries:
    entry["result_identity"] = _identity(company_id=entry["company_id"],
                                         metric_id=entry["metric_id"],
                                         period_end=entry["period_end"])

# Where a reading records the window it read, that window has to be the one the
# result measured; a disagreement is reported rather than pinned over.
for source in (GOVERNANCE, CROSS, LODGING, EVENTS):
    reading = json.loads((REPO / source).read_text())
    for case in (reading.get("per_position") or {}).values():
        if not isinstance(case, dict) or not case.get("period"):
            continue
        for metric in [k for k in case if len(k) == 3 and k[0].isalpha()]:
            row = case[metric]
            if not isinstance(row, dict) or row.get("verdict") != "MATCH":
                continue
            if (case["company_id"], metric, case["period"][1]) in RESULTS:
                _identity(company_id=case["company_id"], metric_id=metric,
                          period_end=case["period"][1],
                          reading_period=case["period"])

# What each reading examined and what it concluded. The guard that used to sit
# here required every reading to contribute at least one acceptance, which is
# indistinguishable from the case it was written for: a reading that runs to
# completion and finds every value inconsistent contributes none, and the guard
# then exited BEFORE writing - leaving the previous register installed and
# still granting exactly what the new reading had just contradicted. Measured:
# with every governance verdict turned to DIFFERS the generator exited 1 and
# all six C04 acceptances remained. A legitimate fall in acceptances is a
# result this register has to be able to carry.
readings = {}
for source in (CROSS, LODGING, EVENTS, GOVERNANCE, TEXT, HEADINGS, RPO, COMPENSATION):
    raw = (REPO / source).read_bytes()
    body = json.loads(raw)
    positions = body.get("per_position")
    # Reported, not gated. The count is only derivable for the readings that
    # carry a per_position map; the others are a flat map of labels or a single
    # coordinate, and a rule written to see those shapes stops seeing the next
    # one. A zero or a fall here is for a reader to notice, not something to
    # exit on - the guard that did exit is what this replaces.
    readings[source] = {
        "content_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "positions_examined": len(positions) if isinstance(positions, dict) else None,
        "positions_examined_is_null_because":
            None if isinstance(positions, dict)
            else "this reading's shape carries no per_position map",
        "acceptances_contributed": sum(1 for e in entries if e["evidence"] == source)}

register = {
 "record_type": "INDEPENDENT_CONTENT_ACCEPTANCE_REGISTER", "schema_version": 1,
 "issue": "https://github.com/wlvh/SEC_metrics/issues/47",
 "purpose": "The third delivery layer. A frozen Run with a public row says the "
            "route computed something and the bytes are bound; it does not say "
            "the number is right. This is where a reading that did not come "
            "from the route says so, for one value at a time.",
 "acceptance_rule": "An acceptance covers a position only while the value it "
                    "names is the value that position still carries. A later "
                    "Run computing something else has not been checked. A "
                    "result a defect withdraws is never accepted, whatever is "
                    "written here.",
 "generated_from": [CROSS, LODGING, EVENTS, GOVERNANCE, TEXT, COMPENSATION,
                    RPO],
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
     "company, metric, period end, value, and the result_identity block - the "
     "measured window, the scope key and the unit. Without all of them an "
     "acceptance is inherited by any later result that happens to carry the "
     "same number, which for a flag whose value is 0 is most of them. The "
     "reading establishes the company, the metric, the measured window and the "
     "value; the scope key and unit are pinned from the result the reading was "
     "made against, so that a change in either stops the inheritance. They are "
     "a binding, not a second reading."),
 "when_an_acceptance_stops_applying": (
     "the value moves, any pinned identity field moves, a registered defect "
     "withdraws the result, or the reading artifact it names no longer hashes "
     "to content_sha256 above - a reading that was re-run and now concludes "
     "something else must not leave the previous grant standing."),
 "acceptances": sorted(entries, key=lambda e: e["acceptance_id"]),
}
(REPO / "docs/evidence/issue47_history/accepted_result_content.json").write_text(
    json.dumps(register, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
print("acceptances:", len(entries))
print(collections.Counter(e["metric_id"] for e in entries))
