"""One recorded D02 Item 8 review end to end in a runtime tree: registration to public row.

Run from the root of a runtime tree that carries the registration patch (the
repository tree cannot build a historical Run). It registers a synthetic review
of the filing's one request - every must-decide block out except the ids named
with ``--in``, the ids named with ``--add`` counted beside them and the ids named
with ``--cannot-tell`` left undecided - so the answer is the test's, never a
model's and never a reading of the filing. It then builds the same position the
way a batch does (LIVE, with no registration to consume, so the keyword decides
Item 8), installs the position with the recorded review, creates and freezes the
native Run under issue_47_v1, renders the public row, removes the registration
from the creator journal and reads the Run back in a separate process that
shares nothing: a recorded Run must replay from what its data root carries.

Zero provider, paid and SEC calls: the answer is supplied, and the sockets are
patched to fail for the whole of it.

Usage:
    python3 docs/evidence/issue47_history/d02-item-8-review/recorded_d02_run.py \
        <work directory outside the tree> <company_id> <report_end> \
        [--in <block_id>]... [--add <block_id>]... [--cannot-tell <block_id>]... [--output <json>]
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
result = [r for r in records if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == 'D02']
assert len(result) == 1
print(json.dumps({'run_id': manifest['run_id'], 'status': manifest['status'],
                  'requirement_id': manifest['requirement_id'],
                  'result_id': result[0]['result_id'], 'quality': result[0]['quality'],
                  'publication': result[0]['publication'], 'reason_code': result[0]['reason_code'],
                  'records': len(records)}))
"""


def _run_summary(run):
    return {"run_id": run["manifest"]["run_id"], "status": run["manifest"]["status"],
            "requirement_id": run["manifest"]["requirement_id"],
            "requirement_closure_hash": run["manifest"]["requirement_closure_hash"],
            "result_id": run["result"]["result_id"], "quality": run["result"]["quality"],
            "publication": run["result"]["publication"], "reason_code": run["result"]["reason_code"],
            "new_calls": run["new_calls"]}


def _item_8_blocks(run_dir, data_root):
    from vnext.run_store import load_frozen_run
    _, records, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
    (candidate,) = [r for r in records if r["record_type"] == "DETERMINISTIC_TEXT_CANDIDATE"]
    return sorted(claim["block_index"] for claim in candidate["selected"].values()
                  if claim["section_id"] == "ITEM_8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("work", type=Path)
    parser.add_argument("company_id")
    parser.add_argument("report_end")
    parser.add_argument("--in", dest="included", action="append", default=[])
    parser.add_argument("--add", action="append", default=[])
    parser.add_argument("--cannot-tell", action="append", default=[])
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    work, company_id, report_end = arguments.work.resolve(), arguments.company_id, arguments.report_end
    assert ROOT not in work.parents and work != ROOT, "work directory must be outside the tree"
    from vnext import historical_legal_review as review
    from vnext.historical_projection import render_historical_run
    from vnext.historical_run import create_historical_run, install_historical_run_inputs
    from vnext.historical_text_input import d02_review_request
    from vnext.normal_period_selection import resolve_period_selection

    no_net = patch.object(socket.socket, "connect", side_effect=AssertionError("no net"))
    no_dns = patch.object(socket, "getaddrinfo", side_effect=AssertionError("no dns"))
    report = {"company_id": company_id, "report_end": report_end, "runtime_tree": str(ROOT),
              "calls": {"provider": 0, "paid": 0, "sec": 0},
              "answer_is": ("synthetic: every must-decide block out except the named ones, the "
                            "added blocks counted, the named blocks left undecided; the test's "
                            "answer, not a model's and not a reading"),
              "in": arguments.included, "added": arguments.add,
              "undecided": arguments.cannot_tell, "production_authorized": False}
    with no_net, no_dns:
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        request, _proofs = d02_review_request(repo_root=ROOT, company_id=company_id,
                                              period_selection=selection)
        texts = {block["block_id"]: block["text"] for block in request["blocks"]}
        must = set(request["must_decide"])
        assert set(arguments.included) | set(arguments.cannot_tell) <= must, "not must-decide"
        assert set(arguments.add) <= set(texts) - must, "not an addable block"

        def entry(identity):
            if identity in arguments.cannot_tell:
                return {"block_id": identity, "decision": "CANNOT_TELL_FROM_THE_TEXT",
                        "quote": texts[identity][:120]}
            if identity in arguments.included:
                return {"block_id": identity, "decision": "IN_SCOPE", "quote": texts[identity][:120]}
            return {"block_id": identity, "decision": "OUT_OF_SCOPE", "quote": None}

        output = json.dumps({"decisions": [entry(identity) for identity in request["must_decide"]],
                             "also_in_scope": [{"block_id": identity, "quote": texts[identity][:120]}
                                               for identity in arguments.add]}).encode("utf-8")
        record, journal_path = review.register_review(
            request=request, company_id=company_id, period_selection_id=selection["selection_id"],
            output=output, mode="RECORDED_TEST_ONLY")
        report["registration"] = {"input_record_id": record["input_record_id"],
                                  "mode": record["mode"], "request_id": record["request_id"],
                                  "blocks": len(request["blocks"]), "must_decide": len(must),
                                  "reviewed": record["reviewed"]}
        try:
            # What a batch sees here: LIVE is the default, a test registration
            # is not a LIVE one, and the keyword decides Item 8.
            default = install_historical_run_inputs(data_root=work / "data-live", company_id=company_id,
                                                    metric_id="D02", period_selection=selection)
            plain = create_historical_run(data_root=work / "data-live", run_dir=work / "run-D02-live",
                                          company_id=company_id, metric_id="D02",
                                          binding_id=default["binding"]["binding_id"], freeze=True)
            report["default_run"] = _run_summary(plain)
            report["default_item_8_blocks"] = _item_8_blocks(work / "run-D02-live", work / "data-live")
            installed = install_historical_run_inputs(
                data_root=work / "data", company_id=company_id, metric_id="D02",
                period_selection=selection, assessment_mode="RECORDED_TEST_ONLY")
            run_dir = work / "run-D02"
            run = create_historical_run(data_root=work / "data", run_dir=run_dir,
                                        company_id=company_id, metric_id="D02",
                                        binding_id=installed["binding"]["binding_id"], freeze=True)
            report["run"] = _run_summary(run)
            report["reviewed_item_8_blocks"] = _item_8_blocks(run_dir, work / "data")
            rendered = render_historical_run(data_root=work / "data", run_dir=run_dir, frozen=True,
                                             persist=True)
            report["public_row"] = {"status": rendered["row"]["status"],
                                    "period_end": rendered["row"]["period_end"],
                                    "notes": rendered["row"]["notes"],
                                    "evidence_count": len(rendered["evidence"]),
                                    "row_hash": rendered["receipt"]["row_hash"],
                                    "semantic_assessment_mode":
                                        rendered["receipt"].get("semantic_assessment_mode")}
            report["recorded_mode_marked"] = (
                "recorded test responses" in rendered["row"]["notes"]
                and rendered["receipt"].get("semantic_assessment_mode") == "RECORDED_TEST_ONLY")
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
    expected = sorted({int(identity[1:]) for identity in [*arguments.included, *arguments.add]})
    report["item_8_is_what_the_review_counts"] = report["reviewed_item_8_blocks"] == expected
    ok = (report["cold_read_matches"] and report["recorded_mode_marked"]
          and report["item_8_is_what_the_review_counts"]
          and report["default_run"]["result_id"] != report["run"]["result_id"])
    text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
    print(text)
    if arguments.output is not None:
        arguments.output.write_text(text + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
