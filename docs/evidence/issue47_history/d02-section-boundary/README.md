# D02 on Pfizer returns another item's text, and the current route does too

Running every wired metric against Pfizer's pinned 2025 period produced a D02
public row of 23,039 characters whose first item is
`INFORMATION ABOUT OUR EXECUTIVE OFFICERS`. D02 is legal proceedings —
`LEGAL_DISCLOSURE_EXCERPTS_V1` over `ITEM_3`, `ITEM_8` and `REFERENCED_NOTES`.

The row is **`EXACT` and `PUBLISHED`**. No quality downgrade, no reason code.
Read from the coverage matrix alone it is indistinguishable from the correct
D02 rows that Marriott and Ford produce, and the count of eleven D02 values this
branch reported includes it.

## It is not the historical route's doing

Both routes select the same filing and feed the same frozen candidate builder:

```
ordinary accession  0000078003-26-000026
historical accession 0000078003-26-000026        identical
```

Built through each path, `result["text_payload"]` is byte-identical: 58 items,
same first item, both `EXACT`. So the current production D02 route has this
behaviour on this company; the historical route only exercised it somewhere the
ordinary one had not been published against.

## Where the boundary goes wrong

`build_text_document` locates the sections correctly — `ITEM_3` is `LOCATED`
with exactly one candidate. The defect is the candidate's **end**:

| block | emphasized | text |
| ---: | --- | --- |
| 936 | yes | `ITEM 3.LEGAL PROCEEDINGS` |
| 937 | no | `Certain legal proceedings in which we are involved are discussed in Note …` |
| **938** | **yes** | **`INFORMATION ABOUT OUR EXECUTIVE OFFICERS`** |
| 939–970 | | the officer table and biographies |
| 971 | yes | `PART II` |

The located range is `937..972`, running to `PART II`. Pfizer's Item 3 is a
single cross-reference sentence, and the unnumbered item that follows it is
swallowed whole — which is why it dominates the extracted text rather than
merely appending to it.

The boundary rule ends a numbered item at the next numbered item or `PART`
heading. An unnumbered emphasized heading between them does not end it. Marriott
and Ford do not show this because their Item 3 is followed directly by `PART II`.

## Why this is not fixed here

`scripts/vnext/text_coverage.py` is inside `issue_28_v13`'s execution authority.
Changing its bytes changes what every existing ordinary Run replays against, and
the rule being changed is what counts as a metric's disclosed text — a
correctness standard for D02 and D03, not a wiring detail. Per `AGENTS.md` that
is an alignment point rather than something to decide while wiring a route.

Options, with the evidence above as their basis:

1. **End a numbered item at the next emphasized heading that is not part of it.**
   Narrowest fix, but it changes extracted text for every company whose filings
   have unnumbered headings inside an item, so every existing D02/D03 result
   needs re-deriving and comparing.
2. **Treat an item whose own body is only a cross-reference as
   `NOT_UNIQUELY_LOCATED`**, so it withholds with a reason instead of
   publishing another item's text. Loses Pfizer's D02 rather than answering it
   wrongly.
3. **Leave the extraction and add a content guard** that refuses a payload whose
   first item is an emphasized heading outside the required sections. Does not
   fix the extraction, only stops it publishing.

Recommendation: **2 now, 1 as the real fix**, because a withheld D02 with a
named reason is honest and a wrong 23,000-character legal disclosure is not.
Neither belongs in this branch's scope without the Issue #28 integrator, since
both re-derive existing production results.

## What this branch does in the meantime

Nothing that hides it. The Pfizer D02 row stays as the run produced it, this
file records what it is, and the D02 value count is stated with the defect
attached rather than as eleven clean values.
