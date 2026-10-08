# D02 Item 8 category-mention rule, version 3: a category reading must be proven [shared-with-#28]

Owner of the shared rule: #47. Reported by #28's scoped review of its copy of version 2 (`79677ed2`, NEEDS_FIX P2; Issue #28 evidence `docs/evidence/issue28_continuous/collab-d02-versioned-20261002/v2/independent-review-79677ed/conclusion.md` on `task/b06-new-source`).

## The defect

Version 2 left out a paragraph that states the registrant's own matter:

- `During 2025, our company faced litigation, regulatory proceedings and fines.`

Three gaps met. Version 2 knew the registrant only as "we" or "the Company"/"the Firm"/... at the start of an item, not "our company". The fronted "During 2025," put the keyword after a comma, so it was no longer the first item of its sentence and read as a list member. And no relation in the exposure list read "faced". Replace "our company" with "the Company" or "we" and version 2 keeps the sentence. The sentence is constructed; no saved filing contains it.

Adding the three words would close this sentence and leave the next one open ("During 2025, the Group defended litigation, ..."; "In 2025, our company was hit with regulatory proceedings, litigation and fines."). So version 3 changes what the rule asks instead: a reading as a category has to be shown, and a sentence the closed-class words cannot place stays in D02's set.

## The repair (`scripts/vnext/d02_item_8_category_mentions.py`, terms in `catalog/r6/D02_item_8_category_mention_v3.json`)

Version 3 runs version 2's decision unchanged, with version 2's vocabulary, and only where version 2 reads a category does it ask for more. The proof can only turn a category reading into a non-category one, so a block version 2 keeps cannot leave - by construction, not only on the material measured. The first version 3 (`2a98ba84`) replaced version 2's registrant-governs check with its own walk instead; a constructed sentence then showed it leaving out what version 2 keeps ("We defended regulatory actions, claims that name us in suits, litigation and fines."), so it was rebuilt this way (`1672097b`).

The proof:

| Condition | Why code when it fails | Example kept |
|---|---|---|
| the keyword opens its own item, apart from a determiner ("other litigation"); words before it may be its own subject and verb | `KEYWORD_PHRASE_FOLLOWS_OTHER_WORDS` | "During 2025, the Group defended litigation, regulatory proceedings and fines." |
| no registrant acting ("we", "the" or "our" + company/firm/corporation/registrant) before the keyword in its item | `GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT` | #28's sentence |
| where the registrant is named before the keyword, the series hangs on a preposition, "including" or "such as" before its first member, not one that opens the sentence; the series is found by walking across plain items, and an item naming the registrant acting is not one | `REGISTRANT_NAMED_AND_NO_GOVERNOR_PROVEN` | "In our business, regulatory matters, litigation and fines increased." |
| and the nearest subject or object reference to the registrant before that governor is not the registrant acting in the same clause; "us" is the registrant acted on, a possessive ("our partners") is neither, and a relative or subordinating word between actor and governor separates them | `GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT` | "In 2025, our company was hit with regulatory proceedings, litigation and fines."; "Costs of compliance rose, and our company defended regulatory proceedings, litigation and fines."; "Our company, with our partners, was hit by regulatory proceedings, litigation and fines." |
| an example ("such as litigation") or parenthetical example is asked the same of the text before its marker, including the sentence before the parenthetical | `GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT` | "Our company has matters such as litigation, fines and penalties."; "Our company has several matters (including litigation, fines and penalties) in Europe." |
| facing a legal matter is a relation that states one (exposure `REGISTRANT_FACES_A_LEGAL_MATTER`) | (keeps the paragraph) | "Kestrel faced regulatory proceedings, litigation and fines." |

The governor test is what keeps the adviser-cost lists out: "We engage outside counsel to advise us on finance, regulatory, litigation and other matters." names the registrant, but the series hangs on "on" and the nearest reference before it is "us", the one advised. In "We are subject to risks that may cause results to differ, such as competition, litigation, ..." the registrant acts, but "that" opens another clause before "such as".

## Measured (`compare.py` → `compare.json`, zero calls)

Version 2 is the committed `54eb39d4` module with its own terms file; version 3 is this tree.

| Set | What it is | Version 2 | Version 3 |
|---|---|---|---|
| Judged Item 8 keyword blocks (174: older-year readings and round 1e1ef948's fresh readings, taken and skipped) | readings | 28 non-disclosures and 7 correctly skipped out, 0 disclosures out | the same, block for block |
| #28's sentence and two controls (3 that state a matter) | the reported defect | 1 left out | 0 |
| Constructed beside version 3 (11 that state a matter / 3 adviser lists) | design material | 8 / 3 left out | 0 / 3 |
| Constructed beside version 2 (26 / 6) | design material | 1 / 6 | 1 / 6 |
| First independent battery (40 / 25) | design material since version 2 | 0 / 8 | 0 / 5 |
| Second independent battery (40 / 25), `independent-battery-2.json` | held out for version 3 as drafted | 1 / 4 | 0 / 3 |
| Every saved annual report (64; Hilton's does not build) | all 158 Item 8 keyword admissions | 28 left out | the same 28; none moves |

The second battery was written by a fresh agent that saw only the rule's purpose. It was run once against version 2 and the draft before its paragraphs were read. Four changes were made after that run, each from a constructed sentence and none from the battery: the parenthetical example's reading of the sentence before it, the sentence-opening preposition, running version 2's decision first, and passing over a possessive. The battery's counts are the same on the committed version 3.

The stated matter version 2 left out of it: "During 2025, the Bank was hit with regulatory investigations, two putative class-action lawsuits and civil money penalties arising from its overdraft fee practices." Version 3 keeps it by the first condition ("two putative class-action" before the keyword), not by its registrant vocabulary, which does not know "the Bank".

Tests: `tests/vnext/test_d02_item_8_category_mentions.py` (`TheRegistrantsOwnSeriesTest`, one case per condition above and the two sentences version 2 keeps that the first version 3 did not; the held counts of both batteries). Injections: `injections.json`, 28, each caught by the case written for it (run in a worktree of `1672097b` that nothing else read). Version 2's check that the registrant heads the keyword's item is not injected: version 3's wider check of the same words makes it, so taking it away changes no answer.

## What it costs and what it does not do

- No saved filing moves. Every proposal that records left-out blocks also records the terms hash, so Lumen FY2022-FY2025, Pfizer FY2021-FY2025, Paramount FY2025 and JPMorgan FY2021-FY2025 get new candidate hashes and new result ids with the same excerpts. Accepted values stay accepted only for the results they name; the recomputed results need their own run, reading check and releases.
- It leaves out fewer constructed category mentions: 3 of the first battery's (an adviser list governed by the registrant engaging advisers; "indemnify the Corporation", where the registrant is the object but the vocabulary cannot tell object from subject; "an adverse outcome of litigation", where the words before the keyword are not a determiner) and 1 of the second battery's ("third-party legal claims"). These stay in D02's set as candidates, the direction the review asked for.
- A registrant named by its own name in the middle of a series, with a verb other than "face", is still read as a list ("Kestrel defended regulatory proceedings, litigation and fines."). A series that is the subject of an open-class verb is too ("In 2025, litigation, fines and penalties increased."), as in version 2.
- It removes only one kind of wrong admission. The keyword proxy still decides which Item 8 blocks are candidates.
- Both batteries were written by models of the executor's family. They are constructed stress tests, not readings of filings.

## For #28

Pin the commit that carries this README: `scripts/vnext/d02_item_8_category_mentions.py` and `catalog/r6/D02_item_8_category_mention_v3.json`. The interface is unchanged (`left_out_as_category_mention(*, text, keyword)`, `classify(...)`). Version 2's why codes are returned as before wherever version 2 reads no category; where it reads one, `classify` may now return `KEYWORD_PHRASE_FOLLOWS_OTHER_WORDS`, `REGISTRANT_NAMED_AND_NO_GOVERNOR_PROVEN` or `GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT`, all non-category. The terms keep version 2's `category_mention` keys and patterns unchanged and add `registrant_actor` and `head_determiner`; the exposure list adds `REGISTRANT_FACES_A_LEGAL_MATTER`. The module reads the clause starters' words anywhere from version 2's anchored pattern, and refuses a terms file whose `clause_starter` does not open with that anchor. On your four checked blocks: Lumen 1670, Pfizer 2175/2240 and Paramount 2257 still leave, Paramount 2108 stays (the census and `tests/vnext/test_historical_d02_category_route.py`).
