# D03 bounded development extraction and non-action aggregation

This batch exercises one existing JPMorgan FY2025 group using the current input and public candidate-response validator. It is development-model work, not a DeepSeek execution, complete company result, absence finding, or production acceptance. There were **0 provider / paid / SEC business calls**.

## Input, independent context and content checks

The fixed effective request is `sha256:c4c7d6b1e90979d23a668cece33307b35f1f23624f8338b3fbaac1420267d4f2`, derived from original request `sha256:d68f64eb9308dee3ea53beaa09abaedf950af570506507cfee764f4598cef4e2`. Its 471,433 input bytes have SHA256 `1ecd2819b28c64ae65a7113dc3852a58c84fb2e4af922f8ba606bbab860c4b4d`. Three complete supplied units retain all 1,320 visible blocks and 33 mandatory candidates; no filtering or source split was introduced for this trial. The old source-fact location is a candidate, never a program-proved current investigation.

Exact input/spec, source/original request, answers and original execution logs remain at:

```text
/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-development-jpm-20261014/
/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-anchor-20261014/
```

The registered original sources remain in `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs`. This report publishes the small response/reference/log material, not another copy of the full source archive. `input-manifest.json` fixes unit identities and discloses prior routing/recorded-debug use. This is **not held-out material**. The saved development input is not a production source package and does not make old model answers mandatory source inputs.

The parent wrote the limited content reference before the independent context started. That context received only the effective request, MetricSpec and input manifest, without the reference or earlier answers. Its full sequential reading is reported in `extraction-log.json`; tool counts are extractor-reported, not an independent runtime audit. Original extraction used 15 tools. One feedback-assisted review used two more, for 17 total and two final messages; no second agent or resource reset was used.

The parent checked the cited original passages against the approved D03 meaning, rather than merely accepting the model labels:

| Original source | Original response and content finding | Bounded revision / remaining limit |
|---|---|---|
| 140 and 339–340 | The defined registrant reports current aggregate involvement in governmental investigations/enforcement. The answer retains this nonempty current disclosure without inventing a case count, start date, guilt, or named matter. | Unchanged. This is a proposal, not a company result. |
| 343–344 and 864 | Past resolutions/admissions are separated from possible future consequences. | Unchanged; no inferred current case status. |
| 348/351 | Initial `OTHER_ENTITY` asserted too much: generic financial institutions does not prove the registrant is excluded. | Exactly one finding changed to historical, subject `UNRESOLVED`, status `NOT_STATED`. All other answer content is unchanged. |
| 174/187/274/308–314/342/355–366/374/384; 504/507, 681/690, 729–730, 782/789, 870–885 | Regulatory powers and conditional consequences do not independently assert an actual current government investigation. Mixed past/future passages retain separate findings. | No unconditional absence conclusion. |
| 172 and 692–693 | OCC consent-order obligations alone lack an established investigation link; investigating a possible cyber attack is internal incident context. | Non-action findings remain explicit and source-linked. Their compatibility timing placeholder must not create a false unresolved action. |
| 997 | The supplied group refers to Note 30 outside this group. | Unresolved in both answers. Other company groups are not filled with synthetic answers. |

This is a limited checkpoint comparison, not an exhaustive gold annotation or measured recall/accuracy. The revision is feedback-assisted and does not prove prompt improvement or holdout performance.

## Actual processing and the small defect

`regulatory_fact_review.validate_candidate_response` rebuilt and authenticated the full actual source for both saved responses, with network, DNS and `CallLedger.claim` forbidden. Original processing took **42.310320s**, revised processing **41.923801s**. Each normalized to 13 findings (10 explicit plus three context shorthand findings). Reference tokenizer counts were **1,780 / 1,789**, with no tokenizer fallback, within 4,096; actual provider usage/cost are **null**, not zero. Six input/source/original-request/ledger/binding files were unchanged.

Those source-validation executions used local head `17fa27f78866d243aff760cd71990e9f24ca106c`, whose D03 validator bytes were unchanged from the accepted base. They are not claimed as executions of the later commit. `postprocessing-summary.json` records the identities and compact observations.

The complete-interpretation aggregator exempted `context_only_source_indices` shorthand from action timing review, but failed to exempt an equivalent explicit `OTHER_MEANING + NOT_AN_ACTION_STATEMENT`. The latter normalizes to a compatibility `timing=UNRESOLVED` even though no action is being claimed. Consequently valid explicit background at 172 and 692–693 was falsely marked for action review.

The patch treats the two typed representations equally. It adds no English rules, changes no categories, bypasses no source/response/coverage checks, and grants no native or absence credit. Explicit `UNRESOLVED` findings, unresolved status/subject/timing on actual actions, and unit-level uncertainty continue to block.

The saved-source observation compares the old and new small predicate against the already source-authenticated normalized findings, using the actual shorthand indices. Exactly the two explicit non-action findings change. That observation is not a rerun of source authentication or the complete 38-group company interpretation. Both actual answers still retain the Note 30 unresolved condition; the revised generic-subject finding also remains uncertain.

## Regression scope and reproduction

Base of the patch and small tests: `7446ef978738370edf9e601387aff42094256a6d`, plus the two named source/test files. `nonaction-before.log` preserves the failure before the fix. `controls.log` records **21 tests in 0.040s, zero failures/errors/skips**:

```bash
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py \
  tests.vnext.test_d03_interpretation_source_root \
  tests.vnext.test_d03_recorded_source_root \
  tests.vnext.test_d03_source_root_seam \
  tests.vnext.test_d03_raw_navigation
```

New tests enter `validate_complete_interpretation` with controlled preparation/response-parser outputs: explicit and shorthand background equivalence; a nonempty current proposal plus valid context; and uncertainty that must remain. They test aggregation behavior, not source parsing or independent content correctness. Existing tests retain full-group-set, changed-source, marked-root, interrupted-record and no-native-credit checks. Unchanged recorded/source-root long-chain evidence is reused; no whole-company or 38-group model replay was performed.

Current main was refreshed to `ccd9d7c2721e2f8c2116d0ca784178b96571e21f`; its intervening changes are D02-only and do not alter this patch's D03 source/test dependencies. This statement describes inspected differences, not a new exact-head source-material run.

## Remaining delivery and authorization

This is initial extraction plus one bounded substantive correction, now closed as a development batch. Do not run another renamed trial on the same input to create apparent accuracy. D03 has no new real-call authorization: the current configuration still excludes it from `live_metrics`. A valid group proposal does not supply the other company groups, provider execution evidence, native review/Run, or company CSV. Those are remaining responsibilities, not evidence of non-applicability. Existing D04/190 results and all failed opportunities remain untouched.
