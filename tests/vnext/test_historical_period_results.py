"""An explicitly selected past period resolves to that period's own sources.

Every case runs against the repository's own saved SEC bytes with no network
and no new business call. Expected values are taken from the original Company
Facts JSON by direct lookup and independent arithmetic in this file; they are
never produced by calling the same selector or resolver under test.
"""
import json
from decimal import Decimal
from pathlib import Path
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import content_hash
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.historical_results import (prepare_historical_run_input,
                                      resolve_historical_companyfacts_metrics)
from vnext.normal_annual_input import NormalAnnualInputError
from vnext.normal_annual_input_v2 import prepare_saved_annual_input as current_annual_input
from vnext.normal_period_selection import (PeriodSelectionError, resolve_period_selection,
                                           selected_historical_filing)


MARRIOTT = "marriott_international"
FY2024_END = "2024-12-31"
FY2023_END = "2023-12-31"
FY2024_ACCESSION = "0001628280-25-004818"
FY2023_ACCESSION = "0001628280-24-004372"


def original_fact(*, cik, concept, accession, start, end):
    """Read one original Company Facts value without any project selector."""
    facts = json.loads((ROOT / "evidence/companyfacts" / ("CIK%010d.json" % cik)).read_text())
    found = [(unit, row["val"]) for unit, rows in facts["facts"]["us-gaap"][concept]["units"].items()
             for row in rows
             if row.get("accn") == accession and row.get("start") == start and row.get("end") == end]
    assert len(found) == 1, (concept, accession, found)
    return found[0]


class HistoricalPeriodSelectionTest(unittest.TestCase):
    def test_a_requested_report_end_pins_that_filing_and_its_prior(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
            again = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                             report_end=FY2024_END)
        self.assertEqual(selection, again)
        self.assertEqual(FY2024_END, selection["target_report_end"])
        self.assertEqual(FY2024_ACCESSION, selection["current_filing"]["accessionNumber"])
        self.assertEqual(FY2023_ACCESSION, selection["prior_filing"]["accessionNumber"])
        self.assertEqual("SAME_CIK_PRIOR_DISCOVERED", selection["prior_status"])
        self.assertIsNone(selection["requested_fiscal_year"])
        self.assertFalse(selection["latest_restated_values_used"])
        self.assertFalse(selection["caller_supplied_selection_trusted"])
        self.assertEqual(content_hash(value={k: v for k, v in selection.items()
                                             if k != "selection_id"}),
                         selection["selection_id"])

    def test_a_resigned_selection_cannot_introduce_another_filing(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
            company = {"company_id": MARRIOTT, "primary_cik": "1048286"}
            submissions = json.loads((ROOT / "evidence/submissions/CIK0001048286.json").read_text())
            forged = json.loads(json.dumps(selection))
            forged["current_filing"] = dict(selection["prior_filing"])
            forged["selection_id"] = content_hash(
                value={k: v for k, v in forged.items() if k != "selection_id"})
            with self.assertRaises(PeriodSelectionError) as changed:
                selected_historical_filing(repo_root=ROOT, company=company,
                                           submissions=submissions, period_selection=forged)
            other = {**selection, "company_id": "ford_motor_company"}
            with self.assertRaises(PeriodSelectionError) as wrong_company:
                selected_historical_filing(repo_root=ROOT, company=company,
                                           submissions=submissions, period_selection=other)
        self.assertEqual("ORDINARY_PERIOD_SELECTION_CHANGED", str(changed.exception))
        self.assertEqual("ORDINARY_PERIOD_SELECTION_COMPANY_CONFLICT", str(wrong_company.exception))

    def test_an_issuer_label_is_read_from_source_not_computed_from_the_date(self):
        with original_sources_only():
            # Salesforce labels the year ending 2026-01-31 as fiscal 2026 while
            # its own DEI focus metadata says 2025. A label request must follow
            # the issuer definition the frozen policy resolves, not the date.
            selection = resolve_period_selection(repo_root=ROOT, company_id="salesforce",
                                                 fiscal_year=2026)
            unreadable = None
            try:
                resolve_period_selection(repo_root=ROOT, company_id="salesforce", fiscal_year=2025)
            except PeriodSelectionError as error:
                unreadable = error
        self.assertEqual("2026-01-31", selection["target_report_end"])
        self.assertEqual(2026, selection["requested_fiscal_year"])
        self.assertEqual("0001108524-26-000060", selection["current_filing"]["accessionNumber"])
        self.assertIsNotNone(unreadable)
        self.assertTrue(str(unreadable).startswith(
            "ORDINARY_PERIOD_SELECTION_CANDIDATE_SOURCE_UNAVAILABLE:"))
        self.assertEqual("SOURCE_UNAVAILABLE", unreadable.category)

    def test_an_unknown_period_or_request_shape_is_an_explicit_refusal(self):
        with original_sources_only():
            with self.assertRaises(PeriodSelectionError) as both:
                resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                         report_end=FY2024_END, fiscal_year=2024)
            with self.assertRaises(PeriodSelectionError) as neither:
                resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT)
            with self.assertRaises(PeriodSelectionError) as absent:
                resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                         report_end="2019-12-30")
            with self.assertRaises(PeriodSelectionError) as malformed:
                resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                         report_end="2024-13-01")
        self.assertEqual("ORDINARY_PERIOD_SELECTION_EXACTLY_ONE_REQUEST_REQUIRED", str(both.exception))
        self.assertEqual("ORDINARY_PERIOD_SELECTION_EXACTLY_ONE_REQUEST_REQUIRED",
                         str(neither.exception))
        self.assertEqual("ORDINARY_PERIOD_SELECTION_REPORT_END_NOT_IN_SAVED_SUBMISSIONS",
                         str(absent.exception))
        self.assertEqual("SOURCE_UNAVAILABLE", absent.exception.category)
        self.assertEqual("ORDINARY_PERIOD_SELECTION_REPORT_END_INVALID", str(malformed.exception))
        self.assertEqual("IMPLEMENTATION_GAP", malformed.exception.category)


class HistoricalAnnualInputTest(unittest.TestCase):
    def test_the_pinned_period_is_read_from_its_own_filing(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
            prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=MARRIOTT,
                                                       period_selection=selection)
            current = current_annual_input(repo_root=ROOT, company_id=MARRIOTT)
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"},
                         prepared["table_input"]["target_period"])
        self.assertEqual(FY2024_ACCESSION, prepared["filing"]["accessionNumber"])
        self.assertEqual(FY2024_ACCESSION, prepared["companyfacts_input"]["accession"])
        self.assertEqual("PINNED_ORDINARY_PERIOD_IN_COMPLETE_SAVED_SUBMISSIONS",
                         prepared["selection_rule"])
        self.assertEqual(selection, prepared["period_selection"])
        self.assertFalse(prepared["current_latest_verified"])
        # The frozen current entry is untouched and still resolves the latest.
        self.assertEqual(2025, current["table_input"]["target_period"]["fiscal_year"])
        self.assertEqual("LATEST_ORDINARY_PERIOD_IN_SAVED_SUBMISSIONS", current["selection_rule"])
        self.assertNotIn("period_selection", current)


class HistoricalCompanyfactsResultTest(unittest.TestCase):
    def test_values_match_independent_arithmetic_on_the_original_filings(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
            component = resolve_historical_companyfacts_metrics(
                repo_root=ROOT, company_id=MARRIOTT, period_selection=selection)
            repeated = resolve_historical_companyfacts_metrics(
                repo_root=ROOT, company_id=MARRIOTT, period_selection=selection)
        self.assertEqual(component["component_id"], repeated["component_id"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, component["calls"])
        self.assertFalse(component["production_authorized"])
        self.assertFalse(component["latest_restated_values_used"])
        self.assertIsNone(component["prior_error"])
        self.assertEqual(FY2024_ACCESSION, component["filings"]["current"]["accessionNumber"])
        self.assertEqual(FY2023_ACCESSION, component["filings"]["prior"]["accessionNumber"])
        self.assertEqual(2023, component["periods"]["prior"]["fiscal_year"])

        cik = 1048286
        net = original_fact(cik=cik, concept="NetIncomeLoss", accession=FY2024_ACCESSION,
                            start="2024-01-01", end="2024-12-31")
        operating = original_fact(cik=cik, concept="NetCashProvidedByUsedInOperatingActivities",
                                  accession=FY2024_ACCESSION, start="2024-01-01", end="2024-12-31")
        capex = original_fact(cik=cik, concept="PaymentsToAcquirePropertyPlantAndEquipment",
                              accession=FY2024_ACCESSION, start="2024-01-01", end="2024-12-31")
        current_revenue = original_fact(cik=cik, concept="Revenues", accession=FY2024_ACCESSION,
                                        start="2024-01-01", end="2024-12-31")
        # The prior value is the prior filing's own first report, not the
        # comparative column of the current year's filing.
        prior_revenue = original_fact(cik=cik, concept="Revenues", accession=FY2023_ACCESSION,
                                      start="2023-01-01", end="2023-12-31")

        b04 = component["metrics"]["B04"]["result"]
        self.assertEqual("EXACT", b04["quality"])
        self.assertEqual(("USD", Decimal(b04["value"])), (net[0], Decimal(net[1])))
        b05 = component["metrics"]["B05"]["result"]
        self.assertEqual("EXACT", b05["quality"])
        self.assertEqual(Decimal(operating[1]) - Decimal(capex[1]), Decimal(b05["value"]))
        b02 = component["metrics"]["B02"]["result"]
        self.assertEqual("EXACT", b02["quality"])
        self.assertEqual("ratio", b02["unit"])
        expected = ((Decimal(current_revenue[1]) - Decimal(prior_revenue[1]))
                    / Decimal(prior_revenue[1]))
        self.assertEqual(expected, Decimal(b02["value"]))
        for metric in ("B02", "B04", "B05"):
            result = component["metrics"][metric]["result"]
            self.assertEqual("2024-01-01", result["period_start"])
            self.assertEqual("2024-12-31", result["period_end"])

    def test_a_missing_prior_source_blocks_only_the_metric_that_needs_it(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2023_END)
            component = resolve_historical_companyfacts_metrics(
                repo_root=ROOT, company_id=MARRIOTT, period_selection=selection)
        self.assertIsNotNone(component["prior_error"])
        self.assertTrue(component["prior_error"]["reason"].startswith("SAVED_SOURCE_MISSING:"))
        self.assertIn("mar-20221231.htm", component["prior_error"]["reason"])
        self.assertIsNone(component["periods"]["prior"])
        withheld = component["metrics"]["B02"]["result"]
        self.assertEqual("WITHHELD", withheld["publication"])
        self.assertEqual("HISTORICAL_COMPANYFACTS_ROUTE_UNRESOLVED", withheld["reason_code"])
        self.assertIsNone(withheld["value"])
        cik = 1048286
        net = original_fact(cik=cik, concept="NetIncomeLoss", accession=FY2023_ACCESSION,
                            start="2023-01-01", end="2023-12-31")
        self.assertEqual("EXACT", component["metrics"]["B04"]["result"]["quality"])
        self.assertEqual(Decimal(net[1]), Decimal(component["metrics"]["B04"]["result"]["value"]))
        self.assertEqual("EXACT", component["metrics"]["B05"]["result"]["quality"])

    def test_a_target_whose_own_original_is_not_saved_is_a_source_gap(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id="ford_motor_company",
                                                 report_end="2024-12-31")
            with self.assertRaises(NormalAnnualInputError) as missing:
                resolve_historical_companyfacts_metrics(repo_root=ROOT,
                                                        company_id="ford_motor_company",
                                                        period_selection=selection)
        self.assertTrue(str(missing.exception).startswith("SAVED_SOURCE_MISSING:"))
        self.assertIn("f-20241231.htm", str(missing.exception))
        self.assertEqual("SOURCE_UNAVAILABLE", missing.exception.category)

    def test_an_accession_instance_cannot_establish_an_issuer_fiscal_label(self):
        """Why a target year without its own primary HTML stays a source gap.

        The prior-annual route may read an accession's own XBRL instance,
        because it only needs that filing's dates and their adjacency. An
        issuer fiscal-year label is a different claim: the frozen policy reads
        the issuer's own explicit definition from the full document, and
        Salesforce is the standing proof that the label and the DEI focus year
        can differ. So the instance is accepted for a period and refused for a
        label, and a target year whose own primary HTML is not saved is
        reported as missing rather than labelled from the instance.
        """
        from sec_urls import companyfacts_url
        from vnext.canonical import sha256_bytes
        from vnext.fiscal_year_labels import FiscalYearLabelError, inspect_fiscal_year_labels
        from vnext.normal_annual_input import annual_period
        from vnext.normal_governance_input import _Sources
        filing = {"form": "10-K", "reportDate": "2024-12-31", "filingDate": "2025-02-06",
                  "accessionNumber": "0000037996-25-000013", "primaryDocument": "f-20241231.htm"}
        with original_sources_only():
            reader = _Sources(ROOT, "ford_motor_company", "37996")
            documents = reader.auditor_filing(filing)
            file_set = reader.file_sets[-1]
            period = annual_period(raw=documents[0]["raw_bytes"], cik="37996", filing=filing)
            facts = reader.read(companyfacts_url(cik=37996), accession=filing["accessionNumber"],
                                role="companyfacts", media_type="application/json")
            with self.assertRaises(FiscalYearLabelError) as refused:
                inspect_fiscal_year_labels(
                    primary_bytes=documents[0]["raw_bytes"], companyfacts_bytes=facts["raw_bytes"],
                    expected_primary_sha256=sha256_bytes(content=documents[0]["raw_bytes"]),
                    expected_companyfacts_sha256=sha256_bytes(content=facts["raw_bytes"]),
                    expected_cik="37996", filing=filing)
        self.assertFalse(file_set["primary_saved"])
        self.assertEqual(["f-20241231_htm.xml"], file_set["expected_xml_documents"])
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"}, period)
        self.assertEqual("FISCAL_LABEL_FULL_DOCUMENT_REQUIRED", str(refused.exception))

    def test_a_run_input_carries_the_selection_and_the_installed_spec(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
            prepared = prepare_historical_run_input(repo_root=ROOT, company_id=MARRIOTT,
                                                    metric_id="B04", period_selection=selection)
        self.assertEqual("HISTORICAL_ZERO_AI_RUN_INPUT", prepared["record_type"])
        self.assertEqual(selection, prepared["period_selection"])
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"}, prepared["target_period"])
        self.assertEqual(["B04"], prepared["required_metric_ids"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, prepared["calls"])
        self.assertEqual("NOT_CREATED", prepared["native_run_status"])
        self.assertEqual(content_hash(value={k: v for k, v in prepared.items()
                                             if k != "input_id"}), prepared["input_id"])


if __name__ == "__main__":
    unittest.main()
