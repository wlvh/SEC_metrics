# SEC_metrics Expert Review Package Manifest

Generated UTC: 2026-07-13T06:45:19Z

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

## Current Repository Reviewer Freshness Rule

This rule applies when a new package is generated after the validation-manifest
feature was introduced. It does not retroactively change the contents of the
historical package listed below, which did not include that manifest.

- Read `outputs/validation_run_manifest.json` before any validation or audit
  CSV. Only names in `refreshed_artifacts` are evidence from that run;
  `not_refreshed_artifacts` may still exist as stale files.
- The only repair-validation statuses are `PASS`, `FAIL`,
  `SKIPPED_LIGHT_PACKAGE`, `NOT_EVALUATED_MISSING_EVIDENCE`, and
  `WORKSPACE_INCOMPLETE`.
- Missing evidence is never PASS. In full mode, a critical NOT_EVALUATED blocks
  GO; in light mode, skipped or NOT_EVALUATED remains an explicit caveat.
- Run `python3 tools/check_capability_contract_alignment.py` for mechanical
  anchor/path/symbol structure. A symbol existing does not prove the claim;
  reviewers still grade evidence as direct, partial, structural, or none.

## Historical Validation Snapshot

The counts below describe only the package run recorded on 2026-07-13. They are
not evidence for a later run.

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
  `SKIPPED_LIGHT_PACKAGE` or `NOT_EVALUATED_MISSING_EVIDENCE`; neither is PASS.
- Full numeric acceptance requires a separate full-workspace run. Its manifest
  proves freshness only for the six tracked validation/audit artifacts;
  Golden and metrics require their own rerun evidence. The historical counts
  above are not a substitute.

## Package File

- `SEC_metrics_expert_review_20260709T142516Z.zip`
