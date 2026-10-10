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
    "resolver": "proxy_compensation_table_v1",
    "preferred_route": "ecd_peo_total_compensation_v1",
    "fallback": "summary_compensation_table_of_a_proxy_without_inline_xbrl",
    "value": "reported_Total_equal_to_the_sum_of_its_row_components_for_the_CEO_or_PEO",
    "period": "table_year_equals_the_pinned_annual_fiscal_year",
    "multiple_people_or_values": "withhold_scalar_preserve_all_candidates",
    "currency": "dollar_sign_in_the_table_without_foreign_or_scaled_currency_context"
  },
  "legacy_projection": {},
  "dependencies": []
}
---

# Reported executive compensation from a proxy without inline XBRL

The approved C03 source is the DEF 14A, ECD facts preferred. A proxy filed
before pay-versus-performance tagging carries no ECD facts; its Summary
Compensation Table is the same approved source. This successor reads that
table's Total for the registrant's chief executive in the row whose year is
the pinned annual report's fiscal year, and accepts the Total only when it
equals the sum of the other amounts in its row, as Item 402(c) defines it. It
does not read a later proxy's restatement, annualize, or choose between two
chief executives in one year. It grants no production permission.
