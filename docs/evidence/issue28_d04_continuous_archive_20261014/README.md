# Original #28 D04 archive reaches the saved-company entry

Progress on #28, shared with #47. The existing public archive reader now understands the original #28 continuous-call artifact format as well as the existing #47 historical format. It does not rewrite old bindings/answers, grant new provider executions, create another controller, or change D04 business semantics.

## Actual user path

The formal company CLI now reads Marriott FY2025's four original live call groups115–118 from a read-only archive, selects the actual annual source, checks all original request/response/acceptance groups, saves an ordinary result, reuses it without preparing/revalidating the groups again, and exports CSV from an independent `results` process.

| Same scenario | Observed outcome | Wall time |
|---|---|---:|
| Initial completed processing, after the preserved local/profile failures | WITHHELD; all four original groups represented |9.437545s|
| Same complete input, case preparation and response reading forbidden | PREVIOUS_INPUT_WITHHELD; same Result, no second result directory |0.137876s|
| Independent process `results` with CSV/evidence export | Same FY2025 period/Result and source references |0.146197s|
| Last group's terminal missing from a separate archive | INPUT_OR_EXECUTION_FAILED; no partial Result |6.029108s|
| Restore original complete archive, processing forbidden | PREVIOUS_INPUT_WITHHELD; same original Result |0.118030s|

Result `sha256:936b92e4d127b2398fbbf06001d5d95866761ac2f37d4f40876236179f84a305` covers2025-01-01–2025-12-31, accession0001048286-26-000007/CIK1048286. Its reason is **D04_SAVED_FILING_MEDIA_COVERAGE_NOT_VERIFIED**. The CSV explicitly says saved complete model **text** groups were read but images/other media are not verified. This is not a finding of whole-filing absence, a health assurance, new model accuracy, or adoption. The nonempty doubt-disclosed path is covered with clearly isolated constructed responses; no real positive disclosure is invented.

The seven result files remained unchanged on repeat/recovery; independent reading preserved23 state files at its execution point. The missing-group test retained the old Result and all five prior failure/check terminal files.76 original call/ledger/source files remained unchanged; all operations used0 provider/paid/SEC calls.

## What changed and what stayed

The format is chosen from the saved binding's record type. Both formats keep their own exact binding, intent, terminal, execution, usage, original counts and original receipt IDs. Unknown/mixed formats fail. Both share the same issuer/filing/period, complete partition, raw request/response, plan/execution/acceptance, and current semantic checks.

The original #28 profile differs from #47 in specific places established by the original generator and actual call115:

- `CONTINUOUS_CALL_ALLOWANCE`, `CONTINUOUS_CALL_INTENT`, `CONTINUOUS_CALL_TERMINAL`; intent links through `binding_id` and must be a PROVIDER call.
- The old zero-retry policy and provider request identity are in the original plan. No corresponding field is inserted into an old intent.
- Intent `request_digest` is the existing **business-request digest**, not the HTTP body hash. Reuse `continuous_semantic_calls.request_digest`, using the original wire's output-token setting. The HTTP body still separately matches its exact plan hash and provider identity.
- Counts and nullable usage remain original data; reading does not charge them again or turn unknown cost/usage into zero.

The #47 profile retains its original fields and checks. This is a read-only input adapter, not a restored live allowance or new Requirement/trust platform. Existing same-issuer/filing/source selection and media withholding are unchanged. #47 owns its processing declarations/consumer; the added branch uses `request_limits.py`, which was directly notified for that declaration.

## Actual commands and material

Use Python with the existing tokenizers0.22.2 dependency. The host's tested interpreter is `/private/tmp/issue28-d03-tokenizers-20261013/bin/python`. No new dependency was installed for this batch. The source root is read-only; the state/output directories are separate:

```sh
TASK_PYTHON=/private/tmp/issue28-d03-tokenizers-20261013/bin/python
"$TASK_PYTHON" tools/vnext_company.py run \
  --company marriott_international --metric D04 --period fiscal-years \
  --fiscal-year-start 2025 --fiscal-year-end 2025 \
  --source-root /Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs \
  --saved-call-package /Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d04-continuous-package-20261014/marriott-fy2025-original-calls.tar.gz \
  --work-dir /absolute/new/review-state --output-dir /absolute/new/review-output
"$TASK_PYTHON" tools/vnext_company.py results \
  --company marriott_international --state-root /absolute/new/review-state \
  --output-root /absolute/new/independent-read
```

The completed host state is `.../d04-continuous-package-20261014/tokenizer-verified/state`; original actual reports and independent CSV are under `.../d04-continuous-package-20261014/business-digest/`. `company-summary.json` has the exact arguments, source/code roots, source-file hashes and measured times. Initial/repeated `run` went through the real CLI `main` argument parsing and implementation in one process, with socket/DNS/claim attempts forbidden; only the repeat preparation/response functions were made errors. Independent `results` was a fresh process using the formal command. Source selection, calculation, persistence and writer were not mocked.

The archive has73 original regular members,19,845,117 bytes, SHA256 `c0878e965004499b60f339aa5f1ef11238bb58f1467982587b58d1138ab7c671`. It was assembled privately from the existing binding and four calls' original evidence, plus their terminals, without altering any member. It is not committed to Git, a replacement ledger, a new model result or a hidden answer in a SEC source package. The original archive and failed states remain. `archive-index.json` records membership/byte-preservation context.

## Tests, failures and limits

`before.log` preserves the old reader rejecting the valid constructed continuous profile. `controls.log`: **67 tests0.877s, zero failures/errors/skips**:

```sh
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py \
  tests.vnext.test_saved_d04_replay \
  tests.vnext.test_historical_d04_selection \
  tests.vnext.test_historical_d04_case \
  tests.vnext.test_current_d04_company \
  tests.vnext.test_d04_native_assessment
```

Controls include nonempty current doubt under both record types, mixed terminal type, wrong channel/requirement/digest, unknown or nonzero retry setting, and a constructed prior2048-output-token request interpreted using its original setting instead of today's default. No real4096/8192 comparison was executed.

`prior-attempts.json` retains the exact failed report paths/hashes. The first company attempt used the host default Python and failed for missing tokenizer. The first compatibility draft then incorrectly expected a retry field and request identity in the intent, and treated the ledger digest as a wire digest. Those real-entry failures were retained, not called source/model errors or successes. A complete field/semantics comparison with the original generator corrected the mapping; the final completed run reused the same failed test state and left those terminals intact. It did not retry a provider request.

Actual base was main `fc0c9a45bad2b9c8ee312e862b68e553463b48e3` plus the two named source/test files. The final production reader's SHA equals the completed run's recorded source SHA. One test-only prior-output-budget control was added afterward; the real-company chain was not repeated for that unchanged production behavior. Current CI/receiver acceptance is separate.

Only Marriott FY2025 was exercised through the actual new archive path. The other nine original sources and93 total response groups are available as prior material, not newly replayed here. This does not resolve Paramount's current source-period conflict, media coverage, D03/B13, or390 acceptance. No Ready, merge, production/adoption or quota authority is added.
