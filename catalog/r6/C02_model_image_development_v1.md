---
{
  "metric_id": "C02",
  "name": "Board composition image-metadata proposals (development only)",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "c02_model_image_development_v1",
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
    "model_development_method": "C02_BLOCK_TABLE_IMAGE_SOURCE_REFERENCES_V1"
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

# Explicit C02 source-image metadata development successor

This keeps the approved composition-fact meaning and SOURCE_EXCERPTS limits. Complete original text/header grids remain, and every parsed img attribute/location is supplied without prefilling meanings. Pixel content is not supplied. Generic filenames, alt values, or blanks do not prove qualification, nonmembership or absence. Original raw tag spelling/byte spans remain on the host and in pending review context.

Actual source admission reconstructs the complete metadata request. Its exact raw request and response identities are preserved through pending native records, source quotations, full table/image context, save and independent reauthentication on read. Prior plain-block/table Specs, mappers, saved wires and identities stay unchanged; the new request is never represented as an old table request.

This is development-only mechanical mapping. DEVELOPMENT_MODEL or RECORDED_PROGRAM_TEST origins produce PENDING review, empty normalized scope and SYSTEM refusal, no accepted observations, Result, Run, provider attempt or production authority. The recorded-program origin is not a model answer. All unresolved entries and source/pixel limits remain visible. Exact hashes prove their declared program/source relationship, not exhaustive omission-free or semantically correct business output.
