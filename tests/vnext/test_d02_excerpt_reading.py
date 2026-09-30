"""D02 excerpt readings: exact coverage of the packet, and the value they render.

A reading judges every block of a position's packet - each excerpt taken,
each block skipped inside Item 3 and the incorporated scopes, and each
heading that names contingencies, legal proceedings, litigation or
commitments. These cases hold the comparison to what it claims: a block not
judged, judged twice, judged on other text or with a verdict of the wrong kind
stops the reading rather than reading as agreement; a wrong block on either
side, or a missed heading, is a disagreement.

On a saved filing the packet is the route's own selection: Pfizer's FY2025
packet puts the two blocks already registered as keyword-proxy errors (2175,
2240) in front of the reader as Item 8 excerpts, beside the two Item 8 blocks
that are right (2302, 2351), and its skipped blocks inside Note 16A are the
running heads and page numbers the earlier reading found there.

Each committed reading carries the text of every block it judged, so the
value it accepted is checked without the filing: its excerpts, in order and
joined as the renderer joins them, are the value named by digest.
"""
import hashlib
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_d02_excerpts as reader


def sha(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def packet():
    taken = [{"i": 10, "scope": "ITEM_3", "text": "Item 3 text.", "text_sha256": sha("Item 3 text.")},
             {"i": 90, "scope": "ITEM_8", "text": "Keyword text.", "text_sha256": sha("Keyword text.")}]
    skipped = [{"i": 11, "scope": "ITEM_3", "text": "12", "text_sha256": sha("12")}]
    headings = [{"i": 80, "text": "Commitments and Contingencies",
                 "text_sha256": sha("Commitments and Contingencies")}]
    return {"taken": taken, "skipped": skipped, "headings": headings}


def reading(verdicts=None):
    verdicts = verdicts or {}
    rows = []
    for kind, key in (("TAKEN", "taken"), ("SKIPPED", "skipped"), ("HEADING", "headings")):
        for order, row in enumerate(packet()[key]):
            default = {"TAKEN": "DISCLOSURE", "SKIPPED": "CORRECTLY_SKIPPED",
                       "HEADING": "REACHED"}[kind]
            rows.append({"kind": kind, "i": row["i"], "order": order, "text": row["text"],
                         "text_sha256": row["text_sha256"],
                         "verdict": verdicts.get((kind, row["i"]), default)})
    return {"position": "constructed:2025-12-31", "judgements": rows}


class ACompleteReadingTest(unittest.TestCase):

    def test_every_block_judged_right_agrees(self):
        answer = reader.read_position(packet=packet(), reading=reading())
        self.assertEqual("READING_AGREES", answer["verdict"])
        self.assertEqual({"taken": 2, "skipped": 1, "context": 0, "headings": 1,
                          "taken_through_item_8": 1, "covered_elsewhere": 0}, answer["counts"])

    def test_a_wrong_block_on_either_side_disagrees(self):
        cases = {("TAKEN", 90): "wrongly_taken", ("SKIPPED", 11): "wrongly_skipped",
                 ("HEADING", 80): "missed_headings"}
        wrong = {"TAKEN": "NOT_DISCLOSURE", "SKIPPED": "WRONGLY_SKIPPED", "HEADING": "MISSED"}
        for key, problem in cases.items():
            with self.subTest(key=key):
                answer = reader.read_position(packet=packet(),
                                              reading=reading({key: wrong[key[0]]}))
                self.assertEqual("READING_DISAGREES", answer["verdict"])
                self.assertEqual([key[1]], [row["i"] for row in answer["problems"][problem]])

    def test_a_matter_the_value_states_elsewhere_is_not_a_miss(self):
        judged = reading({("SKIPPED", 11): "COVERED_ELSEWHERE"})
        judged["judgements"][2]["covered_by"] = [10]
        answer = reader.read_position(packet=packet(), reading=judged)
        self.assertEqual("READING_AGREES", answer["verdict"])
        self.assertEqual([{"i": 11, "kind": "SKIPPED", "covered_by": [10]}],
                         answer["covered_elsewhere"])

    def test_a_heading_outside_d02_is_not_a_miss(self):
        answer = reader.read_position(packet=packet(), reading=reading({("HEADING", 80): "NOT_D02"}))
        self.assertEqual("READING_AGREES", answer["verdict"])


class AReadingThatDidNotSeeTheBlockTest(unittest.TestCase):

    def refused(self, judged, reason):
        with self.assertRaises(SystemExit) as caught:
            reader.read_position(packet=packet(), reading=judged)
        self.assertTrue(str(caught.exception).startswith(reason), str(caught.exception))

    def test_an_unjudged_block_stops_the_reading(self):
        judged = reading()
        judged["judgements"] = [row for row in judged["judgements"] if row["kind"] != "SKIPPED"]
        self.refused(judged, "D02_PACKET_BLOCKS_NOT_JUDGED")

    def test_a_block_outside_the_packet_stops_the_reading(self):
        judged = reading()
        judged["judgements"].append({**judged["judgements"][0], "i": 999})
        self.refused(judged, "D02_JUDGED_BLOCK_NOT_IN_THE_PACKET")

    def test_a_block_judged_twice_stops_the_reading(self):
        judged = reading()
        judged["judgements"].append(dict(judged["judgements"][0]))
        self.refused(judged, "D02_BLOCK_JUDGED_TWICE")

    def test_a_judgement_of_other_text_stops_the_reading(self):
        judged = reading()
        judged["judgements"][0]["text_sha256"] = sha("Something the filing does not say")
        self.refused(judged, "D02_JUDGED_TEXT_CHANGED")

    def test_carried_text_must_be_the_text_judged(self):
        judged = reading()
        judged["judgements"][0]["text"] = "Something the filing does not say"
        self.refused(judged, "D02_JUDGED_TEXT_CHANGED")

    def test_covered_elsewhere_must_cite_an_excerpt(self):
        for cited in ([], [11], [999]):
            with self.subTest(cited=cited):
                judged = reading({("SKIPPED", 11): "COVERED_ELSEWHERE"})
                judged["judgements"][2]["covered_by"] = cited
                self.refused(judged, "D02_COVERED_BY_IS_NOT_A_TAKEN_BLOCK")

    def test_a_verdict_of_the_wrong_kind_stops_the_reading(self):
        judged = reading({("TAKEN", 10): "CORRECTLY_SKIPPED"})
        self.refused(judged, "D02_VERDICT_INVALID")


class ThePacketIsTheRouteSelectionTest(unittest.TestCase):
    """Pfizer FY2025 from the saved filing: the known answer is in front of the reader."""

    @classmethod
    def setUpClass(cls):
        document, proposal, candidate = reader.route_selection(
            source_root=ROOT, company_id="pfizer", report_end="2025-12-31")
        cls.document = document
        cls.packet = reader.make_packet(document=document, proposal=proposal, candidate=candidate)
        cls.candidate = candidate

    def test_the_taken_blocks_are_the_candidate_s_excerpts_in_order(self):
        excerpts = sorted(self.candidate["selected"].values(), key=lambda claim: claim["order"])
        self.assertEqual([claim["text"] for claim in excerpts],
                         [row["text"] for row in self.packet["taken"]])

    def test_the_registered_keyword_errors_are_item_8_excerpts(self):
        item_8 = [row["i"] for row in self.packet["taken"] if row["scope"] == "ITEM_8"]
        self.assertEqual([2175, 2240, 2302, 2351], item_8)

    def test_the_skipped_blocks_are_inside_the_narrow_scopes_and_not_taken(self):
        taken = {row["i"] for row in self.packet["taken"]}
        narrow = [r for r in self.packet["ranges"] if r["section_id"] not in ("ITEM_1A", "ITEM_8")]
        for row in self.packet["skipped"]:
            self.assertNotIn(row["i"], taken)
            self.assertTrue(any(r["start_block"] <= row["i"] < r["end_block_exclusive"]
                                for r in narrow))
        inside = sum(r["end_block_exclusive"] - r["start_block"] for r in narrow)
        self.assertEqual(inside, len(self.packet["skipped"])
                         + sum(1 for row in self.packet["taken"] if row["scope"] != "ITEM_8"))

    def test_the_note_16a_skips_are_page_furniture(self):
        texts = {row["text"] for row in self.packet["skipped"]}
        self.assertEqual(25, len(self.packet["skipped"]))
        self.assertTrue({"Pfizer Inc.", "2025 Form 10-K"} <= texts)

    def test_every_heading_names_one_of_the_definition_s_words_and_is_not_a_link(self):
        blocks = self.document["blocks"]
        for row in self.packet["headings"]:
            self.assertRegex(row["text"], reader.HEADING_WORDS)
            self.assertFalse(blocks[row["i"]].get("linked"))
        self.assertIn(3821, [row["i"] for row in self.packet["headings"]])


class CommittedReadingsRenderTheirValuesTest(unittest.TestCase):
    """Without the filing: each committed reading's excerpts are the value it accepted."""

    def test_each_accepted_position_is_the_value_its_reading_renders(self):
        acceptance = ROOT / "docs/evidence/issue47_history/content-acceptance/d02-older-years-read.json"
        if not acceptance.exists():
            self.skipTest("no committed older-year D02 reading yet")
        body = json.loads(acceptance.read_text(encoding="utf-8"))
        for label, row in body["per_position"].items():
            with self.subTest(label):
                path = ROOT / row["reading"]
                self.assertEqual(row["reading_sha256"],
                                 "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
                judged = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(row["value_sha256"], reader.rendered_value_sha256(judged))
                for judgement in judged["judgements"]:
                    self.assertEqual(judgement["text_sha256"], sha(judgement["text"]))
                wrong = [j for j in judged["judgements"]
                         if j["verdict"] in ("NOT_DISCLOSURE", "WRONGLY_SKIPPED", "MISSED")]
                self.assertEqual(row["verdict"] == "MATCH", not wrong)


if __name__ == "__main__":
    unittest.main()
