# D02: page numbers on facing pages [shared-with-#28]

Found by the held-out readings of JPMorgan FY2021-FY2025 (`d02-older-years/judgements/`): Item 3 incorporates Note 30, and 27 of its excerpts are page furniture: the footer "JPMorgan Chase & Co./<year> Form 10-K" and the running head "Notes to consolidated financial statements".

## Cause

Both furniture criteria rely on page numbers (`page_number_blocks`). A page number is a bare number standing beside a running footer, on a side where the same footer also stands beside the number one lower or one higher. JPMorgan prints its reports as facing pages. On one page the number stands above the footer ("290" then "JPMorgan Chase & Co./2021 Form 10-K"), and on the facing page below it (footer, then "291"). The same side therefore never holds consecutive numbers, and the rule found 4 to 12 page numbers in reports of about 10,000 blocks.

## Change

A number also counts as a page number when two things hold:

- the footer beside it has words;
- the numbers beside that footer, on either side, run through this number for at least five consecutive values (`_FACING_PAGE_RUN`).

Looser forms were measured first, and each took table cells or contents entries for page numbers:

- two pages apart on the same side: cells beside "$", patent-term entries;
- one apart on the other side with no run: Ford's contents rows ("Ford Credit Segment 45 Corporate Other"), Macy's year columns;
- the run without the words condition: Macy's cells beside "—".

## Measured (`effect.py` → `effect.json`, zero calls)

The census covers every saved annual report that builds: 64 of 65, with Hilton FY2024, outside the frame, failing to build as before. Each report is run with and without the change.

| Report | Page numbers | D02 | D03 |
|---|---|---|---|
| JPMorgan FY2020-FY2025 (six) | 4-12 → 271-293 | loses only footers and running heads in Note 30 (FY2021-FY2025: 6, 6, 6, 5, 4 = the 27 the readings judged not disclosures) | unchanged |
| Southwest FY2021-FY2025 (five) | +1 each: the number between the notes' running head and "Item 9." | unchanged | unchanged |
| every other report | unchanged | unchanged | unchanged |

Tests: `tests/vnext/test_historical_note_navigation.py` has constructed facing pages, a footer without words and a short run. `tests/vnext/test_historical_d02_route_repairs.py` (`FacingPageFurnitureTest`) uses JPMorgan FY2025 and holds the lost blocks to the reading's judgements. Injections: `injections.json`.
