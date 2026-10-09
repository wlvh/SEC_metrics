"""Small JPM scope, Paramount continuity/window and fiscal-duration business cases."""
import copy
import csv
from datetime import date
import json
from pathlib import Path
import unittest

from vnext.calculator import calculate_metric
from vnext.composite_scope import index_source_structure
from vnext.financial_balance_scope import _aum_definitions, _aum_reported_scope, _client_population
from vnext.financial_relationships import _reported_segment_sections
from vnext.normal_annual_input import _subject_policy, NormalAnnualInputError
from vnext.observations import scope_key
from vnext.public_projection import event_target_period, PublicProjectionError
from vnext.specs import compile_spec_file
from vnext.table_grid import _AllTablesParser


ROOT = Path(__file__).resolve().parents[2]


def document(*parts):
    raw = ("<html><body>" + "".join(parts) + "</body></html>").encode()
    parser = _AllTablesParser()
    parser.feed(raw.decode())
    parser.close()
    return parser.tables, index_source_structure(source_bytes=raw)


class BankScopeBusinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fragments = json.loads((ROOT / "tests/fixtures/jpm_bank_scope_fragments.json").read_text())["fragments"]

    def segments(self, *parts):
        builders, structure = document(*parts, "<table><tr><td>ASSET &amp; WEALTH MANAGEMENT</td></tr></table>")
        return _reported_segment_sections(builders, structure)

    def test_original_jpm_glossary_names_manager_and_client_classes(self):
        _, structure = document(self.fragments["aum_glossary"]["html"])
        definitions = _aum_definitions(structure)
        self.assertEqual(1, len(definitions))
        manager, expression, _ = definitions[0]
        self.assertEqual("AWM", manager)
        self.assertEqual(["private banking", "institutional", "retail"],
                         _client_population(expression)["included_client_classes"])

    def test_exclusions_and_subsets_are_not_an_unqualified_complete_population(self):
        for expression, excluded, qualifier in (
            ("Private Banking clients, excluding Institutional and Retail clients", ["institutional", "retail"], []),
            ("Private Banking clients, but not Institutional and Retail clients", ["institutional", "retail"], []),
            ("selected Private Banking, Institutional and Retail clients", [], ["selected"]),
        ):
            with self.subTest(expression=expression):
                result = _client_population(expression)
                self.assertFalse(result["complete_unqualified_enumeration"])
                self.assertEqual(excluded, result["excluded_client_classes"])
                self.assertEqual(qualifier, result["subset_qualifiers"])

    def test_a_glossary_alone_cannot_prove_whole_issuer_aum(self):
        builders, structure = document(self.fragments["aum_glossary"]["html"],
                                       "<div>AWM: Asset &amp; Wealth Management</div>")
        self.assertIsNone(_aum_reported_scope(builders=builders, structure=structure, disclosures=[],
            target_period={"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"},
            issuer={"source_consolidated_aliases": ["JPMorgan Chase & Co."]}))

    def test_client_assets_label_cannot_stand_in_for_assets_under_management(self):
        fragment = self.fragments["aum_glossary"]["html"]
        self.assertIn("Assets under management", fragment)
        _, structure = document(fragment.replace("Assets under management", "Total client assets"))
        self.assertEqual([], _aum_definitions(structure))

    def test_original_segment_list_binds_the_aw_management_heading(self):
        result = self.segments(self.fragments["reportable_segments"]["html"])
        self.assertEqual(1, len(result))
        self.assertIsNotNone(result[0]["segment_definition"])
        self.assertEqual(1, len(result[0]["segment_definition"]["consistent_source_definitions"]))

    def test_conflicting_segment_lists_cannot_bind_an_equal_heading(self):
        first = self.fragments["reportable_segments"]["html"]
        self.assertIn("Commercial", first)
        second = first.replace("Commercial", "Consumer", 1)
        result = self.segments(first, second)
        self.assertEqual(1, len(result))
        self.assertIsNone(result[0]["segment_definition"])


class ParamountWindowBusinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "catalog/zero_ai_public_projection.json").read_text())
        with (ROOT / "config/company_registry.csv").open() as stream:
            cls.company = next(c for c in csv.DictReader(stream) if c["company_id"] == "paramount_skydance_paramount_global")

    def test_registered_predecessor_does_not_authorize_financial_combination(self):
        policy = _subject_policy(self.company)
        self.assertEqual("2041610", policy["selected_cik"])
        self.assertEqual(["813828"], policy["related_predecessor_ciks"])
        self.assertFalse(policy["cross_entity_combination_authorized"])
        self.assertTrue(policy["per_metric_statement_scope_required"])

    def test_role_mismatch_is_an_implementation_gap_not_a_new_subject(self):
        company = {**self.company, "roles": "primary:2041610;predecessor:813828"}
        with self.assertRaisesRegex(NormalAnnualInputError, "ENTITY_CONTINUITY_NOT_IMPLEMENTED") as caught:
            _subject_policy(company)
        self.assertEqual("IMPLEMENTATION_GAP", caught.exception.category)

    def test_event_window_preserves_predecessor_lookback_and_fiscal_container(self):
        pinned = {"fiscal_year": 2025, "period_start": "2025-08-08", "period_end": "2025-12-31"}
        before = copy.deepcopy(pinned)
        window = event_target_period(target_period=pinned, continuity_status="successor_predecessor", catalog=self.catalog)
        self.assertEqual({"fiscal_year": 2025, "period_start": "2024-01-01", "period_end": "2025-12-31"}, window)
        self.assertEqual(146, (date.fromisoformat(pinned["period_end"]) - date.fromisoformat(pinned["period_start"])).days + 1)
        self.assertEqual(before, pinned)

    def test_continuous_noncalendar_53_week_window_is_not_calendarized(self):
        pinned = {"fiscal_year": 2023, "period_start": "2023-01-29", "period_end": "2024-02-03"}
        self.assertEqual(371, (date.fromisoformat(pinned["period_end"]) - date.fromisoformat(pinned["period_start"])).days + 1)
        self.assertEqual(pinned, event_target_period(target_period=pinned, continuity_status="continuous", catalog=self.catalog))

    def test_missing_continuity_policy_cannot_guess_a_window(self):
        with self.assertRaisesRegex(PublicProjectionError, "Event continuity policy is absent"):
            event_target_period(target_period={"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"},
                                continuity_status="unknown", catalog=self.catalog)


class FiscalDurationCalculationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = compile_spec_file(path=ROOT / "catalog/metrics/B01_revenue.md", dependency_specs={})

    def calculate(self, start, end, *, entity="2041610", unit="USD", reported_entity=None):
        accession = "0002041610-26-000007"
        scope = {"consolidation": "entity"}
        target = {"company_id": "fixture", "period_start": start, "period_end": end, "accession": accession,
                  "entity": entity, "scope": scope, "scope_key": scope_key(scope=scope)}
        fact = {"accession": accession, "concept": "us-gaap:Revenues", "duration_days": (date.fromisoformat(end)-date.fromisoformat(start)).days+1,
                "entity": reported_entity or entity, "fact_id": "fact:fixture-revenue", "filed": "2026-02-25", "fiscal_period": "FY",
                "form": "10-K", "period_start": start, "period_end": end, "unit": unit, "value": "100",
                "source_binding": {"raw_asset_id": "sha256:"+"a"*64, "source_reference_id": "sha256:"+"b"*64,
                                   "accession": accession, "document_name": "companyfacts.json", "source_role": "companyfacts",
                                   "entity": reported_entity or entity}}
        return calculate_metric(compiled_spec=self.spec, target=target, company_traits=["non_financial"],
                                structured_facts=[fact], verified_observations=[])

    def test_146_day_successor_statement_is_not_zero_or_an_annual_value(self):
        result, trace, observations = self.calculate("2025-08-08", "2025-12-31")
        self.assertEqual(("APPLICABLE", "NOT_MEANINGFUL", "ANNUAL_DURATION_OUT_OF_RANGE"),
                         tuple(result[k] for k in ("applicability", "quality", "reason_code")))
        self.assertIsNone(result["value"])
        self.assertEqual(1, len(observations))

    def test_53_week_revenue_retains_the_actual_noncalendar_interval(self):
        result, _, observations = self.calculate("2023-01-29", "2024-02-03")
        self.assertEqual(("100", "USD", "EXACT"), tuple(result[k] for k in ("value", "unit", "quality")))
        self.assertEqual(("2023-01-29", "2024-02-03"), tuple(result[k] for k in ("period_start", "period_end")))
        self.assertEqual(371, observations[0]["source_binding"]["duration_days"])

    def test_predecessor_amount_cannot_fill_successor_revenue(self):
        result, _, observations = self.calculate("2025-01-01", "2025-12-31", reported_entity="813828")
        self.assertIsNone(result["value"])
        self.assertEqual("WITHHELD", result["publication"])
        self.assertEqual([], observations)

    def test_reported_currency_is_not_relabelled_as_usd(self):
        # B01's existing policy preserves the reported unit. This constructed
        # EUR fact is not a claim about a registrant's actual reporting currency.
        result, _, observations = self.calculate("2025-01-01", "2025-12-31", unit="EUR")
        self.assertEqual(("100", "EUR"), (result["value"], result["unit"]))
        self.assertEqual("EUR", observations[0]["unit"])


if __name__ == "__main__":
    unittest.main()
