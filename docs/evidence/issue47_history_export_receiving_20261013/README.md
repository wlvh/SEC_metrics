# Ordinary source export consumed by an actual historical B02

This is historical-side reception of public PR208, not another exporter. It
combines PR208 `2241e209`, PR207 `8ef2c503`, the received historical D01
declaration (PR204), and the received historical paired-revenue consumer
(PR206). Actual first execution is `73bce1ff2dce73e52a580391272fb5f533a6615a`.
Actual main `31e4a00d14570b6e7128084e23e6628af3f22c3f` was then normally merged
as `e72d76159d6cd1ffee296c37d27ca1fa22b7160c`; that merge changes no production, test or source bytes.
The published branch is `task/issue47-history-export-receiving-20261013`.

## What actually ran

The original source root was read only:
`/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`.
Its bytes can be recovered from the retained PR52 export; use the actual
`source-inputs` root returned by the existing restore command. No original
source, old task, model response or request count was modified.

Formal `export --company marriott_international --metric B02 --history-years 5`
created a new ordinary package: **61 files**, source requirements for
**FY2021–2025**, **29.252256s**. Every copied source/header/ledger/registry file
matches its saved original; the complete mixed request ledger is unchanged.
No new trust journal, AI answer, Result or invocation permission is included.

The same public company CLI then ran B02 FY2023 from that package and an empty
new state, taking **10.812842s**. It selected the two years' own originals:
FY2023 accession **0001628280-24-004372**, **23,713,000,000 USD**; prior FY2022
accession **0001628280-23-003485**, **20,773,000,000 USD**. Both complete original
statement scopes and their native claims are retained here. The calculated
value is **0.1415298705049824291147162182 ratio**, actual period
**2023-01-01–2023-12-31**, result **aae9df4d…**. This does not substitute a later
comparative amount for the selected prior filing.

A repeat with historical factories, the paired scope reader and both numeric
Calculator entry points forbidden took **0.293263s**: no calculation, no new
Result directory, all **7 Result files** unchanged. The ordinary check log may
append its new observation. A separate process read `results` and exported the
complete CSV/evidence in **0.184707s**, leaving **18 state files** unchanged.
The independent reader does not assert that unchanged old data proves a fresh
calculation; the first phase above uses genuinely empty state.

`controls.log`: **48 tests**, **4.459s**, zero failures/errors/skips, including
the actual public export, missing source, failed latest HTTP response,
no-overwrite, interrupted-copy and issuer-label controls. No full company
census, two-year B01 replay, prior original reading or model batch was repeated.

## Reproduce on this code combination

Use an installed project Python environment, read-only saved source and a new
external directory. Existing directory names must be changed rather than reset.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_history_export_receiving_20261013/verify_history.py \
  --source-root /absolute/saved/source-inputs \
  --work-root /absolute/new-history-export-validation

TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. \
  python3 tests/required_unittests.py \
  tests.vnext.test_history_source_export \
  tests.vnext.test_company_fiscal_range \
  tests.vnext.test_selected_source_requirements
```

The script calls these formal interfaces; it only forbids remote sockets and
repeat calculation, never mocks successful source preparation or calculation:

```bash
python3 tools/vnext_company.py export --company marriott_international \
  --metric B02 --history-years 5 --source-root /absolute/saved/source-inputs \
  --output-root /absolute/new-package
python3 tools/vnext_company.py run --company marriott_international \
  --metric B02 --period fiscal-years --fiscal-year-start 2023 --fiscal-year-end 2023 \
  --source-root /absolute/new-package --work-dir /absolute/new-state \
  --output-dir /absolute/new-run-output
python3 tools/vnext_company.py results --company marriott_international \
  --state-root /absolute/new-state --output-root /absolute/new-read
```

## Exact delivery boundary

Main31e4 already receives historical Marriott B02 FY2022–2025 and Enphase B02
FY2022–2025, with their own business limits. PR208 export and PR207 checker are
still candidates; the guide distinguishes the available main entry from this
branch combination. This ordinary package feeds `run --source-root`; it is not
an old native `install/compute` package. Missing dependencies are not fetched
by export, and online historical discovery/completion remains unfinished.
Five-year package readiness is not acceptance of every five-year result: only
one actual B02 year is computed here. Original scope/value references from
PR199/203 are reused; B03 and immature metrics do not gain acceptance credit.

The newly confirmed adjacent-column flaw in the single-segment route is handled
by the public owner's separate main-based repair. This Marriott sample uses
non-dimensional statement group totals and does not validate that flawed
single-segment branch. Its values are not grounds to ignore the counterexample.

New SEC/provider/paid calls are **0/0/0**. No merge by this author, formal adoption,
deployment or active switch. Existing correct values, failures and old result
identities are preserved. Remote CI/receiver validation remain separate.

The two large new JSON receipts are stored as `export.json.gz` and
`selected-source-scopes.json.gz`; `gzip -dc <file>` recovers their exact original
bytes. This only compresses the new verification outputs, not source inputs,
old answers or ledgers. The executable verifier still writes ordinary JSON.
