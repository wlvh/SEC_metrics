---
{
  "metric_id": "B06",
  "name": "Debt-to-equity",
  "kind": "derived_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "ratio",
  "source_mode": "structured",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "consolidated"
  },
  "inputs": {
    "debt": {
      "choose_first": [
        {
          "extraction_role": {
            "approved_concepts": [
              "us-gaap:DebtAndCapitalLeaseObligations",
              "us-gaap:LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"
            ],
            "cardinality": "exactly_one",
            "quality": "EXACT"
          }
        },
        {
          "derived_role": {
            "op": "add",
            "inputs": {
              "current": {
                "approved_concepts": [
                  "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent"
                ],
                "cardinality": "exactly_one"
              },
              "noncurrent": {
                "approved_concepts": [
                  "us-gaap:LongTermDebtAndCapitalLeaseObligationsNoncurrent"
                ],
                "cardinality": "exactly_one"
              }
            },
            "args": [
              "current",
              "noncurrent"
            ],
            "quality": "EXACT",
            "quality_reason": "COMPOSED_FROM_EXACT_COMPONENTS",
            "guards": [
              "same_accession",
              "same_period",
              "same_entity",
              "compatible_units"
            ]
          }
        },
        {
          "derived_role": {
            "op": "add",
            "inputs": {
              "current": {
                "approved_concepts": [
                  "us-gaap:LongTermDebtCurrent"
                ],
                "cardinality": "exactly_one"
              },
              "noncurrent": {
                "approved_concepts": [
                  "us-gaap:LongTermDebtNoncurrent"
                ],
                "cardinality": "exactly_one"
              }
            },
            "args": [
              "current",
              "noncurrent"
            ],
            "quality": "EXACT",
            "quality_reason": "COMPOSED_FROM_EXACT_COMPONENTS",
            "guards": [
              "same_accession",
              "same_period",
              "same_entity",
              "compatible_units"
            ]
          }
        },
        {
          "derived_role": {
            "op": "add",
            "inputs": {
              "current": {
                "approved_concepts": [
                  "us-gaap:FinanceLeaseLiabilityCurrent"
                ],
                "cardinality": "exactly_one"
              },
              "noncurrent": {
                "approved_concepts": [
                  "us-gaap:FinanceLeaseLiabilityNoncurrent"
                ],
                "cardinality": "exactly_one"
              }
            },
            "args": [
              "current",
              "noncurrent"
            ],
            "quality": "EXACT",
            "quality_reason": "COMPOSED_FROM_EXACT_COMPONENTS",
            "guards": [
              "same_accession",
              "same_period",
              "same_entity",
              "compatible_units"
            ]
          }
        }
      ]
    },
    "equity": {
      "choose_first": [
        {
          "extraction_role": {
            "approved_concepts": [
              "us-gaap:StockholdersEquity"
            ],
            "cardinality": "exactly_one",
            "quality": "EXACT"
          }
        }
      ]
    }
  },
  "formula": {
    "op": "divide",
    "args": [
      "debt",
      "equity"
    ]
  },
  "top_level_guards": [
    "same_accession",
    "same_period",
    "same_entity",
    "compatible_units",
    "denominator_positive"
  ],
  "quality_rule": {
    "resolver": "debt_equity_structured_v1",
    "point_in_time": true,
    "direct_totals": [
      "DebtAndCapitalLeaseObligations",
      "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"
    ],
    "same_family_pairs": [
      [
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
        "LongTermDebtAndCapitalLeaseObligationsNoncurrent"
      ],
      [
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent"
      ],
      [
        "FinanceLeaseLiabilityCurrent",
        "FinanceLeaseLiabilityNoncurrent"
      ]
    ],
    "equity_concepts": [
      "StockholdersEquity"
    ],
    "scope": "consolidated",
    "review_only_standalone": [
      "LongTermDebtAndCapitalLeaseObligations"
    ],
    "excluded_short_debt": [
      "ShortTermBorrowings",
      "OtherShortTermBorrowings",
      "CommercialPaper"
    ],
    "lease_only_is_total": false,
    "nonpositive_equity": "NOT_MEANINGFUL",
    "standalone_noncurrent_requires_review": true,
    "fallback_trigger": "STRUCTURED_SOURCE_AMBIGUOUS",
    "new_business_calls": [
      0,
      0,
      0
    ],
    "scope_review_dimension_members": [
      "FordCreditMember",
      "CaptiveFinanceMember",
      "FinancialServicesMember"
    ]
  },
  "legacy_projection": {
    "status_exact": "OK",
    "status_approx": "OK_APPROX",
    "source_class": "DERIVED",
    "formula": "total debt / shareholders equity",
    "confidence": "0.90",
    "component_evidence_grain": "one_source_binding_per_row",
    "metric_context_style": "companyfacts_fiscal",
    "evidence_context_style": "companyfacts_fiscal",
    "evidence_unit_policy": "observation",
    "evidence_extraction_method": "companyfacts_component",
    "parser_version": "vnext_projector_v1",
    "evidence_role_order": [
      "debt",
      "equity"
    ],
    "notes": "Point-in-time consolidated structured-primary candidate; full source strategy retains ambiguity fallback."
  },
  "dependencies": []
}
---

# B06 structured primary

Primary-route Spec only. The unchanged source strategy remains structured_first_ai_fallback. Ambiguous coverage is withheld; this draft neither qualifies the AI fallback nor changes the historical table Spec. The debt hierarchy prevents adders; unresolved economic coverage is retained for review.
