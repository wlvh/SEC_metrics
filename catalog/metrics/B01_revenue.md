---
{
  "metric_id": "B01",
  "name": "Revenue",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "unit_policy": "preserve_reported",
  "source_mode": "structured",
  "applicability": {
    "all": ["non_financial"],
    "none": []
  },
  "selection_policy": "legacy_companyfacts_v1",
  "inputs": {
    "revenue": {
      "structured_role": {
        "approved_concepts": [
          "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
          "us-gaap:Revenues",
          "us-gaap:SalesRevenueNet",
          "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax"
        ],
        "cardinality": "exactly_one",
        "quality": "EXACT"
      }
    }
  },
  "formula": "revenue",
  "top_level_guards": [
    "same_entity",
    {"annual_duration": [300, 400]}
  ],
  "quality_rule": {
    "structured_direct": "EXACT"
  },
  "legacy_projection": {
    "status": "OK",
    "source_class": "STD_XBRL",
    "formula": "direct",
    "confidence": "0.95",
    "notes": "Revenue candidate chain from metric definition."
  },
  "dependencies": []
}
---

# Revenue

复用当前结构化 Company Facts 选择语义。该指标不经过 AI，也不复制第二套 Revenue resolver。
