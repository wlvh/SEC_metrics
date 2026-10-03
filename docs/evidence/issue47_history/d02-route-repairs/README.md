# D02 route repairs found by the older-year readings

The two-direction readings of the thirty older-year D02 values
(`../d02-older-years/`) found four ways the historical route takes what the
filing did not say, or misses what it did, that are not the keyword proxy. Each
is repaired in `scripts/vnext/historical_text_results.py`, for D02 only, and
measured on every saved annual report before it was kept. The keyword proxy
itself stays the registered decision (`../d02-content-read/keyword-proxy-decision.json`).

## 1. An item heading printed at the foot of a page

Southwest's FY2023 report prints "Item 4. Mine Safety Disclosures" as the last
line of page 56. The frozen heading scan (`text_coverage._heading`) refuses a
heading whose next block is a bare number, because a contents list puts item,
title and page in three cells; the page number after a page-foot heading looks
the same. Item 3 ran on to the next heading the scan accepted, and Item 4's
answer, "Not applicable.", was an excerpt.

`page_bottom_item_headings` asks the frozen scan again with the page numbers
blanked (`page_number_blocks`, the same presentation the note navigation uses),
so the scan's own rules decide what a heading is; `_sections_from` rebuilds the
sections from the result and is held to the frozen derivation on every document
before it is used. A heading added this way that moves no section leaves the
document as it was.

Measured over the 61 saved annual reports that build (`page_foot_headings.py`,
`page-foot-headings.json`): the blanking adds five headings - four "Item 6.
Reserved." at a page foot (Marriott FY2025, Salesforce FY2022, FY2024, FY2025)
and Southwest's Item 4 - and one range moves: Southwest FY2023's Item 3, from
[747, 798) (narrowed to [747, 773) by the unnumbered-item boundary) to
[747, 767). The census records the route before this repair (the narrowing
alone) and after it separately: the narrowing that was already there moves
seven reports (Pfizer's six and Southwest FY2023), this repair only Southwest
FY2023. Its first run compared the frozen ranges with the repaired ones only
and so listed Pfizer's six reports as moved too; that output was replaced.

## 2. Page footers taken as excerpts

The furniture rule counts repeats inside the scope it reads and wants a
repeating neighbour there. In Pfizer's FY2023 and FY2024 reports Item 3 is four
blocks - the sentence, "Pfizer Inc.", "<year> Form 10-K" and the page number -
so nothing repeats inside it and the form-name footer became an excerpt. In the
FY2022 report the footer is one block, "Pfizer Inc.2022 Form 10-K", and the page
number stands between it and the running head, so it has no repeating
neighbour; six copies became excerpts of Note 16A.

`page_structure_furniture` finds furniture by its place on the page: walking
out from each page number, a block is furniture while its text stands at that
same offset from a page number on at least three pages. A matter label or a
heading that happens to open a page does not. It applies on D02's branch only,
beside the scope rule, as the scope rule does.

## 3. Captions the note does not carry

Lumen's FY2021 Item 3 incorporates the "Pending Matters" and "Other Proceedings
and Disputes" subheadings of Note 18; the note calls them "Principal
Proceedings" and "Other Proceedings, Disputes and Contingencies". With no quoted
caption found, the route took the whole note, and the value carried the
right-of-way table and the purchase commitments the filing did not incorporate.

`unincorporable_captions` returns every quoted caption the note does not carry
(its own title, with or without the note's number, is not a limit). Any such
caption stops the position as navigation incomplete
(`UNRESOLVED_INCORPORATED_CAPTION_<note>`): a caption the route cannot find is
not replaced by the whole note, and one found caption does not stand for two.

A quoted Form 10-K item is not a caption. Paramount's Item 3 points to "Item 8.
Financial Statements and Supplementary Data" before it names the "Legal
Matters" caption of the note: the quoted item says where the note is, not which
part of it is incorporated. The first version of the repair read it as a
caption the note must carry and stopped every Paramount year as navigation
incomplete; the unit cases passed, and only the frame-wide measurement below
caught it. A quoted string that begins with an item number ("Item 8.", with or
without a Part before it) is no longer a caption.

## 4. Statements printed after a pointer-page Item 8

Macy's FY2021 Item 8 is twenty blocks saying where the statements are; they are
printed after the signatures. The keyword proxy reads Item 8 only, so it read
none of them, and the value lacked the self-insurance claims accrual that the
same company's FY2022-FY2024 values carry through Item 8.

`appended_statements_range` treats Item 8 as a pointer page when it holds none
of the primary statements' titles and the document prints them after it; the
range from the first title after Item 8 to the end of the document is then read
as Item 8 is, through the keyword, for D02 only. A note an Item incorporates
keeps its own blocks (the innermost range owns a block). The census of where
each report prints its statements (`appended_statements.py`,
`appended-statements.json`) finds this layout in every Ford and JPMorgan report,
Macy's FY2020 and FY2021 and Hyatt FY2025.

## Measured effect on the frame's D02 positions

`effect.py` loads the route as committed and as repaired into one process and
gives both the same pinned input for each of the 41 frame positions; it
compares the D02 excerpt set, D03's candidates, the ranges and the coverage.
The result is in `effect.json` (export-restored root of the first approval,
zero calls). Eleven positions move and thirty are unchanged:

| Position | What moves | Repair |
|---|---|---|
| Pfizer FY2022 | six copies of the footer "Pfizer Inc.2022 Form 10-K" leave Note 16A's excerpts | 2 |
| Pfizer FY2023, FY2024 | the "<year> Form 10-K" footer leaves Item 3 | 2 |
| Southwest FY2023 | Item 4's "Not applicable." leaves; Item 3 ends at block 767 | 1 |
| Lumen FY2021 | stops as `HISTORICAL_TEXT_BOUNDARY_NAVIGATION_INCOMPLETE: UNRESOLVED_INCORPORATED_CAPTION_NOTE_18` instead of taking the whole note | 3 |
| Macy's FY2021 | the self-insurance claims accrual (block 2950) is an excerpt | 4 |
| Ford FY2021-FY2025 | a range is added for the statements printed after the pointer-page Item 8; no excerpt moves | 4 |

D03's candidates move in none of the forty positions that build under both
versions (Lumen FY2021 stops under the repair; this route serves D02 and C02
only, so the stop is D02's, and D03 has no historical route). The removals are exactly
the blocks the readings found wrong for these causes, and the one addition is
the block Macy's FY2021 reading found missed; the keyword-proxy blocks of the
same positions stay, as decided.

The first measurement, before the quoted-item exclusion, also moved all five
Paramount years - to a false stop - and is kept as the reason for that rule,
not as a result.

## Fault injections

`injections.py` breaks one rule at a time in an isolated worktree, each run
with its own bytecode directory, after a control run of the sixteen cases in
`tests/vnext/test_historical_d02_route_repairs.py` passes (619 seconds). All
thirteen injections are caught, each by the case written for it
(`injections.json`): page-foot headings not added, a heading that moves
nothing still rewriting the document, the section derivation drifting from the
frozen one, no page-position furniture, the furniture walk not stopping at a
block that does not recur, the furniture skipped for D03 too, uncarried
captions ignored, the note's numbered title read as a missing caption, a
quoted Form item read as a caption, one found caption standing for two, the
appended statements not read, read whole, or feeding D03. The route file was
the repaired one before and after the run.

## Not covered

- The keyword proxy's category-only blocks (Lumen's cost definition and legal
  fee policy, Pfizer's estimates list, receivables and tax paragraphs) are not
  touched; they stay withdrawn under the registered decision.
- The D02 Item 8 review contract's pool (`item_8_review_pool`) still reads Item
  8 alone; for a pointer-page report the appended statements are not in the
  pool. No model call has been made under that contract.
- Southwest's and JPMorgan's newest acquisitions are not in the restored root
  these measurements used.
