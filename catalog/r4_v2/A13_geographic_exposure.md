---
{
  "metric_id": "A13",
  "name": "International net revenue",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "source_mode": "structured_first_ai_fallback",
  "disclosure_group": "financial_statement",
  "applicability": {
    "all": [
      "financial"
    ],
    "none": []
  },
  "required_claims": {
    "geography_scope": "international"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "geography_scope"
    ],
    "allowed_dimensions": [
      "geography_scope"
    ],
    "exact_enum_aliases": {
      "geography_scope": {
        "international": [
          "International",
          "Total international"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "geography_scope"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": [
    "net income",
    "assets",
    "loans",
    "deposits",
    "maturity schedules",
    "segment-only totals",
    "global total"
  ],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# International net revenue

Owner policy comment 5524085182 defines consolidated full-fiscal-year
international/non-US net revenue in USD, explicitly not net income.
Prefer the issuer-disclosed international total. SourceStrategy still runs
accession_xbrl_v1 first; only STRUCTURED_SOURCE_AMBIGUOUS allows the table
fallback. No independent legacy anchor is claimed.
