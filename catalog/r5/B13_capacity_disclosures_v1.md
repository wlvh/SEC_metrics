---
{
  "metric_id": "B13",
  "name": "Production capacity qualitative disclosures",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "b13_capacity_disclosures_v1",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "source_reported",
    "disclosure_basis": "production_capacity_source_text",
    "period_basis": "annual_filing_disclosures",
    "utilization_value": "not_inferred"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "utilization_value"
    ],
    "allowed_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "utilization_value"
    ],
    "exact_enum_aliases": {
      "entity_scope": {
        "source_reported": [
          "source_reported"
        ]
      },
      "disclosure_basis": {
        "production_capacity_source_text": [
          "production_capacity_source_text"
        ]
      },
      "period_basis": {
        "annual_filing_disclosures": [
          "annual_filing_disclosures"
        ]
      },
      "utilization_value": {
        "not_inferred": [
          "not_inferred"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "entity_scope",
        "disclosure_basis",
        "period_basis",
        "utilization_value"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "quality_rule": {
    "deterministic_text_method": "PRODUCTION_CAPACITY_DISCLOSURE_EXCERPTS_V1"
  },
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": [
      "CAPACITY_DISCLOSURES"
    ],
    "allowed_source_roles": [
      "target_primary"
    ],
    "renderer": "ORDERED_NEWLINE_V1",
    "max_items": 64,
    "max_text_chars": 64000,
    "review_required": true
  },
  "legacy_projection": {
    "status_exact": "TEXT_QUAL",
    "source_class": "10-K",
    "formula": "verbatim production capacity disclosures",
    "confidence": "",
    "notes": "Capacity-only and related qualitative disclosures preserve their original period, product and facility scope; no numeric utilization is inferred."
  },
  "dependencies": []
}
---

# B13 qualitative capacity disclosures

Explicit successor for the approved Ford/Enphase scope. Retain exact related source statements, including production or manufacturing capacity, operational restrictions and facility scope. A capacity number alone is not utilization. This branch must not hide a sufficient numeric production/capacity pair that the program failed to understand. Confirmed absence requires a saved defined-scope check; a keyword miss is insufficient. Native source evidence, Review and current-input integration remain separate implementation obligations; this Spec draft is not an executed B13 result or production permission.
