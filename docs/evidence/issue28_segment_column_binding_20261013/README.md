# Bind single-segment supporting amounts to the revenue column

Progress on #28; responds to [PR206 review4250924956](https://github.com/wlvh/SEC_metrics/pull/206#discussion_r4250924956) and the historical owner's independent reproduction. Public implementation owner is #28; historical consumers do not duplicate the checker.

Starting public205 head ae8841b79cf208cca01189f71c8d0dfb0433a4f8/tree3a9c42e3; local normal-merge counterpart5002f2b1 has exactly that tree. No caption follow-up, new metric or AI chain is added to this receiving repair.

## Reproduced cause and change

The old segment path compared only the year-header origins for revenue, cost and net income. A header spanning two amount columns allowed revenue at column1 to be supported by cost or profit at column2. The complete-expense route already requires physical coverage of the selected revenue column; the segment route omitted it.

before.log: shifting only cost, only profit, or both into the neighboring amount column produces three failed rejection assertions. It actually reaches the enabled segment scope, not an unrelated option gate. A cost/profit cell spanning both columns from the correct origin is a legal positive.

The minimal fix requires each supporting amount cell's original column/colspan to cover the selected revenue column, in addition to the existing same year-header group, period, scope, native/visible scale and original XML checks. It does not require equal column indexes: a proper colspan remains valid. It does not change native fact dimensions, count qualifications, calculation inputs, default disabled options or historical records.

## Executed verification

- after-controls.log: required162 tests in1.379s, zero failures/errors/skips. Two new methods cover three wrong-column variants plus a genuine covering-colspan positive; existing scope/count/XML/period/unit/negative controls remain.
- Existing verify_original.py (fixed originally published helper) on saved Enphase FY2024 primary+XML:6.292264s, revenue1330383000USD, c-6, original StatementBusinessSegmentsAxis/enph:ReportableSegmentMember preserved. Original revenue cell column16; original cost cell column15/colspan2 covers16; profit cell column16/colspan1 covers16. XML match retained. Default output is exact to the original8030 baseline.
- Own priorFY2023 original+XML:4.298134s,2290786000USD, nondimensional. No old company result recalculated.
- Existing receiving-negative helper on actual saved MacyFY2022:11.471563s, accurate HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN; no governance-format exception or success credit. Wrapper only selects the new option; source reading and returns remain actual.
- original-baseline-typo.log: the first helper command used a mistyped SHA and stopped before source inspection. It is retained; the corrected original-after.log is the evidence. No failed request or task was rewritten.

Full scope outputs, original SHA/amount/context/statement cells are in enphase-after.json/enphase-prior-after.json; actual negative source outputs in macys-negative.json. These are source checks, not fresh company executions or a universal correctness proof. The already completed company phases are reused. The constructed wrong-column defect is confirmed; these actual Enphase source positions remain valid under the fix. No entire B02 family or previous Result is automatically marked wrong or upgraded.

## Reproduction and boundaries

Source root is the existing read-only `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`. Commands use the existing source helpers under docs/evidence/issue28_single_segment_revenue_20261012/ with explicit new output paths; no old archive/MANIFEST is regenerated. New SEC/provider/paid calls0/0/0; original responses, ledger, old Run/Result and peer state remain unchanged.

```bash
TMPDIR=/private/tmp python3 tests/required_unittests.py tests.vnext.test_single_segment_revenue \
  tests.vnext.test_single_revenue_line tests.vnext.test_statement_group_totals \
  tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_selected_revenue_scope_v1 \
  tests.vnext.test_paired_measure_contradiction tests.vnext.test_historical_statement_cases
```

Tests executed on the stated working-tree code; the subsequent commit preserves those source/test bytes. Public head and exact tree are in the PR reply. New-head CI, historical consumption of the repaired core and receiver personal recheck remain separate; no author Ready/merge/adoption authority.

## Actual-main successor

Before publication the receiver had already merged205/206 to actualmain31e4a00d14570b6e7128084e23e6628af3f22c3f. The repair therefore uses a new short branch from that main, not a push to the mergedPR. Only this own patch is applied: localb0b8c41c, tree2e9f94f0, has exactly the two production-line additions/one condition change and its tests/evidence relative to31e4. main-combination.log: required168 controls1.517s, zero error/failure/skip. The received main source code and thin consumers remain. Original scope inputs/direct negative evidence are reused because no relevant native parser/column binding dependency changed in that composition. Remote receiving/CI remain separate.

Actual-main Macy negative recheck also uses the composed source implementation: HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN 11.039839. It does not create a company result or call SEC/provider.
