# Current A13 at the existing company entrance

The saved-source latest-complete-fy command previously returned
`PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED` for A13 ([before.log](before.log)).
The financial original-source inspector, approved international-net-revenue
Spec, Calculator and historical A13 route already exist. This candidate
connects that existing capability to ordinary current records; it does not
add a geography selector, regional-sum policy or online acquisition purpose.

## Actual current paths

Code root:
`/Users/lyuhongwang/.codex/worktrees/issue28-current-geography/SEC_metrics`.
Base: main `e24a5271325a2a39e8329df45f526f2629b543b0`.
The tests and company runs used that base with the recorded uncommitted
implementation. [tested-tree.json](tested-tree.json) names the tested file
bytes; a later published commit is not falsely described as having run earlier.

Read-only source root:
`/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`.
Its registry and original request-log/manifest hashes stayed unchanged.
Source selection, input preparation, inspection, Calculator, save, projection
and read use actual implementations. Only network access is prohibited;
repeat tests additionally make the calculation factory and result writer fail
on invocation. There are no real SEC/provider/paid calls or ledger claims.

| Company / source issuer year | Result | Actual period | First / forbidden repeat / independent read |
|---|---|---|---|
| JPMorgan FY2025 | 42,758,000,000 USD, source-reported international net revenue | 2025-01-01 .. 2025-12-31 | 7.067 / 0.203 / 0.414 s |
| Marriott FY2025 | `N_A_STRUCTURAL`, null | 2025-01-01 .. 2025-12-31 | 1.489 / 0.172 / 0.413 s |
| Salesforce FY2026 | `N_A_STRUCTURAL`, null | 2025-02-01 .. 2026-01-31 | 1.713 / 0.176 / 0.415 s |

The latter two are nonfinancial companies under the existing A13 applicability,
not missing geography extraction or zero international revenue. JPMorgan
Result remains `4661b0de…`; the original first diagnostic result also keeps
that identity. [actual-company.json](actual-company.json) contains full IDs,
actual commands, roots, dates and CSV fields. Result files do not change on
repeat; independent `results` reads do not modify task state. Seven result
files occupy 325,197 / 142,489 / 189,355 bytes respectively; no second business
result directory is created by repeat. Ordinary check/CLI logs can grow.

[original-source.json](original-source.json) is a separate bounded direct read
of the original primary HTML, international row, unit/scale, native entity and
calendar-year context, and linked definition. Raw SHA
`4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23`:
the row says “Total international”; its Revenue column is 42,758 million;
the footnote defines revenue as net interest income plus noninterest revenue.
The related native fact is `us-gaap:Revenues`, `c-2126`, registrant0000019617,
full-year2025, `iso4217:USD`, scale6. No regional sum supplies the value.
This is not a full visual audit or an independent business acceptance claim.

## Source separation and failures

[verify_source_only.py](verify_source_only.py) copies exactly the three consumed
original bodies plus their headers, original log/manifest and registry: nine
files, with no catalog, Spec, rules or answers. A genuinely new JPMorgan task
completes in 7.337s and has the same Result identity. Program rules are loaded
explicitly from the installed code root.

[verify_source_failure.py](verify_source_failure.py) adds an explicit recorded
503 for the required primary in that isolated copy. Formal `run` refuses it
before calculation with `LATEST_SOURCE_REQUEST_FAILED`; independent reading
shows `INPUT_OR_EXECUTION_FAILED` as the current observation, while the original
2025 success and its files remain unchanged. Neither private source root nor
real ledger is changed. No retry or new paid opportunity is introduced.

Run from this candidate, with sources kept read-only and fresh output paths:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:tools:. \
python3 tools/vnext_company.py run --company jpmorgan_chase \
  --source-root /path/to/saved-source-inputs --metric A13 \
  --work-dir /path/to/new-a13-state --output-dir /path/to/new-a13-output

python3 tools/vnext_company.py results --company jpmorgan_chase \
  --state-root /path/to/new-a13-state --output-root /path/to/read-only-export
```

Full actual scripts and logs are in this directory. The source-only scenario
can be reconstructed from the three proofs recorded in the actual manifest;
the publicly committed script does not invent or download missing responses.
`verify_company.py` uses a fresh isolated task and the original first report
only to locate the existing read-only source root. It does not use old CSV
values as inputs to calculation.

## Changes, compatibility and validation

- `current_geography_case` adapts existing financial resolution into the
  common saved-record case. Full source dispositions remain in input-assessments;
  daily CSV keeps a compact original-location/revenue-meaning summary.
- Current writer dispatch, metric eligibility and actual parser/Spec/fiscal-label
  dependencies are explicit. Relevant processing changes invalidate reuse;
  the new wrapper alone does not invalidate unrelated B01 configuration.
- `ordinary_financial_results` gains optional `rules_root=None`. The default
  old annual reader, Spec root, returns and calculation remain unchanged;
  only the explicit current route chooses issuer-labelled ordinary input and
  installed program rules. Historical geography selectors/core are unchanged.
- The company-source CI layer gains one required five-test step and trigger;
  all existing layers, required steps, skip checks and timeouts are retained.

[combined-controls.log](combined-controls.log): 100 relevant wrapper, update,
history, writer, source-only, company and independent-read tests in 33.713s,
zero skips/failures/errors. The four original-source financial controls
(two direct international totals, wrong geography/revenue meaning, wrong
currency, conflicting scale) also all passed in the earlier 86-test run;
that run as a whole failed on one nonexistent test selector and the obsolete
company assertion that A13 must remain unimplemented. Its original failure
log is retained, not relabelled green. The final100 command uses real selectors
and checks actual current dispatch while retaining the unreceived D03 refusal.

Earlier invalid harness CSV-field assumption, old unsupported-update assertion
and loop-shape error are retained separately. The final actual company evidence
uses the corrected harness and compact final projection. Neither original
Result nor saved source is rewritten to obtain success.

The candidate is independently based on main; it does not require reviewing
C04/PR174, D04/PR171 or debt/PR172/173. Shared writer/controller combination
must preserve both explicit routes and their dependency declarations.
Receiver review, new-head remote CI, all-current-bank acceptance, all390,
online A13, Ready, merge, formal adoption, deployment and active switching
remain separate. Old tasks read their saved record/version; a normal code
configuration change may cause one reprocessing check, not a result re-sign.
