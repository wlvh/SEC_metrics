# SEC_metrics Expert Review Package Manifest

Generated UTC: 2026-07-09T14:25:16Z

## Purpose

This package is a lightweight expert-review handoff for the current bounded
SEC_metrics repair round. It includes the files needed to review the B06
debt/equity stop-loss, B03/B07 safe approximations, JPM A08/A10/A03/A04/A11/A12
evidence handling, Paramount stub-period semantics, golden expectations, and
validation gates. It also includes the applicability sidecars for out-of-scope
RPO/capacity/lodging probes and the Ford B06 captive-finance candidate.

It is not a full offline SEC rerun bundle. Raw SEC response bodies and parsed
concept inventories stay in the local workspace.

## Include

- `scripts/`
- `tools/`
- `config/`
- `tests/test_sec_pipeline_validation.py`
- `tests/fixtures/`
- `README_RUN.md`
- `REPORT_十公司财务指标.md`
- `SEC_metrics_项目全景与专家指南.md`
- `SEC_metrics_项目全景与指南.md`
- `01_SOP_SEC_10公司单年指标计算_直接SEC.md`
- `02_指标定义_SEC_10公司单年指标.md`
- `outputs/metrics_matrix.csv`
- `outputs/metric_evidence.csv`
- `outputs/spec_implementation_audit.csv`
- `outputs/stub_period_metrics.csv`
- `outputs/rpo_crpo_observations.csv`
- `outputs/capacity_text_signals.csv`
- `outputs/lodging_kpi_probe_failures.csv`
- `outputs/b06_debt_to_equity_candidates.csv`
- `outputs/golden_results.csv`
- `outputs/repair_validation_results.csv`
- `outputs/scalability_audit.csv`
- `outputs/stratified_audit.csv`
- `outputs/coverage_matrix.csv`
- `outputs/companyfacts_crosscheck.csv`
- `outputs/exceptions_and_review_items.md`
- `outputs/implementation_map.csv`
- `outputs/company_resolution.csv`
- `outputs/latest_filings_inventory.csv`
- `outputs/accession_materials_inventory.csv`
- `outputs/events.csv`
- `outputs/governance_signals.csv`
- `outputs/risk_legal_signals.csv`
- `outputs/basel_ratio_candidates.csv`
- `outputs/golden_candidates.csv`
- `outputs/review_package_manifest.md`
- `evidence/requests_log.csv`
- `LIGHT_REVIEW_PACKAGE.marker` inside the zip

## Exclude

- `evidence/accession_materials/`
- `evidence/companyfacts/`
- `outputs/concept_inventory/`
- `outputs/review_extracts/`
- old package archives
- Python `__pycache__/`
- `.pyc`
- `.DS_Store`
- nested `.zip`
- `.sha256`

## Validation Snapshot

- `python3 scripts/10_run_golden_assertions.py`: PASS, 63 golden rows.
- `outputs/metrics_matrix.csv`: 230 rows, 161 valued cells, 69 blank cells.
- `python3 scripts/12_validate_repair.py`: PASS, 75 validation rows,
  `validation_package_mode=FULL_VALIDATION`.
- `python3 tools/check_no_company_literals.py`: PASS, 0 scalability violations.
- `outputs/stratified_audit.csv`: PASS, 20 sampled audit rows.
- `outputs/spec_implementation_audit.csv`: 6 rows mapping changed spec rules to
  implementation locations and validation checks.

## Light Package Rerun Semantics

- The zip contains `LIGHT_REVIEW_PACKAGE.marker`; after extraction,
  missing raw `evidence/` and `outputs/concept_inventory/` are treated as
  explicit light-package limitations, not silent failures.
- In light-package mode, raw-evidence checks may be reported as
  `SKIPPED_LIGHT_PACKAGE` or equivalent light-review caveats.
- Full numeric acceptance remains the current local workspace run summarized
  above.

## Package File

- `SEC_metrics_expert_review_20260709T142516Z.zip`
