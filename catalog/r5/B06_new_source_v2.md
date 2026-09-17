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
              "us-gaap:DebtAndCapitalLeaseObligations"
            ],
            "cardinality": "exactly_one",
            "quality": "EXACT"
          }
        },
        {
          "derived_role": {
            "op": "subtract",
            "args": [
              "gross",
              "cost"
            ],
            "inputs": {
              "gross": {
                "approved_concepts": [
                  "us-gaap:LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"
                ],
                "cardinality": "exactly_one"
              },
              "cost": {
                "approved_concepts": [
                  "us-gaap:DeferredFinanceCostsGross"
                ],
                "cardinality": "exactly_one"
              }
            },
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
            "op": "subtract",
            "args": [
              "gross",
              "discount",
              "cost"
            ],
            "inputs": {
              "gross": {
                "approved_concepts": [
                  "us-gaap:LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"
                ],
                "cardinality": "exactly_one"
              },
              "discount": {
                "approved_concepts": [
                  "us-gaap:DebtInstrumentUnamortizedDiscountPremiumNet"
                ],
                "cardinality": "exactly_one"
              },
              "cost": {
                "approved_concepts": [
                  "us-gaap:DeferredFinanceCostsNet"
                ],
                "cardinality": "exactly_one"
              }
            },
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
            "args": [
              "current",
              "noncurrent"
            ],
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
            "args": [
              "short",
              "noncurrent"
            ],
            "inputs": {
              "short": {
                "approved_concepts": [
                  "us-gaap:DebtCurrent"
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
            "args": [
              "borrowing",
              "finance_lease"
            ],
            "inputs": {
              "borrowing": {
                "approved_concepts": [
                  "us-gaap:LongTermDebt"
                ],
                "cardinality": "exactly_one"
              },
              "finance_lease": {
                "approved_concepts": [
                  "us-gaap:FinanceLeaseLiability"
                ],
                "cardinality": "exactly_one"
              }
            },
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
            "args": [
              {
                "op": "subtract",
                "args": [
                  {
                    "op": "add",
                    "args": [
                      "principal",
                      "premium"
                    ]
                  },
                  "cost"
                ]
              },
              "finance_lease"
            ],
            "inputs": {
              "principal": {
                "approved_concepts": [
                  "m:LongTermDebtGrossIncludingCurrentMaturities"
                ],
                "cardinality": "exactly_one"
              },
              "premium": {
                "approved_concepts": [
                  "us-gaap:DebtInstrumentUnamortizedPremiumNoncurrent"
                ],
                "cardinality": "exactly_one"
              },
              "cost": {
                "approved_concepts": [
                  "us-gaap:DebtInstrumentUnamortizedDiscountPremiumAndDebtIssuanceCostsNet"
                ],
                "cardinality": "exactly_one"
              },
              "finance_lease": {
                "approved_concepts": [
                  "us-gaap:FinanceLeaseLiability"
                ],
                "cardinality": "exactly_one"
              }
            },
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
    "resolver": "debt_equity_new_source_v2",
    "scope": "consolidated",
    "scope_review_dimension_members": [
      "FordCreditMember",
      "CaptiveFinanceMember",
      "FinancialServicesMember"
    ],
    "measurement_basis": "PERIOD_END_CARRYING_AMOUNT_OF_DEFINED_DEBT_SET",
    "equity_concept": "us-gaap:StockholdersEquity",
    "debt_set_registry": "config/r5_b06_debt_sets_v3.json",
    "debt_set_registry_sha256": "0ef10b3f5fb97678efe96c7915a3c10992779f1804107a906d3d0a1eea48e203"
  },
  "legacy_projection": {
    "status_exact": "OK",
    "status_approx": "OK_APPROX",
    "source_class": "DERIVED",
    "formula": "total debt / shareholders equity",
    "confidence": "0.90",
    "component_evidence_grain": "one_source_binding_per_row",
    "metric_context_style": "structured_source_context",
    "evidence_context_style": "structured_source_context",
    "evidence_unit_policy": "observation",
    "evidence_extraction_method": "structured_source_component",
    "parser_version": "vnext_projector_v1",
    "evidence_role_order": [
      "debt",
      "equity"
    ],
    "notes": "Recognized borrowing, bond and finance lease carrying amounts; disjoint classes counted once. Source-bound completeness judgment; bank and industrial scopes separately limited."
  },
  "dependencies": []
}
---

B06后继候选：保留期末账面借款、债券、融资租赁及同范围归母权益的原定义。追加原HTML/XML分子分母一致性、其他已知债务计量的独立对账，以及有限当期借款叙述检查；不能凭合计标签或公式一致授予完整性。来源准入、原生冻结和生产权限仍独立要求；本Spec不改变历史v1。
