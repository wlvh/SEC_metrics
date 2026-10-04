"""Source-based duration regressions; no provider or publication execution."""

import copy
import hashlib
import unittest
from pathlib import Path

from vnext.composite_scope import index_source_structure
from vnext.financial_duration import (
    FinancialDurationError,
    inspect_financial_duration,
    validate_financial_duration_receipt,
)


ROOT = Path(__file__).resolve().parents[2]
JPM = ROOT / (
    "evidence/request_attempts/4d/"
    "4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/"
    "jpm-20251231.htm"
)
CITI = ROOT / (
    "evidence/request_attempts/12/"
    "12f5818d577a8b8022e25851849e8d6d453f05ab4f89d906f185593547fb67fe/"
    "c-20251231.htm"
)


class FinancialDurationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = JPM.read_bytes()
        structure = index_source_structure(source_bytes=cls.original)
        table = structure["tables"][64]
        next_table = structure["tables"][65]
        # Unmodified original table plus its following footnotes. This is a
        # local test slice, not a newly acquired source or production source.
        cls.excerpt = cls.original[table["start_byte"]:next_table["start_byte"]]

    def inspect(self, source=None, **overrides):
        source = self.excerpt if source is None else source
        args = {
            "source_bytes": source,
            "expected_source_sha256": hashlib.sha256(source).hexdigest(),
            "table_id": "table_000001",
            "row_index": 28,
            "column_index": 6,
            "measurement_aliases": ["Liquidity coverage ratio", "LCR"],
            "required_row_terms": ["Firm", "average"],
            "reported_unit": "percent",
            "claimed_period_start": "2025-10-01",
            "claimed_period_end": "2025-12-31",
        }
        args.update(overrides)
        return inspect_financial_duration(**args)

    def test_original_quarter_is_positive_and_annual_claim_is_rejected(self):
        good = self.inspect(self.original, table_id="table_000065")
        self.assertEqual("PASSED", good["status"])
        self.assertEqual("2025-10-01", good["measurement_period"]["period_start"])
        self.assertEqual("ROW_LINKED_FOOTNOTE", good["duration_basis"])
        bad = self.inspect(claimed_period_start="2025-01-01")
        self.assertEqual("REJECTED", bad["status"])
        self.assertIn("CLAIMED_MEASUREMENT_PERIOD_DIFFERS", bad["reasons"])
        self.assertEqual(good["measurement_period"], bad["measurement_period"])

    def test_original_explicit_annual_header_completes_without_recipe(self):
        result = self.inspect(
            self.original, table_id="table_000100", row_index=10,
            column_index=3, measurement_aliases=["Net yield"],
            required_row_terms=["managed basis"],
            claimed_period_start="2025-01-01",
        )
        self.assertEqual("PASSED", result["status"])
        self.assertEqual("EXPLICIT_ANNUAL_TABLE_HEADER", result["duration_basis"])

    def test_actual_quarter_header_and_full_column_date_define_the_lcr_interval(self):
        result = self.inspect(self.original, table_id="table_000199", row_index=9,
                              column_index=3, required_row_terms=[])
        self.assertEqual("PASSED", result["status"])
        self.assertEqual("EXPLICIT_MONTHS_HEADER_AND_FULL_COLUMN_DATE", result["duration_basis"])
        self.assertEqual("2025-10-01", result["measurement_period"]["period_start"])
        structure = index_source_structure(source_bytes=self.original)
        span = structure["tables"][198]
        original = self.original[span["start_byte"]:span["end_byte"]]
        for before, after, start, end, expected in [
            (b"December 31, 2025", b"June 30, 2025", "2025-04-01", "2025-06-30", "PASSED"),
            (b"December 31, 2025", b"February 28, 2025", "2024-12-01", "2025-02-28", "PASSED"),
            (b"December 31, 2025", b"February 29, 2024", "2023-12-01", "2024-02-29", "PASSED"),
            (b"December 31, 2025", b"June 15, 2025", "2025-03-16", "2025-06-15", "UNRESOLVED"),
        ]:
            changed = original.replace(before, after)
            self.assertNotEqual(original, changed)
            with self.subTest(end=end):
                checked = self.inspect(changed, row_index=9, column_index=3, required_row_terms=[],
                                       claimed_period_start=start, claimed_period_end=end)
                self.assertEqual(expected, checked["status"])
        changed = original.replace(b"Three months ended", b"Six months ended").replace(
            b"December 31, 2025", b"June 30, 2025")
        checked = self.inspect(changed, row_index=9, column_index=3, required_row_terms=[],
                               claimed_period_start="2025-01-01", claimed_period_end="2025-06-30")
        self.assertEqual("PASSED", checked["status"])

    def test_original_date_and_average_do_not_invent_a_quarter(self):
        result = self.inspect(
            CITI.read_bytes(), table_id="table_000075", row_index=4,
            column_index=3, required_row_terms=[],
        )
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIsNone(result["measurement_period"])

    def test_changed_duration_is_recomputed_with_new_source_hash(self):
        changed = self.excerpt.replace(b"three months ended", b"six months ended")
        self.assertNotEqual(changed, self.excerpt)
        result = self.inspect(changed)
        self.assertEqual("REJECTED", result["status"])
        self.assertEqual("2025-07-01", result["measurement_period"]["period_start"])

    def test_subject_and_unit_changes_do_not_keep_prior_acceptance(self):
        for before, after, reason in [
            (b"Firm Liquidity coverage", b"Bank subsidiary Liquidity coverage", "REQUIRED_ROW_TERM_NOT_PROVEN"),
            (b"the percentage represents", b"the dollar amount represents", "REPORTED_UNIT_NOT_PROVEN"),
        ]:
            changed = self.excerpt.replace(before, after)
            self.assertNotEqual(changed, self.excerpt)
            with self.subTest(reason=reason):
                result = self.inspect(changed)
                self.assertNotEqual("PASSED", result["status"])
                self.assertIn(reason, result["reasons"])

    def test_missing_or_unlinked_footnote_never_falls_back_to_filing_year(self):
        changed = self.excerpt.replace(b"(b)", b"(z)", 1)
        self.assertTrue(changed != self.excerpt)
        result = self.inspect(changed, claimed_period_start="2025-01-01")
        self.assertIn("ROW_FOOTNOTE_NOT_PROVEN", result["reasons"])
        self.assertNotEqual("PASSED", result["status"])

    def test_source_and_receipt_tampering_are_rejected_independently(self):
        receipt = self.inspect()
        self.assertEqual(receipt, validate_financial_duration_receipt(
            receipt=receipt, source_bytes=self.excerpt))
        changed = self.excerpt.replace(b"three months ended", b"six months ended")
        with self.assertRaisesRegex(FinancialDurationError, "SOURCE_BYTES_DIFFER"):
            validate_financial_duration_receipt(receipt=receipt, source_bytes=changed)
        modified = copy.deepcopy(receipt)
        modified["measurement_period"]["period_start"] = "2025-01-01"
        with self.assertRaisesRegex(FinancialDurationError, "RECEIPT_REPLAY_DIFFERS"):
            validate_financial_duration_receipt(receipt=modified, source_bytes=self.excerpt)

    def test_prior_year_header_requires_the_prior_year_measurement_interval(self):
        result = self.inspect(column_index=12)
        self.assertEqual("REJECTED", result["status"])
        self.assertEqual("2024-10-01", result["measurement_period"]["period_start"])
        self.assertEqual("PASSED", self.inspect(
            column_index=12, claimed_period_start="2024-10-01",
            claimed_period_end="2024-12-31")["status"])

    def synthetic(self, notes, *, label="Firm average ratio(a)", header="2025"):
        # TEST_ONLY input exercises relationships independently of any issuer.
        return ("<html><body><table><tr><td>Year ended December 31</td>"
                f"<td>{header}</td></tr><tr><td>{label}</td><td>7</td>"
                "<td>%</td></tr></table>" + notes + "</body></html>").encode()

    def inspect_synthetic(self, source, **overrides):
        return self.inspect(source, row_index=1, column_index=1,
                            measurement_aliases=["ratio"], **overrides)

    def test_duplicate_and_conflicting_footnotes_do_not_choose_a_convenient_period(self):
        notes = ("<p>(a) Average for three months ended December 31, 2025.</p>"
                 "<p>(a) Average for six months ended December 31, 2025.</p>")
        result = self.inspect_synthetic(self.synthetic(notes))
        self.assertIn("ROW_FOOTNOTE_NOT_PROVEN", result["reasons"])
        notes = "<p>(a) Average for three months ended December 31, 2025 and six months ended December 31, 2025.</p>"
        result = self.inspect_synthetic(self.synthetic(notes))
        self.assertIn("CONFLICTING_MEASUREMENT_PERIODS", result["reasons"])

    def test_unrelated_table_footnote_and_unknown_duration_stay_unresolved(self):
        notes = ("<h2>Different measurement</h2><p>(a) Average for three months "
                 "ended December 31, 2025.</p>")
        self.assertIn("ROW_FOOTNOTE_NOT_PROVEN", self.inspect_synthetic(
            self.synthetic(notes))["reasons"])
        notes = "<p>(a) Average for thirteen weeks ended December 31, 2025.</p>"
        self.assertIn("FOOTNOTE_DURATION_UNSUPPORTED", self.inspect_synthetic(
            self.synthetic(notes), claimed_period_start="2025-01-01")["reasons"])
        notes = "<p>(a) Not an average for three months ended December 31, 2025.</p>"
        self.assertIn("FOOTNOTE_DURATION_UNSUPPORTED", self.inspect_synthetic(
            self.synthetic(notes))["reasons"])

    def test_noncalendar_annual_header_and_bad_claim_dates(self):
        source = self.synthetic("", label="Firm average ratio").replace(
            b"December 31", b"June 30")
        result = self.inspect_synthetic(source, claimed_period_start="2024-07-01",
                                        claimed_period_end="2025-06-30")
        self.assertEqual("PASSED", result["status"])
        with self.assertRaisesRegex(FinancialDurationError, "CLAIMED_PERIOD_INVALID"):
            self.inspect_synthetic(source, claimed_period_start="2025-13-01")

    def test_source_month_end_intervals_cover_quarter_half_year_and_leap_boundaries(self):
        for months, end_text, year, start, end in [
            (3, "June 30", 2025, "2025-04-01", "2025-06-30"),
            (6, "June 30", 2025, "2025-01-01", "2025-06-30"),
            (3, "February 28", 2025, "2024-12-01", "2025-02-28"),
            (3, "February 29", 2024, "2023-12-01", "2024-02-29"),
            (12, "February 29", 2024, "2023-03-01", "2024-02-29"),
            (12, "February 28", 2025, "2024-03-01", "2025-02-28"),
        ]:
            notes = f"<p>(a) Average for {months} months ended {end_text}, {year}.</p>"
            source = self.synthetic(notes, header=str(year))
            with self.subTest(months=months, end=end):
                result = self.inspect_synthetic(source, claimed_period_start=start,
                                                claimed_period_end=end)
                self.assertEqual("PASSED", result["status"])
                self.assertEqual(start, result["measurement_period"]["period_start"])

    def test_non_month_end_sources_need_explicit_dates_not_calendar_inference(self):
        notes = "<p>(a) Average for three months ended June 15, 2025.</p>"
        result = self.inspect_synthetic(self.synthetic(notes),
                                        claimed_period_start="2025-03-16",
                                        claimed_period_end="2025-06-15")
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIsNone(result["measurement_period"])
        source = self.synthetic("", label="Firm average ratio").replace(
            b"December 31", b"June 15")
        result = self.inspect_synthetic(source, claimed_period_start="2024-06-16",
                                        claimed_period_end="2025-06-15")
        self.assertEqual("UNRESOLVED", result["status"])

    def test_point_in_time_row_or_linked_note_does_not_inherit_annual_duration(self):
        source = self.synthetic("", label="Firm average ratio at period-end")
        result = self.inspect_synthetic(source, claimed_period_start="2025-01-01")
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIn("MEASUREMENT_ROW_IS_POINT_IN_TIME", result["reasons"])
        notes = "<p>(a) The ratio is as of December 31, 2025.</p>"
        result = self.inspect_synthetic(self.synthetic(notes),
                                        claimed_period_start="2025-01-01")
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIn("FOOTNOTE_DURATION_UNSUPPORTED", result["reasons"])
        self.assertIsNone(result["measurement_period"])

    def test_quarter_header_cannot_be_overridden_by_a_second_annual_header(self):
        source = self.synthetic("", label="Firm average ratio").replace(
            b"Year ended December 31", b"Three months ended December 31; Year ended December 31")
        result = self.inspect_synthetic(source, claimed_period_start="2025-01-01")
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIsNone(result["measurement_period"])

    def test_merged_interior_coordinate_and_nonnumeric_cell_are_not_selection_proof(self):
        with self.assertRaisesRegex(FinancialDurationError, "SELECTED_CELL_NOT_ORIGIN"):
            self.inspect(column_index=7)
        with self.assertRaisesRegex(FinancialDurationError, "SELECTED_CELL_NOT_NUMERIC"):
            self.inspect(column_index=0)


if __name__ == "__main__":
    unittest.main()
