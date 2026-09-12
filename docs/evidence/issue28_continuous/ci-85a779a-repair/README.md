# A12 test fixture setup repair

GitHub run https://github.com/wlvh/SEC_metrics/actions/runs/34670253798 failed on HEAD `85a779a520cf39c4a795a2fb32c042f9df0de77e`. Its 119 selectors had one timeout: `FinancialBalanceScopeTest.test_var_reported_estimate_is_distinct_from_an_illustrative_table` at 30.034 seconds. The original failure log is retained.

The class formerly prepared both AUM and VaR facts before either selector. The test-only repair prepares each on first use. It preserves every selector, source and assertion, the 30-second timeout and all V13 runtime authority bytes.

- Exact selector through the existing fast runner: PASS, 18.442 seconds; `a12-fast-lazy-recheck.json`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_financial_balance_scope`: all 22 PASS, 155.552 seconds; `financial-balance-lazy-tests.log`.

These are local checks of the repair. A later GitHub run must be observed separately. No full acceptance, new call or production action occurred.
