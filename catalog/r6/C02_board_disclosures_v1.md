---
{
  "metric_id": "C02",
  "name": "Board composition source disclosures",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "c02_source_disclosures_v1",
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
    "deterministic_text_method": "BOARD_DISCLOSURE_EXCERPTS_V1"
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

# Board composition source disclosures

C02 preserves the complete supported source-statement set in the selected same-registrant governance filing. Its ordinary annual source anchors the reporting container only. The source filing date and proxy report/meeting metadata remain distinct from a board measurement date, which is not inferred. It does not report a year-end board count or use the compensation fiscal year as a governance as-of date. A current proxy is preferred by the normal source selector; a same-period Part III annual amendment is an explicit successor source candidate, with its own raw identity. Exact source excerpts are mechanically replayed and reviewed through the existing whole ReviewUnit. The source date, annual anchor and unknown board as-of are bound in Evidence. No keyword miss proves nondisclosure.

This is an explicit successor draft; it is not the historical D01 method or an activation/publication grant.
