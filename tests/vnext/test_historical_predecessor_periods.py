"""A registered predecessor's years in the historical frame (Issue #47 section 7.3).

The Issue asks for a predecessor's years to be read from that year's own
filings with the registrant that filed them, and forbids applying today's
successor-only status backward. Paramount is the only company here with a
registered predecessor: CIK 2041610 filed one annual report (FY2025) and CIK
813828 filed the four before it. Each case below is one boundary that reading
has to keep, checked where the saved filings put it.
"""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_amendment_admission as admission
from vnext import historical_debt_results as debt
from vnext import normal_history_catalog as catalog
from vnext import normal_period_selection as selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_annual_input import NormalAnnualInputError

PARAMOUNT = "paramount_skydance_paramount_global"
SUCCESSOR, PREDECESSOR = "2041610", "813828"


def _select(company_id, report_end=None, fiscal_year=None):
    with original_sources_only():
        return selection.resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                                  report_end=report_end,
                                                  fiscal_year=fiscal_year)


class TheWindowCrossesToThePredecessorOnlyWhereTheSuccessorFiledNothingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.candidates, _, cls.histories = catalog.frame_period_candidates(
                repo_root=ROOT, company_id=PARAMOUNT, count=5)

    def test_the_successor_s_year_then_four_predecessor_years(self):
        self.assertEqual([("2025-12-31", None), ("2024-12-31", PREDECESSOR),
                          ("2023-12-31", PREDECESSOR), ("2022-12-31", PREDECESSOR),
                          ("2021-12-31", PREDECESSOR)],
                         [(c["report_date"], c.get("reporting_cik")) for c in self.candidates])
        self.assertEqual([1, 2, 3, 4, 5], [c["target_ordinal"] for c in self.candidates])

    def test_no_prior_is_taken_across_the_registrant_boundary(self):
        """The successor's first year has no prior; each predecessor year's is its own."""
        first = self.candidates[0]
        self.assertIsNone(first["prior_filing"])
        self.assertEqual("NO_SAME_CIK_PRIOR_IN_SAVED_SUBMISSIONS", first["prior_status"])
        for candidate in self.candidates[1:]:
            with self.subTest(candidate["report_date"]):
                self.assertEqual("SAME_CIK_PRIOR_DISCOVERED", candidate["prior_status"])
                self.assertLess(candidate["prior_report_date"], candidate["report_date"])
        self.assertEqual([PREDECESSOR], [h["reporting_cik"] for h in self.histories])

    def test_a_company_without_a_predecessor_reads_exactly_as_before(self):
        with original_sources_only():
            history = catalog.load_annual_history(repo_root=ROOT,
                                                  company_id="marriott_international",
                                                  required_annual_count=6)
            frame, _, earlier = catalog.frame_period_candidates(
                repo_root=ROOT, company_id="marriott_international", count=5, history=history)
            plain = catalog.target_period_candidates(repo_root=ROOT,
                                                     company_id="marriott_international",
                                                     count=5, history=history)
        self.assertEqual(plain, frame)
        self.assertEqual([], earlier)
        self.assertFalse(any("reporting_cik" in c for c in frame))
        self.assertNotIn("reporting_cik", catalog.catalog_identity(history=history))

    def test_a_cik_the_registry_does_not_name_for_the_company_is_not_read(self):
        with original_sources_only(), self.assertRaises(catalog.HistoryCatalogError) as raised:
            catalog.load_history_for_period(repo_root=ROOT, company_id="marriott_international",
                                            report_end="2024-12-31", cik=PREDECESSOR)
        self.assertEqual("HISTORY_CIK_NOT_REGISTERED_FOR_COMPANY", str(raised.exception))


class TheSelectionNamesThePeriodsOwnRegistrantTest(unittest.TestCase):

    def test_a_predecessor_year_is_selected_with_that_registrant_s_own_policy(self):
        chosen = _select(PARAMOUNT, report_end="2024-12-31")
        self.assertEqual(PREDECESSOR, chosen["reporting_cik"])
        self.assertEqual({"mode": "CONTINUOUS_PRIMARY", "selected_cik": PREDECESSOR,
                          "cross_entity_combination_authorized": False},
                         chosen["subject_policy"])
        registrant = chosen["period_registrant"]
        self.assertEqual(("PREDECESSOR", SUCCESSOR, "2025-12-31"),
                         (registrant["role"], registrant["successor_cik"],
                          registrant["successor_oldest_annual_report_end"]))
        self.assertEqual("SUCCESSOR_REGISTRANT_ONLY",
                         registrant["company_subject_policy"]["mode"])
        self.assertEqual("0000813828-25-000005", chosen["current_filing"]["accessionNumber"])
        self.assertEqual("SAME_CIK_PRIOR_DISCOVERED", chosen["prior_status"])

    def test_the_successor_s_own_year_is_never_answered_from_the_predecessor(self):
        chosen = _select(PARAMOUNT, report_end="2025-12-31")
        self.assertEqual(SUCCESSOR, chosen["reporting_cik"])
        self.assertEqual("SUCCESSOR_REGISTRANT_ONLY", chosen["subject_policy"]["mode"])
        self.assertNotIn("period_registrant", chosen)

    def test_a_fiscal_year_request_reaches_the_predecessor_on_the_same_terms(self):
        chosen = _select(PARAMOUNT, fiscal_year=2024)
        self.assertEqual(("2024-12-31", PREDECESSOR, 2024),
                         (chosen["target_report_end"], chosen["reporting_cik"],
                          chosen["requested_fiscal_year"]))

    def test_nothing_is_looked_up_at_or_after_the_successor_s_oldest_report(self):
        company = next(row for row in selection._registry_rows(repo_root=ROOT)
                       if row["company_id"] == PARAMOUNT)
        with original_sources_only():
            found = selection._predecessor_period(
                repo_root=ROOT, company=company, report_end="2024-12-31",
                primary_periods=[{"report_date": "2023-12-31"}])
            older = selection._predecessor_period(
                repo_root=ROOT, company=company, report_end="2023-12-31",
                primary_periods=[{"report_date": "2024-12-31"}])
        self.assertIsNone(found)
        self.assertEqual("2023-12-31", older[1][older[2]]["report_date"])

    def test_a_company_with_no_predecessor_is_unchanged(self):
        chosen = _select("marriott_international", report_end="2024-12-31")
        self.assertNotIn("period_registrant", chosen)
        self.assertEqual("CONTINUOUS_PRIMARY", chosen["subject_policy"]["mode"])


class ARecordThatNamesTheWrongRegistrantIsRefusedTest(unittest.TestCase):
    """The prepared input re-derives the record; re-signed JSON cannot move it."""

    def setUp(self):
        self.chosen = _select(PARAMOUNT, report_end="2024-12-31")

    def _prepare(self, record):
        with original_sources_only():
            return prepare_historical_annual_input(repo_root=ROOT, company_id=PARAMOUNT,
                                                   period_selection=record)

    def test_today_s_successor_only_policy_put_back_on_the_year_is_refused(self):
        forged = copy.deepcopy(self.chosen)
        forged["subject_policy"] = forged["period_registrant"]["company_subject_policy"]
        forged["selection_id"] = selection.content_hash(
            value={k: v for k, v in forged.items() if k != "selection_id"})
        with self.assertRaises(NormalAnnualInputError) as raised:
            self._prepare(forged)
        self.assertEqual("ORDINARY_PERIOD_SELECTION_CHANGED", str(raised.exception))

    def test_a_reporting_cik_the_registry_does_not_name_is_refused(self):
        forged = copy.deepcopy(self.chosen)
        forged["reporting_cik"] = "1048286"
        with self.assertRaises(NormalAnnualInputError) as raised:
            self._prepare(forged)
        self.assertIn(str(raised.exception), {"SUBMISSIONS_ENTITY_CONFLICT",
                                              "SAVED_SOURCE_MISSING:https://data.sec.gov/"
                                              "submissions/CIK0001048286.json"})


class ThePinnedInputReadsTheYearsOwnFilingTest(unittest.TestCase):

    def test_fy2024_is_read_from_the_predecessor_s_own_10_k(self):
        chosen = _select(PARAMOUNT, report_end="2024-12-31")
        with original_sources_only():
            prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=PARAMOUNT,
                                                       period_selection=chosen)
        self.assertEqual(PREDECESSOR, prepared["entity"])
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"},
                         prepared["table_input"]["target_period"])
        self.assertEqual("CONTINUOUS_PRIMARY", prepared["subject_policy"]["mode"])
        self.assertEqual(["0001193125-25-096776"],
                         [item["accessionNumber"] for item in prepared["amendments"]])

    def test_an_earlier_year_without_its_original_is_a_named_source_gap(self):
        chosen = _select(PARAMOUNT, report_end="2023-12-31")
        with original_sources_only(), self.assertRaises(NormalAnnualInputError) as raised:
            prepare_historical_annual_input(repo_root=ROOT, company_id=PARAMOUNT,
                                            period_selection=chosen)
        self.assertEqual("SOURCE_UNAVAILABLE", raised.exception.category)
        self.assertIn("/813828/000081382824000007/para-20231231.htm", str(raised.exception))


class EverythingTheReDerivationReadsIsAdmittedTest(unittest.TestCase):
    """An installed data root holds only the prepared input's admitted sources.

    Re-deriving a predecessor period's record reads the primary's catalog first,
    to show the successor filed nothing there. The first batch over these years
    failed on every metric because that catalog was read and not admitted, so
    the installed root could not replay the selection.
    """

    def _read_and_admitted(self, company_id, report_end):
        from vnext import normal_governance_input
        chosen = _select(company_id, report_end=report_end)
        read, real = [], normal_governance_input._Sources.read

        def recording(reader, url, **kwargs):
            read.append(url)
            return real(reader, url, **kwargs)
        with original_sources_only(), patch.object(normal_governance_input._Sources, "read",
                                                   recording):
            selection.restore_period_selection(repo_root=ROOT, company_id=company_id,
                                               target_report_end=report_end)
        with original_sources_only():
            prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=company_id,
                                                       period_selection=chosen)
        return set(read), {proof["source_url"] for proof in prepared["source_proofs"]}

    def test_a_predecessor_period_admits_the_primary_catalog_it_reads(self):
        read, admitted = self._read_and_admitted(PARAMOUNT, "2024-12-31")
        self.assertIn("https://data.sec.gov/submissions/CIK0002041610.json", read)
        self.assertEqual(set(), read - admitted)

    def test_a_primary_period_is_unchanged(self):
        read, admitted = self._read_and_admitted("marriott_international", "2024-12-31")
        self.assertEqual(set(), read - admitted)
        self.assertFalse(any("CIK0002041610" in url for url in admitted))


class AnAmendmentTheClassifierRefusesOnItsMarkupTest(unittest.TestCase):
    """Paramount Global's FY2024 10-K/A says Part III only. The approved classifier
    refuses it on markup - thirteen blocks for a three-paragraph note, and a
    purpose sentence that goes on past 'such Items' - and the whole-note reader
    (historical_amendment_note) proves the approved class, so the event window
    is cleared and the statement values are not, exactly as for the successor's
    Part III amendment."""

    @classmethod
    def setUpClass(cls):
        chosen = _select(PARAMOUNT, report_end="2024-12-31")
        with original_sources_only():
            cls.prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=PARAMOUNT,
                                                           period_selection=chosen)

    def _admit(self, metric_ids):
        with original_sources_only():
            return admission.amendment_admission(repo_root=ROOT, company_id=PARAMOUNT,
                                                 metric_ids=metric_ids, prepared=self.prepared,
                                                 event_metric_ids=("C01", "E01"))

    def test_the_event_window_is_cleared_under_the_approved_class(self):
        record = self._admit(["C01"])
        self.assertTrue(record["admitted"])
        self.assertEqual(["PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS"],
                         [item["classification"] for item in record["amendments"]])

    def test_the_statement_values_are_still_refused_by_the_policy(self):
        with self.assertRaises(admission.AmendmentAdmissionError) as raised:
            self._admit(["B01"])
        self.assertEqual("HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED:ORIGINAL_STATEMENT_VALUES:"
                         "PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS",
                         str(raised.exception))

    def test_an_integrity_conflict_is_not_folded_into_the_refusal(self):
        def conflict(**_):
            raise admission.AmendmentScopeError("AMENDMENT_PERIOD_END_DIFFERS")
        with patch.object(admission, "inspect_annual_amendment_scope", conflict), \
                self.assertRaises(admission.AmendmentScopeError):
            self._admit(["C01"])

    def test_the_successor_s_part_iii_amendment_still_classifies(self):
        chosen = _select(PARAMOUNT, report_end="2025-12-31")
        with original_sources_only():
            prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=PARAMOUNT,
                                                       period_selection=chosen)
            record = admission.amendment_admission(
                repo_root=ROOT, company_id=PARAMOUNT, metric_ids=["C01"], prepared=prepared,
                event_metric_ids=("C01",))
        self.assertEqual(["PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS"],
                         [item["classification"] for item in record["amendments"]])

    def test_b06_withholds_the_input_instead_of_raising(self):
        with original_sources_only():
            packet = debt.prepare_historical_current_debt_input(
                repo_root=ROOT, company_id=PARAMOUNT,
                packet=debt.historical_amendment_scopes(
                    repo_root=ROOT, company_id=PARAMOUNT,
                    prepared=self.prepared["original_input"]))
        self.assertEqual("WITHHELD", packet["decision"])
        self.assertEqual(["AMENDMENT_SCOPE_UNRESOLVED:AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED"],
                         [issue["reason"] for check in packet["checks"]
                          for issue in check["issues"]])


class AnApprovedRefusalIsAWithheldResultOnEveryRouteTest(unittest.TestCase):
    """The same refusal, in the same year, reads the same way on every route.

    The Company Facts route carries an approved policy refusal as the metric's
    withheld result; the zero-AI route used to fail the attempt instead, so
    FY2024 had withheld public rows for B04 and no row at all for B01 or C01
    for the same refusal. Both routes are asked here for one year.
    """

    @classmethod
    def setUpClass(cls):
        from vnext.historical_results import resolve_historical_companyfacts_metrics
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        chosen = _select(PARAMOUNT, report_end="2024-12-31")
        with original_sources_only():
            cls.zero_ai = {metric: resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id=PARAMOUNT, metric_id=metric,
                period_selection=chosen) for metric in ("B01", "C01")}
            cls.facts = resolve_historical_companyfacts_metrics(
                repo_root=ROOT, company_id=PARAMOUNT, period_selection=chosen)

    def test_the_zero_ai_route_withholds_with_the_policy_s_reason(self):
        component = self.zero_ai["B01"]
        self.assertEqual(("WITHHELD", "HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED"),
                         (component["result"]["publication"], component["result"]["reason_code"]))
        selection = component["input_binding"]["selection"]
        self.assertEqual("APPROVED_AMENDMENT_POLICY_REFUSAL", selection["category"])
        self.assertEqual("HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED:ORIGINAL_STATEMENT_VALUES:"
                         "PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS",
                         selection["amendment_policy_decision"])

    def test_the_event_route_the_policy_clears_is_answered(self):
        # The same amendment clears the event window: C01 is counted, not refused.
        event = self.zero_ai["C01"]
        self.assertEqual(("PUBLISHED", "PASS"),
                         (event["result"]["publication"], event["result"]["reason_code"]))

    def test_nothing_the_refusal_forbids_is_read_for_a_value(self):
        statement = self.zero_ai["B01"]
        self.assertEqual([], statement["input_binding"]["source_set_manifests"])
        self.assertIsNone(statement["result"]["value"])

    def test_a_withheld_result_arrives_with_its_dependency_s_result(self):
        """The Run needs B03 with B01; a B03 withheld before B01 was computed
        failed the attempt on an incomplete dependency set."""
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        chosen = _select(PARAMOUNT, report_end="2024-12-31")
        with original_sources_only():
            ratio = resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=PARAMOUNT,
                                                      metric_id="B03", period_selection=chosen)
        results = {record["metric_id"]: record for record in ratio["records"]
                   if record["record_type"] == "METRIC_RESULT"}
        self.assertEqual({"B01", "B03"}, set(results))
        self.assertEqual({("WITHHELD", "HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED")},
                         {(r["publication"], r["reason_code"]) for r in results.values()})

    def test_the_two_routes_carry_the_refusal_the_same_way(self):
        statement = self.facts["metrics"]["B04"]
        zero_ai = self.zero_ai["B01"]
        self.assertEqual(statement["result"]["reason_code"], zero_ai["result"]["reason_code"])
        self.assertEqual(statement["selection"]["category"],
                         zero_ai["input_binding"]["selection"]["category"])
        self.assertEqual(statement["selection"]["amendment_policy_decision"],
                         zero_ai["input_binding"]["selection"]["amendment_policy_decision"])


if __name__ == "__main__":
    unittest.main()
