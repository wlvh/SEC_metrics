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
    "max_items": 192,
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

`max_items` is 192 here and 64 in `D01_risk_factor_headings.md`. Nothing else
differs: the method, the required sections, the allowed source roles, the
required claims, the renderer, the character bound and every word of the
business definition are that file's bytes, which the Runs frozen under it keep
declaring.

The bound moved because it decided the outcome for a filing whose headings
fit the character budget. D01 reproduces every emphasized heading in the
complete Item 1A and never a subset, so a filing with more than 64 headings
had no result at all. Measured over every annual report the acquisition has
saved (docs/evidence/issue47_history/d01-item-bound/measured.json), the 43
that reached the heading scan have 26 to 68 headings; Enphase's FY2021 Item 1A
has 68, the only one over 64, and Enphase's other four years have 60 to 62.
192 is the successor ceiling `historical_spec_revision` already proves D02 and
C02 against, not a number chosen for this filing; the character bound stays
the operative limit on how much text a result carries.
