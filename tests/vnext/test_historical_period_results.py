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
                                           restore_period_selection,
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

    def test_a_label_request_survives_being_stored_and_restored(self):
        """A replay restores the request it installed, both halves of it.

        The fiscal-year label is part of the selection identity, so a package
        installed by label must be restorable by label. Restoring only the
        report end rebuilds a different selection, which is exactly the
        mismatch a replay would have reported as a changed period.
        """
        with original_sources_only():
            asked = resolve_period_selection(repo_root=ROOT, company_id="salesforce",
                                             fiscal_year=2026)
            restored = restore_period_selection(
                repo_root=ROOT, company_id="salesforce",
                target_report_end=asked["target_report_end"],
                requested_fiscal_year=asked["requested_fiscal_year"])
            end_only = restore_period_selection(repo_root=ROOT, company_id="salesforce",
                                                target_report_end=asked["target_report_end"])
            by_end = resolve_period_selection(repo_root=ROOT, company_id="salesforce",
                                              report_end=asked["target_report_end"])
        self.assertEqual(asked, restored)
        self.assertEqual(asked["selection_id"], restored["selection_id"])
        # Same filing, different request, therefore a different identity.
        self.assertNotEqual(asked["selection_id"], end_only["selection_id"])
        self.assertEqual(by_end, end_only)
        self.assertEqual(asked["current_filing"], end_only["current_filing"])
        # A restored request is still re-derived from source, not trusted.
        with original_sources_only():
            with self.assertRaises(PeriodSelectionError) as absent:
                restore_period_selection(repo_root=ROOT, company_id="salesforce",
                                         target_report_end="2019-12-30",
                                         requested_fiscal_year=2026)
            with self.assertRaises(PeriodSelectionError) as malformed:
                restore_period_selection(repo_root=ROOT, company_id="salesforce",
                                         target_report_end=asked["target_report_end"],
                                         requested_fiscal_year="2026")
        self.assertEqual("ORDINARY_PERIOD_SELECTION_REPORT_END_NOT_IN_SAVED_SUBMISSIONS",
                         str(absent.exception))
        self.assertEqual("ORDINARY_PERIOD_SELECTION_FISCAL_YEAR_INVALID", str(malformed.exception))

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
        """A prior year is a date range, so its own instance may stand in for it.

        The prior role needs that filing's annual interval and its adjacency to
        the target, not an issuer fiscal-year label, so the historical route
        falls back to the accession's own authenticated XBRL instance exactly as
        the frozen current route does. What remains a real source gap is the
        accession index that names those documents: without it there is nothing
        to authenticate, and the ratio stays withheld rather than being computed
        from the current filing's own comparative column.
        """
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2023_END)
            component = resolve_historical_companyfacts_metrics(
                repo_root=ROOT, company_id=MARRIOTT, period_selection=selection)
        self.assertIsNotNone(component["prior_error"])
        self.assertTrue(component["prior_error"]["reason"].startswith("SAVED_SOURCE_MISSING:"))
        prior_accession = selection["prior_filing"]["accessionNumber"].replace("-", "")
        self.assertIn(prior_accession + "/index.json", component["prior_error"]["reason"])
        # The prior primary document is no longer what the route demands first.
        self.assertNotIn("mar-20221231.htm", component["prior_error"]["reason"])
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

    def test_a_prior_year_resolves_from_its_own_instance_when_its_html_is_absent(self):
        """The fallback is the frozen route's, not a new source rule.

        Ford's prior filing 0000037996-25-000013 has no saved primary HTML, only
        its own authenticated inline XBRL instance. The frozen current route
        already accepts that substitute for the prior role, because that role
        supplies a date range and its adjacency, never an issuer label. Demanding
        the HTML here made the ratio a source gap for six companies whose prior
        year was in fact readable, so the expected value below is computed in
        this file from the two original filings' own Company Facts entries.
        """
        cik = 37996
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT,
                                                 company_id="ford_motor_company",
                                                 report_end="2025-12-31")
            component = resolve_historical_companyfacts_metrics(
                repo_root=ROOT, company_id="ford_motor_company", period_selection=selection)
        current_accession = selection["current_filing"]["accessionNumber"]
        prior_accession = selection["prior_filing"]["accessionNumber"]
        self.assertIsNone(component["prior_error"])
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"}, component["periods"]["prior"])
        prior_documents = [r["document_name"] for r in component["source_records"]
                           if r.get("accession") == prior_accession
                           and r.get("source_role") == "auditor_facts"]
        # The prior year is bound to the accession's own instance, and the
        # primary document the selection names for it was never read.
        self.assertEqual(["f-20241231_htm.xml"], prior_documents)
        self.assertEqual("f-20241231.htm", selection["prior_filing"]["primaryDocument"])
        self.assertNotIn("f-20241231.htm", [r.get("document_name")
                                            for r in component["source_records"]])
        current = original_fact(cik=cik,
                                concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                                accession=current_accession,
                                start="2025-01-01", end="2025-12-31")
        # First-report semantics: the prior value comes from the prior filing's
        # own accession, not from the current filing's comparative column.
        prior = original_fact(cik=cik, concept="Revenues", accession=prior_accession,
                              start="2024-01-01", end="2024-12-31")
        b02 = component["metrics"]["B02"]["result"]
        self.assertEqual("EXACT", b02["quality"])
        self.assertEqual("ratio", b02["unit"])
        self.assertEqual((Decimal(current[1]) - Decimal(prior[1])) / Decimal(prior[1]),
                         Decimal(b02["value"]))
        self.assertEqual("2025-01-01", b02["period_start"])
        self.assertEqual("2025-12-31", b02["period_end"])

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

    def test_revenue_comes_from_the_selected_filing_s_own_accession(self):
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        with original_sources_only():
            newer = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                             report_end=FY2024_END)
            older = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                             report_end=FY2023_END)
            current = resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=MARRIOTT,
                                                        metric_id="B01", period_selection=newer)
            prior = resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=MARRIOTT,
                                                      metric_id="B01", period_selection=older)
        cik = 1048286
        expected_current = original_fact(cik=cik, concept="Revenues", accession=FY2024_ACCESSION,
                                         start="2024-01-01", end="2024-12-31")
        expected_prior = original_fact(cik=cik, concept="Revenues", accession=FY2023_ACCESSION,
                                       start="2023-01-01", end="2023-12-31")
        self.assertEqual("EXACT", current["result"]["quality"])
        self.assertEqual(Decimal(expected_current[1]), Decimal(current["result"]["value"]))
        self.assertEqual(("2024-01-01", "2024-12-31"),
                         (current["result"]["period_start"], current["result"]["period_end"]))
        self.assertEqual("EXACT", prior["result"]["quality"])
        self.assertEqual(Decimal(expected_prior[1]), Decimal(prior["result"]["value"]))
        self.assertEqual(("2023-01-01", "2023-12-31"),
                         (prior["result"]["period_start"], prior["result"]["period_end"]))
        # Two periods of the same company resolve to different values and
        # different identities; neither carries the other's answer.
        self.assertNotEqual(current["result"]["value"], prior["result"]["value"])
        self.assertNotEqual(current["component_id"], prior["component_id"])
        for component in (current, prior):
            self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, component["calls"])
            self.assertFalse(component["latest_restated_values_used"])
            self.assertEqual("NOT_CREATED", component["native_run_status"])

    def test_an_unwired_revenue_route_variant_is_an_explicit_gap(self):
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        from vnext.normal_zero_ai_results import NormalZeroAiError
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
            with self.assertRaises(NormalZeroAiError) as event:
                resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=MARRIOTT,
                                                  metric_id="C01", period_selection=selection)
        self.assertEqual("HISTORICAL_ZERO_AI_METRIC_NOT_WIRED:C01", str(event.exception))
        self.assertEqual("IMPLEMENTATION_GAP", event.exception.category)

    def test_a_restated_comparative_does_not_reach_the_earlier_period(self):
        """A real restatement in the repository's own saved Company Facts.

        Marriott's FY2023 filing reports OtherOperatingActivitiesCashFlowStatement
        for 2023 as 21,000,000. The FY2024 filing's comparative column for the
        same period reports -138,000,000. Both rows live in the same saved JSON,
        so which accession a period is bound to is what decides the value, and a
        historical target must land on its own filing's first report.
        """
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        from vnext.sources import companyfacts_structured_facts
        concept = "OtherOperatingActivitiesCashFlowStatement"
        restated = original_fact(cik=1048286, concept=concept, accession=FY2024_ACCESSION,
                                 start="2023-01-01", end="2023-12-31")
        first_report = original_fact(cik=1048286, concept=concept, accession=FY2023_ACCESSION,
                                     start="2023-01-01", end="2023-12-31")
        self.assertNotEqual(restated[1], first_report[1])

        with original_sources_only():
            selections = {end: resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                        report_end=end)
                          for end in (FY2024_END, FY2023_END)}
            components = {end: resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id=MARRIOTT, metric_id="B01",
                period_selection=selection) for end, selection in selections.items()}
            raw = (ROOT / "evidence/companyfacts/CIK0001048286.json").read_bytes()
            values = {}
            for end, component in components.items():
                reference = next(r for r in component["source_references"]
                                 if r["source_role"] == "companyfacts")
                facts = companyfacts_structured_facts(
                    raw_bytes=raw, source_reference=reference, approved_concepts=[concept],
                    allowed_ciks=["1048286"], include_instant=False)
                rows = [f for f in facts if f["period_start"] == "2023-01-01"
                        and f["period_end"] == "2023-12-31"]
                self.assertEqual(1, len(rows), (end, rows))
                values[end] = rows[0]["value"]
        # Each target period reads its own filing's report of the same span.
        self.assertEqual(FY2024_ACCESSION,
                         next(r["accession"] for r in components[FY2024_END]["source_references"]
                              if r["source_role"] == "companyfacts"))
        self.assertEqual(FY2023_ACCESSION,
                         next(r["accession"] for r in components[FY2023_END]["source_references"]
                              if r["source_role"] == "companyfacts"))
        self.assertEqual(Decimal(first_report[1]), Decimal(values[FY2023_END]))
        self.assertEqual(Decimal(restated[1]), Decimal(values[FY2024_END]))

    def test_an_instant_fact_is_read_at_the_selected_period_end(self):
        from vnext.historical_accession_results import resolve_historical_accession_metrics
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id="salesforce",
                                                 report_end="2026-01-31")
            component = resolve_historical_accession_metrics(repo_root=ROOT,
                                                             company_id="salesforce",
                                                             period_selection=selection)
        assets = component["metrics"]["B12"]["result"]
        self.assertEqual("EXACT", assets["quality"])
        self.assertEqual("72400000000", assets["value"])
        # An instant is measured at the selected period end, not over a span.
        self.assertEqual(("2026-01-31", "2026-01-31"),
                         (assets["period_start"], assets["period_end"]))
        # The installed applicability rules still decide structural scope; a
        # bank-only measure stays N_A_STRUCTURAL rather than becoming missing.
        for metric_id in ("A01", "A02"):
            result = component["metrics"][metric_id]["result"]
            self.assertEqual("N_A_STRUCTURAL", result["applicability"])
            self.assertEqual("TRAIT_NOT_APPLICABLE", result["reason_code"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, component["calls"])
        self.assertFalse(component["latest_restated_values_used"])

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
