# R4 source audit: blocked before fixture qualification

This is offline diagnostic evidence, not a qualified fixture matrix, production
freeze, Stage-A, cycle, live grant or R4 publication. No archived PR #22 response
or cycle was read or reused. Provider/paid/SEC calls for this work are `0/0/0`.

## Existing-source inventory

The current 981-row request ledger validates with SHA-256
`fe49d7f8aa4fbb0618924f5e212e713604296be1c4e443476fe38cda6f57722d`.
JPMorgan FY2025 is the only materialized bank 10-K: 12,927,325 HTML bytes,
source SHA `4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23`,
accession `0001628280-26-008131`. The full native DerivedAsset is
`sha256:694e176416c50b28974e8fa9844bd0d8e6ee772bd3915b2819aa708bab288110`:
679 tables and 124,761 expanded cells. Its guarded materialization is separate
from this audit. Its 14,885,065-byte accession XBRL and exact submissions
observation also exist. BAC CIK 70858 and Citi CIK 831001 each have zero request
rows and zero immutable source observations. Different-issuer alternatives
cannot be certified from existing bytes; no acquisition was attempted here.

Machine inventory: [source_inventory.json](source_inventory.json).

## Native Candidate / Evidence results

All coordinates below are zero-based within the named native table. Full source,
DerivedAsset, ReaderInputManifest and complete local Reader payload were passed
to the unchanged `validate_reader_output` and `check_evidence` implementations.

| Task | Original cell | Native result | Reconciliation / fixture status |
|---|---|---|---|
| A03 | `table_000065`, r28 c6, `111` | PASS, auto-eligible; `1.11` | Matches independent `1.11 ratio` anchor; native-cell evidence only, not a complete fixture |
| A04 | `table_000100`, r10 c3, `2.50` | PASS, auto-eligible; `0.025` | Matches independent `0.025 ratio` anchor; native-cell evidence only |
| A09 | `table_000222`, r4 c3, `0.66`; `%` is separate c5 | Required unit `ratio` gives `0.66`; `percent` gives `0.0066` | Current MetricSpec fixes reported unit `ratio`; changing the claim to `percent` fails downstream unit equality. NO_INDEPENDENT_LEGACY_ANCHOR remains unresolved |
| A11 | `table_000149`, r9 c3, `4,791`; header r2 c0 says `(in billions)` | PASS, auto-eligible; `4791` | Does not match independent `4791000000000 USD` anchor. `USD billion`, `USD billions`, `billion` also yield `4791`, and are not the MetricSpec's `USD` |
| A12 | `table_000280`, r20 c4, `40`; header r3 c0 says `(in millions)` | PASS but REVIEW_REQUIRED, auto-eligible **false**; `40` | Does not match `40000000 USD`; required scope is not present inside the table |
| A13 | Current XBRL has several legitimate geographic measures | No synthetic scalar selected | NO_INDEPENDENT_LEGACY_ANCHOR cannot close until the intended economic measure is explicit |

The authoritative root mirrors independently retain the four anchor values
above. A09 and A13 are `NOT_EXTRACTED` with empty values in those mirrors.
No new expected value was substituted into either root output.

The amount-scale limitation is an implementation gap, not evidence that the
economic definition should change. `constraints.parse_numeric_claim` scales a
`million`/`billion` suffix in the exact **value cell**, not a separate header or
the claimed-unit string. `workflow.finalize_reviewed_direct_results` requires
the claimed unit to equal the compiled `reported_unit`; a different spelling
produces `REPORTED_UNIT_MISMATCH`. Concatenating a header into the claimed raw
value would violate the existing exact-cell replay. All three same-scope total
AUM rows were inspected: table 149 rows 9/18 and table 153 row 19 all report
`4,791` with separate billion-scale headers, not a self-scaled value cell.

## A12 is a genuine owner-escalation boundary

The exhaustive native raw-table scan used the existing bounded literal matcher
and **every** approved A12 enum alias: `95%`, `95 percent`, `99%`, `99 percent`,
`one day`, `one-day`, `10 days`, `ten days`, `10-day`.
Across all 679 tables, only an unrelated `99%` appears in table 359; no table
contains a holding-period alias. `complete_scope_tables=[]` is therefore true
for every allowed confidence/holding-period combination, not only 95%/one-day.

The filing's narrative, outside tables, explicitly describes the Risk Management
VaR's one-day holding period and 95% confidence level. The target table is real;
the missing fact is a permitted native locator for that prose. The current
Evidence contract only accepts same-target-table scope labels. Parent D-32
`/single_table_locator_invariant=true` was CARRY_FORWARD to
`S-INHERITED-SEMANTICS /obligations/60`; permitting two windows did not supersede
that invariant. No text was copied into a caption or another table. Owner
direction is required before relaxing that retained locator boundary, or before
substituting another production-source/metric scope.

Coverage evidence: [jpm_a12_scope_coverage.json](jpm_a12_scope_coverage.json),
ID `sha256:cd0f363da8376c12fef61a4e6e0b3cfe789fe95bf88936cbe441d9ca03eb18e4`.

## Structured-first A09/A13 audit

The real `adapt_accession_xbrl` adapter ran first on the immutable accession XML,
bound to the exact submissions source-set manifest
`sha256:dcec6459982bf0518612d05b9bb3c93e99cd69ea8ef2b10316b50f7e0f29e88b`.
The complete XML contains 8,442 facts and 2,216 contexts.

- A09's Nonaccrual/Nonperforming inventory yields 65 adapted claims; 33 are
  current-period candidates across 18 dimension sets. Amounts, retained-loan
  ratios and consumer/wholesale subsets are not a unique firmwide formula.
- A13's geographic dimension inventory yields 531 adapted claims across 14
  concepts; 83 current-period geographic candidates have 51 dimension sets.
  Revenue, assets, income, loans and deposits must not be collapsed into an
  arbitrary USD scalar. The current A13 scope enum specifies geography but not
  the economic measure. The method document also lists revenue/assets/exposure
  as alternatives, without selecting one.

These are actual structured-source ambiguity observations, not permission to
skip structured-first or claims that a table fallback has completed. The
two-source/two-navigation/out-of-window no-anchor closure is **not complete**.
Exact claim-set hashes and recipe are in
[source_audit_evidence.json](source_audit_evidence.json). The
`test_structured_ambiguity_replays_through_native_accession_adapter` regression
reconstructs the actual source-set manifest and re-runs the existing adapter to
verify both complete/current-period claim-set hashes; it does not pick a scalar.

## Commands and boundaries

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/audit_r4_sources.py --inventory-cik 19617 --inventory-cik 70858 --inventory-cik 831001
PYTHONDONTWRITEBYTECODE=1 python3 tools/audit_r4_sources.py --recipe tests/fixtures/vnext/r4_offline/jpm_fy2025_probe.json --full-asset /tmp/r4_jpm_full_asset.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/audit_r4_sources.py --recipe tests/fixtures/vnext/r4_offline/jpm_fy2025_probe.json --scope-coverage-task financial_value_at_risk_table_v1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_r4_offline_qualification
```

Inventory: rc 0, 0.025s. Full ten-variant native probe: rc 0, 167.064s (the
function used by the CLI, with compact stdout projection). Scope coverage:
rc 0, 0.814s. Regression suite: rc 0, 5/5 tests, 2.026s. A diagnostic command's
zero exit means the audit ran; it does **not** mean its positive fixture gate
passed. Full DerivedAsset input must be rebuilt by the hard-guarded materializer,
not fabricated or filtered. No complete R4 fixture authority was produced.

Unmet completion gates: all six tasks' production/alternate positives, A09/A13
no-anchor closure, full out-of-window candidate dispositions, full fixture
matrix and completed offline qualification. A03/A04 native-cell PASS must not
be relabeled as those complete gates. The A12 no-positive and A13 economic-basis
decisions are escalations; no revised Requirement or live authority was issued.
