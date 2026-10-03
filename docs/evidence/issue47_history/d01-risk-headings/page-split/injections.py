"""Undo each part of the page-split join and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../../c03-first-ecd-release/injections.py: each injection edits
a file in place (exactly one match, must compile), runs the module holding its
case with a fresh bytecode prefix, and restores the bytes. The control run must
pass first. It edits the tree it lives in, so nothing else may read that tree
while it runs. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parents[1] / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

ROUTE = "scripts/vnext/historical_text_emphasis.py"
READER = "tools/read_d01_headings.py"
ROUTE_CASES = "tests.vnext.test_historical_page_split_headings"
READER_CASES = "tests.vnext.test_d01_byte_reading"
harness.SOURCE, harness.NOTE = ROUTE, READER
harness.MODULES, harness.CASES = (ROUTE_CASES, READER_CASES), ROUTE_CASES
harness.INJECTIONS = {
    "A_CAPITALISED_NEXT_LINE_IS_JOINED_TOO": (
        ROUTE,
        "                and blocks[following][\"text\"][:1].islower()):\n",
        "                ):\n",
        "test_the_two_filings_that_have_one_are_unchanged_to_the_byte"),
    "NO_PAGE_IS_NEEDED_BETWEEN_THE_HALVES": (
        ROUTE,
        "                and index + 1 < following < end and _heading_only(blocks[following])\n",
        "                and index < following < end and _heading_only(blocks[following])\n",
        "test_without_a_page_between_them_nothing_is_joined"),
    "ANY_UNEMPHASISED_BLOCK_IS_PAGE_FURNITURE": (
        ROUTE,
        "    return (bool(_PAGE_NUMBER.fullmatch(text))\n",
        "    return (not block[\"leading_emphasis\"] or bool(_PAGE_NUMBER.fullmatch(text))\n",
        "test_body_text_between_them_is_not_page_furniture"),
    "AN_UNLINKED_CONTENTS_LINE_IS_PAGE_FURNITURE": (
        ROUTE,
        "            or (block[\"linked\"] and text.casefold() == _CONTENTS_LINK))\n",
        "            or text.casefold() == _CONTENTS_LINK)\n",
        "test_an_unlinked_contents_line_is_not_page_furniture"),
    "A_FIRST_HALF_THAT_ENDS_ITS_SENTENCE_IS_JOINED": (
        ROUTE,
        "        if (_heading_only(block) and not _SENTENCE_END.search(block[\"text\"])\n",
        "        if (_heading_only(block)\n",
        "test_a_first_half_that_ends_a_sentence_is_a_heading_of_its_own"),
    "THE_SECOND_HALF_STAYS_A_LINE_OF_ITS_OWN": (
        ROUTE,
        "            second[\"leading_emphasis\"] = None\n",
        "            pass\n",
        "test_fy2022_delivers_two_whole_headings_where_it_delivered_four_halves"),
    "A_PARTLY_EMPHASISED_HALF_IS_A_HEADING_HALF": (
        ROUTE,
        "    return prefix is not None and not block[\"linked\"] and prefix[\"text\"] == block[\"text\"]\n",
        "    return prefix is not None and not block[\"linked\"]\n",
        "test_a_half_that_is_not_emphasised_whole_is_not_a_heading_half"),
    "OUTSIDE_ITEM_1A_THE_WHOLE_DOCUMENT_IS_SCANNED": (
        ROUTE,
        "    if not section or section.get(\"status\") != \"LOCATED\" or len(section[\"candidates\"]) != 1:\n"
        "        return []\n"
        "    scope = section[\"candidates\"][0]\n"
        "    start, end = scope[\"start_block\"], scope[\"end_block_exclusive\"]\n",
        "    start, end = 0, len(blocks)\n",
        "test_outside_item_1a_nothing_is_joined"),
    "THE_READING_FLAGS_ONLY_A_LOWER_CASE_REST": (
        READER,
        "            if pending is not None and furniture_since:\n",
        "            if pending is not None and furniture_since and heading[:1].islower():\n",
        "test_a_label_at_the_foot_of_a_page_is_flagged_though_the_next_line_is_capitalised",
        READER_CASES),
    "AN_UNJUDGED_PAIR_IS_READ_AS_ONE_HEADING": (
        READER,
        "            if page_split_lines.get(text) == \"ONE_HEADING_ACROSS_THE_PAGE\":\n",
        "            if page_split_lines.get(text, \"ONE_HEADING_ACROSS_THE_PAGE\") == \"ONE_HEADING_ACROSS_THE_PAGE\":\n",
        "test_each_decision_gives_its_own_lines_and_no_decision_fails", READER_CASES),
    "A_DECISION_ABOUT_AN_UNFLAGGED_PAIR_PASSES": (
        READER,
        "        not_found += sorted(set(page_split_lines) - split_flagged)\n",
        "        pass\n",
        "test_a_decision_about_a_pair_the_filing_does_not_flag_fails", READER_CASES),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
