"""One recorded E01 window end to end in a runtime tree: registration to public row.

Run from the root of a runtime tree that carries the registration patch (the
repository tree cannot build a historical Run). It registers a synthetic
confirmation for the window's one request - every item declined except the
accessions named with ``--confirm``, and the item ids named with
``--cannot-tell`` left undecided - so the answer is the test's, never a model's
and never a reading of the filing. It then shows what a batch sees at the same
window (the default LIVE installation, which has no registration to consume),
installs the window with the recorded registration, creates and freezes the
native Run under issue_47_v1, renders the public row, removes the registration
from the creator journal and reads the Run back in a separate process that
shares nothing: a recorded Run must replay from what its data root carries.

Zero provider, paid and SEC calls: the answer is supplied, and the sockets are
patched to fail for the whole of it.

Usage:
    python3 docs/evidence/issue47_history/e01-content-confirmed/recorded_e01_run.py \
        <work directory outside the tree> <company_id> <report_end> \
        [--confirm <accession>]... [--cannot-tell <item_id>]... [--output <json>]
"""
import argparse
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
result = [r for r in records if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == 'E01']
assert len(result) == 1
print(json.dumps({'run_id': manifest['run_id'], 'status': manifest['status'],
                  'requirement_id': manifest['requirement_id'],
                  'requirement_closure_hash': manifest['requirement_closure_hash'],
                  'result_id': result[0]['result_id'], 'value': result[0]['value'],
                  'quality': result[0]['quality'], 'publication': result[0]['publication'],
                  'reason_code': result[0]['reason_code'], 'records': len(records)}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("work", type=Path)
    parser.add_argument("company_id")
    parser.add_argument("report_end")
    parser.add_argument("--confirm", action="append", default=[])
    parser.add_argument("--cannot-tell", action="append", default=[])
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    work, company_id, report_end = arguments.work.resolve(), arguments.company_id, arguments.report_end
    assert ROOT not in work.parents and work != ROOT, "work directory must be outside the tree"
    from vnext import historical_ma_confirmation as confirmation
    from vnext.historical_projection import render_historical_run
    from vnext.historical_run import create_historical_run, install_historical_run_inputs
    from vnext.historical_event_items import successor_public_notes
    from vnext.historical_zero_ai_results import e01_confirmation_request
    from vnext.normal_period_selection import resolve_period_selection

    def decide(item):
        if item["item_id"] in arguments.cannot_tell:
            return "CANNOT_TELL_FROM_THE_ITEM_TEXT"
        if item["accession"] in arguments.confirm:
            return "REPORTS_A_TRANSACTION"
        return "DOES_NOT_REPORT_A_TRANSACTION"

    no_net = patch.object(socket.socket, "connect", side_effect=AssertionError("no net"))
    no_dns = patch.object(socket, "getaddrinfo", side_effect=AssertionError("no dns"))
    report = {"company_id": company_id, "report_end": report_end, "runtime_tree": str(ROOT),
              "calls": {"provider": 0, "paid": 0, "sec": 0},
              "answer_is": ("synthetic: every item declined except the confirmed accessions, the named "
                            "items left undecided; the test's answer, not a model's and not a reading"),
              "confirmed_accessions": arguments.confirm, "undecided_items": arguments.cannot_tell,
              "production_authorized": False}
    with no_net, no_dns:
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        request, _proofs = e01_confirmation_request(repo_root=ROOT, company_id=company_id,
                                                    period_selection=selection)
        missing = set(arguments.cannot_tell) - {item["item_id"] for item in request["items"]}
        assert not missing, "not items of this request: " + ", ".join(sorted(missing))
        output = json.dumps({"item_decisions": [
            {"item_id": item["item_id"], "decision": decide(item), "quote": item["text"][:120].strip()}
            for item in request["items"]]}).encode("utf-8")
        record, journal_path = confirmation.register_confirmation(
            request=request, period_selection_id=selection["selection_id"], output=output,
            mode="RECORDED_TEST_ONLY")
        report["registration"] = {"input_record_id": record["input_record_id"], "mode": record["mode"],
                                  "request_id": record["request_id"], "items": len(request["items"]),
                                  "counted": record["counted"]}
        try:
            # What a batch sees here: LIVE is the default, and a test
            # registration is not a LIVE one.
            default = install_historical_run_inputs(data_root=work / "data-live", company_id=company_id,
                                                    metric_id="E01", period_selection=selection)
            result = default["installed"]["primary_result"]
            report["default_installation"] = {"publication": result["publication"],
                                              "reason_code": result["reason_code"]}
            installed = install_historical_run_inputs(
                data_root=work / "data", company_id=company_id, metric_id="E01",
                period_selection=selection, assessment_mode="RECORDED_TEST_ONLY")
            run_dir = work / "run-E01"
            run = create_historical_run(data_root=work / "data", run_dir=run_dir,
                                        company_id=company_id, metric_id="E01",
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
                                    "notes": rendered["row"]["notes"],
                                    "evidence_count": len(rendered["evidence"]),
                                    "row_hash": rendered["receipt"]["row_hash"],
                                    "semantic_assessment_mode":
                                        rendered["receipt"].get("semantic_assessment_mode")}
            # A row built on a synthetic answer has to say so on the row and
            # in its receipt; one that did not would read like a model's.
            report["recorded_mode_marked"] = (
                "recorded test responses" in rendered["row"]["notes"]
                and rendered["receipt"].get("semantic_assessment_mode") == "RECORDED_TEST_ONLY")
            # And it says what this count is: the successor's meaning, not the
            # approved route's "filing items matched" note.
            report["successor_meaning_on_the_row"] = (
                rendered["row"]["notes"].startswith(successor_public_notes(repo_root=ROOT,
                                                                           metric_id="E01"))
                and "matched by the approved route" not in rendered["row"]["notes"])
        finally:
            # Removed before the cold read: a recorded Run must replay from
            # what its data root carries, not from the checkout that made it.
            journal_path.unlink()
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
    ok = (report["cold_read_matches"] and report["recorded_mode_marked"]
          and report["successor_meaning_on_the_row"])
    text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
    print(text)
    if arguments.output is not None:
        arguments.output.write_text(text + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
