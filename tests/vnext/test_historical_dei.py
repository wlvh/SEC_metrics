"""The DEI readers on #47's historical paths answer for every DEI taxonomy release.

The first live acquisition found the frozen readers rejecting annual reports
filed in 2021 and 2022: their DEI namespace is ``dei/2020-01-31`` or
``dei/2021q4``, and the frozen pattern accepts only ``dei/`` and four digits.
These cases hold ``historical_dei.release_aware`` to exactly that difference: a
view runs the frozen function's own code in its module's namespace with only
``re`` and the views of what it calls changed; on every saved annual report the
views answer as the frozen readers do; they read an older release the frozen
readers cannot; what a view could not redirect is refused by name; and every
#47 function reaches the question only through a view. The older-release
documents here are constructed - a saved FY2025 report with its DEI namespace
rewritten - and say so.
"""
import ast
import importlib
import pkgutil
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import vnext  # noqa: E402
from vnext import fiscal_year_labels as frozen_labels  # noqa: E402
from vnext import historical_dei  # noqa: E402
from vnext import normal_annual_input as frozen  # noqa: E402
from vnext import text_coverage  # noqa: E402
from vnext.sources import raw_blob_record, source_reference_record  # noqa: E402

view = historical_dei.release_aware
# Saved FY2025 annual report primaries: (path, CIK, report date).
_SAVED_ANNUALS = (
    ("enphase_energy_1463101_000146310126000013/enph-20251231.htm", 1463101, "2025-12-31"),
    ("ford_motor_company_37996_000003799626000015/f-20251231.htm", 37996, "2025-12-31"),
    ("jpmorgan_chase_19617_000162828026008131/jpm-20251231.htm", 19617, "2025-12-31"),
    ("lumen_technologies_18926_000001892626000014/lumn-20251231.htm", 18926, "2025-12-31"),
    ("macy_s_794367_000162828026021721/m-20260131.htm", 794367, "2026-01-31"),
    ("marriott_international_1048286_000104828626000007/mar-20251231.htm", 1048286, "2025-12-31"),
    ("paramount_skydance_paramount_global_2041610_000204161026000011/psky-20251231.htm",
     2041610, "2025-12-31"),
    ("pfizer_78003_000007800326000026/pfe-20251231.htm", 78003, "2025-12-31"),
    ("salesforce_1108524_000110852426000060/crm-20260131.htm", 1108524, "2026-01-31"),
    ("southwest_airlines_92380_000009238026000004/luv-20251231.htm", 92380, "2025-12-31"),
)
_DOCUMENT_CASES = (0, 4, 6)  # Enphase, Macy's (fiscal year to January), Paramount
_DEI_2025 = b"http://xbrl.sec.gov/dei/2025"
# #47's Runs are frozen and replayed by run_store, which for an issue_47_v1
# manifest hands the replay, the authority check and the text contexts to
# historical_run and historical_text_results - #47's own code, checked here.
# run_store reaches the question only through other generations' replays,
# which such a Run never takes; the Run-level probe's cold reads are the
# measurement of that.
_RUN_STORE_ENTRIES = {"run_store:load_frozen_run", "run_store:_mechanically_replay_open_run",
                      "run_store:validate_and_freeze_run"}


def _answer(function, **arguments):
    try:
        return ("ANSWER", function(**arguments))
    except (frozen.NormalAnnualInputError, frozen_labels.FiscalYearLabelError,
            text_coverage.TextCoverageError) as error:
        return ("REFUSED", type(error).__name__, str(error))


def _period(function, *, raw, cik, report_end):
    return _answer(function, raw=raw, cik=cik, filing={"form": "10-K", "reportDate": report_end})


def _document_arguments(*, repo_root, relative, raw):
    """The builder's arguments for one saved primary, its records over ``repo_root``."""
    folder, document = relative.split("/")
    parts = folder.rsplit("_", 2)
    company_id, cik, digits = parts[0], str(int(parts[1])), parts[2]
    accession = digits[:10] + "-" + digits[10:12] + "-" + digits[12:]
    path = "evidence/accession_materials/" + relative
    target = Path(repo_root) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(raw)
    blob = raw_blob_record(repo_root=Path(repo_root), repo_relative_path=path,
                           media_type="text/html")
    reference = source_reference_record(
        raw_blob=blob, company_id=company_id,
        source_url="https://www.sec.gov/Archives/edgar/data/%s/%s/%s" % (cik, digits, document),
        accession=accession, document_name=document, source_role="target_primary",
        request_attempt_id="test-attempt")
    return {"raw_bytes": raw, "raw_blob": blob, "source_reference": reference,
            "expected_company_id": company_id, "expected_cik": cik}


def _own_modules():
    """#47's own modules: every historical_* module and the generation's rule files."""
    text = (ROOT / "tools/vnext_mint_historical_requirement.py").read_text(encoding="utf-8")
    rules = next(ast.literal_eval(node.value) for node in ast.parse(text).body
                 if isinstance(node, ast.Assign)
                 and any(getattr(t, "id", "") == "NEW_RULE_FILES" for t in node.targets))
    own = {"vnext." + Path(p).stem for p in rules
           if p.startswith("scripts/vnext/") and p.endswith(".py")}
    return own | {"vnext." + info.name for info in pkgutil.iter_modules(vnext.__path__)
                  if info.name.startswith("historical_")}


def _fixture_module(source):
    """A throwaway module inside the package, for constructed references."""
    module = types.ModuleType("vnext._historical_dei_fixture")
    module.__package__ = "vnext"
    sys.modules[module.__name__] = module
    exec(compile(source, "<historical_dei fixture>", "exec"), vars(module))  # noqa: S102
    return module


class AViewRunsTheFrozenCode(unittest.TestCase):

    def test_the_frozen_code_runs_with_only_named_differences(self):
        raw = (ROOT / "evidence/accession_materials" / _SAVED_ANNUALS[0][0]).read_bytes()
        seen = []

        def profile(frame, event, arg):
            if event == "call" and frame.f_code is frozen.annual_period.__code__:
                seen.append(dict(frame.f_globals))
        sys.setprofile(profile)
        try:
            historical_dei.annual_period(raw=raw, cik=1463101,
                                         filing={"form": "10-K", "reportDate": "2025-12-31"})
        finally:
            sys.setprofile(None)
        self.assertEqual(1, len(seen), "the frozen code object ran, once")
        namespace, original = seen[0], vars(frozen)
        self.assertEqual(set(original) | {"__builtins__"}, set(namespace) | {"__builtins__"})
        changed = {name for name in namespace
                   if name in original and namespace[name] is not original[name]}
        self.assertIn("re", changed)
        self.assertIs(historical_dei.RELEASE_AWARE_RE, namespace["re"])
        for name in changed - {"re", "__builtins__"}:
            with self.subTest(name=name):
                self.assertIs(view(original[name]), namespace[name],
                              "every other difference is the view of the module's own object")

    def test_what_cannot_reach_the_question_is_returned_unchanged(self):
        for obj in (frozen._need, frozen.NormalAnnualInputError, re, len, {"a": 1},
                    text_coverage._byte_offsets):
            with self.subTest(obj=repr(obj)[:40]):
                self.assertIs(obj, view(obj))

    def test_a_view_is_made_once_and_names_what_it_views(self):
        first = view(text_coverage.build_text_document)
        self.assertIs(first, view(text_coverage.build_text_document))
        self.assertIsNot(first, text_coverage.build_text_document)
        self.assertIs(text_coverage.build_text_document, first.release_aware_view_of)
        self.assertIs(first, view(first))

    def test_a_patch_of_the_frozen_module_is_seen_through_the_view(self):
        """The namespace is read on every call: a test's patch is not bypassed."""
        raw = (ROOT / "evidence/accession_materials" / _SAVED_ANNUALS[0][0]).read_bytes()
        original = frozen.parse_accession_xbrl_source
        with mock.patch.object(frozen, "parse_accession_xbrl_source",
                               wraps=original) as counted:
            historical_dei.annual_period(raw=raw, cik=1463101,
                                         filing={"form": "10-K", "reportDate": "2025-12-31"})
        self.assertEqual(1, counted.call_count)


class TheReViewWidensOnlyTheDeiQuestion(unittest.TestCase):

    def test_every_release_form_is_a_dei_namespace(self):
        for release in ("2019-01-31", "2020-01-31", "2021", "2021q4", "2022", "2025", "2026"):
            for scheme in ("http", "https"):
                uri = scheme + "://xbrl.sec.gov/dei/" + release
                with self.subTest(uri=uri):
                    self.assertTrue(historical_dei.is_dei_namespace(uri))
                    for pattern in historical_dei.FROZEN_DEI_NAMESPACE_PATTERNS:
                        self.assertIsNotNone(historical_dei.RELEASE_AWARE_RE.fullmatch(pattern,
                                                                                       uri))

    def test_anything_else_is_refused(self):
        for uri in ("http://xbrl.sec.gov/dei/2021q5", "http://xbrl.sec.gov/dei/2021q",
                    "http://xbrl.sec.gov/dei/21", "http://xbrl.sec.gov/dei/2021-1-31",
                    "http://xbrl.sec.gov/dei/2021q4x", "http://xbrl.sec.gov/dei/",
                    "http://xbrl.sec.gov/deix/2021", "http://fasb.org/us-gaap/2021",
                    "http://example.com/dei/2021", "http://xbrl.sec.gov/dei/2021/",
                    "http://xbrl.sec.gov/dei/2020-01-31x"):
            with self.subTest(uri=uri):
                self.assertFalse(historical_dei.is_dei_namespace(uri))
                for pattern in historical_dei.FROZEN_DEI_NAMESPACE_PATTERNS:
                    self.assertIsNone(historical_dei.RELEASE_AWARE_RE.fullmatch(pattern, uri))

    def test_every_other_pattern_and_attribute_is_the_standard_librarys(self):
        re_view = historical_dei.RELEASE_AWARE_RE
        for pattern, text in ((r"\d{4}", "2021"), (r"\d{4}", "2021q4"),
                              (r"https?://xbrl\.sec\.gov/dei/\d{4}x", "http://xbrl.sec.gov/dei/2021q4")):
            with self.subTest(pattern=pattern, text=text):
                self.assertEqual(bool(re.fullmatch(pattern, text)),
                                 bool(re_view.fullmatch(pattern, text)))
        self.assertEqual(re.findall(r"\d", "a1b2"), re_view.findall(r"\d", "a1b2"))
        self.assertIs(re.I, re_view.I)
        self.assertIs(re.Pattern, re_view.Pattern)

    def test_the_question_asked_any_other_way_is_refused(self):
        re_view = historical_dei.RELEASE_AWARE_RE
        for name in ("search", "match", "compile", "findall", "sub"):
            for pattern in historical_dei.FROZEN_DEI_NAMESPACE_PATTERNS:
                with self.subTest(name=name, pattern=pattern):
                    with self.assertRaises(historical_dei.HistoricalDeiError) as caught:
                        getattr(re_view, name)(pattern, *(("", "x") if name == "sub" else ("x",)))
                    self.assertIn("HISTORICAL_DEI_QUESTION_ASKED_THROUGH:re." + name,
                                  str(caught.exception))

    def test_the_frozen_readers_spell_their_patterns_this_way(self):
        import inspect
        sources = inspect.getsource(frozen) + inspect.getsource(frozen_labels) \
            + inspect.getsource(text_coverage)
        for pattern in historical_dei.FROZEN_DEI_NAMESPACE_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, sources)


class OnSavedAnnualReportsTheViewsAgreeWithTheFrozenReaders(unittest.TestCase):

    def test_the_annual_reader_gives_the_frozen_answer(self):
        for relative, cik, report_end in _SAVED_ANNUALS:
            raw = (ROOT / "evidence/accession_materials" / relative).read_bytes()
            with self.subTest(document=relative):
                self.assertEqual(_period(frozen.annual_period, raw=raw, cik=cik,
                                         report_end=report_end),
                                 _period(historical_dei.annual_period, raw=raw, cik=cik,
                                         report_end=report_end))

    def test_the_text_document_builder_gives_the_frozen_document(self):
        for index in _DOCUMENT_CASES:
            relative, _, report_end = _SAVED_ANNUALS[index]
            raw = (ROOT / "evidence/accession_materials" / relative).read_bytes()
            arguments = _document_arguments(repo_root=ROOT, relative=relative, raw=raw)
            with self.subTest(document=relative):
                expected = _answer(text_coverage.build_text_document,
                                   expected_period_end=report_end, **arguments)
                self.assertEqual("ANSWER", expected[0])
                self.assertEqual(expected, _answer(view(text_coverage.build_text_document),
                                                   expected_period_end=report_end, **arguments))


class AnOlderReleaseIsRead(unittest.TestCase):
    """Constructed: saved FY2025 reports with their DEI namespace rewritten."""

    @classmethod
    def setUpClass(cls):
        relative, cls.cik, cls.report_end = _SAVED_ANNUALS[0]
        cls.relative = relative
        cls.raw = (ROOT / "evidence/accession_materials" / relative).read_bytes()
        assert cls.raw.count(_DEI_2025) == 1, "the saved report declares dei/2025 once"
        cls.expected = _period(frozen.annual_period, raw=cls.raw, cik=cls.cik,
                               report_end=cls.report_end)
        assert cls.expected[0] == "ANSWER"

    def _rewritten(self, release):
        return self.raw.replace(_DEI_2025, b"http://xbrl.sec.gov/dei/" + release)

    def test_a_dated_or_quarterly_release_is_read_as_the_same_period(self):
        for release in (b"2020-01-31", b"2021q4", b"2019-01-31"):
            raw = self._rewritten(release)
            with self.subTest(release=release):
                self.assertEqual(("REFUSED", "NormalAnnualInputError",
                                  "DEI_MISSING_OR_AMBIGUOUS:DocumentType"),
                                 _period(frozen.annual_period, raw=raw, cik=self.cik,
                                         report_end=self.report_end))
                self.assertEqual(self.expected,
                                 _period(historical_dei.annual_period, raw=raw, cik=self.cik,
                                         report_end=self.report_end))

    def test_a_namespace_that_is_not_a_release_is_still_refused(self):
        for release in (b"2021q5", b"2021-1-31"):
            raw = self._rewritten(release)
            with self.subTest(release=release):
                self.assertEqual(("REFUSED", "NormalAnnualInputError",
                                  "DEI_MISSING_OR_AMBIGUOUS:DocumentType"),
                                 _period(historical_dei.annual_period, raw=raw, cik=self.cik,
                                         report_end=self.report_end))

    def test_the_text_document_is_built_with_the_same_blocks(self):
        original = view(text_coverage.build_text_document)(
            expected_period_end=self.report_end,
            **_document_arguments(repo_root=ROOT, relative=self.relative, raw=self.raw))
        for release in (b"2021q4", b"2020-01-31"):
            raw = self._rewritten(release)
            with self.subTest(release=release), tempfile.TemporaryDirectory() as root:
                arguments = _document_arguments(repo_root=root, relative=self.relative, raw=raw)
                refused = _answer(text_coverage.build_text_document,
                                  expected_period_end=self.report_end, **arguments)
                self.assertEqual(("REFUSED", "TextCoverageError",
                                  "TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING"), refused)
                built = view(text_coverage.build_text_document)(
                    expected_period_end=self.report_end, **arguments)
                self.assertEqual([b["text"] for b in original["blocks"]],
                                 [b["text"] for b in built["blocks"]])
                self.assertEqual(original["source_reasons"], built["source_reasons"])

    def test_a_reader_reached_through_a_local_import_is_viewed(self):
        """``text_results.prepare_text_sources`` imports the document builder inside
        its body: the builder it reaches is the view, and so is the question."""
        from vnext import text_results
        from vnext.specs import compile_spec_file
        spec = compile_spec_file(path=ROOT / "catalog/r6/D01_risk_factor_headings.md",
                                 dependency_specs={})

        def arguments(repo_root, raw):
            built = _document_arguments(repo_root=repo_root, relative=self.relative, raw=raw)
            reference = built["source_reference"]
            return {"compiled_spec": spec, "source_references": [reference],
                    "target": {"company_id": reference["company_id"],
                               "accession": reference["accession"], "entity": str(self.cik),
                               "period_start": "2025-01-01", "period_end": self.report_end},
                    "raw_blobs": {reference["raw_asset_id"]: built["raw_blob"]},
                    "raw_bytes_by_id": {reference["raw_asset_id"]: raw}}
        documents, _ = text_results.prepare_text_sources(**arguments(ROOT, self.raw))
        original = next(iter(documents.values()))
        with tempfile.TemporaryDirectory() as root:
            rewritten = arguments(root, self._rewritten(b"2021q4"))
            with self.assertRaises(text_coverage.TextCoverageError) as caught:
                text_results.prepare_text_sources(**rewritten)
            self.assertEqual("TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING", str(caught.exception))
            documents, _ = view(text_results.prepare_text_sources)(**rewritten)
        built = next(iter(documents.values()))
        self.assertEqual([b["text"] for b in original["blocks"]],
                         [b["text"] for b in built["blocks"]])
        self.assertEqual(original["sections"], built["sections"])

    def test_readers_reached_as_module_globals_are_viewed(self):
        """D04's going-concern source asks the question in three functions of two
        modules, each reached by name from the one #47 calls."""
        from vnext import going_concern_source
        from vnext.text_business_candidates import TextBusinessCandidateError

        def arguments(repo_root, raw):
            built = _document_arguments(repo_root=repo_root, relative=self.relative, raw=raw)
            reference = built["source_reference"]
            return {"raw_bytes": raw, "raw_blob": built["raw_blob"], "source_reference": reference,
                    "company_id": reference["company_id"], "cik": str(self.cik),
                    "filing": {"form": "10-K", "accessionNumber": reference["accession"],
                               "primaryDocument": reference["document_name"],
                               "reportDate": self.report_end}}
        original = going_concern_source.inspect_going_concern_source(**arguments(ROOT, self.raw))
        with tempfile.TemporaryDirectory() as root:
            rewritten = arguments(root, self._rewritten(b"2021q4"))
            with self.assertRaises(TextBusinessCandidateError) as caught:
                going_concern_source.inspect_going_concern_source(**rewritten)
            self.assertEqual("TEXT_BUSINESS_DEI_IDENTITY_CONFLICT", str(caught.exception))
            built = view(going_concern_source.inspect_going_concern_source)(**rewritten)
        units = [[(unit["start_block"], unit["end_block_exclusive"], unit["blocks"],
                   unit["source_payload_sha256"]) for unit in source["semantic_source_units"]]
                 for source in (original, built)]
        self.assertTrue(units[0])
        self.assertEqual(units[0], units[1])
        self.assertEqual(original["registrant_name_binding"]["status"],
                         built["registrant_name_binding"]["status"])

    def test_the_fiscal_label_scan_finds_the_same_dei_spans(self):
        raw = self._rewritten(b"2021q4")
        spans = {}
        for name, raw_bytes, scanner in (
                ("original", self.raw, frozen_labels._MetadataSpans),
                ("rewritten", raw, view(frozen_labels._MetadataSpans)),
                ("frozen_on_rewritten", raw, frozen_labels._MetadataSpans)):
            text = raw_bytes.decode("utf-8-sig")
            scan = scanner(text)
            scan.feed(text)
            scan.close()
            # The rewrite lengthens the namespace, so offsets after it move;
            # what must agree is which facts are DEI and the text each span holds.
            spans[name] = {ordinal: text[start:end]
                           for ordinal, (start, end) in scan.dei_spans.items()}
        self.assertTrue(spans["original"])
        self.assertEqual(spans["original"], spans["rewritten"])
        self.assertEqual({}, spans["frozen_on_rewritten"])


class WhatAViewCannotRedirectIsRefused(unittest.TestCase):

    def tearDown(self):
        sys.modules.pop("vnext._historical_dei_fixture", None)

    def test_a_default_argument_on_the_frozen_path_is_refused(self):
        module = _fixture_module(
            "from vnext.normal_annual_input import annual_period\n"
            "def with_default(raw, reader=annual_period):\n"
            "    return reader(raw=raw, cik=1, filing={})\n")
        with self.assertRaises(historical_dei.HistoricalDeiError) as caught:
            view(module.with_default)
        self.assertIn("HISTORICAL_DEI_REFERENCE_NOT_REBINDABLE:vnext._historical_dei_fixture:"
                      "with_default", str(caught.exception))

    def test_the_question_asked_without_re_is_refused(self):
        module = _fixture_module(
            "def asks_another_way(uri):\n"
            "    from re import fullmatch\n"
            "    return fullmatch(r'https?://xbrl\\.sec\\.gov/dei/\\d{4}', uri)\n")
        with self.assertRaises(historical_dei.HistoricalDeiError) as caught:
            view(module.asks_another_way)
        self.assertIn("HISTORICAL_DEI_QUESTION_NOT_ASKED_THROUGH_RE:", str(caught.exception))


class EveryHistoricalReferenceGoesThroughAView(unittest.TestCase):

    def tearDown(self):
        sys.modules.pop("vnext._historical_dei_fixture", None)

    def test_no_historical_function_reaches_the_question_without_a_view(self):
        own = _own_modules()
        found = {}
        for name in sorted(own - {"vnext.historical_dei"}):
            module = importlib.import_module(name)
            for attribute, value in vars(module).items():
                if isinstance(value, (types.FunctionType, type)) and value.__module__ == name:
                    listed = historical_dei.unviewed_references(value, own_modules=own)
                    if listed:
                        found[name.replace("vnext.", "") + ":" + attribute] = {
                            u.__module__.replace("vnext.", "") + ":" + u.__qualname__
                            for u in listed}
        self.assertEqual({"historical_projection:render_historical_run",
                          "historical_run:create_historical_run"}, set(found))
        for caller, listed in found.items():
            with self.subTest(caller=caller):
                self.assertLessEqual(listed, _RUN_STORE_ENTRIES)

    def test_a_direct_reference_is_listed_and_a_view_is_not(self):
        module = _fixture_module(
            "from vnext import text_coverage\n"
            "from vnext.historical_dei import release_aware\n"
            "def direct(**arguments):\n"
            "    return text_coverage.build_text_document(**arguments)\n"
            "def through_the_view(**arguments):\n"
            "    return release_aware(text_coverage).build_text_document(**arguments)\n")
        own = {module.__name__}
        self.assertEqual([text_coverage.build_text_document],
                         historical_dei.unviewed_references(module.direct, own_modules=own))
        self.assertEqual([], historical_dei.unviewed_references(module.through_the_view,
                                                                own_modules=own))


class TheFrozenModulesAreUnchanged(unittest.TestCase):

    def test_the_frozen_modules_keep_their_own_objects(self):
        self.assertIsNot(historical_dei.annual_period, frozen.annual_period)
        self.assertIs(frozen.re, re)
        self.assertIs(text_coverage.re, re)
        self.assertIs(frozen_labels.annual_period, frozen.annual_period)
        self.assertIs(frozen_labels._MetadataSpans.handle_starttag.__globals__["re"], re)

    def test_historical_callers_read_the_views(self):
        from vnext import historical_annual_input, historical_results
        self.assertIs(historical_dei.annual_period, historical_annual_input.annual_period)
        self.assertIs(historical_dei.inspect_prepared_fiscal_year_labels,
                      historical_annual_input.inspect_prepared_fiscal_year_labels)
        self.assertIs(historical_dei.annual_period, historical_results.annual_period)
        self.assertIs(frozen.annual_period, historical_dei.annual_period.release_aware_view_of)


if __name__ == "__main__":
    unittest.main()
