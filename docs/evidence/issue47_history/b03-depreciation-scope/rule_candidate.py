"""Run the candidate D&A rule over the nine B03 filings and record what it answers.

The rule lives in scripts/vnext/historical_da_scope_candidate.py and no route
imports it; this measures what adopting it would move. Zero network calls.
Usage, from the repository root:
    python3 docs/evidence/issue47_history/b03-depreciation-scope/rule_candidate.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
from vnext.historical_da_scope_candidate import (COMPOSITION, DIRECT, WITHHELD_REASON,  # noqa: E402
                                                 annual_facts, da_scope_answer)

HERE = Path(__file__).resolve().parent


def main():
    reading = json.loads((REPO / "docs/evidence/issue47_history/content-acceptance/"
                          "cross-source-read.json").read_text(encoding="utf-8"))["per_position"]
    finding = json.loads((HERE / "finding.json").read_text(encoding="utf-8"))["per_position"]
    positions = {}
    for label, case in sorted(reading.items()):
        if "error" in case or "B03" not in case["metrics"]:
            continue
        identity = case["metrics"]["B03"].get("checked_identity") or {}
        if identity.get("period_start") is None:
            continue
        end = identity.get("period_end") or case["period_end"]
        facts = annual_facts(raw_bytes=(REPO / case["document"]).read_bytes(),
                             period_start=identity["period_start"], period_end=end,
                             concepts=DIRECT + COMPOSITION)
        answer = da_scope_answer(facts=facts)
        chain = finding[label]["chain_takes"]
        taken = answer.get("selected") or {}
        positions[label] = {
            "document": case["document"], "period": [identity["period_start"], end],
            "rule_answer": answer["status"], "why": answer["why"],
            "rule_takes": taken.get("concept"), "rule_value": taken.get("value"),
            "approved_chain_takes": chain,
            "moves": (answer["status"] == "WITHHOLD"
                      or (answer["status"] == "TAKE" and taken.get("concept") != chain)),
            "candidates": [{key: fact[key] for key in ("concept", "value", "decimals",
                                                       "context_ref", "fact_ordinal")}
                           for fact in answer["candidates"]]}
    report = {
        "record_type": "ISSUE_47_B03_DA_SCOPE_RULE_CANDIDATE",
        "rule": "scripts/vnext/historical_da_scope_candidate.py (not imported by any route)",
        "rule_in_words": (
            "Compare only the three direct concepts for exactly the target annual "
            "duration, undimensioned, in USD; two values conflict only beyond the "
            "precision each fact reports. If all agree, take the first in chain order "
            "(the approved selection). If they conflict and the filing tags "
            "Depreciation and AmortizationOfIntangibleAssets for the period, take the "
            "one direct candidate equal to their sum. Otherwise withhold by name as "
            + WITHHELD_REASON + ", with every candidate. Never add back, never "
            "prefer the larger number."),
        "positions": positions,
        "moves": sorted(label for label, row in positions.items() if row["moves"]),
        "adoption": ("a change to which fact an approved Spec selects, so a revision "
                     "through the existing mechanism; until then both B03 routes keep "
                     "their meaning and Salesforce stays withdrawn as a registered defect"),
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "rule-candidate.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"moves": report["moves"]}, indent=1))


if __name__ == "__main__":
    main()
