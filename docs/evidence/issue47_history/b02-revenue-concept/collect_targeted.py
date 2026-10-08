"""Collect the B02 targeted round's per-period records into targeted-runs.json.

Usage: python3 collect_targeted.py <round out dir>

The round ran period-batch/frame_batch.py on the export-restored root with the
runtime tree at the commit that added the paired-measure check plus the
registration patch; each period's record names its Run, result and the two
read-backs (a separate process, and one with the derivation memo off).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEEP = ("value", "quality", "publication", "reason_code", "run_id", "result_id",
        "requirement_closure_hash", "row_hash", "evidence_count", "new_calls")


def main(out_dir):
    periods = {}
    for record in sorted(Path(out_dir).glob("*/period-*.json")):
        body = json.loads(record.read_text(encoding="utf-8"))
        position = body["positions"]["B02"]
        periods[body["label"]] = {
            "company_id": body["company_id"], "report_end": body["report_end"],
            **{key: position.get(key) for key in KEEP},
            "stage": position["stage"],
            "separate_process_read_back_same": all(
                position.get("separate_process_read_back", {}).get(key) == position.get(key)
                for key in ("run_id", "result_id")),
            "memo_off_read_back_same": all(
                position.get("memo_off_read_back", {}).get(key) == position.get(key)
                for key in ("run_id", "result_id")),
            "calls": body["calls"]}
    (HERE / "targeted-runs.json").write_text(json.dumps(
        {"record_type": "ISSUE_47_B02_PAIRED_MEASURE_TARGETED_RUNS", "periods": periods},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
