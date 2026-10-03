"""B06's disclosure resolver on older layouts: two forms the frozen inventory leaves unresolved.

The historical cascade's last stage runs successors of the frozen resolver
(``historical_debt_results.fallback_resolution`` over ``fallback_verify`` over
``fallback_verify_v1``). The inventory learns two forms, both from Southwest's
older annual reports: a debt-table row naming pass-through certificates is a
debt instrument, as the notes beside it are, and a defined-benefit plan's
obligation is an employee-benefit measure, not a financing claim.

The cases call the resolution on the saved bytes (checkout or the
acquisition's export) with the inputs the historical cascade gave it on the
restored root (``b06-older-years/fallback-forms/source-records.json``):

- Southwest FY2022: the frozen resolution withholds at the matured
  certificates row and the pension obligation; the successor answers, with the
  carrying amount and ratio the measurement recorded.
- Southwest FY2024 and Salesforce FY2026, which the frozen resolution answers:
  the successor's answer is the frozen one, record for record.
- Southwest FY2021 and FY2023: the successor still withholds, at the next form
  the program does not handle (recorded in the measurement, not repaired).

Zero calls.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from tools.acceptance_readings import saved_bytes  # noqa: E402
from vnext import b06_disclosure as frozen_v1  # noqa: E402
from vnext import b06_disclosure_v2 as frozen_v2  # noqa: E402
from vnext import historical_debt_results as route  # noqa: E402
from vnext import normal_candidates as frozen_candidates  # noqa: E402

RECORDS = "docs/evidence/issue47_history/b06-older-years/fallback-forms/source-records.json"
FY2022 = "southwest_airlines:2022-12-31"
ANSWERED_BY_THE_FROZEN = ("southwest_airlines:2024-12-31", "salesforce:2026-01-31")
_CACHE = {}


def _preparation(label):
    """The fallback's preparation, rebuilt from the recorded inputs and the saved bytes."""
    if label not in _CACHE:
        filing = json.loads((ROOT / RECORDS).read_text(encoding="utf-8"))["filings"][label]

        def part(name):
            return {"raw_bytes": saved_bytes(repo_root=ROOT, relative=filing[name]["storage_uri"]),
                    "source_reference": filing[name]["source_reference"]}

        _CACHE[label] = {
            "input_binding": {"prepared_annual_input": {
                "company_id": filing["company_id"], "entity": filing["entity"],
                "filing": {"accessionNumber": filing["accession"],
                           "filingDate": filing["filing_date"]},
                "table_input": {"target_period": filing["target_period"]}}},
            "xml": part("xml"), "primary": part("primary"), "facts": part("facts")}
    return _CACHE[label]


def _inventory(resolution):
    return {(item.get("label") or item.get("concept")): item["disposition"]
            for item in resolution["selection"]["measurement"]["disclosure_inventory"]}


class TheOlderReportIsAnsweredWhereTheFrozenInventoryStopped(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.preparation = _preparation(FY2022)
        _, cls.frozen = frozen_candidates._b06_resolution(data_root=ROOT,
                                                          preparation=cls.preparation)
        _, cls.successor = route.fallback_resolution(data_root=ROOT, preparation=cls.preparation)

    def test_the_frozen_resolution_withholds_at_both_forms(self):
        reason = self.frozen["selection"]["reason"]
        self.assertEqual("WITHHELD", self.frozen["result"]["publication"])
        self.assertTrue(reason.startswith("UNRESOLVED_FINANCING_ITEM:"), reason)
        self.assertIn("Pass Through Certificates due 2022", reason)
        self.assertIn("us-gaap:definedbenefitplanbenefitobligation", reason)

    def test_the_successor_answers_with_both_rows_resolved(self):
        result, measurement = self.successor["result"], self.successor["selection"]["measurement"]
        self.assertEqual(("PUBLISHED", "PASS"), (result["publication"], result["reason_code"]))
        self.assertEqual("0.7568073360157200336857864695", result["value"])
        self.assertEqual("8088000000", str(measurement["carrying_amount"]))
        inventory = _inventory(self.successor)
        self.assertEqual("INCLUDED_IN_SELECTED_SET",
                         inventory["Pass Through Certificates due 2022 - 6.24%"])
        self.assertEqual("EXCLUDED_STANDARD_DIFFERENT_MEASUREMENT_OR_NATURE",
                         inventory["us-gaap:definedbenefitplanbenefitobligation"])
        self.assertNotIn("UNRESOLVED", inventory.values())

    def test_the_v2_content_checks_ran_on_the_successor_inventory(self):
        """The v2 checks are not skipped: the successor answer carries them in full."""
        checks = self.successor["selection"]["measurement"]["successor_content_checks"]
        self.assertEqual(frozen_v2.RESOLVER, checks["version"])
        self.assertEqual(65, len(checks["narrative_inventory"]))
        self.assertEqual({"NO_MONETARY_BALANCE_ASSERTION", "EXPLICIT_OTHER_PERIOD",
                          "EXPLICIT_NO_BORROWING_BALANCE"},
                         {row["disposition"] for row in checks["narrative_inventory"]})
        self.assertTrue(checks["primary_xml_numeric_agreement"])


class AReportTheFrozenResolverAnswersIsAnsweredIdentically(unittest.TestCase):

    def test_record_for_record(self):
        for label in ANSWERED_BY_THE_FROZEN:
            with self.subTest(label):
                preparation = _preparation(label)
                frozen = frozen_candidates._b06_resolution(data_root=ROOT, preparation=preparation)
                successor = route.fallback_resolution(data_root=ROOT, preparation=preparation)
                self.assertEqual("PUBLISHED", frozen[1]["result"]["publication"])
                self.assertEqual(frozen, successor)


class TheNextFormIsStillWithheld(unittest.TestCase):
    """Measured, not repaired: each removed form shows the next one."""

    def test_fy2021_and_fy2023_withhold_at_what_the_program_still_does_not_handle(self):
        expected = {"southwest_airlines:2021-12-31": "UNRESOLVED_FINANCING_ITEM:",
                    "southwest_airlines:2023-12-31": "B06_V2_NARRATIVE_BALANCE_UNSUPPORTED:"}
        for label, prefix in expected.items():
            with self.subTest(label):
                _, resolution = route.fallback_resolution(data_root=ROOT,
                                                          preparation=_preparation(label))
                self.assertEqual("WITHHELD", resolution["result"]["publication"])
                self.assertTrue(resolution["selection"]["reason"].startswith(prefix),
                                resolution["selection"]["reason"][:200])


class TheCascadeReachesTheSuccessors(unittest.TestCase):

    def test_each_successor_carries_exactly_its_substitutions(self):
        self.assertEqual(route.OLDER_FALLBACK_FORMS,
                         route.fallback_verify_v1.historical_substitutions)
        self.assertEqual(route.FALLBACK_V1_CALL, route.fallback_verify.historical_substitutions)
        self.assertEqual(route.FALLBACK_CALL, route.fallback_resolution.historical_substitutions)
        self.assertIs(frozen_v1.verify.__globals__, route.fallback_verify_v1.__globals__)

    def test_the_fallback_case_calls_the_successor_resolution(self):
        names = route._fallback_case.__code__.co_names
        self.assertIn("fallback_resolution", names)
        self.assertNotIn("_b06_resolution", names)


if __name__ == "__main__":
    unittest.main()
