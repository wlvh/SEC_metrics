"""The page-number footer test answers what the pattern it replaced answered.

The D02 route first recognised a footer that carries its page number with

    ^(?P<stem>.*?[A-Za-z].*?)[\\s|\\-\\u2013\\u2014]+(?P<page>\\d{1,4})$

Its two lazy groups retry every split of a block that does not end in a page
number, so a paragraph cost time quadratic in its length, and the rule took
about 500 of the 721 seconds the D02 repair cases spent under the profiler.
``_page_numbered`` reads the same answer from the end.

These cases keep the old pattern as the reference. On every string here -
crafted at the boundaries where a reading from the end could part from the
pattern (line breaks, a trailing line break, digit runs of four and five,
separator runs, non-ASCII letters and digits) and drawn at random from an
alphabet made of those boundaries - both must give the same stem and page, or
both none. The footer rule that reads each block once through it is held to
the rule as first written the same way, on generated documents. The last two
cases hold the reason for the change: a long paragraph and a long run of
separators are each answered in linear time.
"""
import random
import re
import sys
import time
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from vnext import historical_text_results as route  # noqa: E402

REFERENCE = re.compile(r"^(?P<stem>.*?[A-Za-z].*?)[\s|\-–—]+(?P<page>\d{1,4})$")


def reference(text):
    """The old pattern's answer: (stem, page), or None."""
    found = REFERENCE.match(text)
    return None if found is None else (found["stem"], found["page"])


CRAFTED = (
    # Footers as the filings print them.
    "Enphase Energy, Inc. | 2025 Form 10-K | 46",
    "Page 4 - 46", "Pfizer Inc. 2024 Form 10-K 112", "Note 16 (Continued) 112",
    "NOTES TO THE FINANCIAL STATEMENTS",
    # No letter before the separator, or nothing before it.
    "46", "", " 12", "— 3", "- 4", "12 - 3",
    # Where the stem ends.
    "x — — — 3", "x 1 2", "12 abc 3", "a b c 9",
    # Digit runs at the four-digit bound, and Unicode digits.
    "x 0", "x 0000", "x 12345", "x 00000", "Page ١٢", "Page １２",
    "Page ²",
    # Each separator, and none.
    "abc -12", "abc|12", "abc–12", "abc—12", "abc\t12", "Page 12",
    "Page​12", "Page12",
    # Line breaks: inside the stem, inside the separator run, at the end.
    "abc\n12", "a\nb 12", "\nab 12", "a\rb 12", "Page 12\n", "Page 12\n\n",
    "Page \n12\n", "Page 12 \n", "Page 12 ",
    # Letters: only ASCII letters count.
    "Ελλάδα 12", "Página 12", "é 12", "éa 12",
)

ALPHABET = ("a", "Z", "é", "1", "9", "١", " ", "\t", "\n", "\r", " ",
            "|", "-", "–", "—", ".", "(")


class ThePageNumberReadingIsTheOldPatternsTest(unittest.TestCase):
    def test_every_crafted_string_gets_the_same_answer(self):
        for text in CRAFTED:
            with self.subTest(text=text):
                self.assertEqual(route._page_numbered(text), reference(text))

    def test_the_crafted_strings_hold_matches_and_refusals(self):
        # A comparison that is all None, or all matches, would not test much.
        answers = [reference(text) for text in CRAFTED]
        self.assertGreater(sum(answer is None for answer in answers), 15)
        self.assertGreater(sum(answer is not None for answer in answers), 15)

    def test_random_strings_over_the_boundary_alphabet(self):
        draw = random.Random(4747)
        matched = 0
        for _ in range(20000):
            text = "".join(draw.choice(ALPHABET) for _ in range(draw.randint(0, 24)))
            expected = reference(text)
            matched += expected is not None
            self.assertEqual(route._page_numbered(text), expected, repr(text))
        self.assertGreater(matched, 500)

    def test_random_footers_with_a_stem_a_separator_run_and_digits(self):
        # Most random strings refuse; these are built to reach the end most of
        # the time, with digit runs on both sides of the four-digit bound and
        # each of the three ways a string can end.
        draw = random.Random(4748)
        separators = (" ", "\t", "\n", "|", "-", "–", "—", " ")
        matched = 0
        for _ in range(20000):
            stem = "".join(draw.choice(ALPHABET) for _ in range(draw.randint(0, 12)))
            run = "".join(draw.choice(separators) for _ in range(draw.randint(0, 4)))
            digits = "".join(draw.choice("0123456789١") for _ in range(draw.randint(0, 6)))
            text = stem + run + digits + draw.choice(("", "", "\n", "\n\n", " "))
            expected = reference(text)
            matched += expected is not None
            self.assertEqual(route._page_numbered(text), expected, repr(text))
        self.assertGreater(matched, 1500)


def reference_footers(*, blocks, start, stop):
    """``_numbered_page_footers`` as first written, reading each block through the old pattern."""
    normalized = route._normalized
    stems, texts = {}, Counter()
    for block in blocks:
        text = " ".join(block["text"].split())
        texts[normalized(text)] += 1
        numbered = REFERENCE.match(text)
        if numbered:
            stems.setdefault(normalized(numbered["stem"]), set()).add(numbered["page"])

    def recurring(index):
        if not 0 <= index < len(blocks):
            return False
        text = " ".join(blocks[index]["text"].split())
        numbered = REFERENCE.match(text)
        return ((numbered is not None and len(stems[normalized(numbered["stem"])]) >= 3)
                or texts[normalized(text)] >= 3)

    footers = set()
    for index in range(start, stop):
        numbered = REFERENCE.match(" ".join(blocks[index]["text"].split()))
        if (numbered and len(stems[normalized(numbered["stem"])]) >= 3
                and (recurring(index - 1) or recurring(index + 1))):
            footers.add(index)
    return footers


# Blocks of the kinds a footer rule meets: numbered footers whose stem recurs
# (some with their whitespace spread over lines, or in other case), running
# heads with and without a number, a page number alone, a numbered caption,
# and prose.
_BLOCK_KINDS = ("Registrant | Form 10-K | {n}", "Registrant\n|  Form 10-K |\t{n}",
                "REGISTRANT | FORM 10-K | {n}", "Page {n}",
                "Notes (Continued) {n}", "Table of Contents", "{n}", "Note 7 | 12",
                "A paragraph.", "A paragraph that ends in {n}", "Item 3. Legal Proceedings",
                "Segment \u2014 Results \u2014 {n}")


class TheFooterSetIsTheOldOnesTest(unittest.TestCase):
    def test_generated_documents_and_ranges(self):
        draw = random.Random(4749)
        found_any = 0
        for _ in range(4000):
            texts = [draw.choice(_BLOCK_KINDS).format(n=draw.randint(1, 5))
                     for _ in range(draw.randint(0, 24))]
            blocks = [{"text": text} for text in texts]
            start = draw.randint(0, len(blocks))
            stop = draw.randint(start, len(blocks))
            expected = reference_footers(blocks=blocks, start=start, stop=stop)
            found_any += bool(expected)
            self.assertEqual(expected, route._numbered_page_footers(blocks=blocks, start=start,
                                                                     stop=stop), texts)
        self.assertGreater(found_any, 500)


class TheReadingIsLinearTest(unittest.TestCase):
    # The old pattern takes about a tenth of a second on a 3,000-character
    # paragraph and grows with its square - 36 seconds on the 53,000 characters
    # below, measured; without the lookbehind, the 40,000-character separator
    # run below took 15 seconds. As written both take milliseconds, so the
    # bound is wide and still far below either.
    BOUND_SECONDS = 2.0

    def test_a_long_paragraph(self):
        paragraph = ("The Company is subject to legal proceedings arising in the ordinary "
                     "course of business. ") * 600
        started = time.perf_counter()
        self.assertIsNone(route._page_numbered(paragraph.strip()))
        self.assertEqual(route._page_numbered(paragraph + "Page 46"),
                         (paragraph + "Page", "46"))
        self.assertLess(time.perf_counter() - started, self.BOUND_SECONDS)

    def test_a_long_separator_run(self):
        run = " -" * 20000
        started = time.perf_counter()
        self.assertIsNone(route._page_numbered("x" + run + "y"))
        self.assertEqual(route._page_numbered("x" + run + " 7"), ("x", "7"))
        self.assertLess(time.perf_counter() - started, self.BOUND_SECONDS)


if __name__ == "__main__":
    unittest.main()
