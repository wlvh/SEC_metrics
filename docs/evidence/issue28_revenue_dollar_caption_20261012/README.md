# Dollar caption and loss-qualified EPS heading

Progress on #28. This is a bounded public follow-up to PR196, not a new revenue method. The historical consumer PR197 had proved Marriott FY2023's current scope but withheld that company's growth at the independently selected FY2022 prior filing. The exact selected original and rejected spans are fixed in PR197 head5eb0f033, `marriott-company-receiving/fy2022-prior-heading.json`.

## The actual defects and change

Original FY2022 filing0001628280-23-003485/mar-20221231.htm, CIK1048286, Jan1–Dec31, primary SHA c041a050, has `($ in millions, except per share amounts)` before table000026. The grouped-total contract recognized `(in millions, ...)` but rejected the dollar symbol. The first small test failed; the actual saved-source reader reproduced SELECTED_REVENUE_STATEMENT_HEADING_SCOPE_UNRESOLVED in3.163s (`before.log`, `original-before.json`).

Adding that exact dollar prefix fixed the introduction but exposed a second real error: table000026 row28 has `EARNINGS (LOSS) PER SHARE`, whereas the contract allowed `EARNINGS PER SHARE`. The raw original diagnosis and the separate failing small EPS test are preserved. The first post-caption original probe failed after this second rejection; its AssertionError is retained in original-after.log, not called success.

The production patch changes only the two finite descriptions in the explicit `allow_statement_group_totals=True` branch. The default is still False. No new name/CIK/filing special case, coverage shortcut, language classifier, quantity mapping or model request is added. Foreign currency, added subsidiary limitation, wrong scale and source/scope/period errors remain rejected. The existing visible/native scale consistency check still applies; accepting the dollar symbol cannot turn thousands into millions. The EPS heading is an exact section description, not permission to ignore arbitrary local prose.

## What was actually verified

- `two-caption-controls.log`:168 required income/current/historical controls in1.397s, zero errors/failures/skips. Added nonempty positive and foreign-currency/scope/scale negatives; former168-minus-new tests are retained.
- `two-caption-original.json/.log`: real original primary+XML now prove20773000000 USD, full2022 annual period, scope31d0bfa6. Visible unit sources, exact source references, original native/XML amount and closing-group evidence remain in the proof. Reader time3.115s. This probe creates no company Result or Run.
- `original-2023-2024-retained.json/.log`: the previous two original proof bodies are exactly equal to PR196's final-originals.json, not merely equal totals. No old company chain or model response was replayed.
- `macys-negative-retained.json/.log`: the actual FY2022 Macy original still has no admitted reported total,2.507s. Its old company/withheld state is not rewritten.

These tests used the dedicated issue28-revenue-dollar-caption checkout with an uncommitted two-line patch over local e8cb2e39, whose tree1c0da495 is exactly public PR19633503f48. Actual main df1c614f was read before publication; it does not yet contain the required source contract. The follow-up therefore targets PR196's branch, with only the new increment visible. No code from the historical branch is merged or copied. The extra D04 guide change on main is not a consumed source-reader change and does not justify financial reruns.

## Reproduction

```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_statement_group_totals tests.vnext.test_single_revenue_line tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_selected_revenue_scope_v1 tests.vnext.test_current_reported_revenue tests.vnext.test_selected_income_calculation tests.vnext.test_historical_statement_cases
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue28_revenue_dollar_caption_20261012/verify_source.py --source-root SOURCE_INPUTS --output NEW_OUTPUT.json --expect proved
```

SOURCE_INPUTS is the existing read-only verified source root under7e99/SEC_metrics-issue47-company-verified-source-20261006. The executable probe refuses network sockets; original data, source metadata, private ledger and historical states are not changed. Only external saved input is read, not a saved financial answer. New SEC/provider/paid calls0/0/0.

## Still required

#47 owns the existing historical consumer. It will consume the fixed public patch, normally migrate only the affected FY2023 company state, verify its own current/prior original amounts, Calculator result, forbidden-processing repeat and independent CSV/evidence. FY2024's successful company record and Macy's negative are reused; this source proof does not itself grant FY2023 company credit. Receiver limited review/combination and CI terminal state remain separate. No independent review, full five-year,390, formal adoption or production claim is made.
