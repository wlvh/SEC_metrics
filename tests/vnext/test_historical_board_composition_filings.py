"""C02 composition facts on the saved governance filings, checked both ways.

``tools/read_c02_composition.py`` recomputes each position's selection through
the historical route and compares it with the two-direction reading kept in
``docs/evidence/issue47_history/c02-composition-facts/judgements/``: nothing
selected may be judged not a composition fact, and nothing judged a
composition fact may be left out unless selected blocks already state it. The
reading binds each block by its text, so it cannot be applied to text it did
not see.

Where readers split on a class of block, the executor's adjudication decides
(``adjudication.json``, written by ``c02-composition-facts/adjudicate.py``
from the readings and the documents alone, never from the route's selection).
The cases here hold the file to its rules: on each latest position it must be
exactly what the rules decide on that document and reading, nothing added and
nothing left out; on an older position (whose filing is not in this checkout)
each decision must be bound to the text its reading saw. A position whose
reading disagrees with today's selection must be a registered disagreement in
``known_result_defects.json``, block for block, so a repair or a regression
shows up here as a changed set rather than as silence.

These cases read ten real filings and so belong to the source-material tier.
"""
from __future__ import annotations

import importlib.util
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_c02_composition as reading
from vnext.historical_board_composition_v3 import board_composition_facts
from vnext.historical_spec_revision import SUCCESSOR_MAX_ITEMS

from contextlib import ExitStack  # noqa: E402
from vnext.historical_xbrl_parse import xbrl_parsed_once  # noqa: E402

# Each document's inline XBRL is parsed once for the module
# (historical_xbrl_parse): the cases' chains parse the same filings again at
# nearly every stage (121 parses of 20 documents here, measured), and nothing a
# case does can change a parsed document.
_PARSED_ONCE = ExitStack()


def setUpModule():
    _PARSED_ONCE.enter_context(xbrl_parsed_once())


def tearDownModule():
    _PARSED_ONCE.close()


READINGS = sorted((ROOT / "docs/evidence/issue47_history/c02-composition-facts/judgements").glob("*.json"))
OLDER_READINGS = sorted((ROOT / "docs/evidence/issue47_history/c02-older-years/judgements").glob("*.json"))
DEFECTS = ROOT / "docs/evidence/issue47_history/known_result_defects.json"


def _adjudicator():
    path = ROOT / "docs/evidence/issue47_history/c02-composition-facts/adjudicate.py"
    spec = importlib.util.spec_from_file_location("c02_adjudicate_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _judged_once(record, key):
    """Blocks a reading judges in ``key`` and in none of its other lists."""
    lists = {name: {row["i"] for row in record.get(name, [])}
             for name in ("selected", "pool_facts", "outside_pool_facts", "supplementary")}
    return {i for i in lists[key] if not any(i in blocks for name, blocks in lists.items() if name != key)}


def _registered_disagreements():
    """position -> the selection problems its open C02 defect records."""
    out = {}
    for row in json.loads(DEFECTS.read_text(encoding="utf-8"))["defects"]:
        if row.get("metric_id") == "C02" and "selection_problems" in row:
            out[row["company_id"] + ":" + row["period_end"]] = row["selection_problems"]
    return out


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

    def test_each_position_agrees_or_is_a_registered_disagreement(self):
        registered = _registered_disagreements()
        for position, (record, document, chosen, _candidate) in self.positions.items():
            with self.subTest(position):
                answer = reading.read_position(document=document, chosen=chosen, reading=record,
                                               adjudications=self.adjudications)
                problems = {kind: sorted(item["i"] if isinstance(item, dict) else item for item in items)
                            for kind, items in answer["problems"].items() if items}
                self.assertEqual(registered.get(position, {}), problems)

    def test_the_adjudication_is_exactly_what_its_rules_decide_here(self):
        adjudicate = _adjudicator()
        written = json.loads(reading.ADJUDICATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual({name: {"decision": decision, "reason": reason}
                          for name, (decision, reason) in adjudicate.RULES.items()}, written["rules"])
        for position, (record, document, _chosen, _candidate) in self.positions.items():
            with self.subTest(position):
                self.assertEqual(adjudicate.decisions_for(position, document, record),
                                 [row for row in written["decisions"] if row["position"] == position])

    def test_an_older_decision_is_bound_to_the_text_its_reading_saw(self):
        written = json.loads(reading.ADJUDICATION_PATH.read_text(encoding="utf-8"))
        readings = {}
        for path in OLDER_READINGS:
            record = json.loads(path.read_text(encoding="utf-8"))
            seen = {row["i"]: row["text_sha256"] for row in [*record["selected"], *record["pool_facts"],
                                                              *record.get("outside_pool_facts", []),
                                                              *record.get("pool", [])]}
            readings[record["position"]] = seen
        older = [row for row in written["decisions"] if row["position"] in readings]
        self.assertTrue(older)
        for row in older:
            with self.subTest(position=row["position"], block=row["i"], rule=row["rule"]):
                seen = readings[row["position"]]
                if row["reader_verdict"] == "NOT_READ":
                    self.assertNotIn(row["i"], seen)
                else:
                    self.assertEqual(seen[row["i"]], row["text_sha256"])

    def test_the_route_uses_the_successor_bound_and_the_frozen_candidate_shape(self):
        for position, (_record, _document, chosen, candidate) in self.positions.items():
            with self.subTest(position):
                self.assertEqual("BOARD_DISCLOSURE_EXCERPTS_V1", candidate["method"])
                self.assertLessEqual(len(chosen), SUCCESSOR_MAX_ITEMS)
                self.assertEqual(sorted(chosen), [c["block_index"] for c in sorted(
                    candidate["selected"].values(), key=lambda c: c["order"])])


class AnAdjudicatedFactIsMissedUnlessSomethingSelectedStatesIt(unittest.TestCase):
    """A FACT decision on a block the reading left out counts against the selection."""

    POSITION = "example_company:2025-12-31"

    def setUp(self):
        texts = ["The Board has nine directors.", "The roles of Chairman and CEO are separate.",
                 "Our Chairman and our CEO are two different people."]
        self.document = {"blocks": [{"text": text, "linked": False} for text in texts]}
        self.record = {"position": self.POSITION,
                       "selected": [{"i": 0, "verdict": "FACT", "why": "board size",
                                     "text_sha256": reading.text_sha256(texts[0])}],
                       "pool_facts": [],
                       "pool": [{"i": i, "text_sha256": reading.text_sha256(text)} for i, text in enumerate(texts)]}
        self.adjudications = {(self.POSITION, 1): {
            "position": self.POSITION, "i": 1, "text_sha256": reading.text_sha256(texts[1]),
            "rule": "CHAIR_CEO_STRUCTURE", "decision": "FACT", "redundant_with": [2]}}

    def _problems(self, chosen):
        answer = reading.read_position(document=self.document, chosen=chosen, reading=self.record,
                                       adjudications=self.adjudications)
        return {kind: [item["i"] if isinstance(item, dict) else item for item in items]
                for kind, items in answer["problems"].items() if items}

    def test_the_left_out_block_is_missed(self):
        self.assertEqual({"missed": [1]}, self._problems([0]))

    def test_it_is_not_missed_when_selected(self):
        self.assertEqual({}, self._problems([0, 1]))

    def test_it_is_not_missed_when_a_block_stating_the_same_fact_is_selected(self):
        # The reading left block 2 out too, so selecting it is a wrong take;
        # what matters here is that block 1 is no longer reported missed.
        self.assertNotIn("missed", self._problems([0, 2]))

    def test_a_decision_on_text_it_was_not_made_for_is_refused(self):
        self.document["blocks"][1]["text"] = "Our Chairman is also our CEO."
        self.assertEqual({"text_changed": [1]}, self._problems([0]))


class ADatedRoleChangeIsCoveredOnlyByTheSameChange(unittest.TestCase):
    """A reader's citation the adjudication rejects does not cover the block (DATED_ROLE_CHANGE).

    #28's content check of Salesforce FY2026 found block 933 - the day Mr. Roos
    took up the Governance Committee's chair - counted as covered by blocks that
    give the current chair and the quarters a fee covers.
    """

    POSITION = "example_company:2025-12-31"
    TEXTS = ["Mr. Roos is the Chair of the Governance Committee.",
             "On March 21, 2025, Mr. Roos assumed the role of Chair of the Governance Committee.",
             "Cash fees paid to Mr. Roos relate to his service as Chair of the Governance Committee for the second, "
             "third, and fourth quarters of fiscal 2025.",
             "In 2019, Mr. Lee became Chair of the Audit Committee.",
             "On April 10, 2025, Ms. Park became Chairman of the Board.",
             "Ms. Park was appointed Chairman in April 2025.",
             "On March 21, 2025, Ms. Washington stepped down as Chair of the Governance Committee."]

    def setUp(self):
        sha = [reading.text_sha256(text) for text in self.TEXTS]
        self.document = {"blocks": [{"text": text, "linked": False} for text in self.TEXTS]}
        self.record = {"position": self.POSITION,
                       "selected": [{"i": i, "verdict": "FACT", "why": "", "text_sha256": sha[i]} for i in (0, 4)],
                       "pool_facts": [{"i": 1, "verdict": "MIXED", "why": "", "text_sha256": sha[1],
                                       "redundant_with": [0, 2]},
                                      {"i": 3, "verdict": "MIXED", "why": "", "text_sha256": sha[3],
                                       "redundant_with": [0]},
                                      {"i": 5, "verdict": "MIXED", "why": "", "text_sha256": sha[5],
                                       "redundant_with": [0]}],
                       "pool": [{"i": i, "text_sha256": h} for i, h in enumerate(sha)]}

    def _decisions(self):
        return {row["i"]: row for row in _adjudicator().decisions_for(self.POSITION, self.document, self.record)}

    def test_the_rule_decides_what_states_each_change(self):
        decided = self._decisions()
        # Neither the current chair nor the fee quarters give Mr. Roos's change.
        self.assertEqual(("DATED_ROLE_CHANGE", "FACT", []),
                         (decided[1]["rule"], decided[1]["decision"], decided[1]["redundant_with"]))
        self.assertEqual([0, 2], decided[1]["reader_redundant_with"])
        # The same change with a more precise date covers a month.
        self.assertEqual([4], decided[5]["redundant_with"])
        # A change before the year is tenure, as a join is.
        self.assertNotIn(3, decided)

    def _problems(self, chosen, adjudications):
        answer = reading.read_position(document=self.document, chosen=chosen, reading=self.record,
                                       adjudications=adjudications)
        return {kind: [item["i"] if isinstance(item, dict) else item for item in items]
                for kind, items in answer["problems"].items() if items}

    def test_the_rejected_citation_no_longer_covers_the_block(self):
        decided = {(self.POSITION, i): row for i, row in self._decisions().items()}
        self.assertEqual({}, self._problems([0, 4], {}))
        self.assertEqual({"missed": [1]}, self._problems([0, 4], decided))
        self.assertEqual({}, self._problems([0, 1, 4], decided))


class AJoinInTheYearIsCoveredOnlyByTheSamePersonsJoin(unittest.TestCase):
    """A roster of the sitting directors does not state when one of them joined (JOIN_IN_THE_YEAR).

    #28's content check of Paramount FY2025 found the biographies' own-board
    start dates counted covered by the roster that names the ten directors.
    """

    POSITION = "example_company:2025-12-31"
    TEXTS = ["Our Board is currently comprised of three members: Barbara Byrne, Andrew Campion and Ann Lee.",
             "Ms. Byrne has served as a member of our Board since August 2025.",
             "Mr. Campion has served as a member of our Board since January 2026.",
             "Ms. Byrne joined our Board on August 7, 2025.",
             "Pursuant to our policy (other than Mr. Morfit, who waived receipt of the grant), upon their appointment "
             "to the Board in July 2025, Ms. Chang and Mr. Kirk each received a prorated grant.",
             "Mr. Morfit was appointed to the Board in July 2025."]

    def setUp(self):
        sha = [reading.text_sha256(text) for text in self.TEXTS]
        self.document = {"blocks": [{"text": text, "linked": False} for text in self.TEXTS]}
        self.record = {"position": self.POSITION,
                       "selected": [{"i": 0, "verdict": "FACT", "why": "", "text_sha256": sha[0]}],
                       "pool_facts": [{"i": i, "verdict": "MIXED", "why": "", "text_sha256": sha[i], "redundant_with": [0]}
                                      for i in (1, 2, 4)],
                       "pool": [{"i": i, "text_sha256": h} for i, h in enumerate(sha)]}

    def test_the_rule_decides_what_states_each_join(self):
        decided = {row["i"]: row for row in _adjudicator().decisions_for(self.POSITION, self.document, self.record)}
        # The same person's join, more precisely dated, covers the month.
        self.assertEqual([3], decided[1]["redundant_with"])
        self.assertEqual([], decided[2]["redundant_with"])
        # The joiners are the people the join is about, not a name further back.
        self.assertEqual([], decided[4]["redundant_with"])
        self.assertEqual("JOIN_IN_THE_YEAR", decided[2]["rule"])

    def test_a_roster_no_longer_covers_the_join(self):
        decided = {(self.POSITION, row["i"]): row
                   for row in _adjudicator().decisions_for(self.POSITION, self.document, self.record)}

        def missed(chosen, adjudications):
            answer = reading.read_position(document=self.document, chosen=chosen, reading=self.record,
                                           adjudications=adjudications)
            return sorted(item["i"] for item in answer["problems"]["missed"])

        # The reader's citation of the roster covered every join.
        self.assertEqual([], missed([0, 3], {}))
        # Under the rule only the same person's join covers one: block 3 covers
        # Ms. Byrne's; Mr. Campion's, the grant sentence's and Mr. Morfit's own
        # joins are stated nowhere else.
        self.assertEqual([2, 4, 5], missed([0, 3], decided))


class ATermEndingIsCoveredOnlyByTheSameDeparture(unittest.TestCase):
    """A named director's term ending at a meeting is a departure (TERM_END_AT_A_MEETING).

    Lumen's director-pay footnotes state each departure this way; the FY2024
    reader cited the unnamed "three current directors will retire" and the
    pay rows under a "Retiring Directors" heading as covering the one that
    names the three (c02-selector-repairs/ section 17).
    """

    POSITION = "example_company:2024-12-31"
    TEXTS = ["At the 2025 annual meeting, the following three current directors will retire from the Board:",
             "(6)The terms of Mr. Brown, Mr. Clontz and Ms. Siegel will end in connection with the election of "
             "directors at the 2025 annual meeting.",
             "(7)Mr. Roberts’ term ended in connection with the election of directors at the 2024 annual meeting.",
             "At the 2024 annual meeting, Michael Roberts, retired from the Board, after 13 years of service.",
             "Mr. Hanks retired from the Board at the 2023 annual meeting.",
             "5Mr. Hanks’ term will end immediately following the 2024 annual shareholders meeting.",
             "Mr. Smith, a nominee, presently serves on our Board and his term of office will expire at the Annual "
             "Meeting.",
             "Their terms will end at the 2025 annual meeting.",
             "The Committee’s term will end at the 2025 annual meeting."]

    def setUp(self):
        sha = [reading.text_sha256(text) for text in self.TEXTS]
        self.document = {"blocks": [{"text": text, "linked": False} for text in self.TEXTS]}
        self.record = {"position": self.POSITION,
                       "selected": [{"i": i, "verdict": "FACT", "why": "", "text_sha256": sha[i]} for i in (0, 3)],
                       "pool_facts": [{"i": 1, "verdict": "FACT", "why": "", "text_sha256": sha[1],
                                       "redundant_with": [0]},
                                      {"i": 2, "verdict": "FACT", "why": "", "text_sha256": sha[2],
                                       "redundant_with": [3]}],
                       # Block 5 is outside the pool: no reader looked at it.
                       "pool": [{"i": i, "text_sha256": h} for i, h in enumerate(sha) if i != 5]}

    def test_the_rule_decides_what_states_each_departure(self):
        decided = {row["i"]: row for row in _adjudicator().decisions_for(self.POSITION, self.document, self.record)}
        # The unnamed retirement sentence names none of the three.
        self.assertEqual([], decided[1]["redundant_with"])
        self.assertEqual("TERM_END_AT_A_MEETING", decided[1]["rule"])
        # The reader's citation of Mr. Roberts' own retirement stands.
        self.assertNotIn(2, decided)
        # No reader looked at block 5; Mr. Hanks' 2023 retirement is another departure.
        self.assertEqual(("FACT", "NOT_READ", []),
                         (decided[5]["decision"], decided[5]["reader_verdict"], decided[5]["redundant_with"]))
        # A nominee's term ending at the meeting, a term nobody is named for and
        # a body's term are not departures.
        for index in (6, 7, 8):
            self.assertNotIn(index, decided)

    def test_an_unnamed_retirement_no_longer_covers_the_footnote(self):
        decided = {(self.POSITION, row["i"]): row
                   for row in _adjudicator().decisions_for(self.POSITION, self.document, self.record)}

        def missed(chosen, adjudications):
            answer = reading.read_position(document=self.document, chosen=chosen, reading=self.record,
                                           adjudications=adjudications)
            return sorted(item["i"] for item in answer["problems"]["missed"])

        self.assertEqual([], missed([0, 3], {}))
        self.assertEqual([1, 5], missed([0, 3], decided))
        self.assertEqual([], missed([0, 1, 3, 5], decided))


class ANomineesNoCommitteeFieldIsNotAFact(unittest.TestCase):
    """"Committees: N/A" on a not-yet-director nominee's card (NOMINEE_CARD_NO_COMMITTEE).

    Paramount's FY2022 reader took the field on Dawn Ostroff's card (block 819);
    its FY2024 readers left out the same field on three new nominees' cards.
    The two cards' fields are Paramount's FY2022 blocks 816-820 and 823-828.
    """

    POSITION = "example_company:2022-12-31"
    TEXTS = ["Director Nominee", "Age: 62", "Director since: N/A", "Committees: N/A", "DAWN OSTROFF",
             "Director", "Age: 63", "Director since: 2019", "Committees: N/A", "CHARLES E. PHILLIPS, JR."]

    def test_only_the_nominees_field_is_decided(self):
        sha = [reading.text_sha256(text) for text in self.TEXTS]
        document = {"blocks": [{"text": text, "linked": False} for text in self.TEXTS]}
        record = {"position": self.POSITION, "selected": [],
                  "pool_facts": [{"i": i, "verdict": "FACT", "why": "", "text_sha256": sha[i]} for i in (3, 8)],
                  "pool": [{"i": i, "text_sha256": h} for i, h in enumerate(sha)]}
        decided = {row["i"]: row for row in _adjudicator().decisions_for(self.POSITION, document, record)}
        self.assertEqual(("NOMINEE_CARD_NO_COMMITTEE", "NOT", "FACT"),
                         (decided[3]["rule"], decided[3]["decision"], decided[3]["reader_verdict"]))
        # A sitting director's "N/A" says that director serves on no committee.
        self.assertNotIn(8, decided)


class ACommitteesRelationshipDeterminationIsAFact(unittest.TestCase):
    """The NCG Committee's determination about each director's relationships (INDEPENDENCE_RELATIONSHIP_DETERMINATION).

    Macy's FY2023 reader left the sentence out (block 1107); its FY2024,
    FY2025 and FY2026 readers took it.
    """

    POSITION = "example_company:2022-12-31"
    TEXT = ("With respect to each Non-Employee Director, the NCG Committee determined that neither the director nor any "
            "immediate family member was employed by a company providing goods or services to Macy’s or the amounts "
            "involved were below the monetary thresholds set forth in the Standards for Director Independence.")

    def decided(self, verdict):
        sha = reading.text_sha256(self.TEXT)
        document = {"blocks": [{"text": self.TEXT, "linked": False}]}
        record = {"position": self.POSITION, "selected": [{"i": 0, "verdict": verdict, "why": "", "text_sha256": sha}],
                  "pool_facts": [], "pool": [{"i": 0, "text_sha256": sha}]}
        return [(row["rule"], row["decision"], row["reader_verdict"])
                for row in _adjudicator().decisions_for(self.POSITION, document, record)]

    def test_a_reader_who_left_it_out_is_overruled(self):
        self.assertEqual([("INDEPENDENCE_RELATIONSHIP_DETERMINATION", "FACT", "NOT")], self.decided("NOT"))
        # A reader who took it needs no decision.
        self.assertEqual([], self.decided("FACT"))


class AReadingRefusesTextItDidNotSee(unittest.TestCase):

    def test_a_changed_block_text_is_not_judged(self):
        path = READINGS[0]
        record = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = record["position"].rsplit(":", 1)
        document, chosen, _candidate = reading.route_selection(repo_root=ROOT, company_id=company_id,
                                                               report_end=report_end)
        # A selected block the reading judged once, among its selected rows.
        once = _judged_once(record, "selected")
        index = next(i for i in chosen if i in once)
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
        index = chosen[0]
        altered = json.loads(json.dumps(record))
        # Remove every trace of the block from the reading: judged nowhere and
        # not in the pool, it was never read.
        for key in ("selected", "pool_facts", "outside_pool_facts", "supplementary", "pool"):
            altered[key] = [row for row in altered.get(key, []) if row["i"] != index]
        answer = reading.read_position(document=document, chosen=chosen, reading=altered)
        self.assertIn(index, answer["problems"]["unread"])

    def test_the_selector_is_the_route_s_not_a_copy(self):
        # The reading tool recomputes the selection through the route; this
        # checks that what it recomputes is what the successor module returns
        # for the same governance document, so the reading tests the rule the
        # Run uses and not a second implementation.
        path = READINGS[0]
        record = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = record["position"].rsplit(":", 1)
        document, chosen, _candidate, period_start = reading.route_selection(
            repo_root=ROOT, company_id=company_id, report_end=report_end, with_period=True)
        direct = [c["block_index"] for c in board_composition_facts(
            document=document, period_start=period_start)["candidates"]]
        self.assertEqual(sorted(chosen), direct)


if __name__ == "__main__":
    unittest.main()
