"""The owner's per-filing admission of two Part III amendments, on real bytes.

The approved policy clears a Part III addition's event window and not its
statement values. The owner decided, on a filing-by-filing review, that the
two amendments listed in ``config/issue47_part_iii_statement_admission_v1.json``
clear statement values for their own periods and the metrics the review
measured. These cases hold the admission to what that decision is and is not:
it is asked only of listed amendments, only for statement values, and only
while every condition still holds on the saved bytes; anything else keeps the
policy's answer, and a failure names the condition.
"""
from pathlib import Path
from unittest.mock import patch
import copy
import json
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import historical_part_iii_admission as ADMISSION
from vnext.historical_amendment_admission import (AmendmentAdmissionError,
                                                  amendment_admission,
                                                  per_filing_admissions)
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_period_selection import resolve_period_selection

from contextlib import ExitStack  # noqa: E402
from vnext.historical_xbrl_parse import xbrl_parsed_once  # noqa: E402

# Each document's inline XBRL is parsed once for the module
# (historical_xbrl_parse): the cases' chains parse the same filings again at
# nearly every stage (122 parses of 4 documents here, measured), and nothing a
# case does can change a parsed document.
_PARSED_ONCE = ExitStack()


def setUpModule():
    _PARSED_ONCE.enter_context(xbrl_parsed_once())


def tearDownModule():
    _PARSED_ONCE.close()


COMPANY = "paramount_skydance_paramount_global"
STATEMENT = ["B02", "B04", "B05", "B07", "B08", "B09"]
_PREPARED = {}


def _prepared(period_end):
    """One period's prepared input, shared: an input here, never what is asserted."""
    if period_end not in _PREPARED:
        selection = resolve_period_selection(repo_root=ROOT, company_id=COMPANY,
                                             report_end=period_end)
        _PREPARED[period_end] = prepare_historical_annual_input(
            repo_root=ROOT, company_id=COMPANY, period_selection=selection)
    return copy.deepcopy(_PREPARED[period_end])


def without_the_owner_s_listing():
    """The approved policy's own answer, as it was before the owner's decision.

    Cases elsewhere that are about the policy - what it clears, how a refusal
    reads on each route - use Paramount's two periods because they are the
    only Part III amendments saved. Since 2026-09-27 the owner's per-filing
    admission lists both, so those cases ask their question without it; this
    module is where the admission itself is tested.
    """
    return patch.object(ADMISSION, "approved_filings", lambda **kwargs: [])


def _listed(change):
    """``approved_filings`` with each entry passed through ``change``."""
    original = ADMISSION.approved_filings

    def patched(**kwargs):
        return [change(copy.deepcopy(entry)) for entry in original(**kwargs)]
    return patch.object(ADMISSION, "approved_filings", patched)


class TheTwoListedAmendmentsAreAdmittedOnTheirOwnBytes(unittest.TestCase):

    def test_both_periods_clear_statement_values_with_every_condition_held(self):
        for period_end in ("2024-12-31", "2025-12-31"):
            with self.subTest(period_end):
                record = amendment_admission(repo_root=ROOT, company_id=COMPANY,
                                             metric_ids=STATEMENT,
                                             prepared=_prepared(period_end))
                self.assertTrue(record["admitted"])
                (item,) = record["amendments"]
                admission = item["per_filing_admission"]
                self.assertTrue(admission["admitted"])
                self.assertEqual({}, {name: held for name, held in
                                      admission["conditions"].items() if not held})
                self.assertEqual(["101", "104", "31"], admission["item_15_exhibits"])
                self.assertEqual(1, len(per_filing_admissions(record)))

    def test_the_event_window_answer_never_consults_the_listing(self):
        # The policy already clears a Part III amendment's event window; the
        # per-filing admission is about statement values and is not asked.
        record = amendment_admission(repo_root=ROOT, company_id=COMPANY, metric_ids=["C01"],
                                     prepared=_prepared("2024-12-31"),
                                     event_metric_ids=["C01", "E01", "E02", "E03", "E04",
                                                       "E05"])
        self.assertTrue(record["admitted"])
        self.assertNotIn("per_filing_admission", record["amendments"][0])
        self.assertEqual([], per_filing_admissions(record))


class AnythingElseKeepsThePolicyAnswerOrNamesTheFailedCondition(unittest.TestCase):

    def _refusal(self, period_end="2024-12-31", metric_ids=STATEMENT):
        with self.assertRaises(AmendmentAdmissionError) as caught:
            amendment_admission(repo_root=ROOT, company_id=COMPANY, metric_ids=metric_ids,
                                prepared=_prepared(period_end))
        return str(caught.exception)

    def test_an_amendment_that_is_not_listed_gets_the_policy_answer(self):
        original = ADMISSION.approved_filings
        with patch.object(ADMISSION, "approved_filings",
                          lambda **kwargs: [entry for entry in original(**kwargs)
                                            if entry["report_end"] != "2024-12-31"]):
            reason = self._refusal()
        self.assertIn("HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED:ORIGINAL_STATEMENT_VALUES",
                      reason)
        self.assertNotIn("PER_FILING_ADMISSION_FAILED", reason,
                         "an unlisted amendment is not a failed admission; it was never asked")

    def test_bytes_other_than_the_reviewed_ones_are_refused_by_name(self):
        def change(entry):
            entry["amendment"]["content_sha256"] = "0" * 64
            return entry
        with _listed(change):
            reason = self._refusal()
        self.assertIn("PER_FILING_ADMISSION_FAILED:AMENDMENT_BYTES_ARE_THE_REVIEWED_ONES",
                      reason)

    def test_a_metric_outside_the_approved_scope_is_refused_by_name(self):
        # B01 was not refused for statement values in the successor's year -
        # it answers through the approved income input - so the listing does
        # not name it, and asking for it through this admission is refused.
        reason = self._refusal(period_end="2025-12-31", metric_ids=["B01"])
        self.assertIn("METRICS_WITHIN_THE_APPROVED_SCOPE", reason)

    def test_an_exhibit_list_other_than_the_reviewed_one_is_refused_by_name(self):
        def change(entry):
            entry["exhibits_allowed"] = ["101", "104"]
            return entry
        with _listed(change):
            reason = self._refusal()
        self.assertIn("ITEM_15_FILES_ONLY_CERTIFICATIONS_AND_INTERACTIVE_DATA", reason)

    def test_a_listing_naming_another_original_is_an_error_not_a_pass(self):
        def change(entry):
            entry["original"]["accession"] = "0000000000-00-000000"
            return entry
        with _listed(change):
            with self.assertRaises(ADMISSION.PartIIIAdmissionError) as caught:
                amendment_admission(repo_root=ROOT, company_id=COMPANY, metric_ids=STATEMENT,
                                    prepared=_prepared("2024-12-31"))
        self.assertIn("PART_III_ADMISSION_LISTING_DOES_NOT_MATCH_THE_FILING",
                      str(caught.exception))

    def test_the_record_itself_must_say_what_it_is(self):
        real = json.loads((ROOT / ADMISSION.CONFIG_PATH).read_text(encoding="utf-8"))
        for field, value, reason in (
                ("input_class", "FISCAL_EVENT_WINDOW", "PART_III_ADMISSION_IS_FOR_ANOTHER_INPUT_CLASS"),
                ("production_authorized", True, "PART_III_ADMISSION_RECORD_INVALID"),
                ("filings", [], "PART_III_ADMISSION_LISTS_NO_FILING")):
            with self.subTest(field), tempfile.TemporaryDirectory() as root:
                path = Path(root) / ADMISSION.CONFIG_PATH
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({**real, field: value}), encoding="utf-8")
                with self.assertRaises(ADMISSION.PartIIIAdmissionError) as caught:
                    ADMISSION.approved_filings(repo_root=Path(root),
                                               input_class="ORIGINAL_STATEMENT_VALUES")
                self.assertIn(reason, str(caught.exception))


class APredecessorYearIsAskedItsOwnContinuity(unittest.TestCase):
    """Admitted statement inputs exposed a second gap, fixed here.

    Once Paramount Global's FY2024 statement inputs were admitted, reported
    net income, free cash flow and interest coverage came back
    ENTITY_CONTINUITY_NOT_COMPARABLE: the frozen graph asks the company's
    registry row, which describes the successor and its predecessor, not the
    predecessor's own single-registrant year. The successor's first year must
    still get the approved non-comparability answer.
    """

    @classmethod
    def setUpClass(cls):
        from vnext.historical_results import resolve_historical_companyfacts_metrics
        cls.years = {}
        for period_end in ("2024-12-31", "2025-12-31"):
            selection = resolve_period_selection(repo_root=ROOT, company_id=COMPANY,
                                                 report_end=period_end)
            cls.years[period_end] = resolve_historical_companyfacts_metrics(
                repo_root=ROOT, company_id=COMPANY, period_selection=selection)["metrics"]

    def test_the_predecessor_year_gets_values_and_says_why(self):
        row = self.years["2024-12-31"]["B04"]
        self.assertEqual(("EXACT", "-6190000000"),
                         (row["result"]["quality"], str(row["result"]["value"])))
        self.assertEqual({"company_registry_status": "successor_predecessor",
                          "period_subject_policy": "CONTINUOUS_PRIMARY",
                          "period_registrant_cik": "813828",
                          "cross_entity_combination_authorized": False},
                         row["selection"]["period_continuity"])
        self.assertEqual("RATIO_NUMERATOR_NOT_POSITIVE",
                         self.years["2024-12-31"]["B07"]["result"]["reason_code"],
                         "a loss year's coverage ratio is not meaningful, and says so")

    def test_the_successor_year_keeps_the_approved_non_comparability(self):
        row = self.years["2025-12-31"]["B04"]
        self.assertEqual("ENTITY_CONTINUITY_NOT_COMPARABLE", row["result"]["reason_code"])
        self.assertNotIn("period_continuity", row["selection"])

    def test_current_instant_metrics_carry_the_admission_and_nothing_else(self):
        for period_end in ("2024-12-31", "2025-12-31"):
            row = self.years[period_end]["B09"]
            self.assertEqual("EXACT", row["result"]["quality"])
            self.assertEqual(["amendment_per_filing_admission"], sorted(row["selection"]))


if __name__ == "__main__":
    unittest.main()
