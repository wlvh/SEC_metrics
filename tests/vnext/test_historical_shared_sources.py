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
from vnext.historical_results import TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.text_results_v2 import TextResultV2Error

MACYS = "macys"
MACYS_END = "2026-01-31"


_PREPARED = {}


def _arguments(company_id=MACYS, report_end=MACYS_END):
    """One real input set per coordinate, copied for each caller.

    Preparing it costs about nine seconds and is identical every time, so it
    is prepared once and deep-copied out - the cases below edit what they are
    handed, and one case editing the shared object would decide the next.
    """
    if (company_id, report_end) not in _PREPARED:
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                                 report_end=report_end)
            prepared = prepare_historical_business_text_input(
                repo_root=ROOT, company_id=company_id, metric_id="D02",
                period_selection=selection)
        spec = compile_historical_spec_file(repo_root=ROOT,
                                            repo_relative_path=TEXT_SPEC_PATHS["D02"],
                                            dependency_specs={})
        _PREPARED[(company_id, report_end)] = (spec, prepared["text_arguments"])
    spec, arguments = _PREPARED[(company_id, report_end)]
    return spec, copy.deepcopy(arguments)


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

    def test_an_emptied_original_set_is_refused_warm_exactly_as_it_is_cold(self):
        """The check the hit was returning in front of.

        The key named four of the frozen preparation's five arguments and left
        out ``raw_blobs``, the dict holding the original records. The frozen
        function refuses a request whose declared source is not in it - that is
        TEXT_V2_ORIGINAL_SOURCE_MISSING - but a hit returned before the frozen
        function ran, so once the entry existed the same request with
        ``raw_blobs`` emptied was served from it. Measured: the key was
        unchanged, the existence check the cold path makes was False, and the
        request hit.
        """
        spec, arguments = _arguments()
        emptied = copy.deepcopy(arguments)
        emptied["raw_blobs"] = {}
        with original_sources_only():
            with self.assertRaises(TextResultV2Error) as cold:
                fixed.prepare_business_text_sources(metric_id="D02", **emptied)
            with fixed.shared_source_preparation():
                fixed.prepare_business_text_sources(metric_id="D02", **arguments)
                with self.assertRaises(TextResultV2Error) as warm:
                    fixed.prepare_business_text_sources(metric_id="D02", **emptied)
        self.assertEqual("TEXT_V2_ORIGINAL_SOURCE_MISSING", str(cold.exception))
        self.assertEqual(str(cold.exception), str(warm.exception))

    def test_an_altered_original_record_is_judged_warm_exactly_as_it_is_cold(self):
        """Not only present: the record's own content is what gets checked.

        ``build_text_document`` verifies the blob against the bytes, so a blob
        that declares a different length is refused. Serving that from an
        entry keyed without the blob would return a document the frozen checks
        never accepted.
        """
        spec, arguments = _arguments()
        altered = copy.deepcopy(arguments)
        # The input set carries three blobs and D02 reads the one its single
        # source reference names; editing any other would prove nothing.
        asset_id = altered["source_references"][0]["raw_asset_id"]
        altered["raw_blobs"][asset_id] = {**altered["raw_blobs"][asset_id],
                                          "byte_length": 1}
        with original_sources_only():
            with self.assertRaises(ValueError) as cold:
                fixed.prepare_business_text_sources(metric_id="D02", **altered)
            with fixed.shared_source_preparation():
                fixed.prepare_business_text_sources(metric_id="D02", **arguments)
                with self.assertRaises(ValueError) as warm:
                    fixed.prepare_business_text_sources(metric_id="D02", **altered)
        self.assertEqual(str(cold.exception), str(warm.exception))

    def test_every_argument_the_frozen_preparation_takes_moves_the_key(self):
        """A key built from a hand-kept list is a key with a hole in it.

        This is the general form of the raw_blobs defect: each argument is
        changed in a way the frozen function would treat differently, and the
        key has to move for every one of them.
        """
        spec, arguments = _arguments()
        base = fixed._preparation_key(metric_id="D02", source_arguments=arguments)
        asset_id = next(iter(arguments["raw_bytes_by_id"]))
        reference_id = next(iter(arguments["source_filings"]))
        edits = {
            "target": lambda a: a["target"].__setitem__("period_end", "2025-01-31"),
            "source_references": lambda a: a["source_references"][0].__setitem__(
                "source_role", "governance_proxy"),
            "raw_blobs": lambda a: a["raw_blobs"].clear(),
            "raw_bytes_by_id": lambda a: a["raw_bytes_by_id"].__setitem__(
                asset_id, a["raw_bytes_by_id"][asset_id] + b" "),
            "source_filings": lambda a: a["source_filings"][reference_id].__setitem__(
                "form", "10-K/A"),
        }
        self.assertEqual(fixed.PREPARATION_ARGUMENTS, set(edits))
        self.assertEqual(fixed.PREPARATION_ARGUMENTS, set(arguments))
        for name, edit in edits.items():
            with self.subTest(argument=name):
                altered = copy.deepcopy(arguments)
                edit(altered)
                self.assertNotEqual(base, fixed._preparation_key(
                    metric_id="D02", source_arguments=altered))

    def test_an_argument_set_the_key_does_not_cover_is_refused(self):
        """The next argument added to the frozen signature stops this, loudly."""
        spec, arguments = _arguments()
        for changed in ({**arguments, "extra": 1},
                        {name: value for name, value in arguments.items()
                         if name != "raw_blobs"}):
            with self.subTest(arguments=sorted(changed)):
                with self.assertRaises(TextResultV2Error) as refused:
                    fixed._preparation_key(metric_id="D02", source_arguments=changed)
                self.assertTrue(str(refused.exception).startswith(
                    "HISTORICAL_TEXT_SHARED_KEY_ARGUMENTS_CHANGED:"))

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
