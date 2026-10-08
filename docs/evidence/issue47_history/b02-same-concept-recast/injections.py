"""Fault injections for the same-concept recast rule, on an in-memory copy of the route.

The checkout is not edited: each injection compiles the route module's source
with one edit (which must apply exactly once) and installs it as
``vnext.historical_results`` in a fresh interpreter, with a bytecode cache the
run owns, before the test module imports it. A control with no edit must pass;
each injection must fail in the test written for it.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/b02-same-concept-recast/injections.py <output.json>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MODULE = REPO / "scripts" / "vnext" / "historical_results.py"
INJECTIONS = {
    "CONTROL": None,
    # The rule before: one concept for both years asks nothing.
    "ONE_CONCEPT_ASKS_NOTHING": (
        '        current, prior = _claim_view(used["current"][0]), _claim_view(used["prior"][0])\n',
        '        current, prior = _claim_view(used["current"][0]), _claim_view(used["prior"][0])\n'
        '        if current["concept"] == prior["concept"]:\n            continue\n'),
    # A year the target filing does not report is treated as a recast.
    "AN_UNREPORTED_YEAR_IS_A_RECAST": (
        '        if current["concept"] == prior["concept"] and not reported:\n            continue\n',
        ''),
    # Every problem says recast, the concept pairs too.
    "EVERY_PROBLEM_IS_MARKED_A_RECAST": (
        '        if current["concept"] == prior["concept"]:\n            problem["same_concept_recast"] = True\n',
        '        problem["same_concept_recast"] = True\n'),
    # A same-concept pair at the reported value is recorded as a bridge.
    "A_SAME_CONCEPT_PAIR_IS_A_BRIDGE": (
        '            if current["concept"] != prior["concept"]:\n                bridged.append(pair)\n',
        '            bridged.append(pair)\n'),
}
EXPECTED_FAILING = {
    "CONTROL": set(),
    "ONE_CONCEPT_ASKS_NOTHING": {"test_one_concept_the_target_filing_recasts_is_withheld",
                                 "test_one_concept_reported_at_the_prior_value_or_not_at_all_asks_nothing"},
    "AN_UNREPORTED_YEAR_IS_A_RECAST": {
        "test_one_concept_reported_at_the_prior_value_or_not_at_all_asks_nothing"},
    "EVERY_PROBLEM_IS_MARKED_A_RECAST": {"test_a_concept_pair_problem_carries_no_recast_mark"},
    "A_SAME_CONCEPT_PAIR_IS_A_BRIDGE": {
        "test_one_concept_reported_at_the_prior_value_or_not_at_all_asks_nothing"},
}
RUNNER = r'''
import sys, types, unittest, json
sys.path.insert(0, %(scripts)r); sys.path.insert(0, %(repo)r)
import vnext
source = open(%(module)r).read()
edit = %(edit)r
if edit is not None:
    if source.count(edit[0]) != 1:
        raise SystemExit("THE_EDIT_DOES_NOT_APPLY_EXACTLY_ONCE")
    source = source.replace(edit[0], edit[1])
module = types.ModuleType("vnext.historical_results")
module.__file__ = %(module)r; module.__package__ = "vnext"
sys.modules["vnext.historical_results"] = module
exec(compile(source, %(module)r, "exec"), module.__dict__)
vnext.historical_results = module
from tests.vnext import test_historical_paired_measure as cases
suite = unittest.defaultTestLoader.loadTestsFromModule(cases)
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
                             "module": str(MODULE), "edit": edit}
            done = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), capture_output=True,
                                  text=True, timeout=1800,
                                  env={"PATH": "/usr/bin:/bin", "PYTHONPYCACHEPREFIX": cache,
                                       "HOME": str(Path.home())})
        if done.returncode != 0:
            raise SystemExit(name + ":RUNNER_FAILED:" + done.stderr[-600:])
        measured = json.loads(done.stdout.strip().splitlines()[-1])
        rows.append({"injection": name, "ran": measured["ran"], "failing": measured["failing"],
                     "expected_failing": sorted(EXPECTED_FAILING[name]),
                     "as_expected": set(measured["failing"]) == EXPECTED_FAILING[name]})
    out.write_text(json.dumps({"record_type": "ISSUE_47_B02_RECAST_FAULT_INJECTIONS",
                               "module": str(MODULE.relative_to(REPO)), "results": rows},
                              indent=1, sort_keys=True) + "\n")
    print(json.dumps([(r["injection"], r["failing"], r["as_expected"]) for r in rows], indent=0))
    if not all(row["as_expected"] for row in rows):
        raise SystemExit("AN_INJECTION_WAS_NOT_CAUGHT_AS_EXPECTED")


if __name__ == "__main__":
    main()
