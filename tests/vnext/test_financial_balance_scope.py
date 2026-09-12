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
        cls._source_facts = {}

    @property
    def aum(self):
        if "aum" not in type(self)._source_facts:
            type(self)._source_facts["aum"] = self.evaluate(inspect_aum_balance, self.source)
        return type(self)._source_facts["aum"]

    @property
    def var(self):
        if "var" not in type(self)._source_facts:
            type(self)._source_facts["var"] = self.evaluate(inspect_total_var, self.source)
        return type(self)._source_facts["var"]

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
        self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", self.aum["semantic_status"])
        complete = self.aum["whole_issuer_scope_evidence"]
        self.assertEqual(2, len(complete["complete_table_group_reconciliations"]))
        self.assertEqual(3, len(complete["manager_section_bindings"]))
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
        self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", self.var["semantic_status"])
        total = self.var["totals"][0]
        self.assertEqual("40000000", total["value"]["canonical_value"])
        self.assertEqual("2025-01-01", total["statistical_window"]["period_start"])
        self.assertEqual("2025-12-31", total["statistical_window"]["period_end"])
        self.assertEqual("AVERAGE", total["statistical_window"]["statistic"])
        self.assertEqual(1, total["risk_horizon"]["holding_period_days"])
        self.assertEqual("95", total["risk_horizon"]["confidence_percent"])
        self.assertTrue(total["trading_components_excluded"])
        self.assertEqual("Regulatory VaR", total["risk_horizon"]["other_named_measure_definitions"][0]["measure"])

    def test_equal_aum_totals_need_original_complete_scope_and_component_agreement(self):
        scope = self.aum["whole_issuer_scope_evidence"]
        definition = scope["aum_definitions"][0]
        before = self.source[definition["start_byte"]:definition["end_byte"]]
        changed = before.replace(b"Includes", b"Excludes")
        self.assertTrue(changed != before)
        source = self.source[:definition["start_byte"]] + changed + self.source[definition["end_byte"]:]
        result = self.evaluate(inspect_aum_balance, source)
        self.assertEqual("BALANCE_SCOPE_PROVEN", result["status"])
        self.assertEqual("UNRESOLVED", result["semantic_status"])
        group = scope["complete_table_group_reconciliations"][0]
        component = group["components"][0]["value"]["locator"]
        source = self.table_change(component["table_id"], lambda raw: raw.replace(component["text"].encode(), b"1", 1))
        result = self.evaluate(inspect_aum_balance, source)
        self.assertEqual("BALANCE_SCOPE_PROVEN", result["status"])
        self.assertEqual("UNRESOLVED", result["semantic_status"])

    _client_phrases = (b"Private Banking clients, excluding Institutional and Retail clients",
                       b"Private Banking clients, but not Institutional and Retail clients",
                       b"selected Private Banking, Institutional and Retail clients",
                       b"Private Banking clients", b"Institutional and Retail clients")

    def _assert_client_phrase(self, index):
        definition = self.aum["whole_issuer_scope_evidence"]["aum_definitions"][0]
        before = self.source[definition["start_byte"]:definition["end_byte"]]
        if index is not None:
            phrase = self._client_phrases[index]
            changed = before.replace(b"Private Banking, Institutional and Retail clients", phrase)
            self.assertTrue(changed != before)
            source = self.source[:definition["start_byte"]] + changed + self.source[definition["end_byte"]:]
            result = self.evaluate(inspect_aum_balance, source)
            self.assertEqual("UNRESOLVED", result["semantic_status"])
            self.assertIsNone(result["whole_issuer_scope_evidence"])
        else:
            unrelated = b"<div>A separate research example includes only selected clients, excluding institutional clients.</div>"
            source = self.source[:definition["end_byte"]] + unrelated + self.source[definition["end_byte"]:]
            self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", self.evaluate(inspect_aum_balance, source)["semantic_status"])

    def test_aum_client_enumeration_cannot_hide_exclusions_or_selected_subsets(self):
        for index in [*range(len(self._client_phrases)), None]:
            self._assert_client_phrase(index)

    def test_var_reported_estimate_is_distinct_from_an_illustrative_table(self):
        intro = self.var["totals"][0]["risk_horizon"]["table_association"]
        before = self.source[intro["start_byte"]:intro["end_byte"]]
        for replacement in (b"shows hypothetical estimates for illustration, not the reported values of",
                            b"presents illustrative figures for"):
            changed = before.replace(b"shows the results of", replacement)
            self.assertTrue(changed != before)
            source = self.source[:intro["start_byte"]] + changed + self.source[intro["end_byte"]:]
            result = self.evaluate(inspect_total_var, source)
            self.assertEqual("UNRESOLVED", result["status"])
            self.assertTrue(any(x["reason"] == "SOURCE_REPORTING_DECLARATION_CONFLICT" for x in result["unresolved"]))
        unrelated = b"<div>The preceding example contains hypothetical amounts, not reported revenue. The model uses hypothetical market shocks.</div>"
        source = self.source[:intro["start_byte"]] + unrelated + self.source[intro["start_byte"]:]
        self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", self.evaluate(inspect_total_var, source)["semantic_status"])

    def test_var_total_arithmetic_does_not_prove_all_portfolios_at_firm_level(self):
        aggregation = self.var["totals"][0]["risk_horizon"]["firmwide_aggregation_evidence"]
        before = self.source[aggregation["start_byte"]:aggregation["end_byte"]]
        changed = before.replace(b"across all portfolios", b"across selected portfolios")
        self.assertTrue(changed != before)
        source = self.source[:aggregation["start_byte"]] + changed + self.source[aggregation["end_byte"]:]
        result = self.evaluate(inspect_total_var, source)
        self.assertEqual("TOTAL_VAR_SCOPE_PROVEN", result["status"])
        self.assertEqual("UNRESOLVED", result["semantic_status"])

    def test_extra_same_named_total_with_unknown_period_cannot_be_silently_skipped(self):
        for function, label in ((inspect_aum_balance, "Total assets under management"), (inspect_total_var, "Total VaR")):
            extra = f"<table><tr><td>Unknown measurement period</td><td>Current</td></tr><tr><td>{label}</td><td>40</td></tr></table>".encode()
            with self.subTest(label=label):
                result = self.evaluate(function, self.source.replace(b"</body>", extra + b"</body>"))
                self.assertEqual("UNRESOLVED", result["status"])
                self.assertEqual("UNRESOLVED", result["semantic_status"])

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


class AumClientFastTest(unittest.TestCase):
    """Retain every client-scope variant without an unrelated VaR setup."""
    @classmethod
    def setUpClass(cls):
        cls.source = JPM.read_bytes()
        cls.aum = cls.evaluate(inspect_aum_balance, cls.source)

    evaluate = staticmethod(FinancialBalanceScopeTest.evaluate)
    _assert_client_phrase = FinancialBalanceScopeTest._assert_client_phrase
    _client_phrases = FinancialBalanceScopeTest._client_phrases

    def test_excluding_clients(self):
        self._assert_client_phrase(0)

    def test_but_not_clients(self):
        self._assert_client_phrase(1)

    def test_selected_clients(self):
        self._assert_client_phrase(2)

    def test_only_private_clients(self):
        self._assert_client_phrase(3)

    def test_only_institutional_and_retail_clients(self):
        self._assert_client_phrase(4)

    def test_unrelated_exclusion_does_not_change_aum_scope(self):
        self._assert_client_phrase(None)


if __name__ == "__main__":
    unittest.main()
