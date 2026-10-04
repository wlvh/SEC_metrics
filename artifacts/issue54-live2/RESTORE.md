# Issue #54 live2 materials (Marriott FY2025, 2026-10-04)

Persistent copies of a fresh live task created in a Claude Code cloud container. This branch is
storage only: no PR, not part of PR55. Evidence/explanation: PR55 branch
`task/sec-company-compute`, `docs/evidence/issue54_company/live2/README.md`.

## Files

| File | Use |
|---|---|
| `marriott-fy2025-company-compute-package.tar.xz` | Minimal computation handoff: `company-source/` (source-only package from the repeat run, checkpoint `sha256:e94a80466696083a88942187a7849e356e869e73ff68291d29182c0755679805`, full 38-metric scope; the later partial-reentry package `48a641a1` covers only B01/C01/D04 and is kept only inside the task-state archive), `trust-company/` (its independent admission record `e94a8046....json`), `d04-original-source[-trust]/` (admitted original baseline SEC version for the saved D04 judgment), `processing.json.as-run`, `outputs/` of the three runs. |
| `marriott-fy2025-task-state.tar.xz` | Full task restore: the whole task work dir except `result-exports/` (re-creatable with `export-results`): `acquisition/` (ledger root, 31 call records, originals + headers, claims, binding), `trust/` (acquisition + company), `programs/` (fixed installed program trees), `company-state/` (stable source, versions, 36 native Runs, journals), `handoffs/`, `local-company.json`, `processing.json`. |
| `work-integrity-manifest.json.xz` | SHA-256 and size of all 128,009 files of the work dir before packing (includes `result-exports/`). |
| `SHA256SUMS` | Archive checksums. |

## Restore

```sh
sha256sum -c SHA256SUMS
# Continue the same acquisition history / read results: the task binds absolute paths.
mkdir -p /home/user/work/live2/work && tar -xJf marriott-fy2025-task-state.tar.xz -C /home/user/work/live2/work
# Verify bytes against the manifest (result-exports/ entries are expected to be absent).
# Re-create cold exports without SEC: tools/vnext_company.py export-results ... (see PR55 docs/company_local_run.md)
```

If the original absolute path cannot be used, record the remount explicitly; do not re-sign Runs,
rebuild the ledger identity or regenerate trust records. The task allowance is fixed at 89 GETs for
this task (31 used; with the original 31 the cumulative count is 62/120).

The saved D04 processing packet/program/trust are not repacked here: rebuild them from Git commit
`7ed952bb` with `docs/evidence/issue28_foundation_integration_20261004/materialize-d04-handoff.py`.
`processing.json` refers to the run host's absolute paths for those inputs.

No tokens, keys or private credentials are included. The SEC User-Agent in the ledger is the
project's configured value.

## Dependencies and disk space (logical bytes, measured)

| Archive | Download | Expanded | Additional to compute/export |
|---|---:|---:|---:|
| company-compute-package | 5.5 MB | 50 MB | fixed program tree about 39 MB; company-state after all 38 metrics about 1.85 GB; each full cold export about 1.7 GB (B01+D01 only: 129 MB state + 93 MB export) |
| task-state | 14.0 MB | 2.2 GB | re-creating the three run exports about 5.0 GB |

The compute package does not contain the program. Install it from the PR55 checkout (product code
`83db2c02`) with `python3 tools/vnext_company.py install-runtime --kind local --output-root <rt>`
(expected authority `sha256:792b50955674f1a1a007f2a1b5f55b7520d5ad4f5b7973e7b102c9e7278aa251`), plus
`python -m pip install --no-deps --require-hashes -r requirements-continuous-context.txt` for the saved
D04 path. A runtime built on a different foundation (e.g. PR56 `9d1ece07`, authority `da36e061...`)
rejects this package with `COMPANY_HANDOFF_RULE_VERSION_CHANGED`; re-export from the same source
under that runtime instead of editing the package.

The task-state archive restores the acquisition ledger, trust, programs, company-state (36 Runs),
handoffs and the two task configuration files; it does not contain `result-exports/`, the saved D04
processing packet/program/trust (Git `7ed952bb`) or the tokenizer dependency.

Record correction (2026-10-04): this file first named the partial package `48a641a1`; the archive
itself always contained `e94a8046` (verified by unpacking). Archive bytes and hashes are unchanged.
