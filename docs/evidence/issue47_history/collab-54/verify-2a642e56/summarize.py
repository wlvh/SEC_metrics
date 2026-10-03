"""One table from the two comparison files: python3 summarize.py compare-*.json > summary.json"""
import json
import sys

rows = []
for path in sys.argv[1:]:
    body = json.load(open(path, encoding="utf-8"))
    for position in body["positions"]:
        company_path = position["company_path"]
        row = {"company_id": body["company_id"], "report_end": body["report_end"],
               "metric_id": position["metric_id"]}
        if not isinstance(company_path, dict) or "result_id" not in company_path:
            row["company_path"] = "FAILED"
            row["failure"] = company_path
        else:
            read_back = position.get("separate_process_read_back", {})
            receipt = read_back.get("receipt_check", {})
            replay = read_back.get("native_cold_replay", {})
            row.update({
                "company_path": company_path["publication"], "reason_code": company_path["reason_code"],
                "value": company_path["value"] if not isinstance(company_path["value"], str)
                or len(company_path["value"]) < 60 else "text (" + str(len(company_path["value"])) + " chars)",
                "entities": company_path["entities"], "filings": company_path["filings"],
                "same_result_id_as_direct_path": position.get("same_result_id"),
                "same_period_selection_as_direct_path": position.get("same_period_selection"),
                "same_row_hash_as_direct_path": position.get("same_row_hash"),
                "receipt_check_hashes_verified": receipt.get("manifest_file_hashes_verified"),
                "receipt_check_same_result": company_path["result_id"] in (receipt.get("result_ids") or []),
                "native_cold_replay_status": replay.get("status"),
                "native_cold_replay_same_result": company_path["result_id"] in (replay.get("result_ids") or []),
                "native_cold_replay_rows_equal": replay.get("row_bytes_equal_compute_rows"),
                "native_cold_replay_evidence_equal": replay.get("evidence_bytes_equal_compute_rows"),
                "read_back_failure": read_back.get("failed")})
        rows.append(row)
print(json.dumps({"record_type": "ISSUE_47_COMPANY_HISTORICAL_CONSUMER_SUMMARY", "positions": rows,
                  "calls": {"provider": 0, "paid": 0, "sec": 0}}, indent=1, ensure_ascii=False))
