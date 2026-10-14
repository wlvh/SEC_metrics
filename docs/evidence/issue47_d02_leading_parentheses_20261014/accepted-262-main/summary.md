# D02 preparation comparison

- baseline: `ccd9d7c2721e2f8c2116d0ca784178b96571e21f` = `ccd9d7c2721e2f8c2116d0ca784178b96571e21f`
- candidate: `81159dd4c182eb76e96d4eab58d37296b25a41d7` = `81159dd4c182eb76e96d4eab58d37296b25a41d7`
- source root: `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`: 4505 files, 1148630267 bytes, `sha256:a1975d771d350efb537f036dd0d24c19b86d475a3594520d38db7bd9e4ce2fb7`; unchanged during run: True
- scope: 10 companies x fiscal years 2021-2025 = 50 samples (whole baseline registry)
- environment: Python 3.14.7, macOS-27.0.1-arm64-arm-64bit-Mach-O, network blocked in workers, 4 workers
- result: COMPLETE
- verified identical: 44; content changed: 0; status changed: 2; failing on both sides (unverified): 4; not compared: 0

| category | samples |
|---|---|
| SAME_OK | 44 |
| CHANGED_OK | 0 |
| FAIL_TO_OK | 2 |
| OK_TO_FAIL | 0 |
| SAME_FAIL | 3 |
| CHANGED_FAIL | 1 |
| NOT_COMPARED | 0 |

## Failed before, prepared now (2)
- `lumen_technologies:2022`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate OK
- `lumen_technologies:2023`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate OK

## Fails on both sides for different reasons (1)
- `lumen_technologies:2021`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR D02_INCORPORATED_CAPTION_NOT_FOUND

## Fails the same way on both sides: not verified by this comparison (3)
- `southwest_airlines:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `paramount_skydance_paramount_global:2024`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED
- `paramount_skydance_paramount_global:2025`: baseline ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED / candidate ERROR D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED

44 samples were prepared with identical compared content on both sides.
