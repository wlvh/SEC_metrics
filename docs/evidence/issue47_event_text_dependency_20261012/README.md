# Historical event amendment reader participates in processing identity

An actual consumer dependency was missing: annual_amendment_scope._source calls text_coverage.build_text_document, but historical_event_cases.PROCESSING_FILES omitted scripts/vnext/text_coverage.py. The ordinary company updater compares the declared processing files before reusing a completed check. An amendment-text parser change could therefore reuse old event/E01 results without applying the changed parsing. E01 already inherits the whole event processing declaration, so it receives the same correction. No public parser/controller/store/runner is changed.

The new method is in the already required HistoricalEventCaseTest class. It uses the real public run_once with the existing explicitly constructed historical state fixture; only source/case/writer outcomes and one digest are controls. No file is corrupted. Before the fix, changing only the text-reader digest fails the expected recalculation assertion (before.log); after adding the one path, the affected selected period reprocesses, subsequent same input returns zero calculation, and the older result directory remains (after.log).64 related event/E01/history/state tests pass0.258s, zero errors/failures/skips. Existing workflows already trigger on this test file and run this class, so no unused runner list or newCI platform is added.

## Actual selected amended E01 task

The real existing ParamountFY2024 E01 task uses already saved original/PartIII amendment/EX99 source bytes. Adding this actual processing dependency legitimately creates one normal processing version; no other fiscal year or metric is processed. First20.714s/exit2 saves the same original333187 resultID/WITHHELD/null and unchanged complete incorporated V2 request. Its exact annual fiscal label,813828reporter,2024Jan1..Dec31 and eight original candidates remain. A missing corresponding response is still E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST; no partial count, oldV1 answer or newsemantic credit is introduced.

The follow-up repeat forbids the E01source/candidate/request factory and both calculators,0.915s/exit2, zero calculation/new resultdir and sameID. Independent official results/CSV process0.421s/exit0 preserves all statebytes. The counts/fullrequestID/commands and protected old/new files are in actual-company.json; all preexisting result files are kept. Source registry/requestledger/manifest hashes unchanged; no refetch or newledger. The execution was main e3 plus the uncommitted dependency/test change, before this evidence commit. Unrelated protected untrackedwork remains; laterSHA is not assigned to this execution.

The driver accepts existing source-root/state-root and a new output-root; use the original complete source root returned by retainedPR52 restore plus its already committed EX99 receipt iffirstrestoring. Existing full source roots are reused, noGET. This is a necessary state migration, not a new financial computation/refreeze or full50event rerun.

```bash
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_event_text_dependency_20261012/verify_e01.py \
  --state-root EXISTING_PARAMOUNT_E01_STATE --source-root SAVED_COMPLETE_SOURCE_ROOT \
  --output-root NEW_EXTERNAL_OUTPUT
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_historical_event_cases tests.vnext.test_historical_e01_company_case \
  tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state
```

Business assertions retained: exact annual and amendment sources, complete original request, noanswer withholding, source/reporting identity, unchanged-input reuse, previous result retention and readonly export. Current mode/corefunctions remain byte-identical. Remaining E01content, sourcesplanner/online, legacywrongCIKpresentationmigration and fullfiveyear business gaps remain.0newSEC/provider/paid/modelcalls, oldRun/source/answer/failure untouched, noauthorReady/merge/adoption/deploy/active. This independent finite repair does not expand reviewing147/189/190 or the Marriottincome candidate.

## Received main3e900c03

PR147/146 were received while this repair was publishing. Their actual merge3e900c03/tree7dadcabd is normally merged without conflicts.76 affected event/E01/history/state/D04case/savedreplay required controls pass0.321s, zero errors/failures/skips. The E01business producer/amendment reader/request algorithms and this one new dependency are unchanged from the actual20.714s migration; no financial/source preparation is repeated solely for this optional-public-input/default compatibility reception. Those actual first/repeat/read phases retain their original premerge version. Main D04's media limitations are unchanged, and reception does not create source/model or business acceptance credit.
