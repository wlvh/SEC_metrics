"""Targeted complete Marriott originals; run separately from small business tests."""
import csv
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from sec_http import request_log_attempt_id
from vnext import lodging_table_source as lodging
from vnext.canonical import sha256_bytes
from vnext.normal_annual_input import annual_period
from vnext.sources import raw_blob_record, source_reference_record
from vnext.specs import compile_spec_file


ROOT = Path(__file__).resolve().parents[2]


class SavedSelectedLodgingSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = {m: compile_spec_file(path=ROOT / p, dependency_specs={})
                     for m, p in lodging.POLICY["metric_specs"].items()}
        with (ROOT / "evidence/requests_log.csv").open() as stream:
            ledger = list(csv.DictReader(stream))
        filings = json.loads((ROOT / "evidence/submissions/CIK0001048286.json").read_text())["filings"]["recent"]
        cls.arguments = {}
        cls.components = {}
        for year in (2023, 2024, 2025):
            filing = next({k: values[i] for k, values in filings.items()}
                          for i, form in enumerate(filings["form"])
                          if form == "10-K" and filings["reportDate"][i] == f"{year}-12-31")
            rows = [(i, row) for i, row in enumerate(ledger)
                    if row["source_url"].endswith("/" + filing["primaryDocument"])
                    and row["accession"] == filing["accessionNumber"]]
            index, row = rows[-1]
            assert row["status_code"] == "200" and not row["error"]
            raw = (ROOT / row["repo_relative_path"]).read_bytes()
            assert sha256_bytes(content=raw) == row["content_sha256"]
            blob = raw_blob_record(repo_root=ROOT, repo_relative_path=row["repo_relative_path"], media_type="text/html")
            reference = source_reference_record(raw_blob=blob, company_id="marriott_international",
                source_url=row["source_url"], accession=filing["accessionNumber"],
                document_name=filing["primaryDocument"], source_role="target_primary",
                request_attempt_id=request_log_attempt_id(row_index=index, row=row))
            args = {"raw": raw, "blob": blob, "reference": reference, "filing": filing,
                    "company_id": "marriott_international", "cik": "1048286",
                    "period": annual_period(raw=raw, cik="1048286", filing=filing)}
            cls.arguments[year] = args
            selected_args = {k: v for k, v in args.items() if k != "cik"}
            with patch.object(lodging, "annual_period", side_effect=AssertionError("DEI reread")):
                cls.components[year] = lodging.read_selected_lodging_source(
                    **selected_args, policy=lodging.POLICY, specs=cls.specs)

    def test_reported_values_units_year_headers_and_original_raw_positions(self):
        expected = {2023: ("0.692", "124.7", 66), 2024: ("0.698", "128.23", 67),
                    2025: ("0.693", "128.8", 68)}
        for year, (occupancy, revpar, count) in expected.items():
            with self.subTest(year=year):
                result = self.components[year]
                facts = result["selection"]["facts"]
                self.assertEqual((occupancy, revpar), (facts["B10"]["value"], facts["B11"]["value"]))
                self.assertEqual(("ratio", "USD"), (facts["B10"]["unit"], facts["B11"]["unit"]))
                self.assertEqual(count, result["table_count"])
                self.assertEqual("table_000011", result["selection"]["table_id"])
                for fact in facts.values():
                    self.assertEqual(self.arguments[year]["period"], fact["period"])
                    self.assertEqual(str(year), fact["source_witnesses"]["year"]["text"])
                    self.assertTrue(fact["source_witnesses"]["geography"]["raw_text"].startswith("\nWorldwide"))
                    for witness in fact["source_witnesses"].values():
                        locator = witness["locator"]
                        cell = lodging._resolve_verified_cell(derived_asset=result["derived_asset"], locator=locator)
                        self.assertEqual(witness["raw_text"], cell["raw_text"])
                self.assertFalse(result["ai_response_used"])
                self.assertFalse(result["native_run_created"])

    def test_current_compatibility_entry_returns_the_same_complete_component(self):
        result = lodging.inspect_lodging_table_source(**self.arguments[2025])
        self.assertEqual(self.components[2025], result)


if __name__ == "__main__":
    unittest.main()
