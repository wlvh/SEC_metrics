---
{
  "metric_id": "D02",
  "name": "Litigation source disclosures",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "d02_source_disclosures_v1",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "registrant",
    "disclosure_basis": "source_filing_text",
    "period_basis": "annual_filing_disclosures",
    "liability_measurement": "not_inferred"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "liability_measurement"
    ],
    "allowed_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "liability_measurement"
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
        "annual_filing_disclosures": [
          "annual_filing_disclosures"
        ]
      },
      "liability_measurement": {
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
        "liability_measurement"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "quality_rule": {
    "deterministic_text_method": "LEGAL_DISCLOSURE_EXCERPTS_V1"
  },
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": [
      "ITEM_3",
      "ITEM_8",
      "REFERENCED_NOTES"
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
    "formula": "verbatim legal disclosures",
    "confidence": "",
    "notes": "Verbatim legal source text. Exact fact contexts remain in Evidence; no current aggregate liability or case count is asserted."
  },
  "dependencies": []
}
---

# Litigation source disclosures

D02 records the complete supported text-existence disclosure set from the ordinary annual filing, including forward references from Item 3 into its financial notes. Note ranges can follow the numbered form items. Exact source facts retain namespace, concept, ordinal, original period, unit and dimensions in Evidence; an older-period accrual, an unaccrued possible-loss interval or a minimum of zero does not become current total litigation liability. This source-text result makes no aggregate liability or case-count assertion. Positive excerpts do not prove semantic absence elsewhere. Mechanical Evidence rebuilds every supported excerpt and all source ranges, and the existing whole ReviewUnit must approve before TEXT_V1 observations, results and traces are created.

This is an explicit successor draft; it is not the historical D01 method or an activation/publication grant.

Reported fact evidence is supplementary to the source disclosures, not a total liability metric. Each matching fact retains its original namespace, concept, lexical value, unit, entity, period, dimensions and locator. Only supported numeric tags, transforms and independently namespace-checked unit/context structures receive a verified normalized amount. Unsupported facts remain visible as source literals with explicit reasons and no verified normalized value. A valid current-period accrual fact does not block the source-text result or become an aggregate Result. Facts are bound inside the existing coverage/Evidence and rendered in the same whole ReviewUnit; old-period facts are never relabelled to the annual grouping period. The declarative source-fact policy is `catalog/r6/text_results_v2_policy.json`.

The current normalized monetary evidence supports USD and EUR as reported, without conversion. Other unit codes remain source literals with a currency-support reason; the parser does not pronounce them invalid currencies. Unformatted numbers require decimal lexical form, while supported dot-decimal transforms admit a conservative subset with optional three-digit comma grouping. Unsupported grouping or formats retain their original text and do not prevent the supported legal excerpts from being reviewed.
