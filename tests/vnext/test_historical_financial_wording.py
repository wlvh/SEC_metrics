"""The financial witnesses read older annual reports' wording (Issue #47).

The frozen financial inspectors stop on six differences of wording or layout in
the bank's four earlier annual reports (historical_financial_wording). These
cases hold the successors to what the module says they are: the frozen
function's own source with the listed substitutions and nothing else; forms
that read the older wording and still refuse what the frozen forms refuse; and
an answer taken from them only where the frozen inspector does not resolve and
they do.

The documents here are constructed and small, and say so; the measurement on
the bank's own five annual reports is in
docs/evidence/issue47_history/financial-older-wording/. Zero calls.
"""
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext import financial_balance_scope as frozen_balance  # noqa: E402
from vnext import financial_duration as frozen_duration  # noqa: E402
from vnext import financial_relationships as frozen_relationships  # noqa: E402
from vnext import historical_financial_results as route  # noqa: E402
from vnext import historical_financial_wording as wording  # noqa: E402
from vnext.composite_scope import index_source_structure  # noqa: E402
from vnext.historical_dei import overrides_of  # noqa: E402
from vnext.table_grid import _AllTablesParser  # noqa: E402

_TARGETS = {
    "GLOSSARY_COLON": frozen_balance._aum_definitions,
    "SEGMENT_LIST": frozen_relationships._reported_segment_sections,
    "MARKETS_NAME": frozen_relationships.inspect_nim_relationships,
    "GENERAL_NOTE": frozen_duration._linked_notes,
    "MEASURE_ABBREVIATION": frozen_duration.inspect_financial_duration,
    "COUNTERFACTUAL_HEADER": frozen_balance.inspect_total_var,
    "TABLE_OF_CONTENTS": frozen_relationships.inspect_nonaccrual_loan_ratio,
}
_SEGMENTS = ("Consumer &amp; Community Banking, Corporate &amp; Investment Bank, "
             "Commercial Banking and Asset &amp; Wealth Management")
_OLDER_LIST = ("The Firm is managed on an LOB basis. There are four major reportable business "
               "segments &#8211; " + _SEGMENTS + ". In addition, there is a Corporate segment.")
_GLOSSARY = ("AUM{colon} &#8220;Assets under management&#8221;: Represent assets managed by AWM on "
             "behalf of its Private Banking, Institutional and Retail clients. Includes "
             "&#8220;Committed capital not Called.&#8221;")


def _document(*blocks):
    """Constructed HTML: each block a div, or a table when given as a list of rows."""
    parts = []
    for block in blocks:
        if isinstance(block, list):
            rows = "".join("<tr>" + "".join("<td>" + cell + "</td>" for cell in row) + "</tr>"
                           for row in block)
            parts.append("<table>" + rows + "</table>")
        else:
            parts.append("<div>" + block + "</div>")
    raw = ("<html><body>" + "".join(parts) + "</body></html>").encode("utf-8")
    parser = _AllTablesParser()
    parser.feed(raw.decode("utf-8"))
    parser.close()
    return parser.tables, index_source_structure(source_bytes=raw)


def _section_definitions(function, *blocks):
    builders, structure = _document(*blocks, [["ASSET &amp; WEALTH MANAGEMENT"]])
    return [heading["segment_definition"] for heading in function(builders, structure)]


class TheSuccessorIsTheFrozenCodeWithOnlyItsSubstitutions(unittest.TestCase):

    def test_each_target_compiles_from_its_source_to_the_loaded_code(self):
        # The identity the module states: compiled as its module compiles it,
        # with no substitution the source is the frozen code object itself.
        for name, function in _TARGETS.items():
            with self.subTest(form=name):
                source = Path(function.__code__.co_filename).read_text(encoding="utf-8")
                self.assertEqual(function.__code__, wording._compiled(function, source))

    def test_each_successor_carries_exactly_its_forms(self):
        for name, function in _TARGETS.items():
            with self.subTest(form=name):
                made = wording.successor(function, wording.FORMS[name])
                self.assertEqual(wording.FORMS[name], made.historical_substitutions)
                self.assertIs(function.__globals__, made.__globals__)
                self.assertNotEqual(function.__code__, made.__code__)

    def test_a_substitution_that_does_not_occur_exactly_once_is_refused(self):
        with self.assertRaisesRegex(wording.HistoricalFinancialWordingError,
                                    "HISTORICAL_SUCCESSOR_SUBSTITUTION_NOT_FOUND_ONCE:_linked_notes"):
            wording.successor(frozen_duration._linked_notes, (("no such text", "x"),))
        with self.assertRaisesRegex(wording.HistoricalFinancialWordingError,
                                    "HISTORICAL_SUCCESSOR_SUBSTITUTION_NOT_FOUND_ONCE:_linked_notes"):
            wording.successor(frozen_duration._linked_notes, (("structure", "x"),))

    def test_a_successor_without_substitutions_is_refused(self):
        with self.assertRaisesRegex(wording.HistoricalFinancialWordingError,
                                    "HISTORICAL_SUCCESSOR_WITHOUT_SUBSTITUTIONS"):
            wording.successor(frozen_duration._linked_notes, ())

    def test_only_a_top_level_package_function_has_a_successor(self):
        def local():
            return None
        for target in (len, local):
            with self.subTest(target=target), self.assertRaisesRegex(
                    wording.HistoricalFinancialWordingError,
                    "HISTORICAL_SUCCESSOR_TARGET_NOT_A_TOP_LEVEL_PACKAGE_FUNCTION"):
                wording.successor(target, (("a", "b"),))

    def test_a_source_that_changed_after_it_was_loaded_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "_wording_fixture.py"
            path.write_text("def frozen():\n    return 'frozen'\n", encoding="utf-8")
            module = types.ModuleType("vnext._wording_fixture")
            module.__file__ = str(path)
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), vars(module))  # noqa: S102
            sys.modules[module.__name__] = module
            try:
                made = wording.successor(module.frozen, (("'frozen'", "'older'"),))
                self.assertEqual("older", made())
                self.assertEqual("frozen", module.frozen())
                path.write_text("def frozen():\n    return 'edited'\n", encoding="utf-8")
                importlib.invalidate_caches()
                with self.assertRaisesRegex(wording.HistoricalFinancialWordingError,
                                            "HISTORICAL_SUCCESSOR_SOURCE_IS_NOT_THE_LOADED_CODE:frozen"):
                    wording.successor(module.frozen, (("'edited'", "'older'"),))
            finally:
                sys.modules.pop(module.__name__, None)


class TheOlderSegmentListNamesTheSameSegments(unittest.TestCase):

    def test_the_older_sentence_binds_the_section_the_frozen_one_does_not(self):
        self.assertEqual([None], _section_definitions(
            frozen_relationships._reported_segment_sections, _OLDER_LIST))
        found = _section_definitions(wording._SEGMENTS, _OLDER_LIST)
        self.assertEqual(1, len(found))
        self.assertEqual(1, len(found[0]["consistent_source_definitions"]))

    def test_the_newest_sentence_reads_as_it_did(self):
        newest = ("The Firm has three reportable business segments &#8211; Consumer &amp; Community "
                  "Banking, Commercial &amp; Investment Bank, and Asset &amp; Wealth Management "
                  "&#8211; with the remaining activities in Corporate.")
        self.assertEqual(_section_definitions(frozen_relationships._reported_segment_sections, newest),
                         _section_definitions(wording._SEGMENTS, newest))

    def test_a_list_that_does_not_put_the_rest_in_corporate_binds_nothing(self):
        other = _OLDER_LIST.replace("there is a Corporate segment", "there is a Treasury segment")
        self.assertEqual([None], _section_definitions(wording._SEGMENTS, other))

    def test_two_lists_that_disagree_bind_nothing(self):
        three = ("The Firm has three reportable business segments &#8211; Consumer &amp; Community "
                 "Banking, Commercial &amp; Investment Bank, and Asset &amp; Wealth Management "
                 "&#8211; with the remaining activities in Corporate.")
        self.assertEqual([None], _section_definitions(wording._SEGMENTS, _OLDER_LIST, three))


class TheGlossaryColonIsTheSameEntry(unittest.TestCase):

    def _definitions(self, function, colon):
        _, structure = _document(_GLOSSARY.format(colon=colon))
        return [(manager, clients) for manager, clients, _ in function(structure)]

    def test_the_colon_form_is_read_and_the_newest_form_still_is(self):
        expected = [("AWM", "Private Banking, Institutional and Retail")]
        self.assertEqual([], self._definitions(frozen_balance._aum_definitions, ":"))
        self.assertEqual(expected, self._definitions(wording._AUM_DEFINITIONS, ":"))
        self.assertEqual(expected, self._definitions(frozen_balance._aum_definitions, ""))
        self.assertEqual(expected, self._definitions(wording._AUM_DEFINITIONS, ""))

    def test_nothing_but_one_colon_is_accepted(self):
        self.assertEqual([], self._definitions(wording._AUM_DEFINITIONS, "::"))
        self.assertEqual([], self._definitions(wording._AUM_DEFINITIONS, " -"))


class OneGeneralNoteMayPrecedeTheLetteredNotes(unittest.TestCase):

    _NOTE_D = ("(d)For the years ended December 31, 2021, 2020 and 2019, the percentage represents "
               "average LCR for the three months ended December 31, 2021, 2020 and 2019.")

    def _linked(self, function, *between):
        _, structure = _document([["LCR (average)(d)", "111"]], *between,
                                 "(a)Prior-period amounts have been revised.",
                                 "(b)Quarterly ratios are based upon annualized amounts.",
                                 "(c)Some other note.", self._NOTE_D)
        notes, missing = function(structure=structure, table_order=0, markers={"d"})
        return [" ".join(note["visible_text"].split()) for note in notes], missing

    def test_a_general_note_sentence_no_longer_hides_the_lettered_notes(self):
        general = ("Effective January 1, 2020, the Firm adopted the new accounting guidance. "
                   "Refer to Note 1 for further information.")
        self.assertEqual(([], True), self._linked(frozen_duration._linked_notes, general))
        notes, missing = self._linked(wording.successor(frozen_duration._linked_notes,
                                                        wording.GENERAL_NOTE), general)
        self.assertFalse(missing)
        self.assertEqual([self._NOTE_D], notes)

    def test_without_a_general_note_both_read_alike(self):
        older = wording.successor(frozen_duration._linked_notes, wording.GENERAL_NOTE)
        self.assertEqual(self._linked(frozen_duration._linked_notes), self._linked(older))

    def test_a_heading_or_a_second_unmarked_block_still_ends_the_notes(self):
        older = wording.successor(frozen_duration._linked_notes, wording.GENERAL_NOTE)
        self.assertEqual(([], True), self._linked(older, "Liquidity Risk Management"))
        self.assertEqual(([], True), self._linked(older, "One general note.", "Another general note."))


class TheUnitNoteMayNameTheMeasureByItsLabelsAbbreviation(unittest.TestCase):
    """The percent unit, proved by a row-linked note that names the measure."""

    def _duration(self, function, note):
        rows = [["As of or for the year ended December 31,", "2021", "2020"],
                ["Firm Liquidity coverage ratio (&#8220;LCR&#8221;) (average)(a)", "111", "110"]]
        body = "".join("<tr>" + "".join("<td>" + c + "</td>" for c in row) + "</tr>" for row in rows)
        raw = ("<html><body><table>" + body + "</table><div>" + note
               + "</div></body></html>").encode("utf-8")
        from vnext.canonical import sha256_bytes
        return function(source_bytes=raw, expected_source_sha256=sha256_bytes(content=raw),
                        table_id="table_000001", row_index=1, column_index=1,
                        measurement_aliases=["Firm Liquidity coverage ratio (\u201cLCR\u201d) (average)(a)"],
                        required_row_terms=[], reported_unit="percent",
                        claimed_period_start="2021-10-01", claimed_period_end="2021-12-31")

    _OLDEST = ("(a)For the years ended December 31, 2021 and 2020, the percentage represents average "
               "{name} for the three months ended December 31, 2021 and 2020.")

    def test_the_label_s_abbreviation_proves_the_unit_where_ratios_did(self):
        older = wording.successor(frozen_duration.inspect_financial_duration,
                                  wording.MEASURE_ABBREVIATION)
        self.assertIn("REPORTED_UNIT_NOT_PROVEN",
                      self._duration(frozen_duration.inspect_financial_duration,
                                     self._OLDEST.format(name="LCR"))["reasons"])
        got = self._duration(older, self._OLDEST.format(name="LCR"))
        self.assertEqual("PASSED", got["status"], got["reasons"])
        self.assertEqual(1, len(got["unit_evidence_footnote_spans"]))
        frozen = self._duration(frozen_duration.inspect_financial_duration,
                                self._OLDEST.format(name="ratios"))
        self.assertEqual("PASSED", frozen["status"], frozen["reasons"])
        self.assertEqual(frozen, self._duration(older, self._OLDEST.format(name="ratios")))

    def test_a_name_the_label_does_not_define_proves_nothing(self):
        older = wording.successor(frozen_duration.inspect_financial_duration,
                                  wording.MEASURE_ABBREVIATION)
        self.assertIn("REPORTED_UNIT_NOT_PROVEN",
                      self._duration(older, self._OLDEST.format(name="NSFR"))["reasons"])


class TheFrozenAnswerIsKeptUnlessOnlyTheOlderWordingResolves(unittest.TestCase):
    """Stubs stand in for the inspectors: what is taken, not what is read."""

    def _run(self, frozen, older):
        calls = []

        def frozen_stub(**arguments):
            calls.append("frozen")
            return frozen

        def older_stub(**arguments):
            calls.append("older")
            return older
        with mock.patch.dict(wording._FROZEN, {"A04": frozen_stub}), \
                mock.patch.dict(wording._OLDER, {"A04": older_stub}):
            return wording.inspect_nim_relationships(source_bytes=b""), calls

    def test_a_resolved_frozen_answer_is_returned_as_it_is(self):
        frozen = {"semantic_status": wording.RESOLVED, "status": "RELATIONSHIP_PROVEN"}
        got, calls = self._run(frozen, {"semantic_status": wording.RESOLVED})
        self.assertIs(frozen, got)
        self.assertEqual(["frozen"], calls)

    def test_the_older_answer_is_taken_only_where_it_resolves_and_says_so(self):
        frozen = {"semantic_status": "UNRESOLVED", "status": "RELATIONSHIP_PROVEN"}
        got, calls = self._run(frozen, {"semantic_status": wording.RESOLVED, "value": "x"})
        self.assertEqual(["frozen", "older"], calls)
        self.assertEqual("x", got["value"])
        self.assertEqual({"rule": wording.RULE, "forms": ["MARKETS_NAME"],
                          "frozen_inspector_status": frozen,
                          "taken_because": "FROZEN_INSPECTOR_UNRESOLVED_AND_OLDER_WORDING_RESOLVED"},
                         got["historical_older_wording"])

    def test_where_neither_resolves_the_frozen_refusal_stands(self):
        frozen = {"semantic_status": "UNRESOLVED"}
        got, _ = self._run(frozen, {"semantic_status": "UNRESOLVED"})
        self.assertIs(frozen, got)


class TheRouteReadsTheseInspectors(unittest.TestCase):

    def test_the_historical_route_takes_the_fact_with_the_five_successors(self):
        self.assertIs(wording.fact, route._fact)
        self.assertEqual({"inspect_lcr_disclosed_fact": wording.inspect_lcr_disclosed_fact,
                          "inspect_nim_relationships": wording.inspect_nim_relationships,
                          "inspect_ordinary_a09_source_fact": wording.inspect_ordinary_a09_source_fact,
                          "inspect_aum_balance": wording.inspect_aum_balance,
                          "inspect_total_var": wording.inspect_total_var},
                         overrides_of(wording.fact))

    def test_the_a09_fallback_is_bound_by_name_and_reads_the_older_segments(self):
        fallback = overrides_of(wording._OLDER["A09"])["inspect_nonaccrual_loan_ratio"]
        self.assertEqual({"_reported_segment_sections": wording._SEGMENTS}, overrides_of(fallback))


if __name__ == "__main__":
    unittest.main()
