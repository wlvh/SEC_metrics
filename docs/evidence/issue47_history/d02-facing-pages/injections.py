"""Undo each part of the facing-page page-number rule and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../c03-first-ecd-release/injections.py: each injection edits
the route in place (exactly one match, must compile), runs the modules holding
the cases with a fresh bytecode prefix, and restores the bytes. The control
run must pass first. It edits the tree it lives in, so run it from a clone or
worktree nothing else reads. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parent / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

ROUTE = "scripts/vnext/historical_text_results.py"
NAVIGATION = "tests.vnext.test_historical_note_navigation"
REPAIRS = "tests.vnext.test_historical_d02_route_repairs"
harness.SOURCE, harness.NOTE = ROUTE, ROUTE
harness.MODULES, harness.CASES = (NAVIGATION, REPAIRS), NAVIGATION
harness.INJECTIONS = {
    "FACING_PAGES_ARE_NOT_READ": (
        ROUTE, "_FACING_PAGES = True\n", "_FACING_PAGES = False\n",
        "test_only_the_footers_in_note_30_leave_and_each_was_judged_not_a_disclosure", REPAIRS),
    "A_FOOTER_NEED_NOT_HAVE_WORDS": (
        ROUTE, '                    _FACING_PAGES and re.search(r"[a-z]", neighbour)\n',
        "                    _FACING_PAGES\n",
        "test_a_footer_without_words_is_not_a_running_footer"),
    "A_SHORT_RUN_IS_ENOUGH": (
        ROUTE, "_FACING_PAGE_RUN = 5\n", "_FACING_PAGE_RUN = 2\n",
        "test_a_short_run_is_not_a_sequence_of_pages"),
    "THE_RUN_IS_NOT_ASKED": (
        ROUTE, "    return high - low + 1 >= _FACING_PAGE_RUN\n", "    return True\n",
        "test_a_short_run_is_not_a_sequence_of_pages"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
