---
{
  "metric_id": "B10",
  "name": "Occupancy rate",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "percent",
  "source_mode": "ai_table",
  "disclosure_group": "lodging_kpi_table",
  "applicability": {
    "all": ["lodging"],
    "none": []
  },
  "required_claims": {
    "period_role": "current_fiscal_year",
    "property_population": "comparable",
    "operating_scope": "systemwide",
    "geography": "worldwide"
  },
  "forbidden_confusions": [
    "prior_year",
    "percentage_change",
    "company_operated",
    "regional_only"
  ],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {
    "unit": "percent",
    "value_multiplier": "100",
    "status_exact": "MDA_OK",
    "source_class": "MDA",
    "metric_name": "Occupancy rate",
    "concept_or_section": "MD&A occupancy",
    "context_or_dimension": "MD&A occupancy",
    "confidence": "0.85",
    "fiscal_year": "",
    "form": "",
    "formula": "reviewed AI table observation projected from canonical ratio",
    "notes_template": "Reviewed current-period occupancy claim from immutable table-grid evidence.",
    "metric_context_style": "constant",
    "evidence_context_style": "constant",
    "evidence_unit_policy": "projected_result",
    "evidence_extraction_method": "reviewed_ai_table",
    "parser_version": "vnext_projector_v1",
    "allowed_metric_delta_fields": ["formula", "notes"],
    "allowed_evidence_delta_fields": [
      "evidence_quote",
      "extraction_method",
      "parser_version"
    ]
  },
  "dependencies": []
}
---

# Occupancy

AI 负责提出表、行、列、年度与 scope；程序只验证 locator/cell/标签/声明式约束，人类批准经济口径。
