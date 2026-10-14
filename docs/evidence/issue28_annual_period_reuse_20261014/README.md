# Reuse exact annual-period parsing inside one company operation

The company entry already shares XBRL parsing, but each consumer still scans
the same HTML again to read DEI metadata and establish the annual interval.
The actual Marriott B04/B07 operation reached `annual_period` three times.
This change shares only a successfully checked period inside that operation.
Source selection, source admission, latest-source observations, calculation,
and saved-result validity keep their existing checks.

## Execution and scope

Tested code root: `/Users/lyuhongwang/.codex/worktrees/record-dispatch/SEC_metrics`.
Base: actual main `190e2f9011d264c5d6527e2bb59efd6b1b9aa3c5`.
Execution used that base plus the two named uncommitted production changes in
`summary.json`; it is not retrospectively described as execution of the later
commit. Their executed file hashes are recorded there.

The key includes exact source SHA/size, CIK, selected filing identity/date/form,
and the DEI parser option. Stored periods are immutable tuples; each caller
gets a fresh dictionary. Only successful parsing is stored. The operation has
a 16-entry bound, resets on exception or normal exit, and does not create a
cross-operation cache. Standalone calls retain the existing behavior.
The existing company entry opens this context beside its source-parse context
and company lock; no default interface or result format changes.

## Actual saved-source company entry

Original source root:
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs`.
Private scripts, profiler data and independent task states:
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/annual-prepare-profile-20261014`.
No source archive or profiler binary is added to Git.

```bash
python3.12 tools/vnext_company.py run \
  --company marriott_international \
  --source-root /path/to/read-only-saved-source \
  --metric B04 --metric B07 \
  --work-dir /path/to/empty-task --output-dir /path/to/output
python3.12 tools/vnext_company.py results \
  --company marriott_international --state-root /path/to/empty-task \
  --output-root /path/to/independent-read
```

Both runs use real selection, preparation, calculation, saving and export;
network/DNS and ledger claims are forbidden. The first runs use independent
empty task roots. Reentry makes the preparation/calculation factory raise on
call; independent process reading makes the updater raise on call.

| Observation | Before | After |
|---|---:|---:|
| `annual_period` calls | 3 | 3 |
| Actual DEI metadata scans | 3 | 1 |
| Original source-proof checks | 9 | 9 |
| Profiled full operation | 4.743342 s | 4.518286 s |
| `annual_period` cumulative time | 1.097855 s | 0.683275 s |

This is one profiler observation with overhead, not a demonstrated percentage
speedup. The verified reduction is two duplicate metadata scans; source-proof
checks have not been removed. The same two native Result IDs survive:
B04 = 2,601,000,000 USD; B07 = 5.118665018541409147095179234 ratio.
Both retain CIK1048286, FY2025, 2025-01-01 through 2025-12-31,
accession0001048286-26-000007 and their original source references.
Forbidden-factory repeat took 0.115681 s, independent reading 0.129628 s;
14 saved result files remain unchanged. See `metrics_matrix.csv`.

## Regression coverage

`before-regression.log` reproduces two scans for the same operation on the
old implementation. At that point the test used an empty context fallback to
exercise old behavior; the committed test calls the real context directly.

```bash
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py \
  tests.vnext.test_annual_period_reuse \
  tests.vnext.test_normal_annual_input_v2 \
  tests.vnext.test_current_statement_metric_case \
  tests.vnext.test_company_current_records
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py \
  tests.vnext.test_annual_period_reuse tests.test_selector_registry
```

64 controls in 22.568 s; 13 selector/small-parse controls in 0.015 s. Both
have zero failures, errors and skips. Controls cover changed source bytes,
entity, period, form, namespace, parser option and filing, unsuccessful checks,
mutable caller results, separate operations and exceptional exit. Existing
company controls retain mixed success/withheld isolation and saved reading.
The additive selector registers only this small module; runner bodies are
unchanged. Other large source chains are not rerun.

New real provider/paid/SEC calls: 0/0/0. The original 195-claim ledger hash is
unchanged. This is parsing reuse and current company integration; it grants
no new model, full-company semantic acceptance or production permission.
