---
{
  "metric_id": "B13",
  "name": "Comparable actual production divided by available capacity",
  "kind": "derived_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "ratio",
  "unit_policy": "fixed_canonical",
  "source_mode": "structured",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "capacity_basis": "actual_production_over_available_capacity"
  },
  "scope_contract": null,
  "forbidden_confusions": [],
  "inputs": {
    "actual_production": {
      "structured_role": {
        "approved_concepts": [
          "b13:ActualProduction"
        ],
        "cardinality": "exactly_one",
        "quality": "EXACT"
      }
    },
    "available_capacity": {
      "structured_role": {
        "approved_concepts": [
          "b13:AvailableCapacity"
        ],
        "cardinality": "exactly_one",
        "quality": "EXACT"
      }
    }
  },
  "formula": {
    "op": "divide",
    "args": [
      "actual_production",
      "available_capacity"
    ]
  },
  "top_level_guards": [
    "same_accession",
    "same_period",
    "same_entity",
    "compatible_units"
  ],
  "identity_constraints": [],
  "quality_rule": {},
  "legacy_projection": {
    "status_exact": "OK",
    "source_class": "DERIVED",
    "formula": "actual production / comparable available capacity"
  },
  "review_policy": "none",
  "selection_policy": {
    "semantic_version": "1",
    "period_filter": "target_period",
    "form_rule": "10-K_PREFIX_AND_FY",
    "within_concept_order": [
      "filed_desc",
      "accession_desc",
      "unit_desc"
    ],
    "target_accession_priority": true,
    "ambiguous_after_tie_break": "AMBIGUOUS_CANDIDATE"
  },
  "dependencies": [],
  "disclosure_group": null
}
---

# B13 comparable production and capacity

User-approved successor of the historical B13 Spec. Applicable companies remain Ford and Enphase, enforced by the bound policy before selecting this Spec. Inputs must be actual output and corresponding available capacity for the same entity, period, product/facility scope and compatible units. The semantic role names are host-assigned only after source validation; they are not assertions that SEC tags have these names. Sales, shipments, installed quantities and future planned capacity are not substitutes. Capacity alone cannot create a ratio. Missing source proof or an unimplemented relation cannot become zero or nondisclosure.

The existing Calculator performs the division. A source adapter must prove the two role assignments and the exact shared scope before calculation; this draft does not itself grant source, model, native Run or production credit. Historical Spec and Runs remain unchanged.
