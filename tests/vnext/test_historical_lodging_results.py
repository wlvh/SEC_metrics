"""B10 and B11 for a pinned period, against the ordinary route and across years.

The load-bearing pair is one company answered for three periods. Marriott is
the only lodging operator in this repository and it holds three saved annual
originals, so a route that took the newest filing would give all three the same
value and pass every case that only checks that a number came out.

The current period is asserted against the ordinary route rather than against a
constant: same value, same unit, same quality, same table and same Spec. A
route reading a different table in the same filing would agree on the number
whenever the filing repeats it, so the table identity is part of the claim.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_coverage import WIRED_HISTORICAL_METRICS
from vnext.historical_lodging_results import (SPEC_PATHS, SUPPORTED_METRICS,
                                              HistoricalLodgingError,
                                              resolve_historical_lodging_metric)
from vnext.historical_results import prepare_historical_run_input
from vnext.normal_lodging_results import prepare_ordinary_lodging_case
from vnext.normal_period_selection import resolve_period_selection

MARRIOTT = "marriott_international"
NOT_A_HOTEL = "pfizer"
CURRENT = "2025-12-31"
EARLIER = ("2024-12-31", "2023-12-31")
RESULT_FIELDS = ("value", "unit", "quality", "publication", "reason_code", "applicability")


def _historical(company_id, report_end, metric_id):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return resolve_historical_lodging_metric(
            repo_root=ROOT, company_id=company_id, metric_id=metric_id,
            period_selection=selection)


def _ordinary(metric_id):
    with original_sources_only():
        return prepare_ordinary_lodging_case(repo_root=ROOT, company_id=MARRIOTT,
                                             metric_id=metric_id)


class HistoricalLodgingResultsTest(unittest.TestCase):
    def test_the_current_period_matches_the_ordinary_route_field_for_field(self):
        for metric_id in SUPPORTED_METRICS:
            with self.subTest(metric_id):
                ordinary = _ordinary(metric_id)
                period = ordinary["target_period"]
                historical = _historical(MARRIOTT, period["period_end"], metric_id)
                for field in RESULT_FIELDS:
                    self.assertEqual(ordinary["results"][metric_id][field],
                                     historical["result"][field], field)
                self.assertEqual(ordinary["selection"]["table_id"],
                                 historical["selection"]["table_id"],
                                 "the same table has to answer, not just the same number")
                self.assertEqual(ordinary["spec_paths"][metric_id], historical["spec_path"])

    def test_the_observation_behind_the_value_is_the_same_reading(self):
        """Seventeen binding fields, sixteen equal and the seventeenth named.

        The result fields above would agree with a route that found the same
        number somewhere else in the filing, so the claim is made where the
        reading is: the raw asset, the source reference, the derived table
        grid, the cell locator, the raw text and the witnesses.

        `source_component_id` is the one that differs, and not because the
        reading does. It hashes the filing record, and the pinned selector
        projects that to the five fields that identify a filing while the
        latest-period preparation carries the whole submissions row - ten more
        fields of SEC bookkeeping, `filmNumber` and `size` among them. Two
        readings of the same bytes therefore get two component identities. The
        narrower record is the better identity for a business claim, so this
        asserts the difference rather than removing it, and a second field
        joining it would fail here.
        """
        for metric_id in SUPPORTED_METRICS:
            with self.subTest(metric_id):
                ordinary = _ordinary(metric_id)
                period = ordinary["target_period"]
                historical = _historical(MARRIOTT, period["period_end"], metric_id)
                expected = ordinary["observations"][0]["source_binding"]
                measured = historical["observation"]["source_binding"]
                self.assertEqual(set(expected), set(measured))
                differ = sorted(key for key in expected
                                if expected[key] != measured[key])
                self.assertEqual(["source_component_id"], differ)
                self.assertGreater(len(expected), 10, "a binding of two fields proves little")

    def test_each_earlier_period_is_answered_by_its_own_filing(self):
        """The pinned rule, stated where it bites.

        Three periods, three different values in each metric. A route that read
        the newest annual report would return the current period's figure for
        all three and satisfy every other case in this file.
        """
        for metric_id in SUPPORTED_METRICS:
            with self.subTest(metric_id):
                answers = {}
                for report_end in (CURRENT, *EARLIER):
                    component = _historical(MARRIOTT, report_end, metric_id)
                    result = component["result"]
                    self.assertEqual(("EXACT", "PUBLISHED", "PASS"),
                                     (result["quality"], result["publication"],
                                      result["reason_code"]))
                    self.assertEqual(report_end, component["target_period"]["period_end"])
                    self.assertEqual(report_end[:4] + "-01-01",
                                     component["target_period"]["period_start"])
                    answers[report_end] = result["value"]
                self.assertEqual(3, len(set(answers.values())), answers)

    def test_the_closed_side_of_the_gate_stays_with_the_structural_route(self):
        """Two answers for one pair is worse than one, even if both are right.

        For a company that is not a lodging operator the answer is that the
        metric does not apply, and the structural route owns it. This one
        refuses by name so the dispatcher cannot end up with both.
        """
        for metric_id in SUPPORTED_METRICS:
            with self.subTest(metric_id):
                with original_sources_only():
                    selection = resolve_period_selection(repo_root=ROOT,
                                                         company_id=NOT_A_HOTEL,
                                                         report_end=CURRENT)
                    with self.assertRaises(HistoricalLodgingError) as refused:
                        resolve_historical_lodging_metric(
                            repo_root=ROOT, company_id=NOT_A_HOTEL, metric_id=metric_id,
                            period_selection=selection)
                self.assertTrue(str(refused.exception).startswith(
                    "HISTORICAL_LODGING_METRIC_NOT_APPLICABLE:"))

    def test_the_dispatcher_sends_each_company_to_the_route_that_owns_it(self):
        with original_sources_only():
            hotel_selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                       report_end=CURRENT)
            other_selection = resolve_period_selection(repo_root=ROOT,
                                                       company_id=NOT_A_HOTEL,
                                                       report_end=CURRENT)
            hotel = prepare_historical_run_input(repo_root=ROOT, company_id=MARRIOTT,
                                                 metric_id="B10",
                                                 period_selection=hotel_selection)
            other = prepare_historical_run_input(repo_root=ROOT, company_id=NOT_A_HOTEL,
                                                 metric_id="B10",
                                                 period_selection=other_selection)
        self.assertEqual("HISTORICAL_LODGING_COMPONENT",
                         hotel["component"]["record_type"])
        self.assertEqual("PASS", hotel["primary_result"]["reason_code"])
        self.assertEqual("TRAIT_NOT_APPLICABLE", other["primary_result"]["reason_code"])
        self.assertNotEqual("HISTORICAL_LODGING_COMPONENT",
                            other["component"]["record_type"])

    def test_the_deterministic_spec_answers_and_no_model_response_is_read(self):
        """The AI Specs for these two metrics exist and are not what this uses.

        `lodging_table_source`'s policy names them as the originals its
        deterministic Specs derive from, so compiling the wrong one is one
        dictionary lookup away and would put the Result under a different Spec
        identity while reading the same table.
        """
        for metric_id in SUPPORTED_METRICS:
            with self.subTest(metric_id):
                component = _historical(MARRIOTT, CURRENT, metric_id)
                self.assertEqual("catalog/ordinary_lodging/" + metric_id + ".md",
                                 SPEC_PATHS[metric_id])
                self.assertEqual(SPEC_PATHS[metric_id], component["spec_path"])
                self.assertIs(False, component["selection"]["ai_response_used"])
                self.assertIs(False, component["selection"]["qualification_credit"])
                self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, component["calls"])

    def test_both_metrics_are_registered_as_wired(self):
        for metric_id in ("B10", "B11"):
            self.assertIn(metric_id, SUPPORTED_METRICS)
            self.assertIn(metric_id, WIRED_HISTORICAL_METRICS)

    def test_a_fact_about_another_period_is_refused_rather_than_used(self):
        """A guard no filing exercises, exercised by constructing the divergence.

        The four fault injections run against this suite caught three of the
        four edits; dropping this check changed nothing on any real filing,
        because `inspect_lodging_table_source` already re-derives the source's
        own annual interval from its bytes and the scope comes from the same
        compiled Spec. The check is kept anyway - the ordinary route makes it,
        and a pinned route that checks less than the route it mirrors is a
        weakening - so it is exercised here by making the inspector return a
        fact about a different period, which is exactly the divergence it
        defends against.

        The input is constructed and says so. What it must not do is produce a
        value: a route that took the fact at its word would return the same
        number under the wrong period.
        """
        from unittest import mock

        import vnext.historical_lodging_results as route

        real = route.inspect_lodging_table_source

        def shifted(**kwargs):
            component = real(**kwargs)
            facts = dict(component["selection"]["facts"])
            for metric_id, fact in facts.items():
                period = dict(fact["period"])
                period["period_end"] = "1999-12-31"
                facts[metric_id] = {**fact, "period": period}
            selection = {**component["selection"], "facts": facts}
            return {**component, "selection": selection}

        with mock.patch.object(route, "inspect_lodging_table_source", shifted):
            component = _historical(MARRIOTT, CURRENT, "B10")
        self.assertIsNone(component["result"]["value"])
        self.assertEqual("HISTORICAL_LODGING_SOURCE_ROUTE_UNRESOLVED",
                         component["result"]["reason_code"])
        self.assertIn("HISTORICAL_LODGING_SCOPE_OR_PERIOD_CHANGED",
                      component["limitation"]["reason"])
        # And the unpatched call still delivers, so the case is about the
        # divergence rather than about the patch being present.
        self.assertIsNotNone(_historical(MARRIOTT, CURRENT, "B10")["result"]["value"])


if __name__ == "__main__":
    unittest.main()
