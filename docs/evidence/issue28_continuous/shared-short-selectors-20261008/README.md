# Shared short selectors: fixed receiving patch

PR75's existing statement-scope, source-inventory and current/history dispatch controls were not selected by its inherited foundation fast runner. This patch is fixed to PR75 `46c30d29712c7db05a4550417fa5f9bccc3c97f7`. It appends three existing class selectors to the v2 list and adds one explicit unittest step in the existing fast job. All sixteen methods run in one process; there is no new runner, long material, source/formula change or broad CI scope expansion.

Parent actually compared runner function ASTs (unchanged), counted the existing 2+5+9 methods, and checked `git apply --cached --check` against a temporary index of that exact commit. These are static checks, not actual consumer test passes. The receiver owns applying the patch and executing the command in its existing branch, then observing that head's real CI. No peer worktree, original ledger, Run or Result was edited. No model/SEC call or permission change.

```
python3 -m unittest -v tests.vnext.test_historical_statement_cases.HistoricalStatementScopeTest tests.vnext.test_historical_filing_inventory_small.ABlockIsHeldToThePriorYearWalksChecks tests.vnext.test_history_company_dispatch.HistoryCompanyDispatchTest
```

Use `PYTHONPATH=scripts:tools`, `PYTHONDONTWRITEBYTECODE=1`, and `TMPDIR=/private/tmp` for the receiver's existing macOS fixture rules. Patch and exact hashes are adjacent; previous PR58/62 shared test-foundation records remain under their original paths and credit.
