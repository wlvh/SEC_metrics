"""D02, Item 8: a keyword paragraph leaves the set only as a category mention without a matter.

The recorded readings are the measure: every Item 8 keyword admission the
thirty older-year readings judged (d02-older-years/judgements) is left out
exactly when the reader judged it NOT_DISCLOSURE. The constructed cases hold
each half of the rule on its own, including the shape that falsified an
earlier candidate (a list member in a paragraph that is a disclosure). Zero
calls.
"""
import json
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import d02_item_8_category_mentions as rule
from vnext.text_business_candidates import _LEGAL

OLDER = ROOT / "docs/evidence/issue47_history/d02-older-years/judgements"
ITEM_8_SCOPES = {"ITEM_8", "ITEM_8_STATEMENTS_PRINTED_AFTER_THE_ITEMS"}


def _left_out(text):
    return rule.left_out_as_category_mention(text=text, keyword=_LEGAL)


HELD_OUT = "held-out round"


def _readings(*, held_out):
    for path in sorted(OLDER.glob("*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        if (HELD_OUT in body["reader"]) == held_out:
            yield body


class TheOlderReadingsTest(unittest.TestCase):
    """The thirty readings the rule was written beside: every admission decided as read."""

    def test_every_judged_item_8_admission_is_decided_as_the_reader_decided(self):
        judged, disagreements = 0, []
        left = {"DISCLOSURE": 0, "NOT_DISCLOSURE": 0}
        for body in _readings(held_out=False):
            for row in body["judgements"]:
                if row["kind"] != "TAKEN" or row.get("scope") not in ITEM_8_SCOPES:
                    continue
                judged += 1
                out = _left_out(row["text"])
                left[row["verdict"]] += out
                if out != (row["verdict"] == "NOT_DISCLOSURE"):
                    disagreements.append((body["position"], row["i"], row["verdict"]))
        self.assertEqual([], disagreements)
        self.assertEqual(61, judged)
        self.assertEqual({"DISCLOSURE": 0, "NOT_DISCLOSURE": 16}, left)


class TheHeldOutReadingsTest(unittest.TestCase):
    """Positions judged after the rule was frozen (104876d6), by readers who did not know it.

    JPMorgan's five years were not looked at before the freeze; Pfizer FY2021's
    keyword blocks were, while drafting, so it is counted apart. The rule may
    leave a non-disclosure in - it is only one of the reasons a block can be
    wrong - but it must never take a disclosure out. The counts are the
    measurement and are held exactly, so a change to the rule shows here.
    """

    def _counts(self, company_id):
        counts = {"kept_disclosure": 0, "lost_disclosure": 0,
                  "left_out_not_disclosure": 0, "kept_not_disclosure": 0}
        for body in _readings(held_out=True):
            if not body["position"].startswith(company_id + ":"):
                continue
            for row in body["judgements"]:
                if row["kind"] != "TAKEN" or row.get("scope") not in ITEM_8_SCOPES:
                    continue
                out = _left_out(row["text"])
                if row["verdict"] == "DISCLOSURE":
                    counts["lost_disclosure" if out else "kept_disclosure"] += 1
                else:
                    counts["left_out_not_disclosure" if out else "kept_not_disclosure"] += 1
        return counts

    def test_no_disclosure_is_lost_and_the_counts_are_the_measured_ones(self):
        self.assertEqual({"kept_disclosure": 10, "lost_disclosure": 0,
                          "left_out_not_disclosure": 9, "kept_not_disclosure": 40},
                         self._counts("jpmorgan_chase"))
        self.assertEqual({"kept_disclosure": 36, "lost_disclosure": 0,
                          "left_out_not_disclosure": 3, "kept_not_disclosure": 0},
                         self._counts("pfizer"))
        self.assertEqual({"kept_disclosure": 0, "lost_disclosure": 0,
                          "left_out_not_disclosure": 0, "kept_not_disclosure": 0},
                         self._counts("salesforce"))


class TheRuleTest(unittest.TestCase):
    """Each condition on a paragraph built to break exactly that one."""

    ADVISERS = ("In the normal course of our business, we incur costs to retain external "
                "counsel to advise us on finance, regulatory, litigation, and other matters. "
                "We expense these costs as the related services are received.")

    def test_a_list_member_in_a_paragraph_without_a_matter_is_left_out(self):
        self.assertTrue(_left_out(self.ADVISERS))

    def test_a_matter_of_the_registrant_anywhere_in_the_paragraph_keeps_it(self):
        self.assertFalse(_left_out(self.ADVISERS + " We are subject to various legal proceedings."))

    def test_an_example_in_a_parenthetical_is_left_out(self):
        self.assertTrue(_left_out(
            "Trade accounts receivable are written off after all reasonable means to collect "
            "the full amount (including litigation, where appropriate) have been exhausted."))

    def test_a_keyword_that_is_not_a_list_member_keeps_the_paragraph(self):
        self.assertFalse(_left_out(
            "The paragraph concerns stockholder litigation related to the merger."))

    def test_one_occurrence_outside_a_list_keeps_the_paragraph(self):
        self.assertFalse(_left_out(
            "Costs include fees for finance, regulatory, litigation and other matters. "
            "The note describes stockholder litigation related to the merger."))

    def test_a_list_member_in_a_disclosure_stays(self):
        # The shape that falsified the enumeration-only candidate: the keyword
        # is a list member and the paragraph is a disclosure, because the
        # registrant accrues for its own claims.
        self.assertFalse(_left_out(
            "The Company is self-insured for general liability claims up to certain amounts. "
            "The amounts accrued reflect losses, settlements, litigation costs and other factors."))

    def test_judgments_in_an_estimate_are_not_a_matter(self):
        self.assertTrue(_left_out(
            "Our estimates are often based on complex judgments. We are subject to risks that "
            "may cause results to differ, such as competition, litigation, legislation and "
            "regulations."))

    def test_a_settlement_with_a_taxing_authority_is_not_a_matter(self):
        self.assertTrue(_left_out(
            "Any settlements with taxing authorities could decrease our uncertain tax positions. "
            "Finalizing audits can include formal administrative and legal proceedings."))

    def test_a_label_is_never_left_out(self):
        for label in ("Litigation and Regulatory Matters", "A1. Litigation and Other Matters",
                      "Commitments, Litigation and Contingencies"):
            with self.subTest(label):
                self.assertFalse(_left_out(label))

    def test_a_paragraph_without_the_keyword_is_not_this_rule_s(self):
        self.assertFalse(_left_out("We expense counsel costs as the services are received."))

    def test_the_record_says_why(self):
        found = rule.classify(text=self.ADVISERS, keyword=_LEGAL)
        self.assertEqual(["LIST_MEMBER"], [item["why"] for item in found["occurrences"]])
        self.assertEqual([], found["exposure"])
        self.assertEqual(rule.TERMS_HASH, found["terms_hash"])


V2 = ROOT / "docs/evidence/issue47_history/d02-keyword-repair/v2"


def _whys(text):
    return [item["why"] for item in rule.classify(text=text, keyword=_LEGAL)["occurrences"]]


class TheReportedFalseExclusionsTest(unittest.TestCase):
    """#28's limited review of de22326d (Issue #47 comment 5948676381): a comma is not a list."""

    def test_the_two_reported_sentences_stay_by_structure_alone(self):
        # Each occurrence is no category mention, so the paragraph stays whether
        # or not any exposure word is present.
        for text in ("We face litigation, which could result in a significant loss.",
                     "Litigation, brought by a customer against us in 2025, remains unresolved."):
            with self.subTest(text):
                found = rule.classify(text=text, keyword=_LEGAL)
                self.assertFalse(found["left_out"])
                self.assertEqual([False], [item["category_mention"] for item in found["occurrences"]])


class TheSeriesStructureTest(unittest.TestCase):
    """Each structural condition on a sentence built to break exactly that one."""

    def test_the_keyword_s_phrase_is_no_clause(self):
        self.assertEqual(["KEYWORD_PHRASE_IS_A_CLAUSE_OR_NAMES_A_PARTY"], _whys(
            "Irrespective of its merits, litigation may be lengthy and disruptive."))

    def test_the_keyword_s_phrase_names_no_party(self):
        self.assertEqual(["KEYWORD_PHRASE_IS_A_CLAUSE_OR_NAMES_A_PARTY"], _whys(
            "The note covers fines, litigation brought by a former supplier, and penalties."))
        self.assertEqual(["LIST_MEMBER"], _whys("The note covers fines, litigation, and penalties."))

    def test_the_keyword_s_phrase_names_not_the_registrant(self):
        self.assertEqual(["KEYWORD_PHRASE_NAMES_THE_REGISTRANT_S_OWN_MATTER"], _whys(
            "Some matters (e.g., the litigation arising from the failure of our dam) could exceed "
            "insurance coverage."))
        self.assertEqual(["PARENTHETICAL_EXAMPLE"], _whys(
            "Some costs (e.g., litigation) could exceed insurance coverage."))

    def test_the_first_item_of_a_sentence_is_governed_by_it(self):
        self.assertEqual(["GOVERNED_BY_ITS_SENTENCE"], _whys(
            "We face litigation, regulatory actions and fines."))

    def test_a_clause_before_the_keyword_in_its_item(self):
        # ViacomCBS FY2020 block 2382, the one saved Item 8 block version 2 moves.
        self.assertEqual(["KEYWORD_PHRASE_IS_A_CLAUSE"], _whys(
            "In 2018, we recorded expenses of $128 million primarily for professional fees related "
            "to legal proceedings, investigations at our Company and the evaluation of potential "
            "merger activity."))

    def test_a_series_governed_by_the_registrant_as_subject(self):
        self.assertEqual(["GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"], _whys(
            "We face regulatory actions, litigation and fines."))
        self.assertEqual(["GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"], _whys(
            "In 2025, the Company faced regulatory actions, litigation and fines."))
        self.assertEqual(["GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"], _whys(
            "In 2025, the Company faced litigation, fines and penalties."))
        self.assertEqual(["LIST_MEMBER"], _whys(
            "These events could result in regulatory actions, litigation and fines."))

    def test_a_series_that_is_the_subject_of_a_predicate(self):
        self.assertEqual(["SERIES_IS_A_SUBJECT"], _whys(
            "In 2025, fines and litigation, brought by customers, remain unresolved."))

    def test_a_separator_without_a_coordinated_series(self):
        self.assertEqual(["NO_COORDINATED_SERIES"], _whys(
            "In 2025, litigation, a costly matter, continued."))

    def test_a_coordinator_into_the_governing_words_counts_for_the_keyword_alone(self):
        self.assertEqual(["LIST_MEMBER"], _whys(
            "Finalizing audits can include formal administrative and legal proceedings."))
        self.assertEqual(["NO_COORDINATED_SERIES"], _whys(
            "These audits can include formal reviews and litigation costs."))

    def test_an_oxford_comma_is_one_separator(self):
        self.assertEqual(["LIST_MEMBER"], _whys(
            "Counsel advises us on finance, regulatory, litigation, and other matters."))


class TheAddedRelationsTest(unittest.TestCase):
    """Version 2's four relation entries, each keeping a paragraph whose keyword is a list member."""

    def test_each_relation_keeps_the_paragraph(self):
        base = TheRuleTest.ADVISERS
        self.assertTrue(_left_out(base))
        for name, sentence in (
                ("REGISTRANT_EXPOSED_TO_OR_NAMED_IN_A_LEGAL_MATTER",
                 " We are exposed to various lawsuits."),
                ("REGISTRANT_EXPOSED_TO_OR_NAMED_IN_A_LEGAL_MATTER",
                 " The Company has been named in two lawsuits."),
                ("A_MATTER_AGAINST_THE_REGISTRANT", " Two claims remain open against the Company."),
                ("A_MATTER_BROUGHT_BY_OR_AGAINST_A_PARTY", " A dispute was brought by a former supplier."),
                ("A_SUIT_OR_AN_ARBITRATION", " In 2024 we sued a former distributor."),
                ("A_SUIT_OR_AN_ARBITRATION", " The receivable is being pursued in arbitration.")):
            with self.subTest(sentence):
                found = rule.classify(text=base + sentence, keyword=_LEGAL)
                self.assertIn(name, found["exposure"])
                self.assertFalse(found["left_out"])


class TheIndependentBatteryTest(unittest.TestCase):
    """Paragraphs a fresh agent wrote to be hard for a pattern rule, without seeing it.

    Version 1 left out 20 of the 40 that state an actual matter; version 2
    leaves out none. This battery was run before version 2's vocabulary was
    final, so it is design material, not a held-out measure.
    """

    def test_no_stated_matter_is_left_out_and_the_leave_count_is_held(self):
        battery = json.loads((V2 / "independent-battery-1.json").read_text(encoding="utf-8"))
        self.assertEqual((40, 25), (len(battery["stay"]), len(battery["leave"])))
        self.assertEqual([], [text for text in battery["stay"] if _left_out(text)])
        self.assertEqual(8, sum(_left_out(text) for text in battery["leave"]))


class TheTermsFileTest(unittest.TestCase):

    def test_another_record_is_refused(self):
        body = json.loads(rule._TERMS_PATH.read_text(encoding="utf-8"))
        for change in ({"record_type": "C02"}, {"metric_id": "D01"}, {"schema_version": 1},
                       {"exposure": []},
                       {"exposure": body["exposure"] + [body["exposure"][0]]},
                       {"category_mention": {"prose": "x"}}):
            with self.subTest(change), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "terms.json"
                path.write_text(json.dumps({**body, **change}), encoding="utf-8")
                with self.assertRaises(rule.CategoryMentionTermsError):
                    rule._load(path)


if __name__ == "__main__":
    unittest.main()
