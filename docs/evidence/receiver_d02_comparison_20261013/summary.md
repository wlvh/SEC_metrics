# D02 preparation comparison

- baseline: `c25872ee388c933b697d9d3a9764e5eb7d1859e3` = `c25872ee388c933b697d9d3a9764e5eb7d1859e3`
- candidate: `9934615fdb92025288fb07567077ef995d58467c` = `9934615fdb92025288fb07567077ef995d58467c`
- source root: `/home/user/acc/hist-src/source-inputs`: 4505 files, 1148630267 bytes, `sha256:a1975d771d350efb537f036dd0d24c19b86d475a3594520d38db7bd9e4ce2fb7`; unchanged during run: True
- scope: 10 companies x fiscal years 2021-2025 = 50 samples (whole baseline registry)
- environment: Python 3.13.16, Linux-6.18.44-fc-v114-x86_64-with-glibc2.39, network blocked in workers, 4 workers
- result: COMPLETE
- verified identical: 19; content changed: 0; status changed: 10; failing on both sides (unverified): 21; not compared: 0

| category | samples |
|---|---|
| SAME_OK | 19 |
| CHANGED_OK | 0 |
| FAIL_TO_OK | 10 |
| OK_TO_FAIL | 0 |
| SAME_FAIL | 17 |
| CHANGED_FAIL | 4 |
| NOT_COMPARED | 0 |

## Failed before, prepared now (10)
- `marriott_international:2022`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `marriott_international:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `marriott_international:2024`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `marriott_international:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `salesforce:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `salesforce:2024`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `salesforce:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `lumen_technologies:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `paramount_skydance_paramount_global:2022`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `paramount_skydance_paramount_global:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK

## Fails on both sides for different reasons (4)
- `pfizer:2022`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `pfizer:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `pfizer:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `lumen_technologies:2024`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate ERROR D02_REVIEW_CANDIDATES_OUTSIDE_ELIGIBLE_POOL

## Fails the same way on both sides: not verified by this comparison (17)
- `marriott_international:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `southwest_airlines:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `southwest_airlines:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `ford_motor_company:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `pfizer:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `pfizer:2024`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `jpmorgan_chase:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `salesforce:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `salesforce:2022`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `lumen_technologies:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `lumen_technologies:2022`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `lumen_technologies:2023`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `macys:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `paramount_skydance_paramount_global:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING
- `paramount_skydance_paramount_global:2024`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `paramount_skydance_paramount_global:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `enphase_energy:2021`: baseline ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING / candidate ERROR TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING

19 samples were prepared with identical compared content on both sides.
