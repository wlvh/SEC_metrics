"""Undo each part of the image-name cover and the pay-table widenings; the case written for it must fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../c03-first-ecd-release/injections.py: each injection edits
one reader in place (exactly one match, must compile), runs the test module
holding its case with a fresh bytecode prefix, and restores the bytes. The
control run - both modules - must pass first. It edits the tree it lives in,
so run it from a clone or worktree nothing else reads. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parent / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

COVER = "scripts/vnext/historical_proxy_identity.py"
TABLE = "scripts/vnext/historical_proxy_compensation.py"
COVER_CASES = "tests.vnext.test_historical_proxy_identity"
TABLE_CASES = "tests.vnext.test_historical_proxy_compensation"
harness.SOURCE, harness.NOTE = COVER, TABLE
harness.MODULES, harness.CASES = (COVER_CASES, TABLE_CASES), TABLE_CASES
harness.INJECTIONS = {
    "THE_WINGDINGS_CHECK_IS_NOT_A_CHECK": (
        COVER, 'CHECKED = frozenset({"☒", "☑", "x", "þ"})', 'CHECKED = frozenset({"☒", "☑", "x"})',
        "test_the_cover_gives_the_first_block_after_it_and_the_definitive_box", COVER_CASES),
    "AN_IMAGE_SLOT_IS_NOT_READ": (
        COVER, "    if any(re.search(pattern, name, re.I) for pattern in OPTIONS.values()):\n        # No text",
        "    if False:\n        # No text",
        "test_the_cover_gives_the_first_block_after_it_and_the_definitive_box", COVER_CASES),
    "A_LINK_AFTER_THE_COVER_IS_TAKEN": (
        COVER, '        if block["linked"] or _FEE_LINE.match(clean):', "        if _FEE_LINE.match(clean):",
        "test_a_link_after_the_cover_is_not_the_name", COVER_CASES),
    "A_FEE_LINE_IS_TAKEN": (
        COVER, '        if block["linked"] or _FEE_LINE.match(clean):', '        if block["linked"]:',
        "test_the_cover_gives_the_first_block_after_it_and_the_definitive_box", COVER_CASES),
    "AN_EMPTY_SLOT_IS_READ_LIKE_AN_IMAGE": (
        COVER, '    _need(re.search(r"<img\\b", slot, re.I) is not None\n          and not re.sub(',
        "    _need(not re.sub(",
        "test_an_empty_slot_is_refused", COVER_CASES),
    "THE_FILER_CAPTION_IS_NOT_REQUIRED": (
        COVER, "    _need(caption + 1 < len(parsed) and parsed[caption + 1][1].casefold() == _FILER_CAPTION,",
        "    _need(True,",
        "test_without_the_filer_caption_the_layout_is_refused", COVER_CASES),
    "EVERY_COVER_RECORDS_A_BASIS": (
        COVER, "    if basis is not None:\n        cover[\"name_basis\"] = basis",
        "    cover[\"name_basis\"] = basis",
        "test_the_eight_covers_that_print_their_name_keep_their_records", COVER_CASES),
    "THE_NUMBERED_TITLE_IS_NOT_A_TITLE": (
        TABLE, '_TITLE = re.compile(r"^(?:(?:[IVX]+|\\d+)\\.\\s*)?(?:(?P<before>',
        '_TITLE = re.compile(r"^(?:(?P<before>',
        "test_the_chief_executive_s_total_is_read"),
    "THE_ABBREVIATION_IS_NOT_PART_OF_THE_TITLE": (
        TABLE, '(?P<after>\\d{4}))?(?:\\s*\\(SCT\\))?$", re.I)', '(?P<after>\\d{4}))?$", re.I)',
        "test_a_numbered_title_and_its_abbreviation_are_the_title"),
    "A_UNIT_S_CHIEF_EXECUTIVE_IS_THE_REGISTRANT_S": (
        TABLE, " or _UNIT_INITIALS.match(text[match.end():]):", ":",
        "test_the_chief_executive_s_total_is_read"),
    "AND_IS_A_UNIT_S_INITIALS": (
        TABLE, '_UNIT_INITIALS = re.compile(r"\\s+(?!(?:AND|OR)\\b)[A-Z]{2,5}\\b")',
        '_UNIT_INITIALS = re.compile(r"\\s+[A-Z]{2,5}\\b")',
        "test_a_unit_s_chief_executive_is_not_the_registrant_s"),
    "MARKS_ARE_TRIED_ON_A_ROW_THAT_SUMS": (
        TABLE, "    if amounts is None or len(amounts) < 3 or _sums(amounts):\n        return amounts, []",
        "    if amounts is None or len(amounts) < 3:\n        return amounts, []",
        "test_mark_cells_are_read_only_when_the_row_fails_its_sum"),
    "MARKS_ARE_KEPT_WITHOUT_THE_SUM": (
        TABLE, "    if marks and _sums(alternative):", "    if marks:",
        "test_mark_cells_are_read_only_when_the_row_fails_its_sum"),
    "THE_MARKS_ARE_NOT_RECORDED": (
        TABLE, '            if marks:\n                candidate["cells_read_as_footnote_marks"] = marks\n', "",
        "test_the_chief_executive_s_total_is_read"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
