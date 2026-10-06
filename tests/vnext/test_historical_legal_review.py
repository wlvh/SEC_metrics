"""D02's Item 8 review: the question, the answer's form, and what a registered answer changes.

The contract is checked on a synthetic document, where every refusal can be
reached directly. The route is checked on a real filing - Lumen's FY2025 10-K,
whose keyword admits a legal-fees policy (block 1670) beside two litigation
blocks (3382, 3383) - with a recorded, synthetic answer: what is asserted is
what the route does with an answer, never that the answer is right. No model
is called anywhere.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import historical_legal_review as review
from vnext.canonical import content_hash

LITIGATION = ("We are subject to various claims, legal proceedings and other contingent "
              "liabilities, including the matters described below.")
FEES = ("In the normal course of our business, we incur costs to hire and retain external legal "
        "counsel to advise us on finance, regulatory, litigation, and other matters.")
LEASES = "Operating lease cost was $120 million for the year ended December 31, 2025."
GUARANTEE = "The Company guarantees certain obligations of its unconsolidated joint venture."


def document(*texts):
    return {"source_reference_id": "sha256:" + "a" * 64, "raw_asset_id": "sha256:" + "b" * 64,
            "text_document_id": "sha256:" + "c" * 64,
            "blocks": [{"text": text} for text in texts]}


def request(*texts, keyword=()):
    doc = document(*texts)
    return review.review_request(company_id="example", target_cik="1", period_end="2025-12-31",
                                 document=doc, pool=list(range(len(texts))),
                                 keyword_admitted=list(keyword))


def answer(decisions, added=()):
    return json.dumps({"decisions": [{"block_id": b, "decision": d, "quote": q} for b, d, q in decisions],
                       "also_in_scope": [{"block_id": b, "quote": q} for b, q in added]})


class TheRequestIsTheBlocksAndWhichMustBeDecided(unittest.TestCase):

    def test_must_decide_is_the_keyword_s_admissions_and_the_legal_vocabulary(self):
        req = request(LITIGATION, FEES, LEASES, GUARANTEE, keyword=[0])
        # Block 3 names no legal process, so it is not asked explicitly - it can
        # still be counted through also_in_scope.
        self.assertEqual(["b0", "b1"], req["must_decide"])
        self.assertEqual(["b0", "b1", "b2", "b3"], [b["block_id"] for b in req["blocks"]])

    def test_a_keyword_admission_is_decided_even_without_the_vocabulary(self):
        # The union is explicit rather than left to the vocabulary: the keyword's
        # admissions are what the review exists to correct.
        self.assertEqual(["b0", "b1"], request(LITIGATION, LEASES, keyword=[1])["must_decide"])

    def test_a_changed_text_or_pool_is_a_different_request(self):
        one = request(LITIGATION, FEES)
        self.assertEqual(one, request(LITIGATION, FEES))
        self.assertNotEqual(one["request_id"], request(LITIGATION, LEASES)["request_id"])
        self.assertNotEqual(one["source_id"], request(LITIGATION, LEASES)["source_id"])
        self.assertNotEqual(one["request_id"], request(LITIGATION)["request_id"])

    def test_a_keyword_block_outside_the_pool_is_refused(self):
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_KEYWORD_OUTSIDE_THE_POOL"):
            review.review_request(company_id="example", target_cik="1", period_end="2025-12-31",
                                  document=document(LITIGATION, FEES), pool=[0], keyword_admitted=[1])


class TheAnswerIsHeldToItsForm(unittest.TestCase):

    def setUp(self):
        self.req = request(LITIGATION, FEES, LEASES, GUARANTEE, keyword=[0, 1])
        self.good = [("b0", "IN_SCOPE", LITIGATION[:60]), ("b1", "OUT_OF_SCOPE", None)]

    def refused(self, raw, reason):
        with self.assertRaisesRegex(review.LegalReviewContractError, reason):
            review.validate_answer(request=self.req, raw_output=raw)

    def test_a_well_formed_answer_is_read(self):
        decisions, added = review.validate_answer(
            request=self.req, raw_output=answer(self.good, [("b3", GUARANTEE[:40])]))
        self.assertEqual({"b0", "b1"}, set(decisions))
        self.assertEqual({"b3"}, set(added))

    def test_every_must_decide_block_is_decided_exactly_once(self):
        self.refused(answer(self.good[:1]), "D02_REVIEW_BLOCKS_UNDECIDED:b1")
        self.refused(answer(self.good + self.good[:1]), "D02_REVIEW_BLOCK_DECIDED_TWICE:b0")
        self.refused(answer(self.good + [("b2", "OUT_OF_SCOPE", None)]),
                     "D02_REVIEW_DECIDES_A_BLOCK_NOT_ASKED:b2")

    def test_decisions_and_quotes(self):
        self.refused(answer([("b0", "MAYBE", LITIGATION[:40]), self.good[1]]),
                     "D02_REVIEW_DECISION_UNKNOWN:b0")
        self.refused(answer([("b0", "IN_SCOPE", None), self.good[1]]),
                     "D02_REVIEW_QUOTE_MISSING:b0")
        self.refused(answer([("b0", "IN_SCOPE", FEES[:40]), self.good[1]]),
                     "D02_REVIEW_QUOTE_FROM_ANOTHER_BLOCK:b0")
        self.refused(answer([("b0", "IN_SCOPE", LITIGATION[:10]), self.good[1]]),
                     "D02_REVIEW_QUOTE_TOO_SHORT:b0")
        self.refused(answer([self.good[0], ("b1", "OUT_OF_SCOPE", FEES[:40])]),
                     "D02_REVIEW_OUT_OF_SCOPE_CARRIES_A_QUOTE:b1")
        self.refused(answer([("b0", "CANNOT_TELL_FROM_THE_TEXT", None), self.good[1]]),
                     "D02_REVIEW_QUOTE_MISSING:b0")

    def test_a_short_block_is_quoted_whole(self):
        req = request("Legal Matters", LITIGATION, keyword=[1])
        decisions, _ = review.validate_answer(
            request=req, raw_output=answer([("b0", "IN_SCOPE", "Legal Matters"),
                                            ("b1", "IN_SCOPE", LITIGATION[:40])]))
        self.assertEqual("IN_SCOPE", decisions["b0"]["decision"])

    def test_additions(self):
        self.refused(answer(self.good, [("b9", GUARANTEE[:40])]),
                     "D02_REVIEW_ADDS_A_BLOCK_NOT_IN_THE_REQUEST:b9")
        self.refused(answer(self.good, [("b0", LITIGATION[:40])]),
                     "D02_REVIEW_ADDS_A_MUST_DECIDE_BLOCK:b0")
        self.refused(answer(self.good, [("b3", GUARANTEE[:40]), ("b3", GUARANTEE[:40])]),
                     "D02_REVIEW_BLOCK_ADDED_TWICE:b3")
        self.refused(answer(self.good, [("b3", LEASES[:40])]),
                     "D02_REVIEW_QUOTE_FROM_ANOTHER_BLOCK:b3")

    def test_extra_keys_and_non_json_are_refused(self):
        self.refused(b"not json", "D02_REVIEW_ANSWER_NOT_STRICT_JSON")
        self.refused(json.dumps({"decisions": [], "also_in_scope": [], "note": "x"}),
                     "D02_REVIEW_ANSWER_SHAPE")
        self.refused(json.dumps({"decisions": [{"block_id": "b0", "decision": "IN_SCOPE",
                                                "quote": LITIGATION[:40], "why": "x"}],
                                 "also_in_scope": []}), "D02_REVIEW_DECISION_SHAPE")


class WhatACheckedAnswerCounts(unittest.TestCase):

    def test_in_scope_and_additions_in_document_order(self):
        req = request(LITIGATION, FEES, LEASES, GUARANTEE, keyword=[0, 1])
        decisions, added = review.validate_answer(request=req, raw_output=answer(
            [("b0", "IN_SCOPE", LITIGATION[:40]), ("b1", "OUT_OF_SCOPE", None)],
            [("b3", GUARANTEE[:40])]))
        self.assertEqual((["b0", "b3"], None, []),
                         review.reviewed_blocks(request=req, decisions=decisions, added=added))

    def test_an_unsettled_block_withholds_the_filing(self):
        req = request(LITIGATION, FEES, keyword=[0, 1])
        decisions, added = review.validate_answer(request=req, raw_output=answer(
            [("b0", "IN_SCOPE", LITIGATION[:40]), ("b1", "CANNOT_TELL_FROM_THE_TEXT", FEES[:40])]))
        self.assertEqual((None, review.WITHHELD_REASON, ["b1"]),
                         review.reviewed_blocks(request=req, decisions=decisions, added=added))


class ARegistrationIsCheckedAgainUnderTheCurrentCode(unittest.TestCase):

    def setUp(self):
        self.req = request(LITIGATION, FEES, keyword=[0, 1])
        self.raw = answer([("b0", "IN_SCOPE", LITIGATION[:40]), ("b1", "OUT_OF_SCOPE", None)])
        self.record = review.registered_review(request=self.req, company_id="example",
                                               period_selection_id="sha256:" + "d" * 64,
                                               output=self.raw, mode="RECORDED_TEST_ONLY")

    def test_the_record_re_derives(self):
        self.assertEqual(self.record, review.select_registered_review(records=[self.record],
                                                                      request=self.req))
        self.assertIsNone(review.select_registered_review(records=[], request=self.req))

    def test_a_record_for_another_request_is_refused_not_read_as_unreviewed(self):
        other = request(LITIGATION, LEASES, keyword=[0])
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_REGISTERED_FOR_ANOTHER_REQUEST"):
            review.select_registered_review(records=[self.record], request=other)

    def test_an_edited_count_is_refused_even_when_resealed(self):
        edited = copy.deepcopy(self.record)
        edited["reviewed"]["in_scope"] = ["b0", "b1"]
        body = {key: value for key, value in edited.items() if key != "input_record_id"}
        edited["input_record_id"] = content_hash(value=body)
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_DOES_NOT_RE_DERIVE"):
            review.select_registered_review(records=[edited], request=self.req)

    def test_two_records_for_the_same_request_are_ambiguous(self):
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_REGISTRATION_AMBIGUOUS"):
            review.select_registered_review(records=[self.record, dict(self.record)],
                                            request=self.req)

    def test_an_installed_recorded_copy_is_read_only_for_its_own_position(self):
        from vnext.historical_legal_review import EXPORT_PATH, load_registered_reviews
        from vnext.native_unit_index import evidence_json_bytes
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / EXPORT_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(evidence_json_bytes(self.record))
            position = {"company_id": "example", "period_selection_id": "sha256:" + "d" * 64,
                        "raw_asset_id": self.req["filing"]["raw_asset_id"]}
            self.assertEqual([self.record], load_registered_reviews(data_root=temporary, **position))
            with self.assertRaisesRegex(review.LegalReviewContractError,
                                        "D02_REVIEW_INSTALLED_FOR_ANOTHER_POSITION"):
                load_registered_reviews(data_root=temporary,
                                        **{**position, "raw_asset_id": "sha256:" + "e" * 64})
            with self.assertRaisesRegex(review.LegalReviewContractError, "D02_REVIEW_MODE_CONFLICT"):
                load_registered_reviews(data_root=temporary, mode="LIVE", **position)


class OnARealFilingOnlyItem8Changes(unittest.TestCase):
    """Lumen FY2025: the keyword admits 3382 and 3383 (litigation); 1670 (legal fees) it no longer does.

    1670 names litigation only among the matters counsel advises on, so the
    category-mention rule leaves it out of the keyword part; it stays in the
    pool and among the blocks a review must decide, because it carries the word.
    """

    @classmethod
    def setUpClass(cls):
        from vnext.historical_results import TEXT_SPEC_PATHS
        from vnext.historical_spec_revision import compile_historical_spec_file
        from vnext.historical_text_input import prepare_historical_business_text_input
        from vnext.historical_text_results import prepare_business_text_sources
        from vnext.normal_period_selection import resolve_period_selection
        selection = resolve_period_selection(repo_root=ROOT, company_id="lumen_technologies",
                                             report_end="2025-12-31")
        cls.selection = selection
        cls.args = prepare_historical_business_text_input(
            repo_root=ROOT, company_id="lumen_technologies", metric_id="D02",
            period_selection=selection)["text_arguments"]
        cls.plain = prepare_business_text_sources(metric_id="D02", **cls.args)
        cls.spec = compile_historical_spec_file(repo_root=ROOT, repo_relative_path=TEXT_SPEC_PATHS["D02"],
                                                dependency_specs={})
        cls._built = {}

    def _built_once(self):
        """The request, a synthetic answer and its registration, built on first use.

        Not in setUpClass: a request the route refuses to build - its pool and
        the proposal disagreeing - should fail the cases that need it, each by
        name, and leave the cases that read the pool directly to say why.
        """
        built = type(self)._built
        if not built:
            from vnext.historical_text_results import legal_review_request
            request = legal_review_request(prepared=self.plain, source_arguments=self.args)
            texts = {block["block_id"]: block["text"] for block in request["blocks"]}
            # A synthetic answer: the fees policy out, the two litigation blocks
            # in, every other must-decide block out, and one block without any
            # legal word added - the omission direction the keyword cannot reach.
            decisions = [(identity, "IN_SCOPE", texts[identity][:60]) if identity in ("b3382", "b3383")
                         else (identity, "OUT_OF_SCOPE", None) for identity in request["must_decide"]]
            extra = next(identity for identity in texts if identity not in request["must_decide"]
                         and len(texts[identity]) > 60)
            raw = answer(decisions, [(extra, texts[extra][:40])])
            record = review.registered_review(
                request=request, company_id="lumen_technologies",
                period_selection_id=self.selection["selection_id"], output=raw,
                mode="RECORDED_TEST_ONLY")
            built.update(request=request, texts=texts, extra=extra, raw=raw, record=record)
        return built

    request = property(lambda self: self._built_once()["request"])
    texts = property(lambda self: self._built_once()["texts"])
    extra = property(lambda self: self._built_once()["extra"])
    raw = property(lambda self: self._built_once()["raw"])
    record = property(lambda self: self._built_once()["record"])

    def test_the_pool_is_item_8_s_own_blocks(self):
        """Read without the request, so a pool that took a note's blocks fails here by name."""
        from vnext.historical_text_results import item_8_review_pool
        document = next(iter(self.plain["documents"].values()))
        proposal = next(iter(self.plain["proposals"].values()))
        pool, keyword = item_8_review_pool(
            document=document, raw_bytes=self.args["raw_bytes_by_id"][document["raw_asset_id"]],
            proposal=proposal)
        notes = [(scope["start_block"], scope["end_block_exclusive"])
                 for scope in proposal["checked_ranges"] if scope["section_id"].startswith("NOTE_")]
        self.assertTrue(notes)
        self.assertEqual([], [index for index in pool if any(a <= index < b for a, b in notes)])
        self.assertEqual([3382, 3383], keyword)
        self.assertIn(1670, pool)
        self.assertGreater(len(pool), 1000)

    def reviewed(self, records):
        from vnext.historical_text_results import prepare_business_text_sources
        return prepare_business_text_sources(metric_id="D02", legal_review=records, **self.args)

    @staticmethod
    def d02(prepared):
        return next(iter(prepared["proposals"].values()))["D02"]["candidates"]

    def test_the_request_holds_the_keyword_admissions_and_more(self):
        self.assertTrue({"b1670", "b3382", "b3383"} <= set(self.request["must_decide"]))
        self.assertGreater(len(self.request["blocks"]), len(self.request["must_decide"]))
        # Blocks owned by the incorporated Note 17 captions are not Item 8's to review.
        self.assertFalse({"b3390", "b3400", "b3430"} & set(self.texts))

    def test_no_review_leaves_the_preparation_unchanged(self):
        self.assertEqual(self.plain, self.reviewed(None))
        self.assertEqual(self.plain, self.reviewed([]))

    def test_a_review_replaces_only_the_item_8_excerpts(self):
        prepared = self.reviewed([self.record])
        before, after = self.d02(self.plain), self.d02(prepared)
        self.assertEqual([c for c in before if c["section_id"] != "ITEM_8"],
                         [c for c in after if c["section_id"] != "ITEM_8"])
        self.assertEqual([3382, 3383],
                         [c["block_index"] for c in before if c["section_id"] == "ITEM_8"])
        self.assertEqual(sorted([3382, 3383, int(self.extra[1:])]),
                         [c["block_index"] for c in after if c["section_id"] == "ITEM_8"])
        self.assertTrue(all(c["labels"] == [review.REVIEW_LABEL]
                            for c in after if c["section_id"] == "ITEM_8"))
        coverage = next(iter(prepared["coverages"].values()))
        self.assertEqual(self.record["input_record_id"], coverage["item_8_selection"]["input_record_id"])
        self.assertEqual([], coverage["item_8_selection"]["keyword_admissions_left_out"])
        self.assertNotEqual(next(iter(self.plain["coverages"].values()))["coverage_hash"],
                            coverage["coverage_hash"])

    def test_the_candidate_and_its_evidence_follow_the_review(self):
        from vnext.historical_text_results import build_text_evidence, create_deterministic_text_candidate
        arguments = {"compiled_spec": self.spec, "legal_review": [self.record], **self.args}
        candidate = create_deterministic_text_candidate(**arguments)
        indices = [claim["block_index"] for claim in candidate["selected"].values()]
        self.assertNotIn(1670, indices)
        self.assertIn(int(self.extra[1:]), indices)
        evidence = build_text_evidence(candidate=candidate, **arguments)
        self.assertEqual("PASS", evidence["status"])
        # The same candidate is not evidence for the unreviewed set.
        with self.assertRaises(ValueError):
            build_text_evidence(candidate=candidate, compiled_spec=self.spec, **self.args)

    def test_an_unsettled_review_withholds_the_filing_by_name(self):
        decisions = [(identity, "CANNOT_TELL_FROM_THE_TEXT", self.texts[identity][:40])
                     if identity == "b1670" else
                     (identity, "IN_SCOPE", self.texts[identity][:60]) if identity in ("b3382", "b3383")
                     else (identity, "OUT_OF_SCOPE", None) for identity in self.request["must_decide"]]
        record = review.registered_review(
            request=self.request, company_id="lumen_technologies",
            period_selection_id=self.selection["selection_id"], output=answer(decisions),
            mode="RECORDED_TEST_ONLY")
        with self.assertRaisesRegex(review.LegalReviewUnsettled,
                                    review.WITHHELD_REASON + ":b1670"):
            self.reviewed([record])

    def test_a_review_of_another_request_is_refused(self):
        stale = review.registered_review(
            request={**self.request, "must_decide": self.request["must_decide"][:-1],
                     "request_id": "sha256:" + "f" * 64},
            company_id="lumen_technologies", period_selection_id=self.selection["selection_id"],
            output=answer([(identity, "OUT_OF_SCOPE", None)
                           for identity in self.request["must_decide"][:-1]]),
            mode="RECORDED_TEST_ONLY")
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_REGISTERED_FOR_ANOTHER_REQUEST"):
            self.reviewed([stale])

    def test_a_pool_that_disagrees_with_the_proposal_is_refused(self):
        from vnext.historical_text_results import TextResultV2Error, legal_review_request
        drifted = copy.deepcopy(self.plain)
        proposal = next(iter(drifted["proposals"].values()))
        proposal["D02"]["candidates"] = [c for c in proposal["D02"]["candidates"]
                                         if c["block_index"] != 3382]
        with self.assertRaisesRegex(TextResultV2Error,
                                    "HISTORICAL_D02_REVIEW_POOL_DISAGREES_WITH_THE_PROPOSAL"):
            legal_review_request(prepared=drifted, source_arguments=self.args)

    def _journal(self, record):
        from sec_http import write_immutable_bytes
        from vnext.native_unit_index import evidence_json_bytes
        directory = review.journal_directory(mode=record["mode"], key=record["review_key"])
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (record["input_record_id"][len("sha256:"):] + ".json")
        write_immutable_bytes(path=path, content=evidence_json_bytes(record))
        self.addCleanup(self._remove, path)
        return path

    @staticmethod
    def _remove(path):
        path.unlink()
        for parent in path.parents:
            if parent.name == "RECORDED_TEST_ONLY" or any(parent.iterdir()):
                break
            parent.rmdir()

    def _input(self, **mode):
        from vnext.historical_text_input import prepare_historical_business_text_input
        return prepare_historical_business_text_input(
            repo_root=ROOT, company_id="lumen_technologies", metric_id="D02",
            period_selection=self.selection, **mode)

    def test_the_input_carries_a_registered_review_only_in_its_mode(self):
        self._journal(self.record)
        recorded = self._input(review_mode="RECORDED_TEST_ONLY")
        self.assertEqual([self.record], recorded["text_arguments"]["legal_review"])
        self.assertEqual({key: self.record[key] for key in ("input_record_id", "request_id", "mode")},
                         recorded["input_binding"]["registered_item_8_review"])
        # A batch reads LIVE, and this registration is a test's: the position
        # is built exactly as if no review existed.
        default = self._input()
        self.assertNotIn("legal_review", default["text_arguments"])
        self.assertNotIn("registered_item_8_review", default["input_binding"])

    def test_a_position_whose_only_review_is_stale_is_refused_at_input(self):
        stale = review.registered_review(
            request={**self.request, "request_id": "sha256:" + "f" * 64},
            company_id="lumen_technologies", period_selection_id=self.selection["selection_id"],
            output=self.raw, mode="RECORDED_TEST_ONLY")
        self._journal(stale)
        with self.assertRaisesRegex(review.LegalReviewContractError,
                                    "D02_REVIEW_REGISTERED_FOR_ANOTHER_REQUEST"):
            self._input(review_mode="RECORDED_TEST_ONLY")

    def test_c02_takes_no_review(self):
        from vnext.historical_text_results import TextResultV2Error, prepare_business_text_sources
        with self.assertRaisesRegex(TextResultV2Error, "HISTORICAL_TEXT_LEGAL_REVIEW_IS_D02_ONLY"):
            prepare_business_text_sources(metric_id="C02", legal_review=[self.record], **self.args)


if __name__ == "__main__":
    unittest.main()
