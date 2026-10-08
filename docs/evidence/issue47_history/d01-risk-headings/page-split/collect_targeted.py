"""Collect the page-split round's per-period D01 records into targeted-runs.json.

Usage: python3 collect_targeted.py <round out dir> <batch out dir>

The round ran period-batch/frame_batch.py on the export-restored root, with the
runtime tree at the join plus the registration patch. Each period's D01 record
names its Run, result and both read-backs; the batch's record of the same
period is set beside it, so a control that did not move shows the same result.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _position(record):
    body = json.loads(record.read_text(encoding="utf-8"))
    position = body["positions"]["D01"]
    return body, position


def main(round_dir, batch_dir):
    periods = {}
    for record in sorted(Path(round_dir).glob("*/period-*.json")):
        body, position = _position(record)
        _, before = _position(Path(batch_dir) / body["label"] / record.name)
        lines = position["value"].split("\n")
        periods[body["label"]] = {
            "company_id": body["company_id"], "report_end": body["report_end"],
            "run_id": position["run_id"], "result_id": position["result_id"],
            "requirement_closure_hash": position["requirement_closure_hash"],
            "quality": position["quality"], "publication": position["publication"],
            "lines": len(lines),
            "lines_beginning_in_lower_case": [line[:60] for line in lines if line[:1].islower()],
            "separate_process_read_back_same": all(
                position.get("separate_process_read_back", {}).get(key) == position.get(key)
                for key in ("run_id", "result_id")),
            "memo_off_read_back_same": all(
                position.get("memo_off_read_back", {}).get(key) == position.get(key)
                for key in ("run_id", "result_id")),
            "batch": {"result_id": before["result_id"], "lines": len(before["value"].split("\n")),
                      "requirement_closure_hash": before["requirement_closure_hash"]},
            "same_result_as_the_batch": before["result_id"] == position["result_id"],
            "calls": body["calls"]}
    (HERE / "targeted-runs.json").write_text(json.dumps(
        {"record_type": "ISSUE_47_D01_PAGE_SPLIT_TARGETED_RUNS", "periods": periods},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
