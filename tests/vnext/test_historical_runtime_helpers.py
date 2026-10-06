"""Historical consumers of #28's shared source/CSV helpers, without company install."""
import csv
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext import annual_sources, annual_update, csv_output, publication


ROOT = Path(__file__).resolve().parents[2]


class HistoricalRuntimeHelpersTest(unittest.TestCase):
    def test_legacy_consumers_share_the_same_errors_and_functions(self):
        self.assertIs(annual_update.saved_source, annual_sources.saved_source)
        self.assertIs(annual_update.AnnualUpdateError, annual_sources.AnnualUpdateError)
        self.assertIs(publication._csv_bytes, csv_output._csv_bytes)
        self.assertIs(publication.PublicationError, csv_output.PublicationError)
        self.assertEqual(publication.METRIC_FIELDS, csv_output.METRIC_FIELDS)
        self.assertEqual(publication.EVIDENCE_FIELDS, csv_output.EVIDENCE_FIELDS)

    def test_a_later_source_failure_cannot_fall_back_to_old_success(self):
        url = "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/source.htm"
        rows = [{"source_url": url, "method": "GET", "status_code": "200", "error": ""},
                {"source_url": url, "method": "GET", "status_code": "503", "error": "HTTP 503"}]
        with patch.object(annual_sources, "_rows", return_value=rows), \
                patch.object(annual_sources.annual_input, "_saved_source", side_effect=AssertionError("Old success reused")):
            with self.assertRaisesRegex(annual_update.AnnualUpdateError, "LATEST_SOURCE_REQUEST_FAILED"):
                annual_sources.saved_source(repo_root=ROOT, url=url)

    def test_actual_saved_current_range_and_missing_year_csv_bytes_are_preserved(self):
        folder = ROOT / "docs/evidence/issue47_history/company-entry-history-2026-10-06"
        paths = sorted([*folder.glob("*metrics_matrix.csv"), *folder.glob("*metric_evidence.csv")])
        self.assertEqual(6, len(paths))
        for path in paths:
            with self.subTest(table=path.name), path.open(newline="") as stream:
                reader = csv.DictReader(stream)
                fields, rows = tuple(reader.fieldnames), list(reader)
                self.assertEqual(path.read_bytes(), csv_output._csv_bytes(rows=rows, fieldnames=fields))

    def test_missing_csv_columns_are_a_failure_through_the_old_exception_name(self):
        with self.assertRaisesRegex(publication.PublicationError, "CSV schema differs"):
            csv_output._csv_bytes(rows=[{"company": "example"}], fieldnames=csv_output.METRIC_FIELDS)


if __name__ == "__main__":
    unittest.main()
