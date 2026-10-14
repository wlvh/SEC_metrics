# D04 processing dependencies follow the selected producer

Progress on #28, shared with #47. This fixes an update-dependency defect, independently of PR282's Company Facts/source-equivalence change. No source, response, old Result, historical working tree or ledger is rewritten. New business calls:0/0/0.

## Reproduced failure and the small change

Read historical feedback6166004172/6166286926 and its [fixed reproduction1a19c6b5](https://github.com/wlvh/SEC_metrics/blob/1a19c6b55c984d2db48b0f8940c2b494608c3eb9/docs/evidence/issue47_d04_history_consumer_20261010/current-route-dependency/README.md). Actual base main is `ccd9d7c2721e2f8c2116d0ca784178b96571e21f`.

The default D04 registration invokes `ordinary_d04_saved_route.prepare_case`, which consumes `current_d04_result` and `capacity_update_input`. An explicitly supplied historical factory calls `saved_d04_replay` and declares its own processing files instead. `_configuration(..., supplied_case=True)` already omits the default registered producer itself, but still added all of the current D04 route's dependencies. Unrelated changes to those current-only modules therefore caused historical processing again.

**The initial e0c89c94 patch was too broad and is not accepted evidence of safe shared-rule reuse.** Receiver6167168976 traced real historical execution and found shared response/semantic/result rules absent from the historical declaration. Its removal of the entire default route would therefore reuse results after those actual rules changed.

The returned patch chooses conservative optionB: retain the existing complete shared route set for D04, and omit **only `current_d04_result.py` and `capacity_update_input.py`** from the supplied producer's base set. Both are proved current-only in this route. Every other shared/configuration dependency remains; the default producer keeps both helpers too. Explicit declarations can still add either helper when a supplied current producer actually uses it. No claim is made that all remaining unused dependencies have been eliminated. #47 keeps ownership of removing its own extra unused declaration.

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

## Receiver return6167168976

`shared-before.log` reproduces all **five failures** on the initial patch with the actual `historical_d04_case.PROCESSING_FILES`: changes to r6_semantic_review, text_results, regulatory_investigation_candidates, capacity_semantic_review and request_limits falsely reused the prior constructed result. No provider or source change was simulated.

`shared-controls.log` records the returned patch: **92 tests1.480s, zero failures/errors/skips**. The new test uses that real declaration and the real public configuration/controller, keeping source and result construction explicitly synthetic. All five actual shared dependencies now cause processing, then the repeated changed configuration reuses its result with preparation/writing forbidden. The existing tests still prove current-only independence, default/explicit-current dependency retention, and old result bytes preserved.

The receiver's real FY2023 execution/profile is read evidence, not a Root rerun. #47 has returned its own existing-task consumption in PR287/7d99fe1c; those company timings/acceptance belong to its execution. Root does not repeat those16 answers. Earlier receipts and the91-test green remain historical and do not supersede this correction. New return-head CI and receiver verification are separate.

The correction was then normally merged with actual local main `fc0c9a45` (including PR282) without conflicts. That combination passed **93 required tests1.371s, zero skips**, recorded in `shared-main-controls.log`. The remote subsequently accepted Macy-only registry PR286 as65a5d647; that later change touches none of this controller/route/test dependency delta. No claim is made that the earlier93-test execution ran on the later Git SHA.
