# D02 preparation comparison

- baseline: `81159dd4c182eb76e96d4eab58d37296b25a41d7` = `81159dd4c182eb76e96d4eab58d37296b25a41d7`
- candidate: `59c14aafc69417ec77a3f2500cddd15ac9116d56` = `59c14aafc69417ec77a3f2500cddd15ac9116d56`
- source root: `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`: 4505 files, 1148630267 bytes, `sha256:a1975d771d350efb537f036dd0d24c19b86d475a3594520d38db7bd9e4ce2fb7`; unchanged during run: True
- scope: 1 companies x fiscal years 2021-2023 = 3 samples (SUBSET of the baseline registry)
- environment: Python 3.14.7, macOS-27.0.1-arm64-arm-64bit-Mach-O, network blocked in workers, 4 workers
- result: COMPLETE
- verified identical: 2; content changed: 0; status changed: 0; failing on both sides (unverified): 1; not compared: 0

| category | samples |
|---|---|
| SAME_OK | 2 |
| CHANGED_OK | 0 |
| FAIL_TO_OK | 0 |
| OK_TO_FAIL | 0 |
| SAME_FAIL | 1 |
| CHANGED_FAIL | 0 |
| NOT_COMPARED | 0 |

## Fails the same way on both sides: not verified by this comparison (1)
- `lumen_technologies:2021`: baseline ERROR D02_INCORPORATED_CAPTION_NOT_FOUND / candidate ERROR D02_INCORPORATED_CAPTION_NOT_FOUND

2 samples were prepared with identical compared content on both sides.
