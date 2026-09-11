---
{
  "metric_id": "C03",
  "name": "Executive compensation signals",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "source_mode": "structured",
  "disclosure_group": "governance_proxy",
  "applicability": {"all": [], "none": []},
  "required_claims": {"entity_scope": "registrant"},
  "quality_rule": {
    "resolver": "ecd_peo_total_compensation_v1",
    "concept": "PeoTotalCompAmt",
    "taxonomy": "ecd",
    "period": "exact_target_duration",
    "subject": "single_reported_peo",
    "person_identity": "same_source_PeoName_exact_person_and_period",
    "zero_placeholder": "typed_other_period_person_and_explicit_current_person_required",
    "duplicate_policy": "same_amount_and_at_most_one_specific_person",
    "multiple_people_or_values": "withhold_scalar_and_preserve_all_facts"
  },
  "legacy_projection": {},
  "dependencies": []
}
---

# PEO total compensation

Implements the existing C03 choice of reported principal executive officer
total compensation from DEF 14A ECD XBRL. It is not compensation actually paid,
an average for other executives, or a count of XBRL facts. Exact fiscal period,
registrant, USD unit and reported person remain source-bound. Repeated copies
of the same amount may agree; distinct reported people or amounts cannot be
silently reduced to a single selected executive. No current source discovery,
formal migration, or production permission is granted by this Spec file.
