# D02 preparation comparison

- baseline: `681b35d865af9660ad03ffbbb20ec93cd499d9cd` = `681b35d865af9660ad03ffbbb20ec93cd499d9cd`
- candidate: `77b0f2fdc3d9c32905e9d00db8ed03f0407032af` = `77b0f2fdc3d9c32905e9d00db8ed03f0407032af`
- source root: `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`: 4505 files, 1148630267 bytes, `sha256:a1975d771d350efb537f036dd0d24c19b86d475a3594520d38db7bd9e4ce2fb7`; unchanged during run: True
- scope: 10 companies x fiscal years 2021-2025 = 50 samples (whole baseline registry)
- environment: Python 3.14.7, macOS-27.0.1-arm64-arm-64bit-Mach-O, network blocked in workers, 4 workers
- result: COMPLETE
- verified identical: 39; content changed: 0; status changed: 0; failing on both sides (unverified): 11; not compared: 0

| category | samples |
|---|---|
| SAME_OK | 39 |
| CHANGED_OK | 0 |
| FAIL_TO_OK | 0 |
| OK_TO_FAIL | 0 |
| SAME_FAIL | 11 |
| CHANGED_FAIL | 0 |
| NOT_COMPARED | 0 |

## Fails the same way on both sides: not verified by this comparison (11)
- `southwest_airlines:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `pfizer:2021`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `pfizer:2022`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `pfizer:2023`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `pfizer:2024`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `pfizer:2025`: baseline ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED / candidate ERROR D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED
- `lumen_technologies:2021`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `lumen_technologies:2022`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `lumen_technologies:2023`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE
- `paramount_skydance_paramount_global:2024`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `paramount_skydance_paramount_global:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED

39 samples were prepared with identical compared content on both sides.
