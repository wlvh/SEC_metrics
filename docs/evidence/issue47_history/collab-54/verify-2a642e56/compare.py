"""Compare #54's company-package historical Runs with #47's own entry on the same code.

Usage (from the root of a company runtime installed by #54's tools/vnext_company.py):
    SEC_METRICS_SOURCE_TRUST_ROOT=<trust root> python3 compare.py <state root> <company> \
        <report end> <direct matrix.json> <out.json>

For each metric with a committed candidate under ``<state root>/updates/historical/
<report end>/``, it records the company Run's receipt, then reads the Run back in a
fresh process two ways that are reported separately: the receipt check (the
manifest's three file hashes, read_run_receipt) and the native cold replay
(load_frozen_run and render_historical_run over the Run's own data root, the row
compared byte for byte with the rows the compute wrote). It then compares the
result, period selection, entity, filings and row with #47's direct-path Run of
the same position (period_runs.py on the same code with the full restored root).
Zero calls.
"""
import json
import subprocess
import sys
from pathlib import Path

READ_BACK = r'''
import json, sys
from pathlib import Path
sys.path[:0] = ["scripts", "."]
from vnext.run_store import load_frozen_run
from vnext.historical_run_receipts import read_run_receipt
from vnext.historical_projection import render_historical_run
from vnext.publication import _csv_bytes, METRIC_FIELDS, EVIDENCE_FIELDS
work, metric = Path(sys.argv[1]), sys.argv[2]
run_dir = work / "runs" / metric
receipt = read_run_receipt(run_dir=run_dir)
manifest, records, _ = load_frozen_run(run_dir=run_dir, repo_root=work / "data")
rendered = render_historical_run(data_root=work / "data", run_dir=run_dir, frozen=True)
matrix = _csv_bytes(rows=[rendered["row"]], fieldnames=METRIC_FIELDS)
evidence = _csv_bytes(rows=rendered["evidence"], fieldnames=EVIDENCE_FIELDS)
print(json.dumps({
    "receipt_check": {"manifest_file_hashes_verified": receipt.get("manifest_file_hashes_verified"),
                      "run_id": receipt.get("run_id"),
                      "result_ids": [r["result_id"] for r in receipt.get("results", [])]},
    "native_cold_replay": {"status": manifest.get("status"), "run_id": manifest.get("run_id"),
                           "result_ids": sorted(r["result_id"] for r in records
                                                if r.get("record_type") == "METRIC_RESULT"),
                           "row_bytes_equal_compute_rows": matrix == (work / "rows/metrics_matrix.csv").read_bytes(),
                           "evidence_bytes_equal_compute_rows": evidence == (work / "rows/metric_evidence.csv").read_bytes()}}))
'''


def main(state_root, company, report_end, direct_matrix, out):
    runtime = Path.cwd()
    direct = {p["metric_id"]: p for p in json.loads(Path(direct_matrix).read_text())["positions"]}
    rows = []
    base = Path(state_root) / "updates/historical" / report_end
    for metric_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        metric = metric_dir.name
        row = {"metric_id": metric}
        current = metric_dir / "current.json"
        failure = metric_dir / "latest_failure.json"
        if not current.is_file():
            row["company_path"] = json.loads(failure.read_text()) if failure.is_file() else "NOT_RUN"
            rows.append(row)
            continue
        pointer = json.loads(current.read_text())
        candidate = pointer["candidate"]
        receipt = candidate["receipt"]
        (result,) = [r for r in receipt["results"] if r["metric_id"] == metric]
        work = metric_dir / "attempts" / pointer["attempt_id"]
        process = subprocess.run([sys.executable, "-c", READ_BACK, str(work), metric], cwd=runtime,
                                 capture_output=True, text=True)
        row["company_path"] = {
            "requirement_id": receipt["requirement_id"], "run_id": receipt["run_id"],
            "result_id": result["result_id"], "publication": result["publication"],
            "reason_code": result["reason_code"], "value": result["value"],
            "entities": result["entities"], "filings": result["filings"],
            "period": [result["period_start"], result["period_end"]],
            "period_selection_id": candidate["period_selection"]["selection_id"],
            "row_hash": receipt["public_row"].get("row_hash")}
        row["separate_process_read_back"] = (json.loads(process.stdout.strip().splitlines()[-1])
                                             if process.returncode == 0
                                             else {"failed": process.stderr.strip().splitlines()[-1:]})
        mine = direct.get(metric)
        if mine:
            row["direct_path"] = {"result_id": mine.get("result_id"), "row_hash": mine.get("row_hash"),
                                  "selection_id": mine.get("selection_id"),
                                  "publication": mine.get("publication"), "reason_code": mine.get("reason_code")}
            row["same_result_id"] = mine.get("result_id") == result["result_id"]
            row["same_period_selection"] = mine.get("selection_id") == candidate["period_selection"]["selection_id"]
            row["same_row_hash"] = mine.get("row_hash") == receipt["public_row"].get("row_hash")
        rows.append(row)
    Path(out).write_text(json.dumps({"record_type": "ISSUE_47_COMPANY_HISTORICAL_CONSUMER_CHECK",
                                     "company_id": company, "report_end": report_end,
                                     "positions": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
                                    indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(rows, indent=1, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main(*sys.argv[1:])
