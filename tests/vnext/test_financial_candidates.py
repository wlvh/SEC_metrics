"""Automatic raw-source candidate discovery; no reference answers in runtime."""

import builtins
from contextlib import contextmanager
import hashlib
import io
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from vnext.financial_candidates import FinancialCandidateError, inspect_financial_candidates
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


if __name__ == "__main__":
    unittest.main()
