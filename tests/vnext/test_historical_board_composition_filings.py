"""C02 composition facts on the saved governance filings, checked both ways.

``tools/read_c02_composition.py`` recomputes each position's selection through
the historical route and compares it with the two-direction reading kept in
``docs/evidence/issue47_history/c02-composition-facts/judgements/``: nothing
selected may be judged not a composition fact, and nothing judged a
composition fact may be left out unless selected blocks already state it. The
reading binds each block by its text, so it cannot be applied to text it did
not see.

Where readers split on a class of block, the executor's adjudication decides
(``adjudication.json``). The cases here also hold each adjudication to its
class: a tenure decision must be on a tenure field, and a card-name decision
on a block the route takes as a card's director, whose surname the same
reader wrote in the reason for a card field the route takes.

These cases read ten real filings and so belong to the source-material tier.
"""
from __future__ import annotations

import json
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_c02_composition as reading
from vnext.historical_board_composition import _strip_name, board_composition_facts
from vnext.historical_spec_revision import SUCCESSOR_MAX_ITEMS

READINGS = sorted((ROOT / "docs/evidence/issue47_history/c02-composition-facts/judgements").glob("*.json"))


class EveryReadPositionAgreesWithTheRoute(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.positions = {}
        for path in READINGS:
            record = json.loads(path.read_text(encoding="utf-8"))
            company_id, report_end = record["position"].rsplit(":", 1)
            document, chosen, candidate = reading.route_selection(
                repo_root=ROOT, company_id=company_id, report_end=report_end)
            cls.positions[record["position"]] = (record, document, chosen, candidate)
        cls.adjudications = reading.load_adjudications()

    def test_there_is_a_reading_for_every_reachable_position(self):
        self.assertEqual(10, len(self.positions))

    def test_nothing_taken_is_judged_outside_the_meaning_and_nothing_stated_is_missed(self):
        for position, (record, document, chosen, _candidate) in self.positions.items():
            with self.subTest(position):
                answer = reading.read_position(document=document, chosen=chosen, reading=record,
                                               adjudications=self.adjudications)
                self.assertEqual("READING_AGREES", answer["verdict"], answer["problems"])

    def test_each_adjudication_stays_inside_its_class(self):
        by_position = {}
        for (position, index), row in self.adjudications.items():
            by_position.setdefault(position, []).append(row)
        self.assertTrue(by_position)
        for position, rows in by_position.items():
            record, document, _chosen, _candidate = self.positions[position]
            labels = {c["block_index"]: c["labels"]
                      for c in board_composition_facts(document=document)["candidates"]}
            reasons = {row["i"]: row.get("why", "") for row in [*record["selected"], *record["pool_facts"],
                                                                *record.get("outside_pool_facts", [])]}
            for row in rows:
                text = document["blocks"][row["i"]]["text"]
                with self.subTest(position=position, block=row["i"], rule=row["rule"]):
                    self.assertEqual(reading.text_sha256(text), row["text_sha256"])
                    if row["rule"] == "CARD_TENURE_FIELD":
                        self.assertEqual("NOT", row["decision"])
                        self.assertRegex(text, r"(?i)^\s*(?:director since|joined the board)\s*:?")
                        self.assertNotIn(row["i"], labels)
                    else:
                        self.assertEqual(("CARD_SUBJECT_NAME", "FACT"), (row["rule"], row["decision"]))
                        self.assertIn("DIRECTOR_NAME", labels.get(row["i"], []))
                        for cited in row["fields_whose_reason_names_it"]:
                            self.assertIn(cited, labels)
                            self.assertRegex(reasons[cited], r"(?i)\b" + re.escape(row["surname"]) + r"\b")

    def test_the_route_uses_the_successor_bound_and_the_frozen_candidate_shape(self):
        for position, (_record, _document, chosen, candidate) in self.positions.items():
            with self.subTest(position):
                self.assertEqual("BOARD_DISCLOSURE_EXCERPTS_V1", candidate["method"])
                self.assertLessEqual(len(chosen), SUCCESSOR_MAX_ITEMS)
                self.assertEqual(sorted(chosen), [c["block_index"] for c in sorted(
                    candidate["selected"].values(), key=lambda c: c["order"])])


class AReadingRefusesTextItDidNotSee(unittest.TestCase):

    def test_a_changed_block_text_is_not_judged(self):
        path = READINGS[0]
        record = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = record["position"].rsplit(":", 1)
        document, chosen, _candidate = reading.route_selection(repo_root=ROOT, company_id=company_id,
                                                               report_end=report_end)
        index = chosen[0]
        altered = json.loads(json.dumps(record))
        for row in altered["selected"]:
            if row["i"] == index:
                row["text_sha256"] = "sha256:" + "0" * 64
        answer = reading.read_position(document=document, chosen=chosen, reading=altered)
        self.assertIn(index, answer["problems"]["text_changed"])

    def test_an_unjudged_selected_block_is_reported_not_assumed(self):
        path = READINGS[0]
        record = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = record["position"].rsplit(":", 1)
        document, chosen, _candidate = reading.route_selection(repo_root=ROOT, company_id=company_id,
                                                               report_end=report_end)
        altered = json.loads(json.dumps(record))
        altered["selected"] = [row for row in altered["selected"] if row["i"] != chosen[0]]
        altered["pool_facts"] = [row for row in altered["pool_facts"] if row["i"] != chosen[0]]
        answer = reading.read_position(document=document, chosen=chosen, reading=altered)
        self.assertIn(chosen[0], answer["problems"]["unread"])

    def test_the_selector_is_the_route_s_not_a_copy(self):
        # The reading tool recomputes the selection through the route; this
        # checks that what it recomputes is what the successor module returns
        # for the same governance document, so the reading tests the rule the
        # Run uses and not a second implementation.
        path = READINGS[0]
        record = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = record["position"].rsplit(":", 1)
        document, chosen, _candidate = reading.route_selection(repo_root=ROOT, company_id=company_id,
                                                               report_end=report_end)
        direct = [c["block_index"] for c in board_composition_facts(document=document)["candidates"]]
        self.assertEqual(sorted(chosen), direct)


if __name__ == "__main__":
    unittest.main()
