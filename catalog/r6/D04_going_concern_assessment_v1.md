---
{
  "metric_id": "D04",
  "name": "Going concern source statements and defined-scope assessment",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "structured_first_ai_fallback",
  "disclosure_group": "d04_going_concern_disclosures_v1",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "source_reported",
    "disclosure_basis": "going_concern_source_text",
    "period_basis": "annual_filing_disclosures"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis"
    ],
    "allowed_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis"
    ],
    "exact_enum_aliases": {
      "entity_scope": {
        "source_reported": [
          "source_reported"
        ]
      },
      "disclosure_basis": {
        "going_concern_source_text": [
          "going_concern_source_text"
        ]
      },
      "period_basis": {
        "annual_filing_disclosures": [
          "annual_filing_disclosures"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "entity_scope",
        "disclosure_basis",
        "period_basis"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "quality_rule": {
    "deterministic_text_method": "GOING_CONCERN_DISCLOSURE_EXCERPTS_V1"
  },
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": [
      "GOING_CONCERN_DISCLOSURES"
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
    "formula": "source-reported going concern statements",
    "confidence": "",
    "notes": "Preserve current-target statements and their original historical or conditional context. A complete defined-scope assessment with no current doubt is distinct from parsing failure or an assertion of financial health."
  },
  "dependencies": []
}
---

# D04 going concern assessment

Use the complete saved annual primary and all current annual amendments, including native facts and continuations. Current target statements are separate from historical doubt, other entities and conditional risks. An unqualified audit opinion alone cannot establish absence of doubt. Defined-scope absence requires complete source assessment and an effective native Review; an incomplete interpretation is a development or execution gap. This successor does not modify historical control responses or grant production credit.
