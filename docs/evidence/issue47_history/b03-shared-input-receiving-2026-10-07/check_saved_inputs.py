"""Call the thin historical consumer on four saved annual primaries.

Uses no company installation, Run, provider, source acquisition or old answer
replay. The selected amounts are explicit regression inputs from the prior
source reading; each is checked again against the actual inline primary.
"""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import time

from vnext.historical_zero_ai_results import inspect_selected_historical_depreciation_input


ROOT = Path(__file__).resolve().parents[4]
READING = ROOT / "docs/evidence/issue47_history/content-acceptance/cross-source-read.json"


def check():
    reading = json.loads(READING.read_text())["per_position"]
    rows = []
    for label, amounts, expected in (
        ("marriott-2024", [("depreciation", "Depreciation", "128000000"),
            ("amortization", "AmortizationOfIntangibleAssets", "255000000")], "KEEP"),
        ("marriott-2025", [("depreciation", "Depreciation", "145000000"),
            ("amortization", "AmortizationOfIntangibleAssets", "313000000")], "KEEP"),
        ("ford-2025", [("depreciation_and_amortization",
            "DepreciationDepletionAndAmortization", "15974000000")], "WITHHOLD"),
        ("salesforce-2026", [("depreciation_and_amortization",
            "DepreciationDepletionAndAmortization", "1200000000")], "WITHHOLD"),
    ):
        case = reading[label]
        identity = case["metrics"]["B03"]["checked_identity"]
        entity, = identity["entities"]
        period = {name: identity[name] for name in ("period_start", "period_end")}
        path = ROOT / case["document"]
        raw = path.read_bytes()
        original_sha = hashlib.sha256(raw).hexdigest()
        observations = [{"semantic_role": role, "value": amount,
            "source_binding": {"concept": "us-gaap:" + concept, "entity": entity}}
            for role, concept, amount in amounts]
        start = time.perf_counter()
        answer = inspect_selected_historical_depreciation_input(raw_bytes=raw,
            entity=entity, period=period, observations=observations)
        elapsed = time.perf_counter() - start
        assert answer["status"] == expected, (label, answer)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original_sha
        if label == "ford-2025":
            assert "Model e asset impairment" in answer["impairment_inclusion"]["footnote_text"]
            assert answer["impairment_inclusion"]["selected_visible_total"] == "15,974"
        if label == "salesforce-2026":
            assert answer["filing_answer"]["status"] == "WITHHOLD"
            assert {Decimal(row["value"]) for row in answer["filing_answer"]["candidates"]} == {
                Decimal("1200000000"), Decimal("3631000000")}
        rows.append({"position": label, "source_path": case["document"],
            "source_sha256": original_sha, "entity": entity, "period": period,
            "observations": observations, "expected_status": expected,
            "wall_seconds": elapsed, "answer": answer,
            "source_bytes_unchanged": True})
    return {"record_type": "HISTORICAL_SHARED_B03_SAVED_INPUT_CHECK",
        "rows": rows, "source_reparsing_shared_per_case": True,
        "company_installs": 0, "copied_source_bytes": 0,
        "calls": {"provider": 0, "paid": 0, "sec": 0},
        "new_runs": 0, "complete_metric_accepted": False,
        "scope": "Actual historical input consumer plus full primary parser; not company CLI/save/read validation."}


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2))
