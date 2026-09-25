"""One recorded D04 position end to end in a runtime tree: registration to public row.

Run from the root of a runtime tree that carries the registration patch (the
repository tree cannot build a historical Run). It registers the synthetic
outputs the unit tests use - each finding is a relation the frozen checker
itself derives, so the response is the checker's own expected answer and says
nothing about the filing - installs the pinned period with that registration,
creates and freezes the native Run under issue_47_v1, reads it back in a
separate process that shares nothing, renders the public row, and asks the
default (LIVE) installation for the same position to show it is refused.

Zero provider, paid and SEC calls: the outputs are supplied, and the sockets are
patched to fail for the whole of it.

Usage:
    python3 docs/evidence/issue47_history/semantic-route-wiring/recorded_d04_run.py \
        <work directory outside the tree> <company_id> <report_end> [<output json>]
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

COLD_READ = """
import json, socket, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, %r)
with patch.object(socket.socket, 'connect', side_effect=AssertionError('no net')), \\
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('no dns')):
    from vnext.run_store import load_frozen_run
    manifest, records, _ = load_frozen_run(run_dir=Path(%r), repo_root=Path(%r))
result = [r for r in records if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == 'D04']
assert len(result) == 1
print(json.dumps({'run_id': manifest['run_id'], 'status': manifest['status'],
                  'requirement_id': manifest['requirement_id'],
                  'requirement_closure_hash': manifest['requirement_closure_hash'],
                  'result_id': result[0]['result_id'], 'value': result[0]['value'],
                  'quality': result[0]['quality'], 'publication': result[0]['publication'],
                  'reason_code': result[0]['reason_code'], 'records': len(records)}))
"""


def main():
    work, company_id, report_end = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
    output = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    assert ROOT not in work.parents and work != ROOT, "work directory must be outside the tree"
    from tests.vnext.test_historical_semantic_routes import synthetic_output
    from vnext.historical_model_session import recorded_historical_model_session
    from vnext.historical_projection import render_historical_run
    from vnext.historical_run import create_historical_run, install_historical_run_inputs
    from vnext.normal_period_selection import resolve_period_selection
    no_net = patch.object(socket.socket, "connect", side_effect=AssertionError("no net"))
    no_dns = patch.object(socket, "getaddrinfo", side_effect=AssertionError("no dns"))
    report = {"company_id": company_id, "report_end": report_end, "runtime_tree": str(ROOT),
              "calls": {"provider": 0, "paid": 0, "sec": 0},
              "outputs_are": "synthetic: the frozen checker's own relations, not a model's",
              "production_authorized": False}
    session = recorded_historical_model_session()
    with no_net, no_dns:
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        planned = session.plan(repo_root=ROOT, company_id=company_id, metric_id="D04",
                               period_selection=selection)
        record = session.register(
            repo_root=ROOT, company_id=company_id, metric_id="D04", period_selection=selection,
            outputs={r["request_id"]: synthetic_output(r) for r in planned["requests"]})
        report["registration"] = {"input_record_id": record["input_record_id"],
                                  "mode": record["mode"], "requests": len(planned["requests"]),
                                  "proposed_branch": record["assessment"]["proposed_branch"]}
        try:
            install_historical_run_inputs(data_root=work / "data-live", company_id=company_id,
                                          metric_id="D04", period_selection=selection)
            report["default_installation"] = "INSTALLED"
        except ValueError as error:
            report["default_installation"] = "REFUSED:" + str(error)
        installed = install_historical_run_inputs(
            data_root=work / "data", company_id=company_id, metric_id="D04",
            period_selection=selection, assessment_mode="RECORDED_TEST_ONLY")
        run_dir = work / "run-D04"
        run = create_historical_run(data_root=work / "data", run_dir=run_dir,
                                    company_id=company_id, metric_id="D04",
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
                                "period_end": rendered["row"]["period_end"],
                                "evidence_count": len(rendered["evidence"]),
                                "row_hash": rendered["receipt"]["row_hash"]}
    # The journal entry is removed before the cold read: a recorded Run must
    # replay from what its data root carries, not from the checkout that made it.
    session.discard()
    completed = subprocess.run(
        [sys.executable, "-c", COLD_READ % (str(ROOT / "scripts"), str(run_dir), str(work / "data"))],
        capture_output=True, text=True, cwd=str(work))
    report["separate_process_cold_read"] = (
        json.loads(completed.stdout.strip().splitlines()[-1]) if completed.returncode == 0
        else {"error": completed.stderr[-600:]})
    cold = report["separate_process_cold_read"]
    report["cold_read_matches"] = (
        "error" not in cold and cold["run_id"] == report["run"]["run_id"]
        and cold["result_id"] == report["run"]["result_id"] and cold["status"] == "FROZEN")
    text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
    print(text)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["cold_read_matches"] else 1


if __name__ == "__main__":
    sys.exit(main())
