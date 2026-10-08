# Targeted round: D02 on the category rule's version 2 (closure `1e1ef948`)

## What ran

The Item 8 category-mention rule moved to version 2 at `147957c4` ([shared-with-#28], `../d02-keyword-repair/v2/`). Version 2 changes no saved frame filing's selection, but every proposal that records left-out blocks also records the rule's terms hash, so those results get new candidate hashes and new result ids. The filings with left-out blocks are Lumen FY2022-FY2025, Pfizer FY2021-FY2025 and Paramount FY2025; Lumen FY2021 stops by name before selecting (`HISTORICAL_TEXT_BOUNDARY_NAVIGATION_INCOMPLETE`, see `../d02-route-repairs/`).

The runtime tree was synced to `4044014a` plus the registration patch, which mints the closure every Run records, `sha256:1e1ef948…`. Driver `../period-batch/frame_batch.py`, 3 workers, zero provider, paid or SEC calls. `collect.py` → `rerun-results.json`: 10 positions, 10 frozen with a public row, each read back by another process with the same run and result.

Every excerpt list is the one the `66569eec` round published: the same lines and characters at every position (Lumen 27/36/43/41; Pfizer 110/113/118/106/94; Paramount 28). Only the result ids moved.

## Reading the new results, both directions

| Positions | How the reading was made | Kind of evidence |
|---|---|---|
| Lumen FY2022-FY2024, Pfizer FY2022-FY2024 | The older-year readings (`../d02-older-years/judgements/`) carried onto the recomputed packets by `tools/read_d02_excerpts.py --carry` (`../d02-older-years/carried/`). Each verdict moves with its block's text and kind; a block nobody judged stops the carry. | The route repairs and the category rule were written beside these readings, so they are regression material for those repairs, not held-out. |
| Pfizer FY2021 | A fresh reader (`judgements/pfizer-2021-12-31.json`). The carry stopped: 73 blocks of Note 16A are taken now that the note-heading repair finds the note, and the held-out reading had judged them as context. That reading stays as it was. | The note-heading repair was written beside this position's held-out reading: regression material. |
| Lumen, Pfizer, Paramount FY2025 | Fresh readers (`judgements/`), the brief verbatim plus the meaning of the scopes and of `left_out_by`. | The category rule was written beside these blocks (Lumen 1670, Pfizer 2175/2240, Paramount 2257): design and regression material. |

Every reader was a fresh same-family subagent, not a person. The four fresh readings judged every block of every list:

- Lumen FY2025: 41 taken, all disclosure; the left-out 1670 (legal fee policy) correctly skipped.
- Pfizer FY2025: 94 taken, all disclosure; 2175/2240 correctly left out; one context block (the opening of Note 16) covered by taken blocks.
- Paramount FY2025: 28 taken, all disclosure. Block 2108 (transaction-related costs whose last sentence states the $156 million stockholder-litigation benefit) the reader judged a disclosure, as the rule SPECIFIC_LEGAL_MATTER_IS_DISCLOSURE decides. The left-out 2257 (a covenant naming litigation reserves as an EBITDA add-back) correctly skipped.
- Pfizer FY2021: 110 taken, all disclosure, including the whole of Note 16A; the three left-out blocks (estimates boilerplate, collection policy, tax audits) correctly skipped.

## Acceptance (`../content-acceptance/d02-read-round-1e1ef948.json`)

`tools/read_d02_excerpts.py` recomputes each packet from the saved filing, holds the reading to it, and checks the Run: its candidate hash is the recomputed one, its published excerpts are the taken blocks in order, and the taken texts render the published value. All ten positions: `READING_AGREES`, `MATCH`. The register (`../accepted_result_content.json`, rebuilt) gains ten D02 acceptances, 845 → 855; none was removed or changed.

## Releases (`release_on_reading.py`)

Each MATCH releases the coordinate-level D02 entries at its coordinate for this result under this closure only: 13 releases, among them Lumen FY2022-FY2025's keyword-proxy entries, Pfizer FY2021's category-mention and note-heading entry, Pfizer FY2022-FY2024's keyword-proxy and page-footer entries, Pfizer FY2025's three coordinate entries and Paramount FY2025's. The exact-result entry D02_PFIZER_2025_OFFICER_SECTION is not released; it names a result, not a coordinate. Every earlier result at these coordinates stays withdrawn.

## What this does not show

The readings that accept these values are regression material for the rules that produced them; the held-out evidence for the category rule is JPMorgan's five years (`../d02-keyword-repair/`). The keyword proxy still decides which Item 8 blocks are candidates; this round shows these ten values are right, not that the proxy is.

## After this round: #28's review of rule version 2

#28's scoped review of its copy of version 2 (`79677ed2`, NEEDS_FIX P2, Issue #28 evidence `collab-d02-versioned-20261002/v2/independent-review-79677ed/`) found that version 2 leaves out "During 2025, our company faced litigation, regulatory proceedings and fines.", a sentence stating the registrant's own matter. It is a constructed sentence. The readings above judged every taken, skipped and context block of these ten filings and found no such sentence among them, so the ten values stay as read. #47 owns the shared rule and repairs it next; a later version's results get their own run, reading check and releases.
