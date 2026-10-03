"""Undo each rule of the older-year C03 reading and require the case written for it to fail.

Usage: python3 reading_injections.py <out.json> [NAME ...]

Same harness as injections.py beside it: each injection edits the reader in
place (exactly one match, must compile), runs the module holding its case with
a fresh bytecode prefix, and restores the bytes. The control run must pass
first. It edits the tree it lives in, so nothing else may read that tree while
it runs. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ecd_injections", HERE / "injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

SOURCE = "tools/read_c03_across_proxies.py"
CASES = "tests.vnext.test_c03_across_proxies_reading"
harness.SOURCE, harness.NOTE, harness.MODULES = SOURCE, SOURCE, (CASES,)
harness.CASES = CASES
harness.INJECTIONS = {
    "PROXIES_THAT_DISAGREE_ARE_READ": (
        SOURCE,
        "           and any(not r[\"named_by_the_result\"] for r in reports)\n",
        "           and any(not r[\"named_by_the_result\"] for r in reports) or len(amounts) > 1\n",
        "test_a_year_two_proxies_report_differently_is_not_chosen_between"),
    "THE_RESULT_S_OWN_FILING_IS_ENOUGH": (
        SOURCE,
        "           and any(not r[\"named_by_the_result\"] for r in reports)\n",
        "\n",
        "test_a_value_only_the_result_s_own_filing_reports_is_not_accepted"),
    "SEVERAL_TOTALS_IN_ONE_PROXY_ARE_READ": (
        SOURCE,
        "    why = (None if reports and all(len(r[\"values\"]) == 1 for r in reports) and len(amounts) == 1\n",
        "    why = (None if reports and len(amounts) <= 2\n",
        "test_a_year_with_two_chief_executives_is_not_chosen_between"),
}

if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
