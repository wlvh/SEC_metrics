"""The D01 reading that grants acceptances, held to the filings it reads.

tools/read_d01_headings.py reads Item 1A off the saved HTML without any of the
route's text modules. Each case below is one thing that reader does because a
filing here needed it, run on that filing, so a reader that stopped doing it
fails where the filing is rather than by an argument about it.
"""
import ast
import hashlib
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_d01_headings as reader
from tools.acceptance_readings import D01_READINGS, saved_bytes

READING = "docs/evidence/issue47_history/content-acceptance/d01-headings-read-from-bytes.json"
REPAIRED = "docs/evidence/issue47_history/content-acceptance/d01-marriott-repaired-read.json"
PARAMOUNT_REPAIRED = "docs/evidence/issue47_history/content-acceptance/d01-paramount-repaired-read.json"
OLDER_YEARS = "docs/evidence/issue47_history/content-acceptance/d01-older-years-read.json"
# Every D01 reading the register grants from, so a reading added there is
# reproduced here without a second list to keep (the predecessor year's reading
# was missing from the list this replaced).
READINGS = D01_READINGS
assert {READING, REPAIRED, PARAMOUNT_REPAIRED, OLDER_YEARS} <= set(READINGS)


def _saved_bytes(relative):
    """A saved document: from the checkout, or else from the acquisition's export."""
    return saved_bytes(repo_root=ROOT, relative=relative)


CUT = "Failures to comply with or changes in U"


def _page_split_decisions(body, label, row):
    """The page-split decisions a row was read under.

    A row carries them from the time the reader flags page splits. A row
    recorded before carries none, and its decisions were recorded afterwards in
    the judgement file the reading names - so every pair the reader flags on its
    filing is still judged, just not by the row itself.
    """
    if "page_split_judgements" in row:
        return row["page_split_judgements"]
    recorded = json.loads((ROOT / body["judgements"]).read_text(encoding="utf-8"))
    return {entry["line"]: entry["decision"]
            for entry in recorded.get(label, {}).get("page_split_lines", ())}


def _document(path, label):
    return ROOT / json.loads((ROOT / path).read_text(encoding="utf-8"))[
        "per_position"][label]["document"]


def _read(path, label, names=()):
    raw = _document(path, label).read_bytes()
    return reader.headings_and_other_marks(raw_bytes=raw, registrant_names=names)


class TheReaderIsNotTheRouteTest(unittest.TestCase):

    def test_it_imports_none_of_the_route_s_text_modules(self):
        tree = ast.parse((ROOT / "tools/read_d01_headings.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                # "from vnext import x" names the module in its alias.
                imported.add(node.module)
                imported.update(node.module + "." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for route_module in ("text_coverage", "historical_text_emphasis",
                             "historical_risk_results", "risk_signals",
                             "text_business_candidates", "historical_text_results"):
            with self.subTest(route_module):
                self.assertFalse([name for name in imported if route_module in name])


class EachFilingSpecificStepTest(unittest.TestCase):

    def test_underline_categories_are_read_where_marriott_sets_them(self):
        headings, shapes, _ = _read(REPAIRED, "marriott-2025")
        self.assertEqual(38, len(headings))
        underlined = [text for text, shape in zip(headings, shapes)
                      if shape["mark"] == "UNDERLINE"]
        self.assertEqual(["Operational Risks", "Development and Financing Risks",
                          "Technology, Information Protection, and Privacy Risks",
                          "General Risk Factors"], underlined)

    def test_the_item_is_the_longest_span_not_the_contents_row(self):
        """Salesforce's contents row 'Item 1A.' is bold and unlinked."""
        headings, _, _ = _read(READING, "salesforce-2026")
        self.assertIn("Risk Factor Summary", headings)
        self.assertGreater(len(headings), 40)

    def test_repeated_category_labels_are_listed_once_at_first_occurrence(self):
        """Southwest names its four categories in a summary and again below."""
        headings, _, _ = _read(READING, "southwest-2025")
        distinct = list(dict.fromkeys(headings))
        self.assertEqual(4, len(headings) - len(distinct))
        self.assertEqual("Financial Risks", distinct[0])

    def test_a_bold_bullet_is_not_a_heading(self):
        headings, _, others = _read(READING, "salesforce-2026")
        self.assertNotIn("•", headings)
        self.assertTrue(any(entry["text"].startswith("•") for entry in others))

    def test_the_item_s_own_title_line_is_not_a_heading_inside_it(self):
        """Paramount sets 'Item 1A.' and 'Risk Factors.' as two blocks."""
        headings, _, _ = _read(READING, "paramount-2025")
        self.assertNotIn("Risk Factors.", headings)

    def test_a_line_cut_at_an_unbolded_period_is_flagged(self):
        headings, shapes, _ = _read(READING, "paramount-2025")
        flagged = [text for text, shape in zip(headings, shapes)
                   if shape["emphasis_resumes_after_a_short_gap"]]
        self.assertEqual([CUT], flagged)
        control, control_shapes, _ = _read(REPAIRED, "marriott-2025")
        self.assertFalse(any(shape["emphasis_resumes_after_a_short_gap"]
                             for shape in control_shapes))


class AFlaggedLineIsReadOnlyThroughItsJudgementTest(unittest.TestCase):
    """The reading offers both readings of a flagged line and applies neither.

    The route bridges a gap of two characters or fewer; if the reading did the
    same, a wrong bridging rule would be wrong on both sides and the reading
    would pass it. So the reading computes the prefix and the extent across the
    gap from its own runs, and only a recorded judgement picks one.
    """

    def setUp(self):
        self.headings, self.shapes, _ = _read(READING, "paramount-2025")

    def test_both_readings_are_the_filing_s_own_text(self):
        shape = self.shapes[self.headings.index(CUT)]
        self.assertEqual("Failures to comply with or changes in U.S. or foreign laws or "
                         "regulations could have an adverse effect on our business, financial "
                         "condition or results of operations.", shape["across_short_gaps"])
        # Only flagged lines carry the second reading.
        self.assertEqual(1, sum("across_short_gaps" in shape for shape in self.shapes))

    def test_no_judgement_fails_and_each_decision_gives_its_own_line(self):
        lines, unjudged, not_found = reader.judged_lines(
            headings=self.headings, shapes=self.shapes, short_gap_lines={})
        self.assertEqual(([CUT], []), (unjudged, not_found))
        self.assertIn(CUT, lines)
        across, unjudged, _ = reader.judged_lines(
            headings=self.headings, shapes=self.shapes,
            short_gap_lines={CUT: "ONE_HEADING_ACROSS_THE_GAP"})
        self.assertEqual([], unjudged)
        self.assertNotIn(CUT, across)
        self.assertEqual(len(lines), len(across))
        ends, unjudged, _ = reader.judged_lines(
            headings=self.headings, shapes=self.shapes,
            short_gap_lines={CUT: "HEADING_ENDS_AT_THE_GAP"})
        self.assertEqual(([], lines), (unjudged, ends))

    def test_a_judgement_about_a_line_the_filing_does_not_flag_fails(self):
        other = next(text for text, shape in zip(self.headings, self.shapes)
                     if not shape["emphasis_resumes_after_a_short_gap"])
        _, _, not_found = reader.judged_lines(
            headings=self.headings, shapes=self.shapes,
            short_gap_lines={CUT: "ONE_HEADING_ACROSS_THE_GAP",
                             other: "ONE_HEADING_ACROSS_THE_GAP"})
        self.assertEqual([other], not_found)

    def test_an_unknown_decision_is_no_judgement(self):
        _, unjudged, _ = reader.judged_lines(
            headings=self.headings, shapes=self.shapes, short_gap_lines={CUT: "PROBABLY"})
        self.assertEqual([CUT], unjudged)

    def test_the_committed_reading_records_the_decision_it_applied(self):
        row = json.loads((ROOT / PARAMOUNT_REPAIRED).read_text(encoding="utf-8"))[
            "per_position"]["paramount-2025"]
        self.assertEqual({CUT: "ONE_HEADING_ACROSS_THE_GAP"}, row["short_gap_judgements"])
        self.assertEqual("MATCH", row["verdict"])
        self.assertEqual([CUT], row["lines_where_emphasis_resumes_after_a_short_gap"])


class AHeadingRunOverAPageIsReadOnlyThroughItsJudgementTest(unittest.TestCase):
    """Two heading lines across page furniture, where the first does not end.

    The route joins them when the second begins in lower case; the reading
    flags every such pair whatever the second looks like, so a split whose rest
    begins with a capital would be flagged here even though the route would not
    join it - and only a recorded decision says which it is.
    """

    OLDER = "docs/evidence/issue47_history/content-acceptance/d01-older-years-read-batch.json"

    def _read_older(self, label):
        row = json.loads((ROOT / self.OLDER).read_text(encoding="utf-8"))["per_position"][label]
        return reader.headings_and_other_marks(
            raw_bytes=_saved_bytes(row["document"]),
            registrant_names=row["registrant_names_tagged_in_the_filing"])

    def test_southwest_fy2022_s_two_split_headings_are_flagged(self):
        headings, shapes, _ = self._read_older("southwest-2022")
        flagged = [(text, shape["runs_over_a_page_into"]) for text, shape in zip(headings, shapes)
                   if "runs_over_a_page_into" in shape]
        self.assertEqual(2, len(flagged))
        self.assertEqual(["a localized disaster", "ability of the Company"],
                         [rest[:len(start)] for (_, rest), start in zip(
                             flagged, ("a localized disaster", "ability of the Company"))])

    def test_each_decision_gives_its_own_lines_and_no_decision_fails(self):
        headings, shapes, _ = self._read_older("southwest-2022")
        first = [text for text, shape in zip(headings, shapes) if "runs_over_a_page_into" in shape]
        lines, unjudged, not_found = reader.judged_lines(
            headings=headings, shapes=shapes, short_gap_lines={}, page_split_lines={})
        self.assertEqual((sorted(first), []), (unjudged, not_found))
        joined, unjudged, _ = reader.judged_lines(
            headings=headings, shapes=shapes, short_gap_lines={},
            page_split_lines={text: "ONE_HEADING_ACROSS_THE_PAGE" for text in first})
        self.assertEqual([], unjudged)
        self.assertEqual(len(lines) - 2, len(joined))
        self.assertTrue(any(line.endswith("or a localized disaster or disturbance in a key "
                                          "geography has adversely and materially impacted, and "
                                          "in the future could again adversely and materially "
                                          "impact, the Company’s business, results of operations, "
                                          "and financial condition.") for line in joined))
        kept, unjudged, _ = reader.judged_lines(
            headings=headings, shapes=shapes, short_gap_lines={},
            page_split_lines={text: "TWO_HEADINGS" for text in first})
        self.assertEqual(([], lines), (unjudged, kept))

    def test_a_decision_about_a_pair_the_filing_does_not_flag_fails(self):
        headings, shapes, _ = self._read_older("southwest-2024")
        _, _, not_found = reader.judged_lines(
            headings=headings, shapes=shapes, short_gap_lines={},
            page_split_lines={headings[0]: "TWO_HEADINGS"})
        self.assertEqual([headings[0]], not_found)

    def test_a_label_at_the_foot_of_a_page_is_flagged_though_the_next_line_is_capitalised(self):
        headings, shapes, _ = _read(READING, "enphase-2025")
        flagged = [shape["runs_over_a_page_into"] for shape in shapes
                   if "runs_over_a_page_into" in shape]
        self.assertEqual(1, len(flagged))
        self.assertTrue(flagged[0][:1].isupper())


class TheReaderReproducesThePublishedValueTest(unittest.TestCase):
    """Byte for byte, from the filing alone, for every accepted position.

    The committed readings record each published value's digest. The reader's
    lines, joined as the route joins them, must hash to it - so a reader that
    grouped differently, dropped a line or took an extra one fails here without
    needing the batch the value came from.
    """

    def test_every_accepted_position(self):
        for path in READINGS:
            body = json.loads((ROOT / path).read_text(encoding="utf-8"))
            for label, row in body["per_position"].items():
                if row["verdict"] != "MATCH":
                    continue
                with self.subTest(path=path, label=label):
                    raw = _saved_bytes(row["document"])
                    headings, shapes, _ = reader.headings_and_other_marks(
                        raw_bytes=raw, registrant_names=row["registrant_names_tagged_in_the_filing"])
                    lines, unjudged, not_found = reader.judged_lines(
                        headings=headings, shapes=shapes,
                        short_gap_lines=row.get("short_gap_judgements", {}),
                        page_split_lines=_page_split_decisions(body, label, row))
                    self.assertEqual(([], []), (unjudged, not_found))
                    joined = "\n".join(reader.as_published(lines))
                    self.assertEqual(row["value_sha256"],
                                     "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest())


class TheCommittedReadingsSayWhatTheyShouldTest(unittest.TestCase):

    def test_the_seven_accepted_and_the_four_that_are_not(self):
        verdicts = {label: row["verdict"] for label, row in json.loads(
            (ROOT / READING).read_text(encoding="utf-8"))["per_position"].items()}
        self.assertEqual({"enphase-2025", "ford-2025", "lumen-2025", "macys-2026",
                          "pfizer-2025", "salesforce-2026", "southwest-2025"},
                         {label for label, verdict in verdicts.items() if verdict == "MATCH"})
        self.assertEqual({"paramount-2025", "marriott-2023", "marriott-2024",
                          "marriott-2025"},
                         {label for label, verdict in verdicts.items() if verdict != "MATCH"})

    def test_every_recorded_identity_was_recorded_when_the_reading_was_made(self):
        for path in READINGS:
            for label, row in json.loads(
                    (ROOT / path).read_text(encoding="utf-8"))["per_position"].items():
                with self.subTest(path=path, label=label):
                    self.assertEqual("RECORDED_AT_READING_TIME",
                                     row["checked_identity"]["established_by"])


if __name__ == "__main__":
    unittest.main()
