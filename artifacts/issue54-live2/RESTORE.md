# Issue #54 live2 materials (Marriott FY2025, 2026-10-04)

Persistent copies of a fresh live task created in a Claude Code cloud container. This branch is
storage only: no PR, not part of PR55. Evidence/explanation: PR55 branch
`task/sec-company-compute`, `docs/evidence/issue54_company/live2/README.md`.

## Files

| File | Use |
|---|---|
| `marriott-fy2025-company-compute-package.tar.xz` | Minimal computation handoff: `company-source/` (source-only package, checkpoint `sha256:48a641a1...`), `trust-company/` (its independent admission record), `d04-original-source[-trust]/` (admitted original baseline SEC version for the saved D04 judgment), `processing.json.as-run`, `outputs/` of the three runs. |
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
