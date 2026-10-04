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
    "resolver": "reported_compensation_table_v2",
    "preferred_route": "ecd_peo_total_compensation_v1",
    "fallback": "source_bound_summary_compensation_table",
    "value": "reported_Total_column_for_CEO_or_PEO",
    "period": "explicit_covered_period_or_explicit_fiscal_year",
    "multiple_people_or_values": "withhold_scalar_preserve_all_candidates",
    "currency": "explicit_USD_or_dollar_header_with_unique_document_USD_unit"
  },
  "legacy_projection": {},
  "dependencies": []
}
---

# Reported executive compensation

The ECD route remains preferred and unchanged. This explicit successor reads
the same reported total-compensation definition from a source-bound Summary
Compensation Table when the table is not ECD tagged. It retains the table's
actual Covered Period, including a stated partial year after a transaction;
it does not annualize the amount or substitute a sign-on award, target pay,
compensation actually paid, or a termination-benefit total. Distinct CEO/PEO
rows remain separate candidates. This candidate Spec grants no production
permission and does not modify the historical ECD source strategy.
