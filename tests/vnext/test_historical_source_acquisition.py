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
        """A number in a document is not an ask; a described object is.

        Asked of a tree that has no allowance, not of this checkout. The
        previous version asserted that the checkout had none, which stops
        being true the day the owner registers the approval and commits it -
        a case that fails because the grant arrived tests the calendar.
        """
        with TemporaryDirectory(prefix="issue47-no-allowance-") as empty:
            with self.assertRaises(HistoricalAcquisitionError) as refused:
                acquisition_allowance(repo_root=Path(empty))
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



class TheGithubReaderPassesGhOnlyWhatItNeeds(unittest.TestCase):
    """The approval re-check runs gh; a provider key in the caller's environment stays behind."""

    def test_the_environment_is_narrowed(self):
        import os
        import subprocess
        from unittest import mock
        from vnext.historical_source_acquisition import GH_ENVIRONMENT, github_comment_reader
        seen = {}

        def run(argv, **kwargs):
            seen.update(argv=argv, env=kwargs["env"])
            return subprocess.CompletedProcess(argv, 0, stdout='{"id": 1}', stderr="")

        caller = {"DEEPSEEK_API_KEY": "secret", "GH_TOKEN": "token", "PATH": "/usr/bin",
                  "AWS_SECRET_ACCESS_KEY": "secret"}
        with mock.patch.dict(os.environ, caller, clear=True), mock.patch("subprocess.run", run):
            self.assertEqual({"id": 1}, github_comment_reader("repos/o/r/issues/comments/1"))
        self.assertEqual(["gh", "api", "--hostname", "github.com", "repos/o/r/issues/comments/1"], seen["argv"])
        self.assertEqual({"GH_TOKEN": "token", "PATH": "/usr/bin"}, seen["env"])
        self.assertTrue(set(seen["env"]) <= set(GH_ENVIRONMENT))

    def test_a_reply_that_is_not_strict_json_is_refused(self):
        import subprocess
        from unittest import mock
        from vnext.historical_source_acquisition import HistoricalAcquisitionError, github_comment_reader

        def run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout='{"id": 1, "id": 2}', stderr="")

        with mock.patch("subprocess.run", run), self.assertRaises(HistoricalAcquisitionError) as caught:
            github_comment_reader("repos/o/r/issues/comments/1")
        self.assertIn("ISSUE_47_GITHUB_READ_NOT_STRICT_JSON", str(caught.exception))



class TheRestReaderReadsOnlyThisIssuesComments(unittest.TestCase):
    """The reader for a host without gh, which is where the owner decided the acquisition runs.

    It can be pointed at one comment of this repository's issue 47 or at a page
    of that issue's comment list, and at nothing else: a reader that fetched
    whatever path it was handed could be aimed at another repository's
    "approval" as easily as at this one.
    """

    def _response(self, text, final):
        class Response:
            def geturl(self):
                return final

            def read(self):
                return text.encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return Response()

    def test_only_this_issue_s_comment_resources_are_readable(self):
        from unittest import mock
        from vnext.historical_source_acquisition import (HistoricalAcquisitionError,
                                                         github_rest_reader)
        for path in ("repos/other/SEC_metrics/issues/comments/1",
                     "repos/wlvh/SEC_metrics/issues/28/comments?per_page=100&page=1",
                     "repos/wlvh/SEC_metrics/pulls/52",
                     "repos/wlvh/SEC_metrics/issues/comments/1?x=y",
                     "repos/wlvh/SEC_metrics/issues/comments/0",
                     "repos/wlvh/SEC_metrics/issues/47/comments?per_page=100&page=1&x=1"):
            with self.subTest(path):
                with mock.patch("urllib.request.urlopen",
                                side_effect=AssertionError("a request was made")), \
                        self.assertRaises(HistoricalAcquisitionError) as caught:
                    github_rest_reader(path)
                self.assertIn("ISSUE_47_GITHUB_READ_PATH_NOT_ALLOWED", str(caught.exception))

    def test_a_comment_and_a_list_page_are_read_from_the_api(self):
        from unittest import mock
        from vnext.historical_source_acquisition import github_rest_reader
        seen = []

        def urlopen(request, timeout):
            seen.append((request.full_url, request.get_header("Accept")))
            return self._response('{"id": 1}' if "comments/1" in request.full_url else "[]",
                                  request.full_url)

        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual({"id": 1},
                             github_rest_reader("repos/wlvh/SEC_metrics/issues/comments/1"))
            self.assertEqual([], github_rest_reader(
                "repos/wlvh/SEC_metrics/issues/47/comments?per_page=100&page=2"))
        self.assertEqual([("https://api.github.com/repos/wlvh/SEC_metrics/issues/comments/1",
                           "application/vnd.github+json"),
                          ("https://api.github.com/repos/wlvh/SEC_metrics/issues/47/comments"
                           "?per_page=100&page=2", "application/vnd.github+json")], seen)

    def test_a_reply_that_is_not_strict_json_is_refused(self):
        from unittest import mock
        from vnext.historical_source_acquisition import (HistoricalAcquisitionError,
                                                         github_rest_reader)
        with mock.patch("urllib.request.urlopen",
                        lambda request, timeout: self._response('{"id": 1, "id": 2}',
                                                                request.full_url)), \
                self.assertRaises(HistoricalAcquisitionError) as caught:
            github_rest_reader("repos/wlvh/SEC_metrics/issues/comments/1")
        self.assertIn("ISSUE_47_GITHUB_READ_NOT_STRICT_JSON", str(caught.exception))

    def test_a_redirected_read_is_refused(self):
        # urlopen follows redirects; a reply from anywhere else is not this
        # issue's comment, whatever it says.
        from unittest import mock
        from vnext.historical_source_acquisition import (HistoricalAcquisitionError,
                                                         github_rest_reader)
        elsewhere = "https://api.github.com/repos/other/SEC_metrics/issues/comments/1"
        with mock.patch("urllib.request.urlopen",
                        lambda request, timeout: self._response('{"id": 1}', elsewhere)), \
                self.assertRaises(HistoricalAcquisitionError) as caught:
            github_rest_reader("repos/wlvh/SEC_metrics/issues/comments/1")
        self.assertIn("ISSUE_47_GITHUB_READ_WAS_REDIRECTED", str(caught.exception))

    def test_a_failed_read_is_a_named_refusal(self):
        import urllib.error
        from unittest import mock
        from vnext.historical_source_acquisition import (HistoricalAcquisitionError,
                                                         github_rest_reader)
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("unreachable")), \
                self.assertRaises(HistoricalAcquisitionError) as caught:
            github_rest_reader("repos/wlvh/SEC_metrics/issues/comments/1")
        self.assertIn("ISSUE_47_GITHUB_READ_FAILED", str(caught.exception))

    def test_the_live_reader_is_gh_where_it_is_installed(self):
        from unittest import mock
        from vnext.historical_source_acquisition import (github_comment_reader,
                                                         github_rest_reader,
                                                         live_github_reader)
        with mock.patch("shutil.which", lambda name: "/usr/bin/gh"):
            self.assertIs(github_comment_reader, live_github_reader())
        with mock.patch("shutil.which", lambda name: None):
            self.assertIs(github_rest_reader, live_github_reader())


if __name__ == "__main__":
    unittest.main()
