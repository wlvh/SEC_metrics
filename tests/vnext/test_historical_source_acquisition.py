"""Issue #47's own dependency gate, and the allowance it does not have.

The load-bearing case is the boundary: the same URL that the existing
acquisition CLI refuses has to be planned here, and a URL nothing declares has
to be refused here. A gate that accepted everything would pass every other case
in this file.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.historical_source_acquisition import (POLICY_PATH, REQUIRED_POLICY_FIELDS,
                                                 HistoricalAcquisitionError,
                                                 acquisition_allowance,
                                                 historical_dependencies,
                                                 historical_dependency,
                                                 offline_source_plan)
from vnext.normal_source_requirements import discover_saved_source_requirements
from tests.vnext.test_normal_zero_ai_results import original_sources_only

SALESFORCE = "salesforce"
MARRIOTT = "marriott_international"
# The newest period, whose proxy is one of the ten saved.
NEWEST = "2025-12-31"
# Two years back. The current-period discovery reaches one.
FY2024 = ("https://www.sec.gov/Archives/edgar/data/1108524/000110852424000005/"
          "crm-20240131.htm")
FY2025 = ("https://www.sec.gov/Archives/edgar/data/1108524/000110852425000006/"
          "crm-20250131.htm")


class HistoricalSourceAcquisitionTest(unittest.TestCase):
    def test_the_gate_reaches_the_years_the_frame_asks_for(self):
        """The boundary, stated on both gates rather than on one.

        The existing discovery declares the current annual primary and one
        prior; this issue's frame needs four prior years. Asserting only that
        the new gate accepts FY2024 would not show that anything changed, so
        the old gate is asked the same question in the same case.
        """
        declared = {row["source_url"] for row in
                    discover_saved_source_requirements(repo_root=ROOT,
                                                       company_id=SALESFORCE)["requirements"]}
        self.assertIn(FY2025, declared)
        self.assertNotIn(FY2024, declared)
        plan = offline_source_plan(repo_root=ROOT, company_id=SALESFORCE, url=FY2024)
        self.assertEqual("OFFLINE_SOURCE_PLAN", plan["status"])
        self.assertEqual([0, 0, 0], plan["calls"])
        self.assertEqual(FY2024, plan["dependency"]["source_url"])
        self.assertFalse(plan["production_authorized"])

    def test_a_url_nothing_declares_is_refused_by_name(self):
        """The gate is what stops an arbitrary URL, so it still has to stop one."""
        for url in (FY2024.replace("crm-20240131", "crm-19990131"),
                    "https://www.sec.gov/Archives/edgar/data/1108524/0/nope.htm",
                    "https://example.invalid/crm-20240131.htm"):
            with self.subTest(url=url):
                with self.assertRaises(HistoricalAcquisitionError) as refused:
                    offline_source_plan(repo_root=ROOT, company_id=SALESFORCE, url=url)
                self.assertTrue(str(refused.exception).startswith(
                    "HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY:"))

    def test_one_company_s_dependency_is_not_another_s(self):
        with self.assertRaises(HistoricalAcquisitionError):
            historical_dependency(repo_root=ROOT, company_id="macys", url=FY2024)

    def test_the_declaration_is_the_planner_s_own_and_is_deduplicated(self):
        rows = historical_dependencies(repo_root=ROOT, company_id=SALESFORCE)
        urls = [row["source_url"] for row in rows]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all(row["new_acquisition_required"] for row in rows))
        self.assertIn(FY2024, urls)

    def test_the_governance_declaration_is_exactly_what_the_route_reads(self):
        """Both directions, because a declaration can be wrong either way.

        Too short and the gate refuses a document the route needs, which no
        allowance can unblock. Too long and an allowance is spent fetching a
        document nobody reads. So this runs the route for a period whose
        governance source IS saved, collects the URL it actually requested
        under the proxy role, and requires the declaration for that period to
        be exactly that one URL - not to contain it.
        """
        from vnext.historical_governance_sources import (DEPENDENCY_CLASS,
                                                         governance_dependencies)
        from vnext.historical_text_input import prepare_historical_business_text_input
        from vnext.normal_period_selection import resolve_period_selection
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=NEWEST)
            prepared = prepare_historical_business_text_input(
                repo_root=ROOT, company_id=MARRIOTT, metric_id="C02",
                period_selection=selection)
            declared = governance_dependencies(repo_root=ROOT, company_id=MARRIOTT,
                                               report_ends=[NEWEST])
        read = {reference["source_url"] for reference in prepared["source_references"]
                if reference["source_role"] == "governance_proxy"}
        self.assertEqual(1, len(read))
        self.assertEqual(read, {row["source_url"] for row in declared["requirements"]})
        self.assertEqual({DEPENDENCY_CLASS},
                         {row["dependency_class"] for row in declared["requirements"]})
        self.assertEqual([], declared["limitations"])

    def test_an_earlier_period_declares_its_own_meeting_and_needs_it(self):
        """The year decides the document, and the newest one is already here.

        A declaration built from "the newest proxy" would name the 2026 filing
        for every period, and that filing is saved - so the earlier periods
        would read as needing nothing while the route cannot resolve them.
        """
        from vnext.historical_governance_sources import governance_dependencies
        with original_sources_only():
            declared = governance_dependencies(repo_root=ROOT, company_id=MARRIOTT,
                                               report_ends=[NEWEST, "2024-12-31"])
        by_period = {row["consumers"][0]: row for row in declared["requirements"]}
        newest, prior = "period:" + NEWEST + ":C02", "period:2024-12-31:C02"
        self.assertEqual({newest, prior}, set(by_period))
        self.assertNotEqual(by_period[newest]["source_url"],
                            by_period[prior]["source_url"])
        self.assertEqual("2026-03-27", by_period[newest]["filing_date"])
        self.assertEqual("2025-03-27", by_period[prior]["filing_date"])
        self.assertEqual("VERIFIED_SAVED_SOURCE", by_period[newest]["saved_status"])
        self.assertEqual("MISSING_SAVED_SOURCE", by_period[prior]["saved_status"])

    def test_a_period_without_its_annual_primary_declares_nothing_and_says_so(self):
        """An undeclarable period is a limitation, not an empty requirement.

        The plan that names the governance document needs the year's own
        annual primary first, so a year whose primary is not saved cannot have
        its proxy named. Reporting that as "needs nothing" is how a
        declaration silently shrinks.
        """
        from vnext.historical_governance_sources import governance_dependencies
        with original_sources_only():
            declared = governance_dependencies(repo_root=ROOT, company_id=MARRIOTT,
                                               report_ends=["2022-12-31"])
        self.assertEqual([], declared["requirements"])
        self.assertEqual(1, len(declared["limitations"]))
        self.assertEqual("2022-12-31", declared["limitations"][0]["report_end"])
        self.assertIn("SAVED_SOURCE_MISSING", declared["limitations"][0]["reason"])

    def test_there_is_no_allowance_and_the_refusal_says_what_is_missing(self):
        """A number in a document is not an ask; a described object is."""
        self.assertFalse((ROOT / POLICY_PATH).exists())
        with self.assertRaises(HistoricalAcquisitionError) as refused:
            acquisition_allowance(repo_root=ROOT)
        reason = str(refused.exception)
        self.assertTrue(reason.startswith("ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED:"))
        self.assertIn(POLICY_PATH, reason)
        for field in REQUIRED_POLICY_FIELDS:
            self.assertIn(field, reason)

    def test_issue_28_s_allowance_is_not_this_issue_s(self):
        """It must not fall back, because falling back is the forbidden thing.

        Issue #28's record is bound to its own requirement_id and its own
        coordinate scope, and this issue's text forbids drawing on it. So a
        record carrying that requirement_id is refused even when it is complete
        and in the right place.
        """
        approved = json.loads((ROOT / "config/issue28_continuous_calls_v1.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual("issue_28_v14", approved["requirement_id"])
        with TemporaryDirectory(prefix="issue47-allowance-") as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            borrowed = {field: approved.get(field, "x") for field in REQUIRED_POLICY_FIELDS}
            borrowed["requirement_id"] = "issue_28_v14"
            (root / POLICY_PATH).write_text(json.dumps(borrowed), encoding="utf-8")
            with self.assertRaises(HistoricalAcquisitionError) as refused:
                acquisition_allowance(repo_root=root)
            self.assertTrue(str(refused.exception).startswith(
                "ISSUE_47_SEC_ALLOWANCE_IS_FOR_ANOTHER_REQUIREMENT:"))
            # And an incomplete record of its own is refused for what it lacks.
            (root / POLICY_PATH).write_text(json.dumps({"requirement_id": "issue_47_v1"}),
                                            encoding="utf-8")
            with self.assertRaises(HistoricalAcquisitionError) as short:
                acquisition_allowance(repo_root=root)
            self.assertTrue(str(short.exception).startswith(
                "ISSUE_47_SEC_ALLOWANCE_INCOMPLETE:"))


if __name__ == "__main__":
    unittest.main()
