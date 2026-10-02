"""Undo each part of the page-split refusal and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../../c03-first-ecd-release/injections.py: each injection edits
a file in place (exactly one match, must compile), runs the module holding its
case with a fresh bytecode prefix, and restores the bytes. The control run must
pass first. It edits the tree it lives in, so run it from a clone or worktree
nothing else reads. Zero calls.
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
CASES = "tests.vnext.test_historical_page_split_headings"
harness.SOURCE, harness.NOTE = ROUTE, ROUTE
harness.MODULES, harness.CASES = (CASES,), CASES
harness.INJECTIONS = {
    "THE_REFUSAL_IS_NEVER_ASKED": (
        ROUTE,
        "    _need(not split_heading_requires_multispan(\n"
        "        blocks=blocks, section=document[\"sections\"].get(\"ITEM_1A\")),\n"
        "        \"D01_MULTISPAN_HEADING_UNSUPPORTED\")\n",
        "",
        "test_both_reports_are_refused_by_name"),
    "A_LONE_PAGE_NUMBER_IS_THE_LAYOUT": (
        ROUTE,
        "    for index in range(start, max(start, end - 3)):\n"
        "        block = blocks[index]\n"
        "        page, contents, continuation = blocks[index + 1:index + 4]\n"
        "        if (_heading_only(block) and not _SENTENCE_END.search(block[\"text\"])\n"
        "                and _PAGE_NUMBER.fullmatch(page[\"text\"].strip())\n"
        "                and contents[\"linked\"]\n"
        "                and contents[\"text\"].strip().casefold() == _CONTENTS_LINK\n"
        "                and _heading_only(continuation)\n",
        "    for index in range(start, max(start, end - 2)):\n"
        "        block = blocks[index]\n"
        "        page, contents, continuation = blocks[index + 1], None, blocks[index + 2]\n"
        "        if (_heading_only(block) and not _SENTENCE_END.search(block[\"text\"])\n"
        "                and _PAGE_NUMBER.fullmatch(page[\"text\"].strip())\n"
        "                and _heading_only(continuation)\n",
        "test_a_lone_page_number_between_two_headings_is_not_the_layout"),
    "AN_UNLINKED_CONTENTS_LINE_IS_THE_LAYOUT": (
        ROUTE,
        "                and contents[\"linked\"]\n",
        "",
        "test_an_unlinked_contents_line_is_not_the_layout"),
    "A_FIRST_HALF_THAT_ENDS_ITS_SENTENCE_IS_THE_LAYOUT": (
        ROUTE,
        "        if (_heading_only(block) and not _SENTENCE_END.search(block[\"text\"])\n",
        "        if (_heading_only(block)\n",
        "test_a_first_half_that_ends_a_sentence_is_a_heading_of_its_own"),
    "A_CAPITALISED_NEXT_HEADING_IS_THE_LAYOUT": (
        ROUTE,
        "                and continuation[\"text\"][:1].islower()):\n",
        "                ):\n",
        "test_a_second_block_that_begins_a_sentence_is_a_heading_of_its_own"),
    "A_PARTLY_EMPHASISED_HALF_IS_A_HEADING_HALF": (
        ROUTE,
        "    return prefix is not None and not block[\"linked\"] and prefix[\"text\"] == block[\"text\"]\n",
        "    return prefix is not None and not block[\"linked\"]\n",
        "test_a_half_that_is_not_emphasised_whole_is_not_a_heading_half"),
    "OUTSIDE_ITEM_1A_THE_WHOLE_DOCUMENT_IS_SCANNED": (
        ROUTE,
        "    if not section or section.get(\"status\") != \"LOCATED\" or len(section[\"candidates\"]) != 1:\n"
        "        return False\n"
        "    scope = section[\"candidates\"][0]\n"
        "    start, end = scope[\"start_block\"], scope[\"end_block_exclusive\"]\n",
        "    start, end = 0, len(blocks)\n",
        "test_outside_item_1a_it_is_not_the_layout"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
