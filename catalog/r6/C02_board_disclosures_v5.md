---
{
  "metric_id": "C02",
  "name": "Board composition facts",
  "kind": "direct_text",
  "canonical_unit": "text",
  "source_mode": "ai_text",
  "disclosure_group": "c02_composition_grouped_v4",
  "applicability": {
    "all": [],
    "none": []
  },
  "required_claims": {
    "entity_scope": "registrant",
    "disclosure_basis": "source_filing_text",
    "period_basis": "annual_grouping_only",
    "board_as_of": "not_inferred"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "board_as_of"
    ],
    "allowed_dimensions": [
      "entity_scope",
      "disclosure_basis",
      "period_basis",
      "board_as_of"
    ],
    "exact_enum_aliases": {
      "entity_scope": {
        "registrant": [
          "registrant"
        ]
      },
      "disclosure_basis": {
        "source_filing_text": [
          "source_filing_text"
        ]
      },
      "period_basis": {
        "annual_grouping_only": [
          "annual_grouping_only"
        ]
      },
      "board_as_of": {
        "not_inferred": [
          "not_inferred"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "entity_scope",
        "disclosure_basis",
        "period_basis",
        "board_as_of"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "quality_rule": {
    "deterministic_text_method": "BOARD_DISCLOSURE_EXCERPTS_V1"
  },
  "text_policy": {
    "version": "TEXT_V1",
    "content_kind": "SOURCE_EXCERPTS",
    "required_sections": [
      "GOVERNANCE_DISCLOSURES"
    ],
    "allowed_source_roles": [
      "target_primary",
      "governance_proxy"
    ],
    "renderer": "ORDERED_NEWLINE_V1",
    "max_items": 64,
    "max_text_chars": 64000,
    "review_required": true
  },
  "legacy_projection": {
    "status_exact": "TEXT_QUAL",
    "source_class": "PROXY",
    "formula": "verbatim governance disclosures",
    "confidence": "",
    "notes": "Annual coordinate groups source disclosures. Filing date is bound in Evidence; board measurement as-of is not inferred."
  },
  "dependencies": []
}
---

# Board composition source disclosures (reversible source-block groups)

C02 preserves the complete set of **board composition facts** that the selected same-registrant governance filing states in a supported structure. Composition facts are: the board's total size (directors or seats, and nominees only when the whole board stands for election rather than one class's slate); how many directors are independent and which ones are or are not; which committees exist; who sits on each committee and who chairs it; the determinations about directors' and committee members' independence and qualifications (financially literate, audit committee financial expert, non-employee director, no member an officer or employee); who chairs the board and who is lead independent director; and changes in who sits on the board or a committee, stated with the person or date concerned. General governance process, independence standards in the abstract, nomination and evaluation procedure, what a committee or its chair does, pay, auditor independence and equity-plan terms are outside it, as is anything about another organisation's board or committees.

Committee membership is read as the filing lays it out: a committee's page heading followed by its chair line, member label and one block per member (including a member column the layout moved after the committee's duties), an inline members line, a report signature or membership table naming the committee and then its members, a director card whose committee lines are followed by the director it names, and a dated list of committee additions and departures. A membership matrix whose marks lost their columns is not reconstructed, and a card whose director is not named beside its committees is not associated by guess. Prose facts are read sentence by sentence and set aside when the sentence states a rule, a hypothetical, a pay or voting matter, or places a board or committee at another body.

Excerpts are complete contiguous ranges of original source blocks. The selector first runs on the full original governance document. Nearby selected blocks may be joined when at most two original blocks lie between them; those intervening context blocks are included verbatim, never dropped or silently counted as separate facts. A deterministic complete-document partition maps each grouped excerpt back to every original block and its exact raw-byte span. The 64-item limit applies to these grouped excerpts, and the unchanged 64,000-character limit applies to all included visible text. A complete source still exceeding either limit fails without truncation. The ordinary annual source anchors the reporting container only. The source filing date and proxy report/meeting metadata remain distinct from a board measurement date, which is not inferred; no count is computed and no year-end board is asserted. Exact source excerpts are mechanically replayed and reviewed through the existing whole ReviewUnit. No keyword miss proves nondisclosure.

This explicit #28 successor retains the approved composition-fact meaning and the frozen TEXT_V1 record and renderer limits. It changes the unit of an excerpt from one original block to a mapped contiguous group of complete original blocks. The previous v1/v2 Specs, Results and Runs retain their own identities. Grouping cannot turn a selector omission into a fact, and the added context remains visible for content review.

This explicit selector revision distinguishes an external auditor’s independence from a director or committee member’s determination. It preserves member independence in the same sentence, the complete source grouping, and the approved composition-fact scope. The preceding Specs and selector paths retain their original bytes.

This explicit member-clause revision requires the stated members or a listed status after the clause verb; an oversight disclaimer without such a fact is outside the unchanged composition scope.
