"""Break each N1 check the repository holds, one at a time; its case must fail.

The egress suite's injections run only in a patched tree. These hold the part
of N1 that lives in the repository - the registration contracts and the check
their consumers share - against ``tests/vnext/test_historical_counted_calls.py``
and D04's case in ``tests/vnext/test_historical_semantic_routes.py``, which CI
runs. Each injection edits one module in memory and runs the suite in a child
process whose ``vnext`` package searches a temporary directory holding only the
edited module before the checkout's own package, so the checkout is never
written (the mechanism of ``../../d02-item-8-review/fault_injections.py``). An
edit that does not hit exactly once, or does not compile, stops the run before
anything is judged; so does a control run - nothing edited - that fails or runs
no test.

Usage:
    python3 docs/evidence/issue47_history/model-egress/independent-review-2026-09-27-rereview/repository_injections.py
"""
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
FAST = "tests.vnext.test_historical_counted_calls"
D04 = ("tests.vnext.test_historical_semantic_routes.ARegisteredAssessmentTravelsToATextResultTest."
       "test_a_live_record_without_the_calls_that_answered_it_is_refused")
CALLS = REPO / "scripts/vnext/historical_counted_calls.py"
E01 = REPO / "scripts/vnext/historical_ma_confirmation.py"
D02 = REPO / "scripts/vnext/historical_legal_review.py"
SEMANTIC = REPO / "scripts/vnext/historical_semantic_results.py"

INJECTIONS = [
    ("E01_REGISTERS_LIVE_WITHOUT_CALLS", E01, (FAST,),
     '    _need(mode != "LIVE" or counted is not None, "E01_LIVE_CONFIRMATION_WITHOUT_COUNTED_CALLS")\n', ""),
    ("D02_REGISTERS_LIVE_WITHOUT_CALLS", D02, (FAST,),
     '    _need(mode != "LIVE" or counted is not None, "D02_LIVE_REVIEW_WITHOUT_COUNTED_CALLS")\n', ""),
    ("D04_REGISTERS_LIVE_WITHOUT_CALLS", SEMANTIC, (D04,),
     '    _need(mode != "LIVE" or counted is not None, "HISTORICAL_LIVE_ASSESSMENT_WITHOUT_COUNTED_CALLS")\n',
     ""),
    ("A_LIVE_D04_RECORD_IS_READ_WITHOUT_CALLS", SEMANTIC, (D04,),
     "    if mode == \"LIVE\":\n        from .historical_counted_calls import check_live_registration\n"
     "        check_live_registration(counted=counted, answered=answered, repo_root=ROOT)\n    elif",
     "    if False:\n        pass\n    elif"),
    ("NO_BLOCK_IS_ACCEPTED", CALLS, (FAST,),
     '    _need(counted is not None, "ISSUE_47_LIVE_REGISTRATION_WITHOUT_COUNTED_CALLS")\n', ""),
    ("THE_BLOCK_S_SEAL_IS_NOT_READ", CALLS, (FAST,),
     '    _need(mode in MODES and _holds(counted, "counted_calls_id")',
     '    _need(mode in MODES'),
    ("THE_BLOCK_S_MODE_IS_NOT_READ", CALLS, (FAST,),
     '          and counted.get("requirement_id") == REQUIREMENT_ID and counted.get("mode") == mode,',
     '          and counted.get("requirement_id") == REQUIREMENT_ID,'),
    ("THE_LEDGER_S_MODE_IS_NOT_READ", CALLS, (FAST,),
     '          and binding.get("execution_mode") == mode, "ISSUE_47_COUNTED_CALLS_LEDGER_CHANGED")',
     '          and True, "ISSUE_47_COUNTED_CALLS_LEDGER_CHANGED")'),
    ("NO_CALL_ANSWERS", CALLS, (FAST,),
     '    _need(type(calls) is list and len(calls) == len(answered) and bool(calls),',
     '    _need(type(calls) is list and len(calls) == len(answered),'),
    ("ANY_LEDGER_WILL_DO", CALLS, (FAST,),
     '    _need(counted["mode"] == "LIVE" and counted["ledger_binding"] == granted["ledger_binding"]',
     '    _need(counted["mode"] == "LIVE"'),
    ("ANY_TRANSPORT_WILL_DO", CALLS, (FAST,),
     '          and counted["transport"] == granted["transport"],\n', ',\n'),
    ("THE_GRANTED_RECORD_S_SEAL_IS_NOT_READ", CALLS, (FAST,),
     '    _need(_holds(granted, "granted_ledger_id") and granted.get("record_type") == GRANTED_TYPE',
     '    _need(granted.get("record_type") == GRANTED_TYPE'),
    ("NO_REGISTERED_APPROVAL_IS_NEEDED", CALLS, (FAST,),
     '    path = Path(repo_root) / GRANTED_LEDGER_PATH\n',
     '    path = Path(repo_root) / GRANTED_LEDGER_PATH\n'
     '    if not path.is_file():\n        return None\n'),
]


def run(edits, suites):
    """(failed cases, tests run, returncode) for ``suites`` with ``edits`` ({module: text})."""
    with tempfile.TemporaryDirectory() as tmp:
        for module, text in edits.items():
            target = Path(tmp) / module.name
            target.write_text(text, encoding="utf-8")
            py_compile.compile(str(target), doraise=True)
        code = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r); import vnext; "
                "vnext.__path__.insert(0, %r); sys.argv=['x', *%r]; import unittest; "
                "unittest.main(module=None)") % (str(REPO / "scripts"), str(REPO), tmp, list(suites))
        done = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True,
                              text=True, timeout=3600)
        failed = sorted({line.split(" ")[1] for line in done.stderr.splitlines()
                         if line.startswith(("FAIL: ", "ERROR: "))})
        ran = [int(line.split()[1]) for line in done.stderr.splitlines() if line.startswith("Ran ")]
        return failed, (ran[-1] if ran else 0), done.returncode


def main():
    originals = {path: path.read_text(encoding="utf-8") for path in (CALLS, E01, D02, SEMANTIC)}
    edited = {}
    for name, path, _, old, new in INJECTIONS:
        if originals[path].count(old) != 1:
            raise SystemExit("AN_INJECTION_EDIT_DOES_NOT_HIT_EXACTLY_ONCE:" + name)
        text = originals[path].replace(old, new)
        compile(text, str(path), "exec")
        edited[name] = text
    controls = {}
    for suites in sorted({tuple(suites) for _, _, suites, _, _ in INJECTIONS}):
        failed, ran, code = run({}, suites)
        if failed or code or not ran:
            raise SystemExit("THE_CONTROL_DID_NOT_RUN_CLEAN:%s:%s:%s:%s" % (suites, failed, ran, code))
        controls[" ".join(suites)] = ran
    results = []
    for name, path, suites, _, _ in INJECTIONS:
        failed, ran, code = run({path: edited[name]}, suites)
        results.append({"id": name, "file": path.relative_to(REPO).as_posix(),
                        "suites": list(suites), "caught": bool(failed) and code != 0,
                        "failed_cases": failed, "tests_run": ran})
        print(json.dumps(results[-1]), flush=True)
    body = {"record_type": "ISSUE_47_N1_REPOSITORY_FAULT_INJECTIONS", "controls": controls,
            "injections": results, "caught": sum(r["caught"] for r in results),
            "total": len(results), "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "repository-injections.json").write_text(
        json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if body["caught"] == body["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
