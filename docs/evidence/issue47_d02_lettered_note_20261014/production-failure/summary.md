# D02 preparation comparison

- baseline: `a77b4ee145b7d084d13a0f62c3479807dbd987f2` = `a77b4ee145b7d084d13a0f62c3479807dbd987f2`
- candidate: `c21545ff1757b2e6568b90a2e641aaa101022a1b` = `c21545ff1757b2e6568b90a2e641aaa101022a1b`
- source root: `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`: 4505 files, 1148630267 bytes, `sha256:a1975d771d350efb537f036dd0d24c19b86d475a3594520d38db7bd9e4ce2fb7`; unchanged during run: True
- scope: 10 companies x fiscal years 2021-2025 = 50 samples (whole baseline registry)
- environment: Python 3.14.7, macOS-27.0.1-arm64-arm-64bit-Mach-O, network blocked in workers, 4 workers
- result: COMPLETE
- verified identical: 16; content changed: 0; status changed: 17; failing on both sides (unverified): 17; not compared: 0

| category | samples |
|---|---|
| SAME_OK | 16 |
| CHANGED_OK | 0 |
| FAIL_TO_OK | 14 |
| OK_TO_FAIL | 3 |
| SAME_FAIL | 17 |
| CHANGED_FAIL | 0 |
| NOT_COMPARED | 0 |

## Prepared before, fails now (3)
- `southwest_airlines:2022`: baseline OK / candidate ERROR D02_AUDITOR_REPORT_CLOSING_SCOPE_NOT_PROVEN
- `southwest_airlines:2023`: baseline OK / candidate ERROR D02_AUDITOR_REPORT_CLOSING_SCOPE_NOT_PROVEN
- `southwest_airlines:2024`: baseline OK / candidate ERROR D02_AUDITOR_REPORT_CLOSING_SCOPE_NOT_PROVEN

## Failed before, prepared now (14)
- `marriott_international:2022`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `marriott_international:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `marriott_international:2024`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `marriott_international:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `pfizer:2022`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `pfizer:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `pfizer:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `salesforce:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `salesforce:2024`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `salesforce:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `lumen_technologies:2024`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `lumen_technologies:2025`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `paramount_skydance_paramount_global:2022`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK
- `paramount_skydance_paramount_global:2023`: baseline ERROR D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED / candidate OK

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

16 samples were prepared with identical compared content on both sides.
