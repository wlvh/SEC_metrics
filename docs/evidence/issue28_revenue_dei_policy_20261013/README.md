# Reported revenue header obeys the explicit DEI release policy

This #28 public correction addresses receiver [6133724712](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-6133724712) and [PR205 review4250917121](https://github.com/wlvh/SEC_metrics/pull/205#discussion_r4250917121). Actual base is main `385991307f35bfbac771913de4d2ba4156ed7c95`. Only the existing `_defined_income_headers` namespace filter changes; no metric definition, revenue amount selection, common default, period/subject rule or permission is widened.

## Reproduced failure and correction

The outer public `reported_revenue_scope` already validates `dei_release` and passes it to the header helper after its expense proof. The helper instead filtered EntityRegistrantName with hardcoded `YEAR_QUARTER_OR_DATE`, despite its default `YEAR_ONLY`. Corrected two nonempty small tests reproduce that quarterly/date name facts authorize a named statement header under the wrong declared policy, and the full expense statement is accepted instead of refusing that unsupported header. `before-corrected-controls.log` records the failures. Initial `before-controls.log` also contains a test-harness mistake comparing escaped regex text as literal text; it is retained but not counted as business reproduction. The final assertions match the actual heading against the returned patterns.

The helper now filters with the passed `dei_release`. Default stays YEAR_ONLY. Explicit YEAR_QUARTER_OR_DATE still supports actual SEC quarter/date release forms and remains recorded in the explicit scope body. Foreign extension URI, q5/unknown suffix, unsupported policy, changed entity/period and conflicting cover remain rejected or provide no alias. No whole statement, table, source, unit or native XML check is removed.

One old helper-only cover negative expected a downstream exception from a cover branch reached through the erroneous broad name filter. Once the name is correctly filtered, that branch is unused. Its negative now proves **no cover definition and no heading alias**, consistent with the existing wrong-entity helper behavior. The new full-response/source-scope test separately requires the precise statement refusal, so lack of a helper exception is not treated as accepted revenue. The first affected failure is retained in `after-controls.log`.

## Caller boundary and independent responsibility

The #28 current reader still uses its existing YEAR_ONLY annual source contract; its call shape/defaults are unchanged. `historical_dei.annual_period` explicitly supports YEAR_QUARTER_OR_DATE. The historical paired B02 admission already passes that same explicit DEI policy. #47 independently traced its historical B01 call: it passes FASB YEAR_OR_DATE_RELEASE and the historical annual reader but omits the separate SEC DEI policy. That caller must use the existing explicit option after this helper fix; it is a #47-owned change, not silently changing the shared default. FASB and SEC policies are distinct and cannot substitute for each other.

An initial public queue sentence saying the expense branch failed to pass the policy was disproved by source tracing and withdrawn before coding: the helper itself is the confirmed defect. No extra parameter/framework is introduced to solve that incorrect diagnosis. Peer will consume the fixed public commit and verify affected historical inputs before granting current reuse credit. This helper PR alone does not certify that consumer's acceptance.

## Actual results

- `final-affected-controls.log`: **168 required tests /1.464s /zero skips**, covering direct/header/full expense proof, original single segment, group totals, cover release, source/calculation and historical B03/statement controls. Constructed inputs are explicitly development controls, not company results.
- `actual-current-original.json/.log`: existing Enphase FY2024 complete original HTML and separate native XML, no network, existing finite single-segment option. **6.204s**, source-qualified reported revenue **1330383000 USD**, c-6 original segment context retained, same visible whole statement/count/column/source checks. Original primary `275bc6e2…` and XML `48b84800…` bytes are unchanged. Default proof equals the unmodified main385 default; the complete explicit proof equals the previously saved source result dictionary, including Scope `065a2f881…`. This is source qualification, not a new complete B02 company result or new Calculator operand.
- `actual-proof-comparison.json` records exact old/new source proof equality. Current/older successful source/Result identities are not rewritten. Already valid unrelated company/result chains are not rerun wholesale.

The actual material reuses the unchanged `docs/evidence/issue28_single_segment_revenue_20261012/verify_original.py`, with base385 and only its current FY2024 mode. Its old prior-year-before-failed comparison was not used because that older fix is already main-delivered. Reproduction:

```sh
PYTHONPATH=scripts python3 tests/required_unittests.py tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_single_segment_revenue tests.vnext.test_single_revenue_line tests.vnext.test_statement_group_totals tests.vnext.test_cover_dei_release tests.vnext.test_selected_income_calculation tests.vnext.test_historical_b03_case tests.vnext.test_historical_statement_cases
PYTHONPATH=scripts:. python3 docs/evidence/issue28_single_segment_revenue_20261012/verify_original.py --source-root /absolute/saved/source-inputs --baseline 385991307f35bfbac771913de4d2ba4156ed7c95 --output /absolute/new-source-proof.json
```

Source root is the existing read-only company-verified input root recorded in the actual output. `tested-worktree.json` records main baseline plus uncommitted tested blobs; the subsequent delivery commit is not retroactively called the execution SHA. Existing required workflow/fast selectors already run the two affected test modules. New head CI and receiver review remain separate.

New provider/paid/SEC **0/0/0**, no ledger/account/response/production change, no author Ready/merge/adoption/deployment/active. Full company/390/update goals remain incomplete. The next independent source-range failure-status work uses the peer's fixed probe rather than a new source collector.
