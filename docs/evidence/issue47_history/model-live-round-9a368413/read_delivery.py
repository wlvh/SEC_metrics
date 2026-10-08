"""Read the round's saved Runs through the normal three-layer predicates.

Reads existing receipts and registers only; creates no Run and makes no call.
Run from any directory after copying the canonical e01/d02/d04 batch outputs.
"""
import hashlib
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from vnext import historical_coverage as coverage
from vnext.historical_run_receipts import classify_result, read_run_receipt


def main():
    rows = []
    with patch.object(socket.socket, "connect", side_effect=AssertionError("no network")), \
         patch.object(socket, "getaddrinfo", side_effect=AssertionError("no DNS")):
        defects = coverage.known_result_defects(repo_root=REPO)
        acceptances = coverage.independent_content_acceptances(repo_root=REPO)
        for group in ("e01", "d02", "d04"):
            for period_file in sorted((HERE / group).glob("*/period-*.json")):
                period = json.loads(period_file.read_text())
                assert period["calls"] == {"provider": 0, "paid": 0, "sec": 0}
                for metric, position in period["positions"].items():
                    assert position["stage"] == "PUBLIC_ROW"
                    for key in ("separate_process_read_back", "memo_off_read_back"):
                        assert position[key]["run_id"] == position["run_id"]
                        assert position[key]["result_id"] == position["result_id"]
                    run_dir = period_file.parent / ("run-" + period["label"] + "-" + metric)
                    receipt = read_run_receipt(run_dir=run_dir)
                    result, = receipt["results"]
                    company, end = period["company_id"], period["report_end"]
                    defect = coverage._matching_defect(
                        defects=defects, company_id=company, metric_id=metric,
                        report_end=end, result=result, receipt=receipt)
                    acceptance, reason, findings = coverage._acceptance_for_position(
                        acceptances=acceptances, company_id=company, metric_id=metric,
                        report_end=end, result=result)
                    layers = coverage._delivery(
                        receipt=receipt, result=result, status=classify_result(result),
                        defect=defect, defects=defects, acceptance=acceptance,
                        acceptance_reason=reason, acceptance_findings=findings,
                        row={"receipt": receipt, "bundle": receipt["public_row"],
                             "rendered_by_other_runs": 0})
                    rows.append({"company_id": company, "metric_id": metric,
                                 "report_end": end, "layers": layers,
                                 "quality": result["quality"],
                                 "publication": result["publication"],
                                 "value_sha256": hashlib.sha256(
                                     str(result["value"]).encode()).hexdigest()})
    modeled = {}
    summaries = HERE.parent / "model-egress/runtime-original-path-docker"
    for name in ("first-e01.json", "e01-rest.json", "d02.json", "d04-run.json"):
        summary = json.loads((summaries / name).read_text())
        assert summary["stop"] is None and summary["stopped"] == []
        for key, value in summary["positions"].items():
            assert key not in modeled
            modeled[key] = value
    assert len(modeled) == 22 and sum(v["requests"] for v in modeled.values()) == 35
    found = {r["metric_id"] + ":" + r["company_id"] + ":" + r["report_end"] for r in rows}
    for key, modeled_position in modeled.items():
        if key in found:
            assert modeled_position["registered"]["mode"] == "LIVE"
            continue
        metric, company, end = key.split(":")
        reason = ("NEW_MODEL_ASSESSMENT_NOT_REGISTERED_AFTER_CONTRACT_FAILURE"
                  if modeled_position["registered"] is None
                  else "NEW_NATIVE_BUILD_NOT_YET_COMPLETED")
        rows.append({"company_id": company, "metric_id": metric, "report_end": end,
                     "layers": {name: {"proven": False, "reason": reason}
                                for name in ("native_run", "public_row", "content_acceptance")},
                     "unsuccessful_slots": modeled_position["unsuccessful"],
                     "old_results_not_consulted_or_relabelled": True})
    report = {"record_type": "ISSUE_47_NORMAL_MODEL_DELIVERY_READ", "positions": rows,
              "scope": "All 22 positions of this 35-call round; old results are not assessed by this read.",
              "approved_positions": 22,
              "new_live_registered_positions": sum(v["registered"] is not None for v in modeled.values()),
              "layer_counts": {name: sum(row["layers"][name]["proven"] for row in rows)
                               for name in ("native_run", "public_row", "content_acceptance")},
              "calls": [0, 0, 0], "production_authorized": False}
    (HERE / "normal-delivery.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(report["layer_counts"]))


if __name__ == "__main__":
    main()
