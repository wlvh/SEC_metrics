# D02, Item 8: a category mention of litigation is not a legal disclosure [shared-with-#28]

Owner of the shared repair: #47 (Issue #47 comment 5946182786; #28 supplies counterexamples, the positives that must stay, and the ordinary-route integration).

## The defect

D02's approved sources are Item 3, legal proceedings and the contingencies notes. Item 8 at large is not a source, so the route admits an Item 8 paragraph only through the frozen keyword `_LEGAL` (litigation, lawsuit, legal proceeding, legal claim, loss contingency, litigation reserve). The keyword admits wherever the word stands. The two-direction readings found the same wrong admissions again and again. Each was a paragraph that names litigation only as a category, never as a matter: counsel fees for "finance, regulatory, litigation, and other matters"; receivables written off "(including litigation, where appropriate)"; estimates moved by "competition, litigation, legislation and regulations"; covenant add-backs. Three deterministic replacements were tried first, and each failed on a real filing (`d02-content-read/keyword-proxy-decision.json`).

## The rule (`scripts/vnext/d02_item_8_category_mentions.py`, terms in `catalog/r6/D02_item_8_category_mention_v1.json`)

A keyword paragraph is left out only when both hold:

1. every occurrence of the keyword is a list member (between separators such as a comma, "and", "or", "including", "such as") or an example in a parenthetical ("(including litigation ...)"), and the paragraph is prose;
2. nothing in the paragraph states a legal matter of the registrant: subject to / involved in / party to a legal matter, accrued or recorded for one, self-insured for claims, a matter in a court (filed, pending, alleged, judgment, verdict, appeal, dismissal, subpoena, injunction, plaintiff, defendant, class action, complaint), or a settlement of one.

A label is never left out. The terms file holds no company names. Interface: `left_out_as_category_mention(*, text, keyword)`; `classify(...)` returns why.

Where the route asks it: `historical_text_results._d02_section` for Item 8 and for statements printed after a pointer Item 8. Both the ordinary branch and the hyperlinked-sentence branch use it. The proposal records the blocks it left out under `item_8_category_mentions_left_out`, with the terms hash; a filing with none keeps its proposal byte for byte. `item_8_review_pool` asks the same function, so the D02 model-review request's keyword part is still exactly the proposal's Item 8 excerpts. `tools/read_d02_excerpts.py` lists each left-out block in the packet's skipped set (`left_out_by: D02_ITEM_8_CATEGORY_MENTION`), so a reader still sees it.

## Measured (zero calls)

| Set | Item 8 keyword admissions judged | Disclosures kept | Disclosures lost | Non-disclosures left out | Non-disclosures kept |
|---|---|---|---|---|---|
| Thirty older-year readings the rule was written beside (design) | 61 | 45 | 0 | 16 | 0 |
| JPMorgan FY2021-FY2025, judged after the rule was frozen (104876d6) by readers who did not know it (held-out) | 59 | 10 | 0 | 9 | 40 |
| Pfizer FY2021, judged after the freeze; its keyword blocks were looked at while drafting, so it is reported as seen, not held-out | 39 | 36 | 0 | 3 | 0 |
| Salesforce FY2022-FY2024, judged after the freeze | 0 | - | - | - | - |

Latest years (the census in `d02-content-read/keyword-proxy-decision.json`): Lumen 1670, Paramount 2257, and Pfizer 2175 and 2240 leave. Lumen 3382/3383, Paramount 1900/2108 and Pfizer 2302/2351 stay. Every other latest-year D02 proposal is unchanged.

`tests/vnext/test_d02_item_8_category_mentions.py` holds the design and held-out counts exactly. `tests/vnext/test_historical_d02_category_route.py` holds the route to them on the saved latest-year filings. It checks the left-out blocks, the disclosures beside them, D03's candidates, the review pool, and Marriott's unchanged proposal.

## What it does not do

It removes only one kind of wrong admission, and it does so without losing a disclosure on the held-out set. Of JPMorgan's 49 held-out non-disclosures it leaves 40 in place, for reasons that are not category mentions:

* 22 are MD&A text (critical accounting estimates, forward-looking statements, Russia exposure). They come in because the range for statements printed after a pointer Item 8 starts at an MD&A heading ("Consolidated balance sheets analysis") rather than at the statements. That is a range defect, repaired separately.
* 18 are in the notes, and the rule keeps each on one of its two conditions. Ten describe the Visa class B shares, whose conversion depends on Visa's covered litigation. The keyword there names another entity's litigation, not one item of a list, so condition 1 fails (one paragraph also names a court). Eight are the composition of accounts payable and other liabilities and its cross-reference. The keyword there is a list member, but the paragraph says "accrued interest", which reads as an accrual, so condition 2 fails. The rule errs toward keeping.

Pfizer FY2021's 49 skipped Note 16A blocks are a navigation defect, not a keyword one: the Note 17 heading prints its number bold and its separator in body weight. JPMorgan's Note 30 page footers are a furniture defect. Both are repaired separately.

The D02 model-review requests' digests move wherever the keyword part of the pool moves. The call application's D02 measurement is regenerated when the code is final.
