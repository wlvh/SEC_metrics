"""D02's route leaves an Item 8 category mention out, records it, and moves nothing else.

The rule itself is held to the readings in test_d02_item_8_category_mentions;
these cases hold the route to it on the saved latest-year filings: the blocks
the readers judged category mentions leave the excerpt set and are recorded
under ``item_8_category_mentions_left_out``, the disclosures beside them stay
(including Paramount's block 2108, whose last sentence reports a stockholder
litigation benefit), the review pool's keyword part is still the proposal's
Item 8 excerpts, D03's candidates are what they were, and a filing the rule
leaves alone keeps its proposal byte for byte. Zero calls.
"""
import copy
import unittest

from tests.vnext.test_historical_text_boundary import (LUMEN, MARRIOTT, PARAMOUNT, PFIZER,
                                                        _frozen_document, _text_arguments)
from tests.vnext.test_historical_text_boundary import setUpModule as _boundary_setup
from tests.vnext.test_historical_text_boundary import tearDownModule as _boundary_teardown
from vnext import historical_text_results as route

ITEM_8_SCOPES = {"ITEM_8", "ITEM_8_STATEMENTS_PRINTED_AFTER_THE_ITEMS"}
# Block indices the latest-year census judged (d02-content-read/keyword-proxy-decision.json,
# with its recorded correction of 2108).
LEFT_OUT = {LUMEN: {1670}, PARAMOUNT: {2257}, PFIZER: {2175, 2240}}
KEPT = {LUMEN: {3382, 3383}, PARAMOUNT: {1900, 2108}, PFIZER: {2302, 2351}}


def setUpModule():
    _boundary_setup()


def tearDownModule():
    _boundary_teardown()


def _proposal(company_id, *, rule=True):
    _, prepared = _text_arguments(company_id, "2025-12-31")
    document = _frozen_document(prepared, company_id)
    arguments = prepared["text_arguments"]
    raw = arguments["raw_bytes_by_id"][arguments["source_references"][0]["raw_asset_id"]]
    narrowed = route.narrow_document_sections(document=document)
    if rule:
        return route.referenced_note_candidates(document=narrowed, raw_bytes=raw), narrowed, raw
    original = route.left_out_as_category_mention
    route.left_out_as_category_mention = lambda **_: False
    try:
        return route.referenced_note_candidates(document=narrowed, raw_bytes=raw), narrowed, raw
    finally:
        route.left_out_as_category_mention = original


def _item_8(proposal):
    return {c["block_index"] for c in proposal["D02"]["candidates"]
            if c["section_id"] in ITEM_8_SCOPES}


class TheRouteLeavesCategoryMentionsOutTest(unittest.TestCase):

    def test_the_judged_category_mentions_leave_and_are_recorded(self):
        for company_id, expected in LEFT_OUT.items():
            with self.subTest(company_id):
                proposal, _, _ = _proposal(company_id)
                self.assertEqual(set(), expected & _item_8(proposal))
                recorded = proposal["item_8_category_mentions_left_out"]
                self.assertEqual(expected, {row["block_index"] for row in recorded["blocks"]})
                self.assertEqual("d02_item_8_category_mentions", recorded["rule"])

    def test_the_disclosures_beside_them_stay(self):
        for company_id, expected in KEPT.items():
            with self.subTest(company_id):
                proposal, _, _ = _proposal(company_id)
                self.assertEqual(expected, expected & _item_8(proposal))

    def test_only_the_left_out_blocks_move(self):
        for company_id in LEFT_OUT:
            with self.subTest(company_id):
                with_rule, _, _ = _proposal(company_id)
                without, _, _ = _proposal(company_id, rule=False)
                self.assertEqual(LEFT_OUT[company_id], _item_8(without) - _item_8(with_rule))
                self.assertEqual(set(), _item_8(with_rule) - _item_8(without))
                self.assertEqual(without["D03"], with_rule["D03"])

    def test_the_review_pool_s_keyword_part_is_the_proposal_s_item_8(self):
        for company_id in LEFT_OUT:
            with self.subTest(company_id):
                proposal, document, raw = _proposal(company_id)
                pool, keyword = route.item_8_review_pool(document=document, raw_bytes=raw,
                                                         proposal=proposal)
                self.assertEqual(sorted(c["block_index"] for c in proposal["D02"]["candidates"]
                                        if c["section_id"] == "ITEM_8"), keyword)
                self.assertTrue(LEFT_OUT[company_id] <= set(pool))

    def test_a_filing_the_rule_leaves_alone_keeps_its_proposal(self):
        with_rule, _, _ = _proposal(MARRIOTT)
        without, _, _ = _proposal(MARRIOTT, rule=False)
        self.assertNotIn("item_8_category_mentions_left_out", with_rule)
        self.assertEqual(without, with_rule)


if __name__ == "__main__":
    unittest.main()
