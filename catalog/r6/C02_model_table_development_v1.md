---
{
  "metric_id": "C02",
  "name": "Board composition table-input proposals (development only)",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "c02_model_table_development_v1",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "registrant",
    "disclosure_basis": "source_filing_text",
    "period_basis": "annual_grouping_only",
    "board_as_of": "not_inferred"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "board_as_of"
    ],
    "allowed_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "board_as_of"
    ],
    "exact_enum_aliases": {
      "entity_scope": {
        "registrant": [
          "registrant"
        ]
      },
      "disclosure_basis": {
        "source_filing_text": [
          "source_filing_text"
        ]
      },
      "period_basis": {
        "annual_grouping_only": [
          "annual_grouping_only"
        ]
      },
      "board_as_of": {
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
        "board_as_of"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "quality_rule": {
    "model_development_method": "C02_BLOCK_TABLE_SOURCE_REFERENCES_V1"
  },
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": [
      "GOVERNANCE_DISCLOSURES"
    ],
    "allowed_source_roles": [
      "target_primary",
      "governance_proxy"
    ],
    "renderer": "ORDERED_NEWLINE_V1",
    "max_items": 64,
    "max_text_chars": 64000,
    "review_required": true
  },
  "legacy_projection": {
    "status_exact": "TEXT_QUAL",
    "source_class": "PROXY",
    "formula": "verbatim governance disclosures",
    "confidence": "",
    "notes": "Annual coordinate groups source disclosures. Filing date is bound in Evidence; board measurement as-of is not inferred."
  },
  "dependencies": []
}
---

# Explicit C02 table-input development successor

This draft keeps the approved composition-fact meaning and SOURCE_EXCERPTS limits. It changes input representation only: complete original B blocks and all decoded table text/header grids, with original row and column spans. Images, styles and raw-cell entity spelling are not interpreted by this representation. Empty text is not non-membership; no complete semantic absence or year-end board is inferred.

The actual table request and raw response are preserved under their own external hashes. They are never replaced by a fabricated plain-block request. Native grid and processing assets bind the full admitted source, actual request, source references, source partition and model facts/unresolved. The complete table grid and each cited source block remain inspectable in pending review. The original plain-block Spec, mapper and saved identities remain unchanged.

This is mechanical development mapping only: origin must be DEVELOPMENT_MODEL or RECORDED_PROGRAM_TEST. The latter is explicitly a program fixture, not a model answer. Both produce pending review, no SYSTEM approval, verified semantic observations, Result, Run, real provider attempt, business calls or production authority. Unresolved model entries and rendering limits survive saving and independent source reauthentication on read.
