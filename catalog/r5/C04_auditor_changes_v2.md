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
    "resolver": "auditor_change_complete_filings_v2",
    "name_concept": "AuditorName",
    "event_forms": ["8-K", "8-K/A"],
    "annual_amendments": "ordered_current_and_prior_amendments_before_same_period_original",
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

This explicit successor includes original and amended 8-K filings and retains ordered annual amendments for both comparison periods. It does not relabel old 8-K-only evidence or change the v1 resolver.
