# PR147 receives the current main company range

Normal merge of the original PR147 head `16597da7bbbcd126f29820cde7cee873c6c8ce1f` with actual main `c2f48e1ba18e2afab2bf19fa79598f99d3ec33ed` (received PR128). The original D04 selector, saved-response replay and case producer remain unchanged. The company dispatcher preserves main's C03 and lazy B01/B02 fiscal range factories and their separate processing dependencies, while keeping D04's explicit saved package processing input. No source or original answer was changed.

The original mixed D04/B01/C01 test asserted a bare B01 producer and failed after the correct main range integration. `affected-tests.log` preserves that failure (120 tests, one failure, zero skips). The repaired control calls the real range wrapper, verifies the selected year reaches the original statement producer, and checks income+range files, unchanged C01 and D04 factories, and the explicit package dependency. It does not substitute a computed financial answer. The same 120 affected tests pass in 2.340 seconds, zero skips (`affected-tests-repaired.log`).

The company workflow reuses public PR140's `adf915bd` five-job layout and required summary; it retains every actual main selector and trigger, appends main's source-preflight step, and executes both historical D04 modules plus the saved-replay checks. `workflow-check.json` records selector/trigger preservation. No runner or global policy is implemented here. Actual remote execution for this new head is checked separately; the older green head is not credited to this merge.

Independent company `results` on the original Marriott task takes 0.516 seconds, with selection, response replay, both calculators and network forbidden. All 45 existing state files stay byte-identical. FY2023/FY2024 retain their separate `WITHHELD`/null media-coverage results and CIK1048286; the requested FY2026 missing-source state remains readable. This is old-result compatibility, not a new computation. See `independent-read.json`; the original fresh task, zero-compute repeats and full original-call correspondence remain in the parent [primary record](../README.md), under their actual execution versions.

Reproduce the affected tests from this PR head with saved inputs read-only and output in a new directory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
 tests.vnext.test_historical_d04_selection tests.vnext.test_historical_d04_case \
 tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state \
 tests.vnext.test_historical_compensation_case tests.vnext.test_company_fiscal_range \
 tests.vnext.test_selected_source_requirements tests.vnext.test_selected_historical_fiscal_label \
 tests.vnext.test_saved_d04_replay tests.vnext.test_d04_processing_scope \
 tests.vnext.test_ordinary_current_update.SelectedPeriodUpdateTest
```

The parent primary record and `docs/historical_company_usage.md` contain the source restoration, retained PR52 package location and actual same-company CLI commands. The public dependency remains PR146 (saved replay/processing inputs); this merge consumes it, rather than writing another caller or controller. This candidate is still not on main. Four filings' 14 images remain unverified and full D04 media/business acceptance remains unproved. No new SEC/provider/paid calls, no new Run/acceptance, no Ready/merge/adoption/deployment/active change.
