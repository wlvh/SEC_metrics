# B06 consumed text parser in processing identity

Progress on #28. This is an independent follow-up to received PR189/190, not an expansion of those candidates.

`current_b06_case.PROCESSING_FILES` declared annual_amendment_scope but omitted its actual `text_coverage.build_text_document` dependency. The inline-note and selected-release tuples inherit this list. The new red regressions show both the absent path and unchanged actual B06 configuration when only the consumed text reader hash changes. This can reuse a stale completed conclusion after a parser change.

The production change is one path in the existing tuple. No source selector, debt/equity scope, Calculator, controller, cache platform, Rule/Requirement chain or registry policy changes. Existing current, inline-note and selected-release consumers inherit it. It does not make missing financing relationships complete or add a debt value.

## Actual checks

- `before.log`: 2 required tests, 4 subtest failures, zero skips. Actual main c2267ede, no source calls.
- `after-controls.log`: 66 required current-B06/update controls, 0.379s, zero errors/failures/skips. The actual configuration now changes with the text parser version. Existing source/configuration-change, withheld reuse, success preservation, selected-period and interrupted-write tests remain.
- `company-receipt.json/.log`: a new isolated Marriott FY2025 task through the actual `tools/vnext_company.py run --source-root` entry. First3.458s, repeat0.121s with the actual B06 factory set to raise if called, independent subprocess `results`0.122s. Existing result a847e602 is NOT_MEANINGFUL/null because the source-verified denominator is nonpositive, at 2025-12-31; debt completeness is explicitly NOT_EVALUATED, not asserted as proved. This is one real consumer, not all B06 inputs or an amendment-specific content acceptance. Nine result/pointer files are byte-identical across repeat and reading, with no second result.

The actual source root is `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`; code root is the dedicated `issue28-b06-text-dependency/SEC_metrics` checkout. The new state/output paths and commands are in the receipt. No network sockets were allowed during run/repeat, only the repeat factory is replaced with rejection; calculation/save are real. Independent reading uses the formal CLI in a new process. Tests used the uncommitted one-path/test patch over c2267ede, as recorded, not a future SHA.

## Reproduce

```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_current_b06_case tests.vnext.test_ordinary_current_update
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue28_b06_text_dependency_20261012/verify_company.py --source-root SOURCE_INPUTS --state-root NEW_STATE --output-root NEW_OUTPUT --receipt NEW_RECEIPT.json
```

No new SEC/provider/paid calls, source writes, ledger changes, old result rewrites or new retry opportunities. The original195 claims remain143/143/52, remaining97/97/28. Actual main then advanced only with the received D04 historical guide (#194) to df1c614f. The normal main combination retains the tested production/test blobs exactly; main-combination.json records this evidence reuse, with no repeat of the financial source. Receiver review is still needed; existing B06 values/applicability and unresolved content retain their original acceptance boundaries. No formal adoption, merge, Ready or production permission is claimed.
