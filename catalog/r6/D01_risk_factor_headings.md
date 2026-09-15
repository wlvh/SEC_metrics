---
{
  "metric_id": "D01",
  "name": "Risk factors summary",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "risk_text_v1",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "registrant"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "entity_scope"
    ],
    "allowed_dimensions": [
      "entity_scope"
    ],
    "exact_enum_aliases": {
      "entity_scope": {
        "registrant": [
          "registrant"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "entity_scope"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "quality_rule": {
    "deterministic_text_method": "RISK_FACTOR_HEADINGS_V1"
  },
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": [
      "ITEM_1A"
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
    "source_class": "MDA",
    "formula": "verbatim Item 1A headings",
    "confidence": "",
    "notes": "Source-rebuilt Item 1A heading list; disclosures are not assertions of risk occurrence."
  },
  "dependencies": []
}
---

# Risk factor headings

D01 follows the approved title-level summary option: all emphasized headings and lead titles in the complete original Item 1A are reproduced with source locators. The deterministic proposal does not choose a convenient subset. Mechanical Evidence and the existing whole-ReviewUnit decision bind the source, target, complete set and rendered text. This source-excerpt policy makes no claim that a risk occurred, that no other risk exists, or that an amendment has no effect.
