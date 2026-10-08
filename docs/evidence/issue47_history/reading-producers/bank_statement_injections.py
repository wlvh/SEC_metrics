"""Fault injections for the bank statement-facts reader (tools/read_bank_statement_facts.py).

The checkout is not edited: each injection compiles the reader's source with one
edit (it must apply exactly once and compile), installs it as
tools.read_bank_statement_facts in a fresh interpreter with a bytecode cache the
run owns, and runs tests.vnext.test_bank_statement_facts_reading against it. A
control with no edit must pass every case; each injection must fail exactly the
cases written for it.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/reading-producers/bank_statement_injections.py <output.json>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
READER = "tools/read_bank_statement_facts.py"
TESTS = "tests.vnext.test_bank_statement_facts_reading"
REDERIVE = "test_every_position_re_derives_from_the_two_reports_it_names"

# name: (old, new, expected failing cases, what it breaks)
INJECTIONS = {
    "CONTROL": (None, None, set(), "nothing"),
    "NO_RESTATEMENT_CHECK": (
        "            if comparative is not None and comparative != value:\n",
        "            if False:\n",
        # The FY2021 report restates total assets at the end of 2020, so the
        # committed reading of that position changes too.
        {"test_a_prior_year_the_target_restates_is_not_read", REDERIVE},
        "a prior year the target report restates is read from the prior filing anyway"),
    "PRIOR_FROM_THE_TARGET": (
        "        source = {\"current\": target, \"prior\": prior}[component[\"accession_role\"]]\n",
        "        source = target\n",
        # Reading the prior year from the target also compares the target with
        # itself, so the restatement check never fires: the constructed
        # restatement and the FY2021 report's restated 2020 total assets are
        # both read.
        {"test_a_prior_component_is_read_from_the_prior_filing",
         "test_a_prior_year_the_target_restates_is_not_read", REDERIVE},
        "a component the catalog takes from the prior filing is read from the target"),
    "SUBSET_DIMENSIONS": (
        "        entries = facts.get(key)\n",
        "        entries = [entry for found, values in facts.items() if found[:4] == key[:4]\n"
        "                   and set(key[4]) <= set(found[4]) for entry in values]\n",
        {"test_capital_ratios_need_exactly_the_required_dimensions", REDERIVE},
        "a fact carrying more dimensions than the catalog requires is used"),
    "US_GAAP_ONLY": (
        "        if \":\" not in name or name.split(\":\")[-1] not in concepts:\n",
        "        if not name.startswith(\"us-gaap:\") or name.split(\":\")[-1] not in concepts:\n",
        {"test_two_namespaces_that_disagree_give_no_value", REDERIVE},
        "a fact the filer tags under its own namespace with the approved name is not read"),
    "LAST_CONCEPT_FIRST": (
        "    for concept in component[\"approved_concepts\"]:\n",
        "    for concept in reversed(component[\"approved_concepts\"]):\n",
        {"test_the_first_approved_concept_wins", REDERIVE},
        "the approved concepts are tried in another order"),
    "AVERAGE_WITHOUT_HALVING": (
        "            return +(values[0] / ((values[1] + values[2]) / Decimal(2)))\n",
        "            return +(values[0] / (values[1] + values[2]))\n",
        {"test_the_average_denominator_is_the_mean_of_the_two_year_ends", REDERIVE},
        "the average denominator is the sum of the two year ends"),
    "IMPORT_A_ROUTE_MODULE": (
        "    from acceptance_readings import accession_of_document\n",
        "    from acceptance_readings import accession_of_document\n"
        "    from vnext import deterministic_router  # noqa: F401\n",
        {"test_no_import_names_a_route_module"},
        "the reader importing the route's structured-fact module"),
}
RUNNER = r'''
import importlib, json, sys, types, unittest
sys.path.insert(0, %(scripts)r); sys.path.insert(0, %(repo)r)
import tools
import linecache
path, old, new = %(path)r, %(old)r, %(new)r
source = open(path, encoding="utf-8").read()
if old is not None:
    if source.count(old) != 1:
        raise SystemExit("THE_EDIT_DOES_NOT_APPLY_EXACTLY_ONCE")
    source = source.replace(old, new)
# The module's source lives under a name beside the file that is not on disk,
# so inspect.getsource returns the edited source, not the checkout's.
loaded = path[:-len(".py")] + "_under_injection.py"
linecache.cache[loaded] = (len(source), None, source.splitlines(True), loaded)
module = types.ModuleType("tools.read_bank_statement_facts")
module.__file__ = loaded; module.__package__ = "tools"
sys.modules["tools.read_bank_statement_facts"] = module
exec(compile(source, loaded, "exec"), module.__dict__)
tools.read_bank_statement_facts = module
cases = importlib.import_module(%(tests)r)
result = unittest.TestResult()
unittest.defaultTestLoader.loadTestsFromModule(cases).run(result)
def name(test):
    case = getattr(test, "test_case", test)  # a failed subTest names its case here
    return getattr(case, "_testMethodName", str(case))
failing = sorted({name(test) for test, _ in result.failures + result.errors})
print(json.dumps({"ran": result.testsRun, "failing": failing}))
'''


def main():
    out = Path(sys.argv[1])
    before = (REPO / READER).read_bytes()
    rows = []
    for name, (old, new, expected, what) in INJECTIONS.items():
        with tempfile.TemporaryDirectory() as cache:
            code = RUNNER % {"scripts": str(REPO / "scripts"), "repo": str(REPO),
                             "path": str(REPO / READER), "old": old, "new": new, "tests": TESTS}
            done = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), capture_output=True,
                                  text=True, timeout=1800,
                                  env={"PATH": "/usr/bin:/bin", "PYTHONPYCACHEPREFIX": cache,
                                       "HOME": str(Path.home())})
        if done.returncode != 0:
            raise SystemExit(name + ":RUNNER_FAILED:" + done.stderr[-800:])
        measured = json.loads(done.stdout.strip().splitlines()[-1])
        as_expected = measured["ran"] > 0 and set(measured["failing"]) == expected
        rows.append({"injection": name, "what": what, "ran": measured["ran"],
                     "failing": measured["failing"], "expected_failing": sorted(expected),
                     "as_expected": as_expected})
        print(json.dumps(rows[-1]), flush=True)
    if (REPO / READER).read_bytes() != before:
        raise SystemExit("THE_READER_CHANGED_ON_DISK")
    out.write_text(json.dumps({"record_type": "ISSUE_47_BANK_STATEMENT_READER_FAULT_INJECTIONS",
                               "reader": READER, "suite": TESTS, "results": rows},
                              indent=1, sort_keys=True) + "\n")
    if not all(row["as_expected"] for row in rows):
        raise SystemExit("AN_INJECTION_WAS_NOT_CAUGHT_AS_EXPECTED")


if __name__ == "__main__":
    main()
