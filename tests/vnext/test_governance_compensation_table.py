"""Native SCT source/identity/actual-period and competing-total regressions."""

import copy
import json
import unittest

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import annual, binding
from vnext.governance_compensation_table import CompensationTableError, SPEC_PATH
from vnext.governance_compensation_table import resolve_compensation_table, replay_compensation_table
from vnext.specs import compile_spec_file


HEADERS = ["Name and Principal Position", "Year", "Salary ($)", "Total ($)"]
PERSON = ["Alex Example Chairman and CEO", "2025", "40", "125,000"]
COVERED = "The following table sets forth total compensation for our executives for the period commencing on the Closing Date and ending on December 31, 2025 (the Covered Period)."


def source(*, headers=None, rows=None, description=COVERED, closing="August 7, 2025", prefix="", suffix="", currency="USD"):
    headers = HEADERS if headers is None else headers
    rows = [PERSON] if rows is None else rows
    table = "<table><tr>" + "".join("<th>" + c + "</th>" for c in headers) + "</tr>"
    table += "".join("<tr>" + "".join("<td>" + c + "</td>" for c in row) + "</tr>" for row in rows) + "</table>"
    raw = annual('<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="annual">2025</ix:nonNumeric>'
        '<xbrli:unit id="money"><xbrli:measure>iso4217:' + currency + '</xbrli:measure></xbrli:unit>'
        + (('<p>On ' + closing + ' (the “Closing Date”), the transaction closed.</p>') if closing else "")
        + prefix + '<h2>SUMMARY COMPENSATION TABLE FOR 2025</h2><p>' + description + '</p>' + table + suffix,
        form="10-K/A")
    return raw.replace(b"<html ", b'<html xmlns:iso4217="http://www.xbrl.org/2003/iso4217" ', 1)


def arguments(raw):
    args = binding(raw)
    args["report_period_end"] = args.pop("expected_period_end")
    args.update(report_period_start="2025-01-01", fiscal_year=2025,
                compiled_spec=compile_spec_file(path=REPO_ROOT / SPEC_PATH, dependency_specs={}))
    return args


class CompensationTableTest(unittest.TestCase):
    def test_actual_covered_period_native_value_locators_and_json_replay(self):
        args = arguments(source())
        result = resolve_compensation_table(**args)
        self.assertEqual("125000", result["result"]["value"])
        self.assertEqual("2025-08-07", result["result"]["period_start"])
        self.assertEqual("2025-12-31", result["result"]["period_end"])
        candidate = result["selection"]["candidates"][0]
        self.assertEqual("125,000", candidate["amount"]["raw_text"])
        self.assertEqual(8, len(candidate["amount"]["locator"]))
        self.assertEqual(result, replay_compensation_table(resolution=json.loads(json.dumps(result)), **args))
        self.assertFalse(result["formal_publication_authorized"])

    def test_added_table_reordered_columns_and_new_amount_are_source_driven(self):
        headers = [HEADERS[i] for i in [3, 0, 2, 1]]
        row = ["987,654", "Another Name Chief Executive Officer", "80", "2025"]
        args = arguments(source(headers=headers, rows=[row], prefix='<table><tr><td>Unrelated table</td></tr></table>'))
        result = resolve_compensation_table(**args)
        self.assertEqual("987654", result["result"]["value"])
        self.assertEqual("table_000002", result["selection"]["candidates"][0]["table_id"])

    def test_missing_or_conflicting_closing_date_and_period_do_not_guess(self):
        variants = [source(closing=""), source(closing="January 1, 2026"),
                    source(prefix='<p>On August 8, 2025 (the “Closing Date”), a different transaction closed.</p>'),
                    source(description=COVERED + ' The table also covers compensation for the period commencing on January 1, 2025 and ending on December 31, 2025.')]
        for raw in variants:
            with self.subTest(raw=raw[-100:]):
                result = resolve_compensation_table(**arguments(raw))
                self.assertIsNone(result["result"]["value"])
                self.assertTrue(result["selection"]["diagnostics"])

    def test_two_reported_ceos_preserve_both_without_first_win_or_sum(self):
        rows = [PERSON, ["Second Person Former Chief Executive Officer", "2025", "20", "75,000"]]
        result = resolve_compensation_table(**arguments(source(rows=rows)))
        self.assertIsNone(result["result"]["value"])
        self.assertEqual(["125000", "75000"], [c["value"] for c in result["selection"]["candidates"]])

    def test_double_total_column_or_changed_total_meaning_is_not_accepted(self):
        for raw in [source(headers=HEADERS + ["Total ($)"], rows=[PERSON + ["900,000"]]),
                    source(headers=HEADERS[:-1] + ["Compensation Actually Paid ($)"])]:
            self.assertIsNone(resolve_compensation_table(**arguments(raw))["result"]["value"])

    def test_wrong_year_financial_officer_assistant_or_divisional_ceo_is_not_selected(self):
        for row in [[PERSON[0], "2024", "40", "125,000"], ["Alex Example Chief Financial Officer", "2025", "40", "125,000"],
                    ["Alex Example Assistant to Chief Executive Officer", "2025", "40", "125,000"],
                    ["Alex Example Chief Executive Officer of International Division", "2025", "40", "125,000"]]:
            result = resolve_compensation_table(**arguments(source(rows=[row])))
            self.assertIsNone(result["result"]["value"])

    def test_missing_period_title_or_wrong_currency_is_not_public_nondisclosure(self):
        variants = [source(description="The following table gives amounts."), source(currency="CAD"),
                    source(description=COVERED + " All amounts are in Canadian dollars."),
                    source(description=COVERED + " All dollar amounts are in thousands."),
                    source().replace(b"SUMMARY COMPENSATION TABLE FOR 2025", b"POTENTIAL PAYMENTS UPON TERMINATION")]
        for raw in variants:
            result = resolve_compensation_table(**arguments(raw))
            self.assertEqual("WITHHELD", result["result"]["publication"])
            self.assertNotIn("DISCLOSED", result["result"]["reason_code"])

    def test_full_year_statement_uses_bound_fiscal_duration_not_closing_date(self):
        result = resolve_compensation_table(**arguments(source(description="The following table sets forth compensation for the year ended December 31, 2025.")))
        self.assertEqual("2025-01-01", result["result"]["period_start"])
        self.assertEqual("125000", result["result"]["value"])

    def test_bad_numeric_grouping_dash_and_missing_year_fail(self):
        for value in ["1,23", "—", "125,000 (1)"]:
            result = resolve_compensation_table(**arguments(source(rows=[[PERSON[0], "2025", "40", value]])))
            self.assertIsNone(result["result"]["value"])
        result = resolve_compensation_table(**arguments(source(rows=[[PERSON[0], "", "40", "125,000"]])))
        self.assertIsNone(result["result"]["value"])

    def test_source_entity_period_and_result_tampering_cannot_replay(self):
        args = arguments(source())
        result = resolve_compensation_table(**args)
        changed = copy.deepcopy(result)
        changed["result"]["period_start"] = "2025-01-01"
        with self.assertRaisesRegex(CompensationTableError, "REPLAY_MISMATCH"):
            replay_compensation_table(resolution=changed, **args)
        args["raw_bytes"] += b" "
        with self.assertRaises(ValueError):
            resolve_compensation_table(**args)

    def test_noncalendar_fiscal_year_is_not_forced_to_calendar_year(self):
        raw = source(description="The following table sets forth compensation for the fiscal year ended January 31, 2026.")
        raw = raw.replace(b"2025-01-01", b"2025-02-02").replace(b"2025-12-31", b"2026-01-31")
        args = arguments(raw)
        args.update(report_period_start="2025-02-02", report_period_end="2026-01-31")
        result = resolve_compensation_table(**args)
        self.assertEqual("2025-02-02", result["result"]["period_start"])
        self.assertEqual("2026-01-31", result["result"]["period_end"])
        self.assertEqual(2025, result["selection"]["fiscal_year"])

    def test_fake_taxonomy_or_currency_namespace_does_not_grant_semantic_credit(self):
        raw = source().replace(b"http://xbrl.sec.gov/dei/2025", b"https://example.test/not-dei")
        with self.assertRaises(ValueError):
            resolve_compensation_table(**arguments(raw))
        raw = source().replace(b"http://www.xbrl.org/2003/iso4217", b"https://example.test/not-currency")
        result = resolve_compensation_table(**arguments(raw))
        self.assertIsNone(result["result"]["value"])
        raw = source(description=COVERED + " All amounts are in euros.")
        self.assertIsNone(resolve_compensation_table(**arguments(raw))["result"]["value"])

    def test_conflicting_title_year_is_not_overridden_by_numeric_row(self):
        raw = source().replace(b"SUMMARY COMPENSATION TABLE FOR 2025", b"SUMMARY COMPENSATION TABLE FOR 2024")
        result = resolve_compensation_table(**arguments(raw))
        self.assertIsNone(result["result"]["value"])
        self.assertEqual("SCT_TITLE_YEAR_CONFLICT", result["selection"]["diagnostics"][0]["reason"])

    def test_native_rowspan_aliases_do_not_create_a_second_executive(self):
        raw = source().replace(b"<td>Alex Example Chairman and CEO</td><td>2025</td><td>40</td><td>125,000</td>",
            b'<td rowspan="2">Alex Example Chairman and CEO</td><td rowspan="2">2025</td><td>40</td><td rowspan="2">125,000</td></tr><tr><td>Additional salary detail</td>')
        result = resolve_compensation_table(**arguments(raw))
        self.assertEqual("125000", result["result"]["value"])
        self.assertEqual(1, len(result["selection"]["candidates"]))
        args = arguments(source())
        args["expected_cik"] = "54321"
        with self.assertRaises(ValueError):
            resolve_compensation_table(**args)


if __name__ == "__main__":
    unittest.main()
