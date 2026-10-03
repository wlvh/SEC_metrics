"""Fault injections for B03's D&A scope gate, run on an in-memory copy of the route.

The checkout is not edited: each injection compiles the route module's source
with one edit (the edit must apply exactly once) and installs it as
``vnext.historical_zero_ai_results`` in a fresh interpreter before the test
module imports it, with a bytecode cache the run owns. A control with no edit
must pass; each injection must fail in the test written for it.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/b03-bank-structural/injections.py <output.json>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MODULE = REPO / "scripts" / "vnext" / "historical_zero_ai_results.py"
GATE = ('if (metric_id == "B03" and result["publication"] == "PUBLISHED"\n'
        '                and result["reason_code"] == "PASS"):')
INJECTIONS = {
    "CONTROL": None,
    # The gate before the fix: any published result is asked.
    "ASK_ANY_PUBLISHED_RESULT": 'if (metric_id == "B03" and result["publication"] == "PUBLISHED"):',
    # Applicability alone: a bank is no longer asked, a first short period still is.
    "ASK_ANY_APPLICABLE_PUBLISHED_RESULT": (
        'if (metric_id == "B03" and result["publication"] == "PUBLISHED"\n'
        '                and result["applicability"] == "APPLICABLE"):'),
}
EXPECTED_FAILING = {
    "CONTROL": set(),
    "ASK_ANY_PUBLISHED_RESULT": {
        "test_a_structural_answer_is_kept_where_the_filing_tags_a_d_and_a_total",
        "test_an_answer_that_does_not_depend_on_d_and_a_is_not_rewritten"},
    "ASK_ANY_APPLICABLE_PUBLISHED_RESULT": {
        "test_an_answer_that_does_not_depend_on_d_and_a_is_not_rewritten"},
}
RUNNER = r'''
import importlib.util, sys, types, unittest, json
sys.path.insert(0, %(scripts)r); sys.path.insert(0, %(repo)r)
import vnext
source = open(%(module)r).read()
edit = %(edit)r
if edit is not None:
    if source.count(%(gate)r) != 1:
        raise SystemExit("THE_GATE_DOES_NOT_APPLY_EXACTLY_ONCE")
    source = source.replace(%(gate)r, edit)
module = types.ModuleType("vnext.historical_zero_ai_results")
module.__file__ = %(module)r; module.__package__ = "vnext"
sys.modules["vnext.historical_zero_ai_results"] = module
exec(compile(source, %(module)r, "exec"), module.__dict__)
vnext.historical_zero_ai_results = module
from tests.vnext import test_historical_da_scope_route as cases
suite = unittest.defaultTestLoader.loadTestsFromTestCase(cases.AnAnswerThatTookNoDAIsNotAsked)
result = unittest.TestResult(); suite.run(result)
failing = sorted(test.id().rsplit(".", 1)[1] for test, _ in result.failures + result.errors)
print(json.dumps({"ran": result.testsRun, "failing": failing}))
'''


def main():
    out = Path(sys.argv[1])
    rows = []
    for name, edit in INJECTIONS.items():
        with tempfile.TemporaryDirectory() as cache:
            code = RUNNER % {"scripts": str(REPO / "scripts"), "repo": str(REPO),
                             "module": str(MODULE), "edit": edit, "gate": GATE}
            done = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), capture_output=True,
                                  text=True, timeout=1800,
                                  env={"PATH": "/usr/bin:/bin", "PYTHONPYCACHEPREFIX": cache,
                                       "HOME": str(Path.home())})
        if done.returncode != 0:
            raise SystemExit(name + ":RUNNER_FAILED:" + done.stderr[-600:])
        measured = json.loads(done.stdout.strip().splitlines()[-1])
        caught = set(measured["failing"]) == EXPECTED_FAILING[name] and measured["ran"] == 2
        rows.append({"injection": name, "ran": measured["ran"], "failing": measured["failing"],
                     "expected_failing": sorted(EXPECTED_FAILING[name]), "as_expected": caught})
    out.write_text(json.dumps({"record_type": "ISSUE_47_B03_GATE_FAULT_INJECTIONS",
                               "module": str(MODULE.relative_to(REPO)), "results": rows},
                              indent=1, sort_keys=True) + "\n")
    if not all(row["as_expected"] for row in rows):
        raise SystemExit("AN_INJECTION_WAS_NOT_CAUGHT_AS_EXPECTED")


if __name__ == "__main__":
    main()
