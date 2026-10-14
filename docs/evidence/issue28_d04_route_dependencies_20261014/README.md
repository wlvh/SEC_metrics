# D04 processing dependencies follow the selected producer

Progress on #28, shared with #47. This fixes an update-dependency defect, independently of PR282's Company Facts/source-equivalence change. No source, response, old Result, historical working tree or ledger is rewritten. New business calls:0/0/0.

## Reproduced failure and the small change

Read historical feedback6166004172/6166286926 and its [fixed reproduction1a19c6b5](https://github.com/wlvh/SEC_metrics/blob/1a19c6b55c984d2db48b0f8940c2b494608c3eb9/docs/evidence/issue47_d04_history_consumer_20261010/current-route-dependency/README.md). Actual base main is `ccd9d7c2721e2f8c2116d0ca784178b96571e21f`.

The default D04 registration invokes `ordinary_d04_saved_route.prepare_case`, which consumes `current_d04_result` and `capacity_update_input`. An explicitly supplied historical factory calls `saved_d04_replay` and declares its own processing files instead. `_configuration(..., supplied_case=True)` already omits the default registered producer itself, but still added all of the current D04 route's dependencies. Unrelated changes to those current-only modules therefore caused historical processing again.

The patch adds the current route's dependency set only for the default producer. Explicit producers continue to retain their **declared** `processing_files`, producer source version, processing inputs, shared source/parser/writer/Spec dependencies and source checks. An explicit current factory may declare the same `ordinary_d04_saved_route.processing_paths()` set: the regression does so and proves that either current module's change still triggers processing. This is not a blanket `supplied_case` waiver or automatic dependency discovery. As before, a wrapper using a producer must declare that producer's real processing dependencies; arbitrary undeclared indirect dependencies are not inferred.

No current/historical controller fork, callable inspection platform, old-configuration rewrite, hash whitelist or unconditional reprocessing is added. Existing records keep their old configuration. A record with a genuinely different recorded producer/dependency shape can take the ordinary processing path once; this patch does not silently re-sign it or promise zero work for every prior configuration.

## Tests and observed consumer boundary

`before.log`: two current-only-file subcases fail on the unmodified controller. Repeated processing is made an error, so the red tests expose the actual attempted factory call.

`controls.log`: **91 required tests,1.417s, zero failures/errors/skips**:

```sh
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py \
  tests.vnext.test_ordinary_current_update \
  tests.vnext.test_saved_result_registration \
  tests.vnext.test_current_d04_company \
  tests.vnext.test_historical_d04_case
```

New tests use real configuration and the real controller, with explicitly constructed source census, producer and result writer. They exercise first stable withholding → same-input reuse with factory/write forbidden → changed dependency → reuse again. Historical current-only changes no longer process; default and explicitly declared current processing still do; actual shared replay/acceptor changes still process. Old result bytes and directories remain. They are not financial content validation, fresh source acquisition, or model acceptance.

The initial wider command named two nonexistent test modules and failed with two loader errors; `initial-command-error.log` retains that invocation. The corrected command above passed, without deleting or weakening a business assertion.

The peer's exact published small replay/control script was read, saved only to a temporary path and executed with network forbidden. Its actual small replay still calls neither current producer helper:

| Observation | Only this public patch | Plus simulated removal of one unused historical declaration |
|---|---|---|
| Public configuration includes either current-only helper | no | no |
| `capacity_update_input` change: historical factory calls |1|1|
| `current_d04_result` change: historical factory calls |2|1|
| Default current configuration reacts to either change |yes|yes|
| Old constructed result directories retained |yes|yes|
| Elapsed time |0.140734s|0.131089s|

Receipts are `public-only.json` and `consumer-combination.json`. The second execution patches **only the imported historical declaration in memory**, removing its extra unused `current_d04_result` entry. It does not edit the historical core/branch or claim a delivered historical fix. Thus the residual dependency is explicit: #47 must remove that one unused declaration and verify its own selected existing consumer task. Root does not repeat sixteen saved responses or claim this constructed check proves an existing company result. No financial/media/absence credit is granted.

The supplied-reader/writer and current D04 source-equivalence behavior are unchanged. Unchanged source-material and complete-company evidence is reused at its original version and boundary; receiver verification of this finite dependency change remains separate.
