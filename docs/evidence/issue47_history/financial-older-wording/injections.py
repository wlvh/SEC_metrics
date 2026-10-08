"""Fault injections for the financial witnesses' older-wording successors.

The checkout is not edited: each injection compiles one module's source with one
edit (it must apply exactly once and compile) and installs it under its own
name in a fresh interpreter, with a bytecode cache the run owns, before the test
modules import it. A control with no edit must pass every case; each injection
must fail exactly the cases written for it. The constructed-document cases run
in under a second; the report cases read the bank's FY2021 annual report from
the export and take a few minutes, so only the injections they are written for
run them.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/financial-older-wording/injections.py <output.json>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WORDING = "scripts/vnext/historical_financial_wording.py"
DEI = "scripts/vnext/historical_dei.py"
FAST = "tests.vnext.test_historical_financial_wording"
FILINGS = "tests.vnext.test_historical_financial_wording_filings"

# name: (module, old, new, test module, expected failing cases)
INJECTIONS = {
    "CONTROL_FAST": (None, None, None, FAST, set()),
    "CONTROL_FILINGS": (None, None, None, FILINGS, set()),
    "ALWAYS_TAKE_THE_OLDER_ANSWER": (
        WORDING, "    if _resolved(metric_id, frozen):\n        return frozen\n", "", FAST,
        {"test_a_resolved_frozen_answer_is_returned_as_it_is"}),
    "TAKE_AN_UNRESOLVED_OLDER_ANSWER": (
        WORDING, "    if not _resolved(metric_id, older):\n        return frozen\n", "", FAST,
        {"test_where_neither_resolves_the_frozen_refusal_stands"}),
    "TAKE_IT_WITHOUT_SAYING_SO": (
        WORDING, '    return {**older, "historical_older_wording": {',
        '    return older\n    return {**older, "historical_older_wording": {', FAST,
        {"test_the_older_answer_is_taken_only_where_it_resolves_and_says_so"}),
    "ANY_REMAINDER_SEGMENT": (
        WORDING, "In addition, there is a Corporate segment\\\\b",
        "In addition, there is a \\\\w+ segment\\\\b",
        FAST, {"test_a_list_that_does_not_put_the_rest_in_corporate_binds_nothing"}),
    "ANY_GLOSSARY_SEPARATOR": (
        WORDING, "r'AUM:? [", "r'AUM\\\\W* [", FAST, {"test_nothing_but_one_colon_is_accepted"}),
    "ANY_BLOCK_BEFORE_THE_NOTES": (
        WORDING, 'if notes or general or not _text(block["visible_text"]).endswith("."):',
        "if notes or general:", FAST,
        {"test_a_heading_or_a_second_unmarked_block_still_ends_the_notes"}),
    "MANY_GENERAL_NOTES": (
        WORDING, 'if notes or general or not _text(block["visible_text"]).endswith("."):',
        'if notes or not _text(block["visible_text"]).endswith("."):', FAST,
        {"test_a_heading_or_a_second_unmarked_block_still_ends_the_notes"}),
    "ANY_NAME_FOR_THE_MEASURE": (
        WORDING, '"|" + re.escape(name) for name in', '"|[A-Za-z]+" for name in', FAST,
        {"test_a_name_the_label_does_not_define_proves_nothing"}),
    "A_SUBSTITUTION_MAY_OCCUR_TWICE": (
        WORDING, "_need(body.count(old) == 1,", "_need(body.count(old) >= 1,", FAST,
        {"test_a_substitution_that_does_not_occur_exactly_once_is_refused"}),
    "NO_SOURCE_IDENTITY_CHECK": (
        WORDING, "_need(_compiled(function, source) == function.__code__,", "_need(True,", FAST,
        {"test_a_source_that_changed_after_it_was_loaded_is_refused"}),
    "AN_IMPORT_ONLY_OVERRIDE_IS_ACCEPTED": (
        DEI, "    if imported_only:\n", "    if False:\n", "tests.vnext.test_historical_dei",
        {"test_a_name_the_code_only_imports_is_refused"}),
    "ANOTHER_EXCLUDED_BUSINESS_IN_THE_LABEL": (
        WORDING, 'excluding (?:cib )?markets"', 'excluding (?:cib )?\\\\w+"', FILINGS,
        {"test_a04_does_not_set_aside_a_measure_excluding_another_business"}),
    "ANOTHER_EXCLUDED_BUSINESS_IN_THE_INTRODUCTION": (
        WORDING, 'excluding (?:CIB )?Markets, as shown below"',
        'excluding (?:CIB )?\\\\w+, as shown below"', FILINGS,
        {"test_a04_does_not_read_an_introduction_excluding_another_business"}),
    "A_COUNTERFACTUAL_HEADER_IN_ANY_DIRECTION": (
        WORDING, '"amount by which reported average var would have been higher")',
        '"amount by which reported average var would have been higher") or _clean(c["text"])'
        '.startswith("amount by which reported average var would have been")', FILINGS,
        {"test_a12_does_not_set_aside_a_header_that_states_no_direction"}),
    "CONTENTS_WITHOUT_THEIR_NAME": (
        WORDING, 'and re.search(r"\\\\bTable of Contents$", contents["visible_text"], re.I)):',
        "and True):", FILINGS,
        {"test_a09_does_not_set_aside_a_table_no_longer_named_contents"}),
    "NO_MEASURE_ABBREVIATION_FOR_A03": (
        WORDING, "                successor(_frozen_duration.inspect_financial_duration, MEASURE_ABBREVIATION),",
        "                _frozen_duration.inspect_financial_duration,", FILINGS,
        {"test_a03_reaches_the_lettered_note_past_the_general_note"}),
}
TEST_CASES = {FAST: None, FILINGS: None, "tests.vnext.test_historical_dei":
              "AnOverrideViewReplacesOnlyWhatItNames"}
RUNNER = r'''
import importlib, json, sys, types, unittest
sys.path.insert(0, %(scripts)r); sys.path.insert(0, %(repo)r)
import vnext
module_path, old, new = %(module)r, %(old)r, %(new)r
if module_path is not None:
    source = open(module_path, encoding="utf-8").read()
    if source.count(old) != 1:
        raise SystemExit("THE_EDIT_DOES_NOT_APPLY_EXACTLY_ONCE")
    source = source.replace(old, new)
    name = "vnext." + module_path.rsplit("/", 1)[1][:-3]
    module = types.ModuleType(name)
    module.__file__ = module_path; module.__package__ = "vnext"
    sys.modules[name] = module
    code = compile(source, module_path, "exec")
    try:
        exec(code, module.__dict__)
    except Exception as error:
        print(json.dumps({"ran": 0, "failing": [], "import_error": type(error).__name__ + ": " + str(error)[:300]}))
        raise SystemExit(0)
    setattr(vnext, name.rsplit(".", 1)[1], module)
cases = importlib.import_module(%(tests)r)
loader = unittest.defaultTestLoader
suite = (loader.loadTestsFromTestCase(getattr(cases, %(case)r)) if %(case)r
         else loader.loadTestsFromModule(cases))
result = unittest.TestResult(); suite.run(result)
failing = sorted(test.id().rsplit(".", 1)[1] for test, _ in result.failures + result.errors)
print(json.dumps({"ran": result.testsRun, "failing": failing}))
'''


def main():
    out = Path(sys.argv[1])
    rows = []
    for name, (module, old, new, tests, expected) in INJECTIONS.items():
        with tempfile.TemporaryDirectory() as cache:
            code = RUNNER % {"scripts": str(REPO / "scripts"), "repo": str(REPO),
                             "module": None if module is None else str(REPO / module),
                             "old": old, "new": new, "tests": tests, "case": TEST_CASES[tests]}
            done = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), capture_output=True,
                                  text=True, timeout=3600,
                                  env={"PATH": "/usr/bin:/bin", "PYTHONPYCACHEPREFIX": cache,
                                       "HOME": str(Path.home())})
        if done.returncode != 0:
            raise SystemExit(name + ":RUNNER_FAILED:" + done.stderr[-800:])
        measured = json.loads(done.stdout.strip().splitlines()[-1])
        caught = (measured["ran"] > 0 and set(measured["failing"]) == expected) if expected or module is None \
            else False
        rows.append({"injection": name, "module": module, "tests": tests, "ran": measured["ran"],
                     "failing": measured["failing"], "expected_failing": sorted(expected),
                     "import_error": measured.get("import_error"), "as_expected": caught})
        print(json.dumps(rows[-1]), flush=True)
    out.write_text(json.dumps({"record_type": "ISSUE_47_FINANCIAL_OLDER_WORDING_FAULT_INJECTIONS",
                               "results": rows}, indent=1, sort_keys=True) + "\n")
    if not all(row["as_expected"] for row in rows):
        raise SystemExit("AN_INJECTION_WAS_NOT_CAUGHT_AS_EXPECTED")


if __name__ == "__main__":
    main()
