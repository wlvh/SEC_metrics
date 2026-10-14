# Reserve the approved history calls in the existing shared allowance

The user decision transcribed by the receiver is
[#28 comment6170123741](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-6170123741),
with exact execution scope in
[#47 comment6170138586](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-6170138586).
This change reserves those 81 model calls and one SEC request in the original
#28 ledger. It does not add allowance, change source/metric definitions,
authorize retries or implement D02/E01 provider transport.

## Registration actually completed

Original root:
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`.
Record: `history-20261014-allocation.json`.
Allocation ID:
`sha256:b230b8a1bcac1fc112f2adfa5e12db1934ae421ea5a01c961ab59835039f2269`.

| Channel | Actual used | Reserved | Unallocated | Total limit |
|---|---:|---:|---:|---:|
| Provider | 143 | 81 | 16 | 240 |
| Paid call count | 143 | 81 | 16 | 240 |
| SEC | 52 | 1 | 27 | 80 |

Registration occurred while holding the existing stable-directory lock. A
separate ledger object reopened it and read the same counts/reservation.
All195 previous claims, binding and initialization anchor retain their bytes.
No pending claim or stopped channel existed. No network or business claim is
made by registration; network and DNS were forbidden during it. The original
claim hash is `6023bf1790b31d5895dad3ef824b3d102d56b0381140f6b79463d8e97964f6eb`.
See `registration-receipt.json`; `allocation.json` is a readable semantic JSON
copy of the registered record, not a new call permission or replacement ledger.

The fixed scope is commit7e4ee18c46172c760fc9401bb4610e6e63db6936,
`docs/receiver/progress_snapshot_v1/output_v1_1/scope_table.csv`.
Its1950 rows contain exactly81 `ANSWER_GAP_MODEL_RESPONSE` rows: D02=43,
E01=38. That1.6MB CSV is not duplicated into thisPR. The connector rejected its
size; GitHub's contents API returned `encoding:none`. The actual Git blob
287262b738e7976418889cc61d2ca96f1a93b952 was then read, decoded, sized and
checked; its SHA256 is recorded. Only82 approved task identities are copied.
The SEC task is solely Macy's FY2019 primary
0000794367-20-000040/m-0201202010xk.htm, one attempt.

## What changed

The old `CallLedger.claim` did not deduct a reservation, so a second ordinary
caller could spend credit held for the batch. `before-regression.log`
reproduces that mistake with a small recorded ledger.

The existing `snapshot` now includes allocation progress only when this
record exists; ledgers without it retain their original state shape. Ordinary
claims must fit the unallocated balance. Explicit allocated claims must match
one recorded task, executor, channel and allocation ID. They consume the task
when claimed, even if the result fails or remains unknown. A new digest cannot
reset that task. New allocation claims do not consume or reopen old33-group
opportunities. All existing purpose, original request deduplication, stop,
terminal, atomic claim-write and total-count checks still apply.

The82 tasks are fixed; no generic approval platform or new ledger root exists.
Input accounting uses at least the estimate, and a greater recorded provider
usage when available. Pending/null usage remains unknown and retains its
estimate; original stop behavior remains. Per-request and batch bounds are
200000/9000000 input tokens; output configuration remains4096. Recorded usage
above the input bound prevents further batch claims. Actual usage/cost logs
are not converted from estimates or inferred from call counts.

Consumer interface (inside the original ledger lock):

```python
ledger.claim(channel=task['channel'], request_digest=actual_digest,
             requirement=current_configuration, plan_id=actual_plan,
             purpose='remaining_development_feasibility',
             budget_allocation_id=record['allocation_id'],
             budget_allocation_task=task, allocation_executor='issue47',
             estimated_input_tokens=measured_input if task['channel']=='PROVIDER' else None)
```

Task must be the complete corresponding `record['tasks']` item, including the
company/year/source-scope fields. The execution consumer must additionally
check actual main request preparation, source coverage, transport, output,
usage and complete company results. **This budget interface does not open
the old current-runtime D02/E01 live gate.** #47 owns that finite consumer;
#28 owns this shared counter. No public caller is silently switched to it.
Before actual execution use the allocation-aware implementation, not a saved
old program that cannot see reservations. On completion reconcile actual
consumption; do not delete the record or pre-count82 calls as executed.

## Validation and limits

```bash
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py \
  tests.vnext.test_continuous_call_allocation \
  tests.vnext.test_continuous_call_ledger tests.vnext.test_company_online \
  tests.test_selector_registry
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py \
  tests.vnext.test_current_request_runtime.CurrentConfigurationTest \
  tests.vnext.test_current_request_runtime.CurrentVariantLimitsTest
```

44 controls and3 request configuration controls, zero failures/errors/skips;
logs record the actual duration. They cover reserved/unallocated counts,
separate reopen, idempotent reservation, wrong scope/owner/channel/input,
input total, task consumption on failure/pending, SEC counts, corruption,
old-batch separation, and unchanged current transport gating. Existing online
HTTP-boundary and interrupt/no-repeat tests execute alongside them.
No real provider/paid/SEC call:0/0/0. No model correctness or full-company
result is asserted. This registration unblocks the budget prerequisite; final
main request/consumer validation, PR275/276 impact and actual execution still
belong to the designated executor. Public commit CI and receiver review are
separate from these local execution facts.

Current main advanced to97005a37 during preparation. Git fetch actually timed out. All14 changed production/test blobs were then materialized from the fixed GitHub compare and checked against their Git blob IDs; this includes accepted B07, D04 dependencies and historical consumers. Combined48 controls pass (duration in main-controls.log). Public commit inherits the full97005a37 tree, including its documentation and previous evidence. Local tests use the verified production/test overlay plus this named allocation change; they do not claim a local Git merge or full-tree identity. No model or old company chain is rerun.
