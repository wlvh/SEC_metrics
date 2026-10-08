"""The C02 core-fact record is refused when it stops describing the selection.

docs/evidence/issue47_history/c02-board-read/core_fact_reach.py holds the
judgements in core-fact-judgements.json to the route's selection and the
governance document's bytes. These cases give its check a selection and
blocks built in the test - so they run without the saved proxies - and break
each property the check is there for.
"""
import copy
import importlib.util
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT

PRODUCER = ROOT / "docs/evidence/issue47_history/c02-board-read/core_fact_reach.py"
_spec = importlib.util.spec_from_file_location("core_fact_reach", PRODUCER)
reach = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reach)

BLOCKS = [{"text": "Our Board of Directors has seven members."},
          {"text": "The Board has determined that six directors are independent."},
          {"text": "Audit Committee"},
          {"text": "Chair: A. Director"},
          {"text": "The Audit Committee is composed of three named directors."}]
SELECTED = {0, 1, 4}
FACTS = {0: "COMPOSITION_FACT", 1: "COMPOSITION_FACT", 4: "COMPOSITION_FACT"}


def _entry(index):
    return {"block_index": index, "text_start": BLOCKS[index]["text"][:20]}


JUDGED = {"board_size": {"status": "IN_THE_VALUE", "in_the_value": [_entry(0)]},
          "board_independence": {"status": "IN_THE_VALUE", "in_the_value": [_entry(1)]},
          "committee_information": {"status": "PARTIAL", "in_the_value": [_entry(4)]},
          "committee_pages_not_selected": [{"committee": "Audit",
                                            "blocks": [_entry(2), _entry(3)]}],
          "other_missed": []}


def problems(judged, *, facts=FACTS, blocks=BLOCKS):
    return reach.check_position(judged=judged, facts=facts, selected=SELECTED, blocks=blocks)


class TheRecordMustDescribeTheSelection(unittest.TestCase):

    def test_a_record_that_describes_the_selection_passes(self):
        self.assertEqual([], problems(JUDGED))

    def test_a_block_called_in_the_value_that_is_not_selected_is_refused(self):
        """The mistake this record was nearly written with, the other way round."""
        judged = copy.deepcopy(JUDGED)
        judged["board_independence"]["in_the_value"].append(_entry(3))
        self.assertEqual(["board_independence:NOT_SELECTED:3"], problems(judged))

    def test_a_block_called_missed_that_is_selected_is_refused(self):
        """Marriott's 1217 was first written down as missed; it is in the value."""
        judged = copy.deepcopy(JUDGED)
        judged["other_missed"].append({**_entry(1), "kind": "BOARD_INDEPENDENCE", "states": "x"})
        self.assertEqual(["MISSED_BLOCK_IS_SELECTED:1"], problems(judged))

    def test_a_selected_block_not_judged_a_composition_fact_is_refused(self):
        facts = {**FACTS, 4: "COMMITTEE_OR_BOARD_FUNCTION"}
        self.assertEqual(["committee_information:NOT_JUDGED_A_COMPOSITION_FACT:4"],
                         problems(JUDGED, facts=facts))

    def test_changed_text_is_refused_on_both_sides(self):
        blocks = copy.deepcopy(BLOCKS)
        blocks[0]["text"] = "Our Board has eight members."
        blocks[3]["text"] = "Chair: Another Director"
        self.assertEqual(["board_size:TEXT_CHANGED:0", "MISSED_BLOCK_TEXT_CHANGED:3"],
                         problems(JUDGED, blocks=blocks))


class TheCommittedRecordCoversTheCommittedPositions(unittest.TestCase):

    def test_every_position_judged_is_a_committed_position_and_every_status_is_named(self):
        here = "docs/evidence/issue47_history/c02-board-read/"
        judged = json.loads((ROOT / (here + "core-fact-judgements.json")).read_text(
            encoding="utf-8"))["positions"]
        committed = json.loads((ROOT / (here + "excerpt-judgements.json")).read_text(
            encoding="utf-8"))["positions"]
        self.assertEqual(set(committed), set(judged))
        for key, entry in judged.items():
            for field in reach.NAMED:
                with self.subTest(position=key, field=field):
                    self.assertIn(entry[field]["status"],
                                  {"IN_THE_VALUE", "PARTIAL", "MISSING"})
                    # A named output can be in the value only through excerpts.
                    self.assertEqual(entry[field]["status"] == "MISSING",
                                     not entry[field]["in_the_value"])


if __name__ == "__main__":
    unittest.main()
