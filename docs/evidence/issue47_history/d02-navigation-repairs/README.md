# D02: two navigation repairs the held-out readings found [shared-with-#28]

Found by the nine positions read after the Item 8 category-mention rule was frozen (`d02-older-years/judgements/`, held-out round). These positions are design material for these two repairs: the readings named the defects, and the repairs were written after them.

## 1. The statements printed after a pointer Item 8 start at the statements

JPMorgan's Item 8 is a pointer page, like Macy's FY2021. `appended_statements_range` started the range for the statements printed after the items at the first block that begins with a statement's name. In JPMorgan's reports that block is an MD&A heading, "CONSOLIDATED BALANCE SHEETS AND CASH FLOWS ANALYSIS", about 3,500 blocks before "Consolidated statements of income". The MD&A then came under the keyword: critical accounting estimates, forward-looking statements and country exposure. The readings judged all 22 such admissions that the category-mention rule keeps (FY2021-FY2025) not disclosures.

`statements_start` now starts the range where titles of at least three kinds of primary statement stand together: balance sheet, income, comprehensive income, cash flows or equity, each title within 300 blocks of the one before. Macy's FY2021 statements open such a run, so its range does not move.

## 2. A note heading whose separator is in body weight

Pfizer's FY2020 and FY2021 reports print "Note 17" in bold, ". " in body weight and the title in bold. The frozen scan takes a heading only when the whole block is emphasized, so Note 17 was never a heading and Note 16 ran on to the end of Item 8. Item 3 incorporates sub-note 16A. Within that long range, 16A's "A. Legal Proceedings" met Note 17's own "A. Segment Information", so the sub-note was never located. Its legal proceedings were then read only where the keyword admitted a paragraph. The FY2021 reading judged 49 skipped blocks legal proceedings, and found one case label taken without its class action.

`split_emphasis_note_heading` shows such a block to the frozen scan as emphasized when three things hold:

- its leading emphasis is exactly an explicit note number (the frozen `note_identifier` with the frozen `explicit_note_prefix`);
- its whole text is a frozen note heading;
- it does not end like a sentence.

A census over every saved annual report found two such blocks, both these headings. The same shape with a bare number is a table cell or a page footer (Bank of America's "1 Bank of America", JPMorgan's "2 — NM"), which is why the explicit prefix is required. Excerpt records carry no emphasis, so this change never reaches an excerpt's text.

## Measured (`effect.py` → `effect.json`, zero calls)

All 64 saved annual reports that build were run four times: with neither repair, with each repair alone, and with both. One more report, outside the frame, does not build (`TEXT_DOCUMENT_PERIOD_LEXICAL_UNSUPPORTED`). Eight reports move, each under exactly one repair:

| Report | Repair | D02 | D03 |
|---|---|---|---|
| JPMorgan FY2020-FY2025 (six) | statements start | loses 4 or 5 MD&A blocks each (FY2021-FY2025: the 22 the readings judged not disclosures), gains none | unchanged |
| Pfizer FY2021 | split heading | gains 73: the 49 blocks the reading judged wrongly skipped, and 24 it judged covered elsewhere (case labels and lead-ins of Note 16A); none it judged correctly skipped; loses none | unchanged |
| Pfizer FY2020 (outside the frame) | split heading | gains 82, loses none | unchanged |

Every other report keeps its proposal. Tests: `tests/vnext/test_historical_note_navigation.py` (`SplitEmphasisNoteHeadingTest`) and `tests/vnext/test_historical_d02_route_repairs.py` (`TheStatementsBeginWhereTheyArePrintedTogetherTest`, `StatementsStartTest`). Injections: `injections.json`.

## What remains for these positions

The six positions are registered as coordinate-level defects in `known_result_defects.json` (`register_defects.py` with `d02-older-years/causes.json`). The defects that remain for JPMorgan are:

- 18 keyword admissions the category-mention rule keeps (Visa class B shares; the composition of accounts payable);
- 27 page footers and running heads inside the incorporated Note 30.

Withdrawn results stay withdrawn until the recomputed ones are read.
