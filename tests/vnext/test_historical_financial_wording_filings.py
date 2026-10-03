"""The financial witnesses' older-wording successors on the bank's FY2021 annual report.

FY2021 is the one saved report that meets every form in
historical_financial_wording: the glossary colon and the older segment list
(A11), the excluded business's earlier name (A04), the general note and the
measure's abbreviation before the LCR row's lettered note (A03), the other
counterfactual header (A12), and the table of contents beside the older
segment list (A09's HTML fallback). Each successor is run once and must
resolve with the value the measurement recorded
(docs/evidence/issue47_history/financial-older-wording/measured.json); the
frozen inspectors' refusals of the same report are in that measurement.

Four copies of the same report with one phrase changed (constructed, and named
as such) hold the forms to what they say: a business other than the one the
report excludes, a counterfactual header that states no direction, and a table
of contents no longer named one are each refused as the frozen forms refuse
them.

Reads the report from the acquisition's export (saved-source tier). Zero calls.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from tools.acceptance_readings import saved_bytes  # noqa: E402
from vnext import historical_financial_wording as wording  # noqa: E402
from vnext.canonical import sha256_bytes  # noqa: E402
from vnext.historical_dei import overrides_of  # noqa: E402
from vnext.normal_source_authority import ROOT as RULE_ROOT  # noqa: E402

FY2021 = ("evidence/request_attempts/7c/7c58f18f4348ede74dea11e95de81ff18634f45c50f22f6d1dccdd8abf36d478/"
          "jpm-20211231.htm")
CIK = "0000019617"


def _arguments(raw):
    return {"repo_root": RULE_ROOT, "source_bytes": raw,
            "expected_source_sha256": sha256_bytes(content=raw), "expected_cik": CIK,
            "target_period": {"fiscal_year": 2021, "period_start": "2021-01-01",
                              "period_end": "2021-12-31"}}


class TheOlderFormsResolveTheOldestReport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = saved_bytes(repo_root=ROOT, relative=FY2021)
        cls.arguments = _arguments(cls.raw)

    def _changed(self, old, new):
        """The report with one phrase changed (constructed); the phrase must occur once."""
        self.assertEqual(1, self.raw.count(old.encode("utf-8")), old)
        return _arguments(self.raw.replace(old.encode("utf-8"), new.encode("utf-8")))

    def test_a11_reads_the_glossary_colon_and_the_older_segment_list(self):
        fact = wording._OLDER["A11"](**self.arguments)
        self.assertEqual(wording.RESOLVED, fact["semantic_status"])
        self.assertEqual("3113000000000", fact["value"])
        sections = {binding["manager_section"]["heading"]["text"]
                    for binding in fact["whole_issuer_scope_evidence"]["manager_section_bindings"]}
        self.assertEqual({"ASSET & WEALTH MANAGEMENT"}, sections)

    def test_a04_knows_the_excluded_business_by_its_earlier_name(self):
        fact = wording._OLDER["A04"](**self.arguments)
        self.assertEqual(wording.RESOLVED, fact["semantic_status"])
        self.assertEqual("0.0164", fact["relations"][0]["rate_check"]["disclosed_ratio"])
        excluded = [item for item in fact["same_named_rate_census"]
                    if item["disposition"] == "EXPLICIT_MARKETS_EXCLUDED_MEASURE"]
        self.assertEqual(["Net yield on average interest-earning assets excluding CIB Markets"],
                         [item["label"]["text"] for item in excluded])

    def test_a03_reaches_the_lettered_note_past_the_general_note(self):
        fact = wording._OLDER["A03"](**self.arguments)
        self.assertEqual(wording.RESOLVED, fact["status"], fact["unresolved"])
        self.assertEqual("1.11", fact["value"])
        self.assertEqual({"period_start": "2021-10-01", "period_end": "2021-12-31"},
                         {key: fact["measurement_period"][key] for key in ("period_start", "period_end")})

    def test_a12_sets_aside_the_increase_adjustment(self):
        fact = wording._OLDER["A12"](**self.arguments)
        self.assertEqual(wording.RESOLVED, fact["semantic_status"])
        self.assertEqual("55000000", fact["totals"][0]["value"]["canonical_value"])
        self.assertIn("COUNTERFACTUAL_INCREASE_AMOUNT_NOT_REPORTED_TOTAL",
                      {item["disposition"] for item in fact["same_named_total_census"]})

    def test_a09_fallback_sets_aside_the_contents_and_the_segment_tables(self):
        fallback = overrides_of(wording._OLDER["A09"])["inspect_nonaccrual_loan_ratio"]
        fact = fallback(**self.arguments)
        self.assertEqual(wording.RESOLVED, fact["status"], fact["unresolved"])
        self.assertEqual("0.0072", fact["value"])
        dispositions = {item["disposition"] for item in fact["candidate_census"]}
        self.assertLessEqual({"SOURCE_NAMED_TABLE_OF_CONTENTS", "OTHER_REPORTED_BUSINESS_SEGMENT"},
                             dispositions)


    def test_a04_does_not_set_aside_a_measure_excluding_another_business(self):
        fact = wording._OLDER["A04"](**self._changed(
            "Net yield on average interest-earning assets excluding CIB Markets",
            "Net yield on average interest-earning assets excluding CIB Lending"))
        self.assertNotEqual(wording.RESOLVED, fact["semantic_status"])
        self.assertIn("SAME_NAMED_NIM_CANDIDATE_UNRESOLVED",
                      {item["disposition"] for item in fact["same_named_rate_census"]})

    def test_a04_does_not_read_an_introduction_excluding_another_business(self):
        fact = wording._OLDER["A04"](**self._changed("excluding CIB Markets, as shown below",
                                                     "excluding CIB Lending, as shown below"))
        self.assertNotEqual(wording.RESOLVED, fact["semantic_status"])
        self.assertEqual([], fact["whole_issuer_scope_evidence"])

    def test_a12_does_not_set_aside_a_header_that_states_no_direction(self):
        fact = wording._OLDER["A12"](**self._changed(
            "Amount by which reported average VaR would have been higher",
            "Amount by which reported average VaR would have been revised"))
        self.assertNotEqual(wording.RESOLVED, fact["semantic_status"])
        self.assertIn("SAME_NAMED_VAR_PERIOD_OR_AVERAGE_AMBIGUOUS",
                      {item["reason"] for item in fact["unresolved"]})

    def test_a09_does_not_set_aside_a_table_no_longer_named_contents(self):
        fallback = overrides_of(wording._OLDER["A09"])["inspect_nonaccrual_loan_ratio"]
        fact = fallback(**self._changed("Table of contents", "Summary of sections"))
        self.assertNotEqual(wording.RESOLVED, fact["status"])
        self.assertNotIn("SOURCE_NAMED_TABLE_OF_CONTENTS",
                         {item["disposition"] for item in fact["candidate_census"]})


if __name__ == "__main__":
    unittest.main()
