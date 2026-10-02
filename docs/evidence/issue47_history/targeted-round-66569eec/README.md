# Targeted round: D02 after the navigation, statement-range and facing-page repairs (closure `66569eec`)

## What ran

The runtime tree was synced to `ebac1015` plus the registration patch. That commit mints the closure every Run records, `sha256:66569eec…`; this was re-minted in a separate worktree, not inferred. Driver: `period-batch/frame_batch.py`, 3 workers, zero provider, paid or SEC calls.

| Periods | Metrics | Why |
|---|---|---|
| JPMorgan FY2021–FY2025 | D02 (and A01/A02 for FY2021) | statements printed after a pointer Item 8 now start at the statements (`8c55b601`); page numbers on facing pages (`e76e2953`); FY2021 A01/A02 under the dated FASB release reading |
| Pfizer FY2021–FY2025 | D02 | Note 17's split-emphasis heading (`8c55b601`); facing pages |
| Lumen FY2021–FY2025, Paramount FY2025 | D02 | the Item 8 category-mention rule version 1 (`36c64ab6`) on the frame |
| Salesforce FY2022 | B12 | the dated FASB release reading |

This is not a full frame.

## Results (`rerun-results.json`, collected by `collect.py`)

19 positions; 18 frozen with a public row, each read back by another process with the same run and result; one stop by name.

- Lumen FY2021 D02 stops as `HISTORICAL_TEXT_BOUNDARY_NAVIGATION_INCOMPLETE: UNRESOLVED_INCORPORATED_CAPTION_NOTE_18`. This is the deliberate stop of `d02-route-repairs`: Item 3 limits Note 18 by a caption the note does not carry, so the whole note is not taken.
- JPMorgan FY2021 A01 0.15 and A02 0.131; Salesforce FY2022 B12 43,700,000,000.
- D02 excerpt counts: JPMorgan 38/39/44/39/36; Pfizer 110/113/118/106/94; Lumen FY2022–FY2025 27/36/43/41; Paramount FY2025 28.

## What this closure is for

The Item 8 category rule moved to version 2 at `147957c4` (`../d02-keyword-repair/v2/`). Version 2 changes no saved frame filing's selection. It does change the candidate hash of every filing whose proposal records left-out blocks, because the proposal records the rule's terms hash. Those filings are Lumen FY2021–FY2025, Pfizer FY2021–FY2025 and Paramount FY2025. Their D02 results here are therefore read and accepted only after a rerun on the version 2 closure. JPMorgan's proposals record no left-out block, so its D02 results here are the ones the current tree reproduces.
