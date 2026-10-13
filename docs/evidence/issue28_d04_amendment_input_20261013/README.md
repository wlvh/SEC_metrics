# D04 complete annual/amendment input comparison

This public update successor starts from actual main `f767dac2efb90a0c97e195a933cd743f38f414be` (tree `69960225cb8832ab1228de24f352a6de34cc680d`). It closes the specific comparison limitation recorded in the [actual Southwest company evidence](https://github.com/wlvh/SEC_metrics/blob/6a3b509aab3d0a2119396dbeb3df818b3dfa9efc/docs/evidence/issue28_southwest_d04_company_20261013/README.md). The existing full company result and original six model answers are retained; they are not replayed or re-signed for this comparison change.

## What changes

The single-document text reader deliberately marks a `10-K/A` as `INCOMPLETE / TEXT_AMENDMENT_SOURCE_SET_REQUIRED`. Previously the full-task fingerprint called that reader separately for each annual source and rejected the amendment even when the original report and complete selected amendment set were present.

The full-task entry now rechecks the saved submissions selection and target CIK, so a supplied prepared input cannot omit a selected amendment. It reads every original and amendment, checks the actual document form against the selected form, and verifies their source proofs. Its explicit parser option permits only a well-formed annual amendment whose sole incomplete reason is the full-set requirement and whose reference role is `annual_amendment`. All identity, period, truncation and other structural checks remain. The parsed document still says `INCOMPLETE`; no whole-report, absence, semantic or result credit comes from this option. Default single-document behavior remains unchanged.

Visible blocks, native facts/contexts/units, tables, media, relationships, quotation ownership, opaque embedded script bodies and original byte locators remain in the comparison. An empty external script can be outside this fixed D04 input; changed relevant content cannot disappear. This is not a general equivalence rule for other metrics.

## Actual tests and real saved input

`before-controls.log` records two errors and two failures before the repair: full amendment comparison fails, the new parser option does not exist, a prepared caller can omit an amendment, and an amendment catalog entry can point to a 10-K body without a form mismatch refusal. These are actual small recorded-source controls, not paid calls.

`after-controls.log`: 62 relevant checks /1.272s /zero failures/errors/skips. `update-controls.log` retains a test-harness `copy` import mistake; only that harness expression was corrected. `update-final-controls.log` then passes all 18 controller checks. `final-controls.log` passes 106 parser, text coverage, D04 company/provenance/processing and ordinary-update checks /1.691s /zero failures/errors/skips.

The new controller test uses the real recorded-source selection and complete amendment parser with the existing update writer branch. Only its business-result writer is explicitly constructed: same task after a script-only amendment change refuses any assessment replay; the following unchanged check refuses parsing too; visible disclosure changes trigger processing; the old saved record remains exact. This mechanical integration does not establish model accuracy or a new business conclusion.

`verify_saved_input.py` actually calls the company's existing `_task_input` on the original saved Southwest FY2025 source set. The selected forms are 10-K `0000092380-26-000004` and 10-K/A `0000092380-26-000006`. Selection takes **1.348s**, full input assessment **1.791s**. The former comparison-unavailable reason is absent and both documents contribute to the task identity. No metric calculation or model request runs.

Two isolated copies of the actual amendment then check the parser: an added empty external script has equal task content; an added visible disclosure changes it. All 169/170 original-byte spans respectively remain locatable. These variants are constructed controls, never registered as real SEC sources or company/model results. Their combined baseline/variant parse takes **0.239s**. `saved-input.json` records actual code/data roots, base commit, working-tree hashes and 127 protected originals/ledger files unchanged. New provider/paid/SEC **0/0/0**.

These timings describe different operations from the earlier 101-second complete company assessment; they are not a claimed speedup ratio. The measured saved-input run is base f767 plus its explicitly recorded working-tree differences, not a committed-SHA run.

## Existing records and usage

New fully processed D04 results can now save this complete input comparison. The established update branch can reuse them after a proven task-equivalent raw change. Existing results that lack a usable fingerprint continue through the established full processing path; no old record or original answer is altered to manufacture reuse. Parser/config changes are already consumed by the D04 processing configuration, so this repair does not silently claim compatibility with every old comparison. Failure, missing source, changed selection/config and genuinely changed input remain processing responsibilities.

```sh
PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_ordinary_task_input tests.vnext.test_text_coverage tests.vnext.test_current_d04_company tests.vnext.test_d04_provenance_reuse tests.vnext.test_d04_processing_scope tests.vnext.test_ordinary_current_update
PYTHONPATH=scripts:. /path/to/python-with-dependencies docs/evidence/issue28_d04_amendment_input_20261013/verify_saved_input.py --source-root /absolute/original/source-inputs --ledger-root /absolute/original/issue28-ledger --receipt /absolute/new-comparison-receipt.json
```

This changes no shared selector or #47 consumer, no metric definition, model configuration, budget or opportunity. It does not recreate the original D04 installation/cold-read chain, certify omitted disclosures, adopt a company result or complete390/automatic updates. Receiver review and exact-head remote CI are separate from the executions recorded here.

## Reception of main's completed source delivery

While this work was being verified, the receiver merged PR218/223 as actual main `ff59413289e0b0530aa643ecd7b7d9c17ffc1e77` (record [6135612075](https://github.com/wlvh/SEC_metrics/pull/223#issuecomment-6135612075), actually read). This branch normally merges that main without a conflict. `received-main-controls.log` reruns the 106 affected controls on the combined worktree. The D04 implementation and real-input measured blobs are unchanged by the merge; the f767 real-source timings remain tied to that original execution, not re-signed as an ff594 run. The receiver's separate E01 failed-source URL observation is retained as a subsequent public source repair, not folded into this D04 increment.
