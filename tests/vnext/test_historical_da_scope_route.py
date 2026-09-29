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

A kept direct total is also asked whether the filing says it includes
impairment-related depreciation. Ford's FY2025 filing does: its segment table's
D&A total is footnoted as including $8.1 billion of depreciation related to an
asset impairment. The route withholds it by name, asking the question #28's own
check asks and getting the same answer; the prior years' columns of the same
table are not footnoted and are not caught; and a total retaken from the
filing's composition is asked too (constructed: no saved filing retakes).

A kept composition is asked #28's other question: whether the filing reports,
apart from the depreciation and intangible-asset amortization it takes, a
positive amortization of capitalized contract costs. Marriott's filings do, so
its composed B03 is withheld by name with #28's own answer; with that check
answering nothing, the same composition is published as before.
"""
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import historical_zero_ai_results as route
from vnext.b03_depreciation_scope import assess_direct_depreciation_scope
from vnext.normal_period_selection import resolve_period_selection
from vnext.sources import resolve_repository_file

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
        # Marriott's composition is proven too, and then withheld for another
        # reason (AComposedTotalBesideAContractCostAmortization).
        for company_id, report_end, why in (
                ("enphase_energy", "2025-12-31", "EVERY_DIRECT_CANDIDATE_AGREES"),):
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


def switched_off():
    """The route with the whole D&A scope check replaced by a keep."""
    return patch.object(route, "depreciation_scope",
                        lambda **_: {"status": "KEEP", "why": "CHECK_SWITCHED_OFF"})


class AKeptTotalTheFilingSaysIncludesImpairment(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.wired = resolve("ford_motor_company", "2025-12-31")
        with switched_off():
            cls.unchecked = resolve("ford_motor_company", "2025-12-31")
        (cls.observation,) = d_and_a(cls.unchecked)
        accession = cls.observation["source_binding"]["accession"]
        (primary,) = [proof for proof in cls.unchecked["source_proofs"]
                      if proof.get("accession") == accession
                      and proof.get("document_name", "").lower().endswith((".htm", ".html"))]
        cls.raw = resolve_repository_file(
            repo_root=ROOT, repo_relative_path=primary["request_repo_relative_path"]).read_bytes()

    def test_it_is_withheld_by_name_and_still_carries_b01(self):
        self.assertEqual(("PUBLISHED", "PASS"), (self.unchecked["result"]["publication"],
                                                 self.unchecked["result"]["reason_code"]))
        self.assertEqual(("WITHHELD", REASON), (self.wired["result"]["publication"],
                                                self.wired["result"]["reason_code"]))
        scope = self.wired["selection"]["depreciation_scope"]
        self.assertEqual("THE_SELECTED_TOTAL_INCLUDES_IMPAIRMENT_RELATED_DEPRECIATION", scope["why"])
        self.assertEqual("15,974", scope["impairment_inclusion"]["selected_visible_total"])
        self.assertIn("depreciation related to", scope["impairment_inclusion"]["footnote_text"])
        self.assertIn("impairment", scope["impairment_inclusion"]["footnote_text"])
        self.assertEqual("DISCLOSURE_SCOPE_UNPROVEN", self.wired["selection"]["category"])
        b01 = [r for r in self.wired["dependency_records"]
               if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == "B01"]
        self.assertEqual(["PUBLISHED"], [r["publication"] for r in b01])

    def test_it_is_the_question_and_the_answer_of_28_s_own_check(self):
        base = assess_direct_depreciation_scope(
            case={"primary_metric_id": "B03", "results": {"B03": self.unchecked["result"]},
                  "observations": self.unchecked["observations"],
                  "source_proofs": self.unchecked["source_proofs"],
                  "target_period": self.unchecked["target_period"]},
            data_root=ROOT)
        self.assertEqual("SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT", base["status"])
        proof = base["impairment_inclusion_proof"]
        ported = self.wired["selection"]["depreciation_scope"]["impairment_inclusion"]
        self.assertEqual((proof["table_id"], proof["table_grid_sha256"],
                          proof["included_component"], proof["footnote"]["span_sha256"]),
                         (ported["table_id"], ported["table_grid_sha256"],
                          ported["included_component"], ported["footnote_span_sha256"]))

    def test_the_same_table_s_prior_years_are_not_footnoted(self):
        for start, end, value in (("2024-01-01", "2024-12-31", 7567000000),
                                  ("2023-01-01", "2023-12-31", 7690000000)):
            with self.subTest(year=end):
                self.assertIsNone(route.impairment_included(
                    raw_bytes=self.raw, period={"period_start": start, "period_end": end},
                    observation={**self.observation, "value": value}))

    def test_the_proof_is_the_measured_period_s_fact(self):
        # The footnoted total asked about another period: no fact of that
        # period carries it, so there is nothing to prove inclusion of.
        self.assertIsNone(route.impairment_included(
            raw_bytes=self.raw, period={"period_start": "2024-01-01", "period_end": "2024-12-31"},
            observation=self.observation))

    def test_a_retaken_total_is_asked_too(self):
        retake = {"status": "RETAKE", "concept": "DepreciationDepletionAndAmortization",
                  "why": "CONSTRUCTED_RETAKE"}
        with patch.object(route, "depreciation_scope", lambda **_: retake):
            outcome = resolve("ford_motor_company", "2025-12-31")
        self.assertEqual(REASON, outcome["result"]["reason_code"])
        scope = outcome["selection"]["depreciation_scope"]
        self.assertEqual(("WITHHOLD", "THE_SELECTED_TOTAL_INCLUDES_IMPAIRMENT_RELATED_DEPRECIATION"),
                         (scope["status"], scope["why"]))


class AComposedTotalBesideAContractCostAmortization(unittest.TestCase):
    """Marriott's filings report contract-cost amortization apart from the composition."""

    @classmethod
    def setUpClass(cls):
        cls.wired = {end: resolve("marriott_international", end)
                     for end in ("2025-12-31", "2024-12-31")}

    def test_it_is_withheld_by_name_and_still_carries_b01(self):
        for end, outcome in self.wired.items():
            with self.subTest(end=end):
                self.assertEqual(("WITHHELD", REASON), (outcome["result"]["publication"],
                                                        outcome["result"]["reason_code"]))
                scope = outcome["selection"]["depreciation_scope"]
                self.assertEqual(
                    "THE_FILING_REPORTS_AN_AMORTIZATION_THE_COMPOSITION_DOES_NOT_TAKE",
                    scope["why"])
                answer = scope["contract_amortization"]
                self.assertEqual("COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED",
                                 answer["status"])
                self.assertFalse(answer["amount_added_or_result_recomputed"])
                self.assertTrue(answer["additional_facts"])
                b01 = [r for r in outcome["dependency_records"]
                       if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == "B01"]
                self.assertEqual(["PUBLISHED"], [r["publication"] for r in b01])

    def test_it_is_the_answer_of_28_s_own_check(self):
        from tests.vnext.test_normal_zero_ai_results import original_sources_only
        from vnext.b03_contract_amortization_scope import assess_current_b03_scope
        from vnext.normal_run_v3 import prepare_case
        with original_sources_only():
            case = prepare_case(data_root=ROOT, company_id="marriott_international",
                                metric_id="B03")
            ordinary = assess_current_b03_scope(case=case, data_root=ROOT)
        ours = self.wired["2025-12-31"]["selection"]["depreciation_scope"]["contract_amortization"]
        self.assertEqual(ordinary, {**ours, "blocked": True})

    def test_without_it_the_composition_is_published_as_before(self):
        for end in self.wired:
            with self.subTest(end=end):
                with patch.object(route, "contract_amortization_unreconciled",
                                  lambda **_: None):
                    unchecked = resolve("marriott_international", end)
                self.assertEqual("PUBLISHED", unchecked["result"]["publication"])
                scope = unchecked["selection"]["depreciation_scope"]
                self.assertEqual(("KEEP", "THE_APPROVED_COMPOSITION_APPLIES"),
                                 (scope["status"], scope["why"]))
                self.assertEqual({"depreciation", "amortization"},
                                 {o["semantic_role"] for o in d_and_a(unchecked)})

    def test_a_direct_total_is_not_its_question(self):
        # Enphase's B03 takes a direct total; #28's check answers None for it,
        # so the published result is the one the check leaves alone.
        outcome = resolve("enphase_energy", "2025-12-31")
        self.assertEqual("PUBLISHED", outcome["result"]["publication"])
        self.assertNotIn("contract_amortization", outcome["selection"]["depreciation_scope"])


if __name__ == "__main__":
    unittest.main()