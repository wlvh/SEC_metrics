# SEC_metrics Round 2 Review Package Manifest

Generated UTC: 2026-07-07T08:01:36Z

## Purpose

This package is the lightweight reviewer handoff for the second round of
de-company-specialization repair. It includes only files needed to review code,
configuration, fixtures, validation outputs, and human-readable reports.

## Include

- `scripts/`
- `tools/`
- `config/`
- `tests/test_sec_pipeline_validation.py`
- `tests/fixtures/`
- `LIGHT_REVIEW_PACKAGE.marker`
- `README_RUN.md`
- `REPORT_十公司财务指标.md`
- `02_指标定义_SEC_10公司单年指标.md`
- `04_验收清单_SEC_10公司单年指标.md`
- `outputs/metrics_matrix.csv`
- `outputs/metric_evidence.csv`
- `outputs/basel_ratio_candidates.csv`
- `outputs/coverage_matrix.csv`
- `outputs/golden_results.csv`
- `outputs/repair_validation_results.csv`
- `outputs/scalability_audit.csv`
- `outputs/exceptions_and_review_items.md`
- `outputs/stratified_audit.csv`
- `outputs/company_resolution.csv`
- `outputs/latest_filings_inventory.csv`
- `outputs/events.csv`
- `outputs/governance_signals.csv`
- `outputs/risk_legal_signals.csv`
- `outputs/companyfacts_crosscheck.csv`
- `outputs/review_package_manifest.md`

## Exclude

- `evidence/`
- `outputs/concept_inventory/`
- `outputs/review_extracts/`
- Python `__pycache__/`
- `.DS_Store`
- generated package archives

## Full Workspace Validation Snapshot

- `python3 scripts/10_run_golden_assertions.py`: PASS, 57 golden rows.
- `python3 scripts/12_validate_repair.py`: PASS, 39 repair validations, `validation_package_mode=FULL_VALIDATION`.
- `python3 tools/check_no_company_literals.py`: PASS, 0 scalability violations.
- `outputs/stratified_audit.csv`: PASS, 19 audit rows.

## Light Package Self-Contained Rerun

- Root `LIGHT_REVIEW_PACKAGE.marker` is required before missing `evidence/` or `outputs/concept_inventory/` may run as a light package.
- `python3 scripts/12_validate_repair.py`: PASS_LIGHT_REVIEW only for an explicitly marked light package.
- Full-evidence checks are explicitly marked `SKIPPED_LIGHT_PACKAGE`, including request log and instance-inventory dependent probes.
- `python3 scripts/10_run_golden_assertions.py`: recomputes included `outputs/golden_results.csv` snapshot integrity and reports `PASS_LIGHT_GOLDEN_INTEGRITY`; raw companyfacts rerun requires full `evidence/`.
- This light package is suitable for code/config/fixture review and stratified audit gate replay. It is not a substitute for complete SEC evidence acceptance.

## Package File

- `outputs/review_package/SEC_metrics_repair_round3_review_20260707T080136Z.zip`
