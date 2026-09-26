"""Verify Issue #47's model-egress patch offline, in a tree where it is applied, and seal the result.

Run from the root of a runtime tree that carries the issue_47_v1 registration
patch, after applying this directory's egress-registration.patch and minting:

    git apply docs/evidence/issue47_history/model-egress/egress-registration.patch
    python3 tools/vnext_mint_historical_requirement.py
    python3 docs/evidence/issue47_history/model-egress/verify.py

It never runs in the repository checkout: the patch is not applied there, and
the controller refuses issue_47_v1 there (which the repository's own
tests/vnext/test_historical_model_calls.py asserts). Steps, each recorded:

1. the patch is the one applied here (``git apply -R --check``) and the
   snapshot is minted for these bytes;
2. the repository's egress gate passes and names the one new caller;
3. the verification suite passes (every case, network refused);
4. every fault injection is caught, and by which case first (fail-fast, fast
   classes first; ``first_caught_by`` is not the full set of catching cases);
5. which frozen generations record the three boundary files, and so would be
   moved by applying the patch - measured from their manifests, not assumed.

Only if all of that holds is ``offline-verification.json`` sealed. Zero calls.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
HERE = "docs/evidence/issue47_history/model-egress"
PATCH = HERE + "/egress-registration.patch"
OUTPUT = HERE + "/offline-verification.json"
SUITE = "tests.vnext.test_historical_model_egress"
# Fast classes first, so fail-fast injections are decided without the slow ones.
ORDER = ("TheEgressGateNamesExactlyOneNewCaller", "OnlyIssue47sOwnAuthorityReachesTheCallPath",
         "TheLimitIsCumulativeAndTheAllowanceIsTheAuthoritys",
         "EveryCallIsCountedOnceAndStopsWhereTheCountCannotBeTrusted",
         "TheLivePathSendsThePlannedBytesOnceThroughTheControlledOpener",
         "ACompleteAssessmentRegistersOnlyFromItsOwnSlots")
BOUNDARY = ("scripts/vnext/invocation_control.py", "scripts/vnext/ai_adapter.py",
            "tools/check_provider_egress.py")
BOUND = ("scripts/vnext/historical_model_calls.py", "scripts/vnext/historical_model_egress.py",
         *BOUNDARY, "tools/vnext_mint_historical_requirement.py",
         "tests/vnext/test_historical_model_egress.py", HERE + "/verify.py", PATCH)
CALLS = "scripts/vnext/historical_model_calls.py"
EGRESS = "scripts/vnext/historical_model_egress.py"
INJECTIONS = [
    ("A_REQUEST_MAY_BE_REDRAWN", CALLS,
     [('        _need(request_digest not in state["requests"],\n'
       '              "ISSUE_47_MODEL_REQUEST_ALREADY_CLAIMED_NO_REDRAW")\n', "")]),
    ("A_SLOT_WITHOUT_A_TERMINAL_DOES_NOT_STOP", CALLS,
     [('                stopped.append(slot.name + "=UNKNOWN_PENDING_RECONCILIATION")\n', "")]),
    ("HTTP_402_DOES_NOT_STOP", CALLS,
     [('STOPS = frozenset({"HTTP_402", ', 'STOPS = frozenset({')]),
    ("UNKNOWN_USAGE_DOES_NOT_STOP", CALLS,
     [('"USAGE_UNKNOWN", "CONTEXT_REFERENCE_MISMATCH"})', '"CONTEXT_REFERENCE_MISMATCH"})'),
      ('            stop = stop or "USAGE_UNKNOWN"\n', "")]),
    ("NO_CUMULATIVE_LIMIT", CALLS,
     [('        _need(state["counts"][0] + 1 <= self.binding["limits"][0]\n',
       '        _need(True or state["counts"][0] + 1 <= self.binding["limits"][0]\n')]),
    ("A_CALLERS_ALLOWANCE_IS_TRUSTED", CALLS,
     [('    _need(all(policy[key] == value for key, value in _allowance_hashes(allowance).items()),',
       '    _need(True or all(policy[key] == value for key, value in _allowance_hashes(allowance).items()),')]),
    ("THE_ADAPTER_MATCHES_THE_CLASS_NAME_ONLY", "scripts/vnext/ai_adapter.py",
     [('    if (type(prepared_request).__module__ == __package__ + ".historical_model_calls"\n'
       '            and type(prepared_request).__name__ == "HistoricalSemanticRequest"):',
       '    if (type(prepared_request).__name__ == "HistoricalSemanticRequest"):')]),
    ("NO_SOURCE_CHECK_AT_THE_SOCKET", EGRESS,
     [("                source_check()\n", ""),
      ("                    before_socket_open=source_check)", "                    )")]),
    ("NO_GITHUB_RECHECK_BEFORE_THE_SOCKET", EGRESS,
     [("                model_allowance(repo_root=ROOT, delegation_reader=github_comment_reader)\n",
       "")]),
    ("RECORDED_BYTES_ARE_ONLY_REFUSED_AFTER_THE_CLAIM", EGRESS,
     [('        _need(recorded_wire is None, "ISSUE_47_MODEL_RECORDED_BYTES_CANNOT_RUN_LIVE")\n'
       '        _need(ledger.root', '        _need(ledger.root')]),
    ("A_SECOND_TRANSPORT_CALLER", EGRESS,
     [('    from sec_http import write_immutable_bytes\n',
       '    from sec_http import write_immutable_bytes\n'
       '    from . import ai_adapter as _adapter\n'
       '    if False:\n'
       '        _adapter._build_repository_transport(policy=None)\n')]),
    ("REGISTRATION_TAKES_A_MODE_OF_ITS_OWN", EGRESS,
     [("                               outputs=outputs, mode=ledger.mode)",
       '                               outputs=outputs, mode="LIVE")')]),
    ("A_FAILED_SLOT_MAY_BE_REGISTERED", EGRESS,
     [('_need(terminal["intent_id"] == intent["intent_id"] and terminal["status"] == "SUCCEEDED"\n'
       '              and terminal["stop_reason"] == "", "ISSUE_47_MODEL_SLOT_DID_NOT_SUCCEED")',
       '_need(terminal["intent_id"] == intent["intent_id"], "ISSUE_47_MODEL_SLOT_DID_NOT_SUCCEED")')]),
    ("THE_CONTROLLER_BRANCH_IS_ABSENT", "scripts/vnext/invocation_control.py",
     [('    if requirement.get("requirement_id") == "issue_47_v1":',
       '    if requirement.get("requirement_id") == "issue_47_v1_NOT":')]),
    ("PLANS_MAY_NOT_KEEP_AN_UNAVAILABLE_PRICE", "scripts/vnext/invocation_control.py",
     [('.get("requirement_id") in {"issue_28_v14", "issue_47_v1"})',
       '.get("requirement_id") in {"issue_28_v14"})')]),
    ("THE_GATE_DOES_NOT_NAME_THE_CALLER", "tools/check_provider_egress.py",
     [('    ("scripts/vnext/historical_model_egress.py", "_Transport.send"),\n', "")]),
]


def _run(arguments, **kwargs):
    return subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, **kwargs)


def _suite(fail_fast):
    names = [SUITE + "." + name for name in ORDER]
    run = _run([sys.executable, "-m", "unittest", *(["-f"] if fail_fast else []), *names],
               timeout=5400)
    lines = run.stderr.strip().splitlines()
    failed = [line.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "")
              for line in lines if line.startswith(("FAIL:", "ERROR:"))]
    return run.returncode, failed, (lines[-1] if lines else ""), next(
        (line for line in lines if line.startswith("Ran ")), "")


def _sha(path):
    import hashlib
    raw = (ROOT / path).read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def _moved_generations():
    moved = {}
    for manifest in sorted((ROOT / "requirements").glob("*/baseline_manifest.json")):
        files = json.loads(manifest.read_text(encoding="utf-8")).get(
            "execution_authority", {}).get("files", {})
        bound = {relative: files[relative] for relative in BOUNDARY if relative in files}
        differs = sorted(relative for relative, binding in bound.items()
                         if binding != _sha(relative))
        if bound:
            moved[manifest.parent.name] = differs
    return moved


def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "tools"))
    applied = _run(["git", "apply", "-R", "--check", PATCH])
    minted = _run([sys.executable, "tools/vnext_mint_historical_requirement.py", "--check"])
    from check_provider_egress import check_provider_egress
    gate = check_provider_egress(repo_root=ROOT)
    code, failed, summary, ran = _suite(fail_fast=False)
    suite = {"returncode": code, "failed": failed, "summary": summary, "ran": ran}
    print("suite", suite, flush=True)
    injections = []
    for name, path, edits in INJECTIONS:
        target = ROOT / path
        original = target.read_bytes()
        text = original.decode("utf-8")
        for old, _ in edits:
            assert text.count(old) == 1, (name, old[:60], text.count(old))
        for old, new in edits:
            text = text.replace(old, new)
        try:
            target.write_text(text, encoding="utf-8")
            code_i, failed_i, summary_i, _ = _suite(fail_fast=True)
        finally:
            target.write_bytes(original)
        row = {"id": name, "file": path, "outcome": "CAUGHT" if code_i else "NOT_CAUGHT",
               "first_caught_by": failed_i, "suite_result": summary_i}
        injections.append(row)
        print(json.dumps(row), flush=True)
    moved = _moved_generations()
    checks = {"patch_is_applied_here": applied.returncode == 0,
              "snapshot_minted_for_these_bytes": minted.returncode == 0,
              "egress_gate_passes": gate["status"] == "PASS",
              "suite_passes": code == 0,
              "every_injection_caught": all(r["outcome"] == "CAUGHT" for r in injections)}
    body = {"record_type": "ISSUE_47_MODEL_EGRESS_OFFLINE_VERIFICATION",
            "requirement_id": "issue_47_v1", "all_checks_passed": all(checks.values()),
            "checks": checks, "calls": {"provider": 0, "paid": 0, "sec": 0},
            "suite": suite, "egress_gate": {
                "repository_transport_factories": gate["repository_transport_factories"],
                "egress_capability_references": gate["egress_capability_references"],
                "gate_receipt_id": gate["gate_receipt_id"]},
            "fault_injections": injections,
            "generations_that_record_the_boundary_files": moved,
            "what_applying_the_patch_moves": (
                "every generation listed above records these files by bytes; those whose list "
                "is non-empty no longer validate their execution authority in a tree with the "
                "patch applied, so the patch cannot be applied beside them unchanged"),
            "bound_files": {path: _sha(path) for path in BOUND},
            "production_authorized": False, "live_call_authorized": False}
    from vnext.canonical import content_hash
    receipt = {**body, "receipt_id": content_hash(value=body)}
    if not receipt["all_checks_passed"]:
        print(json.dumps(checks, indent=1))
        return 2
    (ROOT / OUTPUT).write_text(json.dumps(receipt, ensure_ascii=False, indent=1, sort_keys=True)
                               + "\n", encoding="utf-8")
    print(json.dumps({"receipt_id": receipt["receipt_id"], "checks": checks}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
