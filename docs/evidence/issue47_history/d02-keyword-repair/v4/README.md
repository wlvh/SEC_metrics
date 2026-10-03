# D02 Item 8 category-mention rule, version 4: a list member leaves only under a proven closed-class governor [shared-with-#28]

Owner of the shared rule: #47. Asked by #28 (Issue #47 comment 5956052190), after it fixed version 3 (`60c6b4d6`, module bytes `1672097b`) and reproduced on its copy the two limits version 3's own notes listed:

- `Kestrel defended regulatory proceedings, litigation and fines.` - the registrant by its own name, an open-class verb;
- `In 2025, litigation, fines and penalties increased.` - the series is the subject of an open-class verb.

Version 3 left both out. #28 asked in what range the exclusion can be proven, and that a block stays a candidate where it cannot.

## The change (`scripts/vnext/d02_item_8_category_mentions.py`, terms in `catalog/r6/D02_item_8_category_mention_v4.json`)

Version 3 asked for a closed-class governor of the series - a preposition, "including" or "such as" before its first member, not one that opens the sentence - only where the registrant was named before the series. Version 4 asks it of every list member. Without one the block stays, with reason `NO_CLOSED_CLASS_GOVERNOR_PROVEN` (or version 3's `REGISTRANT_NAMED_AND_NO_GOVERNOR_PROVEN` where the registrant is named, so that answer keeps its name). Examples after "including"/"such as" and parenthetical examples carry their own governor and are read as in version 3.

Version 4 runs version 3's decision unchanged and only adds this condition to a category reading, so a block version 3 keeps cannot leave. The terms file differs from version 3's only in its version, what it supersedes and its explanation; every pattern is the same, and the terms hash changes so a record shows which version decided.

## What a removal proves, and what it does not

A block leaves only if it is prose, contains none of the legal-matter vocabulary (`exposure`), and every keyword in it is either an example after "including"/"such as" (or a parenthetical example), or a determiner-only item ("other litigation") of a coordinated series whose first member a preposition governs; the keyword's own item holds no clause, party or registrant; and the registrant is not acting before the governor in its clause.

That is a statement about structure, read from closed-class words. It is not a proof that the series is about categories rather than the registrant's own matters, because two things are open-class:

- **the registrant by its own name.** The vocabulary knows "we", "us", "our", and "the" or "our" with company, firm, corporation or registrant. `In 2025, Kestrel was hit with regulatory proceedings, litigation and fines.` still leaves.
- **what the governor's noun is about.** `The increase reflects costs of settlements, litigation and fines.` can be the registrant's own costs; it still leaves.

Both sentences are held in `test_the_range_the_proof_does_not_reach` as recorded limits, not as wanted answers. Where they matter, the block's legal-matter vocabulary is the only protection, and a matter stated in words outside it is not seen.

Measured against that residue: of the 23 blocks version 4 removes across the saved annual reports (census below), none names the registrant by its own name as the actor of the series' clause. One names it in another clause: Paramount's covenant add-back paragraph (`psky-20251231.htm` block 2257, "Paramount Global entered into an amendment ..."), which the latest-year reading judged no disclosure.

## Measured (`compare.py` → `compare.json`, zero calls)

Version 3 is the committed `1672097b` module with its own terms file; version 4 is this tree.

| Set | What it is | Version 3 | Version 4 |
|---|---|---|---|
| Judged Item 8 keyword blocks (174: older-year readings and round 1e1ef948, taken and skipped) | readings | 99 disclosures kept; 28 non-disclosures and 7 correctly skipped out | 99 disclosures kept; 24 non-disclosures and 6 correctly skipped out |
| #28's four sentences on version 3 (3 that state a matter / 1 adviser list) | the question | 2 / 1 left out | 0 / 1 |
| #28's three P2 sentences on version 2 | earlier review | 0 left out | 0 |
| Constructed beside version 4 (4 that state a matter / 3 governed category lists) | design material | 4 / 3 | 0 / 3 |
| Constructed beside version 3 (11 / 3) and version 2 (26 / 6) | design material | 0 / 3; 1 / 6 | 0 / 3; 0 / 5 |
| Independent battery 1 (40 / 25) and battery 2 (40 / 25) | earlier held-out material | 0 / 5; 0 / 3 | 0 / 5; 0 / 2 |
| Every Item 8 keyword admission in the 64 saved annual reports (158) | census | 28 left out | 23 left out |

**Every block that moves is the same paragraph.** In the census the five are Pfizer's uncertain-tax-position paragraph, FY2020 to FY2024 (`pfe-2020…2024`, blocks 2821, 2685, 2555, 2961, 2877): "Finalizing audits with the relevant taxing authorities can include formal administrative and legal proceedings". The series is the object of "can include"; "include" is no closed-class word, so no governor is proven - the same shape as "Kestrel defended regulatory proceedings, litigation and fines." The readers judged it no disclosure (incidental proceedings with tax authorities), so this is the measured cost of asking for proof: four judged non-disclosures stay (FY2021–FY2024; FY2021's block was judged again in round 1e1ef948, the one correctly skipped row that moves). Version 4 removes nothing version 3 kept. In the batteries the two category lists version 4 now keeps have the same shape ("can include", "comprise").

## What it costs #47

Pfizer FY2021–FY2024 D02 were accepted on results computed before version 4. Those acceptances stay bound to those results. A D02 run under a closure carrying version 4 includes the tax paragraph in those four years; a reader judged it no disclosure, so those new results would not be accepted on reading. Resolving it needs either the Item 8 review contract (`../../d02-item-8-review/`, a model call not yet granted) or a rule that can prove a membership verb ("include", "comprise") a category marker without the residue above; neither is done here.

## Injections (`injections.py` → `injections.json`)

Each condition taken away in turn, in a worktree nothing else read; the case written for it must fail. Version 4's two conditions come first, then version 3's proof and version 2's structure: 30 injections, control passed, all 30 caught by the case written for each. One change was needed on the way: under version 4 the governor test also keeps #28's two earlier reported sentences, so the case written for version 2's structure ("We face litigation, which could ...") no longer saw the structure taken away; it now holds the structure's own reason (`GOVERNED_BY_ITS_SENTENCE`) as well as the outcome.

## For #28

Interface unchanged (`classify`, `left_out_as_category_mention`). Terms file `catalog/r6/D02_item_8_category_mention_v4.json`; new reason `NO_CLOSED_CLASS_GOVERNOR_PROVEN`; `REGISTRANT_NAMED_AND_NO_GOVERNOR_PROVEN` kept for version 3's case. Candidate hashes move wherever a block was left out (the terms hash is recorded); the excerpts move only where the tax paragraph returns.
