"""D02 quote form and saved-answer regressions; no company install or network."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from vnext import legal_review_contract as review


LITIGATION = "We are subject to legal proceedings and claims arising in the ordinary course."
FEES = "External legal counsel advises us on finance and regulatory matters."
LEASES = "Operating lease cost was $120 million for the year."


def request(*texts, keyword=()):
    document = {"source_reference_id": "sha256:" + "a" * 64,
                "raw_asset_id": "sha256:" + "b" * 64,
                "text_document_id": "sha256:" + "c" * 64,
                "blocks": [{"text": text} for text in texts]}
    return review.review_request(company_id="example", target_cik="1", period_end="2025-12-31",
                                 document=document, pool=list(range(len(texts))),
                                 keyword_admitted=list(keyword))


def answer(decisions, added=()):
    return json.dumps({"decisions": [{"block_id": b, "decision": d, "quote": q}
                                     for b, d, q in decisions],
                       "also_in_scope": [{"block_id": b, "quote": q} for b, q in added]})


class QuoteProblemsTest(unittest.TestCase):
    def test_missing_and_non_string_are_different(self):
        for quote in (None, ""):
            with self.subTest(quote=quote):
                self.assertEqual("D02_REVIEW_QUOTE_MISSING",
                                 review.quote_problem(quote=quote, text=LITIGATION))
        for quote in (False, 12, [], {"text": LITIGATION}):
            with self.subTest(quote=quote):
                self.assertEqual("D02_REVIEW_QUOTE_WRONG_TYPE",
                                 review.quote_problem(quote=quote, text=LITIGATION))

    def test_wrong_block_and_absent_words_are_different(self):
        self.assertEqual("D02_REVIEW_QUOTE_FROM_ANOTHER_BLOCK", review.quote_problem(
            quote=FEES, text=LITIGATION, other_texts=[FEES]))
        self.assertEqual("D02_REVIEW_QUOTE_NOT_IN_BLOCK", review.quote_problem(
            quote="The company settled the lawsuit for $10 million.",
            text=LITIGATION, other_texts=[FEES]))

    def test_source_matching_precedes_length(self):
        invented = "An invented claim. " * 20
        self.assertEqual("D02_REVIEW_QUOTE_NOT_IN_BLOCK",
                         review.quote_problem(quote=invented, text=LITIGATION))
        other = "The other block's exact words. " * 20
        self.assertEqual("D02_REVIEW_QUOTE_FROM_ANOTHER_BLOCK", review.quote_problem(
            quote=other, text=LITIGATION, other_texts=[other]))
        self.assertEqual("D02_REVIEW_QUOTE_TOO_LONG",
                         review.quote_problem(quote=other, text=other))

    def test_existing_character_bounds_are_inclusive(self):
        text = "x" * 301
        for length, expected in ((19, "D02_REVIEW_QUOTE_TOO_SHORT"), (20, None),
                                 (300, None), (301, "D02_REVIEW_QUOTE_TOO_LONG")):
            with self.subTest(length=length):
                self.assertEqual(expected, review.quote_problem(quote=text[:length], text=text))
        self.assertEqual((20, 300), review.QUOTE_CHARACTERS)

    def test_characters_are_not_utf8_bytes(self):
        quote = "é" * 300
        self.assertEqual(600, len(quote.encode("utf-8")))
        self.assertIsNone(review.quote_problem(quote=quote, text=quote))

    def test_matching_does_not_normalize_the_raw_text(self):
        text = "The Company’s  legal\nproceedings remain unresolved."
        self.assertIsNone(review.quote_problem(quote=text, text=text))
        for quote in (text.replace("’", "'"), text.replace("  ", " "),
                      text.replace("\n", " ")):
            with self.subTest(quote=quote):
                self.assertEqual("D02_REVIEW_QUOTE_NOT_IN_BLOCK",
                                 review.quote_problem(quote=quote, text=text))

    def test_short_blocks_keep_the_existing_whole_text_rule(self):
        self.assertIsNone(review.quote_problem(quote="Legal Matters", text="Legal Matters"))
        self.assertEqual("D02_REVIEW_QUOTE_TOO_SHORT",
                         review.quote_problem(quote="Legal", text="Legal Matters"))


class AnswerContractTest(unittest.TestCase):
    def test_decisions_and_additions_report_their_own_block(self):
        req = request(LITIGATION, FEES, LEASES)
        for quote, cause in ((None, "MISSING"), (False, "WRONG_TYPE"),
                             (FEES, "FROM_ANOTHER_BLOCK"),
                             ("An invented legal claim", "NOT_IN_BLOCK"),
                             (LITIGATION[:10], "TOO_SHORT")):
            with self.subTest(cause=cause):
                with self.assertRaisesRegex(review.LegalReviewContractError,
                                            "D02_REVIEW_QUOTE_" + cause + ":b0$"):
                    review.validate_answer(request=req, raw_output=answer(
                        [("b0", "IN_SCOPE", quote), ("b1", "OUT_OF_SCOPE", None)]))
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_QUOTE_FROM_ANOTHER_BLOCK:b2$"):
            review.validate_answer(request=req, raw_output=answer(
                [("b0", "IN_SCOPE", LITIGATION), ("b1", "OUT_OF_SCOPE", None)],
                [("b2", FEES)]))

    def test_overlong_addition_is_still_rejected(self):
        text = "An ordinary accounting disclosure. " * 12
        req = request(LITIGATION, text)
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_QUOTE_TOO_LONG:b1$"):
            review.validate_answer(request=req, raw_output=answer(
                [("b0", "IN_SCOPE", LITIGATION)], [("b1", text)]))

    def test_well_formed_decisions_keep_source_order_and_do_not_change_inputs(self):
        req = request(LITIGATION, FEES, LEASES)
        before = copy.deepcopy(req)
        raw = answer([("b1", "OUT_OF_SCOPE", None), ("b0", "IN_SCOPE", LITIGATION)],
                     [("b2", LEASES)])
        decisions, added = review.validate_answer(request=req, raw_output=raw)
        self.assertEqual((["b0", "b2"], None, []), review.reviewed_blocks(
            request=req, decisions=decisions, added=added))
        self.assertEqual(before, req)

    def test_unsettled_is_withheld_and_not_a_partial_count(self):
        req = request(LITIGATION, FEES)
        decisions, added = review.validate_answer(request=req, raw_output=answer(
            [("b0", "IN_SCOPE", LITIGATION), ("b1", "CANNOT_TELL_FROM_THE_TEXT", FEES)]))
        self.assertEqual((None, review.WITHHELD_REASON, ["b1"]), review.reviewed_blocks(
            request=req, decisions=decisions, added=added))

    def test_missing_duplicate_and_out_of_scope_decisions_still_fail(self):
        req = request(LITIGATION, FEES)
        good = [("b0", "IN_SCOPE", LITIGATION), ("b1", "OUT_OF_SCOPE", None)]
        for entries, error in ((good[:1], "D02_REVIEW_BLOCKS_UNDECIDED:b1"),
                               (good + good[:1], "D02_REVIEW_BLOCK_DECIDED_TWICE:b0"),
                               ([good[0], ("b1", "OUT_OF_SCOPE", FEES)],
                                "D02_REVIEW_OUT_OF_SCOPE_CARRIES_A_QUOTE:b1")):
            with self.subTest(error=error):
                with self.assertRaisesRegex(review.LegalReviewContractError, error):
                    review.validate_answer(request=req, raw_output=answer(entries))


class SavedFailedResponsesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / "fixtures/d02_saved_quote_failures.json"
        cls.original_bytes = cls.path.read_bytes()
        cls.fixture = json.loads(cls.original_bytes)

    def test_eight_original_answers_fail_for_length_and_remain_unchanged(self):
        self.assertEqual(8, len(self.fixture["cases"]))
        for case in self.fixture["cases"]:
            with self.subTest(response=case["name"]):
                self.assertEqual("FAILED_TERMINAL", case["original_terminal_status"])
                self.assertEqual(case["raw_answer_sha256"], hashlib.sha256(
                    case["raw_answer"].encode("utf-8")).hexdigest())
                identity = next(iter(case["overlong_quotes"]))
                with self.assertRaisesRegex(review.LegalReviewContractError,
                                            "D02_REVIEW_QUOTE_TOO_LONG:" + identity + "$"):
                    review.validate_answer(request=case["request"], raw_output=case["raw_answer"])
        self.assertEqual(self.original_bytes, self.path.read_bytes())

    def test_all_fourteen_overlong_quotes_have_exact_source_support(self):
        seen = 0
        for case in self.fixture["cases"]:
            with self.subTest(response=case["name"]):
                answer = json.loads(case["raw_answer"])
                texts = {b["block_id"]: b["text"] for b in case["request"]["blocks"]}
                problems = {}
                for entry in answer["decisions"] + answer["also_in_scope"]:
                    if entry.get("decision") == "OUT_OF_SCOPE":
                        self.assertIsNone(entry["quote"])
                        continue
                    quote, identity = entry["quote"], entry["block_id"]
                    self.assertIn(quote, texts[identity])
                    problem = review.quote_problem(quote=quote, text=texts[identity])
                    if problem:
                        self.assertEqual("D02_REVIEW_QUOTE_TOO_LONG", problem)
                        problems[identity] = len(quote)
                        seen += 1
                self.assertEqual(case["overlong_quotes"], problems)
        self.assertEqual(14, seen)


if __name__ == "__main__":
    unittest.main()
