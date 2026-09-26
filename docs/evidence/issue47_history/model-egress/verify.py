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
   classes first; ``first_caught_by`` is not the full set of catching cases).
   Two ways an injection can look caught without any case having seen it are
   closed. Injected text must compile: a syntax error fails the suite before
   one case runs. And an injection into a file the snapshot records by bytes
   is minted before the suite runs, because the byte binding refuses every
   change, harmless or not - a catch there says the file is bound, not that a
   case asserts the property the injection breaks. The file is restored and
   minted again afterwards, and the snapshot must come back byte for byte.
   A catch in a class fixture is recorded as one, with what it raised;
5. which frozen generations record the three boundary files, and so would be
   moved by applying the patch - measured from their manifests, not assumed;
6. the tree is back where it started: the patch still applies in reverse, the
   snapshot still matches, and every bound file has the bytes it had before.

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
      ('            stop = stop or "USAGE_UNKNOWN"\n', "            pass\n")]),
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
    # The caller is listed in both exact sets; each is broken on its own, so a
    # gate that checked only one of them is seen.
    ("THE_GATE_DOES_NOT_LIST_THE_TRANSPORT_CALLER", "tools/check_provider_egress.py",
     [('    ("scripts/vnext/historical_model_egress.py", "_Transport.send"),\n}\n'
       'ALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n',
       '}\nALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n')]),
    ("THE_GATE_DOES_NOT_LIST_THE_CAPABILITY_REFERENCE", "tools/check_provider_egress.py",
     [('ALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n'
       '    ("scripts/vnext/continuous_semantic_calls.py", "_Transport.send"),\n'
       '    ("scripts/vnext/historical_model_egress.py", "_Transport.send"),\n',
       'ALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n'
       '    ("scripts/vnext/continuous_semantic_calls.py", "_Transport.send"),\n')]),
]


def _run(arguments, **kwargs):
    return subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, **kwargs)


FIXTURES = ("setUpClass", "setUpModule", "tearDownClass", "tearDownModule")


def _failures(lines):
    """Each FAIL/ERROR block: the case, its class for a fixture, and the last line it raised."""
    rows = []
    for index, line in enumerate(lines):
        if not line.startswith(("FAIL: ", "ERROR: ")):
            continue
        case, _, where = line.split(": ", 1)[1].partition(" (")
        raised = ""
        for later in lines[index + 2:]:
            if later.startswith(("=" * 20, "-" * 20)):
                break
            if later.strip():
                raised = later.strip()
        rows.append({"case": case, **({"class": where.rstrip(")").split(".")[-1]}
                                      if case in FIXTURES else {}), "raised": raised[:300]})
    return rows


def _outcome(code, failures):
    """Only a failing case is a catch; a fixture failure is one, recorded as such."""
    if code == 0:
        return "NOT_CAUGHT"
    if any(row["case"] not in FIXTURES for row in failures):
        return "CAUGHT"
    return "CAUGHT_AT_FIXTURE" if failures else "FAILED_OUTSIDE_ANY_CASE"


def _suite(fail_fast):
    names = [SUITE + "." + name for name in ORDER]
    run = _run([sys.executable, "-m", "unittest", *(["-f"] if fail_fast else []), *names],
               timeout=5400)
    lines = run.stderr.strip().splitlines()
    failures = _failures(lines)
    return run.returncode, failures, (lines[-1] if lines else ""), next(
        (line for line in lines if line.startswith("Ran ")), "")


def _mint(check=False):
    return _run([sys.executable, "tools/vnext_mint_historical_requirement.py",
                 *(["--check"] if check else [])])


def _snapshot():
    return {path.relative_to(ROOT).as_posix(): path.read_bytes()
            for path in sorted((ROOT / "requirements/issue_47_v1").glob("*")) if path.is_file()}


def _recorded_by_the_snapshot():
    manifest = json.loads((ROOT / "requirements/issue_47_v1/baseline_manifest.json").read_text(
        encoding="utf-8"))
    return set(manifest["execution_authority"]["files"])


def _sha(path):
    import hashlib
    raw = (ROOT / path).read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def _generation_manifests():
    """Each generation's manifest bytes, so a reader can tell which snapshots were measured.

    A tree that is behind the repository measures stale generations; the first
    sealing attempt ran in one and was stopped when a comparison showed it.
    """
    return {manifest.parent.name: _sha(manifest.relative_to(ROOT).as_posix())
            for manifest in sorted((ROOT / "requirements").glob("*/baseline_manifest.json"))}


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
    minted = _mint(check=True)
    if applied.returncode or minted.returncode:
        print(applied.stderr, minted.stdout, minted.stderr)
        return 2
    before = {path: _sha(path) for path in BOUND}
    snapshot = _snapshot()
    recorded = _recorded_by_the_snapshot()
    from check_provider_egress import check_provider_egress
    gate = check_provider_egress(repo_root=ROOT)
    code, failures, summary, ran = _suite(fail_fast=False)
    suite = {"returncode": code, "failed": [row["case"] for row in failures],
             "summary": summary, "ran": ran}
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
        row = {"id": name, "file": path, "minted_for_the_injection": path in recorded}
        try:
            compile(text, path, "exec")
        except SyntaxError as error:
            row.update(outcome="INJECTION_DOES_NOT_COMPILE", error=str(error))
            injections.append(row)
            print(json.dumps(row), flush=True)
            continue
        try:
            target.write_text(text, encoding="utf-8")
            if row["minted_for_the_injection"]:
                assert _mint().returncode == 0, name
            code_i, failures_i, summary_i, _ = _suite(fail_fast=True)
        finally:
            target.write_bytes(original)
            if row["minted_for_the_injection"]:
                _mint()
        if _snapshot() != snapshot:
            print(json.dumps({"id": name, "stopped": "SNAPSHOT_DID_NOT_COME_BACK"}))
            return 2
        row.update(outcome=_outcome(code_i, failures_i),
                   first_caught_by=[failure["case"] for failure in failures_i],
                   failures=failures_i, suite_result=summary_i)
        injections.append(row)
        print(json.dumps(row), flush=True)
    moved = _moved_generations()
    restored = (_run(["git", "apply", "-R", "--check", PATCH]).returncode == 0
                and _mint(check=True).returncode == 0 and _snapshot() == snapshot
                and {path: _sha(path) for path in BOUND} == before)
    checks = {"patch_is_applied_here": applied.returncode == 0,
              "snapshot_minted_for_these_bytes": minted.returncode == 0,
              "egress_gate_passes": gate["status"] == "PASS",
              "suite_passes": code == 0,
              "every_injection_compiles": all(
                  r["outcome"] != "INJECTION_DOES_NOT_COMPILE" for r in injections),
              "every_injection_caught": all(
                  r["outcome"] in ("CAUGHT", "CAUGHT_AT_FIXTURE") for r in injections),
              "tree_restored_after_injections": restored}
    body = {"record_type": "ISSUE_47_MODEL_EGRESS_OFFLINE_VERIFICATION",
            "requirement_id": "issue_47_v1", "all_checks_passed": all(checks.values()),
            "checks": checks, "calls": {"provider": 0, "paid": 0, "sec": 0},
            "suite": suite, "egress_gate": {
                "repository_transport_factories": gate["repository_transport_factories"],
                "egress_capability_references": gate["egress_capability_references"],
                "gate_receipt_id": gate["gate_receipt_id"]},
            "fault_injections": injections,
            "generations_that_record_the_boundary_files": moved,
            "generation_manifests_measured": _generation_manifests(),
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
