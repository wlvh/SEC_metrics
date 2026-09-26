"""An amendment's declared scope decides which inputs still stand.

The historical route used to refuse any period carrying a 10-K/A, and that
refusal was recorded as a business question needing a decision. It was not one:
config/annual_amendment_scope_v1.json is an approved policy that already
classifies these shapes. These cases run it against the two real amendments the
repository holds, because a policy that only works on constructed fixtures is
not evidence that it decides real filings.

The two amendments differ in exactly the way the policy exists to distinguish,
which is why both are needed. Southwest's corrects one exhibit hyperlink and
says in its own explanatory note that it modifies nothing else; Paramount's
adds Part III Items 10 to 14 and declares no new financial statements. So the
same question - may this metric resolve? - gets different answers per company
and per input class, and a test that only checked one would pass on a route
that ignored the classification entirely.
"""
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_amendment_admission import (NOT_COVERED_METRIC_IDS,
                                                  AmendmentAdmissionError,
                                                  amendment_admission,
                                                  required_input_class)
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.historical_zero_ai_results import EVENT_METRICS
from vnext.normal_period_selection import resolve_period_selection

LINK_CORRECTION = "southwest_airlines"
PART_III = "paramount_skydance_paramount_global"
NO_AMENDMENT = "ford_motor_company"
PERIOD = "2025-12-31"


def _prepared(company_id):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=PERIOD)
        return prepare_historical_annual_input(repo_root=ROOT, company_id=company_id,
                                               period_selection=selection)


def _admit(company_id, metric_ids, prepared):
    with original_sources_only():
        return amendment_admission(repo_root=ROOT, company_id=company_id,
                                   metric_ids=metric_ids, prepared=prepared,
                                   event_metric_ids=EVENT_METRICS)


class AmendmentAdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.link = _prepared(LINK_CORRECTION)
        cls.part_iii = _prepared(PART_III)

    def test_both_corpus_filings_really_carry_one_amendment(self):
        """Otherwise these cases would be asserting nothing."""
        for prepared in (self.link, self.part_iii):
            self.assertEqual(1, len(prepared["amendments"]))
            self.assertEqual("10-K/A", prepared["amendments"][0]["form"])
            self.assertEqual("10-K", prepared["filing"]["form"])
        self.assertEqual([], list(_prepared(NO_AMENDMENT)["amendments"]))

    def test_a_link_correction_clears_both_input_classes(self):
        record = _admit(LINK_CORRECTION, ["B01"], self.link)
        self.assertTrue(record["admitted"])
        self.assertEqual("ORIGINAL_STATEMENT_VALUES", record["required_input_class"])
        self.assertEqual(["EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15"],
                         [a["classification"] for a in record["amendments"]])
        self.assertEqual([[]], [a["issues"] for a in record["amendments"]])
        # The target is the original filing; the amendment is only evidence.
        self.assertEqual(self.link["filing"]["accessionNumber"], record["target_accession"])
        self.assertTrue(_admit(LINK_CORRECTION, ["E01"], self.link)["admitted"])

    def test_a_part_three_addition_clears_the_event_window_and_not_the_statements(self):
        """The distinction the policy exists for, on the filing that makes it."""
        events = _admit(PART_III, ["E01"], self.part_iii)
        self.assertTrue(events["admitted"])
        self.assertEqual("FISCAL_EVENT_WINDOW", events["required_input_class"])
        self.assertEqual(["PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS"],
                         [a["classification"] for a in events["amendments"]])
        for metrics in (["B01"], ["B02", "B04", "A05"]):
            with self.subTest(metrics=metrics):
                with self.assertRaises(AmendmentAdmissionError) as refused:
                    _admit(PART_III, metrics, self.part_iii)
                reason = str(refused.exception)
                # The reason names the classification. Reporting a decided
                # policy refusal as NOT_IMPLEMENTED is how a settled question
                # reads as an open one.
                self.assertIn("HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED", reason)
                self.assertIn("ORIGINAL_STATEMENT_VALUES", reason)
                self.assertIn("PART_III_ADDITION", reason)
                self.assertNotIn("NOT_IMPLEMENTED", reason)

    def test_the_two_companies_do_not_get_the_same_answer(self):
        """A route ignoring the classification would pass every case but this."""
        self.assertTrue(_admit(LINK_CORRECTION, ["B01"], self.link)["admitted"])
        with self.assertRaises(AmendmentAdmissionError):
            _admit(PART_III, ["B01"], self.part_iii)

    def test_the_metrics_the_policy_does_not_cover_are_refused_either_way(self):
        self.assertTrue(NOT_COVERED_METRIC_IDS)
        for company, prepared in ((LINK_CORRECTION, self.link), (PART_III, self.part_iii)):
            for metric in sorted(NOT_COVERED_METRIC_IDS):
                with self.subTest(company=company, metric=metric):
                    with self.assertRaises(AmendmentAdmissionError) as refused:
                        _admit(company, [metric], prepared)
                    self.assertIn("NOT_COVERED_BY_POLICY", str(refused.exception))

    def test_two_input_classes_cannot_share_one_decision(self):
        """B01 and E01 get different answers from Paramount's amendment."""
        with self.assertRaises(AmendmentAdmissionError) as refused:
            _admit(PART_III, ["B01", "E01"], self.part_iii)
        self.assertIn("MIXED_INPUT_CLASSES", str(refused.exception))

    def test_the_required_class_follows_the_route_s_own_event_set(self):
        for metric in EVENT_METRICS:
            self.assertEqual("FISCAL_EVENT_WINDOW",
                             required_input_class(metric_id=metric,
                                                  event_metric_ids=EVENT_METRICS))
        for metric in ("B01", "B03", "B02", "A05"):
            self.assertEqual("ORIGINAL_STATEMENT_VALUES",
                             required_input_class(metric_id=metric,
                                                  event_metric_ids=EVENT_METRICS))
        # An empty event set is not a licence: everything is then a statement
        # metric, which is the stricter reading rather than the looser one.
        self.assertEqual("ORIGINAL_STATEMENT_VALUES",
                         required_input_class(metric_id="E01", event_metric_ids=()))


if __name__ == "__main__":
    unittest.main()
