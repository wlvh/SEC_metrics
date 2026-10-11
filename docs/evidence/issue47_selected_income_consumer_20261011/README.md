# Selected historical B03 at the ordinary company entry

This candidate follows main0482aefd and the fixed public PR166/011e8266. It does not update166's review scope. By explicit temporary single-writer agreement, the historical executor extracts the existing B01/B03 calculation from normal_zero_ai_results into selected_income_calculation; the public executor consumes it for current processing/configuration and checks its current consumers. The current resolver still selects latest, resolves its amendments/subject and passes the original default options. Historical selection supplies one actual issuer-year and complete verified primary/XML/CompanyFacts sources. Neither side supplies monetary operands or uses a second Calculator/store/controller.

New historical B03 is dispatched by the same tools/vnext_company.py fiscal-years command and ordinary shared updater/writer/read/export. Current income calculation calls the very same function. Revenue admission, native entity/annual dates/USD, reported precision, complete revenue scope, D&A comparison, one existing direct-candidate retake and contract-amortization relation remain. Historical input explicitly uses finite YEAR_OR_DATE_RELEASE and the existing historical annual reader; no arbitrary regex or dynamic release wrapper is installed into the calculation. Positive observations must match both complete primary and XML. Default revenue components-v1 and all False option defaults remain. No acquisition, model invocation, native Run or publication is created.

Actual saved Marriott FY2024 proves operating income3767m + depreciation128m + amortization255m, divided by reported revenue25100m = **0.1653386454183266932270916335 ratio**, actual2024-01-01..2024-12-31. Four selected observations match both native originals; the existing contract-cost proof excludes a revenue deduction without adding it again. Original FY2024 source reading/reference is reused; it is not a newly invented expected value. First empty company6.472s. A declared processing dependency was then completed, so one necessary normal reprocess6.508s uses the same result ID9cf2d114. Final forbidden factory/shared computation/Calculator repeat1.026s has no computation/new result; independent read0.496s exports the same CSV and preserves state. Summary protects14 result files over the two processing versions; older files remain.

A second actual consumer is Salesforce FY2026 (2025-02-01..2026-01-31). Primary direct D&A candidates3631m and1200m conflict and no native composition resolves them. The exact existing scope check produces B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN, null; a larger amount is not preferred. Empty company5.086s, CLI exit2 is its documented limitation terminal. Same-input forbidden processing repeat1.018s remains PREVIOUS_INPUT_WITHHELD without another result; independent read0.507s keeps null and all saved files. This is a real source refusal, not constructed withholding. No scope failure is converted to N/A or a financial zero.

80 focused current/history/dispatch/state tests pass6.591s, zero skips. This includes actual current Marriott/Salesforce saved-source consumers, source/namespace/unit/period and contract aggregate checks, plus small labelled constructed state tests (success, stable withholding, input/dependency change, missing year and local failure). Additional10 seam/source/dispatch controls pass.082s, zero skips. The old prototype module also ran once:21 failures were an obsolete source_credit exact-string assertion against the already received ordinary source checker, before its summary count; its source/Calc tests otherwise passed. That exact test correction belongs to the public test owner; original failure log is retained. No arbitrary success allowance or business assertion relaxation is used. Verification instrument mistakes and their corrections are retained in verification-corrections.json.

## Reproduce using obtainable code and saved sources

Use this candidate plus its fixed public configuration/test dependency when reported in the PR. The historical source export and restore command are retained in PR52's task/sec-history-five-year branch at bcc0c0bc. Restore to a **new external directory** once, and use the restore output's actual source-inputs root; existing saved sources may be read directly. No new SEC request is necessary.

```bash
# In the retained PR52 checkout; the command is offline.
python3 tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out /your/new/restored-root

# In this candidate checkout, with PyYAML available in the project environment.
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
 tests.vnext.test_selected_income_calculation tests.vnext.test_historical_b03_case \
 tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state \
 tests.vnext.test_current_reported_revenue tests.vnext.test_b03_current_input_scope

python3 docs/evidence/issue47_selected_income_consumer_20261011/verify_company.py \
 --source-root /your/restored/source-inputs --output-root /your/new/review-marriott

python3 tools/vnext_company.py run --company salesforce --period fiscal-years \
 --fiscal-year-start 2026 --fiscal-year-end 2026 --metric B03 \
 --source-root /your/restored/source-inputs --work-dir /your/new/salesforce-state \
 --output-dir /your/new/salesforce-runs
# The real scope refusal exits2; repeat must reuse the same withheld record.
python3 tools/vnext_company.py results --company salesforce \
 --state-root /your/new/salesforce-state --output-root /your/new/salesforce-read
```

Read-only originals; new output roots. actual-company.json contains real arguments, result identities, amounts/native locations, scope refusal and measured phases. Full source assessments remain in ordinary saved task records; they are not a second acceptance package. For mixed selection, the B03 factory coexists with the received B01/B02 range and lodging factories; the small real-dispatch control verifies identities rather than calculating all neighbours again.

## Still incomplete

Marriott FY2021–2023 lack approved full D&A delivery and remain their original nulls. FY2025 has the earlier correct historical reference but was not recalculated for this change; this record proves FY2024's new entry only. Selected B03 amendments and successor subject processing are explicitly IMPLEMENTATION_GAP, not N/A. No complete five-year B03 acceptance, online discovery/completion, shared model success or whole1950-target completion is claimed. Original Runs/results/failures remain readable under their recorded readers; this patch changes new computation and does not migrate old state. Technical reception/CI does not authorize Ready, merge, formal adoption, deployment, active switch or any real call.
