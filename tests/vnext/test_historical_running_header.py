"""D01: a running header naming two parts is page furniture, not a heading.

JPMorgan prints a running header at the top of each page of its annual report:
``Part I`` on Item 1A's pages and ``Parts I and II`` on the page where Part I
ends. In four of its five saved reports (FY2021, FY2023-FY2025) that page also
closes Item 1A, so the header falls inside Item 1A, bold and standing alone.
The frozen selector skips a one-part label and took the two-part one as the
last heading. The historical D01 chain runs a successor of the selector with
that one form added (``historical_risk_results.SEVERAL_PARTS``).

The real cases rebuild JPMorgan's documents from the records the 50-period
batch's Runs carried (``running-header/source-records.json``) and the saved
bytes (checkout or export), and run both selectors on the same document: they
differ by that one line where the page closes Item 1A, and not at all in
FY2022, where it does not. The constructed cases hold the form's edges. Zero
calls.
"""
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools.acceptance_readings import saved_bytes
from vnext import historical_risk_results as route
from vnext import risk_signals
from vnext import text_results as frozen
from vnext.canonical import content_hash
from vnext.historical_results import TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.historical_text_results import text_api

RECORDS = "docs/evidence/issue47_history/d01-risk-headings/running-header/source-records.json"
HEADER = "Parts I and II"
_PREPARED = {}


def _spec():
    return compile_historical_spec_file(repo_root=ROOT, repo_relative_path=TEXT_SPEC_PATHS["D01"],
                                        dependency_specs={})


def _arguments(label):
    filing = json.loads((ROOT / RECORDS).read_text(encoding="utf-8"))["filings"][label]
    blob, reference = filing["raw_blob"], filing["source_reference"]
    return dict(compiled_spec=_spec(), target=filing["calculation_target"],
                source_references=[reference], raw_blobs={blob["raw_asset_id"]: blob},
                raw_bytes_by_id={blob["raw_asset_id"]: saved_bytes(
                    repo_root=ROOT, relative=blob["storage_uri"])})


def _prepared(label):
    """The arguments and the document built once, by the D01 chain as it stands."""
    if label not in _PREPARED:
        arguments = _arguments(label)
        documents, coverages = route.prepare_text_sources(**arguments)
        _PREPARED[label] = (arguments, dict(
            compiled_spec=arguments["compiled_spec"], target=arguments["target"],
            source_references=arguments["source_references"],
            documents=documents, coverages=coverages))
    return _PREPARED[label]


def _lines(candidate):
    return [claim["text"] for claim in sorted(candidate["selected"].values(),
                                              key=lambda claim: claim["order"])]


def _document(texts):
    """A located Item 1A whose every block is heading-marked with these texts."""
    blocks = [{"block_index": index, "linked": False,
               "leading_emphasis": {"text": text, "raw_start_byte": 100 * index,
                                    "raw_end_byte": 100 * index + len(text),
                                    "raw_span_sha256": "0" * 64}}
              for index, text in enumerate(texts)]
    body = {"company_id": "example", "period_end": "2025-12-31",
            "source_reference_id": "source", "raw_asset_id": "raw", "source_reasons": [],
            "registrant_names": ["Example Corp"], "blocks": blocks,
            "sections": {"ITEM_1A": {"status": "LOCATED", "candidates": [
                {"start_block": 0, "end_block_exclusive": len(blocks)}]}}}
    return {**body, "text_document_id": content_hash(value=body)}


def _taken(selector, texts):
    return [heading["text"] for heading in selector(document=_document(texts))["headings"]]


class TheFormIsTheLabelAloneTest(unittest.TestCase):
    """Constructed: what the added form takes out, and what it leaves."""

    def test_the_two_part_label_goes_where_the_one_part_label_went(self):
        texts = ["Risk Factors Summary", "Part I", "Competition could hurt our results.",
                 HEADER]
        self.assertEqual(["Risk Factors Summary", "Competition could hurt our results.", HEADER],
                         _taken(risk_signals.risk_factor_headings, texts))
        self.assertEqual(["Risk Factors Summary", "Competition could hurt our results."],
                         _taken(route.risk_factor_headings, texts))

    def test_a_heading_that_begins_with_a_part_label_is_still_a_heading(self):
        """The label must be the whole text, as the frozen one-part form requires."""
        texts = ["Parts I and II of our network depend on a single supplier.",
                 "Parts shortages could disrupt our production."]
        self.assertEqual(texts, _taken(route.risk_factor_headings, texts))

    def test_the_successors_carry_exactly_their_listed_substitutions(self):
        """Each is the frozen function's own source with these and nothing else."""
        self.assertEqual(route.SEVERAL_PARTS,
                         route.risk_factor_headings.historical_substitutions)
        self.assertEqual(route.SELECTOR_IMPORT, route._derive_candidate.historical_substitutions)


class OnJPMorgansReportsTest(unittest.TestCase):
    """The same document, both selectors: one line apart, or none."""

    def test_where_the_page_closes_item_1a_the_header_is_the_one_line_dropped(self):
        for label in ("jpmorgan-2021", "jpmorgan-2025"):
            with self.subTest(label):
                _, shared = _prepared(label)
                before = _lines(frozen._derive_deterministic_candidate(**shared))
                after = _lines(route._derive_candidate(**shared))
                self.assertEqual(HEADER, before[-1])
                self.assertEqual(before[:-1], after)

    def test_where_it_does_not_nothing_moves(self):
        _, shared = _prepared("jpmorgan-2022")
        self.assertEqual(frozen._derive_deterministic_candidate(**shared),
                         route._derive_candidate(**shared))

    def test_the_route_delivers_the_successor_s_candidate_and_replays_it(self):
        """Both call sites: D01's API builds it, and its Evidence replays it.

        A chain that left either site on the frozen derivation would deliver
        the header again or refuse its own candidate on replay.
        """
        arguments, shared = _prepared("jpmorgan-2025")
        api, _ = text_api("D01")
        candidate = api.create_deterministic_text_candidate(**arguments)
        self.assertEqual(route._derive_candidate(**shared), candidate)
        self.assertNotIn(HEADER, _lines(candidate))
        evidence = api.build_text_evidence(candidate=candidate, **arguments)
        self.assertEqual("PASS", evidence["status"])


if __name__ == "__main__":
    unittest.main()
