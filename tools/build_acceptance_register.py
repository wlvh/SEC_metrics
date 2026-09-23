"""Build the acceptance register from the readings, so nothing is hand-written.

Three readings, three shapes of source locator - a document, a table row, a
window of filings - so what every entry must carry is not one field name but
the artifact that holds the full reading. That is what a reader needs to redo
it, and it is uniform across the three.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = "docs/evidence/issue47_history/content-acceptance/"
CROSS = EVIDENCE + "cross-source-read.json"
LODGING = EVIDENCE + "lodging-table-read.json"
EVENTS = EVIDENCE + "event-count-read.json"
GOVERNANCE = EVIDENCE + "governance-read.json"
PERIODS = {"marriott-2025": "2025-12-31", "marriott-2024": "2024-12-31",
           "marriott-2023": "2023-12-31", "ford-2025": "2025-12-31",
           "pfizer-2025": "2025-12-31", "lumen-2025": "2025-12-31",
           "enphase-2025": "2025-12-31", "southwest-2025": "2025-12-31",
           "salesforce-2026": "2026-01-31", "macys-2026": "2026-01-31"}

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
        "same and no 8-K in the window reported a change. It does not "
        "establish " + COMMON}

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
 "generated_from": [CROSS, LODGING, EVENTS, GOVERNANCE],
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
  "C03 for four companies": "no saved proxy reports an ecd PEO total for the "
                            "target period; ten proxies are saved of the "
                            "eighty-five the submissions indexes list.",
  "C04 for five": "the previous year's 10-K is not saved, and 'the auditor did "
                  "not change' cannot be read from one year's filing alone.",
  "everything else": "no reading has been made."},
 "acceptances": sorted(entries, key=lambda e: e["acceptance_id"]),
}
(REPO / "docs/evidence/issue47_history/accepted_result_content.json").write_text(
    json.dumps(register, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
import collections
print("acceptances:", len(entries))
print(collections.Counter(e["metric_id"] for e in entries))
