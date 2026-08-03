---
{
  "metric_id": "DISCLOSURE_LODGING_KPI_TABLE",
  "name": "Lodging KPI disclosure group",
  "kind": "disclosure_group",
  "canonical_unit": "mixed",
  "reported_unit": "mixed",
  "source_mode": "ai_table",
  "disclosure_group": "lodging_kpi_table",
  "applicability": {
    "all": ["lodging"],
    "none": []
  },
  "required_claims": {
    "period_role": "current_fiscal_year",
    "property_population": "comparable",
    "operating_scope": "systemwide",
    "geography": "worldwide"
  },
  "forbidden_confusions": [
    "prior_year",
    "percentage_change",
    "company_operated",
    "regional_only"
  ],
  "identity_constraints": [
    {
      "expression": {
        "expected": {
          "op": "multiply",
          "args": ["adr", "occupancy"]
        },
        "actual": "revpar"
      },
      "tolerance": {
        "kind": "relative",
        "value": "0.01"
      }
    }
  ],
  "review_policy": "human_required_during_poc",
  "ai_instructions": [
    "Read every table supplied by ReaderInputManifest.",
    "Return selected, competing, and unresolved claims with exact cell locators.",
    "Return occupancy, revpar, and adr in one response."
  ],
  "prompt_examples": [],
  "legacy_projection": {
    "roles": ["occupancy", "revpar"],
    "supporting_roles": ["adr"],
    "role_metric_ids": {
      "occupancy": "B10",
      "revpar": "B11"
    },
    "supporting_role_units": {
      "adr": "USD"
    }
  },
  "dependencies": []
}
---

# Lodging KPI disclosure group

Reader 收到目标文档的全部 table-grid。上述业务词只存在于 catalog，不得进入通用 transform、Checker、renderer 或 Projector 的控制分支。
