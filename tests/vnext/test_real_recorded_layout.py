"""Real Marriott filing fixture through the production Reader workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from vnext.ai_adapter import build_recorded_adapter
from vnext.run_store import load_open_run
from vnext.workflow import create_review_run


FIXTURE_PATH = (
    REPO_ROOT
    / "fixtures"
    / "vnext"
    / "recorded"
    / "marriott_2025_reader_response.json"
)
SOURCE_PATH = (
    "evidence/accession_materials/"
    "marriott_international_1048286_000104828626000007/"
    "mar-20251231.htm"
)


class RealRecordedLayoutTest(unittest.TestCase):
    """Prove the checked-in response is bound to exact public filing bytes."""

    def test_marriott_real_layout_reaches_human_review(self) -> None:
        """Run the complete table-grid, Reader, Evidence, and Review path."""
        adapter = build_recorded_adapter(
            response_bytes=FIXTURE_PATH.read_bytes(),
            fixture_id="marriott-2025-real-layout-v1",
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            result = create_review_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                run_id="run:recorded:marriott-real-layout-v1",
                company_id="marriott_international",
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
                source_repo_relative_path=SOURCE_PATH,
                source_media_type="text/html",
                source_url=(
                    "https://www.sec.gov/Archives/edgar/data/1048286/"
                    "000104828626000007/mar-20251231.htm"
                ),
                accession="0001048286-26-000007",
                document_name="mar-20251231.htm",
                source_role="target_primary",
                request_attempt_id=(
                    "request:attempt:"
                    "ab0e9646e2392c66a2c835f60030605e2fde2f3676774b18"
                    "fbaa6dc2ccaca125"
                ),
                disclosure_spec_path=(
                    "catalog/disclosures/lodging_kpi_table.md"
                ),
                adapter=adapter,
                clock=None,
            )
            _manifest, records, decisions = load_open_run(run_dir=run_dir)
        self.assertEqual("PENDING_HUMAN_REVIEW", result["status"])
        self.assertEqual([], decisions)
        evidence = [
            record
            for record in records
            if record["record_type"] == "EVIDENCE_CHECK"
        ]
        self.assertEqual(1, len(evidence))
        self.assertEqual("PASS", evidence[0]["status"])
        self.assertEqual(
            {
                "adr": "185.81",
                "occupancy": "0.693",
                "revpar": "128.8",
            },
            evidence[0]["normalized_values"],
        )
        self.assertEqual(
            1,
            len(
                [
                    record
                    for record in records
                    if record["record_type"] == "REVIEW_UNIT"
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
