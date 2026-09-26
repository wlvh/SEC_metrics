"""One pinned bank position end to end, on the one root where a bank period resolves.

Every JPMorgan period stops at selection on this repository's saved catalog: the
saved history blocks' bodies lie outside the ranges the saved index declares for
them. The refresh chain in ``tests/vnext/test_historical_sec_session.py``
(``ARefreshIsFinishedWhenThePlanStopsAskingForIt``) builds a recorded root whose
index is re-derived from those same saved blocks - each block's declared range
becomes its own body's first and last filing date - and on that root FY2025
resolves. Everything else it reads is this repository's saved bytes: the 10-K,
the company facts, the six history blocks. So this is a test of the mechanism
on real material, not a delivery: the derived index is ``RECORDED_TEST_ONLY``.

It runs the chain a batch runs - selection, installation into a fresh data root,
native Run under issue_47_v1, freeze, public row, and a separate process reading
the Run back from its own data root - and compares the value with the ordinary
route's on the same filing. Run from the root of a runtime tree that carries the
registration patch.

Usage:
    python3 docs/evidence/issue47_history/financial-route/recorded_bank_run.py \
        <work directory outside the tree> <metric_id> [<output json>]
"""
import json
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
BANK, CIK, REPORT_END = "jpmorgan_chase", 19617, "2025-12-31"

COLD_READ = """
import json, socket, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, %r)
with patch.object(socket.socket, 'connect', side_effect=AssertionError('no net')), \\
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('no dns')):
    from vnext.run_store import load_frozen_run
    manifest, records, _ = load_frozen_run(run_dir=Path(%r), repo_root=Path(%r))
result = [r for r in records if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == %r]
assert len(result) == 1
print(json.dumps({'run_id': manifest['run_id'], 'status': manifest['status'],
                  'requirement_id': manifest['requirement_id'],
                  'result_id': result[0]['result_id'], 'value': result[0]['value'],
                  'quality': result[0]['quality'], 'records': len(records)}))
"""


def source_root(work):
    """The recorded root with the re-derived index, built once under ``work``."""
    from tests.vnext.test_historical_sec_session import (
        ARefreshIsFinishedWhenThePlanStopsAskingForIt as Chain)
    from vnext.historical_sec_session import (install_historical_source_inputs,
                                              recorded_historical_session)
    from sec_urls import submissions_url
    built = work / "ledger" / "source-inputs"
    if (built / "source-baseline.json").is_file():
        return built, "REUSED_FROM_AN_EARLIER_RUN_OF_THIS_SCRIPT"
    payload, measured = Chain._measure(ROOT)
    session = recorded_historical_session(
        root=work / "ledger", company_ids=(BANK,),
        response={submissions_url(cik=CIK): Chain._derived_index(payload, measured)})
    install_historical_source_inputs(root=session.data_root)
    capture = session.capture(company_id=BANK, url=submissions_url(cik=CIK))
    return Path(session.data_root), capture


def main():
    work, metric_id = Path(sys.argv[1]).resolve(), sys.argv[2]
    output = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    assert ROOT not in work.parents and work != ROOT, "work directory must be outside the tree"
    from vnext.historical_projection import render_historical_run
    from vnext.historical_run import create_historical_run, install_historical_run_inputs
    from vnext.normal_period_selection import resolve_period_selection
    from vnext.ordinary_financial_results import resolve_current_financial_metric
    report = {"company_id": BANK, "report_end": REPORT_END, "metric_id": metric_id,
              "runtime_tree": str(ROOT), "calls": {"provider": 0, "paid": 0, "sec": 0},
              "source_root_is": "RECORDED_TEST_ONLY: this repository's saved bytes with the "
                                "submissions index re-derived from its own saved history blocks",
              "production_authorized": False}
    no_net = patch.object(socket.socket, "connect", side_effect=AssertionError("no net"))
    no_dns = patch.object(socket, "getaddrinfo", side_effect=AssertionError("no dns"))
    with no_net, no_dns:
        root, capture = source_root(work)
        report["index_capture"] = capture.get("status") if isinstance(capture, dict) else capture
        selection = resolve_period_selection(repo_root=root, company_id=BANK,
                                             report_end=REPORT_END)
        report["selection"] = {"selection_id": selection["selection_id"],
                               "loaded_inventories": selection["loaded_inventories"],
                               "target_accession": selection["current_filing"]["accessionNumber"]}
        ordinary = resolve_current_financial_metric(repo_root=ROOT, company_id=BANK,
                                                    metric_id=metric_id)
        report["ordinary_value"] = ordinary["result"]["value"]
        try:
            installed = install_historical_run_inputs(
                data_root=work / "data", company_id=BANK, metric_id=metric_id,
                period_selection=selection, source_root=root)
        except ValueError as error:
            report["installation"] = "REFUSED:" + str(error)
            text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
            print(text)
            if output is not None:
                output.write_text(text + "\n", encoding="utf-8")
            return 1
        report["installation"] = {"binding_id": installed["binding"]["binding_id"],
                                  "source_proofs": [p["document_name"] for p in
                                                    installed["installed"]["source_proofs"]]}
        run_dir = work / ("run-" + metric_id)
        run = create_historical_run(data_root=work / "data", run_dir=run_dir, company_id=BANK,
                                    metric_id=metric_id,
                                    binding_id=installed["binding"]["binding_id"], freeze=True)
        report["run"] = {"run_id": run["manifest"]["run_id"], "status": run["manifest"]["status"],
                         "requirement_id": run["manifest"]["requirement_id"],
                         "requirement_closure_hash": run["manifest"]["requirement_closure_hash"],
                         "target_period": run["manifest"]["target_period"],
                         "result_id": run["result"]["result_id"], "value": run["result"]["value"],
                         "quality": run["result"]["quality"],
                         "publication": run["result"]["publication"],
                         "reason_code": run["result"]["reason_code"],
                         "new_calls": run["new_calls"]}
        rendered = render_historical_run(data_root=work / "data", run_dir=run_dir, frozen=True,
                                         persist=True)
        report["public_row"] = {"status": rendered["row"]["status"],
                                "value": rendered["row"]["value"],
                                "period_start": rendered["row"]["period_start"],
                                "period_end": rendered["row"]["period_end"],
                                "evidence_count": len(rendered["evidence"]),
                                "row_hash": rendered["receipt"]["row_hash"]}
    completed = subprocess.run(
        [sys.executable, "-c", COLD_READ % (str(ROOT / "scripts"), str(run_dir),
                                            str(work / "data"), metric_id)],
        capture_output=True, text=True, cwd=str(work))
    report["separate_process_cold_read"] = (
        json.loads(completed.stdout.strip().splitlines()[-1]) if completed.returncode == 0
        else {"error": completed.stderr[-600:]})
    cold = report["separate_process_cold_read"]
    report["matches"] = {
        "cold_read": ("error" not in cold and cold["run_id"] == report["run"]["run_id"]
                      and cold["result_id"] == report["run"]["result_id"]
                      and cold["status"] == "FROZEN"),
        "ordinary_value": report["run"]["value"] == report["ordinary_value"]}
    text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
    print(text)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
    return 0 if all(report["matches"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
