# A D02 row held another item's text, was `EXACT`, and is now repaired

Running every wired metric against Pfizer's pinned 2025 period produced a D02
public row of 23,039 characters whose first item is
`INFORMATION ABOUT OUR EXECUTIVE OFFICERS`. D02 is legal proceedings —
`LEGAL_DISCLOSURE_EXCERPTS_V1` over `ITEM_3`, `ITEM_8` and `REFERENCED_NOTES`.

The row was **`EXACT` and `PUBLISHED`**. No quality downgrade, no reason code.
Read from the coverage matrix alone it was indistinguishable from the correct
D02 rows Marriott and Ford produce, and the count of eleven D02 values this
branch reported included it.

It was found by reading the text of a result that had passed, not by reading a
failure log. That method is now `SOP.md` SOP 2.

## It was inherited, not introduced

Both routes select the same filing and feed the same frozen candidate builder:

```
ordinary accession   0000078003-26-000026
historical accession 0000078003-26-000026        identical
```

Built through each path, `result["text_payload"]` is byte-identical: 58 items,
same first item, both `EXACT`. Two routes agreeing proves common inheritance,
not correctness, so the chain was walked backwards to the first deviation
instead.

## The cause is two form facts meeting, not one filing's layout

`build_text_document` locates the sections correctly — `ITEM_3` is `LOCATED`
with exactly one candidate. The defect is the candidate's **end**:

| block | emphasized | linked | text |
| ---: | --- | --- | --- |
| 936 | yes | no | `ITEM 3.LEGAL PROCEEDINGS` |
| 937 | no | yes | `Certain legal proceedings in which we are involved are discussed in Note 16A.` |
| **938** | **yes** | **no** | **`INFORMATION ABOUT OUR EXECUTIVE OFFICERS`** |
| 939–970 | | | the officer table and biographies |
| 971 | yes | no | `PART II` |

`_SUCCESSOR["3"] = {"4", "5"}` in `scripts/vnext/text_coverage.py` deliberately
lets a later number close an item, with the comment "Some reports omit
inapplicable 1B/4 entirely". Form 10-K separately lets a registrant carry the
executive officer information as an unnumbered item inside Part I. Where both
apply, the numbered item runs past the unnumbered one.

Measured on the nine registrants whose 10-K this repository holds, reading each
`ITEM_3` candidate's own closing block:

| registrant | ITEM_3 closes at | carries the unnumbered item |
| --- | --- | --- |
| Enphase, Ford, Lumen, Macy's, Marriott, Salesforce, Southwest, Paramount | `Item 4. Mine Safety Disclosures` | Macy's, Marriott, Salesforce, Southwest |
| **Pfizer** | **`ITEM 5. MARKET FOR THE COMPANY'S COMMON EQUITY…`** | **yes, inside Item 3** |

Eight of nine are unaffected only because they file an Item 4. Five of nine
carry the unnumbered item at all; Marriott's sits two blocks past a boundary
that holds and Southwest's four. It is a form element meeting a deliberate
widening, so the repair is a form rule, not a company branch.

## The repair

`scripts/vnext/historical_text_results.py` closes a numbered item at the form's
unnumbered Part I item. The caption is matched on the block's **whole** text,
so an emphasized subheading inside an item's own body cannot end it.

It could not go where it belongs. `scripts/vnext/text_coverage.py` is named by
`issue_28_v11`'s rule set, and `issue_28_v11`'s engine re-checks those bytes on
both roots; `issue_47_v1` loads it through its parent chain, so changing that
file stops every Requirement from v11 onward from loading. The measured proof is
in this directory's own history: patching the file produced
`RequirementError: Normal candidate rule bytes differ: scripts/vnext/text_coverage.py`.
The successor therefore corrects the located ranges for the historical route
only, and the ordinary route keeps the behaviour until a generation that can
re-record that file carries the same rule. That is a stated limitation, not a
closure.

`_derive_candidate`, `build_text_review_unit`, the excerpt scan in
`legal_risk_candidates` and the record shape validator are the frozen ones,
called unchanged. Three functions are duplicated because they look up
`prepare_business_text_sources` and each other as module globals; the
duplication is held to the original by the subset assertions below.

## Measured effect: 26 blocks lost, all of them inside the officer section

`create_deterministic_text_candidate` run through both modules on all nine
filings:

| registrant | items before → after | characters | byte-equal to frozen |
| --- | ---: | ---: | --- |
| Enphase | 18 → 18 | 9,910 | yes |
| Ford | 53 → 53 | 18,025 | yes |
| Lumen | 15 → 15 | 7,979 | yes |
| Macy's | 3 → 3 | 1,181 | yes |
| Marriott | 10 → 10 | 4,924 | yes |
| **Pfizer** | **58 → 32** | **22,982 → 18,373** | **no** |
| Salesforce | 9 → 9 | 9,518 | yes |
| Southwest | 25 → 25 | 35,521 | yes |
| Paramount | 16 → 16 | 13,765 | yes |

`ITEM_3` narrows from `[937, 972)` to `[937, 938)`. The test asserts the strong
form of "no under-capture": the corrected block set is a strict **subset** of
the frozen one, and the difference is exactly the frozen set's intersection with
the officer section. Nothing outside it moved.

## What the repair does not fix, stated rather than folded in

Pfizer's Item 3 holds exactly one sentence — block 937, the cross-reference to
Note 16A. It is a hyperlink of 77 characters, and `_substantive` in
`text_business_candidates.py` excludes a linked block shorter than 120
characters as navigation. So after the repair Pfizer's D02 contains **no Item 3
text at all**; its 32 excerpts are Item 8's, which is where Note 16A's own text
lives.

That exclusion is inherited and unchanged: block 937 was absent from the frozen
58-item set too. This repair neither causes nor fixes it. Whether a short
hyperlinked sentence that is an item's entire body should count as disclosure is
a separate question about a rule with a wider blast radius — including it would
change four of the nine registrants:

| registrant | ITEM_3 blocks | short linked blocks dropped | entering the candidate set |
| --- | ---: | ---: | ---: |
| Enphase | 17 | 1 | 16 |
| Ford | 24 | 0 | 20 |
| Lumen | 1 | 0 | 1 |
| Macy's | 1 | 0 | 1 |
| Marriott | 5 | 1 | 3 |
| Pfizer | 35 | 1 | 26 → 0 after the repair |
| Salesforce | 3 | 0 | 3 |
| Southwest | 32 | 6 | 20 |
| Paramount | 1 | 0 | 1 |

It is recorded here as an open inherited question, with the measurement that
would scope it, rather than bundled into a boundary repair.

## Disposition of the wrong result

The Pfizer D02 Result that was published as `EXACT` keeps its original Run
bytes and keeps its repair responsibility. What it loses is its standing as a
valid result:

* it no longer cold reads. The corrected rule file changes the Requirement's
  closure, so the Run's recorded
  `sha256:a82225ad…` no longer resolves. The refusal layer is
  `REQUIREMENT_AUTHORITY`; the semantic Evidence replay is never reached,
  because the outer seal refuses first.
* every other `issue_47_v1` Run frozen before this repair refuses for the same
  reason, so "affected" is all of them, not one. They are recomputed, not
  re-labelled.
* the matrix driver's resume key was `(case, metric, selection_id)`, which would
  have skipped them as finished. It now includes the Requirement closure hash,
  so a position whose closure differs is re-run rather than reused.

The honest count of what this branch produced for D02 is: eleven results
produced, one confirmed wrong and now recomputed, the other ten with semantic
review not performed.
