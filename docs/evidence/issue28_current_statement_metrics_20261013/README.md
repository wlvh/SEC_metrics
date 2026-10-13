# Current B04/B07 company entry and finite qualified-row correction

This candidate changes the ordinary saved-source B04/B07 factory. It selects
the latest saved annual filing using the existing current selector, resolves
its actual issuer fiscal year and report end, and supplies that selection to
the existing common statement core. Source roles, entity, period and the five
filing identity fields are checked; additional inventory metadata remains in
the assessment. The original selected case, records and result identity stay
intact. This is not online freshness evidence or permission to combine entities.

The case needs the public statement properties and consumer/glue delivered by
PR234/236/235. It does not change the historical core or B05 dispatcher. The
ordinary update configuration names the new factory and its actual processing
dependencies; a version change reprocesses B04/B07, leaves B05 unchanged, and
then reuses the new completion. No new provider/paid/SEC calls were made.

## Executed evidence

- `current-baseline-comparison.json`: actual Marriott FY2025 current cases
  have the same public business fields and Result IDs as the retained adapter:
  B04 2,601,000,000 USD; B07 5.118665018541409147095179234 ratio.
- `verify_company.py` / `current-company.json`: public `run --source-root`
  from an empty isolated task, actual preparation/calculation/save/CSV,
  3.517043 s. Same-input repeat with the current factory forbidden took
  0.114180 s; no additional result files. A new-process `results` took
  0.125114 s and preserved all 33 state files. The source registry/log remained
  unchanged; network, DNS and call claiming were forbidden during execution.
- `verify_current_boundaries.py` / `current-boundaries.json`: actual saved
  Salesforce non-calendar and Paramount successor-period cases compared with
  the retained adapter. These are direct preparation comparisons, not extra
  company persistence or independent business acceptance. Salesforce FY2026
  retains 2025-02-01 to 2026-01-31, B04 7,457,000,000 USD and B07
  25.71296296296296296296296296 ratio. Paramount FY2025 B04/B07 both retain
  `NOT_MEANINGFUL/null`, `ENTITY_CONTINUITY_NOT_COMPARABLE`; no predecessor
  amount is substituted. All four Result IDs match the retained adapter.
- `before-qualified-row-controls.log`: two actual failing subcases for
  `Net income attributable to common shareholders` and
  `Interest expense, net of interest income`. The finite suffix change now
  keeps these unproved numeric rows unresolved. The existing Adjusted OIBDA
  compensation-target positive remains accepted; the original income/default
  contracts are not rewritten. This closes receiver feedback on PR235, discussion
  r4254267766, in the next batch rather than expanding the received PR.
- `qualified-current-controls.log`: 104 affected tests, 9.860 s, zero
  failures/errors/skips. `current-configuration-controls.log`: 7 current
  selection/writer/configuration controls, 0.139 s, zero skips. The latter
  includes actual controller version-change and forbidden-repeat controls.

The initial source-selection mismatch was unused inventory metadata, not a
different accession/entity/period; `selection-mismatch.json` retains that
diagnosis. Initial `writer-controls.log` was a continuation-line syntax error
in the test harness. The first cross-company harness incorrectly assumed
nested result and plural resolver arguments; `before-boundary-harness.*`
preserve those harness errors, not business refusals or passing checks.

## Reproduction and versions

Run from the candidate checkout with the existing source root read-only and a
new task directory. The recorded executions used Python 3.12.14 with
tokenizers 0.22.2 at `/private/tmp/issue28-d03-tokenizers-20261013/bin/python`.
`TMPDIR=/private/tmp` avoids macOS `/var` aliases for the retained path checks;
it does not disable them.

```sh
TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py \
  tests.vnext.test_current_statement_metric_case \
  tests.vnext.test_statement_metric_amendment \
  tests.vnext.test_income_amendment_paragraph_dispatch \
  tests.vnext.test_ordinary_current_update \
  tests.vnext.test_company_current_records

python3 tools/vnext_company.py run --company marriott_international \
  --source-root /absolute/saved-sources --work-dir /absolute/new-task \
  --metric B04 --metric B07 --output-dir /absolute/first-output
python3 tools/vnext_company.py results --company marriott_international \
  --state-root /absolute/new-task --output-root /absolute/read-output
```

The company run records base a8941ea8 and the actual uncommitted factory,
writer and controller hashes, code root, source root and state root. It is
not relabelled as a later committed-SHA execution. Subsequent source-property
and configuration deltas have their own controls. Existing unchanged
Paramount FY2024 original-property and historical company evidence is reused
from PR234/236/235 with its original limits; no old Run/Result was re-signed.

This candidate does not prove all 39 metrics, all ten current companies,
new online discovery, model correctness, business acceptance or production
adoption. Saved inputs may still yield explicit unresolved results under
their existing scope checks. Default retained-native installation and new
model purposes are outside this change. Current input support and old saved
record reading remain separate.

## Received-main combination

Local implementation e14e9dc7 was committed before receiving dependencies.
Normal merges receive PR235's local 70aea885 (same tree as published
30826a5b) and actual main 731f8fd1; combined code commit
d96154bc78cbe9edf3ad98102d6c5942c12e592b has tree
dd2820a11f4232d6b86e50c0bb696090bea9a007. No merge conflict or source/ledger
rewrite occurred. `received-main-controls.log` executed 146 affected tests
in 9.568 s, zero failures/errors/skips. Only this log was untracked during
that committed-code test; this paragraph/log are subsequent evidence changes.
The earlier saved-company evidence keeps its actual working-tree provenance,
and the new main's unrelated C03 receiver evidence is not claimed as a new
execution by this author.
