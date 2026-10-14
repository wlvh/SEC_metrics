# D02 preparation comparison

- baseline: `840f7a9d9141fb796c695e4642d9fbe4a6305360` = `840f7a9d9141fb796c695e4642d9fbe4a6305360`
- candidate: `29718155d5c88ba3c0b1b3b8ebb4cc8414ac4008` = `29718155d5c88ba3c0b1b3b8ebb4cc8414ac4008`
- source root: `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`: 4505 files, 1148630267 bytes, `sha256:a1975d771d350efb537f036dd0d24c19b86d475a3594520d38db7bd9e4ce2fb7`; unchanged during run: True
- scope: 1 companies x fiscal years 2021-2024 = 4 samples (SUBSET of the baseline registry)
- environment: Python 3.14.7, macOS-27.0.1-arm64-arm-64bit-Mach-O, network blocked in workers, 3 workers
- result: COMPLETE
- verified identical: 1; content changed: 0; status changed: 2; failing on both sides (unverified): 1; not compared: 0

| category | samples |
|---|---|
| SAME_OK | 1 |
| CHANGED_OK | 0 |
| FAIL_TO_OK | 2 |
| OK_TO_FAIL | 0 |
| SAME_FAIL | 0 |
| CHANGED_FAIL | 1 |
| NOT_COMPARED | 0 |

## Failed before, prepared now (2)
- `lumen_technologies:2022`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate OK
- `lumen_technologies:2023`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate OK

## Fails on both sides for different reasons (1)
- `lumen_technologies:2021`: baseline ERROR TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE / candidate ERROR D02_INCORPORATED_CAPTION_NOT_FOUND

1 samples were prepared with identical compared content on both sides.
