---
{
  "metric_id": "B11",
  "name": "RevPAR",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
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
    "unit": "USD",
    "value_multiplier": "1",
    "status_exact": "MDA_OK",
    "source_class": "MDA",
    "metric_name": "RevPAR",
    "concept_or_section": "MD&A RevPAR",
    "context_or_dimension": "MD&A RevPAR",
    "confidence": "0.85",
    "fiscal_year": "",
    "form": "",
    "formula": "reviewed AI table observation",
    "notes_template": "Reviewed current-period RevPAR claim from immutable table-grid evidence.",
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

# RevPAR

与 Occupancy、ADR 同属一次 disclosure-group extraction；不得拆成独立 Reader 调用。
