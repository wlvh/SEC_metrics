"""C04 for a pinned annual period, and what it says when the material is not there.

The load-bearing case is one company answered for two periods. C04 delivers a
flag for the period whose accession material is saved and a withheld Result
naming the missing file for the one whose is not; a route that ignored the
period would give both the same answer and pass every other case here.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_coverage import WIRED_HISTORICAL_METRICS
from vnext.historical_governance_results import (SUPPORTED_METRICS,
                                                 HistoricalGovernanceError,
                                                 resolve_historical_governance_metric)
from vnext.historical_results import prepare_historical_run_input
from vnext.normal_period_selection import resolve_period_selection

MARRIOTT = "marriott_international"
# The most recent period, whose accession material is saved, and an earlier one
# whose is not. Both are in this repository's saved originals, so the pair is a
# real contrast rather than one real case and one fabricated absence.
DELIVERS = "2025-12-31"
WITHHOLDS = "2023-12-31"


def _resolve(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return resolve_historical_governance_metric(
            repo_root=ROOT, company_id=company_id, metric_id="C04",
            period_selection=selection)


class HistoricalGovernanceResultsTest(unittest.TestCase):
    def test_one_company_two_periods_two_answers(self):
        """The whole point of a pinned route, stated as a contrast."""
        delivered = _resolve(MARRIOTT, DELIVERS)["result"]
        withheld = _resolve(MARRIOTT, WITHHOLDS)["result"]
        self.assertEqual(("EXACT", "PUBLISHED", "PASS"),
                         (delivered["quality"], delivered["publication"],
                          delivered["reason_code"]))
        self.assertIsNotNone(delivered["value"])
        self.assertEqual(("NONE", "WITHHELD"),
                         (withheld["quality"], withheld["publication"]))
        self.assertNotEqual(delivered["reason_code"], withheld["reason_code"])
        # And each answers for its own period rather than for the newest one.
        self.assertEqual(DELIVERS, delivered["period_end"])
        self.assertEqual(WITHHOLDS, withheld["period_end"])

    def test_a_missing_file_is_a_source_gap_not_a_route_gap(self):
        """The frame has to be able to tell them apart.

        Reporting a missing accession index as an unimplemented route is how a
        settled question reads as an open one, and the reverse hides real work
        behind an acquisition request.
        """
        component = _resolve(MARRIOTT, WITHHOLDS)
        self.assertEqual("HISTORICAL_GOVERNANCE_SOURCE_ROUTE_UNRESOLVED",
                         component["result"]["reason_code"])
        self.assertIsNotNone(component["limitation"])
        self.assertIn("SAVED_SOURCE_MISSING", component["limitation"]["reason"])
        # A withheld Result still carries the sources that were read, so the
        # Run is about this period rather than about nothing.
        self.assertTrue(component["source_proofs"])
        self.assertTrue(component["source_references"])

    def test_the_selection_is_by_the_period_and_says_so(self):
        component = _resolve(MARRIOTT, WITHHOLDS)
        self.assertEqual("PINNED_PERIOD_END_EQUALITY", component["selection"]["annual"])
        self.assertEqual("GREATEST_ANNUAL_REPORT_END_BEFORE_THE_PINNED_ONE",
                         component["selection"]["prior"])
        self.assertEqual(WITHHOLDS, component["target_period"]["period_end"])

    def test_the_route_is_reachable_through_the_run_input(self):
        """Wired, not merely written: the dispatcher has to find it."""
        self.assertIn("C04", SUPPORTED_METRICS)
        self.assertIn("C04", WIRED_HISTORICAL_METRICS)
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=DELIVERS)
            prepared = prepare_historical_run_input(
                repo_root=ROOT, company_id=MARRIOTT, metric_id="C04",
                period_selection=selection)
        self.assertEqual("C04", prepared["primary_metric_id"])
        self.assertEqual("PUBLISHED", prepared["primary_result"]["publication"])
        # The Run's coordinate is the pinned fiscal year, not the measurement.
        self.assertEqual(DELIVERS, prepared["target_period"]["period_end"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, prepared["calls"])

    def test_an_unwired_governance_metric_is_refused_by_name(self):
        """C03 used to be the example here; now C02 is, and for a real reason.

        C02 reads the proxy as text and its source strategy is ``ai_text``, so
        it needs a model call this route does not make. Answering for it would
        be inventing a route, and the refusal names the metric so the frame
        reports a gap rather than a silence.
        """
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=DELIVERS)
            with self.assertRaises(HistoricalGovernanceError) as refused:
                resolve_historical_governance_metric(
                    repo_root=ROOT, company_id=MARRIOTT, metric_id="C02",
                    period_selection=selection)
        self.assertTrue(str(refused.exception).startswith(
            "HISTORICAL_GOVERNANCE_METRIC_NOT_WIRED:"))


if __name__ == "__main__":
    unittest.main()


PARAMOUNT = "paramount_skydance_paramount_global"
PARAMOUNT_PERIOD = "2025-12-31"


def _resolve_c03(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return resolve_historical_governance_metric(
            repo_root=ROOT, company_id=company_id, metric_id="C03",
            period_selection=selection)


def _ordinary_c03(company_id):
    from vnext.normal_candidates import _governance_resolution
    from vnext.normal_governance_input import prepare_saved_governance_input
    with original_sources_only():
        prepared = prepare_saved_governance_input(repo_root=ROOT, company_id=company_id)
        path, resolution = _governance_resolution(data_root=ROOT, preparation=prepared,
                                                  metric_id="C03")
        period = prepared["input_binding"]["prepared_annual_input"]["table_input"]
        return path, resolution, period["target_period"]


class HistoricalCompensationResultsTest(unittest.TestCase):
    """C03 for a pinned period: two stages, and a proxy chosen by that period.

    The ordinary route tries the annual-meeting proxy's pay-versus-performance
    facts first and the annual report's own compensation table second. Nine of
    this repository's ten companies are answered by the first stage and one by
    the second, so a route carrying either alone gives the other's companies an
    answer that is confident and wrong - which is why both are here.

    The proxy is pinned rather than latest. For the current period those are
    the same filing, and that equality is asserted against the ordinary route
    rather than assumed; for an earlier period they are not, and taking the
    latest would read a later proxy's restatement as that year's first report.
    """

    def test_the_current_period_matches_the_ordinary_route_stage_for_stage(self):
        for company_id in (MARRIOTT, PARAMOUNT):
            with self.subTest(company_id):
                path, ordinary, period = _ordinary_c03(company_id)
                historical = _resolve_c03(company_id, period["period_end"])
                for field in ("quality", "reason_code", "value"):
                    self.assertEqual(ordinary["result"][field],
                                     historical["result"][field], field)
                self.assertEqual(path, historical["spec_path"],
                                 "the same stage has to answer, not just the same value")

    def test_the_two_companies_are_answered_by_different_stages(self):
        # Load-bearing for "both stages or neither": if this ever stops being
        # true the cascade has collapsed into one stage and the case above
        # would no longer notice a route that carried only that one.
        paths = {company_id: _resolve_c03(company_id, PARAMOUNT_PERIOD
                                          if company_id == PARAMOUNT else DELIVERS)["spec_path"]
                 for company_id in (MARRIOTT, PARAMOUNT)}
        self.assertEqual(2, len(set(paths.values())), paths)

    def test_an_earlier_period_names_the_proxy_it_could_not_read(self):
        # The pinned rule, stated where it bites. This repository holds one
        # proxy per company and it is the current one, so an earlier period's
        # first proxy is listed and not saved. A latest-proxy rule would read
        # the saved one and produce a value here; this names the file instead.
        component = _resolve_c03(MARRIOTT, "2024-12-31")
        self.assertIsNone(component["result"]["value"])
        self.assertEqual("C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND",
                         component["result"]["reason_code"])
        named = [entry.get("reason", "") for entry in component["limitation"]["details"]]
        missing = [reason for reason in named if reason.startswith("SAVED_SOURCE_MISSING:")]
        self.assertTrue(missing, named)
        self.assertIn("def14a", missing[0].lower())

    def test_the_pinned_proxy_is_not_the_one_the_current_period_uses(self):
        current = _resolve_c03(MARRIOTT, DELIVERS)
        earlier = _resolve_c03(MARRIOTT, "2024-12-31")
        self.assertEqual("PASS", current["result"]["reason_code"])
        self.assertIsNotNone(current["result"]["value"])
        self.assertIsNone(earlier["result"]["value"],
                          "the current period's proxy must not answer an earlier one")

    def test_c03_is_registered_as_wired(self):
        self.assertIn("C03", SUPPORTED_METRICS)
        self.assertIn("C03", WIRED_HISTORICAL_METRICS)


class ComponentCarriesWhatItBindsTest(unittest.TestCase):
    """An observation's derived asset has to be a record of the same Run.

    A batch found this: C03's compensation-table stage rebuilds the annual
    report's grid and binds the observation to it, and the component did not
    carry the grid. Every case in this file asserted on the component's result,
    which was right, so none of them could see it - the Run factory refuses it
    later, with "Observation DerivedAsset is absent", in a tree these cases
    cannot create a Run in.

    So the claim is made where it can be checked here: through
    `prepare_historical_run_input`, on the records the Run would be built from.
    The two companies are the point - one resolves through the stage that builds
    a grid and one through the stage that does not, so a route that carried no
    assets and a route that invented one both fail.
    """

    def test_the_stage_that_builds_a_grid_carries_it(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=PARAMOUNT,
                                                 report_end=PARAMOUNT_PERIOD)
            prepared = prepare_historical_run_input(
                repo_root=ROOT, company_id=PARAMOUNT, metric_id="C03",
                period_selection=selection)
        observations = [r for r in prepared["records"]
                        if r.get("record_type") == "VERIFIED_OBSERVATION"]
        self.assertEqual(1, len(observations))
        named = observations[0]["source_binding"].get("derived_asset_id")
        self.assertIsNotNone(named, "this company is only useful if its stage binds one")
        carried = {r["derived_asset_id"] for r in prepared["records"]
                   if r.get("record_type") == "DERIVED_ASSET"}
        self.assertIn(named, carried)

    def test_the_stage_that_builds_none_carries_none(self):
        """The other half: carrying an asset nothing names is its own defect."""
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=DELIVERS)
            prepared = prepare_historical_run_input(
                repo_root=ROOT, company_id=MARRIOTT, metric_id="C03",
                period_selection=selection)
        observations = [r for r in prepared["records"]
                        if r.get("record_type") == "VERIFIED_OBSERVATION"]
        self.assertEqual(1, len(observations))
        self.assertIsNone(observations[0]["source_binding"].get("derived_asset_id"))
        self.assertEqual([], [r for r in prepared["records"]
                              if r.get("record_type") == "DERIVED_ASSET"])

    def test_the_check_sits_where_every_component_route_passes(self):
        """Four routes, one check - not four copies that drift apart."""
        from vnext.historical_results import _check_bound_assets
        _check_bound_assets(records=[
            {"record_type": "DERIVED_ASSET", "derived_asset_id": "sha256:a"},
            {"record_type": "VERIFIED_OBSERVATION",
             "source_binding": {"derived_asset_id": "sha256:a"}}])
        with self.assertRaises(Exception) as refused:
            _check_bound_assets(records=[
                {"record_type": "VERIFIED_OBSERVATION",
                 "source_binding": {"derived_asset_id": "sha256:a"}}])
        self.assertIn("HISTORICAL_COMPONENT_DERIVED_ASSET_NOT_CARRIED",
                      str(refused.exception))
