# Read-only company source planning: selected registry context

On actual main b529ab91, changing only Pfizer's display name in an isolated source package blocks an unchanged Marriott task in both report-end and issuer fiscal-range planners. `before.log` records the two actual exceptions. The ordinary update controller already compares selected company rows (main PR155); this fixes the remaining source-planner mismatch without changing registry policy, financial extraction, metrics or paid execution.

Both planners use the existing `ordinary_registry_scope.registered_company_row` on program and source registries, and compare all fields of the selected company. The helper still reads and validates the complete CSV: duplicate company identities, duplicate field names, missing cells, empty identities, nonpositive/nonnumeric CIKs and missing selected company remain errors. Target CIK, roles, industry, fiscal-year end, period policy, continuity and related registrants remain comparison inputs. No shared helper is rewritten. The issuer-range wrapper declares the actual additional helper dependency. Its process-local complete-registry refresh hash remains as a safe rediscovery key; it is not a financial-result reuse key.

The first tests expose the production bug. Subsequent test-only corrections preserved the existing duplicate-row exception type, replaced an unsuitable non-path program overlay with a real isolated policy directory, and excluded the CLI's measured elapsed time from plan equality. Those initial logs remain. No production exception was suppressed and no computation/source selection was replaced.

Final required command (from this checkout):

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_selected_source_requirements tests.vnext.test_company_fiscal_range tests.vnext.test_selected_historical_fiscal_label tests.vnext.test_registry_processing_scope tests.vnext.test_company_current_records
```

91 tests / 10.627 seconds / zero failures, errors and skips (`required-controls.log`). These include both planners' source/program unrelated-row controls, selected-row and malformed-registry rejection, existing update configuration controls, and actual saved Marriott company CSV/reentry/independent-reading checks. Tests do not establish all 39 metrics or new business acceptance.

`verify_saved_sources.py` runs the formal `tools/vnext_company.py sources` entrance on real, already verified Southwest FY2025 saved originals. Only the program registry and matching policy file are copied into a temporary test input; source files, authentic request-log/proof checks, annual/metadata selection and fiscal resolver remain real. Sockets and Calculator are forbidden. Original and unrelated-Pfizer program registries give equal complete plans (except measured elapsed time): report-end `SAVED_SOURCE_BYTES_AVAILABLE`, 1.270/1.279 seconds; FY2025 `FISCAL_RANGE_RESOLVED`, 3.783/3.748 seconds. Request log, its manifest and source registry hashes remain unchanged. Full args/roots/source records in `saved-source-cli.json`; output in its log. The source root is read only; no new Result or output financial value is claimed.

This successor is based directly on main b529ab91, independent of PR168. It does not enable B03 acquisition or online execution; existing B01/B02 public source scope is retained. PR168's B03 source expansion and existing historical consumer evidence are reused as separate candidates, not copied into this patch. Its actual five workflows at 3745c83b were read as SUCCESS; that success is not this successor's CI.

`tested-tree.json` records actual uncommitted code/test bytes and roots. A subsequent commit must match those bytes; publication record relates local commit/tree to the public commit, without claiming these tests ran retrospectively on a differently authored public SHA. No new SEC/provider/paid calls, source/run/result/ledger rewrites, receiver merge/Ready or production actions.
