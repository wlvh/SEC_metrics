"""Production structured release Run tests using repository SEC bytes."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from tests.vnext.projection_fixture_support import scoped_repository
from tests.vnext.test_publication import request_ledger_fixture
from tests.vnext.test_publication import write_request_ledger_rows
from vnext.batch_workflow import build_release_input_plan
from vnext.batch_workflow import BatchWorkflowError
from vnext.batch_workflow import create_companyfacts_release_run
from vnext.batch_workflow import create_structural_release_run
from vnext.batch_workflow import request_attempt_binding
from vnext.batch_workflow import validate_planned_request_binding
from vnext.canonical import sha256_file
from vnext.run_store import load_open_run, validate_and_freeze_run


def legacy_request_binding_fixture(
    *, repo_root: Path,
) -> tuple[dict[str, str], dict[str, object]]:
    """Rewrite one fixture row to honest legacy working-file locators.

    Args:
        repo_root: Isolated scoped repository containing request evidence.

    Returns:
        Exact rewritten ledger row and its verified plan binding.
    """
    request_ledger_fixture(repo_root=repo_root)
    log_path = repo_root / "evidence/requests_log.csv"
    with log_path.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    original_body = repo_root / row["repo_relative_path"]
    original_headers = repo_root / row["headers_repo_relative_path"]
    working_root = repo_root / "evidence/legacy_working"
    working_root.mkdir(parents=True)
    working_body = working_root / row["document_name"]
    working_headers = working_root / (
        row["document_name"] + ".headers.json"
    )
    working_body.write_bytes(original_body.read_bytes())
    working_headers.write_bytes(original_headers.read_bytes())
    row["repo_relative_path"] = working_body.relative_to(
        repo_root
    ).as_posix()
    row["headers_repo_relative_path"] = working_headers.relative_to(
        repo_root
    ).as_posix()
    write_request_ledger_rows(repo_root=repo_root, rows=[row])
    binding = request_attempt_binding(
        repo_root=repo_root,
        source_url=row["source_url"],
        content_sha256=row["content_sha256"],
        accession="0000078003-26-100099",
        document_name=row["document_name"],
    )
    return row, binding


class BatchWorkflowTest(unittest.TestCase):
    """Prove B01/B03 and structural N/A use one production Run path."""

    def test_request_binding_prefers_verified_immutable_attempt(self) -> None:
        """Prefer immutable audit bytes over a later legacy working locator."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(
                workspace=Path(directory),
            )
            expected = request_ledger_fixture(repo_root=repo_root)
            log_path = repo_root / "evidence/requests_log.csv"
            with log_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            legacy = dict(rows[0])
            legacy["timestamp_utc"] = "2026-08-03T00:00:02+00:00"
            legacy["repo_relative_path"] = (
                "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
                "CIK0000078003.json"
            )
            legacy["headers_repo_relative_path"] = (
                legacy["repo_relative_path"] + ".headers.json"
            )
            rows.append(legacy)
            write_request_ledger_rows(repo_root=repo_root, rows=rows)
            binding = request_attempt_binding(
                repo_root=repo_root,
                source_url=rows[0]["source_url"],
                content_sha256=rows[0]["content_sha256"],
                accession="0000078003-26-100099",
                document_name=rows[0]["document_name"],
            )
        self.assertEqual(expected, binding["request_attempt_id"])
        self.assertEqual(
            "IMMUTABLE_ATTEMPT", binding["request_locator_kind"],
        )

    def test_request_binding_rejects_claimed_immutable_locator_tamper(
        self,
    ) -> None:
        """Fail closed when a ledger row claims an absent attempt locator."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(
                workspace=Path(directory),
            )
            request_ledger_fixture(
                repo_root=repo_root,
                row_changes={
                    "headers_repo_relative_path": (
                        "evidence/request_attempts/00/"
                        + "0" * 64
                        + "/missing.headers.json"
                    )
                },
            )
            log_path = repo_root / "evidence/requests_log.csv"
            with log_path.open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream))
            with self.assertRaises(BatchWorkflowError):
                request_attempt_binding(
                    repo_root=repo_root,
                    source_url=row["source_url"],
                    content_sha256=row["content_sha256"],
                    accession="0000078003-26-100099",
                    document_name=row["document_name"],
                )

    def test_legacy_request_binding_binds_and_rechecks_exact_bytes(
        self,
    ) -> None:
        """Bind unique working bytes and reject body or header drift."""
        for target_field in (
            "request_repo_relative_path",
            "request_headers_repo_relative_path",
        ):
            with self.subTest(target_field=target_field):
                with tempfile.TemporaryDirectory() as directory:
                    repo_root = scoped_repository(
                        workspace=Path(directory),
                    )
                    row, binding = legacy_request_binding_fixture(
                        repo_root=repo_root,
                    )
                    source = {
                        "accession": "0000078003-26-100099",
                        "content_sha256": row["content_sha256"],
                        "document_name": row["document_name"],
                        "source_url": row["source_url"],
                        **binding,
                    }
                    self.assertEqual(
                        "LEGACY_WORKING_LOCATOR",
                        binding["request_locator_kind"],
                    )
                    self.assertEqual(
                        row["content_sha256"],
                        binding["request_body_sha256"],
                    )
                    self.assertGreater(binding["request_body_size"], 0)
                    self.assertGreater(binding["request_headers_size"], 0)
                    self.assertEqual(
                        binding["request_attempt_id"],
                        validate_planned_request_binding(
                            repo_root=repo_root, source=source,
                        ),
                    )
                    target = repo_root / str(binding[target_field])
                    target.write_bytes(target.read_bytes() + b"tamper")
                    with self.assertRaisesRegex(
                        BatchWorkflowError,
                        "locator bytes|locators differ",
                    ):
                        validate_planned_request_binding(
                            repo_root=repo_root, source=source,
                        )

    def test_legacy_request_binding_rejects_non_regular_locator(
        self,
    ) -> None:
        """Never accept a symlink as recorded working-file authority."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(workspace=Path(directory))
            row, binding = legacy_request_binding_fixture(
                repo_root=repo_root,
            )
            body_path = repo_root / str(
                binding["request_repo_relative_path"]
            )
            real_path = body_path.with_name("real-body.json")
            real_path.write_bytes(body_path.read_bytes())
            body_path.unlink()
            body_path.symlink_to(real_path)
            with self.assertRaisesRegex(
                BatchWorkflowError, "locator evidence.*invalid"
            ):
                request_attempt_binding(
                    repo_root=repo_root,
                    source_url=row["source_url"],
                    content_sha256=row["content_sha256"],
                    accession="0000078003-26-100099",
                    document_name=row["document_name"],
                )

    def test_pinned_request_binding_survives_append_only_ledger_tail(
        self,
    ) -> None:
        """Keep one content-addressed plan stable after a later retry row."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(workspace=Path(directory))
            request_ledger_fixture(repo_root=repo_root)
            log_path = repo_root / "evidence/requests_log.csv"
            with log_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            row = rows[0]
            binding = request_attempt_binding(
                repo_root=repo_root,
                source_url=row["source_url"],
                content_sha256=row["content_sha256"],
                accession="0000078003-26-100099",
                document_name=row["document_name"],
            )
            source = {
                "accession": "0000078003-26-100099",
                "content_sha256": row["content_sha256"],
                "document_name": row["document_name"],
                "source_url": row["source_url"],
                **binding,
            }
            rows.append(dict(row))
            write_request_ledger_rows(repo_root=repo_root, rows=rows)
            latest = request_attempt_binding(
                repo_root=repo_root,
                source_url=row["source_url"],
                content_sha256=row["content_sha256"],
                accession="0000078003-26-100099",
                document_name=row["document_name"],
            )
            pinned = validate_planned_request_binding(
                repo_root=repo_root, source=source,
            )
        self.assertNotEqual(binding["request_attempt_id"], latest[
            "request_attempt_id"
        ])
        self.assertEqual(binding["request_attempt_id"], pinned)

    def test_marriott_companyfacts_recomputes_frozen_anchors(self) -> None:
        """Recompute both Marriott structured anchors from exact SEC bytes."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            source_path = (
                REPO_ROOT
                / "evidence/companyfacts/CIK0001048286.json"
            )
            binding = request_attempt_binding(
                repo_root=REPO_ROOT,
                source_url=(
                    "https://data.sec.gov/api/xbrl/companyfacts/"
                    "CIK0001048286.json"
                ),
                content_sha256=sha256_file(path=source_path),
                accession="0001048286-26-000007",
                document_name="CIK0001048286.json",
            )
            created = create_companyfacts_release_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                run_id="run:batch-workflow:marriott",
                company_id="marriott_international",
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
                source_repo_relative_path=(
                    "evidence/companyfacts/CIK0001048286.json"
                ),
                source_url=(
                    "https://data.sec.gov/api/xbrl/companyfacts/"
                    "CIK0001048286.json"
                ),
                accession="0001048286-26-000007",
                document_name="CIK0001048286.json",
                request_attempt_id=binding["request_attempt_id"],
            )
            manifest, records, decisions = load_open_run(run_dir=run_dir)
        self.assertEqual("marriott_international", manifest["company_id"])
        self.assertEqual([], decisions)
        self.assertEqual({"B01", "B03"}, set(created["results"]))
        self.assertEqual("26186000000", created["results"]["B01"]["value"])
        self.assertEqual(
            "0.1756281982738868097456656229",
            created["results"]["B03"]["value"],
        )
        self.assertEqual(
            {"B01", "B03"},
            {
                record["metric_id"]
                for record in records
                if record["record_type"] == "METRIC_RESULT"
            },
        )

    def test_non_lodging_run_adds_durable_structural_disclosures(self) -> None:
        """Persist B10/B11 N/A beside real Enphase B01/B03 results."""
        with tempfile.TemporaryDirectory() as directory:
            source_path = (
                REPO_ROOT
                / "evidence/companyfacts/CIK0001463101.json"
            )
            binding = request_attempt_binding(
                repo_root=REPO_ROOT,
                source_url=(
                    "https://data.sec.gov/api/xbrl/companyfacts/"
                    "CIK0001463101.json"
                ),
                content_sha256=sha256_file(path=source_path),
                accession="0001463101-26-000013",
                document_name="CIK0001463101.json",
            )
            created = create_companyfacts_release_run(
                repo_root=REPO_ROOT,
                run_dir=Path(directory) / "run",
                run_id="run:batch-workflow:enphase",
                company_id="enphase_energy",
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
                source_repo_relative_path=(
                    "evidence/companyfacts/CIK0001463101.json"
                ),
                source_url=(
                    "https://data.sec.gov/api/xbrl/companyfacts/"
                    "CIK0001463101.json"
                ),
                accession="0001463101-26-000013",
                document_name="CIK0001463101.json",
                request_attempt_id=binding["request_attempt_id"],
            )
        self.assertEqual(
            {"B01", "B03", "B10", "B11"}, set(created["results"]),
        )
        for metric_id in ("B10", "B11"):
            self.assertEqual(
                "N_A_STRUCTURAL",
                created["results"][metric_id]["applicability"],
            )
            self.assertEqual(
                "PUBLISHED",
                created["results"][metric_id]["publication"],
            )

    def test_financial_company_creates_four_no_source_structural_rows(
        self,
    ) -> None:
        """Create all migrated rows without reading or inventing data."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_structural_release_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                run_id="run:batch-workflow:jpm",
                company_id="jpmorgan_chase",
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )
            manifest, records, _decisions = load_open_run(run_dir=run_dir)
            frozen = validate_and_freeze_run(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
        self.assertEqual("FROZEN", frozen["status"])
        self.assertEqual([], manifest["source_references"])
        self.assertEqual(
            {"B01", "B03", "B10", "B11"}, set(created["results"]),
        )
        self.assertFalse(
            any(
                record["record_type"] in {"RAW_BLOB", "SOURCE_REFERENCE"}
                for record in records
            )
        )
        self.assertTrue(
            all(
                result["applicability"] == "N_A_STRUCTURAL"
                for result in created["results"].values()
            )
        )

    def test_frozen_legacy_builds_exact_ten_company_input_plan(self) -> None:
        """Derive source coordinates without caller-provided values."""
        plan = build_release_input_plan(
            repo_root=REPO_ROOT,
            legacy_snapshot_dir=REPO_ROOT / "outputs",
        )
        companies = plan["companies"]
        self.assertEqual(10, len(companies))
        self.assertEqual(10, len({item["company_id"] for item in companies}))
        self.assertEqual(2025, plan["target_fiscal_year"])
        modes = {item["company_id"]: item["mode"] for item in companies}
        self.assertEqual("STRUCTURAL_ONLY", modes["jpmorgan_chase"])
        self.assertEqual("COMPANYFACTS", modes["marriott_international"])
        lodging = next(
            item
            for item in companies
            if item["company_id"] == "marriott_international"
        )
        self.assertEqual(
            "evidence/accession_materials/"
            "marriott_international_1048286_000104828626000007/"
            "mar-20251231.htm",
            lodging["table_source"]["repo_relative_path"],
        )


if __name__ == "__main__":
    unittest.main()
