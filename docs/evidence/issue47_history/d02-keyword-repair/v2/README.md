# D02 Item 8 category-mention rule, version 2: a comma beside the keyword is not a list [shared-with-#28]

Owner of the shared repair: #47. Reported by #28's limited review of its own wiring of version 1 (de22326d; [Issue #47 comment 5948676381](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5948676381)).

## The defect

Version 1 (`104876d6`, wired in `36c64ab6`) took any separator next to the keyword as evidence that the keyword is one item of a list. A comma that opens a relative clause or a participial phrase therefore counted. #28's two sentences were left out although each states a matter of the company:

- `We face litigation, which could result in a significant loss.`
- `Litigation, brought by a customer against us in 2025, remains unresolved.`

Neither sentence occurs in a saved filing, but the review showed the rule could drop a real disclosure. It also showed the vocabulary of the second condition could not be the fix ("只扩充暴露词难以穷尽表达方式").

## The repair (`scripts/vnext/d02_item_8_category_mentions.py`, terms in `catalog/r6/D02_item_8_category_mention_v2.json`)

Version 2 keeps version 1's evidence (the separator beside the word, or the parenthetical that opens with "including"/"such as") and adds the structure that evidence has to stand in. It reads only closed-class words: auxiliaries, relative words, prepositions, coordinators, "we", "the Company". An occurrence is a category mention only when all of these hold:

| Condition | Why code when it fails | Example kept |
|---|---|---|
| the keyword's own phrase is no clause and names no party (`by`, `against`) | `KEYWORD_PHRASE_IS_A_CLAUSE_OR_NAMES_A_PARTY` | "Irrespective of its merits, litigation may be lengthy" |
| the phrase does not name the registrant (`our`, `us`, `the Company`) | `KEYWORD_PHRASE_NAMES_THE_REGISTRANT_S_OWN_MATTER` | "(e.g., the litigation arising from the failure of our dam)" |
| the phrase is not the first item of its sentence | `GOVERNED_BY_ITS_SENTENCE` | both of #28's sentences |
| the words before the keyword in its item are no clause | `KEYWORD_PHRASE_IS_A_CLAUSE` | "In 2018, we recorded expenses ... related to legal proceedings, investigations ..." |
| the series is not governed by the registrant as subject | `GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT` | "We face regulatory actions, litigation and fines." |
| no item right after the series opens with a clause word | `SERIES_IS_A_SUBJECT` | "In 2025, fines and litigation, brought by customers, remain unresolved." |
| a coordinator (and, or, as well as) joins it to another list item, or it is an example after "including"/"such as" or in such a parenthetical | `NO_COORDINATED_SERIES` | "In 2025, litigation, a costly matter, continued." |

A coordinator joined straight to the governing words ("can include formal administrative and legal proceedings") counts only when the phrase is the keyword alone. An Oxford comma (", and") is one separator.

Four relation entries join the exposure list: exposed to or named in a legal matter; a matter against the registrant; a matter brought or asserted by or against a party; suing and arbitration. They were added after the independent battery below found paragraphs that state a matter in those words.

Version 2 only adds conditions to version 1's evidence. A block version 1 keeps therefore cannot leave under version 2. The census checks this rather than assuming it.

## Measured (`compare.py` → `compare.json`, zero calls)

Version 1 is the committed `104876d6` module with its own terms file; version 2 is this tree.

| Set | What it is | Version 1 | Version 2 |
|---|---|---|---|
| Judged Item 8 admissions, design (61) | readings the rule was written beside | 16 non-disclosures out, 0 disclosures out | the same |
| Judged, held-out JPMorgan (59) | readings made after version 1 was frozen | 9 out, 0 disclosures out | the same |
| Judged, Pfizer FY2021 seen (39) | read while drafting version 1 | 3 out, 0 disclosures out | the same |
| Constructed by the executor (26 that state a matter / 6 that only name a category) | design material for version 2 | 24 / 6 left out | 1 / 6 left out |
| Independent battery (40 / 25) | written by a fresh agent that did not see the rule (`independent-battery-1.json`) | 20 / 11 left out | 0 / 8 left out |
| Every saved annual report (64; one does not build) | all 158 Item 8 keyword admissions | 29 left out | 28 left out; none that version 1 keeps |

The one saved block that moves is ViacomCBS FY2020 block 2382: "In 2018, we recorded expenses of $128 million primarily for professional fees related to legal proceedings, investigations at our Company and the evaluation of potential merger activity." Version 1 left it out; version 2 keeps it. The report is the predecessor's FY2020, outside the frame's target years, so no D02 position in the frame changes its excerpts.

The four real exclusions #28 checked (Lumen 1670, Pfizer 2175/2240, Paramount 2257) still leave. Paramount 2108 still stays. The latest-year route test (`tests/vnext/test_historical_d02_category_route.py`) holds both. Tests: `tests/vnext/test_d02_item_8_category_mentions.py`, with one case per condition, #28's two sentences, the four relation entries and the independent battery. Injections: `injections.json`.

## What it does not do

- It reads closed-class words only. A series in subject position whose verb is attached to its last item ("In 2025, litigation, fines and penalties increased.") still reads as a list. A matter stated entirely in words outside the vocabulary is not seen. The rule still requires both conditions together, so such a paragraph leaves only if every keyword occurrence also passes the structure above.
- The independent battery was run before the four relation entries and the registrant-reference check were written. It is design material for those parts, not a held-out measure of version 2.
- Both batteries were written by models of the executor's family. They are constructed stress tests, not readings of filings.
- It removes only one kind of wrong admission. JPMorgan's 18 Visa and accounts-payable admissions, and the other reasons a block can be wrong, are unchanged.

## For #28

Pin this commit's `scripts/vnext/d02_item_8_category_mentions.py` and `catalog/r6/D02_item_8_category_mention_v2.json`. The interface is unchanged: `left_out_as_category_mention(*, text, keyword)` and `classify(...)`. `classify` now also returns the why codes in the table above. The module reads the terms file next to it by a path relative to itself. Where version 2's terms hash enters a proposal (`item_8_category_mentions_left_out.terms_hash`), the candidate hash moves even when the left-out blocks do not.
