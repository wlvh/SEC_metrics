"""Copy the target filing's records from a batch's D01 Runs into source-records.json.

Usage: python3 collect_records.py <runs root> <out.json> <label> [<label> ...]

A label names a Run directory ``run-<label>-D01``. For each, the target
filing's SOURCE_REFERENCE and RAW_BLOB records and the candidate's calculation
target are copied, so a case can rebuild the document from the saved bytes
(checkout or export) without the batch. Zero calls.
"""
import json
import sys
from pathlib import Path


def main(runs_root, out, *labels):
    filings = {}
    for label in labels:
        run = Path(runs_root) / ("run-" + label + "-D01")
        records = [json.loads(line) for line in (run / "records.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip()]
        candidate = next(r for r in records if r.get("record_type") == "DETERMINISTIC_TEXT_CANDIDATE")
        reference = next(r for r in records if r.get("record_type") == "SOURCE_REFERENCE"
                         and r.get("source_role") == "target_primary")
        blob = next(r for r in records if r.get("record_type") == "RAW_BLOB"
                    and r["raw_asset_id"] == reference["raw_asset_id"])
        filings[label] = {"calculation_target": candidate["calculation_target"],
                          "source_reference": reference, "raw_blob": blob,
                          "batch_candidate_hash": candidate["candidate_hash"]}
    Path(out).write_text(json.dumps(
        {"record_type": "ISSUE_47_D01_RUNNING_HEADER_SOURCE_RECORDS",
         "why": "The target filing's SOURCE_REFERENCE and RAW_BLOB records and the calculation "
                "target, copied from the 50-period batch's D01 Runs (closure 500ddf5f), so a "
                "case can rebuild the document from the saved bytes (checkout or export) "
                "without the batch.",
         "filings": filings}, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
