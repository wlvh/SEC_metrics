"""Automatic raw-source candidate discovery; no reference answers in runtime."""

import builtins
from contextlib import contextmanager
import hashlib
import io
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from vnext.financial_candidates import FinancialCandidateError, inspect_financial_candidates, inspect_lcr_disclosed_fact
from tests.vnext.test_financial_duration import JPM, ROOT


TASKS = {"A03": "r4_liquidity_coverage_ratio_table_v2",
         "A04": "r4_net_interest_margin_table_v2",
         "A13": "r4_international_net_revenue_table_v2"}
ANNUAL = {"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"}


@contextmanager
def no_answers_or_network():
    real_open, real_io = builtins.open, io.open

    def checked(opener):
        def opening(path, *args, **kwargs):
            if isinstance(path, (str, Path)):
                text = str(path)
                if any(part in text for part in (
                        "/fixtures/", "/r4_offline/", "/r4_v3/",
                        "metrics_matrix.csv", "metric_evidence.csv")):
                    raise AssertionError("Answer/fixture read: " + text)
            return opener(path, *args, **kwargs)
        return opening

    with patch("builtins.open", checked(real_open)), patch("io.open", checked(real_io)), patch.object(
            socket.socket, "connect", side_effect=AssertionError("network")):
        yield


class FinancialCandidateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = JPM.read_bytes()
        with no_answers_or_network():
            cls.actual = {metric: inspect_financial_candidates(
                repo_root=ROOT, source_bytes=source,
                expected_source_sha256=hashlib.sha256(source).hexdigest(),
                task_contract_id=TASKS[metric], target_period=ANNUAL,
            ) for metric in ("A03", "A04")}

    def source(self, *, value="17", year="2025", label=None, leading="", extra_row=""):
        # TEST_ONLY examples vary the issuer-neutral numbers, year and layout.
        label = label or "Firm Liquidity coverage ratio (average)(a)"
        return (f"<html><body>{leading}<table><tr><td>Year ended December 31</td>"
                f"<td>{year}</td></tr><tr><td>{label}</td><td>{value}</td><td>%</td></tr>"
                f"{extra_row}</table><p>(a) Average for three months ended December 31, "
                f"{year}.</p></body></html>").encode()

    def inspect(self, source, *, metric="A03", period=None):
        with no_answers_or_network():
            return inspect_financial_candidates(
                repo_root=ROOT, source_bytes=source,
                expected_source_sha256=hashlib.sha256(source).hexdigest(),
                task_contract_id=TASKS[metric], target_period=period or ANNUAL,
            )

    def test_actual_source_auto_locates_firm_and_subsidiary_and_retains_other_tables(self):
        result = self.actual["A03"]
        self.assertEqual(679, result["source_table_count"])
        firm = next(c for c in result["candidates"] if c["measurement_row"]["text"].startswith(
            "Firm Liquidity") and c["locator"]["text"] == "111")
        self.assertEqual("table_000065", firm["locator"]["table_id"])
        self.assertEqual("2025-10-01", firm["duration_component"]["measurement_period"]["period_start"])
        self.assertIn("DISCLOSED_PERIOD_DIFFERS_FROM_REQUEST", firm["unresolved_obligations"])
        subsidiary = next(c for c in result["candidates"] if "Bank, N.A." in c["measurement_row"]["text"])
        self.assertIn("REQUIRED_SCOPE_NOT_PROVEN_IN_ROW", subsidiary["unresolved_obligations"])
        self.assertTrue(any(c["locator"]["table_id"] == "table_000199" for c in result["candidates"]))
        self.assertTrue(all(not c["auto_execution_eligible"] for c in result["candidates"]))

    def test_actual_nim_lead_requires_economic_bridge_despite_duration_success(self):
        result = self.actual["A04"]
        candidate = next(c for c in result["candidates"] if c["locator"]["text"] == "2.50")
        self.assertEqual("table_000100", candidate["locator"]["table_id"])
        self.assertEqual("PASSED", candidate["duration_component"]["status"])
        self.assertEqual("percent", candidate["source_unit"])
        self.assertIn("MEASUREMENT_SEMANTICS_UNPROVEN", candidate["unresolved_obligations"])
        amounts = [c for c in result["candidates"] if c["source_unit"] == "USD"]
        self.assertTrue(amounts)
        self.assertTrue(all("SOURCE_UNIT_CONFLICT" in c["unresolved_obligations"] for c in amounts))

    def test_novel_values_year_and_shifted_table_are_discovered_from_bytes(self):
        period = {"fiscal_year": 2026, "period_start": "2026-01-01", "period_end": "2026-12-31"}
        source = self.source(value="23", year="2026", leading="<table><tr><td>Unrelated</td></tr></table>")
        result = self.inspect(source, period=period)
        self.assertEqual(2, result["source_table_count"])
        self.assertEqual(1, len(result["candidates"]))
        candidate = result["candidates"][0]
        self.assertEqual("table_000002", candidate["locator"]["table_id"])
        self.assertEqual("23", candidate["locator"]["text"])
        self.assertEqual("2026-10-01", candidate["duration_component"]["measurement_period"]["period_start"])

    def test_scope_and_unit_mutations_are_visible_after_source_rehash(self):
        source = self.source(label="Bank subsidiary Liquidity coverage ratio (average)(a)")
        result = self.inspect(source)
        self.assertEqual(1, len(result["candidates"]))
        self.assertIn("FORBIDDEN_ROW_SCOPE", result["candidates"][0]["unresolved_obligations"])
        source = self.source().replace(b"<td>%</td>", b"<td>$</td>")
        candidate = self.inspect(source)["candidates"][0]
        self.assertIn("SOURCE_UNIT_NOT_PROVEN", candidate["unresolved_obligations"])
        self.assertNotEqual("PASSED", candidate["duration_component"]["status"])

    def test_conflicting_same_period_rows_are_retained_without_answer_tie_break(self):
        second = "<tr><td>Firm Liquidity coverage ratio (average)(a)</td><td>18</td><td>%</td></tr>"
        result = self.inspect(self.source(extra_row=second))
        self.assertEqual({"17", "18"}, {c["locator"]["text"] for c in result["candidates"]})
        self.assertEqual(2, len(result["unresolved_candidate_set"]))
        self.assertEqual("NOT_PROVEN_BY_LITERAL_SEARCH", result["semantic_completeness"])

    def test_no_match_is_an_implementation_limit_not_a_disclosure_failure(self):
        result = self.inspect(b"<table><tr><td>Unimplemented presentation</td><td>17</td></tr></table>")
        self.assertEqual("NO_LITERAL_CANDIDATE_IMPLEMENTATION_LIMIT", result["status"])
        self.assertEqual([], result["candidates"])
        self.assertEqual("NOT_EXECUTED", result["execution"])

    def test_structured_first_is_not_bypassed_by_a_table_candidate(self):
        source = self.source(label="International net revenue").replace(b"<td>17</td>", b"<td>$</td><td>17</td>")
        result = self.inspect(source, metric="A13")
        self.assertTrue(result["candidates"])
        self.assertTrue(all("STRUCTURED_PRIMARY_NOT_EVALUATED" in c["unresolved_obligations"]
                            for c in result["candidates"]))

    def test_source_identity_cannot_be_reused_after_source_change(self):
        source = self.source()
        with self.assertRaisesRegex(FinancialCandidateError, "SOURCE_BYTES_DIFFER"):
            inspect_financial_candidates(
                repo_root=ROOT, source_bytes=source.replace(b">17<", b">18<"),
                expected_source_sha256=hashlib.sha256(source).hexdigest(),
                task_contract_id=TASKS["A03"], target_period=ANNUAL,
            )


class LcrDisclosedFactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vnext.composite_scope import index_source_structure
        cls.raw = JPM.read_bytes()
        cls.structure = index_source_structure(source_bytes=cls.raw)
        cls.actual = cls.evaluate(cls.raw)

    @staticmethod
    def evaluate(raw):
        with no_answers_or_network():
            return inspect_lcr_disclosed_fact(repo_root=ROOT, source_bytes=raw,
                expected_source_sha256=hashlib.sha256(raw).hexdigest(), expected_cik="19617", target_period=ANNUAL)

    def replace_table(self, source, locator, transform):
        from vnext.composite_scope import index_source_structure
        span = index_source_structure(source_bytes=source)["tables"][int(locator["table_id"].split("_")[1]) - 1]
        original = source[span["start_byte"]:span["end_byte"]]
        changed = transform(original)
        self.assertTrue(original != changed, "TEST_ONLY table mutation must change original bytes")
        return source[:span["start_byte"]] + changed + source[span["end_byte"]:]

    def test_two_real_disclosures_form_one_quarter_fact_and_keep_all_twelve_candidates(self):
        result = self.actual
        self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", result["status"])
        self.assertEqual("1.11", result["value"])
        self.assertEqual("2025-10-01", result["measurement_period"]["period_start"])
        self.assertEqual("2025-01-01", result["target_filing_period"]["period_start"])
        self.assertEqual(2, len(result["selected"]))
        self.assertEqual(12, len(result["candidate_census"]))
        self.assertEqual(2, sum(c["disposition"] == "OTHER_EXPLICIT_NAMED_ENTITY" for c in result["candidate_census"]))
        self.assertFalse(result["annual_average_claimed"])
        self.assertFalse(result["historical_citi_exception_reused"])
        self.assertEqual("EXPLICIT_DISCLOSED_PERIOD_RULE_REQUIRED", result["ordinary_result_rule_status"])

    def test_same_scope_disclosures_with_conflicting_rates_are_not_selected_by_preference(self):
        entry = self.actual["selected"][0]
        changed = self.replace_table(self.raw, entry["locator"], lambda raw: raw.replace(b">111<", b">112<"))
        result = self.evaluate(changed)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIn("CONFLICTING_SAME_SCOPE_LCR_FACTS", [c["disposition"] for c in result["unresolved"]])

    def test_equal_annual_and_quarter_average_numbers_remain_different_facts(self):
        extra = (b"<table><tr><td>Year ended December 31</td><td>2025</td></tr>"
                 b"<tr><td>Firm Liquidity coverage ratio (average)</td><td>111</td><td>%</td></tr></table>")
        result = self.evaluate(self.raw.replace(b"</body>", extra + b"</body>"))
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual(3, len(result["selected"]))
        self.assertIsNone(result["measurement_period"])

    def test_novel_consistent_numbers_do_not_depend_on_the_old_answer(self):
        changed = self.raw
        for entry in self.actual["selected"]:
            changed = self.replace_table(changed, entry["locator"], lambda raw: raw.replace(b">111<", b">137<"))
        result = self.evaluate(changed)
        self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", result["status"])
        self.assertEqual("1.37", result["value"])

    def test_unknown_same_name_scope_and_lost_aggregation_are_not_ignored(self):
        extra = (b"<table><tr><td>Year ended December 31</td><td>2025</td></tr>"
                 b"<tr><td>Other Liquidity coverage ratio (average)</td><td>111</td><td>%</td></tr></table>")
        self.assertEqual("UNRESOLVED", self.evaluate(self.raw.replace(b"</body>", extra + b"</body>"))["status"])
        entry = self.actual["selected"][0]
        changed = self.replace_table(self.raw, entry["locator"], lambda raw: raw.replace(b"(average)", b""))
        self.assertEqual("UNRESOLVED", self.evaluate(changed)["status"])

    def _assert_unknown_entity(self, heading):
        extra = (f'<table><tr><td colspan="3">{heading}</td></tr>'
                 '<tr><td>Year ended December 31</td><td>2025</td><td></td></tr>'
                 '<tr><td>Liquidity coverage ratio (average)(a)</td><td>112</td><td>%</td></tr></table>'
                 '<p>(a) Average for three months ended December 31, 2025.</p>').encode()
        result = self.evaluate(self.raw.replace(b"</body>", extra + b"</body>"))
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIsNone(result["value"])
        self.assertTrue(any(c["disposition"] == "LCR_NAMED_ISSUER_OR_MEASURE_UNPROVEN" for c in result["unresolved"]))

    def test_unnamed_consolidated_group_is_not_proof_of_another_legal_entity(self):
        for heading in ("Reported consolidated entity:", "Unidentified Holdings Inc:"):
            self._assert_unknown_entity(heading)
        others = [c for c in self.actual["candidate_census"] if c["disposition"] == "OTHER_EXPLICIT_NAMED_ENTITY"]
        self.assertTrue(all(c["distinct_entity_definition"]["relationship"] == "EXPLICIT_SUBSIDIARY_OF_REGISTRANT" for c in others))

    def test_a_firm_word_without_its_source_issuer_definition_does_not_close_scope(self):
        changed = self.raw
        # Rewrite all actual alias witnesses, preserving DEI and every number.
        for alias in reversed(self.actual["issuer_identity"]["source_defined_aliases"]):
            span = alias["definition"]
            before = self.raw[span["start_byte"]:span["end_byte"]]
            after = before.replace(b"Firm", b"Subsidiary")
            self.assertNotEqual(before, after)
            changed = changed[:span["start_byte"]] + after + changed[span["end_byte"]:]
        result = self.evaluate(changed)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual([], result["issuer_identity"]["source_defined_aliases"])


class LcrEntityFastTest(unittest.TestCase):
    """One source evaluation per bounded CI selector; no unrelated setup."""
    @classmethod
    def setUpClass(cls):
        cls.raw = JPM.read_bytes()

    evaluate = staticmethod(LcrDisclosedFactTest.evaluate)
    _assert_unknown_entity = LcrDisclosedFactTest._assert_unknown_entity

    def test_unidentified_consolidated_group_is_rejected(self):
        self._assert_unknown_entity("Reported consolidated entity:")

    def test_unidentified_named_holding_is_rejected(self):
        self._assert_unknown_entity("Unidentified Holdings Inc:")

    def test_explicit_subsidiaries_keep_their_original_definition(self):
        actual = self.evaluate(self.raw)
        others = [c for c in actual["candidate_census"] if c["disposition"] == "OTHER_EXPLICIT_NAMED_ENTITY"]
        self.assertEqual(2, len(others))
        self.assertTrue(all(c["distinct_entity_definition"]["relationship"]
                            == "EXPLICIT_SUBSIDIARY_OF_REGISTRANT" for c in others))


if __name__ == "__main__":
    unittest.main()
