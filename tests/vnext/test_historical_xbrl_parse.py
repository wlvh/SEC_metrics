"""One native XBRL parse per document while the block is open, and nothing else.

The block may save time only by answering the same bytes with the object a
fresh parse would have produced. So the cases hold: equal bytes give one
object and one parse, equal to a fresh parse field by field; different bytes of
the same length are different documents; what the frozen parser refuses it
still refuses, and a refusal is not kept; every binding is swapped inside and
put back outside, a module imported inside the block included; and a saved
annual report read through the release-aware view gives the answer it gives
outside the block.
"""
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext import deterministic_router  # noqa: E402
from vnext import historical_xbrl_parse  # noqa: E402
from vnext import normal_annual_input  # noqa: E402
from vnext import text_coverage  # noqa: E402
from vnext.historical_xbrl_parse import xbrl_parsed_once  # noqa: E402

FROZEN = deterministic_router.parse_accession_xbrl_source
DOCUMENT = (
    b'<html><body><xbrli:context id="c-1"><xbrli:entity><xbrli:identifier '
    b'scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>'
    b'<xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31'
    b'</xbrli:endDate></xbrli:period></xbrli:context><ix:nonFraction name="us-gaap:Revenues" '
    b'contextRef="c-1" unitRef="usd" scale="6" decimals="-6">1,234</ix:nonFraction></body></html>')
# The same length, one fact's text changed.
OTHER = DOCUMENT.replace(b">1,234<", b">4,321<")


def _fields(parsed):
    return (parsed.source_sha256, parsed.source_size, parsed.parsed_source_id,
            {key: dict(value) for key, value in parsed.contexts.items()},
            [dict(fact) for fact in parsed.facts])


class OneParsePerDocumentTest(unittest.TestCase):
    def test_equal_bytes_are_parsed_once_and_answer_what_a_fresh_parse_answers(self):
        parses = []
        with xbrl_parsed_once(parses=parses):
            first = normal_annual_input.parse_accession_xbrl_source(raw_bytes=bytes(DOCUMENT))
            again = text_coverage.parse_accession_xbrl_source(raw_bytes=bytes(bytearray(DOCUMENT)))
        self.assertIs(first, again)
        self.assertEqual(1, len(parses))
        self.assertEqual(_fields(FROZEN(raw_bytes=DOCUMENT)), _fields(first))

    def test_different_bytes_of_one_length_are_different_documents(self):
        self.assertEqual(len(DOCUMENT), len(OTHER))
        parses = []
        with xbrl_parsed_once(parses=parses):
            first = deterministic_router.parse_accession_xbrl_source(raw_bytes=DOCUMENT)
            other = deterministic_router.parse_accession_xbrl_source(raw_bytes=OTHER)
        self.assertEqual(2, len(parses))
        self.assertEqual("1,234", first.facts[0]["text"])
        self.assertEqual("4,321", other.facts[0]["text"])
        self.assertEqual(_fields(FROZEN(raw_bytes=OTHER)), _fields(other))

    def test_what_the_parser_refuses_is_refused_as_before_and_not_kept(self):
        parses = []
        with xbrl_parsed_once(parses=parses):
            for _ in range(2):
                with self.assertRaisesRegex(deterministic_router.DeterministicRouterError,
                                            "must be immutable bytes"):
                    deterministic_router.parse_accession_xbrl_source(raw_bytes=bytearray(DOCUMENT))
                with self.assertRaisesRegex(deterministic_router.DeterministicRouterError,
                                            "not UTF-8"):
                    deterministic_router.parse_accession_xbrl_source(raw_bytes=b"\xff\xfe")
            self.assertEqual([], parses)
            deterministic_router.parse_accession_xbrl_source(raw_bytes=DOCUMENT)
        self.assertEqual(1, len(parses))

    def test_a_dropped_document_is_parsed_again_not_answered_differently(self):
        parses = []
        with mock.patch.object(historical_xbrl_parse, "MAX_DOCUMENTS", 1):
            with xbrl_parsed_once(parses=parses):
                first = deterministic_router.parse_accession_xbrl_source(raw_bytes=DOCUMENT)
                deterministic_router.parse_accession_xbrl_source(raw_bytes=OTHER)
                again = deterministic_router.parse_accession_xbrl_source(raw_bytes=DOCUMENT)
        self.assertEqual(3, len(parses))
        self.assertEqual(_fields(first), _fields(again))


class TheBindingsAreSwappedOnlyInsideTest(unittest.TestCase):
    MODULES = (deterministic_router, normal_annual_input, text_coverage)

    def test_every_binding_inside_and_none_outside(self):
        with xbrl_parsed_once():
            for module in self.MODULES:
                inside = module.parse_accession_xbrl_source
                self.assertIsNot(FROZEN, inside, module.__name__)
                self.assertTrue(getattr(inside, "parsed_once", False), module.__name__)
        for module in self.MODULES:
            self.assertIs(FROZEN, module.parse_accession_xbrl_source, module.__name__)

    def test_the_bindings_are_put_back_when_the_block_raises(self):
        with self.assertRaises(RuntimeError):
            with xbrl_parsed_once():
                raise RuntimeError("inside")
        for module in self.MODULES:
            self.assertIs(FROZEN, module.parse_accession_xbrl_source, module.__name__)

    def test_a_module_first_imported_inside_the_block_is_put_back(self):
        probe = types.ModuleType("vnext._xbrl_parse_probe")
        try:
            with xbrl_parsed_once():
                sys.modules[probe.__name__] = probe
                # What ``from .deterministic_router import ...`` binds inside the block.
                probe.parse_accession_xbrl_source = deterministic_router.parse_accession_xbrl_source
                self.assertIsNot(FROZEN, probe.parse_accession_xbrl_source)
            self.assertIs(FROZEN, probe.parse_accession_xbrl_source)
        finally:
            sys.modules.pop(probe.__name__, None)

    def test_a_block_inside_another_keeps_the_outer_memo(self):
        parses = []
        with xbrl_parsed_once(parses=parses):
            outer = deterministic_router.parse_accession_xbrl_source(raw_bytes=DOCUMENT)
            with xbrl_parsed_once():
                inner = deterministic_router.parse_accession_xbrl_source(raw_bytes=DOCUMENT)
            self.assertTrue(getattr(deterministic_router.parse_accession_xbrl_source,
                                    "parsed_once", False))
        self.assertIs(outer, inner)
        self.assertEqual(1, len(parses))

    def test_a_block_open_in_another_thread_is_refused(self):
        refused = []

        def other():
            try:
                with xbrl_parsed_once():
                    pass
            except ValueError as error:
                refused.append(str(error))
        with xbrl_parsed_once():
            thread = threading.Thread(target=other)
            thread.start()
            thread.join()
        self.assertEqual(1, len(refused))
        self.assertIn("HISTORICAL_XBRL_PARSE_BLOCK_OPEN_IN_ANOTHER_THREAD", refused[0])

    def test_a_parser_someone_else_replaced_is_refused(self):
        with mock.patch.object(deterministic_router, "parse_accession_xbrl_source",
                               lambda *, raw_bytes: None):
            with self.assertRaisesRegex(ValueError, "HISTORICAL_XBRL_PARSER_ALREADY_REPLACED"):
                with xbrl_parsed_once():
                    pass


class ASavedFilingThroughTheViewTest(unittest.TestCase):
    """The release-aware view reads its module's namespace on every call, so it
    sees the remembered parser; it must take it as it takes the frozen one."""

    FILING = ("evidence/accession_materials/enphase_energy_1463101_000146310126000013/"
              "enph-20251231.htm", 1463101, "2025-12-31")

    def test_the_view_answers_inside_the_block_what_it_answers_outside(self):
        from vnext import historical_dei
        path, cik, report_end = self.FILING
        raw = (ROOT / path).read_bytes()
        filing = {"form": "10-K", "reportDate": report_end}
        outside = historical_dei.annual_period(raw=raw, cik=cik, filing=filing)
        parses = []
        with xbrl_parsed_once(parses=parses):
            inside = [historical_dei.annual_period(raw=raw, cik=cik, filing=filing)
                      for _ in range(2)]
        self.assertEqual([outside, outside], inside)
        self.assertEqual(1, len(parses))


if __name__ == "__main__":
    unittest.main()
