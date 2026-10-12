# D02 malformed block identities report contract failures

This is a bounded follow-up to receivedPR58, not a repeat of H1 or a new legal extraction method. A JSON decision/addition with block_id array/object reaches set/dictionary membership and raises ordinaryTypeError; other nonstrings are mislabeled as unknown block. The model can produce such malformed values without malicious behavior. Two exact-type checks now reject them with D02_REVIEW_DECISION_BLOCK_ID_WRONG_TYPE or D02_REVIEW_ADDITION_BLOCK_ID_WRONG_TYPE before block lookup. They do not stringify, trim, normalize or accept a false identity. Well-typed unknown IDs retain their old failures. No request/prompt/quote20–300/semantic definition or oldRun/answer is changed.

The added method stays in existing AnswerContractTest and covers seven JSON nonstring types in both lists. Initial fixture mistakenly hardcoded b000000 instead of the builder's actual b0, so the addition-side first log is not a clean reproducer; corrected fixture obtains request.must_decide[0]. The corrected pre-fix log has6failures/8TypeErrors. After the two guards, all16 module tests pass0.005s, zero errors/failures/skips. The actual fast workflow already invokes this whole module, so no new selector/runner/CI platform.

Existing12 saved contract fixtures retain identical canonical request bytes and identical original outcomes:8 exact quote-too-long failures/4 passes.14 overlong quotes still have exact source support. Fixture requests are deliberately minimal contract inputs without system_prompt: an initial parity driver trying provider_messages on them raised KeyError, so full historical provider-request parity is not newly claimed here. A complete constructed request produces identical old/new provider messages; the original full-request proof is the received H1 evidence. parity.json states this boundary. Nothing is cropped/reissued or relabeled as accepted law content.

Production consumers import the same legal_review_contract.validate_answer; the retained historical_legal_review shim reexports it. No ordinary companyD02 model/controller/store is added. This mechanical component repair does not deliver that unfinished company chain. Current/future consumers receive an explicit contract error instead of a genericprogram exception; old saved failures remain unchanged under their original identities.

```bash
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_legal_review_contract
```

Actual source/test change is only2guardlines and one existing-class method. Current main0b275 code is the base; no othercandidate scope is expanded. No source reading/acquisition, model/SEC/provider/paid call, agenttrial, Run/acceptance, authorReadymerge/adoption/deploy/active. CorporateD02 semantics, knownPfizer/Marriott content limits and fullfiveyear remain.
