# D02 older years: two-direction readings

The latest-year D02 values were read in both directions by hand
(`content-acceptance/d02-both-directions-read.json`), and that record has no
code that reproduces it. The thirty older-year values here are read the same
way, but the packet each reader judges is built by committed code and every
judgement is checked by it.

## Packet

`tools/read_d02_excerpts.py --packet` recomputes the route's own selection from
the saved annual report (an export-restored root for older years) and lists:

- `taken` - every excerpt of the value, in order, with its scope: `ITEM_3`, a
  `NOTE_` scope Item 3 incorporates by reference, or `ITEM_8` (a keyword block
  from elsewhere in the financial statements);
- `skipped` - every block inside Item 3 and the incorporated scopes that the
  value does not contain;
- `context` - the blocks under an Item 8 heading that names contingencies,
  legal proceedings or litigation, in a note Item 3 does not incorporate: a
  numbered note up to the next numbered note, any other heading up to the next
  bold heading, capped. The definition names contingencies notes as a source,
  and only the keyword blocks of such a note reach the value, so this is the
  direction a reading of the excerpts alone cannot see;
- `outside` - where a filing's Item 8 is a pointer page, the keyword blocks
  printed after Item 8 and outside every range the route reads. This list was
  added after the thirty readings (see `reader-prompts.md`); only Macy's FY2021
  has a block in it;
- `headings` - every heading-shaped block of the document naming
  contingencies, legal proceedings, litigation or commitments (the
  definition's source words, not the proxy's keyword set).

## Reading

Each company's packets were read by one independent reader - a fresh-context
subagent of the same model family, not a person - given `reader-brief.md`
verbatim and the packets, and nothing of the selector's rules or of any
earlier reading. Its verdicts by block index were merged with the packet's
texts (`--merge`) into `judgements/<company>-<period>.json`; the merge refuses
an answer that does not cover the packet exactly.

A skipped or context block can be `COVERED_ELSEWHERE`: litigation text whose
matter the value already states, with the excerpts that state it cited. The
first reading found the case this exists for: Enphase FY2024's Note 14
describes the Zola complaint (block 2043), which the keyword proxy did not
take and Item 3 states at 755/756.

## What it does not cover

Item 8 outside the incorporated scopes is read only where the keyword proxy
took a block, under the headings that name the definition's words, and - after
a pointer-page Item 8 - where the keyword occurs; a litigation disclosure under
a heading worded otherwise, or under none, is not in the packet. The readers are of the same model family as the executor who
wrote the rules. The keyword proxy's own decision stays where it is
(`d02-content-read/keyword-proxy-decision.json`).

## Findings so far

- **Enphase FY2021-FY2024, Ford FY2021-FY2024: agree.** Ford's one judgement
  call is the warranty table's year row, which the selector skips (the frozen
  `_substantive` test drops a block with no letters): the reader called it
  covered elsewhere citing the table's introduction, which does not state the
  years; the executor decided the class (`adjudication.json`,
  NUMERIC_TABLE_HEADER_ROW) - table structure that states no matter - and
  recorded that the value's warranty columns are unlabelled, as in the
  accepted latest-year Ford value.
- **Lumen FY2021-FY2024: disagree.** Every year carries keyword-proxy blocks
  that are not litigation disclosure - the SG&A definition that lists
  litigation as a cost (FY2021-FY2023) and the outside-counsel fee policy
  (every year; the reader's prompt carried this example, see
  `reader-prompts.md`). FY2021 also has a scope defect the reader found and
  the executor verified: Item 3 incorporates the note's "Pending Matters" and
  "Other Proceedings and Disputes" subheadings, the note calls them
  "Principal Proceedings" and "Other Proceedings, Disputes and Contingencies",
  and with no caption matching, the route falls back to the whole of Note 18 -
  so the value also carries the Right-of-Way table (part of it: the rows
  without letters are dropped) and the purchase commitments, which the filing
  did not incorporate. The reader departed from the brief's literal rule
  (incorporated-scope content counts) on those nine blocks, because the
  rule's reason - the filing chose to incorporate them - does not hold; the
  executor accepts the departure on that verification.
- **Macy's FY2022-FY2024: agree.** The one call is a footnote, "2022 includes
  an income tax benefit from the favorable resolution of state income tax
  litigation", which the reader judged incidental because the brief listed
  "tax" among incidental contexts. The executor decided it
  (`adjudication.json`, SPECIFIC_LEGAL_MATTER_IS_DISCLOSURE): it states the
  resolution of a specific suit of the registrant's, and litigation named only
  as a category is what the brief's examples meant. The same rule moved two of
  the executor's own earlier classifications (Paramount FY2025 block 2108 and
  FY2024 block 2010, both stating stockholder-litigation settlement amounts),
  recorded in `known_result_defects.json` and
  `d02-content-read/keyword-proxy-decision.json`.
- **Macy's FY2021: disagree.** Its Item 8 is a pointer page and the statements
  are printed after the signatures, so the keyword proxy read none of them and
  the value is Item 3 alone. The outside list brought in the self-insurance
  claims accrual (block 2950) - the paragraph the FY2022-FY2024 values carry
  and their reader judged DISCLOSURE. The second reader judged it correctly
  skipped (the legal words read as actuarial inputs); the executor held the
  paragraph to one answer across the years (CLAIMS_ACCRUAL_IS_DISCLOSURE: the
  definition names loss contingencies and accruals arising from claims).
- **Marriott FY2021-FY2022, Paramount FY2021-FY2024, Salesforce FY2025,
  Southwest FY2021, FY2022 and FY2024: agree.**
- **Pfizer FY2022-FY2024: disagree.** Each year carries three keyword-proxy
  blocks that name litigation only as a category (the critical-estimates list,
  the collection of receivables, uncertain tax positions) and page footers
  taken as excerpts - the "<year> Form 10-K" block inside the four-block Item 3
  (FY2023, FY2024) and six copies of the merged footer "Pfizer Inc.2022 Form
  10-K" inside Note 16A (FY2022).
- **Southwest FY2023: disagree.** "Item 4. Mine Safety Disclosures" is the last
  line of a page, followed by the page number; the frozen heading scan reads
  that as a contents row, Item 3 runs on, and Item 4's "Not applicable." is an
  excerpt.

The route causes are registered by position (`causes.json`,
`register_defects.py`); three of them - the page-foot heading, the footers and
Lumen FY2021's captions - and Macy's pointer page are repaired in
`../d02-route-repairs/`. The keyword proxy remains the registered decision.
