"""B10/B11: the older wording of the lodging table introduction (Issue #47).

The approved introduction is the newest reports' sentence. Marriott's FY2022
and FY2021 reports print it in the plural ("The following tables present"),
and FY2021 also without the comma before "and". The historical route inspects
a filing again with a pattern that accepts those two forms only when the frozen
inspector refuses because the introduction is unproven.

Reads Marriott's FY2021 and FY2022 reports from the acquisition's export and
its FY2025 report from the checkout (saved-source tier). Zero calls.
"""
import json
import re
import unittest
from unittest.mock import Mock, patch

from sec_urls import accession_document_url
from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tools.acceptance_readings import saved_bytes
from vnext import historical_lodging_results as route
from vnext import lodging_table_source as frozen
from vnext.annual_update import saved_source
from vnext.canonical import content_hash, sha256_bytes
from vnext.historical_dei import release_aware
from vnext.normal_annual_input import annual_period as frozen_annual_period
from vnext.sources import raw_blob_record, source_reference_record

CIK = "1048286"
# The route reads older DEI taxonomy releases through its views (historical_dei);
# the frozen readers alone refuse FY2021/FY2022 before any lodging check.
annual_period = release_aware(frozen_annual_period)
COMPANY = "marriott_international"
OLDER = {  # report end: (saved path, accession, primary document)
    2021: ("evidence/request_attempts/54/54effe78b84966cd0793dcb23b8db4ad30b0614ea3d42074f3ece89adebe8bf5/"
           "mar-20211231.htm", "0001628280-22-002666", "mar-20211231.htm"),
    2022: ("evidence/request_attempts/c0/c041a0501c788a5cc6bb2e6155e6ea345834e1baca2d6165d6d7af22e1b5e95d/"
           "mar-20221231.htm", "0001628280-23-003485", "mar-20221231.htm"),
}
NEWEST = "The following table presents RevPAR, occupancy, and ADR statistics for comparable properties for 2023, and 2023 compared to 2022. Systemwide statistics include data from our franchised properties, in addition to our company-operated properties."
PLURAL = NEWEST.replace("table presents", "tables present").replace("2023", "2022").replace("2022.", "2021.", 1)
PLURAL_WITHOUT_COMMA = PLURAL.replace("2022, and", "2022 and")


def _filing(year):
    block = json.loads((ROOT / "evidence/submissions/CIK0001048286.json").read_text())["filings"]["recent"]
    return next({key: values[i] for key, values in block.items()} for i, form in enumerate(block["form"])
                if form == "10-K" and block["reportDate"][i] == "%d-12-31" % year)


def _arguments(raw, filing, template):
    blob = {**template["blob"], "raw_asset_id": "sha256:" + sha256_bytes(content=raw), "byte_length": len(raw)}
    reference = source_reference_record(
        raw_blob=blob, company_id=COMPANY,
        source_url=accession_document_url(cik=int(CIK), accession=filing["accessionNumber"],
                                          document_name=filing["primaryDocument"]),
        accession=filing["accessionNumber"], document_name=filing["primaryDocument"],
        source_role="target_primary", request_attempt_id=template["reference"]["request_attempt_id"])
    return {"raw": raw, "blob": blob, "reference": reference, "filing": filing, "company_id": COMPANY,
            "cik": CIK, "period": annual_period(raw=raw, cik=CIK, filing=filing)}


class TheOlderIntroductionIsReadOnlyWhereTheFrozenOneRefusesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        filing = _filing(2025)
        with original_sources_only():
            saved = saved_source(repo_root=ROOT, url=accession_document_url(
                cik=int(CIK), accession=filing["accessionNumber"], document_name=filing["primaryDocument"]),
                accession=filing["accessionNumber"])
            blob = raw_blob_record(repo_root=ROOT, repo_relative_path=saved["proof"]["request_repo_relative_path"],
                                   media_type="text/html")
            reference = source_reference_record(
                raw_blob=blob, company_id=COMPANY, source_url=saved["proof"]["source_url"],
                accession=filing["accessionNumber"], document_name=filing["primaryDocument"],
                source_role="target_primary", request_attempt_id=saved["proof"]["request_attempt_id"])
        cls.newest = {"raw": saved["raw"], "blob": blob, "reference": reference, "filing": filing,
                      "company_id": COMPANY, "cik": CIK,
                      "period": annual_period(raw=saved["raw"], cik=CIK, filing=filing)}
        cls.older = {}
        for year, (path, accession, document) in OLDER.items():
            filing = _filing(year)
            assert (filing["accessionNumber"], filing["primaryDocument"]) == (accession, document)
            cls.older[year] = _arguments(saved_bytes(repo_root=ROOT, relative=path), filing, cls.newest)

    def test_the_frozen_inspector_refuses_the_older_reports_for_the_introduction(self):
        for year, arguments in self.older.items():
            with self.subTest(year=year), \
                    self.assertRaisesRegex(frozen.LodgingSourceError, "LODGING_MATCHING_TABLE_NOT_UNIQUE:") as caught:
                route.inspect_lodging_table_source(**arguments)
            self.assertIn(route.INTRODUCTION_REFUSAL, str(caught.exception))

    def test_the_older_reports_resolve_one_table_under_the_older_forms(self):
        expected = {2021: ("0.513", "74.66"), 2022: ("0.64", "110.64")}
        for year, arguments in self.older.items():
            with self.subTest(year=year):
                component = route.inspect_with_older_introduction(**arguments)
                facts = component["selection"]["facts"]
                self.assertEqual(expected[year], (str(facts["B10"]["value"]), str(facts["B11"]["value"])))
                self.assertEqual(content_hash(value=route.OLDER_INTRODUCTION_POLICY), component["policy_hash"])
                self.assertNotEqual(content_hash(value=frozen.POLICY), component["policy_hash"])
                intro = component["selection"]["context"]["introduction"]["text"]
                self.assertIn("The following tables present", intro)

    def test_a_report_the_frozen_inspector_accepts_is_unchanged(self):
        self.assertEqual(route.inspect_lodging_table_source(**self.newest),
                         route.inspect_with_older_introduction(**self.newest))

    def test_another_refusal_is_raised_unchanged_and_the_older_forms_are_not_tried(self):
        older = Mock()
        refusal = frozen.LodgingSourceError(
            "LODGING_MATCHING_TABLE_NOT_UNIQUE:[{'table_id': 't', 'reason': 'LODGING_MEASURE_HEADER_NOT_UNIQUE'}]")
        with patch.object(route, "inspect_lodging_table_source", side_effect=refusal), \
                patch.object(route, "inspect_older_introduction", older), \
                self.assertRaisesRegex(frozen.LodgingSourceError, "LODGING_MEASURE_HEADER_NOT_UNIQUE"):
            route.inspect_with_older_introduction(**self.newest)
        older.assert_not_called()


class TheOlderFormsAreTwoAndOnlyTwoTest(unittest.TestCase):

    def test_the_policy_changes_one_pattern(self):
        changed = {key for key in frozen.POLICY if frozen.POLICY[key] != route.OLDER_INTRODUCTION_POLICY[key]}
        self.assertEqual(set(frozen.POLICY), set(route.OLDER_INTRODUCTION_POLICY))
        self.assertEqual({"table_introduction_pattern"}, changed)

    def test_the_older_pattern_accepts_the_three_printed_forms_and_the_frozen_one_only_the_newest(self):
        older = route.OLDER_INTRODUCTION_POLICY["table_introduction_pattern"]
        newest = frozen.POLICY["table_introduction_pattern"]
        for sentence in (NEWEST, PLURAL, PLURAL_WITHOUT_COMMA):
            with self.subTest(sentence=sentence[:60]):
                self.assertIsNotNone(re.fullmatch(older, sentence))
        self.assertIsNotNone(re.fullmatch(newest, NEWEST))
        self.assertIsNone(re.fullmatch(newest, PLURAL))
        self.assertIsNone(re.fullmatch(newest, PLURAL_WITHOUT_COMMA))

    def test_nothing_else_is_accepted(self):
        older = route.OLDER_INTRODUCTION_POLICY["table_introduction_pattern"]
        for sentence in (NEWEST.replace("table presents", "tables presents"),
                         NEWEST.replace("table presents", "table present"),
                         NEWEST.replace(", and", "; and"),
                         NEWEST.replace("franchised properties", "managed properties"),
                         NEWEST.replace("comparable properties", "all properties"),
                         NEWEST.replace("2023 compared", "2024 compared")):
            with self.subTest(sentence=sentence[:80]):
                self.assertIsNone(re.fullmatch(older, sentence))

    def test_a_frozen_pattern_without_the_replaced_text_stops_the_successor(self):
        with self.assertRaisesRegex(ValueError, "HISTORICAL_LODGING_INTRODUCTION_FORM_NOT_IN_THE_FROZEN_PATTERN"):
            route._older_introduction(frozen.POLICY["table_introduction_pattern"].replace(", and", " and"))


if __name__ == "__main__":
    unittest.main()
