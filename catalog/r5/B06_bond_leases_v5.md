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
    "resolver": "debt_equity_bond_and_separate_lease_v5",
    "scope": "consolidated",
    "scope_review_dimension_members": [
      "FordCreditMember",
      "CaptiveFinanceMember",
      "FinancialServicesMember"
    ],
    "measurement_basis": "PERIOD_END_CARRYING_AMOUNT_OF_DEFINED_DEBT_SET",
    "equity_concept": "us-gaap:StockholdersEquity",
    "debt_set_registry": "config/b06_bond_debt_set_v1.json",
    "debt_set_registry_sha256": "d488ea9f62247459cff27c9248cd1ebb6e31b870030a7e161e8547136676e024",
    "source_policy": "config/b06_bond_leases_v1.json",
    "source_policy_sha256": "eb8536c412bbcf4086a1994513f1766c2bee268f08d9835b6393b1c66f2b5f2c",
    "original_metric_spec": "catalog/r5/B06_new_source_v2.md",
    "original_metric_spec_sha256": "e34a540f246302cd67abfa4c98a6da62bcced32f14b28be30a64049e80bfd944"
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

保留期末账面债务和同范围权益定义。债券本金、折价/溢价及费用与当前和非当前报表余额对账，另加已证明单独列报的融资租赁。公司付款条件未变且明确列为普通贸易应付款的供应商项目按既有排除类别处理。历史模型和旧规格不改；当前与非当前借款都进入新对账规则。
