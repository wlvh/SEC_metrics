"""Fault injections for the bank-measures reader (tools/read_bank_measures.py).

The checkout is not edited: each injection compiles the reader's source with one
edit (it must apply exactly once and compile), installs it as
tools.read_bank_measures in a fresh interpreter with a bytecode cache the run
owns, and runs tests.vnext.test_bank_measures_reading against it. A control with
no edit must pass every case; each injection must fail exactly the cases
written for it.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/reading-producers/bank_injections.py <output.json>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
READER = "tools/read_bank_measures.py"
TESTS = "tests.vnext.test_bank_measures_reading"
REDERIVE = "test_every_position_of_every_reading_re_derives"

# name: (old, new, expected failing cases, what it breaks)
INJECTIONS = {
    "CONTROL": (None, None, set(), "nothing"),
    "FIRST_READ_WINS": (
        "values = sorted({(Decimal(item[\"value\"]), tuple(item[\"window\"])) for item in found})",
        "values = sorted({(Decimal(item[\"value\"]), tuple(item[\"window\"])) for item in found})[:1]",
        {"test_tables_that_disagree_are_not_read"},
        "tables that state the measure differently: the first is taken"),
    "ANY_YEAR_COLUMN": (
        "return years.index(year) if year in years else None, len(years)",
        "return 0, len(years)",
        {"test_a_header_without_the_target_year_is_not_read"},
        "the first column of years is read whether or not it is the target year"),
    "NO_WINDOW_CHECK": (
        "        if re.search(r\"\\byear ended \" + _month_day(end) + r\"\\b\", text, re.I) is None:\n"
        "            return None\n",
        "",
        {"test_a_header_without_the_window_is_not_read"},
        "a figure whose header does not state the year ended on the period end"),
    "ANY_SCALE": (
        "return _SCALES[found.pop()] if len(found) == 1 else None",
        "return _SCALES[sorted(found)[0]] if found else None",
        # The bank's international-metrics table states billions with a revenue
        # block in millions; its assets-under-management row is not read, and
        # picking a scale reads it.
        {"test_two_scales_in_a_header_are_not_read", REDERIVE},
        "a header stating two scales: one is picked"),
    "NO_SPLIT_REQUIRED": (
        "            if column is None or not splits or window is None:\n"
        "                continue\n"
        "            split = [cell for cell in splits[-1] if cell in (\"Avg.\", \"Min\", \"Max\")]\n"
        "            if len(split) != 3 * count or split[:3] != [\"Avg.\", \"Min\", \"Max\"]:\n"
        "                continue\n"
        "            figures = _numbers(row)\n"
        "            scale = _scale(rows, index)\n"
        "            if len(figures) != len(split) or scale is None:\n"
        "                continue\n"
        "            reads.append({\"table_ordinal\": ordinal, \"row\": row, \"figure\": figures[3 * column],\n"
        "                          \"window\": window, \"value\": str(_figure(figures[3 * column]) * scale)})\n",
        "            if column is None or window is None:\n"
        "                continue\n"
        "            figures = _numbers(row)\n"
        "            scale = _scale(rows, index)\n"
        "            stride = 3 if splits else 1\n"
        "            if scale is None:\n"
        "                continue\n"
        "            reads.append({\"table_ordinal\": ordinal, \"row\": row, \"figure\": figures[stride * column],\n"
        "                          \"window\": window, \"value\": str(_figure(figures[stride * column]) * scale)})\n",
        {"test_average_var_needs_the_avg_min_max_split",
         "test_the_counterfactual_var_total_is_not_the_average", REDERIVE},
        "a Total VaR row in a table not split into Avg., Min and Max (the counterfactual adjustment)"),
    "NO_REGISTRANT_GROUP": (
        "if not groups or _name_words(groups[-1][0]) != _name_words(name) or not dates:",
        "if not groups or not dates:",
        {"test_a_subsidiarys_lcr_is_not_the_registrants", REDERIVE},
        "an LCR row under another entity's group (the bank subsidiary)"),
    "ONE_SOURCE_SUFFICES": (
        "if sources != {\"QUARTER_AVERAGE_TABLE\", \"SELECTED_FINANCIAL_DATA\"}:",
        "if not sources:",
        # The subsidiary case also carries the selected data's firm LCR, so it
        # is refused only while both sources are required.
        {"test_one_source_alone_is_not_read", "test_a_subsidiarys_lcr_is_not_the_registrants"},
        "an LCR stated by one of the two sources only"),
    "NOT_ONLY_FIRMWIDE": (
        "\"A09\": \"firmwide nonaccrual loans to total loans outstanding\",",
        "\"A09\": \"nonaccrual loans to total loans outstanding\",",
        {"test_a_segment_ratio_is_not_the_firmwide_ratio", REDERIVE},
        "a segment's nonaccrual ratio as the firm's"),
    "ANY_YIELD_BY_PREFIX": (
        "if not row or _label(row[0]) != _LABELS[metric]:",
        "if not row or not _label(row[0]).startswith(_LABELS[metric][:44]):",
        {"test_the_yield_excluding_a_business_is_not_the_managed_basis", REDERIVE},
        "the net yield excluding a business as the managed-basis yield"),
    "ANY_FIRST_COLUMN": (
        "if len(row) > 1 and row[1].casefold().startswith(\"revenue\")]",
        "if len(row) > 1]",
        {"test_international_revenue_is_read_only_under_a_revenue_column"},
        "an international total under a first figure column that is not revenue"),
    "IMPORT_A_FINANCIAL_INSPECTOR": (
        "    from acceptance_readings import accession_of_document\n",
        "    from acceptance_readings import accession_of_document\n"
        "    from vnext import financial_relationships  # noqa: F401\n",
        {"test_no_import_names_a_financial_module"},
        "the reader importing a financial inspector"),
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
module = types.ModuleType("tools.read_bank_measures")
module.__file__ = loaded; module.__package__ = "tools"
sys.modules["tools.read_bank_measures"] = module
exec(compile(source, loaded, "exec"), module.__dict__)
tools.read_bank_measures = module
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
    out.write_text(json.dumps({"record_type": "ISSUE_47_BANK_MEASURES_READER_FAULT_INJECTIONS",
                               "reader": READER, "suite": TESTS, "results": rows},
                              indent=1, sort_keys=True) + "\n")
    if not all(row["as_expected"] for row in rows):
        raise SystemExit("AN_INJECTION_WAS_NOT_CAUGHT_AS_EXPECTED")


if __name__ == "__main__":
    main()
