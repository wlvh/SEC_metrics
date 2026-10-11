# Historical B03 source consumer: public registry fix plus actual main

This independent development branch normally receives public PR169 `bee55167`, keeps public PR168 `3745c83b` B03 source expansion, and receives actual main `ac3657a8` after the project receiver merged PR143. The two income/source candidates remain unchanged. This is a usable development combination, not another receiving PR or a claim that those candidates are in main.

Only a guide conflict occurs when receiving 169. Receiving main also requires combining the existing historical B03 and now-main C04 dispatch and preserving both workflows' test steps. Both factories and their processing dependencies remain distinct. The public registry helper is used unchanged; there is no second planner, controller, saved-result store or registry validator. The merged production version tested here is local `704885ac`.

`combination-controls.log`: 105 tests in 3.174 seconds, zero errors, failures or skips. Modules are selected source requirements, fiscal range, fiscal labels, registry processing scope, historical B03, history company dispatch, selected history state and historical auditor case. These test the changed seams, including C04 alongside B03, not the full financial population. Existing C04 financial evidence and the receiver-tested main tree are reused; no company/year batch is repeated.

`verify_combined_sources.py` invokes the same `tools/vnext_company.py sources` entrance using the already verified Southwest FY2025 archive. Program registry changes are constructed controls in a temporary directory; actual source registry, request log and request-log manifest are read only. No network or Calculator is allowed. Full plan equality excludes only measured elapsed time.

Actual results (`combined-sources.json`, `combined-sources.log`):

- B03 report-end sources: 1.083 seconds, then 1.082 after an unrelated Pfizer display-name change; both `SAVED_SOURCE_BYTES_AVAILABLE`, identical complete plans.
- B03 issuer FY2025 range: 3.607 seconds, then 3.568 under that change; both `FISCAL_RANGE_RESOLVED`, identical complete plans.
- In both modes the six URLs exactly match the previously calculated B03 task's real `manifest.source_proofs`: metadata, CompanyFacts, original annual primary/index/XML and amendment primary. No unused previous annual or amendment index/XML appears.
- B01+B03 mixed source selection: 1.298 seconds, source-ready and the required union preserved. It does not compute either metric.
- A constructed change to Southwest's program CIK is rejected as `SELECTED_SOURCE_COMPANY_REGISTRY_CHANGED`; an invalid unrelated CIK is rejected as `CURRENT_UPDATE_COMPANY_REGISTRY_ROW_INVALID`. These are registry controls, not financial statements.
- Three actual source metadata hashes remain unchanged. SEC/provider/paid calls are all zero.

The initial recording harness expected the entry function to return exit 2 for the registry controls; that function raises the explicit `ValueError`. `initial-rejection-harness.log` retains this test-harness failure. The harness now asserts the actual exact reasons. No production rejection or financial assertion was relaxed. Complete observed plans are retained locally; the committed receipt contains arguments, exact source URL sets, equality hashes and measured times. The executable verifier recreates them from restored equivalent source materials without depending on those local plan files.

Reproduce from this checkout with the existing environment (replace source root in the verifier with the equivalent archive restored by `tools/vnext_historical_sec.py restore` if needed):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_selected_source_requirements tests.vnext.test_company_fiscal_range tests.vnext.test_selected_historical_fiscal_label tests.vnext.test_registry_processing_scope tests.vnext.test_historical_b03_case tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state tests.vnext.test_historical_auditor_case
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_b03_link_amendment_20261011/source-receiving/registry-scope/verify_combined_sources.py
```

The earlier Southwest calculation/repeat/read, Marriott FY2024/FY2025 B03 and bounded B07 amendment consumer remain in this same major record under their actual program versions. They are not rerun or reassigned to this source-only observation. Source-ready does not establish full D&A, amendment eligibility, source freshness or business acceptance. B07 is still outside this source/acquire planner. Online historical discovery/completion, older Marriott D&A, unresolved financial families, model responses/images and the full five-year obligation remain. No author Ready/merge/adoption/deployment/active action.
