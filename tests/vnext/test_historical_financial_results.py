"""The six financial metrics' open side, against the ordinary route.

No position of the five-year frame reaches this route today: JPMorgan is the
only registrant whose traits open the ``financial`` gate, and every one of its
target periods fails selection on the saved catalog. So the load-bearing check
is the substitution itself: the ordinary preparation handed to both the
ordinary resolver and this one must give every returned field equal, for all
six metrics, on JPMorgan's real latest filing. The pinned-input half - an
earlier year's preparation, an amended period's extra proofs - is exercised on
companies whose periods do resolve.

JPMorgan's primary document is parsed once per metric. The frozen fact
inspector is shared between the two calls under a key that covers every byte
of the bundle it is handed, so a pinned route that built a different bundle
would miss the shared entry and be computed on its own rather than borrow the
ordinary route's answer.
"""
import hashlib
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import financial_results, historical_financial_results as pinned
from vnext import ordinary_financial_results as ordinary
from vnext.annual_update import saved_source
from vnext.canonical import content_hash
from vnext.financial_results import FinancialResultError
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.historical_coverage import STRUCTURAL_APPLICABILITY_METRICS, WIRED_HISTORICAL_METRICS
from vnext.historical_results import prepare_historical_run_input
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.traits import repository_company_traits
from sec_urls import submissions_file_url

BANK = "jpmorgan_chase"
_FACTS = {}
_FROZEN_FACT = financial_results._fact


def _shared_fact(*, metric_id, bundle):
    """The frozen inspector, computed once per exact bundle."""
    key = content_hash(value={
        "metric_id": metric_id,
        "source": hashlib.sha256(bundle["source_bytes"]).hexdigest(),
        "inventory": hashlib.sha256(bundle["inventory_bytes"]).hexdigest(),
        **{k: v for k, v in bundle.items() if k not in ("source_bytes", "inventory_bytes")}})
    if key not in _FACTS:
        _FACTS[key] = _FROZEN_FACT(metric_id=metric_id, bundle=bundle)
    return _FACTS[key]


def _shared():
    return (patch.object(ordinary, "_fact", _shared_fact),
            patch.object(pinned, "_fact", _shared_fact))


def _pinned_input(company_id, report_end):
    selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                         report_end=report_end)
    return selection, prepare_historical_annual_input(repo_root=ROOT, company_id=company_id,
                                                      period_selection=selection)


class TheRestatedResolverIsTheOrdinaryOne(unittest.TestCase):
    """Same preparation in, every field out equal - for all six metrics."""

    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.prepared = prepare_saved_annual_input(repo_root=ROOT, company_id=BANK)

    def test_all_six_on_the_bank_s_latest_filing(self):
        first, second = _shared()
        with original_sources_only(), first, second:
            for metric_id in pinned.SUPPORTED_METRICS:
                with self.subTest(metric_id):
                    expected = ordinary.resolve_current_financial_metric(
                        repo_root=ROOT, company_id=BANK, metric_id=metric_id)
                    actual = pinned.resolve_prepared_financial_metric(
                        repo_root=ROOT, company_id=BANK, metric_id=metric_id,
                        prepared=self.prepared)
                    self.assertEqual(sorted(expected), sorted(actual))
                    for field in expected:
                        self.assertEqual(expected[field], actual[field], field)
                    # Two identical refusals would also be equal; the claim is
                    # that the value the ordinary route delivers is delivered.
                    self.assertEqual(("APPLICABLE", "EXACT", "PUBLISHED"),
                                     tuple(actual["result"][k] for k in
                                           ("applicability", "quality", "publication")))

    def test_the_read_proofs_are_found_by_what_they_are_not_by_position(self):
        """A pinned preparation carries more than three proofs, in any order.

        Reversed, and with a history block's proof appended, the same three
        documents have to be read. A reader taking the first three would hand
        the company facts to the source-set builder as the submissions
        inventory, which it refuses.
        """
        block = saved_source(repo_root=ROOT,
                             url=submissions_file_url(file_name="CIK0000019617-submissions-004.json"),
                             accession="")
        self.assertIsNotNone(block, "the saved history block this case needs is missing")
        shuffled = {**self.prepared,
                    "source_proofs": [*reversed(self.prepared["source_proofs"]), block["proof"]]}
        first, second = _shared()
        with original_sources_only(), first, second:
            expected = pinned.resolve_prepared_financial_metric(
                repo_root=ROOT, company_id=BANK, metric_id="A04", prepared=self.prepared)
            actual = pinned.resolve_prepared_financial_metric(
                repo_root=ROOT, company_id=BANK, metric_id="A04", prepared=shuffled)
        self.assertEqual(expected["source_references"], actual["source_references"])
        self.assertEqual(expected["source_fact"], actual["source_fact"])
        for field in ("value", "quality", "reason_code", "period_start", "period_end"):
            self.assertEqual(expected["result"][field], actual["result"][field], field)
        # The extra proof travels with the Run; it is carried, not read.
        self.assertIn(block["proof"], actual["source_proofs"])

    def test_a_proof_set_missing_one_of_the_three_is_refused(self):
        partial = {**self.prepared, "source_proofs": self.prepared["source_proofs"][:2]}
        with original_sources_only(), self.assertRaises(FinancialResultError) as caught:
            pinned.resolve_prepared_financial_metric(repo_root=ROOT, company_id=BANK,
                                                     metric_id="A04", prepared=partial)
        self.assertEqual("NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE", str(caught.exception))


class ThePinnedInputPassesThroughUnchanged(unittest.TestCase):
    """The pinned preparation's shape, on periods that do resolve."""

    def test_an_earlier_year_gives_what_the_ordinary_route_gives_that_preparation(self):
        """Marriott FY2023 through both resolvers, the ordinary one handed it.

        The gate is closed for a hotel company, so this is the closed side of the
        ordinary code - which is not this route's to answer in the frame, but is
        the part of the restated body that runs on a real earlier year's
        preparation: the five-field filing, the three proofs found by URL, the
        source set discovered from that year's filing day.
        """
        with original_sources_only():
            _, prepared = _pinned_input("marriott_international", "2023-12-31")
            original = prepared["original_input"]
            with patch.object(ordinary, "prepare_saved_annual_input",
                              return_value=original) as handed:
                expected = ordinary.resolve_current_financial_metric(
                    repo_root=ROOT, company_id="marriott_international", metric_id="A04")
            handed.assert_called_once()
            actual = pinned.resolve_prepared_financial_metric(
                repo_root=ROOT, company_id="marriott_international", metric_id="A04",
                prepared=original)
        for field in expected:
            self.assertEqual(expected[field], actual[field], field)
        self.assertEqual("0001628280-24-004372", actual["source_references"][1]["accession"])

    def test_an_amended_period_s_extra_proof_travels_without_being_read(self):
        """The ordinary reader requires exactly three proofs; a pinned one cannot.

        Paramount's FY2025 carries its Part III amendment's proof so the
        installed data root can replay the amendment decision. The ordinary
        reader refuses that preparation as incomplete; the restated one reads
        the same three documents and carries the fourth.
        """
        with original_sources_only():
            _, prepared = _pinned_input("paramount_skydance_paramount_global", "2025-12-31")
            original = prepared["original_input"]
            self.assertGreater(len(original["source_proofs"]), 3)
            with patch.object(ordinary, "prepare_saved_annual_input", return_value=original), \
                    self.assertRaises(FinancialResultError) as caught:
                ordinary.resolve_current_financial_metric(
                    repo_root=ROOT, company_id="paramount_skydance_paramount_global",
                    metric_id="A04")
            self.assertEqual("NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE", str(caught.exception))
            actual = pinned.resolve_prepared_financial_metric(
                repo_root=ROOT, company_id="paramount_skydance_paramount_global",
                metric_id="A04", prepared=original)
        self.assertEqual(original["source_proofs"], actual["source_proofs"])
        self.assertEqual(3, len(actual["source_references"]))
        self.assertEqual("N_A_STRUCTURAL", actual["result"]["applicability"])

    def test_the_entrypoint_reads_the_pinned_filing_and_hands_on_the_unrelabelled_body(self):
        """The wrapper's own preparation, exercised with the gate forced open.

        No financial registrant has a reachable period, so the one path this
        module adds - pinned selection to preparation to resolver - is run on
        Marriott FY2023 with the bank's traits standing in for Marriott's.
        That is a constructed input and the assertions are only about which
        filing was read and which body was handed on, never about a value: the
        inspectors are free to find nothing in a hotel company's report.
        """
        bank = repository_company_traits(repo_root=ROOT, company_id=BANK)
        with original_sources_only(), \
                patch.object(pinned, "repository_company_traits", return_value=bank):
            selection, prepared = _pinned_input("marriott_international", "2023-12-31")
            component = pinned.resolve_historical_financial_metric(
                repo_root=ROOT, company_id="marriott_international", metric_id="A04",
                period_selection=selection)
        self.assertEqual("0001628280-24-004372", component["source_references"][1]["accession"])
        self.assertEqual(prepared["original_input"],
                         component["input_binding"]["prepared_input"])
        self.assertEqual(prepared["table_input"]["target_period"], component["target_period"])
        self.assertEqual(prepared["source_proofs"], component["source_proofs"])
        self.assertEqual("APPLICABLE", component["result"]["applicability"])


class TheGateIsAnsweredOnce(unittest.TestCase):
    def test_the_closed_side_is_refused_here_and_answered_by_the_structural_route(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id="macys",
                                                 report_end="2026-01-31")
            with self.assertRaises(FinancialResultError) as caught:
                pinned.resolve_historical_financial_metric(
                    repo_root=ROOT, company_id="macys", metric_id="A03",
                    period_selection=selection)
            self.assertEqual("HISTORICAL_FINANCIAL_METRIC_NOT_APPLICABLE:macys",
                             str(caught.exception))
            self.assertEqual("IMPLEMENTATION_GAP", caught.exception.category)
            closed = prepare_historical_run_input(repo_root=ROOT, company_id="macys",
                                                  metric_id="A03", period_selection=selection)
        self.assertEqual("HISTORICAL_STRUCTURAL_RESULT", closed["component"]["record_type"])

    def test_the_dispatcher_sends_the_bank_to_this_route(self):
        """Routing only: the bank has no selection to resolve with.

        The resolver is replaced by one that records it was reached, and the
        structural one by one that fails if it is.
        """
        reached = []

        def here(**arguments):
            reached.append(arguments["metric_id"])
            raise LookupError("REACHED")

        def elsewhere(**arguments):
            raise AssertionError("the structural route answered an open gate")

        for metric_id in pinned.SUPPORTED_METRICS:
            with patch.object(pinned, "resolve_historical_financial_metric", here), \
                    patch("vnext.historical_structural_results."
                          "resolve_historical_structural_metric", elsewhere), \
                    self.assertRaises(LookupError):
                prepare_historical_run_input(repo_root=ROOT, company_id=BANK,
                                             metric_id=metric_id, period_selection={})
        self.assertEqual(list(pinned.SUPPORTED_METRICS), reached)

    def test_the_six_are_wired_and_no_metric_is_structural_only(self):
        self.assertTrue(set(pinned.SUPPORTED_METRICS) <= set(WIRED_HISTORICAL_METRICS))
        self.assertEqual((), STRUCTURAL_APPLICABILITY_METRICS)


if __name__ == "__main__":
    unittest.main()
