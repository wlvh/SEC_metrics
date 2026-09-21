"""A pinned annual period's governance filings, selected by the period.

The load-bearing case asks both selectors the same question about the same
period. The frozen one decides which annual report is current by taking the
maximum report date across the loaded rows, so it answers only for the newest
year; a successor that merely returned something would pass every other case
here and fail that one.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.historical_governance_input import (HistoricalGovernanceError,
                                               select_historical_governance_metadata)
from vnext.normal_annual_input import _registry_rows
from vnext.normal_governance_input import select_governance_metadata
from vnext.normal_history_catalog import load_history_for_period
from vnext.normal_period_selection import resolve_period_selection

def _inventories(history):
    """The frozen selector's inventory shape, from the blocks that were read."""
    from vnext.canonical import strict_json_loads
    payloads = {history["inventory"]["source_reference"]["document_name"]:
                strict_json_loads(text=history["inventory"]["raw_bytes"].decode("utf-8"))}
    return [{"name": name, "payload": payloads[name]}
            for name in history["loaded_inventories"] if name in payloads]


MARRIOTT = "marriott_international"
LATEST = "2025-12-31"
EARLIER = "2023-12-31"


def _period(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=company_id,
                                                   period_selection=selection)
        history = load_history_for_period(repo_root=ROOT, company_id=company_id,
                                          report_end=report_end)
    return prepared, history


class HistoricalGovernanceSelectionTest(unittest.TestCase):
    def test_an_earlier_year_is_selected_by_its_own_period_not_by_the_maximum(self):
        """Both selectors, same period and same blocks, so the difference shows.

        The first version of this case handed the frozen selector an empty
        inventory list. It raised, the case passed, and what it had shown was
        that an empty list crashes - not that the maximum is the wrong rule.
        The blocks are real here and the refusal has to be the specific one.
        """
        company = next(row for row in _registry_rows(repo_root=ROOT)
                       if row["company_id"] == MARRIOTT)
        prepared, history = _period(MARRIOTT, EARLIER)
        inventories = _inventories(history)
        self.assertTrue(inventories, "the case needs the blocks that were read")
        with self.assertRaises(Exception) as refused:
            select_governance_metadata(company=company, prepared_input=prepared,
                                       inventories=inventories)
        self.assertEqual("GOVERNANCE_CURRENT_ORDINARY_MISSING_OR_CHANGED",
                         str(refused.exception))
        # And it is the maximum that refuses, not the blocks: the same blocks
        # answer for the newest period.
        newest, newest_history = _period(MARRIOTT, LATEST)
        self.assertEqual(LATEST,
                         select_governance_metadata(
                             company=company, prepared_input=newest,
                             inventories=_inventories(newest_history))["ordinary"]["reportDate"])
        chosen = select_historical_governance_metadata(prepared=prepared, history=history)
        self.assertEqual(EARLIER, chosen["ordinary"]["reportDate"])
        self.assertEqual(prepared["filing"]["accessionNumber"],
                         chosen["ordinary"]["accessionNumber"])
        self.assertEqual("PINNED_PERIOD_END_EQUALITY", chosen["selected_by"]["annual"])

    def test_the_prior_year_is_the_one_before_the_pinned_period(self):
        """Not the one before the newest, which is what a max would give."""
        prepared, history = _period(MARRIOTT, EARLIER)
        chosen = select_historical_governance_metadata(prepared=prepared, history=history)
        self.assertEqual("SAME_CIK_PRIOR_DISCOVERED", chosen["prior_status"])
        prior_end = chosen["prior_ordinary"]["reportDate"]
        self.assertLess(prior_end, EARLIER)
        # And nothing between them: the prior is the greatest end before the
        # pinned one, so no annual report sits in the gap.
        between = [row for row in history["all_rows"] if row["form"] == "10-K"
                   and prior_end < row["reportDate"] < EARLIER]
        self.assertEqual([], between)

    def test_the_latest_year_still_selects_the_same_filing_as_before(self):
        """The successor must not answer a different question for the newest year."""
        company = next(row for row in _registry_rows(repo_root=ROOT)
                       if row["company_id"] == MARRIOTT)
        prepared, history = _period(MARRIOTT, LATEST)
        chosen = select_historical_governance_metadata(prepared=prepared, history=history)
        self.assertEqual(LATEST, chosen["ordinary"]["reportDate"])
        self.assertEqual(prepared["filing"]["accessionNumber"],
                         chosen["ordinary"]["accessionNumber"])
        del company

    def test_the_event_window_is_the_pinned_period_not_the_latest_one(self):
        earlier, history = _period(MARRIOTT, EARLIER)
        chosen = select_historical_governance_metadata(prepared=earlier, history=history)
        period = earlier["table_input"]["target_period"]
        for row in chosen["events"]:
            self.assertLessEqual(period["period_start"], row["filingDate"])
            self.assertLessEqual(row["filingDate"], period["period_end"])
        self.assertEqual("FILING_DATE_INSIDE_THE_PINNED_PERIOD",
                         chosen["selected_by"]["events"])

    def test_a_row_that_only_shares_a_report_date_cannot_stand_in(self):
        """The selection has to be the filing the period selection pinned."""
        prepared, history = _period(MARRIOTT, EARLIER)
        impostor = {**prepared, "filing": {**prepared["filing"],
                                           "accessionNumber": "0000000000-00-000000"}}
        with self.assertRaises(HistoricalGovernanceError) as refused:
            select_historical_governance_metadata(prepared=impostor, history=history)
        self.assertEqual("HISTORICAL_GOVERNANCE_PINNED_ANNUAL_DIVERGED",
                         str(refused.exception))

    def test_a_period_with_no_annual_row_in_the_loaded_blocks_is_refused(self):
        prepared, history = _period(MARRIOTT, EARLIER)
        emptied = {**history, "all_rows": [row for row in history["all_rows"]
                                           if row["form"] != "10-K"]}
        with self.assertRaises(HistoricalGovernanceError) as refused:
            select_historical_governance_metadata(prepared=prepared, history=emptied)
        self.assertTrue(str(refused.exception).startswith(
            "HISTORICAL_GOVERNANCE_PINNED_ANNUAL_NOT_UNIQUE:"))


if __name__ == "__main__":
    unittest.main()
