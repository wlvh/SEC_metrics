# Used legacy wrapper compatibility

The PR258 nonblocking follow-up [4262636577](https://github.com/wlvh/SEC_metrics/pull/258#discussion_r4262636577) is reproduced. With the exact earlier component fixture, three controlled changes in the old implementation still returned compatibility: rebinding the selected factory, changing the outer source root, and changing the save-call arguments. `before.log` retains the three failures. This proves the comparison gap; it is not evidence that existing company values are wrong. The receiver already inspected the historical committed versions and reported that their compatible outer wrappers were identical; those results are not withdrawn.

The fix keeps the existing one-time inline-to-JSON dispatch transition. For an old default-dispatch record it compares the entire `create_saved_result` wrapper, including parameters, decorators, outer statements and save arguments. Only the separately checked nested route body and the new exact registration lookup are normalized. Additional executed statements in the selected old route now reject compatibility. Explicit supplied factories do not consume that wrapper, so their unused wrapper remains outside this check. Original bytes, selected entry, real processing dependencies, core writer/reader and missing-code checks remain. No approval/head gate, version whitelist or generic framework is added.

Tests executed on the worktree based on main `17569516a8be63002f0a6336041421ac14d33459`, then committed unchanged as product `127cae4912255c7c9d50b4611f50e8d938171c28`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.vnext.test_saved_result_registration \
  tests.vnext.test_ordinary_current_update \
  tests.vnext.test_company_current_records \
  tests.vnext.test_d04_processing_scope \
  tests.vnext.test_selected_history_result_state -v
```

Python 3.14.7: 123 controls, 9.462s, zero skips/failures. Python 3.12.10: same 123 controls, 10.654s, zero skips/failures. Logs remain `/private/tmp/issue28-legacy-wrapper-after.log` and `...-after-py312.log`. New small controller test proves changed legacy source logic processes once, then reuses the new result while preserving the old success. Existing genuine mechanical-transition and supplied-factory positives remain. The module is already in the feature selector registry; no selector/platform expansion is required.

Actual current company consumer under clean product `127cae49`: the Salesforce FY2026 D04 ordinary state from [f651417c](https://github.com/wlvh/SEC_metrics/blob/f651417cd280a37f587e5a6f82065be5819b0fad/docs/evidence/issue28_salesforce_d04_company_20261014/README.md), original calls152--156, runs with sockets/DNS/claims and the actual D04 factory forbidden. It returns `PREVIOUS_INPUT_WITHHELD` in 0.081299s, same `04d871...` result, no calculation or new candidate. All seven result files, result directories and claims bytes remain; `company.json` records the actual check. This consumer checks that the new comparison does not cause unnecessary processing of an already registered current record; it does not replace the constructed old-wrapper transition tests. Prior independent CSV reading is reused because result/reader bytes did not change.

No original record/configuration, model response, source, budget or business definition is changed. Real additions SEC/provider/paid are 0/0/0. Unknown or changed used logic reprocesses through the ordinary controller, with existing paid-call permissions still required. This candidate is independent of PR265/266/268, based on actual main175, and does not imply full company/390 acceptance or adoption. New-head CI and receiver verification are separate from the local controls above.
