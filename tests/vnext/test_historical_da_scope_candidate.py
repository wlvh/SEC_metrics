"""The candidate B03 rule: take, compose or withhold D&A by name.

Real filings first: the nine B03 filings the cross-source reading opened, where
the rule must leave eight answers exactly as the approved chain gives them and
withhold only Salesforce's, whose direct candidates are a fixed-asset subtotal
and a statement total that also carries impairment. Then the shapes no saved
filing has - a disagreement inside reported precision, a composition that
resolves a conflict, facts for another period, segment or unit - built in
memory and saying so.
"""
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.deterministic_router import _XbrlFactParser
from vnext.historical_da_scope_candidate import (COMPOSITION, DIRECT, WITHHELD_REASON,
                                                 _DecimalsFactParser, agree, annual_facts,
                                                 da_scope_answer)

READING = "docs/evidence/issue47_history/content-acceptance/cross-source-read.json"
FINDING = "docs/evidence/issue47_history/b03-depreciation-scope/finding.json"


def _filings():
    reading = json.loads((ROOT / READING).read_text(encoding="utf-8"))["per_position"]
    for label, case in sorted(reading.items()):
        if "error" in case or "B03" not in case["metrics"]:
            continue
        identity = case["metrics"]["B03"].get("checked_identity") or {}
        if identity.get("period_start") is None:
            continue
        yield label, (ROOT / case["document"]).read_bytes(), identity["period_start"], \
            identity.get("period_end") or case["period_end"]


def _inline(*facts, contexts=None):
    """A minimal inline XBRL document: facts are (concept, context, unit, decimals, scale, text)."""
    contexts = contexts or {"fy": ("2025-01-01", "2025-12-31", None),
                            "prior": ("2024-01-01", "2024-12-31", None),
                            "segment": ("2025-01-01", "2025-12-31", "x:SegmentMember")}
    header = ["<html><body><ix:header><ix:resources>"]
    for context_id, (start, end, member) in contexts.items():
        segment = ("" if member is None else
                   "<xbrli:segment><xbrldi:explicitMember dimension=\"us-gaap:"
                   "StatementBusinessSegmentsAxis\">" + member
                   + "</xbrldi:explicitMember></xbrli:segment>")
        header.append("<xbrli:context id=\"" + context_id + "\"><xbrli:entity>"
                      "<xbrli:identifier scheme=\"http://www.sec.gov/CIK\">0000000001"
                      "</xbrli:identifier>" + segment + "</xbrli:entity><xbrli:period>"
                      "<xbrli:startDate>" + start + "</xbrli:startDate><xbrli:endDate>"
                      + end + "</xbrli:endDate></xbrli:period></xbrli:context>")
    header.append("<xbrli:unit id=\"usd\"><xbrli:measure>iso4217:USD</xbrli:measure>"
                  "</xbrli:unit><xbrli:unit id=\"eur\"><xbrli:measure>iso4217:EUR"
                  "</xbrli:measure></xbrli:unit></ix:resources></ix:header>")
    for concept, context, unit, decimals, scale, text in facts:
        header.append("<p><ix:nonFraction name=\"us-gaap:" + concept + "\" contextRef=\""
                      + context + "\" unitRef=\"" + unit + "\" decimals=\"" + decimals
                      + "\" scale=\"" + scale + "\">" + text + "</ix:nonFraction></p>")
    return ("".join(header) + "</body></html>").encode("utf-8")


def _answer(raw):
    return da_scope_answer(facts=annual_facts(raw_bytes=raw, period_start="2025-01-01",
                                              period_end="2025-12-31",
                                              concepts=DIRECT + COMPOSITION))


class TheParserIsTheFrozenOneWithPrecision(unittest.TestCase):

    def test_the_same_facts_in_the_same_order(self):
        for label, raw, _, _ in _filings():
            frozen, successor = _XbrlFactParser(), _DecimalsFactParser()
            frozen.feed(raw.decode("utf-8"))
            successor.feed(raw.decode("utf-8"))
            ours = successor.facts()
            with self.subTest(label):
                self.assertEqual([{k: v for k, v in fact.items() if k != "decimals"}
                                  for fact in ours], frozen.facts())
                self.assertTrue(any(fact["decimals"] for fact in ours))


class OnTheNineFilings(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.answers = {label: da_scope_answer(facts=annual_facts(
            raw_bytes=raw, period_start=start, period_end=end, concepts=DIRECT + COMPOSITION))
            for label, raw, start, end in _filings()}
        cls.finding = json.loads((ROOT / FINDING).read_text(encoding="utf-8"))["per_position"]

    def test_eight_answers_stay_what_the_approved_chain_gives(self):
        taken = {label: answer for label, answer in self.answers.items()
                 if answer["status"] == "TAKE"}
        self.assertEqual(sorted(taken), ["enphase-2025", "ford-2025", "lumen-2025",
                                         "macys-2026", "pfizer-2025", "southwest-2025"])
        for label, answer in taken.items():
            recorded = self.finding[label]
            with self.subTest(label):
                self.assertEqual(answer["selected"]["concept"], recorded["chain_takes"])
                self.assertEqual(answer["selected"]["value"],
                                 str(int(float(recorded["value_taken"]))))
        for label in ("marriott-2024", "marriott-2025"):
            with self.subTest(label):
                self.assertEqual(self.answers[label]["status"], "NO_DIRECT_CANDIDATE")

    def test_salesforce_is_withheld_with_both_candidates_named(self):
        answer = self.answers["salesforce-2026"]
        self.assertEqual((answer["status"], answer["reason_code"]),
                         ("WITHHOLD", WITHHELD_REASON))
        self.assertEqual(sorted((c["concept"], c["value"], c["decimals"])
                                for c in answer["candidates"]),
                         [("DepreciationAndAmortization", "3631000000", "-6"),
                          ("DepreciationDepletionAndAmortization", "1200000000", "-8")])

    def test_lumen_s_two_concepts_agree_and_are_not_a_conflict(self):
        answer = self.answers["lumen-2025"]
        self.assertEqual(len(answer["candidates"]), 2)
        self.assertEqual(answer["why"], "EVERY_DIRECT_CANDIDATE_AGREES")


class ShapesNoSavedFilingHas(unittest.TestCase):
    """Built in memory."""

    def test_a_difference_inside_reported_precision_is_not_a_conflict(self):
        answer = _answer(_inline(
            ("DepreciationDepletionAndAmortization", "fy", "usd", "-8", "9", "1.2"),
            ("DepreciationAndAmortization", "fy", "usd", "-6", "6", "1,234")))
        self.assertEqual((answer["status"], answer["selected"]["value"]), ("TAKE", "1200000000"))

    def test_a_difference_beyond_it_is(self):
        answer = _answer(_inline(
            ("DepreciationDepletionAndAmortization", "fy", "usd", "-8", "9", "1.2"),
            ("DepreciationAndAmortization", "fy", "usd", "-6", "6", "1,260")))
        self.assertEqual(answer["status"], "WITHHOLD")

    def test_the_filing_s_own_composition_resolves_a_conflict(self):
        # The chain's first concept equals depreciation alone; the other equals
        # depreciation plus intangible amortization - the definition's own
        # composition - so it is the one taken, although it comes second.
        answer = _answer(_inline(
            ("DepreciationDepletionAndAmortization", "fy", "usd", "-6", "6", "1,000"),
            ("DepreciationAndAmortization", "fy", "usd", "-6", "6", "1,500"),
            ("Depreciation", "fy", "usd", "-6", "6", "1,000"),
            ("AmortizationOfIntangibleAssets", "fy", "usd", "-6", "6", "500")))
        self.assertEqual((answer["status"], answer["why"], answer["selected"]["concept"]),
                         ("TAKE", "EQUALS_THE_FILING_S_OWN_COMPOSITION",
                          "DepreciationAndAmortization"))

    def test_the_larger_number_is_not_taken_for_being_larger(self):
        answer = _answer(_inline(
            ("DepreciationDepletionAndAmortization", "fy", "usd", "-6", "6", "1,000"),
            ("DepreciationAndAmortization", "fy", "usd", "-6", "6", "1,500")))
        self.assertEqual(answer["status"], "WITHHOLD")

    def test_another_period_segment_or_unit_is_not_a_candidate(self):
        answer = _answer(_inline(
            ("DepreciationDepletionAndAmortization", "fy", "usd", "-6", "6", "1,000"),
            ("DepreciationAndAmortization", "prior", "usd", "-6", "6", "900"),
            ("DepreciationAndAmortization", "segment", "usd", "-6", "6", "400"),
            ("DepreciationAndAmortization", "fy", "eur", "-6", "6", "850")))
        self.assertEqual((answer["status"], len(answer["candidates"])), ("TAKE", 1))

    def test_one_concept_carrying_two_amounts_is_withheld(self):
        answer = _answer(_inline(
            ("DepreciationAndAmortization", "fy", "usd", "-6", "6", "1,000"),
            ("DepreciationAndAmortization", "fy", "usd", "-6", "6", "1,100")))
        self.assertEqual((answer["status"], answer["why"]),
                         ("WITHHOLD", "ONE_CONCEPT_CARRIES_TWO_AMOUNTS:DepreciationAndAmortization"))

    def test_precision_is_read_from_each_fact(self):
        self.assertTrue(agree({"value": "1200000000", "decimals": "-8"},
                              {"value": "1249000000", "decimals": "-6"}))
        self.assertFalse(agree({"value": "1200000000", "decimals": "-6"},
                               {"value": "1249000000", "decimals": "-6"}))
        self.assertFalse(agree({"value": "1", "decimals": "not-a-number"},
                               {"value": "1", "decimals": "-6"}))


if __name__ == "__main__":
    unittest.main()
