"""The C02 judgements, held to what the route selects from the saved proxies.

Every committed judgement describes one excerpt of a published C02 value. The
reading re-derives each position's selection through the route's own text
input and candidate builder and refuses a judgement file that does not describe
it, so these cases re-derive it and check both refusals.
"""
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_c02_board_statements as reader

JUDGEMENTS = json.loads((ROOT / reader.JUDGEMENTS).read_text(encoding="utf-8"))
READING = json.loads((ROOT / reader.OUTPUT).read_text(encoding="utf-8"))


class TheCommittedReadingReDerivesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.selected = {key: reader.route_selection(repo_root=ROOT, company_id=key.split(":")[0],
                                                    report_end=key.split(":")[1])
                        for key in JUDGEMENTS["positions"]}

    def test_every_position_re_derives(self):
        for key, judged in JUDGEMENTS["positions"].items():
            with self.subTest(key):
                self.assertEqual(READING["positions"][key],
                                 reader.read_position(judged=judged, selected=self.selected[key]))

    def test_every_value_holds_text_outside_board_composition(self):
        self.assertEqual({"DIFFERS"}, {row["verdict"] for row in READING["positions"].values()})
        self.assertTrue(all(len(row["outside_board_composition"]) >= 3
                            for row in READING["positions"].values()))

    def test_a_missing_judgement_is_refused_not_reported(self):
        key = "macys:2026-01-31"
        judged = JUDGEMENTS["positions"][key][:-1]
        self.assertEqual("JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION",
                         reader.read_position(judged=judged, selected=self.selected[key])["verdict"])

    def test_a_judgement_of_other_text_is_refused(self):
        key = "macys:2026-01-31"
        judged = [dict(row) for row in JUDGEMENTS["positions"][key]]
        judged[0]["text_start"] = "Something the filing does not say"
        self.assertEqual("JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION",
                         reader.read_position(judged=judged, selected=self.selected[key])["verdict"])

    def test_the_middle_categories_do_not_decide_a_value(self):
        """A value holding only facts and policies depends on the definition."""
        judged = [dict(row, category="COMPOSITION_POLICY_OR_PROCESS")
                  for row in JUDGEMENTS["positions"]["macys:2026-01-31"]]
        self.assertEqual("DEPENDS_ON_THE_DEFINITION",
                         reader.read_position(judged=judged,
                                              selected=self.selected["macys:2026-01-31"])["verdict"])


if __name__ == "__main__":
    unittest.main()
