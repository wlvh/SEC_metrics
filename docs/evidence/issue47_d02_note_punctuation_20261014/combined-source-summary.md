# D02 preparation comparison

- baseline: `17569516a8be63002f0a6336041421ac14d33459` = `17569516a8be63002f0a6336041421ac14d33459`
- candidate: `HEAD` = `840f7a9d9141fb796c695e4642d9fbe4a6305360`
- source root: `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`: 4505 files, 1148630267 bytes, `sha256:a1975d771d350efb537f036dd0d24c19b86d475a3594520d38db7bd9e4ce2fb7`; unchanged during run: True
- scope: 10 companies x fiscal years 2021-2025 = 50 samples (whole baseline registry)
- environment: Python 3.14.7, macOS-27.0.1-arm64-arm-64bit-Mach-O, network blocked in workers, 4 workers
- result: COMPLETE
- verified identical: 29; content changed: 0; status changed: 14; failing on both sides (unverified): 7; not compared: 0

| category | samples |
|---|---|
| SAME_OK | 29 |
| CHANGED_OK | 0 |
| FAIL_TO_OK | 14 |
| OK_TO_FAIL | 0 |
| SAME_FAIL | 6 |
| CHANGED_FAIL | 1 |
| NOT_COMPARED | 0 |

## Failed before, prepared now (14)
- `marriott_international:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `southwest_airlines:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `ford_motor_company:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `pfizer:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `pfizer:2022`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate OK
- `pfizer:2023`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate OK
- `pfizer:2025`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate OK
- `jpmorgan_chase:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `salesforce:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `salesforce:2022`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `lumen_technologies:2024`: baseline ERROR D02_REVIEW_CANDIDATES_OUTSIDE_ELIGIBLE_POOL / candidate OK
- `macys:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `paramount_skydance_paramount_global:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK
- `enphase_energy:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate OK

## Fails on both sides for different reasons (1)
- `lumen_technologies:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE

## Fails the same way on both sides: not verified by this comparison (6)
- `southwest_airlines:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `pfizer:2024`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `lumen_technologies:2022`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `lumen_technologies:2023`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `paramount_skydance_paramount_global:2024`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `paramount_skydance_paramount_global:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED

29 samples were prepared with identical compared content on both sides.
