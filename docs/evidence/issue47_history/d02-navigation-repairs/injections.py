"""Undo each part of the two D02 navigation repairs and require the case written for it to fail.

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
    "THE_SPLIT_HEADING_IS_NOT_SHOWN": (
        ROUTE,
        "    headings = {index for index, block in enumerate(blocks) if split_emphasis_note_heading(block)}\n",
        "    headings = set()\n",
        "test_note_16_ends_where_note_17_begins"),
    "A_BARE_NUMBER_IS_A_HEADING": (
        ROUTE,
        '                and _PATTERNS["explicit_note_prefix"].match(lead)\n',
        "",
        "test_a_block_in_the_same_shape_without_the_explicit_number_is_not_a_heading"),
    "THE_LEAD_NEED_NOT_BE_THE_NUMBER": (
        ROUTE,
        '                and _PATTERNS["note_identifier"].fullmatch(lead)\n',
        "",
        "test_a_block_in_the_same_shape_without_the_explicit_number_is_not_a_heading"),
    "A_SENTENCE_IS_A_HEADING": (
        ROUTE,
        '                and not text.endswith((".", ":", ";", ",")))\n',
        "                )\n",
        "test_a_block_in_the_same_shape_without_the_explicit_number_is_not_a_heading"),
    "A_LINK_IS_A_HEADING": (
        ROUTE,
        '    return bool(not block["linked"] and not block.get("emphasized") and len(block["text"]) <= 300\n',
        '    return bool(not block.get("emphasized") and len(block["text"]) <= 300\n',
        "test_a_block_in_the_same_shape_without_the_explicit_number_is_not_a_heading"),
    "THE_STATEMENTS_START_AT_THE_FIRST_TITLE": (
        ROUTE,
        "    for begin, (first, _) in enumerate(titles):\n",
        "    return titles[0][0] if titles else None\n    for begin, (first, _) in enumerate(titles):\n",
        "test_jpmorgan_s_range_starts_at_the_income_statement", REPAIRS),
    "TWO_KINDS_ARE_THE_STATEMENTS": (
        ROUTE,
        "_STATEMENTS_TOGETHER = 3\n",
        "_STATEMENTS_TOGETHER = 2\n",
        "test_two_kinds_are_not_the_statements", REPAIRS),
    "THE_RUN_HAS_NO_GAP_BOUND": (
        ROUTE,
        "            if index - last > _STATEMENT_GAP:\n                break\n",
        "",
        "test_jpmorgan_s_range_starts_at_the_income_statement", REPAIRS),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
