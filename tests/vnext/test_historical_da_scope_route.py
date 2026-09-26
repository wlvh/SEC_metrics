"""B03 through the pinned route with the D&A scope rule wired in.

The rule (``historical_da_scope_candidate``) was tested alone on the nine B03
filings; this is the route. On real filings: Salesforce's FY2026 B03 is
withheld by name and still carries its B01, and where the filing proves the
chain's input - a direct total every candidate agrees with, or the approved
composition where no direct total is tagged - the route's result is exactly the
result with the check switched off. Then the shapes no saved filing has, built
by replacing what the filing's inline facts say and saying so: a conflict the
filing's own composition resolves, a chain input the filing does not tag, a
composition taken while the filing tags a total, and a value that differs from
the filing's beyond its reported precision.
"""
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import historical_zero_ai_results as route
from vnext.normal_period_selection import resolve_period_selection

REASON = "B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN"


def resolve(company_id, report_end):
    selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                         report_end=report_end)
    return route.resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=company_id,
                                                   metric_id="B03", period_selection=selection)


def fact(concept, value, decimals):
    return {"concept": concept, "fact_ordinal": 0, "context_ref": "constructed",
            "unit_ref": "usd", "value": value, "decimals": decimals}


def the_filing_says(*facts):
    """Replace what the target filing's inline facts say - constructed, not read."""
    return patch.object(route, "annual_facts", lambda **_: list(facts))


def d_and_a(outcome):
    return [o for o in outcome["observations"]
            if o["semantic_role"] in ("depreciation_and_amortization", "depreciation",
                                      "amortization")]


class OnSavedFilings(unittest.TestCase):

    def test_salesforce_is_withheld_by_name_and_still_carries_b01(self):
        outcome = resolve("salesforce", "2026-01-31")
        self.assertEqual(("WITHHELD", REASON),
                         (outcome["result"]["publication"], outcome["result"]["reason_code"]))
        scope = outcome["selection"]["depreciation_scope"]
        self.assertEqual("DIRECT_CANDIDATES_CONFLICT_AND_NOTHING_IN_THE_FILING_RESOLVES_IT",
                         scope["why"])
        self.assertEqual({"DepreciationDepletionAndAmortization", "DepreciationAndAmortization"},
                         {c["concept"] for c in scope["filing_answer"]["candidates"]})
        self.assertEqual("DISCLOSURE_SCOPE_UNPROVEN", outcome["selection"]["category"])
        b01 = [r for r in outcome["dependency_records"]
               if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == "B01"]
        self.assertEqual(["PUBLISHED"], [r["publication"] for r in b01])

    def test_where_the_filing_proves_the_input_the_result_is_the_chain_s(self):
        keep = {"status": "KEEP", "why": "CHECK_SWITCHED_OFF"}
        for company_id, report_end, why in (
                ("enphase_energy", "2025-12-31", "EVERY_DIRECT_CANDIDATE_AGREES"),
                ("marriott_international", "2025-12-31", "THE_APPROVED_COMPOSITION_APPLIES")):
            with self.subTest(company=company_id):
                wired = resolve(company_id, report_end)
                with patch.object(route, "depreciation_scope", lambda **_: keep):
                    unchecked = resolve(company_id, report_end)
                self.assertEqual(unchecked["result"], wired["result"])
                self.assertEqual("PUBLISHED", wired["result"]["publication"])
                self.assertEqual(why, wired["selection"]["depreciation_scope"]["why"])


class ShapesNoSavedFilingHas(unittest.TestCase):

    def test_a_conflict_the_filing_s_composition_resolves_takes_the_proven_total(self):
        with the_filing_says(fact("DepreciationDepletionAndAmortization", "1200000000", "-8"),
                             fact("DepreciationAndAmortization", "3631000000", "-6"),
                             fact("Depreciation", "1000000000", "-6"),
                             fact("AmortizationOfIntangibleAssets", "2631000000", "-6")):
            outcome = resolve("salesforce", "2026-01-31")
        self.assertEqual("PUBLISHED", outcome["result"]["publication"])
        self.assertEqual("RETAKE", outcome["selection"]["depreciation_scope"]["status"])
        (taken,) = d_and_a(outcome)
        self.assertEqual("us-gaap:DepreciationAndAmortization", taken["source_binding"]["concept"])
        self.assertEqual(3631000000, int(taken["value"]))

    def test_a_direct_total_the_filing_does_not_tag_is_withheld(self):
        with the_filing_says():
            outcome = resolve("enphase_energy", "2025-12-31")
        self.assertEqual(REASON, outcome["result"]["reason_code"])
        self.assertEqual("THE_CHAIN_TOOK_A_DIRECT_TOTAL_THE_FILING_DOES_NOT_TAG_FOR_THIS_PERIOD",
                         outcome["selection"]["depreciation_scope"]["why"])

    def test_a_composition_taken_while_the_filing_tags_a_total_is_withheld(self):
        with the_filing_says(fact("DepreciationDepletionAndAmortization", "458000000", "-6")):
            outcome = resolve("marriott_international", "2025-12-31")
        self.assertEqual(REASON, outcome["result"]["reason_code"])
        self.assertEqual("THE_CHAIN_COMPOSED_WHILE_THE_FILING_TAGS_A_DIRECT_TOTAL",
                         outcome["selection"]["depreciation_scope"]["why"])

    def test_the_chain_s_value_must_be_the_filing_s_at_its_precision(self):
        with the_filing_says(fact("DepreciationDepletionAndAmortization", "80700000", "-3")):
            outcome = resolve("enphase_energy", "2025-12-31")
        self.assertEqual(REASON, outcome["result"]["reason_code"])
        with the_filing_says(fact("DepreciationDepletionAndAmortization", "80600000", "-5")):
            inside = resolve("enphase_energy", "2025-12-31")
        self.assertEqual("PUBLISHED", inside["result"]["publication"])


if __name__ == "__main__":
    unittest.main()
