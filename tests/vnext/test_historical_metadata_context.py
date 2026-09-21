"""An earlier period is read from the blocks that hold it, or refused by name.

Every case here runs on this repository's own saved submissions bytes. No
block is written, moved or re-labelled: what changes is which of them the
pinned period is allowed to look in.

The frozen view is called alongside the successor in the cases where the
difference is the point, because "the new one accepts it" only means something
next to "the old one refused it, here, for this reason".
"""
import copy
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from sec_urls import submissions_url
from vnext.historical_metadata_context import (HistoricalMetadataError,
                                               check_historical_metadata_scope,
                                               historical_metadata_context)
from vnext.normal_governance_input import _Sources
from vnext.normal_history_catalog import load_annual_history
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_text_input_v2 import _current_metadata_context

# Measured from the saved indexes: the 10-K row for these periods is in a
# history shard, not in filings.recent, so no recent-only scan can find it.
IN_A_SHARD = (("salesforce", "2023-01-31"), ("salesforce", "2022-01-31"),
              ("pfizer", "2019-12-31"))
# The current block holds these, so both views must agree on them.
IN_THE_RECENT_BLOCK = (("marriott_international", "2023-12-31"),
                       ("macys", "2026-01-31"))
FROZEN_REFUSAL = "TEXT_INPUT_CURRENT_METADATA_SCOPE_REQUIRES_HISTORY"
_IDENTITY = ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")


def _from_catalog(company_id, report_end):
    """A pinned-period input built from the saved metadata's own annual row.

    The periods whose row is in a shard have no saved primary document, so
    prepare_historical_annual_input refuses before the metadata view is
    reached. That refusal is a material gap and this module is not it, so the
    fields this function reads - the entity, the pinned period and the filing
    the selection means - are taken from the saved submissions rows directly.
    Nothing here is invented: every value is a column of a real SEC row.
    """
    with original_sources_only():
        catalog = load_annual_history(repo_root=ROOT, company_id=company_id,
                                      required_annual_count=8)
        rows = [row for row in catalog["annual_rows"]
                if row["form"] == "10-K" and row["reportDate"] == report_end]
        assert len(rows) == 1, (company_id, report_end, len(rows))
        cik = catalog["primary_cik"]
        prepared = {"company_id": company_id, "entity": cik,
                    "filing": {key: rows[0][key] for key in _IDENTITY},
                    "table_input": {"target_period": {"period_start": None,
                                                      "period_end": report_end}}}
        reader = _Sources(ROOT, company_id, cik)
        inventory = reader.read(submissions_url(cik=int(cik)),
                                role="sec_submissions_inventory",
                                media_type="application/json")
    return prepared, inventory, reader, catalog


def _context(company_id, report_end, *, prepared=None):
    built, inventory, reader, _ = _from_catalog(company_id, report_end)
    with original_sources_only():
        return historical_metadata_context(repo_root=ROOT, company_id=company_id,
                                           prepared=prepared or built,
                                           inventory=inventory, reader=reader,
                                           metric_id="D02")


class PinnedPeriodsReadTheBlocksThatHoldThemTest(unittest.TestCase):
    def test_the_frozen_view_refuses_every_period_a_declared_shard_reaches(self):
        """Not a material gap: this refusal is about where it is allowed to look."""
        for company_id, report_end in IN_A_SHARD:
            with self.subTest(company=company_id, period=report_end):
                prepared, inventory, _, _ = _from_catalog(company_id, report_end)
                with original_sources_only():
                    with self.assertRaises(ValueError) as refused:
                        _current_metadata_context(prepared=prepared, inventory=inventory,
                                                  metric_id="D02")
                self.assertEqual(FROZEN_REFUSAL, str(refused.exception))

    def test_the_pinned_period_resolves_from_the_shard_that_holds_it(self):
        for company_id, report_end in IN_A_SHARD:
            with self.subTest(company=company_id, period=report_end):
                prepared, _, _, _ = _from_catalog(company_id, report_end)
                context = _context(company_id, report_end)
                selected = context["selection"]["ordinary"]
                origin = selected["metadata_origin"]["inventory_name"]
                # The row came from a shard, and the shard is one of the blocks
                # this input read and admitted.
                self.assertNotEqual(context["loaded_inventories"][0], origin)
                self.assertIn(origin, context["loaded_inventories"])
                self.assertEqual(report_end, selected["reportDate"])
                for key in _IDENTITY:
                    self.assertEqual(prepared["filing"][key], selected[key])

    def test_the_recent_block_path_answers_exactly_as_before(self):
        """The change is what an earlier period may read, not what a current one does."""
        for company_id, report_end in IN_THE_RECENT_BLOCK:
            with self.subTest(company=company_id, period=report_end):
                prepared, inventory, _, _ = _from_catalog(company_id, report_end)
                with original_sources_only():
                    frozen = _current_metadata_context(prepared=prepared, inventory=inventory,
                                                       metric_id="D02")
                context = _context(company_id, report_end)
                self.assertEqual(frozen["selection"]["ordinary"],
                                 context["selection"]["ordinary"])
                self.assertEqual(frozen["selection"]["amendments"],
                                 context["selection"]["amendments"])
                self.assertEqual([context["loaded_inventories"][0]],
                                 context["loaded_inventories"])

    def test_a_block_the_period_needs_and_cannot_read_is_named_not_skipped(self):
        """JPMorgan is the case: the blocks exist and this repository lacks them.

        Fifty-six declared shards are not saved and eleven of the saved ones do
        not agree with their declared ranges. Reading more blocks does not make
        that go away, and reporting it as "no filing" would turn a source gap
        into a disclosure claim.
        """
        with self.assertRaises(HistoricalMetadataError) as refused:
            _context("jpmorgan_chase", "2024-12-31")
        self.assertTrue(str(refused.exception).startswith(
            "HISTORICAL_TEXT_METADATA_BLOCK_UNUSABLE:"), str(refused.exception))
        self.assertIn("HISTORY_SHARD_NOT_SAVED", str(refused.exception))
        self.assertEqual("SOURCE_UNAVAILABLE", refused.exception.category)

    def test_a_selection_the_blocks_do_not_confirm_is_refused(self):
        """Reading more blocks must not make it easier to accept a wrong filing."""
        company_id, report_end = IN_A_SHARD[0]
        prepared, _, _, _ = _from_catalog(company_id, report_end)
        for key, value in (("accessionNumber", "0000000000-00-000000"),
                           ("primaryDocument", "not-the-document.htm"),
                           ("filingDate", "1999-01-01")):
            with self.subTest(changed=key):
                altered = copy.deepcopy(prepared)
                altered["filing"][key] = value
                with self.assertRaises(HistoricalMetadataError) as refused:
                    _context(company_id, report_end, prepared=altered)
                self.assertEqual("HISTORICAL_TEXT_METADATA_ANNUAL_SELECTION_CHANGED",
                                 str(refused.exception))

    def test_a_period_no_block_reports_is_not_answered_with_another_year(self):
        company_id, report_end = IN_A_SHARD[0]
        prepared, _, _, _ = _from_catalog(company_id, report_end)
        altered = copy.deepcopy(prepared)
        altered["table_input"]["target_period"]["period_end"] = "2020-06-30"
        with self.assertRaises(HistoricalMetadataError) as refused:
            _context(company_id, report_end, prepared=altered)
        self.assertEqual("HISTORICAL_TEXT_METADATA_ANNUAL_NOT_UNIQUE",
                         str(refused.exception))

    def test_only_the_metric_whose_roles_are_resolved_is_served(self):
        """C02 needs the proxy roles, which this does not resolve."""
        prepared, inventory, reader, _ = _from_catalog(*IN_THE_RECENT_BLOCK[0])
        with original_sources_only():
            with self.assertRaises(HistoricalMetadataError) as refused:
                historical_metadata_context(repo_root=ROOT,
                                            company_id=IN_THE_RECENT_BLOCK[0][0],
                                            prepared=prepared, inventory=inventory,
                                            reader=reader, metric_id="C02")
        self.assertEqual("HISTORICAL_TEXT_METADATA_METRIC_NOT_WIRED:C02",
                         str(refused.exception))
        self.assertEqual("IMPLEMENTATION_GAP", refused.exception.category)


class AdmittedBlocksAreTheBlocksThatWereReadTest(unittest.TestCase):
    """What replaces "the filing must be in the current block".

    The frozen check is what made an earlier period unreachable, so its
    replacement has to be shown not to be weaker: a block that was read has to
    be a block that was proved, and the selected filing has to come from one.
    """
    @classmethod
    def setUpClass(cls):
        cls.company_id, cls.report_end = IN_A_SHARD[0]
        cls.context = _context(cls.company_id, cls.report_end)
        cls.plan = {"text_filings": [cls.context["selection"]["ordinary"]]}
        cls.references = [{"record_type": "SOURCE_REFERENCE", "source_role": role,
                           "document_name": name}
                          for name, role in zip(cls.context["loaded_inventories"],
                                                ("sec_submissions_inventory",
                                                 "sec_submissions_history"))]

    def test_the_blocks_read_and_the_blocks_admitted_are_the_same_set(self):
        check_historical_metadata_scope(plan=self.plan, context=self.context,
                                        references=self.references)

    def test_a_block_that_was_read_without_being_admitted_is_refused(self):
        for dropped in range(len(self.references)):
            with self.subTest(without=self.references[dropped]["document_name"]):
                kept = [r for i, r in enumerate(self.references) if i != dropped]
                with self.assertRaises(HistoricalMetadataError) as refused:
                    check_historical_metadata_scope(plan=self.plan, context=self.context,
                                                    references=kept)
                self.assertTrue(str(refused.exception).startswith(
                    "HISTORICAL_TEXT_METADATA_BLOCK_NOT_ADMITTED:"))

    def test_a_block_that_was_admitted_without_being_read_is_refused(self):
        extra = [*self.references,
                 {"record_type": "SOURCE_REFERENCE", "source_role": "sec_submissions_history",
                  "document_name": "CIK0001108524-submissions-004.json"}]
        with self.assertRaises(HistoricalMetadataError) as refused:
            check_historical_metadata_scope(plan=self.plan, context=self.context,
                                            references=extra)
        self.assertIn("CIK0001108524-submissions-004.json", str(refused.exception))

    def test_a_filing_from_no_read_block_is_refused(self):
        filing = {**self.context["selection"]["ordinary"],
                  "metadata_origin": {"inventory_name": "CIK0001108524-submissions-009.json",
                                      "row_index": 0}}
        with self.assertRaises(HistoricalMetadataError) as refused:
            check_historical_metadata_scope(plan={"text_filings": [filing]},
                                            context=self.context,
                                            references=self.references)
        self.assertEqual("HISTORICAL_TEXT_SELECTED_FILING_OUTSIDE_READ_METADATA",
                         str(refused.exception))
        self.assertEqual("SOURCE_COVERAGE_CONFLICT", refused.exception.category)


class TheSelectedFilingStillComesFromThePeriodSelectionTest(unittest.TestCase):
    def test_the_selection_and_the_metadata_view_name_the_same_filing(self):
        """Two independent readers of the same saved metadata must agree."""
        for company_id, report_end in IN_A_SHARD + IN_THE_RECENT_BLOCK:
            with self.subTest(company=company_id, period=report_end):
                with original_sources_only():
                    selection = resolve_period_selection(repo_root=ROOT,
                                                         company_id=company_id,
                                                         report_end=report_end)
                context = _context(company_id, report_end)
                for key in _IDENTITY:
                    self.assertEqual(selection["current_filing"][key],
                                     context["selection"]["ordinary"][key])


if __name__ == "__main__":
    unittest.main()
