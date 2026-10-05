---
{
  "metric_id": "D03",
  "name": "Regulatory investigation source statements and reviewed assessment",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "d03_regulatory_source_assessment_v1",
  "applicability": {"all": [], "none": []},
  "required_claims": {
    "entity_scope": "source_reported",
    "disclosure_basis": "regulatory_investigation_source_text",
    "period_basis": "annual_filing_disclosures"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["entity_scope", "disclosure_basis", "period_basis"],
    "allowed_dimensions": ["entity_scope", "disclosure_basis", "period_basis"],
    "exact_enum_aliases": {
      "entity_scope": {"source_reported": ["source_reported"]},
      "disclosure_basis": {"regulatory_investigation_source_text": ["regulatory_investigation_source_text"]},
      "period_basis": {"annual_filing_disclosures": ["annual_filing_disclosures"]}
    },
    "selection_preference": {
      "dimension_order": ["entity_scope", "disclosure_basis", "period_basis"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "quality_rule": {},
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": ["REGULATORY_INVESTIGATION_DISCLOSURES"],
    "allowed_source_roles": ["target_primary"],
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

# D03 regulatory investigation assessment candidate

Use the complete saved annual primary and current amendments, including native source units. Keep governmental action, recipient, investigated subject, event date and reported status distinct. Preserve historical, conditional, other-entity and unresolved statements. Keyword hits and source references are evidence to assess, not a current investigation finding. This development Spec does not itself authorize calls, absence conclusions, native company Results or production.
