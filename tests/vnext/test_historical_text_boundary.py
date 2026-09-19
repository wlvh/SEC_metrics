"""A numbered Form 10-K item stops at the form's unnumbered Part I item.

Every expectation here is read out of the filing's own blocks, never produced by
calling the boundary rule under test: the closing block is found by matching the
caption text directly, and the control cases are the frozen derivation's own
output. The corpus supplies both directions - Pfizer files no Item 4 and carries
the unnumbered item inside Item 3, and Macy's and Paramount carry blocks naming
a chief executive officer inside Item 8 that must not close anything.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_text_results as fixed
from vnext import text_results_v2 as frozen
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.specs import compile_spec_file
from vnext.text_coverage import build_text_document

PFIZER = "pfizer"
MACYS = "macys"
CAPTION = "information about our executive officers"


def _text_arguments(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_business_text_input(
            repo_root=ROOT, company_id=company_id, metric_id="D02",
            period_selection=selection)
    spec = compile_spec_file(path=ROOT / "catalog/r6/D02_legal_disclosures_v1.md",
                             dependency_specs={})
    return spec, prepared


def _frozen_document(prepared, company_id):
    arguments = prepared["text_arguments"]
    reference = arguments["source_references"][0]
    return build_text_document(
        raw_bytes=arguments["raw_bytes_by_id"][reference["raw_asset_id"]],
        raw_blob=arguments["raw_blobs"][reference["raw_asset_id"]],
        source_reference=reference, expected_company_id=company_id,
        expected_cik=prepared["prepared_input"]["entity"],
        expected_period_end=prepared["target_period"]["period_end"])


class FormUnnumberedItemBoundaryTest(unittest.TestCase):
    def test_item_three_stops_at_the_caption_block_the_filing_itself_carries(self):
        """The expectation is the caption's own block index, read from the document.

        Pfizer files no Item 4, so `_SUCCESSOR` closes Item 3 at Item 5 and the
        officer section between them is reported as legal proceedings. The
        corrected range must end at the caption, and the block before it - the
        one sentence Item 3 actually holds - must survive.
        """
        spec, prepared = _text_arguments(PFIZER, "2025-12-31")
        document = _frozen_document(prepared, PFIZER)
        blocks = document["blocks"]
        captions = [i for i, block in enumerate(blocks)
                    if block["text"].strip().casefold() == CAPTION and not block["linked"]]
        self.assertEqual(1, len(captions), captions)
        caption = captions[0]
        original = document["sections"]["ITEM_3"]["candidates"]
        self.assertEqual(1, len(original))
        self.assertLess(original[0]["start_block"], caption)
        self.assertLess(caption, original[0]["end_block_exclusive"])

        corrected = fixed.narrow_document_sections(document=document)
        candidates = corrected["sections"]["ITEM_3"]["candidates"]
        self.assertEqual("LOCATED", corrected["sections"]["ITEM_3"]["status"])
        self.assertEqual(1, len(candidates))
        self.assertEqual(original[0]["start_block"], candidates[0]["start_block"])
        self.assertEqual(caption, candidates[0]["end_block_exclusive"])
        self.assertEqual(document["blocks"], corrected["blocks"])
        self.assertEqual(document["text_document_id"], corrected["frozen_text_document_id"])
        self.assertNotEqual(document["text_document_id"], corrected["text_document_id"])

    def test_the_corrected_set_only_loses_blocks_from_inside_the_officer_section(self):
        """Over-capture goes and nothing else moves - asserted as a subset.

        The strong form of "no under-capture" is not a section head count: it is
        that every excerpt the frozen derivation selected outside the officer
        section is still selected, and that every excerpt it loses lies inside
        it. Anything the boundary cost elsewhere fails this.

        What Item 3 itself holds is one sentence pointing at Note 16A, and it is
        a hyperlink under 120 characters, which `_substantive` treats as
        navigation. It is absent from the corrected set and was absent from the
        frozen one too, so this repair neither causes nor fixes that; it is
        recorded in the evidence directory as its own inherited question. The
        note's own text is still reached, through Item 8.
        """
        spec, prepared = _text_arguments(PFIZER, "2025-12-31")
        document = _frozen_document(prepared, PFIZER)
        arguments = {"compiled_spec": spec, **prepared["text_arguments"]}
        with original_sources_only():
            before = frozen.create_deterministic_text_candidate(**arguments)
            after = fixed.create_deterministic_text_candidate(**arguments)
            evidence = fixed.build_text_evidence(candidate=after, **arguments)
        self.assertEqual("PASS", evidence["status"])
        self.assertNotEqual(before["candidate_hash"], after["candidate_hash"])

        captions = [i for i, block in enumerate(document["blocks"])
                    if block["text"].strip().casefold() == CAPTION and not block["linked"]]
        officer_start = captions[0]
        officer_end = document["sections"]["ITEM_3"]["candidates"][0]["end_block_exclusive"]
        kept = {claim["block_index"] for claim in after["selected"].values()}
        had = {claim["block_index"] for claim in before["selected"].values()}
        self.assertTrue(kept < had)
        self.assertEqual(set(), kept & set(range(officer_start, officer_end)))
        self.assertEqual(had - kept, had & set(range(officer_start, officer_end)))

        def officer_rows(candidate):
            return [claim["text"] for claim in candidate["selected"].values()
                    if CAPTION in claim["text"].casefold()]
        self.assertTrue(officer_rows(before))
        self.assertFalse(officer_rows(after))

    def test_a_signature_line_naming_an_officer_does_not_close_an_item(self):
        """Macy's block 774 sits inside Item 8 and names a chief executive officer.

        A rule keyed on the words rather than on the whole caption would cut Item
        8 there. The assertion is that this filing's ranges come back unchanged
        and its whole record set is the frozen module's, byte for byte.
        """
        spec, prepared = _text_arguments(MACYS, "2026-01-31")
        document = _frozen_document(prepared, MACYS)
        officer_blocks = [i for i, block in enumerate(document["blocks"])
                          if "executive officer" in block["text"].casefold()
                          and not block["linked"]
                          and any(c["start_block"] <= i < c["end_block_exclusive"]
                                  for c in document["sections"]["ITEM_8"]["candidates"])]
        self.assertTrue(officer_blocks)
        self.assertIs(document, fixed.narrow_document_sections(document=document))

        arguments = {"compiled_spec": spec, **prepared["text_arguments"]}
        with original_sources_only():
            self.assertEqual(frozen.create_deterministic_text_candidate(**arguments),
                             fixed.create_deterministic_text_candidate(**arguments))

    def test_the_successor_routes_only_the_metric_it_corrects(self):
        module, _ = fixed.text_api("D02")
        self.assertIs(fixed, module)
        parent, _ = fixed.text_api("C02")
        self.assertIs(frozen, parent)


if __name__ == "__main__":
    unittest.main()
