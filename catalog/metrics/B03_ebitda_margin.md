---
{
  "metric_id": "B03",
  "name": "EBITDA margin",
  "kind": "derived_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "ratio",
  "source_mode": "structured_and_derived",
  "applicability": {
    "all": ["non_financial"],
    "none": []
  },
  "selection_policy": "legacy_companyfacts_v1",
  "dependencies": ["B01"],
  "inputs": {
    "revenue": {
      "reuse_metric_observation": "B01",
      "cardinality": "exactly_one"
    },
    "operating_income": {
      "choose_first": [
        {
          "extraction_role": {
            "approved_concepts": ["us-gaap:OperatingIncomeLoss"],
            "cardinality": "exactly_one",
            "quality": "EXACT"
          }
        },
        {
          "derived_role": {
            "op": "subtract",
            "inputs": {
              "pretax": {
                "approved_concepts": [
                  "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                  "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"
                ],
                "cardinality": "exactly_one"
              },
              "nonoperating": {
                "approved_concepts": [
                  "us-gaap:NonoperatingIncomeExpense",
                  "us-gaap:OtherNonoperatingIncomeExpense"
                ],
                "cardinality": "exactly_one"
              }
            },
            "args": ["pretax", "nonoperating"],
            "quality": "APPROX",
            "guards": [
              "same_accession",
              "same_period",
              "same_entity",
              "compatible_units"
            ],
            "cross_check": {
              "when_available": true,
              "role": "costs_and_expenses",
              "approved_concepts": ["us-gaap:CostsAndExpenses"],
              "cardinality": "zero_or_one",
              "expression": {
                "expected": {
                  "op": "subtract",
                  "args": ["revenue", "costs_and_expenses"]
                },
                "actual": "operating_income"
              },
              "denominator": "ABS_ACTUAL_OR_ONE",
              "relative_tolerance": "0.01"
            }
          }
        }
      ]
    },
    "depreciation_and_amortization": {
      "choose_first": [
        {
          "extraction_role": {
            "approved_concepts": [
              "us-gaap:DepreciationDepletionAndAmortization",
              "us-gaap:DepreciationAmortizationAndAccretionNet",
              "us-gaap:DepreciationAndAmortization"
            ],
            "cardinality": "exactly_one",
            "quality": "EXACT"
          }
        },
        {
          "derived_role": {
            "op": "add",
            "inputs": {
              "depreciation": {
                "approved_concepts": ["us-gaap:Depreciation"],
                "cardinality": "exactly_one"
              },
              "amortization": {
                "approved_concepts": ["us-gaap:AmortizationOfIntangibleAssets"],
                "cardinality": "exactly_one"
              }
            },
            "args": ["depreciation", "amortization"],
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
    }
  },
  "top_level_guards": [
    "same_accession",
    "same_period",
    "same_entity",
    "compatible_units",
    {"annual_duration": [300, 400]},
    "denominator_nonzero"
  ],
  "formula": {
    "op": "divide",
    "args": [
      {
        "op": "add",
        "args": ["operating_income", "depreciation_and_amortization"]
      },
      "revenue"
    ]
  },
  "quality_rule": {
    "operating_income_direct": "EXACT",
    "operating_income_reconstructed": "APPROX",
    "dna_direct": "EXACT",
    "dna_composed": "EXACT"
  },
  "legacy_projection": {
    "status_exact": "OK",
    "status_approx": "OK_APPROX",
    "source_class": "DERIVED",
    "formula": "(Operating income + D&A) / revenue",
    "confidence": "0.90",
    "component_evidence_grain": "one_source_binding_per_row",
    "metric_context_style": "companyfacts_fiscal",
    "evidence_context_style": "companyfacts_fiscal",
    "evidence_unit_policy": "observation",
    "evidence_extraction_method": "companyfacts_component",
    "parser_version": "vnext_projector_v1",
    "evidence_role_order": [
      "operating_income",
      "depreciation_and_amortization",
      "revenue"
    ],
    "allowed_metric_delta_fields": [],
    "allowed_evidence_delta_fields": [
      "evidence_quote",
      "extraction_method",
      "parser_version"
    ]
  }
}
---

# EBITDA margin

所有选择、fallback、guard、cross-check、Decimal 与 quality 规则均由本 Spec 表达。Calculator 只执行通用角色选择与四则运算。
