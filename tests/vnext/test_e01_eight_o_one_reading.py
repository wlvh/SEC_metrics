"""E01's 8.01 reading, held to the filings it reads.

The route's 8.01 branch matches the aliases against a constant brief, so it
admits nothing. tools/read_e01_eight_o_ones.py reads each item off the saved
document instead. These cases run it on the filings that needed each step, so
a reader that stopped doing one fails where the filing is.
"""
import ast
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_e01_eight_o_ones as reader

READING = "docs/evidence/issue47_history/content-acceptance/e01-eight-o-one-read.json"
REGISTER = "docs/evidence/issue47_history/accepted_result_content.json"
DEFECTS = "docs/evidence/issue47_history/known_result_defects.json"
METSERA = "0000078003-25-000159"


def _committed():
    return json.loads((ROOT / READING).read_text(encoding="utf-8"))


def _window(label):
    windows = json.loads((ROOT / "docs/evidence/issue47_history/content-acceptance/"
                          "event-count-read.json").read_text(encoding="utf-8"))
    case = windows["per_position"][label]
    return {**case, "period_end": case["window"][1]}


def _judgements():
    return json.loads((ROOT / reader.JUDGEMENTS).read_text(encoding="utf-8"))["per_filing"]


class TheReaderIsNotTheRouteTest(unittest.TestCase):

    def test_it_imports_none_of_the_route_s_event_modules(self):
        tree = ast.parse((ROOT / "tools/read_e01_eight_o_ones.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for route_module in ("deterministic_router", "zero_ai_r2", "normal_zero_ai_results",
                             "historical_zero_ai_results", "historical_event_sources"):
            with self.subTest(route_module):
                self.assertFalse([name for name in imported if route_module in name])


class EachFilingSpecificStepTest(unittest.TestCase):

    def setUp(self):
        self.cik = reader.registered_ciks()

    def test_pfizer_heads_its_item_results_of_other_events(self):
        """The first extraction looked for 'Other Events' and read this item as
        empty - the route's miss again, one layer up."""
        _, eights = reader.read_window(case=_window("pfizer-2025"), judgements=_judgements(),
                                       cik=self.cik["pfizer"])
        item = next(e for e in eights if e["accession"] == METSERA)
        self.assertEqual("Item 8.01 Results of Other Events", item["heading"])
        self.assertEqual(["acquisition", "merger"], item["aliases_in_the_8_01_item"])
        self.assertIn("completed the previously announced acquisition of Metsera", item["item"])

    def test_an_alias_in_another_item_does_not_make_the_item_carry_it(self):
        _, eights = reader.read_window(case=_window("macys-2026"), judgements=_judgements(),
                                       cik=self.cik["macys"])
        covenant = next(e for e in eights if e["accession"] == "0000794367-25-000137")
        self.assertEqual([], covenant["aliases_in_the_8_01_item"])
        self.assertEqual(["merger", "transaction"],
                         covenant["aliases_anywhere_in_the_primary_document"])

    def test_the_item_ends_before_item_9_01(self):
        _, eights = reader.read_window(case=_window("southwest-2025"), judgements=_judgements(),
                                       cik=self.cik["southwest_airlines"])
        self.assertEqual(1, len(eights))
        self.assertNotIn("Item 9.01", eights[0]["item"])
        self.assertTrue(eights[0]["item"].startswith("Item 8.01 Other Events."))


class TheVerdictDoesNotRestOnTheOpenDecisionTest(unittest.TestCase):

    def test_match_only_when_every_reading_gives_the_published_count(self):
        every = {name: 2 for name in reader.READINGS_OF_THE_CONFIRMATION}
        self.assertEqual("MATCH", reader.verdict(published="2", counts=every, complete=True))
        some = {**every, "LITERAL_IN_THE_8_01_ITEM": 3}
        self.assertEqual("DEPENDS_ON_THE_CONFIRMATION_READING",
                         reader.verdict(published="2", counts=some, complete=True))
        none = {name: 1 for name in every}
        self.assertEqual("DIFFERS", reader.verdict(published="2", counts=none, complete=True))

    def test_an_unjudged_item_makes_the_reading_incomplete_whatever_the_counts(self):
        every = {name: 2 for name in reader.READINGS_OF_THE_CONFIRMATION}
        self.assertEqual("READING_INCOMPLETE",
                         reader.verdict(published="2", counts=every, complete=False))
        judgements = {key: value for key, value in _judgements().items() if key != METSERA}
        _, eights = reader.read_window(case=_window("pfizer-2025"), judgements=judgements,
                                       cik=reader.registered_ciks()["pfizer"])
        self.assertIsNone(next(e for e in eights if e["accession"] == METSERA)["decision"])

    def test_counts_are_in_the_route_s_unit(self):
        """One per matched item: a filing with a 1.01 and an admitted 8.01 counts twice."""
        lumen = _committed()["per_position"]["lumen-2025"]
        both = {e["accession"] for e in lumen["eight_o_ones"]
                if e["aliases_anywhere_in_the_primary_document"]}
        direct = {claim["accession"] for claim in lumen["direct_item_claims"]}
        self.assertEqual(3, len(both & direct))
        self.assertEqual(7 + 4, lumen["counts"]["LITERAL_ANYWHERE_IN_THE_PRIMARY_DOCUMENT"])

    def test_the_judged_reading_needs_the_alias_as_well(self):
        eights = [{"aliases_in_the_8_01_item": [], "aliases_anywhere_in_the_primary_document": [],
                   "decision": reader.REPORTS}]
        counts = reader.counts_under_each_reading(direct=0, eights=eights)
        self.assertEqual(0, counts["ALIAS_IN_THE_ITEM_AND_IT_REPORTS_A_TRANSACTION"])


class TheCommittedReadingSaysWhatTheFilingsSayTest(unittest.TestCase):

    def test_each_item_re_derives_from_the_saved_bytes(self):
        judgements = _judgements()
        ciks = reader.registered_ciks()
        for label, row in _committed()["per_position"].items():
            _, eights = reader.read_window(case=_window(label), judgements=judgements,
                                           cik=ciks[row["company_id"]])
            with self.subTest(label):
                self.assertEqual([(e["accession"], e["item_sha256"], e["aliases_in_the_8_01_item"],
                                   e["aliases_anywhere_in_the_primary_document"], e["decision"])
                                  for e in eights],
                                 [(e["accession"], e["item_sha256"], e["aliases_in_the_8_01_item"],
                                   e["aliases_anywhere_in_the_primary_document"], e["decision"])
                                  for e in row["eight_o_ones"]])

    def test_the_verdicts(self):
        verdicts = {label: row["verdict"] for label, row in _committed()["per_position"].items()}
        self.assertEqual({"enphase-2025": "MATCH", "ford-2025": "MATCH",
                          "southwest-2025": "MATCH",
                          "lumen-2025": "DEPENDS_ON_THE_CONFIRMATION_READING",
                          "macys-2026": "DEPENDS_ON_THE_CONFIRMATION_READING",
                          "marriott-2025": "DEPENDS_ON_THE_CONFIRMATION_READING",
                          "pfizer-2025": "DIFFERS"}, verdicts)

    def test_every_judgement_is_about_a_filing_a_window_holds(self):
        body = _committed()
        self.assertEqual([], body["judgements_not_found_in_any_window"])
        read = {e["accession"] for row in body["per_position"].values()
                for e in row["eight_o_ones"]}
        self.assertEqual(set(_judgements()), read)

    def test_the_identity_was_recorded_when_the_reading_was_made(self):
        for label, row in _committed()["per_position"].items():
            with self.subTest(label):
                identity = row["checked_identity"]
                self.assertEqual("RECORDED_AT_READING_TIME", identity["established_by"])
                self.assertIn("filings_equal_the_whole_set_the_reading_enumerated",
                              identity["checked_against_the_reading"])


class TheRegisterTakesE01FromThisReadingOnlyTest(unittest.TestCase):

    def test_accepted_where_no_reading_moves_the_count(self):
        register = json.loads((ROOT / REGISTER).read_text(encoding="utf-8"))
        e01 = {entry["company_id"]: entry["evidence"] for entry in register["acceptances"]
               if entry["metric_id"] == "E01"}
        self.assertEqual({"enphase_energy": READING, "ford_motor_company": READING,
                          "southwest_airlines": READING}, e01)

    def test_pfizer_is_withdrawn_by_a_registered_defect(self):
        defects = json.loads((ROOT / DEFECTS).read_text(encoding="utf-8"))["defects"]
        entry = next(d for d in defects
                     if d["defect_id"] == "E01_PFIZER_2025_EIGHT_O_ONE_BRANCH_NEVER_READS_THE_ITEM")
        self.assertEqual(("pfizer", "E01", "2025-12-31", None),
                         (entry["company_id"], entry["metric_id"], entry["period_end"],
                          entry["result_id"]))
        self.assertNotIn("released", entry)


if __name__ == "__main__":
    unittest.main()
