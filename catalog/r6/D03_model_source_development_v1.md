---
{
  "metric_id": "D03",
  "name": "Regulatory investigation complete model proposals (development only)",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "d03_model_source_development_v1",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "source_reported",
    "disclosure_basis": "regulatory_investigation_source_text",
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
        "regulatory_investigation_source_text": [
          "regulatory_investigation_source_text"
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
    "model_development_method": "D03_COMPLETE_MODEL_SOURCE_INPUT_V1"
  },
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": [
      "REGULATORY_INVESTIGATION_DISCLOSURES"
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
    "formula": "source-reported regulatory investigation statements",
    "confidence": "",
    "notes": "A cited process, current involvement and subject identity are separate judgments. A per-request Candidate/Evidence is not a whole-filing conclusion. Defined-scope absence requires an explicit approved rule and native Review; missing or unresolved groups remain development or execution gaps."
  },
  "dependencies": []
}
---

# D03 complete development-model source proposals

This explicit draft retains the approved regulatory-investigation meaning, source-reported subject and annual disclosure scope. It binds every original source unit to exactly one actual development request and raw response, with full visible interpretation context. Findings, dates, recipient/target uncertainty and repeated supporting context remain proposals; source locations and complete byte coverage do not prove their semantics or make them separate investigations. No literal absence, count, current-involvement credit, provider execution or native company Result/Run is authorized by this mapping. The complete original source and individual responses remain available in the review context. Review is PENDING with empty normalized scope and SYSTEM approval disabled. This is separate from the old recorded/live request contract and preserves its Spec/Run identity.
