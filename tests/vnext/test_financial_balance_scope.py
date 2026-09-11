"""Real AUM/VaR scope, time and duplicate-disclosure counterexamples."""

import hashlib
import re
import unittest

from tests.vnext.test_financial_candidates import no_answers_or_network
from tests.vnext.test_financial_duration import JPM, ROOT
from vnext.composite_scope import index_source_structure
from vnext.financial_balance_scope import inspect_aum_balance, inspect_total_var


PERIOD = {"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"}


class FinancialBalanceScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = JPM.read_bytes()
        cls.structure = index_source_structure(source_bytes=cls.source)
        cls.aum = cls.evaluate(inspect_aum_balance, cls.source)
        cls.var = cls.evaluate(inspect_total_var, cls.source)

    @staticmethod
    def evaluate(function, source):
        with no_answers_or_network():
            return function(repo_root=ROOT, source_bytes=source,
                expected_source_sha256=hashlib.sha256(source).hexdigest(),
                expected_cik="19617", target_period=PERIOD)

    def table_change(self, table_id, transform):
        order = int(table_id.split("_")[1]) - 1
        span = self.structure["tables"][order]
        raw = self.source[span["start_byte"]:span["end_byte"]]
        changed = transform(raw)
        self.assertTrue(changed != raw, "TEST_ONLY mutation did not change the original table")
        return self.source[:span["start_byte"]] + changed + self.source[span["end_byte"]:]

    def test_original_aum_has_three_consistent_total_balance_disclosures(self):
        self.assertEqual("BALANCE_SCOPE_PROVEN", self.aum["status"])
        self.assertEqual("4791000000000", self.aum["value"])
        self.assertEqual(3, len(self.aum["disclosures"]))
        for item in self.aum["disclosures"]:
            self.assertEqual("total_assets_under_management", item["scope"]["asset_scope"])
            self.assertEqual("INSTANT_BALANCE", item["measurement_time"]["kind"])
            self.assertEqual("2025-12-31", item["measurement_time"]["period_start"])
            self.assertEqual("2025-12-31", item["measurement_time"]["period_end"])

    def test_same_scope_duplicate_conflict_is_not_silently_deduplicated(self):
        first = self.aum["disclosures"][0]["value"]["locator"]
        source = self.table_change(first["table_id"], lambda raw: raw.replace(
            first["text"].encode(), b"4,792", 1))
        result = self.evaluate(inspect_aum_balance, source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIsNone(result["value"])
        self.assertIn("CONFLICTING_SAME_SCOPE_AUM_BALANCES", [r["reason"] for r in result["unresolved"]])

    def test_equal_numbers_under_average_or_client_asset_names_are_not_total_aum(self):
        for replacement in (b"Average assets under management", b"Total client assets"):
            source = self.source.replace(b"Total assets under management", replacement)
            self.assertTrue(source != self.source)
            result = self.evaluate(inspect_aum_balance, source)
            self.assertEqual("UNRESOLVED", result["status"])
            self.assertEqual([], result["disclosures"])

    def test_explicit_other_instant_is_excluded_and_does_not_block_unaffected_disclosure(self):
        first = self.aum["disclosures"][0]["value"]["locator"]
        source = self.table_change(first["table_id"], lambda raw: re.sub(
            rb"December(?:&#160;| )31", b"September 30", raw))
        result = self.evaluate(inspect_aum_balance, source)
        self.assertEqual("BALANCE_SCOPE_PROVEN", result["status"])
        self.assertEqual(1, len(result["disclosures"]))
        self.assertEqual(2, sum(r["reason"] == "DIFFERENT_SOURCE_INSTANT" for r in result["excluded"]))

    def test_wrong_scale_cannot_use_equal_printed_digits_as_duplicate_proof(self):
        first = self.aum["disclosures"][0]["value"]["locator"]
        source = self.table_change(first["table_id"], lambda raw: raw.replace(b"in billions", b"in millions"))
        self.assertEqual("UNRESOLVED", self.evaluate(inspect_aum_balance, source)["status"])

    def test_original_var_separates_annual_average_from_one_day_risk_horizon(self):
        self.assertEqual("TOTAL_VAR_SCOPE_PROVEN", self.var["status"])
        total = self.var["totals"][0]
        self.assertEqual("40000000", total["value"]["canonical_value"])
        self.assertEqual("2025-01-01", total["statistical_window"]["period_start"])
        self.assertEqual("2025-12-31", total["statistical_window"]["period_end"])
        self.assertEqual("AVERAGE", total["statistical_window"]["statistic"])
        self.assertEqual(1, total["risk_horizon"]["holding_period_days"])
        self.assertEqual("95", total["risk_horizon"]["confidence_percent"])
        self.assertTrue(total["trading_components_excluded"])
        self.assertEqual("Regulatory VaR", total["risk_horizon"]["other_named_measure_definitions"][0]["measure"])

    def test_var_must_reconcile_named_components_and_diversification(self):
        total = self.var["totals"][0]
        offset = total["offset"]["locator"]["text"].encode()
        source = self.table_change(total["value"]["locator"]["table_id"], lambda raw: raw.replace(offset, b"(8)", 1))
        result = self.evaluate(inspect_total_var, source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIn("TOTAL_VAR_COMPONENT_RECONCILIATION_CONFLICT", [r["reason"] for r in result["unresolved"]])

    def test_same_total_number_in_trading_component_does_not_change_scope_selection(self):
        total = self.var["totals"][0]
        source = self.table_change(total["value"]["locator"]["table_id"], lambda raw: raw.replace(b">34<", b">40<", 1))
        result = self.evaluate(inspect_total_var, source)
        self.assertEqual("TOTAL_VAR_SCOPE_PROVEN", result["status"])
        self.assertEqual("Total VaR", result["totals"][0]["total_label"]["text"])
        self.assertTrue(result["totals"][0]["trading_components_excluded"])

    def test_maximum_or_quarterly_statistic_cannot_be_used_as_annual_average(self):
        table_id = self.var["totals"][0]["value"]["locator"]["table_id"]
        source = self.table_change(table_id, lambda raw: raw.replace(b"Avg.", b"Max"))
        self.assertEqual("UNRESOLVED", self.evaluate(inspect_total_var, source)["status"])
        source = self.table_change(table_id, lambda raw: raw.replace(
            b"As of or for the year ended", b"For the quarter; As of or for the year ended"))
        self.assertEqual("UNRESOLVED", self.evaluate(inspect_total_var, source)["status"])

    def test_different_holding_period_or_confidence_does_not_reuse_required_scope(self):
        definition = self.var["totals"][0]["risk_horizon"]["selected_definition"]["source_block"]
        raw = self.source[definition["start_byte"]:definition["end_byte"]]
        for before, after in ((b"one-day", b"ten-day"), (b"95%", b"99%")):
            changed = raw.replace(before, after)
            self.assertTrue(changed != raw)
            source = self.source[:definition["start_byte"]] + changed + self.source[definition["end_byte"]:]
            self.assertEqual("UNRESOLVED", self.evaluate(inspect_total_var, source)["status"])

    def test_unclassified_competing_scope_span_blocks_total_even_when_arithmetic_matches(self):
        introduction = self.var["totals"][0]["risk_horizon"]["table_association"]
        extra = b"<div>Risk Management VaR uses a ten-day holding period and a 99% confidence level.</div>"
        source = self.source[:introduction["start_byte"]] + extra + self.source[introduction["start_byte"]:]
        result = self.evaluate(inspect_total_var, source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual([], result["totals"])


if __name__ == "__main__":
    unittest.main()
