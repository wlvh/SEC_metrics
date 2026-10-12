# Ordinary five-year source export through the public company entry

Progress on #28; shared with #47. Responds to the actual CLI failure reported in comment [6127399920](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-6127399920).

The initial code/test root is `/Users/lyuhongwang/.codex/worktrees/issue28-current-c04-failure-detail/SEC_metrics`, branch `task/issue28-history-export-entry`, from actual main `df11e1b0`. Main then advanced to `8876b2e0`; composition is checked separately below. Tests were executed on the stated working-tree edits, then committed; commit identity is supplied in the PR, not retroactively claimed as the test start SHA.

## What works and what stays separate

`export --history-years 5 --metric B01` previously raised a missing `historical_source_acquisition` import before the exporter. It would also have selected an absent `issue_47_v1` snapshot. The new explicit history branch reuses the received `company_fiscal_range`, `selected_source_requirements`, issuer-label reader and `saved_source_checks`. `company_history_export.py` is a small source declaration; the existing fiscal-range processing module is byte-for-byte unchanged, so export-only work does not change its processing version.

Only explicit B01/B02/B03 source scope is connected. The latest original's issuer label determines the five-year window; financial dates are not renamed as fiscal labels. Every task's originals, amendment/index/instance dependencies and all candidate label inputs are retained, including an older original needed for selection even when B01 does not consume its amounts. Missing/failed sources or unresolved labels return `SOURCE_EXPORT_INCOMPLETE`, exit 2, and publish no package.

A completed `COMPANY_SAVED_SOURCE_PACKAGE_V1` is consumed by the existing ordinary `run --source-root`, not old native `install/compute`. It retains the original mixed-company request log/manifest and registry bytes without cutting rows, renumbering or minting allowance; only selected source bodies and headers are copied. No program, AI answer, old Result or creator journal is hidden in the package. The legacy no-history exporter, its optional Python declaration callback and old install/recovery paths retain their defaults. `--trust-root` is required for that legacy branch; it is not needed or written by this new ordinary branch.

Copying stages to a new directory, checks actual bytes/proofs and re-reads the complete selection before atomic publication. It refuses existing outputs. Ordinary company locking/state and paid-call controls are unchanged.

## Actually executed evidence

- `before-entry.log`: the two initial controls reproduce the missing-module error.
- `after-entry.log`: initial full legacy-test invocation hit macOS `/var` alias restrictions; that is an environment setup failure, not retired business checks. Subsequent legacy tests use `TMPDIR=/private/tmp`.
- `after-small.log`, `final-export-only.log`: actual small captured sources through public export, package re-read, missing instance, current HTTP503 after success, existing-output protection; no exporter/parser success mock in those cases.
- `final-targeted.log`: 111 selected tests passed in 12.202s, including existing handoff, range, source-preflight, fiscal-label and company-controller cases. `required-entry.log`: 8 new cases, 1.992s, zero errors/failures/skips. The new selector is registered at the end of the fast additions and explicitly required in the company workflow.
- `source-frame-initial-scope.json`: initial diagnostic before the copied-package check revealed the missing older label dependency. It is not the final 18-requirement package proof.
- `company-material-initial-state-assertion.log`: actual export/first/repeat had completed, but the harness incorrectly expected all state files to remain unchanged. A repeat appropriately adds a check observation. The corrected harness requires unchanged result bytes/directories and zero calculation instead; it does not remove normal observation logs.
- `company-material.log`: corrected fresh task on the existing exact package; intermediate export-helper placement still changed the fiscal-range file. `company-final-material.log`: final production placement preserves that original module and runs a new task. No old task or source was overwritten.

The real saved source is `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs` (read only). The exact exported ordinary package is `/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/history-export-marriott-20261013/package`: 51 original/ledger/registry files, 34,538,141 bytes; FY2021–2025 dependencies are resolved. Its full ledger bytes equal the original. No independent trust directory or checkpoint is created. The initial export duration was not separately saved; later checks reuse this exact package rather than repeat the copy for a timing number.

Final task state is `/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/history-export-marriott-final-consumer-20261013/task`. Formal CLI B01 FY2025 first processing: **5.050442s**; calculator entry forbidden repeat: **0.125290s**, no new result directory or changed result byte; independent `results`/CSV: **0.117860s**, state unchanged. Value **26,186,000,000 USD**, actual period **2025-01-01 through 2025-12-31**, result `sha256:e279b28db1cecf3434d84fb7455717e5f7340a7e64310d84af935c92e55288bc`, primary accession `0001048286-26-000007`, filing date 2026-02-10. Source package and paid/SEC ledger remain read-only; new business calls are **0/0/0**.

Reproducer `verify_company.py` uses the public CLI in-process, forbids sockets, and reads results in an independent process. The optional `--package-root` reuses the exact saved export. It never mocks source selection, installation, calculation or output as successful.

## Portable commands and limits

```bash
TMPDIR=/private/tmp python3 -m unittest tests.vnext.test_history_source_export \
  tests.vnext.test_company_handoff tests.vnext.test_company_fiscal_range \
  tests.vnext.test_selected_source_requirements tests.vnext.test_selected_historical_fiscal_label \
  tests.vnext.test_company_current_records
python3 tools/vnext_company.py export --company marriott_international \
  --source-root /absolute/saved-full-source --output-root /absolute/new-company-source \
  --metric B01 --history-years 5
python3 tools/vnext_company.py run --company marriott_international \
  --source-root /absolute/new-company-source --work-dir /absolute/new-company-state \
  --output-dir /absolute/new-output --metric B01 --period fiscal-years \
  --fiscal-year-start 2025 --fiscal-year-end 2025
python3 tools/vnext_company.py results --company marriott_international \
  --state-root /absolute/new-company-state --output-root /absolute/new-read
```

The placeholder directories must be real saved inputs and new external output directories. Five-year source readiness is not acceptance of five-year results. Only B01 FY2025 is calculated in this real-source proof; B02/B03 source scopes and other companies need their own affected acceptance. No new online acquisition, AI validation, full390 acceptance, production adoption or cluster deployment is claimed. Saved native tasks retain their creator program and original admission; this patch does not convert them or restore retired trust systems to new ordinary tasks.

## Actual main composition

Local `26ad1c01` records the first tested change. Normal merge of the actually read `8876b2e06c509ccc4e39df5e9675cc7dd097a221` creates `28acbe89ee70735dbf4b44d2e234d8b0ac1567f1`, tree `3942cc2352272ed1b44b072867394e6806262ed0`; no conflict or discarded upstream change. This receives the already accepted 199/203/204 through main, not a historical branch. `combination-targeted.log`: 139 selected controls, 12.247s, zero failure/error/skip. `combination-company.log`: a fresh FY2025 B01 task on the same exact source package, first 5.039822s, forbidden-calculation repeat 0.125002s, independent CSV 0.118795s; same value, dates and e279 result. Existing packets/tasks remain unchanged. These executions start at actual HEAD 28ac with only resulting logs/docs uncommitted; the final evidence commit changes no production or test bytes. Remote CI and receiving remain separate gates.

## Receiving list composition

Actual feedback6130759039 and207 feedback6130757933 were read. This candidate normally receives the fixed207 A13 increment (publicd65ca72c/local5e137990) and actualmain31e4, localmerge415efbb8. Only one adjacent runner append conflicts: preserve cover, single-segment, processing guard, its source material, and history-export selectors once each; bodies/timeouts stay. Workflow merges cleanly; Ruby YAML actually parsed all sixjobs and read permission. fixed-207-combination.log:103 selected tests12.480s, zero errors/failures/skips. Old formal export/company results and receiver15-row comparison are reused by responsibility; no full financial replay or new call. This is code/list composition, not new source/business acceptance. Final evidence commit preserves production/test bytes; public head/tree and exact parents in PR reply.
