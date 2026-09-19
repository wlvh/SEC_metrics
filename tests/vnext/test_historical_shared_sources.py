"""Reusing a parse inside one execution must not reuse an identity or an object.

The measured duplication is real: counted by (parser, source bytes,
parameters), one D02 position makes ten parse calls over four distinct keys,
because the source set is prepared once to build the candidate and again inside
``build_text_evidence``. The second derivation is the point - it rebuilds the
candidate independently - so the derivation is kept and only the parse of the
same immutable bytes is shared.

These cases check the three ways that could be wrong rather than only that it
is faster: an identity carried across calls, an object shared across callers,
and reuse leaking outside the block that asked for it.
"""
import copy
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_text_results as fixed
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.specs import compile_spec_file
from vnext.text_results_v2 import TextResultV2Error

MACYS = "macys"
MACYS_END = "2026-01-31"


def _arguments(company_id=MACYS, report_end=MACYS_END):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_business_text_input(
            repo_root=ROOT, company_id=company_id, metric_id="D02",
            period_selection=selection)
    spec = compile_spec_file(path=ROOT / "catalog/r6/D02_legal_disclosures_v1.md",
                             dependency_specs={})
    return spec, prepared["text_arguments"]


class SharedSourcePreparationTest(unittest.TestCase):
    def test_the_shared_parse_returns_what_a_fresh_parse_returns(self):
        spec, arguments = _arguments()
        call = {"compiled_spec": spec, **arguments}
        with original_sources_only():
            fresh = fixed.create_deterministic_text_candidate(**call)
            fresh_evidence = fixed.build_text_evidence(candidate=fresh, **call)
            with fixed.shared_source_preparation():
                shared = fixed.create_deterministic_text_candidate(**call)
                shared_evidence = fixed.build_text_evidence(candidate=shared, **call)
        self.assertEqual(fresh, shared)
        self.assertEqual(fresh_evidence, shared_evidence)

    def test_the_same_bytes_claimed_for_another_period_are_still_refused(self):
        """The key carries the target, so a re-labelled claim is a new key.

        A cache keyed on bytes alone would hand the first call's verified
        document to a second call that says those bytes cover a different year.
        """
        spec, arguments = _arguments()
        call = {"compiled_spec": spec, **arguments}
        moved = copy.deepcopy(arguments)
        moved["target"] = {**moved["target"], "period_end": "2025-01-31",
                           "period_start": "2024-02-04"}
        with original_sources_only(), fixed.shared_source_preparation():
            fixed.create_deterministic_text_candidate(**call)
            with self.assertRaises(TextResultV2Error) as refused:
                fixed.create_deterministic_text_candidate(
                    **{"compiled_spec": spec, **moved})
        self.assertNotIn("HISTORICAL_TEXT_BOUNDARY", str(refused.exception))

    def test_the_same_bytes_claimed_for_another_company_are_still_refused(self):
        spec, arguments = _arguments()
        moved = copy.deepcopy(arguments)
        moved["target"] = {**moved["target"], "company_id": "marriott_international"}
        with original_sources_only(), fixed.shared_source_preparation():
            fixed.create_deterministic_text_candidate(**{"compiled_spec": spec, **arguments})
            with self.assertRaises(TextResultV2Error):
                fixed.create_deterministic_text_candidate(**{"compiled_spec": spec, **moved})

    def test_one_caller_editing_what_it_was_handed_does_not_reach_the_next(self):
        spec, arguments = _arguments()
        with original_sources_only(), fixed.shared_source_preparation():
            first = fixed.prepare_business_text_sources(metric_id="D02", **arguments)
            reference_id = next(iter(first["documents"]))
            original_blocks = len(first["documents"][reference_id]["blocks"])
            first["documents"][reference_id]["blocks"].clear()
            first["coverages"][reference_id]["ranges"] = []
            second = fixed.prepare_business_text_sources(metric_id="D02", **arguments)
        self.assertEqual(original_blocks, len(second["documents"][reference_id]["blocks"]))
        self.assertTrue(second["coverages"][reference_id]["ranges"])

    def test_nothing_is_reused_outside_the_block_that_asked_for_it(self):
        spec, arguments = _arguments()
        with original_sources_only():
            with fixed.shared_source_preparation():
                inside = fixed.prepare_business_text_sources(metric_id="D02", **arguments)
            outside = fixed.prepare_business_text_sources(metric_id="D02", **arguments)
        self.assertIsNone(fixed._SHARED_SOURCES.get())
        self.assertEqual(inside["documents"], outside["documents"])
        self.assertIsNot(inside["documents"], outside["documents"])

    def test_a_nested_scope_shares_the_outer_one_rather_than_resetting_it(self):
        """A Run creation opens the scope and the text execution inside opens one too.

        Binding a fresh dict in the inner block hid the outer entries and threw
        its own away on exit. The whole-Run census caught it: the creation
        still made five real preparations where it needed one, and eighty parse
        calls fell only to twenty-five instead of to five.
        """
        spec, arguments = _arguments()
        with original_sources_only(), fixed.shared_source_preparation():
            outer = fixed.prepare_business_text_sources(metric_id="D02", **arguments)
            shared = fixed._SHARED_SOURCES.get()
            self.assertEqual(1, len(shared))
            with fixed.shared_source_preparation():
                self.assertIs(shared, fixed._SHARED_SOURCES.get())
                inner = fixed.prepare_business_text_sources(metric_id="D02", **arguments)
                self.assertEqual(1, len(fixed._SHARED_SOURCES.get()))
            self.assertIs(shared, fixed._SHARED_SOURCES.get())
        self.assertEqual(outer["documents"], inner["documents"])

    def test_the_key_hashes_the_bytes_rather_than_trusting_the_supplied_asset_id(self):
        """A key that trusts a caller-supplied id is a key that can be collided."""
        spec, arguments = _arguments()
        first = fixed._preparation_key(metric_id="D02", source_arguments=arguments)
        altered = copy.deepcopy(arguments)
        asset_id = next(iter(altered["raw_bytes_by_id"]))
        altered["raw_bytes_by_id"][asset_id] = altered["raw_bytes_by_id"][asset_id] + b" "
        self.assertNotEqual(first, fixed._preparation_key(metric_id="D02",
                                                          source_arguments=altered))


if __name__ == "__main__":
    unittest.main()
