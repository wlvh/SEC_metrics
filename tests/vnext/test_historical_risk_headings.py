"""D01 for a pinned annual period, against the chain it is a pinned version of.

D01 is the cheapest shape in this frame: one filing, one text role, no prior
accession and no second source, so what the pinned route had to change is which
filing the role means. Everything else - the selector, the compiler, the
renderer, the review unit - is the frozen current route's and is imported.

The current period's expectations are the ordinary chain's own candidate,
compared as a whole record rather than as a heading count. A pinned route that
quietly widened or narrowed its source set would produce a candidate just as
readily as a correct one, and a count would not tell them apart.

Two things asserted here cannot be produced by the saved corpus, and both say
so where they are: the reuse of D02's frozen source plan, and the argument
shape the frozen v1 result API accepts. Both are inherited checks rather than
new rules, so they are kept and exercised by constructing the divergence they
guard - as the lodging route's scope check was - instead of dropped for having
no example.
"""
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_text_input as pinned_input
from vnext.historical_results import TEXT_METRICS, TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.historical_text_results import text_api
from vnext.normal_period_selection import resolve_period_selection
from vnext.ordinary_remaining_cases import prepare_current_source_case
from vnext.specs import compile_spec_file

MARRIOTT = "marriott_international"
ENPHASE = "enphase_energy"
FORD = "ford_motor_company"
MACYS = "macys"
PARAMOUNT = "paramount_skydance_paramount_global"
SOUTHWEST = "southwest_airlines"


def _spec(metric_id="D01"):
    return compile_historical_spec_file(repo_root=ROOT,
                                        repo_relative_path=TEXT_SPEC_PATHS[metric_id],
                                        dependency_specs={})


def _candidate(arguments, spec):
    """The selected headings for this input, through D01's own API.

    ``text_api`` is asked rather than a module imported directly, because which
    implementation answers D01 is part of what this file checks.
    """
    api, _ = text_api("D01")
    return api.create_deterministic_text_candidate(
        **{"compiled_spec": spec,
           **{key: value for key, value in arguments.items() if key != "compiled_spec"}})


def _pinned(company_id, report_end, metric_id="D01"):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return prepare_historical_business_text_input(
            repo_root=ROOT, company_id=company_id, metric_id=metric_id,
            period_selection=selection)


def _current(company_id, metric_id="D01"):
    with original_sources_only():
        return prepare_current_source_case(data_root=ROOT, company_id=company_id,
                                           metric_id=metric_id)


class PinnedRiskHeadingsTest(unittest.TestCase):
    """The pinned route against the ordinary chain, on the current period."""

    def test_the_current_period_gets_the_ordinary_chain_s_own_candidate(self):
        """Two companies at opposite ends of the observed heading range.

        Enphase carries 60 headings and Ford 30, so a route that truncated,
        re-scoped or re-ordered the selection would move one of them. The
        candidate record carries each heading's exact text and raw byte span,
        so equality is not a count agreeing by coincidence.
        """
        spec = _spec()
        for company_id in (ENPHASE, FORD):
            with self.subTest(company_id):
                ordinary = _current(company_id)
                pinned = _pinned(company_id, "2025-12-31")
                self.assertEqual("PREPARED", pinned["input_status"])
                self.assertEqual(ordinary["target"], pinned["text_arguments"]["target"])
                self.assertEqual(ordinary["target_period"], pinned["target_period"])
                self.assertEqual(_candidate(ordinary["text_arguments"], spec),
                                 _candidate(pinned["text_arguments"], spec))

    def test_the_pinned_route_compiles_the_same_spec_the_ordinary_one_does(self):
        """D01 declares the frozen bound, so the two compilers must agree.

        The comparison above passes one compiled Spec to both sides, which
        proves the inputs agree and says nothing about the Spec. D02's two
        compilations differ - its successor declares 192 items where the frozen
        compiler caps a declaration at 64 - so this is the assertion that D01
        was not quietly given that revision along with the route.
        """
        self.assertEqual(compile_spec_file(path=ROOT / TEXT_SPEC_PATHS["D01"],
                                           dependency_specs={}), _spec())

    def test_an_earlier_year_reads_that_year_s_filing(self):
        """The point of pinning: the year asked for, not the year filed last.

        Marriott has three annual primaries saved, so it is the one company
        where the two answers can differ. The assertion is on the accession -
        a route taking the latest filing would return the 2025 one for all
        three - and on the candidates differing, because three pinned periods
        returning one candidate would mean the pin reached the selection but
        not the bytes.
        """
        spec, seen = _spec(), {}
        for report_end in ("2025-12-31", "2024-12-31", "2023-12-31"):
            with self.subTest(report_end):
                prepared = _pinned(MARRIOTT, report_end)
                self.assertEqual("PREPARED", prepared["input_status"])
                target = prepared["text_arguments"]["target"]
                self.assertEqual(report_end, target["period_end"])
                self.assertEqual(report_end, prepared["target_period"]["period_end"])
                candidate = _candidate(prepared["text_arguments"], spec)
                seen[report_end] = (target["accession"], candidate["candidate_hash"])
        self.assertEqual(3, len({accession for accession, _ in seen.values()}))
        self.assertEqual(3, len({candidate for _, candidate in seen.values()}))

    def test_a_same_period_amendment_is_context_for_d01_as_it_is_for_d02(self):
        """Paramount is the one company where all three text rules can differ.

        Its pinned period carries a 10-K/A, and that same amendment is context
        for D01 and D02 - the target is the original 10-K - while for C02 it is
        the source, because that is where this company's governance
        information is. So the assertion is that D01 agrees with D02 and that
        C02 does not, which a rule keyed on D02 alone fails on the first half
        and a rule keyed on "has amendments" fails on the second.

        Southwest is the second company with an amendment in the period and is
        included because it resolves C02 through the proxy instead: the C02
        answer there has to be the same for the opposite reason.
        """
        for company_id in (PARAMOUNT, SOUTHWEST):
            with self.subTest(company_id):
                statuses = {metric: _pinned(company_id, "2025-12-31",
                                            metric_id=metric)["input_status"]
                            for metric in ("C02", "D01", "D02")}
                self.assertEqual("PREPARED_ORIGINAL_WITH_AMENDMENTS", statuses["D02"])
                self.assertEqual(statuses["D02"], statuses["D01"])
                self.assertEqual("PREPARED", statuses["C02"])

    def test_d01_is_answered_by_the_frozen_v1_api(self):
        """Which implementation answers D01, asserted rather than assumed.

        ``historical_text_results`` corrects D02's section boundary and carries
        its raised item capacity; D01 declares the frozen bound and needs
        neither. Routing it to the successor would change its renderer's
        capacity without anything in D01's own Spec saying so.
        """
        successor, _ = text_api("D02")
        frozen, _ = text_api("D01")
        self.assertEqual("vnext.historical_text_results", successor.__name__)
        self.assertEqual("vnext.text_results", frozen.__name__)
        self.assertEqual(("C02", "D01", "D02"), TEXT_METRICS)


class TheD01InputShapeIsNotInheritedByAccidentTest(unittest.TestCase):
    """The two reuses the saved corpus cannot exercise on its own."""

    def test_the_v1_api_is_not_handed_an_argument_it_rejects(self):
        """``source_filings`` is v2's; the v1 API refuses a shape it lacks.

        The corpus cannot show this, because D01's preparation simply does not
        add the key. So the positive is that the prepared arguments are exactly
        what the frozen entry point accepts, and the negative hands it the v2
        shape and requires a refusal - which is what adding the key for every
        text metric alike would produce.
        """
        prepared = _pinned(FORD, "2025-12-31")
        self.assertEqual({"target", "source_references", "raw_blobs", "raw_bytes_by_id"},
                         set(prepared["text_arguments"]))
        self.assertIn("source_filings",
                      set(_pinned(FORD, "2025-12-31", metric_id="D02")["text_arguments"]))
        api, _ = text_api("D01")
        with self.assertRaises(TypeError):
            api.create_deterministic_text_candidate(compiled_spec=_spec(), source_filings={},
                                                    **prepared["text_arguments"])

    def test_a_second_filing_in_the_reused_plan_stops_d01(self):
        """D02's plan is reused; the guard is what keeps the reuse honest.

        ``_source_plan``'s D02 branch is byte-frozen by the parent rule set, so
        no saved filing can make it return two text filings - the divergence is
        constructed here, and said to be constructed. Without the guard, a
        future generation that gave D02 a second source would silently give
        D01 one as well, and D01's Spec allows a single role.
        """
        real = pinned_input._source_plan

        def two_filings(**kwargs):
            plan = real(**kwargs)
            return {**plan, "text_filings": [*plan["text_filings"], plan["text_filings"][0]]}

        with patch.object(pinned_input, "_source_plan", side_effect=two_filings):
            prepared = _pinned(FORD, "2025-12-31")
        self.assertEqual("BLOCKED", prepared["input_status"])
        self.assertEqual(["HISTORICAL_TEXT_D01_PLAN_SHAPE_CHANGED"],
                         [limitation["reason"]
                          for limitation in prepared["input_binding"]["limitations"]])

    def test_widening_the_forms_is_keyed_off_the_metric(self):
        """Macy's has proxies in the same block; D01 must not be given them.

        C02 needed the governance forms admitted into the pinned metadata
        view. A version that widened them for every text metric would fill
        D01's governance selection here and change which inventories its scope
        record names, without changing any heading - so the assertion is on the
        scope record rather than on the candidate.
        """
        scope = _pinned(MACYS, "2026-01-31")["input_binding"]["current_metadata_scope"]
        self.assertIsNone(scope["selection"]["latest_def14a"])
        self.assertEqual([], scope["selection"]["def14a_amendments"])
        self.assertEqual([], scope["governance_inventories"])


if __name__ == "__main__":
    unittest.main()
