"""Fault injections for the C03 reader's first-report table read (tools/read_c03_across_proxies.py).

The checkout is not edited: each injection compiles the reader's source with one
edit (it must apply exactly once and compile), installs it as
tools.read_c03_across_proxies in a fresh interpreter with a bytecode cache the
run owns, and runs tests.vnext.test_c03_across_proxies_reading against it. A
control with no edit must pass every case; each injection must fail exactly the
cases written for it.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/reading-producers/c03_table_injections.py <output.json>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
READER = "tools/read_c03_across_proxies.py"
TESTS = "tests.vnext.test_c03_across_proxies_reading"
REDERIVE = "test_every_position_of_every_reading"

# name: (old, new, expected failing cases, what it breaks)
INJECTIONS = {
    "CONTROL": (None, None, set(), "nothing"),
    "ANY_PAY_TABLE": (
        "                       and any(_STOCK_AWARDS.match(cell) for cell in row)\n"
        "                       and any(_ALL_OTHER.match(cell) for cell in row)), None)",
        "                       ), None)",
        # JPMorgan's 2022 proxy also prints the committee's own view of the
        # year's award under name, year, salary and total.
        {"test_the_summary_compensation_table_and_not_another_pay_table", REDERIVE},
        "any pay table opening with name, year, salary and total is taken for the SCT"),
    "THE_SUM_IS_NOT_CHECKED": (
        "    if sum(row[\"amounts\"][:-1]) != row[\"amounts\"][-1]:\n",
        "    if False:\n",
        {"test_a_row_whose_components_do_not_add_up_is_not_read"},
        "a row whose components do not add up to its total"),
    "THE_FIRST_ROW_WINS": (
        "    if len(found) != 1:\n        return {\"refused\": \"THE_NAMED_PEO_HAS_\"",
        "    if not found:\n        return {\"refused\": \"THE_NAMED_PEO_HAS_\"",
        {"test_two_rows_for_the_person_and_year_are_not_chosen_between"},
        "two rows for the person and year: the first is taken"),
    "FOOTNOTE_MARKS_ARE_AMOUNTS": (
        "                if cell == \"$\" or re.fullmatch(r\"\\d{1,2}\", cell):\n",
        "                if cell == \"$\":\n",
        {"test_the_summary_compensation_table_and_not_another_pay_table", REDERIVE},
        "a footnote mark beside an amount read as an amount"),
    "ANY_PERSON": (
        "            if not row or row[0] != year or person is None or not person.startswith(name):\n",
        "            if not row or row[0] != year or person is None:\n",
        {"test_a_year_row_continues_the_person_above_and_no_one_else", REDERIVE},
        "every person's row for the year, not the PEO's"),
    "ONE_OF_TWO_PEOS_IS_PICKED": (
        "        if len(names) != 1:\n",
        "        if not names:\n",
        {"test_the_table_is_not_read_when_the_tags_name_two_peos"},
        "the tagged proxies name two PEOs for the year and one is picked"),
    "A_LATER_TABLE_IS_A_FIRST_REPORT": (
        "            before = [r for r in table if _filed_year(r[\"accession\"]) < earliest_year]\n",
        "            before = list(table)\n",
        {"test_a_table_filed_after_a_tagged_report_is_not_the_first_report"},
        "a table filed after a tagged report taken as the first report"),
}
RUNNER = r'''
import importlib, json, sys, types, unittest
sys.path.insert(0, %(scripts)r); sys.path.insert(0, %(tools)r); sys.path.insert(0, %(repo)r)
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
module = types.ModuleType("tools.read_c03_across_proxies")
module.__file__ = loaded; module.__package__ = "tools"
sys.modules["tools.read_c03_across_proxies"] = module
exec(compile(source, loaded, "exec"), module.__dict__)
tools.read_c03_across_proxies = module
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
            code = RUNNER % {"scripts": str(REPO / "scripts"), "tools": str(REPO / "tools"),
                             "repo": str(REPO), "path": str(REPO / READER), "old": old,
                             "new": new, "tests": TESTS}
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
    out.write_text(json.dumps({"record_type": "ISSUE_47_C03_FIRST_REPORT_TABLE_FAULT_INJECTIONS",
                               "reader": READER, "suite": TESTS, "results": rows},
                              indent=1, sort_keys=True) + "\n")
    if not all(row["as_expected"] for row in rows):
        raise SystemExit("AN_INJECTION_WAS_NOT_CAUGHT_AS_EXPECTED")


if __name__ == "__main__":
    main()
