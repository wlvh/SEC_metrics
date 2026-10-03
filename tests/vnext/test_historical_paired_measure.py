"""A current and a prior claim of one quantity must read one quantity.

B02's branch reads revenue once from the target filing and once from the prior
filing, each the first approved concept its own filing tags. Pfizer moved its
revenue concepts between filings, and the historical route published growth
that divided product revenue by total revenue. The historical Company Facts
route now withholds such a pair by name unless the target filing reports the
prior year under the current claim's concept at the prior claim's value.

One concept can still read two quantities when the target filing recasts the
prior year: Pfizer's FY2021 10-K reports 2020 revenue at 41,651,000,000 after
moving Meridian to discontinued operations, and the branch took the
41,908,000,000 its FY2020 10-K reported. That pair is withheld too; a target
filing reporting the prior year at the prior claim's value, or not at all,
asks nothing.

These cases use Pfizer's own saved Company Facts (the checkout's copy carries
every filing's facts with the accession that reported them). Zero calls.
"""
import json
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import historical_results as route_module
from vnext.annual_update import saved_source
from vnext.zero_ai_r2 import _load_deterministic_catalog

CIK = 78003
FILINGS = {"FY2020": "0000078003-21-000038", "FY2021": "0000078003-22-000027",
           "FY2022": "0000078003-23-000024",
           "FY2023": "0000078003-24-000039", "FY2024": "0000078003-25-000054"}


def _claims():
    """Every annual USD claim of the chain's concepts, shaped as the route's claims are."""
    from sec_urls import companyfacts_url
    body = json.loads(saved_source(repo_root=ROOT, url=companyfacts_url(cik=CIK))["raw"])
    claims = []
    for concept in ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                    "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"):
        for fact in body["facts"]["us-gaap"].get(concept, {}).get("units", {}).get("USD", []):
            if "start" not in fact:
                continue
            claims.append({"locator": {"concept": concept, "period_start": fact["start"],
                                       "period_end": fact["end"]},
                           "attributes": {"accession": fact["accn"]}, "unit": "USD",
                           "value": str(fact["val"])})
    return claims


def _one(claims, *, accession, concept, end):
    found = [claim for claim in claims if claim["attributes"]["accession"] == accession
             and claim["locator"]["concept"] == concept and claim["locator"]["period_end"] == end]
    assert len(found) == 1, (accession, concept, end, len(found))
    return found[0]


class APairOnTwoConceptsIsKeptOnlyWhereTheFilingJoinsThemTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.claims = _claims()
        cls.route = _load_deterministic_catalog(repo_root=ROOT)["metrics"]["B02"]

    def _ask(self, *, current, prior, target):
        return route_module.paired_measure_problem(
            route=self.route, claims=[current, prior], current_claims=self.claims,
            accessions={"current": target, "prior": prior["attributes"]["accession"]})

    def test_product_revenue_over_total_revenue_is_withheld(self):
        # FY2023: the contract concept is product revenue only; the FY2022 10-K
        # tagged total revenue as Revenues. The FY2023 10-K reports 2022 under
        # the contract concept at 91,793,000,000, not 100,330,000,000.
        problem, bridged = self._ask(
            current=_one(self.claims, accession=FILINGS["FY2023"],
                         concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                         end="2023-12-31"),
            prior=_one(self.claims, accession=FILINGS["FY2022"], concept="Revenues",
                       end="2022-12-31"),
            target=FILINGS["FY2023"])
        self.assertEqual(route_module.PAIRED_MEASURE_REASON, problem["reason_code"])
        self.assertEqual(["91793000000"],
                         problem["target_filing_reports_the_prior_year_under_the_current_concept"])
        self.assertEqual([], bridged)

    def test_total_revenue_over_product_revenue_is_withheld(self):
        # FY2024: Revenues against the FY2023 contract concept; the FY2024 10-K
        # reports 2023 under Revenues at its recast 59,553,000,000.
        problem, _ = self._ask(
            current=_one(self.claims, accession=FILINGS["FY2024"], concept="Revenues",
                         end="2024-12-31"),
            prior=_one(self.claims, accession=FILINGS["FY2023"],
                       concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                       end="2023-12-31"),
            target=FILINGS["FY2024"])
        self.assertEqual(["59553000000"],
                         problem["target_filing_reports_the_prior_year_under_the_current_concept"])

    def test_two_concepts_the_target_filing_shows_are_one_quantity_are_kept(self):
        # FY2022: Revenues against the FY2021 contract concept, and the FY2022
        # 10-K reports 2021 under Revenues at the same 81,288,000,000.
        problem, bridged = self._ask(
            current=_one(self.claims, accession=FILINGS["FY2022"], concept="Revenues",
                         end="2022-12-31"),
            prior=_one(self.claims, accession=FILINGS["FY2021"],
                       concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                       end="2021-12-31"),
            target=FILINGS["FY2022"])
        self.assertIsNone(problem)
        self.assertEqual(1, len(bridged))
        self.assertEqual(["81288000000"],
                         bridged[0]["target_filing_reports_the_prior_year_under_the_current_concept"])

    def test_one_concept_the_target_filing_recasts_is_withheld(self):
        # FY2021: the contract concept both years. The FY2020 10-K reported
        # 2020 at 41,908,000,000; the FY2021 10-K reports it at 41,651,000,000
        # with Meridian in discontinued operations.
        problem, bridged = self._ask(
            current=_one(self.claims, accession=FILINGS["FY2021"],
                         concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                         end="2021-12-31"),
            prior=_one(self.claims, accession=FILINGS["FY2020"],
                       concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                       end="2020-12-31"),
            target=FILINGS["FY2021"])
        self.assertEqual(route_module.PAIRED_MEASURE_REASON, problem["reason_code"])
        self.assertTrue(problem["same_concept_recast"])
        self.assertEqual("41908000000", problem["prior"]["value"])
        self.assertEqual(["41651000000"],
                         problem["target_filing_reports_the_prior_year_under_the_current_concept"])
        self.assertEqual([], bridged)

    def test_one_concept_reported_at_the_prior_value_or_not_at_all_asks_nothing(self):
        # FY2024 against FY2023 on Revenues: the FY2024 10-K recasts 2023 to
        # 59,553,000,000 from 58,496,000,000, so the real pair is withheld; a
        # prior claim at the reported value (constructed) asks nothing, and so
        # does a target filing that does not report the year (constructed).
        current = _one(self.claims, accession=FILINGS["FY2024"], concept="Revenues",
                       end="2024-12-31")
        prior = _one(self.claims, accession=FILINGS["FY2023"], concept="Revenues",
                     end="2023-12-31")
        problem, _ = self._ask(current=current, prior=prior, target=FILINGS["FY2024"])
        self.assertTrue(problem["same_concept_recast"])
        self.assertEqual(["59553000000"],
                         problem["target_filing_reports_the_prior_year_under_the_current_concept"])
        self.assertEqual((None, []), self._ask(current=current,
                                               prior={**prior, "value": "59553000000"},
                                               target=FILINGS["FY2024"]))
        unreported = [claim for claim in self.claims
                      if not (claim["attributes"]["accession"] == FILINGS["FY2024"]
                              and claim["locator"]["period_end"] == "2023-12-31")]
        self.assertEqual((None, []), route_module.paired_measure_problem(
            route=self.route, claims=[current, prior], current_claims=unreported,
            accessions={"current": FILINGS["FY2024"], "prior": FILINGS["FY2023"]}))

    def test_a_concept_pair_problem_carries_no_recast_mark(self):
        # The two-concept withholds keep the record they had.
        problem, _ = self._ask(
            current=_one(self.claims, accession=FILINGS["FY2024"], concept="Revenues",
                         end="2024-12-31"),
            prior=_one(self.claims, accession=FILINGS["FY2023"],
                       concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                       end="2023-12-31"),
            target=FILINGS["FY2024"])
        self.assertNotIn("same_concept_recast", problem)

    def test_a_value_the_filing_reports_differently_is_not_a_bridge(self):
        # The target filing must report the prior claim's own value: FY2024's
        # 10-K reports 2023 Revenues at 59,553,000,000, so a prior Revenues
        # claim at 58,496,000,000 is one concept, and nothing is asked of it;
        # but the same 10-K's claim put against the 2023 contract concept is
        # not joined by a Revenues value that equals it.
        prior = _one(self.claims, accession=FILINGS["FY2023"],
                     concept="RevenueFromContractWithCustomerExcludingAssessedTax", end="2023-12-31")
        forged = {**prior, "value": "59553000000"}
        problem, bridged = self._ask(
            current=_one(self.claims, accession=FILINGS["FY2024"], concept="Revenues",
                         end="2024-12-31"),
            prior=forged, target=FILINGS["FY2024"])
        self.assertIsNone(problem)
        self.assertEqual(1, len(bridged))


class OnlyPairedComponentsAreAskedTest(unittest.TestCase):

    def test_the_routes_that_read_one_quantity_twice(self):
        catalog = _load_deterministic_catalog(repo_root=ROOT)["metrics"]
        paired = {metric_id for metric_id, route in catalog.items()
                  if route["adapter_id"] == "companyfacts"
                  and route_module._paired_concept_lists(route)}
        # A05 and A06 read Assets and StockholdersEquity twice - one concept
        # each, so a pair can never differ - and A07 and B02 read a chain.
        self.assertEqual({"A05", "A06", "A07", "B02"}, paired)

    def test_a_result_without_a_prior_claim_asks_nothing(self):
        claims = _claims()
        route = _load_deterministic_catalog(repo_root=ROOT)["metrics"]["B02"]
        current = _one(claims, accession=FILINGS["FY2023"],
                       concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                       end="2023-12-31")
        self.assertEqual((None, []), route_module.paired_measure_problem(
            route=route, claims=[current], current_claims=claims,
            accessions={"current": FILINGS["FY2023"], "prior": FILINGS["FY2022"]}))


if __name__ == "__main__":
    unittest.main()
