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


class TheOlderReadingsTest(unittest.TestCase):

    def test_every_judged_item_8_admission_is_decided_as_the_reader_decided(self):
        judged, disagreements = 0, []
        left = {"DISCLOSURE": 0, "NOT_DISCLOSURE": 0}
        for path in sorted(OLDER.glob("*.json")):
            body = json.loads(path.read_text(encoding="utf-8"))
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


class TheTermsFileTest(unittest.TestCase):

    def test_another_record_is_refused(self):
        body = json.loads(rule._TERMS_PATH.read_text(encoding="utf-8"))
        for change in ({"record_type": "C02"}, {"metric_id": "D01"}, {"schema_version": 2},
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
