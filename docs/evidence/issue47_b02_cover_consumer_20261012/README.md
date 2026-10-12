# Historical B02: consume the explicit SEC cover release option

The existing Marriott FY2022 task failed on its **prior FY2021** original:
official SEC DEI `2021q4` was accepted by the issuer heading scan but refused
by the cover text/name binder. Public PR202 repairs that reader interface.
The historical paired-revenue adapter now selects
`dei_release=YEAR_QUARTER_OR_DATE`. Its FASB policy remains
`YEAR_OR_DATE_RELEASE`; neither option admits custom namespaces.

Only `historical_paired_revenue.py` and its consumer tests change.
The scope records the explicit SEC choice and is already part of the input
binding. PR197's received, deduplicated eight-file processing dependency set
already includes the actual cover, text, name-binding and source readers;
no additional controller, renderer or state implementation is introduced.

## Actual usable combination and inputs

Actual main read before development: `8030f851e467c456bb9c9267280a45e2c515d05e`,
which contains received PR197.
Public dependencies:
- PR202 `9452631f1c180c2ccd6c212c677f9830f2bd4b5f`: explicit SEC cover option.
- PR199 `e8ef3643d12d3a7f00c201cedaf6b84adc198d30`: dollar-caption/EPS format.
  This remains necessary for the FY2022 statement, independently of the DEI fix.

Execution commit `383407c42d90edd6824b90878a1f6da9b63ced4f` includes both public
heads and actual main through normal merges. The evidence commit adds no
production change. The thin consumer PR is based on PR202 and excludes PR199's
code/evidence changes from its own diff; reviewers must combine PR199 for the
complete FY2022 company run. The published combination branch is
`task/issue47-b02-cover-consumer-20261012`.

Saved sources are read only. This execution used
`/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`.
Existing restoration is reused. For a first restoration, use the retained
`task/sec-history-five-year` checkout:
`python tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out <new-directory>`.
Use its returned `data_root`, not the export directory or its parent. This
restoration performs no SEC request. See [historical usage](../../../historical_company_usage.md)
for saved-source versus online acquisition boundaries.

## Actual processing, repeat and read

The existing failed FY2022 task had no successful cached result. Its ordinary
company recovery ran the real factory/calculation, saved and exported:
- Recovery: **11.764s**, one FY2022 B02 result,
  `0.4990979288446272641985999856`.
- Factory/paired-source/two-calculator-forbidden repeat: **0.692s**, no
  calculation, no new candidate or result directory; same complete result ID.
- Independent `results`/CSV read: **0.296s**, all saved state bytes unchanged.
- The original two failed checks' four intent/terminal files remain exact.
  New ordinary latest pointers advance; old failures are not upgraded.

The current original, accession `0001628280-23-003485`, has 20,773 million USD
in `table_000026`, native ordinal74. The separately selected prior original,
`0001628280-22-002666`, has 13,857 million USD in `table_000028`, ordinal79.
Both are consolidated annual revenue with original cell, context, statement
scope and XML checks. `post-phase-check.json` retains those coordinates,
source identities and an independent exact Decimal calculation. The result
uses FY2022 dates 2022-01-01–2022-12-31 and reporter1048286.

`recovery.json`, `repeat-forbidden.json`, `independent-read.json`,
`summary.json` and both CSVs record the actual arguments, identities and
timings. `verify_company.py` repeats these distinct phases using a new output
directory and either the existing task or a new external task:
```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_b02_cover_consumer_20261012/verify_company.py \
  --source-root /saved/sec/source-inputs \
  --state-root /external/marriott/state --output-root /new/review-output
```
On an already completed same-input task, the first call can reuse rather than
calculate; this driver deliberately requires recovery/fresh processing. Use a
new task to verify processing again, rather than forcing the old task to run.

## Preserved refusals and small controls

The actual Macy's FY2022 adapter still rejects
`HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN`, 10.712s. This is the
existing incomplete-scope source, not a constructed financial conclusion.
The focused source probe creates no Run or company result.
`macys-negative.json`/`verify_negative.py` retain its selected filing,
non-calendar dates and exact unresolved scope. Its previously saved company
withheld/repeat/read evidence is reused, not replayed.

125 historical/source controls passed in 1.138s; 34 company-dispatch/state
controls passed in 0.353s; **159 required, zero skips/failures/errors**.
The first new-control run had a missing option assertion and a constructed
quarter fixture missing its XML neighbor. The fixture was corrected before
the final run; neither first failure is hidden.
The existing company workflow both watches this test file and executes its
whole module; no new runner is added.

Commands:
```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_historical_statement_cases tests.vnext.test_cover_dei_release \
  tests.vnext.test_statement_group_totals tests.vnext.test_single_revenue_line \
  tests.vnext.test_selected_reported_revenue_v2 \
  tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state
```

No FY2023–FY2025 company processing or fifty-position census was repeated.
The earlier three successful year records remain their original versions.
FY2021's separate prior FY2020 amendment-property gap is still open.
This delivers one candidate historical consumer increment, not full five-year
B02, online historical source preparation, or the 1950-position goal.
New SEC/provider/paid/model calls: **0**; no merge, Ready, adoption or active switch.
