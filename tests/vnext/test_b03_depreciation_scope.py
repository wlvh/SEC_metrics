"""B03's D&A, read for what each filing says it covers.

The approved chain takes the first direct D&A concept a filing carries. These
cases hold the census that found Salesforce's first concept tagged on
fixed-asset depreciation only, so a census that stopped seeing that fact - the
way the earlier reading did not see it - fails on the filing.
"""
import importlib.util
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT

FINDING = "docs/evidence/issue47_history/b03-depreciation-scope/finding.json"
DEFECTS = "docs/evidence/issue47_history/known_result_defects.json"
TARGETED = "docs/evidence/issue47_history/b03-depreciation-scope/targeted-runs.json"
SALESFORCE = ("evidence/accession_materials/salesforce_1108524_000110852426000060/"
              "crm-20260131.htm")


def _census():
    spec = importlib.util.spec_from_file_location(
        "da_census", ROOT / "docs/evidence/issue47_history/b03-depreciation-scope/da_census.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheSubtotalIsInThePrimaryDocumentTest(unittest.TestCase):

    def test_salesforce_tags_fixed_asset_depreciation_with_the_chain_s_first_concept(self):
        facts = _census().census(document=SALESFORCE, period_start="2025-02-01",
                                 period_end="2026-01-31")
        direct = {(f["concept"], f["value"]) for f in facts}
        self.assertIn(("DepreciationDepletionAndAmortization", "1200000000.0"), direct)
        self.assertIn(("DepreciationAndAmortization", "3631000000"), direct)
        taken = next(f for f in facts if f["concept"] == "DepreciationDepletionAndAmortization")
        self.assertIn("Depreciation and amortization of fixed assets totaled", taken["text_before"])


class OnlyOneFilingsDirectCandidatesDisagreeTest(unittest.TestCase):

    def test_the_committed_finding_re_derives_and_names_one_filing(self):
        census = _census()
        finding = json.loads((ROOT / FINDING).read_text(encoding="utf-8"))
        chain = ("DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
                 "DepreciationAndAmortization")
        reading = json.loads((ROOT / "docs/evidence/issue47_history/content-acceptance/"
                              "cross-source-read.json").read_text(encoding="utf-8"))["per_position"]
        disagreeing = []
        for label, row in finding["per_position"].items():
            identity = reading[label]["metrics"]["B03"]["checked_identity"]
            facts = census.census(document=reading[label]["document"],
                                  period_start=identity["period_start"],
                                  period_end=identity["period_end"])
            values = {f["value"] for f in facts if f["concept"] in chain}
            with self.subTest(label):
                self.assertEqual(row["direct_candidates_agree"], len(values) <= 1)
            if len(values) > 1:
                disagreeing.append(label)
        self.assertEqual(["salesforce-2026"], disagreeing)


class TheDefectWithdrawsTheCoordinateTest(unittest.TestCase):

    def test_registered_and_released_only_on_the_withheld_result(self):
        """The published 0.2295 stays withdrawn; the release names the withheld repair only.

        Until the route was repaired this case asserted the entry had no release
        at all. The repair withholds the coordinate by name, and the entry now
        releases that one result under the version that produced it - so what
        is held here is that the release can never cover a published value.
        """
        defects = json.loads((ROOT / DEFECTS).read_text(encoding="utf-8"))["defects"]
        entry = next(d for d in defects if d["defect_id"]
                     == "B03_SALESFORCE_2026_CHAIN_TAKES_FIXED_ASSET_DEPRECIATION_AS_TOTAL")
        self.assertEqual(("salesforce", "B03", "2026-01-31", None),
                         (entry["company_id"], entry["metric_id"], entry["period_end"],
                          entry["result_id"]))
        runs = json.loads((ROOT / TARGETED).read_text(encoding="utf-8"))
        row = next(r for r in runs["rows"] if r["position"] == "salesforce-2026")
        withheld, published = row["targeted"]["results"]["B03"], row["batch"]["results"]["B03"]
        self.assertEqual(("WITHHELD", None), (withheld["publication"], withheld["value"]))
        self.assertEqual("PUBLISHED", published["publication"])
        self.assertEqual([(withheld["result_id"], runs["targeted_closure"])],
                         [(r["result_id"], r["requirement_closure_hash"])
                          for r in entry["released"]])
        self.assertNotIn(published["result_id"], [r["result_id"] for r in entry["released"]])


if __name__ == "__main__":
    unittest.main()
