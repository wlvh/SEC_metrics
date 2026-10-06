"""Small table business cases, independent of company install and source acquisition."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext import lodging_table_source as lodging
from vnext.canonical import content_hash, sha256_bytes
from vnext.normal_annual_input import annual_period, NormalAnnualInputError
from vnext.specs import compile_spec_file


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "tests/fixtures/lodging_selected_table.html").read_bytes()


def annual_source(**overrides):
    """Small complete DEI input, with independent 52-week-year expectations."""
    facts = {"DocumentType": "10-K", "DocumentPeriodEndDate": "2025-02-01",
             "DocumentFiscalYearFocus": "2024", "DocumentFiscalPeriodFocus": "FY",
             "AmendmentFlag": "false", "EntityCentralIndexKey": "0000000001"}
    facts.update(overrides)
    raw = ('<!doctype html><html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" '
           'xmlns:xbrli="http://www.xbrl.org/2003/instance" '
           'xmlns:dei="http://xbrl.sec.gov/dei/2025"><body>'
           '<xbrli:context id="annual"><xbrli:entity><xbrli:identifier '
           'scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>'
           '<xbrli:period><xbrli:startDate>2024-02-04</xbrli:startDate>'
           '<xbrli:endDate>2025-02-01</xbrli:endDate></xbrli:period></xbrli:context>')
    for name, text in facts.items():
        raw += f'<ix:nonNumeric name="dei:{name}" contextRef="annual">{text}</ix:nonNumeric>'
    return (raw + '</body></html>').encode()


class PreparedPeriodBusinessTest(unittest.TestCase):
    def period(self, raw, cik="1"):
        return annual_period(raw=raw, cik=cik, filing={"form": "10-K", "reportDate": "2025-02-01"})

    def test_source_label_and_52_week_interval_are_kept(self):
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-02-04", "period_end": "2025-02-01"},
                         self.period(annual_source()))

    def test_invalid_label_is_an_integrity_failure(self):
        for label, reason in (("unknown", "ANNUAL_IDENTITY_CONFLICT"),
                              ("1999", "DEI_FISCAL_YEAR_CONFLICT")):
            with self.subTest(label=label), self.assertRaisesRegex(NormalAnnualInputError, reason) as caught:
                self.period(annual_source(DocumentFiscalYearFocus=label))
            self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)

    def test_context_and_reported_cik_cannot_change_the_selected_subject(self):
        for raw, cik, reason in ((annual_source(), "2", "DEI_SUBJECT_CONFLICT"),
                                 (annual_source(EntityCentralIndexKey="2"), "1", "ANNUAL_IDENTITY_CONFLICT")):
            with self.subTest(cik=cik), self.assertRaisesRegex(NormalAnnualInputError, reason) as caught:
                self.period(raw, cik)
            self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)

    def test_quarter_and_amendment_are_not_an_ordinary_annual_selection(self):
        for overrides in ({"DocumentFiscalPeriodFocus": "Q4"}, {"AmendmentFlag": "true"}):
            with self.subTest(overrides=overrides), self.assertRaisesRegex(NormalAnnualInputError, "ANNUAL_IDENTITY_CONFLICT"):
                self.period(annual_source(**overrides))

    def test_short_interval_is_a_named_implementation_gap(self):
        raw = annual_source(DocumentFiscalYearFocus="2025").replace(b"2024-02-04", b"2025-01-01")
        with self.assertRaisesRegex(NormalAnnualInputError, "ANNUAL_DURATION_NOT_IMPLEMENTED") as caught:
            self.period(raw)
        self.assertEqual("IMPLEMENTATION_GAP", caught.exception.category)


class SelectedLodgingSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = {m: compile_spec_file(path=ROOT / p, dependency_specs={})
                     for m, p in lodging.POLICY["metric_specs"].items()}

    def arguments(self, raw=HTML, *, year=2025, start="2025-01-01", end="2025-12-31"):
        identity = "sha256:" + sha256_bytes(content=raw)
        return {"raw": raw, "blob": {"raw_asset_id": identity, "byte_length": len(raw)},
                "reference": {"raw_asset_id": identity, "company_id": "example",
                              "accession": "0000000001-26-000001"},
                "filing": {"accessionNumber": "0000000001-26-000001", "reportDate": end},
                "company_id": "example", "period": {"fiscal_year": year, "period_start": start,
                                                      "period_end": end},
                "policy": copy.deepcopy(lodging.POLICY), "specs": self.specs}

    def changed(self, before, after):
        self.assertIn(before, HTML)
        return self.arguments(HTML.replace(before, after))

    def test_both_metrics_keep_units_scope_period_and_raw_cell_positions(self):
        args = self.arguments()
        result = lodging.read_selected_lodging_source(**args)
        facts = result["selection"]["facts"]
        self.assertEqual(("0.693", "128.8"), (facts["B10"]["value"], facts["B11"]["value"]))
        self.assertEqual(("%", "$"), (facts["B10"]["reported_unit"], facts["B11"]["reported_unit"]))
        self.assertEqual(("ratio", "USD"), (facts["B10"]["unit"], facts["B11"]["unit"]))
        for fact in facts.values():
            self.assertEqual(args["period"], fact["period"])
            self.assertEqual({"property_population": "comparable", "operating_scope": "systemwide",
                              "geography": "worldwide"}, fact["scope"])
            self.assertEqual("2025", fact["source_witnesses"]["year"]["raw_text"])
            self.assertEqual("\nWorldwide (1)", fact["source_witnesses"]["geography"]["raw_text"])
        self.assertFalse(result["ai_response_used"])
        self.assertFalse(result["native_run_created"])

    def test_non_calendar_prepared_period_is_not_inferred_from_end_year(self):
        raw = HTML.replace(b"2024", b"2023").replace(b"2025", b"2024")
        args = self.arguments(raw, year=2024, start="2024-02-04", end="2025-02-01")
        facts = lodging.read_selected_lodging_source(**args)["selection"]["facts"]
        self.assertEqual(args["period"], facts["B10"]["period"])
        self.assertEqual("2024", facts["B11"]["source_witnesses"]["year"]["text"])

    def test_policy_is_explicit_and_never_changes_module_globals(self):
        args = self.changed(b"table presents", b"tables present")
        with self.assertRaisesRegex(lodging.LodgingSourceError, "INTRODUCTION_UNPROVEN"):
            lodging.read_selected_lodging_source(**args)
        args["policy"]["table_introduction_pattern"] = args["policy"]["table_introduction_pattern"].replace(
            "table presents", "(?:table presents|tables present)")
        before = copy.deepcopy(lodging.POLICY)
        result = lodging.read_selected_lodging_source(**args)
        self.assertEqual(content_hash(value=args["policy"]), result["policy_hash"])
        self.assertEqual(before, lodging.POLICY)
        with self.assertRaisesRegex(lodging.LodgingSourceError, "INTRODUCTION_UNPROVEN"):
            lodging.read_selected_lodging_source(**self.changed(b"table presents", b"tables present"))

    def test_company_accession_raw_bytes_and_period_must_match_selected_source(self):
        for field, value, error in (("company_id", "other", "SOURCE_BINDING_CONFLICT"),
                                   ("accession", "other", "SOURCE_BINDING_CONFLICT"),
                                   ("raw_asset_id", "sha256:" + "0" * 64, "SOURCE_BINDING_CONFLICT"),
                                   ("period_end", "2024-12-31", "ANNUAL_PERIOD_CONFLICT")):
            with self.subTest(field=field):
                args = self.arguments()
                if field == "period_end":
                    args["period"][field] = value
                else:
                    args["reference"][field] = value
                with self.assertRaisesRegex(lodging.LodgingSourceError, error):
                    lodging.read_selected_lodging_source(**args)

    def test_year_column_and_introduction_are_independent_checks(self):
        for args, reason in ((self.changed(b"properties for 2025", b"properties for 2024"), "INTRODUCTION_UNPROVEN"),
                             (self.changed(b">2025</th>", b">2024</th>"), "CURRENT_YEAR_COLUMN")):
            with self.subTest(raw=args["raw"][:30]):
                with self.assertRaisesRegex(lodging.LodgingSourceError, reason):
                    lodging.read_selected_lodging_source(**args)

    def test_scope_and_unit_cannot_be_borrowed_or_guessed(self):
        for before, after, reason in ((b"Comparable Systemwide Properties", b"Other Properties", "POPULATION_SECTION"),
                                      (b"<td>%</td>", b"<td>$</td>", "AMOUNT_AND_UNIT"),
                                      (b"69.3", b"169.3", "REPORTED_VALUE_OUT_OF_RANGE")):
            with self.subTest(after=after):
                with self.assertRaisesRegex(lodging.LodgingSourceError, reason):
                    lodging.read_selected_lodging_source(**self.changed(before, after))

    def test_local_period_currency_and_footnote_conflicts_are_not_ignored(self):
        for before, after, reason in ((b"<p>(2) Includes Europe.</p>", b"<p>(2) Includes Europe. For Q4 only.</p>", "LOCAL_MEASUREMENT_PERIOD_QUALIFIER"),
                                      (b"constant U.S. dollar", b"constant euro", "US_DOLLAR_DEFINITION_NOT_UNIQUE"),
                                      (b"(2) Includes Europe.", b"(2) Includes U.S. &amp; Canada.", "FOOTNOTE_COMPOSITION_DIFFERS")):
            with self.subTest(after=after):
                with self.assertRaisesRegex(lodging.LodgingSourceError, reason):
                    lodging.read_selected_lodging_source(**self.changed(before, after))

    def test_competing_target_and_truncated_html_are_not_a_success(self):
        table = HTML[HTML.index(b"<table>"):HTML.index(b"</table>") + len(b"</table>")]
        duplicated = HTML.replace(b"</body>", b"<p><b>Other disclosure</b></p>" + table + b"</body>")
        with self.assertRaisesRegex(lodging.LodgingSourceError, "COMPETING_TARGET"):
            lodging.read_selected_lodging_source(**self.arguments(duplicated))
        with self.assertRaisesRegex(lodging.LodgingSourceError, "FULL_PRIMARY_REQUIRED"):
            lodging.read_selected_lodging_source(**self.arguments(HTML.replace(b"</body>", b"")))

    def test_selected_reader_does_not_prepare_or_parse_dei_again(self):
        with patch.object(lodging, "annual_period", side_effect=AssertionError("DEI reread")), \
                patch.object(lodging, "prepare_saved_annual_input", side_effect=AssertionError("selection repeated")):
            result = lodging.read_selected_lodging_source(**self.arguments())
        self.assertEqual("0.693", result["selection"]["facts"]["B10"]["value"])


if __name__ == "__main__":
    unittest.main()
