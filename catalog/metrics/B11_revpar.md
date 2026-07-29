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
  "review_policy": "human_required_during_poc",
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
    "notes_template": "Reviewed current-period RevPAR claim from immutable table-grid evidence."
  },
  "dependencies": []
}
---

# RevPAR

与 Occupancy、ADR 同属一次 disclosure-group extraction；不得拆成独立 Reader 调用。
