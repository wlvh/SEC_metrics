---
{
  "metric_id": "C04",
  "name": "Auditor changes",
  "kind": "direct_numeric",
  "canonical_unit": "flag",
  "reported_unit": "flag",
  "source_mode": "structured",
  "disclosure_group": "auditor_report",
  "applicability": {"all": [], "none": []},
  "required_claims": {"entity_scope": "registrant"},
  "quality_rule": {
    "resolver": "auditor_change_dual_source_v1",
    "name_concept": "AuditorName",
    "name_normalization": "ignore_case_punctuation_and_whitespace",
    "amendment_fallback": "same_cik_same_period_original_only_if_target_name_absent",
    "absence": "same_current_prior_names_and_complete_fiscal_8k_set_without_item_4_01",
    "positive": "different_current_prior_names_or_filed_item_4_01"
  },
  "legacy_projection": {},
  "dependencies": []
}
---

# Auditor changes

Uses the existing C04 two-source definition: filed Item 4.01 and same-registrant
current/prior AuditorName facts. A year-end name comparison alone cannot rule
out an intervening auditor change. Current amendments precede original-report
fallback, and conflicting current names cannot be hidden by that fallback.
Source discovery, Requirement/Run acceptance and production permission remain
separate from this source adapter.
