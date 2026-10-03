"""C02 for a pinned annual period: two levels, and the proxy the year means.

Both expectations here come from somewhere other than the route under test.
The current period's are the ordinary chain's own answers, compared field for
field - basis, filings and selected block indices - because a pinned route that
quietly widened or narrowed its source set would produce a result just as
readily as a correct one. The earlier periods' are the filings' own dates: the
proxy that reports on a year is the annual meeting held after that year ends,
and this repository has the 2026 proxies saved and no earlier ones, so a route
that took the newest would produce a value where the correct answer is a named
source gap.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_text_results as successor
from vnext.historical_results import TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.ordinary_text_input import prepare_current_business_text_input

MARRIOTT = "marriott_international"
PARAMOUNT = "paramount_skydance_paramount_global"
MACYS = "macys"


def _spec():
    return compile_historical_spec_file(repo_root=ROOT,
                                        repo_relative_path=TEXT_SPEC_PATHS["C02"],
                                        dependency_specs={})


def _blocks(prepared, spec):
    api, _ = successor.text_api("C02")
    candidate = api.create_deterministic_text_candidate(
        compiled_spec=spec, **prepared["text_arguments"])
    return sorted(item["block_index"] for item in candidate["selected"].values())


def _pinned(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return prepare_historical_business_text_input(
            repo_root=ROOT, company_id=company_id, metric_id="C02",
            period_selection=selection)


def _current(company_id):
    with original_sources_only():
        return prepare_current_business_text_input(repo_root=ROOT, company_id=company_id,
                                                   metric_id="C02")


class PinnedGovernanceTextTest(unittest.TestCase):
    """The pinned route against the chain it is a pinned version of."""

    def test_the_current_period_gets_the_ordinary_chain_s_own_answer(self):
        """Two companies, one on each level of the cascade.

        Marriott resolves through the proxy and Paramount through the Part III
        annual amendment, which is the reason both levels are wired: a route
        with only the first would hand the second company a source gap that is
        not true of it.
        """
        spec = _spec()
        for company_id, report_end, basis in (
                (MARRIOTT, "2025-12-31", "CURRENT_SAME_CIK_DEF14A"),
                (PARAMOUNT, "2025-12-31", "SAME_PERIOD_PART_III_ANNUAL_AMENDMENT")):
            with self.subTest(company_id):
                ordinary = _current(company_id)
                pinned = _pinned(company_id, report_end)
                self.assertEqual("PREPARED", ordinary["input_status"])
                self.assertEqual(ordinary["input_status"], pinned["input_status"])
                self.assertEqual(basis, ordinary["input_binding"]["source_plan"]["basis"])
                self.assertEqual(basis, pinned["input_binding"]["source_plan"]["basis"])
                self.assertEqual(
                    sorted(f["accessionNumber"] for f
                           in ordinary["text_arguments"]["source_filings"].values()),
                    sorted(f["accessionNumber"] for f
                           in pinned["text_arguments"]["source_filings"].values()))
                self.assertEqual(_blocks(ordinary, spec), _blocks(pinned, spec))

    def test_the_part_iii_level_carries_its_raw_proof(self):
        """The level that reads an amendment has to prove it carries Part III.

        Asserted separately from the block comparison because the proof is not
        an input to the selection: a route that skipped it would select the
        same blocks and the comparison above would still pass.
        """
        pinned = _pinned(PARAMOUNT, "2025-12-31")
        self.assertTrue(pinned["input_binding"]["source_plan"]["requires_part_iii_proof"])
        proof = pinned["input_binding"]["part_iii_source_proof"]
        self.assertIsNotNone(proof)
        current = _current(PARAMOUNT)["input_binding"]["part_iii_source_proof"]
        self.assertEqual(current, proof)

    def test_an_earlier_year_names_its_own_proxy_and_stops(self):
        """The 2026 proxy is saved; the ones these years mean are not.

        The expectation is the filings' own dates, read out of the plan rather
        than out of the selector: a 2023 annual report is reported on by the
        2024 annual meeting. A route taking the newest proxy would find a saved
        document and produce a value here, which is why this asserts the
        accession as well as the refusal.
        """
        for report_end, filing_date in (("2024-12-31", "2025-03-27"),
                                        ("2023-12-31", "2024-03-27")):
            with self.subTest(report_end):
                pinned = _pinned(MARRIOTT, report_end)
                self.assertEqual("BLOCKED", pinned["input_status"])
                limitations = pinned["input_binding"]["limitations"]
                self.assertEqual(1, len(limitations))
                self.assertEqual("SOURCE_UNAVAILABLE", limitations[0]["category"])
                self.assertTrue(limitations[0]["reason"].startswith("SAVED_SOURCE_MISSING:"),
                                limitations[0]["reason"])
                proxies = [f for f in pinned["input_binding"]["source_plan"]["text_filings"]
                           if f["form"] == "DEF 14A"]
                self.assertEqual(1, len(proxies))
                self.assertEqual(filing_date, proxies[0]["filingDate"])

    def test_d02_still_gets_no_proxy_role(self):
        """Widening the forms is keyed off the metric, not done for everyone.

        Macy's is the control: it has proxies in the same block, so a version
        that widened the form set unconditionally would fill D02's proxy roles
        and change which inventories its scope record names.
        """
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MACYS,
                                                 report_end="2026-01-31")
            pinned = prepare_historical_business_text_input(
                repo_root=ROOT, company_id=MACYS, metric_id="D02",
                period_selection=selection)
        scope = pinned["input_binding"]["current_metadata_scope"]
        self.assertIsNone(scope["selection"]["latest_def14a"])
        self.assertEqual([], scope["selection"]["def14a_amendments"])
        self.assertEqual([], scope["governance_inventories"])
        self.assertEqual(1, len(pinned["text_source_reference_ids"])
                         if "text_source_reference_ids" in pinned
                         else len(pinned["input_binding"]["text_source_reference_ids"]))


if __name__ == "__main__":
    unittest.main()
