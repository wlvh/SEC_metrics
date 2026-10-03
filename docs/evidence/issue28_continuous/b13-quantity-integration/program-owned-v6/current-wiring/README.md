# Current main V6 offline wiring and execution preparation

Current closure: sha256:1ef08f67e6ef52e8fc4185d65b4c124a18c8d4e2dc8814495ea431e5a0fe7e1d. The old provider wiring receipt is preserved in previous-provider-wiring.json; current-provider-wiring.json is the exact replacement validated by the existing reader. Main runtime code was not edited by this wiring task.

Ford group1 (5units/16 candidates/no program quantity) and Enphase group1 (5units/5candidates/one program quantity) passed actual saved-source preparation, exact official-opener mock, native Candidate/Evidence acceptance and recorded controller execution. An omitted unit failed for each company. A partial set remained incomplete, not non-disclosure. All17 prepared request IDs and provider bodies matched the counted plan. 27 ledger/count/role tests passed.

The original run completed all checks but its final summary writer rejected a binary float duration. That original failure log is retained. The finalizer did not rerun executions: it validated all original recorded ledger bytes, success/failure outcomes and current closure, then wrote the integer/string-only summary and verified every archive member. Its first assertion incorrectly expected the exception text once (traceback showed it twice); that harness-only log is also retained. Neither error is converted into native or live credit. This is actual-source/synthetic-response wiring only.

execute_company.py defaults to preparation and never opens the live ledger or reads credentials in that mode. Its dry run passed for Enphase6/Ford11, including all original identities, body hashes, context bounds and the current wiring receipt. No real execution was started.

After parent review, execution requires the exact company, a NEW absolute output directory, the independently checked current cumulative provider/paid/SEC totals and the finite company cap. Example command shape (replace placeholders, do not copy them as values):

```
python3 /tmp/sec_metrics_issue28_continuous/b13-v6-current/execute_company.py --execute --company enphase_energy --expected-counts PROVIDER,PAID,SEC --max-provider-requests 6 --output-root NEW_ABSOLUTE_RESULT_DIRECTORY
```

Ford uses ford_motor_company and cap11 in a separate invocation. The script pins this current closure, all request/body identities and exact counts. It uses the existing native assessment interface, never clears the ordinary B13 LIVE pause, never retries failed identities, and only reuses original successes after current acceptance. A complete accepted company set is registered and installed into a new native Run/public-row package. Ordinary update/history replay and final unified acceptance remain distinct subsequent work. The fixed240/240/80 global allowance,120 seconds,8MiB,200000 context and no automatic retries remain in force. This script and wiring evidence do not authorize production or new resources.
