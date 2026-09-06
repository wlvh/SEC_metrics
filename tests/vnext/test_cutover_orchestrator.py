"""Formal Cutover orchestrator authorization and state-transition tests."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import sec_pipeline
import vnext.ai_adapter as ai_adapter
from sec_http import request_log_prefix_bytes
from tests.vnext.common import REPO_ROOT
from tests.vnext.projection_fixture_support import _write_registry
from tests.vnext.projection_fixture_support import scoped_repository
from tests.vnext.test_publication import write_csv
from tests.vnext.test_publication import request_ledger_fixture
from tests.vnext.test_publication import write_request_ledger_rows
from tools.vnext_review import append_human_decision
from vnext.batch_workflow import build_release_input_plan
from vnext.batch_workflow import request_attempt_binding
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.canonical import sha256_file, strict_json_file
from vnext.cutover import CutoverError, _disclosure_spec_path
from vnext.cutover import _freeze_structured_run, _run_identity
from vnext.cutover import _load_pinned_live_release_input_plan
from vnext.cutover import _live_retry_policy, _prepare_review_run
from vnext.cutover import _pin_live_release_input_plan
from vnext.cutover import _prepare_runs, _run_live_sec_acquisition
from vnext.cutover import _validate_live_sec_acquisition_receipt
from vnext.cutover import _write_sec_acquisition_receipt
from vnext.cutover import run_cutover
from vnext.publication import REQUIRED_BUNDLE_FILES
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS
from vnext.publication import _commit_initial_publication_chain
from vnext.publication import publication_layout
from vnext.publication import publication_state_snapshot
from vnext.qualification import QualificationError
from vnext.run_store import load_run_for_status


TEST_QUALIFICATION = {
    "schema_version": 1,
    "production_freeze_receipt_id": "sha256:" + "6" * 64,
    "production_semantic_tree_id": "sha256:" + "7" * 64,
    "second_layout": {"receipt_id": "sha256:" + "8" * 64},
    "post_freeze_holdout": {"receipt_id": "sha256:" + "9" * 64},
    "qualification_id": "sha256:" + "a" * 64,
}

TEST_PROJECTION_MANIFEST = {
    "projection_manifest_id": "sha256:" + "b" * 64,
    "publication_candidate_status": "PUBLISHABLE",
}


class CutoverOrchestratorTest(unittest.TestCase):
    """Prove one workflow gates remote authority, review, and publication."""

    @staticmethod
    def _marriott_legacy_snapshot(*, root: Path) -> Path:
        """Create one real-company frozen baseline from current root bytes.

        Args:
            root: Empty scenario root that owns the isolated legacy snapshot.

        Returns:
            Directory containing strict Marriott metrics/evidence and Golden.
        """
        legacy = root / "legacy"
        legacy.mkdir()
        for filename in ("metrics_matrix.csv", "metric_evidence.csv"):
            source = REPO_ROOT / "outputs" / filename
            with source.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                fieldnames = tuple(reader.fieldnames or ())
                rows = [
                    row
                    for row in reader
                    if row["company"] == "Marriott International"
                ]
            if not rows:
                raise AssertionError("Marriott legacy rows are absent")
            write_csv(
                path=legacy / filename,
                fieldnames=fieldnames,
                rows=rows,
            )
        shutil.copy2(
            REPO_ROOT / "outputs" / "golden_results.csv",
            legacy / "golden_results.csv",
        )
        return legacy

    @staticmethod
    def _commit_repository(*, repo_root: Path) -> None:
        """Commit the isolated authority consumed by formal validation.

        Args:
            repo_root: Complete scoped repository with no later source edits.
        """
        commands = (
            ("init",),
            ("config", "user.name", "Cutover Orchestrator Test"),
            ("config", "user.email", "cutover@example.invalid"),
            ("add", "."),
            ("commit", "-m", "test-only formal authority"),
        )
        for arguments in commands:
            completed = subprocess.run(
                ["git", "-C", str(repo_root), *arguments],
                check=False,
                capture_output=True,
            )
            if completed.returncode != 0:
                raise AssertionError(completed.stderr.decode("utf-8"))

    @classmethod
    def _marriott_repository(
        cls, *, root: Path, legacy_snapshot_dir: Path,
    ) -> Path:
        """Build one clean Marriott authority with exact SEC source ledger.

        Args:
            root: Scenario root for the copied repository.
            legacy_snapshot_dir: Filtered baseline inputs bound into
                Requirement.

        Returns:
            Clean committed repository usable by the fixed-root live workflow.
        """
        authority_workspace = root / "authority"
        authority_workspace.mkdir()
        repo_root = scoped_repository(
            workspace=authority_workspace,
            baseline_snapshot_dir=legacy_snapshot_dir,
        )

        # A one-company registry keeps this public-flow proof bounded while
        # retaining the same repository-derived planning and exact-set rules.
        registry_path = REPO_ROOT / "config" / "company_registry.csv"
        with registry_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fieldnames = tuple(reader.fieldnames or ())
            rows = [
                row
                for row in reader
                if row["company_id"] == "marriott_international"
            ]
        if len(rows) != 1:
            raise AssertionError("Marriott registry row is ambiguous")
        _write_registry(
            path=repo_root / "config" / "company_registry.csv",
            rows=rows,
            fieldnames=fieldnames,
        )

        source_relatives = (
            "evidence/companyfacts/CIK0001048286.json",
            "evidence/companyfacts/CIK0001048286.json.headers.json",
            (
                "evidence/accession_materials/"
                "marriott_international_1048286_000104828626000007/"
                "mar-20251231.htm"
            ),
            (
                "evidence/accession_materials/"
                "marriott_international_1048286_000104828626000007/"
                "mar-20251231.htm.headers.json"
            ),
        )
        for relative in source_relatives:
            destination = repo_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / relative, destination)

        # Both SourceReferences must resolve to one immutable ordered ledger
        # attempt; unrelated historical attempts are intentionally excluded.
        with (REPO_ROOT / "evidence/requests_log.csv").open(
            encoding="utf-8", newline="",
        ) as stream:
            source_rows = list(csv.DictReader(stream))
        ledger_rows = [
            row
            for row in source_rows
            if row["source_url"] in {
                (
                    "https://data.sec.gov/api/xbrl/companyfacts/"
                    "CIK0001048286.json"
                ),
                (
                    "https://www.sec.gov/Archives/edgar/data/1048286/"
                    "000104828626000007/mar-20251231.htm"
                ),
            }
            and row["status_code"] == "200"
            and not row["error"]
        ]
        if len(ledger_rows) != 2:
            raise AssertionError("Marriott source ledger exact set differs")
        portable_ledger_rows = []
        for row in ledger_rows:
            body_source = repo_root / row["repo_relative_path"]
            headers_source = repo_root / row["headers_repo_relative_path"]
            body_relative = Path(
                "evidence",
                "request_attempts",
                row["content_sha256"][:2],
                row["content_sha256"],
                row["document_name"],
            )
            attempt_dir = (
                repo_root
                / body_relative.parent
            )
            attempt_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(body_source, repo_root / body_relative)
            headers_digest = sha256_file(path=headers_source)
            headers_relative = body_relative.with_name(
                "{}.{}.headers.json".format(
                    row["document_name"], headers_digest,
                )
            )
            shutil.copy2(
                headers_source,
                repo_root / headers_relative,
            )
            portable_ledger_rows.append({
                **row,
                "repo_relative_path": body_relative.as_posix(),
                "headers_repo_relative_path": (
                    headers_relative.as_posix()
                ),
            })
        write_request_ledger_rows(
            repo_root=repo_root, rows=portable_ledger_rows,
        )

        # Formal provenance declares tests as runtime source. Copying that
        # tree lets the real semantic and clean-source gates execute here.
        shutil.copytree(
            REPO_ROOT / "tests",
            repo_root / "tests",
            dirs_exist_ok=True,
        )

        outputs = repo_root / "outputs"
        outputs.mkdir()
        for filename in (
            "metrics_matrix.csv", "metric_evidence.csv", "golden_results.csv",
        ):
            shutil.copy2(legacy_snapshot_dir / filename, outputs / filename)
        provenance_path = outputs / "validation_snapshot_provenance.json"
        provenance_path.write_bytes(b"legacy-baseline:provenance\n")
        synthetic = {
            "legacy_invariant_migration_receipt.json",
            "projection_manifest.json",
            "publication_validation_receipt.json",
        }
        for relative in sorted(REQUIRED_BUNDLE_FILES - synthetic):
            destination = repo_root / ROOT_MIRROR_RELATIVE_PATHS[relative]
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(
                    "legacy-baseline:{}\n".format(relative).encode("utf-8")
                )

        # The imported predecessor binds only the five baseline artifacts
        # required by the production importer; no test-authored PASS appears.
        baseline_path = (
            repo_root
            / "requirements"
            / "ai_first_v3_3_1"
            / "baseline_manifest.json"
        )
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        bound = baseline["artifact_digests"]
        baseline["artifact_digests"] = {
            "outputs/golden_results.csv": bound[
                "outputs/golden_results.csv"
            ],
            "outputs/metric_evidence.csv": bound[
                "outputs/metric_evidence.csv"
            ],
            "outputs/metrics_matrix.csv": bound[
                "outputs/metrics_matrix.csv"
            ],
            "outputs/validation_run_manifest.json": {
                "sha256": sha256_file(
                    path=outputs / "validation_run_manifest.json",
                ),
                "size": (
                    outputs / "validation_run_manifest.json"
                ).stat().st_size,
            },
            "outputs/validation_snapshot_provenance.json": {
                "sha256": sha256_file(path=provenance_path),
                "size": provenance_path.stat().st_size,
            },
        }
        baseline_path.write_bytes(canonical_json_bytes(value=baseline) + b"\n")
        cls._commit_repository(repo_root=repo_root)
        return repo_root

    @mock.patch("vnext.cutover._validate_live_authority_roots")
    def test_public_cutover_ignores_all_retired_resolvers(
        self, _authority: mock.Mock,
    ) -> None:
        """Publish through ``run_cutover`` while every retired path explodes.

        The provider, SEC acquisition, qualification, and expensive fault
        matrix are explicit test prerequisites. Planning, three Reader Runs,
        hash-bound test HUMAN decisions, freeze/replay validation, Batch,
        Projector, formal preparation, initial A-to-B commit, and read-back all
        execute through the supported production orchestrator. The temporary
        HUMAN decisions prove workflow reachability only; they are never full
        acceptance or live evidence.
        """

        def retired_resolver(*_args: object, **_kwargs: object) -> object:
            """Fail immediately if the public Cutover calls retired code."""
            raise AssertionError("retired legacy resolver was called")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = self._marriott_legacy_snapshot(root=root)
            repo_root = self._marriott_repository(
                root=root, legacy_snapshot_dir=legacy,
            )
            workspace = (
                repo_root
                / "artifacts"
                / "vnext"
                / "test-old-resolver-cutover"
            )
            publication_root = root / "official"
            provider_calls = []
            response_text = (
                REPO_ROOT
                / "fixtures"
                / "vnext"
                / "recorded"
                / "marriott_2025_reader_response.json"
            ).read_text(encoding="utf-8")
            raw_provider_response = canonical_json_bytes(
                value={
                    "id": "resp_test_old_resolver_public_flow",
                    "model": "gpt-5.6-terra",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": response_text,
                                }
                            ],
                        }
                    ],
                }
            )

            def provider_open(*, fullurl: object, timeout: int) -> object:
                """Return one deterministic Responses API observation.

                Args:
                    fullurl: Real urllib Request built by the OpenAI adapter.
                    timeout: D-01 timeout supplied to the transport boundary.

                Returns:
                    Context-managed response carrying exact provider bytes.
                """
                if (
                    getattr(fullurl, "full_url", "")
                    != "https://api.openai.com/v1/responses"
                    or timeout != 120
                ):
                    raise AssertionError("OpenAI request policy differs")
                provider_calls.append(getattr(fullurl, "data", b""))
                response = mock.MagicMock()
                response.__enter__.return_value = response
                response.__exit__.return_value = False
                response.headers = {
                    "x-request-id": "request:test:{}".format(
                        len(provider_calls)
                    )
                }
                response.read.return_value = raw_provider_response
                return response

            def sec_acquisition_prerequisite(
                *, repo_root: Path, workspace_dir: Path,
                executed_at_utc: str,
            ) -> dict:
                """Persist the exact dependency receipt required by resume.

                Args:
                    repo_root: Isolated repository authority.
                    workspace_dir: Repository-owned Cutover workspace.
                    executed_at_utc: Explicit test observation time.

                Returns:
                    Real content-addressed SEC prerequisite reference.
                """
                log_path = repo_root / "evidence" / "requests_log.csv"
                with log_path.open(encoding="utf-8", newline="") as stream:
                    before_rows = list(csv.DictReader(stream))
                before = {
                    "rows": before_rows,
                    "row_count": len(before_rows),
                    "content_sha256": sha256_file(path=log_path),
                }
                write_request_ledger_rows(
                    repo_root=repo_root,
                    rows=[*before_rows, *(dict(row) for row in before_rows)],
                )
                with log_path.open(encoding="utf-8", newline="") as stream:
                    after_rows = list(csv.DictReader(stream))
                after = {
                    "rows": after_rows,
                    "row_count": len(after_rows),
                    "content_sha256": sha256_file(path=log_path),
                }
                for relative in (
                    "outputs/company_resolution.csv",
                    "outputs/latest_filings_inventory.csv",
                    "outputs/accession_materials_inventory.csv",
                    "outputs/concept_inventory/marriott_companyfacts.csv",
                ):
                    path = repo_root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"test-only acquisition\n")
                completed = mock.Mock(
                    returncode=0, stdout=b"ok", stderr=b"",
                )
                with mock.patch(
                    "vnext.cutover._request_ledger_state",
                    side_effect=(before, after),
                ), mock.patch(
                    "vnext.cutover.subprocess.run", return_value=completed,
                ):
                    return _run_live_sec_acquisition(
                        repo_root=repo_root,
                        workspace_dir=workspace_dir,
                        executed_at_utc=executed_at_utc,
                    )

            def fault_prerequisite(**arguments: object) -> dict:
                """Materialize the isolated chain expected by Cutover.

                Args:
                    arguments: Public fault-matrix call fields from Cutover.

                Returns:
                    Test-only prerequisite identity after a real A-to-B commit.
                """
                successor_id = str(
                    arguments["prepared_successor_publication_id"]
                )
                official_layout = publication_layout(
                    publication_root=publication_root,
                )
                official_bundle = (
                    Path(official_layout["publications_dir"]) / successor_id
                )
                successor_manifest = strict_json_file(
                    path=official_bundle / "publication_manifest.json",
                )
                predecessor_id = str(
                    successor_manifest["previous_publication_id"]
                )
                fault_root = (
                    Path(str(arguments["cutover_workspace_dir"]))
                    / "fault_matrix_source"
                )
                fault_layout = publication_layout(
                    publication_root=fault_root,
                )
                destination = Path(fault_layout["publications_dir"])
                destination.mkdir(parents=True)
                for publication_id in (predecessor_id, successor_id):
                    shutil.copytree(
                        Path(official_layout["publications_dir"])
                        / publication_id,
                        destination / publication_id,
                    )
                _commit_initial_publication_chain(
                    publication_root=fault_root,
                    legacy_predecessor_publication_id=predecessor_id,
                    successor_publication_id=successor_id,
                    committed_at_utc="2026-08-06T12:00:01Z",
                )
                scenario = {
                    "scenario": "TEST_ONLY_FAULT_PREREQUISITE",
                    "predecessor": predecessor_id,
                    "successor": successor_id,
                }
                return {
                    "status": "PASSED",
                    "fault_matrix_id": content_hash(value=scenario),
                    "fault_receipt_references": [
                        {
                            "fault_receipt_id": content_hash(
                                value={**scenario, "role": "receipt"},
                            )
                        }
                    ],
                }

            with ExitStack() as stack:
                stack.enter_context(
                    mock.patch.dict(
                        os.environ,
                        {
                            "OPENAI_API_KEY": "test-only-secret",
                            "SEC_CONTACT_EMAIL": "operator@axaxl.co",
                        },
                    )
                )
                stack.enter_context(
                    mock.patch("vnext.cutover._REPOSITORY_ROOT", repo_root)
                )
                stack.enter_context(
                    mock.patch("vnext.ai_adapter._REPOSITORY_ROOT", repo_root)
                )
                stack.enter_context(
                    mock.patch.object(
                        ai_adapter._OPENAI_OPENER,
                        "open",
                        side_effect=provider_open,
                    )
                )
                stack.enter_context(
                    mock.patch(
                        "vnext.cutover.validate_cutover_qualifications",
                        return_value=TEST_QUALIFICATION,
                    )
                )
                stack.enter_context(
                    mock.patch(
                        "vnext.publication.validate_cutover_qualifications",
                        return_value=TEST_QUALIFICATION,
                    )
                )
                stack.enter_context(
                    mock.patch(
                        "vnext.publication.qualification_closure_paths",
                        return_value=(),
                    )
                )
                stack.enter_context(
                    mock.patch(
                        "vnext.cutover._run_live_sec_acquisition",
                        side_effect=sec_acquisition_prerequisite,
                    )
                )
                stack.enter_context(
                    mock.patch(
                        "vnext.cutover.run_cutover_publication_fault_matrix",
                        side_effect=fault_prerequisite,
                    )
                )
                for name in sec_pipeline.RETIRED_LEGACY_PRODUCER_NAMES:
                    stack.enter_context(
                        mock.patch.object(
                            sec_pipeline,
                            name,
                            side_effect=retired_resolver,
                        )
                    )

                with self.assertRaises(CutoverError) as pending:
                    run_cutover(
                        repo_root=repo_root,
                        workspace_dir=workspace,
                        legacy_snapshot_dir=repo_root / "outputs",
                        publication_root=publication_root,
                        execute_live=True,
                        recorded_response_path=None,
                        recorded_fixture_id=None,
                        commit=True,
                        validated_at_utc="2026-08-06T12:00:00Z",
                        committed_at_utc="2026-08-06T12:00:01Z",
                    )
                self.assertEqual(
                    "HUMAN_REVIEW_REQUIRED", pending.exception.code,
                )
                reviews = pending.exception.details["pending_reviews"]
                self.assertEqual(3, len(reviews))
                self.assertIsNone(
                    publication_state_snapshot(
                        publication_root=publication_root,
                    )["active_publication_id"]
                )

                for review in reviews:
                    append_human_decision(
                        run_dir=Path(str(review["run_dir"])),
                        review_unit_hash=str(review["review_unit_hash"]),
                        decision="APPROVE",
                        reviewer_id="human:test-only-old-resolver-flow",
                        decided_at_utc="2026-08-06T12:00:00Z",
                        reason=(
                            "Test-only explicit review of bound Marriott "
                            "claims; not acceptance evidence."
                        ),
                        supersedes_decision_id=None,
                    )

                result = run_cutover(
                    repo_root=repo_root,
                    workspace_dir=workspace,
                    legacy_snapshot_dir=repo_root / "outputs",
                    publication_root=publication_root,
                    execute_live=True,
                    recorded_response_path=None,
                    recorded_fixture_id=None,
                    commit=True,
                    validated_at_utc="2026-08-06T12:00:00Z",
                    committed_at_utc="2026-08-06T12:00:01Z",
                )
                metrics = (
                    publication_root / "outputs" / "metrics_matrix.csv"
                ).read_bytes()
                self.assertEqual("PUBLISHED", result["status"])
                self.assertEqual(
                    "PASS", result["candidate"]["compatibility_status"],
                )
                self.assertEqual(3, len(provider_calls))
                self.assertEqual(
                    result["publication_id"],
                    publication_state_snapshot(
                        publication_root=publication_root,
                    )["active_publication_id"],
                )
                for metric_id in (b"B01", b"B03", b"B10", b"B11"):
                    self.assertIn(metric_id, metrics)

    @mock.patch("vnext.cutover._validate_live_authority_roots")
    def test_live_preflight_reports_all_missing_credentials(
        self, _authority: mock.Mock,
    ) -> None:
        """Fail before source planning when either live identity is absent."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"SEC_CONTACT_EMAIL": ""},
            clear=True,
        ), mock.patch(
            "vnext.cutover.build_release_input_plan"
        ) as planner:
            with self.assertRaises(CutoverError) as raised:
                run_cutover(
                    repo_root=REPO_ROOT,
                    workspace_dir=Path(directory) / "workspace",
                    legacy_snapshot_dir=REPO_ROOT / "outputs",
                    publication_root=REPO_ROOT,
                    execute_live=True,
                    recorded_response_path=None,
                    recorded_fixture_id=None,
                    commit=True,
                    validated_at_utc="2026-08-06T00:00:00+00:00",
                    committed_at_utc="2026-08-06T00:00:01+00:00",
                )
        self.assertEqual("LIVE_PREREQUISITES_MISSING", raised.exception.code)
        self.assertEqual(
            ["DEEPSEEK_API_KEY_REQUIRED", "SEC_CONTACT_EMAIL_REQUIRED"],
            raised.exception.details["error_codes"],
        )
        planner.assert_not_called()

    def test_pending_human_review_blocks_projection_and_publication(
        self,
    ) -> None:
        """Keep real Runs OPEN and return exact recovery commands."""
        pending = {
            "run_id": "run:cutover:review:1",
            "run_dir": "/tmp/review-1",
            "review_unit_hash": "sha256:" + "1" * 64,
            "review_path": "/tmp/review-1/review.md",
            "review_command": (
                "python3 tools/vnext_review.py decide "
                "--run-dir /tmp/review-1"
            ),
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "vnext.cutover._prepare_runs",
            return_value={
                "batch_run_dirs": [],
                "live_attempts": [],
                "pending_reviews": [pending],
            },
        ), mock.patch(
            "vnext.cutover.build_release_input_plan",
            return_value={"release_input_plan_id": "sha256:" + "2" * 64},
        ), mock.patch(
            "vnext.cutover.write_projection_batch_manifest"
        ) as batch_writer, mock.patch(
            "vnext.cutover.prepare_publication_bundle"
        ) as publication_preparer:
            response = Path(directory) / "response.json"
            response.write_text("{}", encoding="utf-8")
            with self.assertRaises(CutoverError) as raised:
                run_cutover(
                    repo_root=REPO_ROOT,
                    workspace_dir=Path(directory) / "workspace",
                    legacy_snapshot_dir=REPO_ROOT / "outputs",
                    publication_root=REPO_ROOT,
                    execute_live=False,
                    recorded_response_path=response,
                    recorded_fixture_id="recorded-layout-v1",
                    commit=False,
                    validated_at_utc="2026-08-06T00:00:00+00:00",
                    committed_at_utc=None,
                )
        self.assertEqual("HUMAN_REVIEW_REQUIRED", raised.exception.code)
        self.assertEqual(
            [pending], raised.exception.details["pending_reviews"]
        )
        batch_writer.assert_not_called()
        publication_preparer.assert_not_called()

    @mock.patch("vnext.cutover._validate_live_authority_roots")
    def test_missing_qualification_code_blocks_live_before_planning(
        self, _authority: mock.Mock,
    ) -> None:
        """Preserve the qualification code without leaking internal details."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-only-secret",
                "SEC_CONTACT_EMAIL": "operator@example.co",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover.validate_sec_identity",
            return_value=("axaxl", "operator@example.co"),
        ), mock.patch(
            "vnext.cutover.validate_cutover_qualifications",
            side_effect=QualificationError(
                code="CUTOVER_QUALIFICATION_REQUIRED",
                message="sensitive internal detail",
            ),
        ), mock.patch(
            "vnext.cutover.build_release_input_plan",
        ) as planner:
            with self.assertRaises(CutoverError) as raised:
                run_cutover(
                    repo_root=REPO_ROOT,
                    workspace_dir=Path(directory) / "workspace",
                    legacy_snapshot_dir=REPO_ROOT / "outputs",
                    publication_root=REPO_ROOT,
                    execute_live=True,
                    recorded_response_path=None,
                    recorded_fixture_id=None,
                    commit=True,
                    validated_at_utc="2026-08-06T00:00:00+00:00",
                    committed_at_utc="2026-08-06T00:00:01+00:00",
                )

        self.assertEqual(
            "CUTOVER_QUALIFICATION_REQUIRED", raised.exception.code,
        )
        self.assertEqual({}, raised.exception.details)
        self.assertNotIn("sensitive", str(raised.exception))
        planner.assert_not_called()

    def test_live_retry_policy_is_derived_from_effective_d01(self) -> None:
        """Use the immutable effective Decision instead of a caller value."""
        policy = _live_retry_policy()

        self.assertEqual("D-01", policy["decision_id"])
        self.assertEqual(2, policy["retry_count"])
        self.assertRegex(
            str(policy["decision_record_hash"]), r"^sha256:[0-9a-f]{64}$",
        )
        self.assertRegex(
            str(policy["requirement_closure_hash"]),
            r"^sha256:[0-9a-f]{64}$",
        )

    def test_live_failures_are_independent_retries_before_three_successes(
        self,
    ) -> None:
        """Retain two failed Runs, then require three stable successes."""
        stable = {
            "candidate_hash": "sha256:" + "1" * 64,
            "evidence_check_id": "sha256:" + "2" * 64,
            "review_unit_hash": "sha256:" + "3" * 64,
            "review_context_hash": "sha256:" + "4" * 64,
            "rendered_review_hash": "sha256:" + "5" * 64,
            "selected_values_locators_claims": {
                "occupancy": {
                    "claimed_value": "69.3",
                    "locator": {"row": 1, "column": 1},
                },
            },
            "required_claims": {"scope": "systemwide"},
            "metric_results": [{
                "metric_id": "B10",
                "status": "MDA_OK",
                "value": "69.3",
            }],
            "effective_decision": {
                "approval_effect_hash": "sha256:" + "6" * 64,
                "decision": "APPROVE",
            },
        }

        def summary(*, status: str, ordinal: int) -> dict:
            """Return one path-free test attempt identity."""
            value = {
                "run_id": "run:cutover:" + str(ordinal) * 64,
                "run_dir": "run-{}".format(ordinal),
                "attempt_id": "attempt:{}".format(ordinal),
                "request_body_sha256": "0" * 64,
                "assistant_output_sha256": (
                    "" if status == "FAILED" else "c" * 64
                ),
                "raw_response_sha256": "a" * 64,
                "model_requested": "gpt-5.6-terra",
                "model_returned": (
                    "none" if status == "FAILED" else "gpt-5.6-terra"
                ),
                "provider_request_id": "request:{}".format(ordinal),
                "error_class": (
                    "OPENAI_TIMEOUT" if status == "FAILED" else ""
                ),
                "transport_observation_hash": "sha256:" + "b" * 64,
                "status": status,
                "decision_count": 1,
            }
            if status == "FAILED":
                value["failure_status"] = "FAILED_ATTEMPT"
            else:
                value.update(stable)
            return value

        attempts = [
            summary(status="FAILED", ordinal=1),
            summary(status="FAILED", ordinal=2),
            summary(status="FROZEN", ordinal=3),
            summary(status="FROZEN", ordinal=4),
            summary(status="FROZEN", ordinal=5),
        ]
        plan = {
            "release_input_plan_id": "sha256:" + "c" * 64,
            "companies": [
                {
                    "company_id": "company-1",
                    "table_source": {},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "vnext.cutover._freeze_structured_run",
            return_value=Path(directory) / "structured",
        ), mock.patch(
            "vnext.cutover._disclosure_spec_path",
            return_value="catalog/disclosures/test.md",
        ), mock.patch(
            "vnext.cutover._prepare_review_run",
            side_effect=attempts,
        ) as prepare:
            result = _prepare_runs(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory),
                plan=plan,
                execute_live=True,
                recorded_response_bytes=None,
                recorded_fixture_id=None,
                cutover_qualification=TEST_QUALIFICATION,
            )

            receipt_path = Path(str(result["live_stability_receipt_path"]))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            serialized = receipt_path.read_text(encoding="utf-8")

        self.assertEqual(5, prepare.call_count)
        self.assertEqual(
            ["attempt:1", "attempt:2", "attempt:3", "attempt:4", "attempt:5"],
            [attempt["attempt_id"] for attempt in result["live_attempts"]],
        )
        self.assertEqual(
            "SEMANTICS_STABLE_PENDING_COMPATIBILITY", receipt["status"]
        )
        self.assertEqual(2, receipt["retry_policy"]["retry_count"])
        self.assertEqual(
            TEST_QUALIFICATION,
            receipt["cutover_qualification"],
        )
        self.assertEqual(5, len(receipt["attempts"]))
        self.assertRegex(
            receipt_path.name,
            r"^live_reader_stability_[0-9a-f]{64}\.json$",
        )
        receipt_body = {
            field: receipt[field]
            for field in receipt
            if field != "stability_receipt_id"
        }
        self.assertEqual(
            content_hash(value=receipt_body),
            receipt["stability_receipt_id"],
        )
        self.assertEqual(
            "live_reader_stability_{}.json".format(
                receipt["stability_receipt_id"].split(":", maxsplit=1)[1]
            ),
            receipt_path.name,
        )
        self.assertNotIn(directory, serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_live_retry_exhaustion_stops_after_initial_plus_two(self) -> None:
        """Persist three failed Run identities and never invoke a fallback."""
        failed = []
        for ordinal in range(1, 4):
            failed.append(
                {
                    "run_id": "run:cutover:" + str(ordinal) * 64,
                    "run_dir": "run-{}".format(ordinal),
                    "attempt_id": "attempt:{}".format(ordinal),
                    "request_body_sha256": "0" * 64,
                    "assistant_output_sha256": "",
                    "raw_response_sha256": "",
                    "model_requested": "gpt-5.6-terra",
                    "model_returned": "none",
                    "provider_request_id": "",
                    "error_class": "OPENAI_RATE_LIMIT",
                    "transport_observation_hash": "sha256:" + "d" * 64,
                    "failure_status": "FAILED_ATTEMPT",
                    "status": "FAILED",
                    "decision_count": 0,
                }
            )
        plan = {
            "release_input_plan_id": "sha256:" + "e" * 64,
            "companies": [
                {
                    "company_id": "company-1",
                    "table_source": {},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "vnext.cutover._freeze_structured_run",
            return_value=Path(directory) / "structured",
        ), mock.patch(
            "vnext.cutover._disclosure_spec_path",
            return_value="catalog/disclosures/test.md",
        ), mock.patch(
            "vnext.cutover._prepare_review_run",
            side_effect=failed,
        ) as prepare:
            with self.assertRaises(CutoverError) as raised:
                _prepare_runs(
                    repo_root=REPO_ROOT,
                    workspace_dir=Path(directory),
                    plan=plan,
                    execute_live=True,
                    recorded_response_bytes=None,
                    recorded_fixture_id=None,
                    cutover_qualification=TEST_QUALIFICATION,
                )
            receipt_path = Path(
                str(raised.exception.details["stability_receipt_path"])
            )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(
            "LIVE_READER_RETRIES_EXHAUSTED", raised.exception.code,
        )
        self.assertEqual(3, prepare.call_count)
        self.assertEqual("FAILED_RETRIES_EXHAUSTED", receipt["status"])
        self.assertEqual(3, len(receipt["attempts"]))
        self.assertEqual(
            ["attempt:1", "attempt:2", "attempt:3"],
            [attempt["attempt_id"] for attempt in receipt["attempts"]],
        )

    def test_invalid_reader_response_is_sealed_as_independent_failed_run(
        self,
    ) -> None:
        """Make one schema failure immutable before a retry may begin."""
        plan = build_release_input_plan(
            repo_root=REPO_ROOT,
            legacy_snapshot_dir=REPO_ROOT / "outputs",
        )
        table_companies = [
            company
            for company in plan["companies"]
            if "table_source" in company
        ]
        self.assertEqual(1, len(table_companies))
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "failed-run"
            summary = _prepare_review_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                company=table_companies[0],
                plan_id=str(plan["release_input_plan_id"]),
                stability_ordinal=1,
                attempt_ordinal=1,
                disclosure_spec_path=_disclosure_spec_path(
                    repo_root=REPO_ROOT,
                ),
                execute_live=False,
                recorded_response_bytes=b'{"invalid":true}',
                recorded_fixture_id="invalid-reader-response",
            )
            manifest, records, decisions = load_run_for_status(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            validation = strict_json_file(path=run_dir / "validation.json")

        attempts = [
            record
            for record in records
            if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
        ]
        self.assertEqual("FAILED", summary["status"])
        self.assertEqual("FAILED_ATTEMPT", summary["failure_status"])
        self.assertEqual("FAILED", manifest["status"])
        self.assertEqual("FAILED", validation["status"])
        self.assertEqual(1, len(attempts))
        self.assertEqual("FAILED", attempts[0]["status"])
        self.assertEqual([], decisions)
        self.assertRegex(
            str(summary["run_audit_manifest_hash"]),
            r"^sha256:[0-9a-f]{64}$",
        )

    def test_recorded_builds_staging_without_publication_mutation(
        self,
    ) -> None:
        """Build an offline candidate while leaving active state alone."""
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "vnext.cutover.build_release_input_plan",
            return_value={"release_input_plan_id": "sha256:" + "3" * 64},
        ), mock.patch(
            "vnext.cutover._prepare_runs",
            return_value={
                "batch_run_dirs": [
                    Path(directory) / "workspace" / "runs" / "a"
                ],
                "live_attempts": [],
                "pending_reviews": [],
            },
        ), mock.patch(
            "vnext.cutover.write_projection_batch_manifest",
            return_value={"batch_manifest_id": "sha256:" + "4" * 64},
        ), mock.patch(
            "vnext.cutover.write_projection_candidate",
            return_value={"compatibility_status": "PASS"},
        ), mock.patch(
            "vnext.cutover.build_projection_manifest",
            return_value=TEST_PROJECTION_MANIFEST,
        ), mock.patch(
            "vnext.cutover._write_cutover_publication_validation_receipt"
        ) as validator, mock.patch(
            "vnext.cutover.prepare_publication_bundle"
        ) as publication_preparer, mock.patch(
            "vnext.cutover._commit_publication"
        ) as publication_committer:
            response = Path(directory) / "response.json"
            response.write_text("{}", encoding="utf-8")
            result = run_cutover(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory) / "workspace",
                legacy_snapshot_dir=REPO_ROOT / "outputs",
                publication_root=REPO_ROOT,
                execute_live=False,
                recorded_response_path=response,
                recorded_fixture_id="recorded-layout-v1",
                commit=False,
                validated_at_utc="2026-08-06T00:00:00+00:00",
                committed_at_utc=None,
            )
        self.assertEqual("PASSED_RECORDED_ONLY", result["status"])
        self.assertIsNone(result["publication_id"])
        validator.assert_not_called()
        publication_preparer.assert_not_called()
        publication_committer.assert_not_called()

    @mock.patch("vnext.cutover._validate_live_authority_roots")
    def test_live_success_prepares_and_commits_same_candidate(
        self, _authority: mock.Mock,
    ) -> None:
        """Use formal publication only after the shared staging phases pass."""
        previous = "publication_" + "5" * 64
        publication_id = "publication_" + "6" * 64

        def publication_state(*, publication_root: Path) -> dict:
            """Return isolated expected or official before/after state."""
            if publication_root.name == "fault_matrix_source":
                return {
                    "active_publication_id": publication_id,
                    "mirror_hashes": {},
                }
            if not hasattr(publication_state, "observed"):
                publication_state.observed = True
                return {
                    "active_publication_id": previous,
                    "mirror_hashes": {},
                }
            return {
                "active_publication_id": publication_id,
                "mirror_hashes": {},
            }

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-only-secret",
                "SEC_CONTACT_EMAIL": "operator@example.co",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover.validate_sec_identity",
            return_value=("axaxl", "operator@example.co"),
        ), mock.patch(
            "vnext.cutover.validate_cutover_qualifications",
            return_value=TEST_QUALIFICATION,
        ), mock.patch(
            "vnext.cutover._run_live_sec_acquisition",
            return_value={
                "receipt_id": "sha256:" + "0" * 64,
                "receipt_path": "artifacts/vnext/cutover/sec.json",
            },
        ), mock.patch(
            "vnext.cutover.build_release_input_plan",
            return_value={"release_input_plan_id": "sha256:" + "7" * 64},
        ), mock.patch(
            "vnext.cutover._prepare_runs",
            return_value={
                "batch_run_dirs": [
                    Path(directory) / "workspace" / "runs" / "a"
                ],
                "live_attempts": [{
                    "attempt_id": "attempt:1", "run_id": "run:1",
                }],
                "pending_reviews": [],
                "live_stability_receipt_id": "sha256:" + "f" * 64,
                "live_stability_receipt_path": (
                    "workspace/receipts/live_reader_stability.json"
                ),
                "semantic_stability_complete": True,
                "retry_policy": {"retry_count": 2},
            },
        ), mock.patch(
            "vnext.cutover.write_projection_batch_manifest",
            return_value={"batch_manifest_id": "sha256:" + "8" * 64},
        ), mock.patch(
            "vnext.cutover.write_projection_candidate",
            return_value={"compatibility_status": "PASS"},
        ), mock.patch(
            "vnext.cutover.build_projection_manifest",
            return_value=TEST_PROJECTION_MANIFEST,
        ), mock.patch.multiple(
            "vnext.cutover",
            _bind_live_strict_compatibility=mock.Mock(return_value={
                "attempts": [{
                    "attempt_id": "attempt:1", "run_id": "run:1",
                }],
                "stability_receipt_id": "sha256:" + "1" * 64,
                "stability_receipt_path": "final-stability.json",
            }),
            _write_live_attempt_audit_closure=mock.Mock(return_value={
                "audit_closure_id": "sha256:" + "2" * 64,
                "audit_closure_path": "audit",
                "portable_run_paths": {"run:1": "audit/runs/run-1"},
            }),
            _write_committed_cutover_receipt=mock.Mock(return_value={
                "receipt_id": "sha256:" + "3" * 64,
                "receipt_path": "committed-cutover.json",
            }),
            write_latest_run_status=mock.Mock(),
        ), mock.patch(
            "vnext.cutover.publication_state_snapshot",
            side_effect=publication_state,
        ), mock.patch(
            "vnext.cutover._write_cutover_publication_validation_receipt",
            return_value={"validation_receipt_id": "sha256:" + "9" * 64},
        ), mock.patch(
            "vnext.cutover.prepare_publication_bundle",
            return_value={"publication_id": publication_id},
        ), mock.patch(
            "vnext.cutover._write_staging_parity_receipt",
            return_value={
                "receipt_id": "sha256:" + "a" * 64,
                "receipt_path": "staging-parity.json",
                "legacy_invariant_migration_receipt_id": (
                    "sha256:" + "b" * 64
                ),
            },
        ), mock.patch(
            "vnext.cutover.run_cutover_publication_fault_matrix",
            return_value={
                "status": "PASSED",
                "fault_matrix_id": "sha256:" + "c" * 64,
                "fault_receipt_references": [
                    {"fault_receipt_id": "sha256:" + "d" * 64},
                ],
            },
        ), mock.patch(
            "vnext.cutover._write_formal_cutover_receipt",
            return_value={
                "receipt_id": "sha256:" + "e" * 64,
                "receipt_path": "cutover.json",
            },
        ), mock.patch(
            "vnext.cutover._commit_publication",
            return_value={"publication_id": publication_id},
        ) as publication_committer:
            result = run_cutover(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory) / "workspace",
                legacy_snapshot_dir=REPO_ROOT / "outputs",
                publication_root=REPO_ROOT,
                execute_live=True,
                recorded_response_path=None,
                recorded_fixture_id=None,
                commit=True,
                validated_at_utc="2026-08-06T00:00:00+00:00",
                committed_at_utc="2026-08-06T00:00:01+00:00",
            )
        self.assertEqual("PUBLISHED", result["status"])
        self.assertEqual(previous, result["previous_publication_id"])
        self.assertEqual(publication_id, result["publication_id"])
        self.assertEqual(
            TEST_QUALIFICATION,
            result["cutover_qualification"],
        )
        self.assertEqual(
            "sha256:" + "0" * 64,
            result["invocation_sec_acquisition_receipt_id"],
        )
        self.assertEqual(
            "artifacts/vnext/cutover/sec.json",
            result["invocation_sec_acquisition_receipt_path"],
        )
        publication_committer.assert_called_once_with(
            publication_root=REPO_ROOT,
            publication_id=publication_id,
            expected_active_publication_id=previous,
            committed_at_utc="2026-08-06T00:00:01+00:00",
        )

    @mock.patch("vnext.cutover._validate_live_authority_roots")
    def test_live_acquires_sec_inventory_before_release_planning(
        self, _authority: mock.Mock,
    ) -> None:
        """Refresh official SEC inputs before deriving any live Run plan."""
        order = []
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-only-secret",
                "SEC_CONTACT_EMAIL": "operator@example.co",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover.validate_sec_identity",
            return_value=("axaxl", "operator@example.co"),
        ), mock.patch(
            "vnext.cutover.validate_cutover_qualifications",
            return_value=TEST_QUALIFICATION,
        ), mock.patch(
            "vnext.cutover._run_live_sec_acquisition",
            side_effect=lambda **_arguments: order.append("acquisition") or {
                "receipt_id": "sha256:" + "a" * 64,
                "receipt_path": (
                    "artifacts/vnext/cutover/receipts/"
                    "sec_acquisition_{}.json".format("a" * 64)
                ),
            },
        ), mock.patch(
            "vnext.cutover.build_release_input_plan",
            side_effect=lambda **_arguments: order.append("plan") or {
                "release_input_plan_id": "sha256:" + "b" * 64,
            },
        ), mock.patch(
            "vnext.cutover._prepare_runs",
            return_value={
                "batch_run_dirs": [],
                "live_attempts": [],
                "pending_reviews": [{"review_unit_hash": "sha256:x"}],
                "live_stability_receipt_id": "sha256:" + "c" * 64,
                "live_stability_receipt_path": "receipts/stability.json",
            },
        ):
            with self.assertRaises(CutoverError) as raised:
                run_cutover(
                    repo_root=REPO_ROOT,
                    workspace_dir=Path(directory) / "workspace",
                    legacy_snapshot_dir=REPO_ROOT / "outputs",
                    publication_root=REPO_ROOT,
                    execute_live=True,
                    recorded_response_path=None,
                    recorded_fixture_id=None,
                    commit=True,
                    validated_at_utc="2026-08-06T00:00:00+00:00",
                    committed_at_utc="2026-08-06T00:00:01+00:00",
                )
        self.assertEqual("HUMAN_REVIEW_REQUIRED", raised.exception.code)
        self.assertEqual(["acquisition", "plan"], order)

    def test_live_core_rejects_all_caller_authority_roots_before_read(
        self,
    ) -> None:
        """Reject every non-exact live root before prerequisites or writes."""
        exact = {
            "repo_root": REPO_ROOT,
            "workspace_dir": REPO_ROOT / "artifacts/vnext/cutover",
            "legacy_snapshot_dir": REPO_ROOT / "outputs",
            "publication_root": REPO_ROOT,
        }
        with tempfile.TemporaryDirectory() as directory:
            caller = Path(directory)
            mutations = {
                "repo_root": caller / "repository",
                "workspace_dir": caller / "workspace",
                "legacy_snapshot_dir": caller / "legacy",
                "publication_root": caller / "publication",
            }
            for field, value in mutations.items():
                with self.subTest(field=field), mock.patch(
                    "vnext.cutover._validate_live_prerequisites",
                    side_effect=AssertionError(
                        "caller authority reached prerequisite read"
                    ),
                ) as prerequisites:
                    arguments = dict(exact)
                    arguments[field] = value
                    with self.assertRaises(CutoverError) as raised:
                        run_cutover(
                            **arguments,
                            execute_live=True,
                            recorded_response_path=None,
                            recorded_fixture_id=None,
                            commit=True,
                            validated_at_utc="2026-08-07T08:00:00Z",
                            committed_at_utc="2026-08-07T08:00:01Z",
                        )
                    self.assertEqual(
                        "LIVE_AUTHORITY_ROOT_INVALID",
                        raised.exception.code,
                    )
                    prerequisites.assert_not_called()
                    self.assertFalse(value.exists())

    def test_sec_acquisition_receipt_binds_fixed_stages_and_ledger_tail(
        self,
    ) -> None:
        """Persist command receipts for the exact non-legacy SEC stage set."""
        new_row = {
            "source_url": "https://www.sec.gov/test.json",
            "status_code": "200",
            "error": "",
            "content_sha256": "1" * 64,
            "repo_relative_path": "evidence/request_attempts/test/body.json",
            "headers_repo_relative_path": (
                "evidence/request_attempts/test/headers.json"
            ),
            "accession": "",
            "document_name": "test.json",
        }
        states = (
            {"rows": [], "row_count": 0, "content_sha256": "0" * 64},
            {
                "rows": [new_row],
                "row_count": 1,
                "content_sha256": "2" * 64,
            },
        )
        completed = mock.Mock(returncode=0, stdout=b"ok", stderr=b"")
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "vnext.cutover._request_ledger_state", side_effect=states,
        ), mock.patch(
            "vnext.cutover.subprocess.run", return_value=completed,
        ) as runner, mock.patch(
            "vnext.cutover.request_log_attempt_id",
            return_value="request:attempt:" + "3" * 64,
        ), mock.patch(
            "vnext.cutover._live_acquisition_artifacts",
            return_value={
                "outputs/company_resolution.csv": {
                    "sha256": "4" * 64,
                    "size": 1,
                }
            },
        ):
            root = Path(directory)
            reference = _run_live_sec_acquisition(
                repo_root=root,
                workspace_dir=root / "artifacts" / "vnext" / "cutover",
                executed_at_utc="2026-08-06T00:00:00+00:00",
            )
            receipt = json.loads(
                (root / reference["receipt_path"]).read_text(encoding="utf-8")
            )
            receipt_text = (root / reference["receipt_path"]).read_text(
                encoding="utf-8"
            )
        self.assertEqual(5, runner.call_count)
        self.assertEqual("PASSED", receipt["status"])
        self.assertEqual(1, len(receipt["new_attempts"]))
        self.assertEqual(reference["receipt_id"], receipt["receipt_id"])
        self.assertNotIn(str(Path(sys.executable).resolve()), receipt_text)
        self.assertEqual(
            {"$PYTHON_CURRENT"}, set(receipt["runtime_bindings"])
        )
        runtime = receipt["runtime_bindings"]["$PYTHON_CURRENT"]
        self.assertEqual(Path(sys.executable).resolve().name, runtime["name"])
        self.assertEqual(
            sha256_file(path=Path(sys.executable).resolve()),
            runtime["sha256"],
        )
        self.assertTrue(all(
            command["argv"][0] == "$PYTHON_CURRENT"
            for command in receipt["commands"]
        ))
        self.assertEqual(
            [
                "scripts/00_smoke_test_sec_access.py",
                "scripts/01_resolve_companies.py",
                "scripts/02_inventory_filings.py",
                "scripts/03_companyfacts_inventory.py",
                "scripts/05_fetch_accession_materials.py",
            ],
            [call.args[0][1] for call in runner.call_args_list],
        )

    def test_sec_acquisition_validator_binds_runtime_and_commands(
        self,
    ) -> None:
        """Reject a forged interpreter and an empty command observation."""
        stages = (
            "scripts/00_smoke_test_sec_access.py",
            "scripts/01_resolve_companies.py",
            "scripts/02_inventory_filings.py",
            "scripts/03_companyfacts_inventory.py",
            "scripts/05_fetch_accession_materials.py",
        )
        before_bytes = b"header\n"
        after_bytes = b"header\nrow\n"
        attempt_id = "request:attempt:" + "3" * 64
        row = {
            "source_url": "https://www.sec.gov/test.json",
            "status_code": "200",
            "error": "",
            "content_sha256": "1" * 64,
            "repo_relative_path": (
                "evidence/request_attempts/test/body.json"
            ),
            "headers_repo_relative_path": (
                "evidence/request_attempts/test/headers.json"
            ),
            "accession": "",
            "document_name": "test.json",
        }
        inventory = {
            "outputs/company_resolution.csv": {
                "sha256": "4" * 64,
                "size": 1,
            }
        }
        expected_runtime = {"name": "python-current", "sha256": "5" * 64}
        body = {
            "schema_version": 1,
            "receipt_type": "LIVE_SEC_ACQUISITION",
            "executed_at_utc": "2026-08-06T00:00:00+00:00",
            "status": "PASSED",
            "runtime_bindings": {"$PYTHON_CURRENT": expected_runtime},
            "commands": [
                {
                    "argv": ["$PYTHON_CURRENT", stage],
                    "duration_ms": 1,
                    "return_code": 0,
                    "stdout_sha256": sha256_bytes(content=b""),
                    "stdout_size": 0,
                    "stderr_sha256": sha256_bytes(content=b""),
                    "stderr_size": 0,
                    "error_class": "",
                }
                for stage in stages
            ],
            "ledger_before": {
                "row_count": 0,
                "content_sha256": sha256_bytes(content=before_bytes),
            },
            "ledger_after": {
                "row_count": 1,
                "content_sha256": sha256_bytes(content=after_bytes),
            },
            "new_attempts": [{
                "attempt_id": attempt_id,
                **row,
            }],
            "inventory_artifacts": inventory,
        }

        def addressed(*, value: dict[str, object]) -> dict[str, object]:
            """Add the canonical identity expected by the strict loader."""
            return {**value, "receipt_id": content_hash(value=value)}

        receipt = addressed(value=body)
        current = {
            "rows": [row],
            "row_count": 1,
            "content_sha256": sha256_bytes(content=after_bytes),
            "text": "ledger",
        }
        with mock.patch(
            "vnext.cutover._request_ledger_state", return_value=current,
        ), mock.patch(
            "vnext.cutover.request_log_prefix_bytes",
            side_effect=lambda *, text, row_count: (
                before_bytes if row_count == 0 else after_bytes
            ),
        ), mock.patch(
            "vnext.cutover.request_log_attempt_id", return_value=attempt_id,
        ), mock.patch(
            "vnext.cutover._live_acquisition_artifacts",
            return_value=inventory,
        ), mock.patch(
            "vnext.cutover._current_python_runtime_binding",
            return_value=expected_runtime,
        ):
            validated = _validate_live_sec_acquisition_receipt(
                repo_root=REPO_ROOT, receipt=receipt,
            )
            self.assertEqual(receipt, validated)

            forged_body = dict(body)
            forged_body["runtime_bindings"] = {
                "$PYTHON_CURRENT": {
                    "name": "not-the-running-python",
                    "sha256": "f" * 64,
                }
            }
            with self.assertRaises(CutoverError) as forged:
                _validate_live_sec_acquisition_receipt(
                    repo_root=REPO_ROOT,
                    receipt=addressed(value=forged_body),
                )
            self.assertEqual(
                "SEC_ACQUISITION_RECEIPT_INVALID", forged.exception.code,
            )

            empty_body = dict(body)
            empty_body["commands"] = []
            with self.assertRaises(CutoverError) as empty:
                _validate_live_sec_acquisition_receipt(
                    repo_root=REPO_ROOT,
                    receipt=addressed(value=empty_body),
                )
            self.assertEqual(
                "SEC_ACQUISITION_RECEIPT_INVALID", empty.exception.code,
            )

    def test_pinned_plan_rejects_caller_self_signed_sec_pass(self) -> None:
        """Reject a self-hashed PASSED receipt with no acquisition evidence."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(workspace=Path(directory))
            body = {
                "schema_version": 1,
                "release_id": "caller-self-signed-plan",
                "target_fiscal_year": 2025,
                "legacy_input_hashes": {},
                "companies": [{"company_id": "caller-self-signed"}],
            }
            plan = {
                **body,
                "release_input_plan_id": content_hash(value=body),
            }
            workspace = repo_root / "artifacts" / "vnext" / "self-signed"
            sec = _write_sec_acquisition_receipt(
                repo_root=repo_root,
                workspace_dir=workspace,
                body={
                    "schema_version": 1,
                    "receipt_type": "LIVE_SEC_ACQUISITION",
                    "status": "PASSED",
                },
            )
            with self.assertRaises(CutoverError) as raised:
                _pin_live_release_input_plan(
                    repo_root=repo_root,
                    workspace_dir=workspace,
                    plan=plan,
                    sec_acquisition=sec,
                )
                _load_pinned_live_release_input_plan(
                    repo_root=repo_root, workspace_dir=workspace,
                )
        self.assertEqual(
            "SEC_ACQUISITION_RECEIPT_INVALID", raised.exception.code
        )

    @mock.patch("vnext.cutover._validate_live_authority_roots")
    def test_incomplete_live_semantics_cannot_bootstrap_first_cutover(
        self, _authority: mock.Mock,
    ) -> None:
        """Reject the former test-only A-to-B production compatibility path."""
        predecessor = "publication_" + "1" * 64
        final = "publication_" + "2" * 64
        prepared = iter(
            ({"publication_id": predecessor}, {"publication_id": final})
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-only-secret",
                "SEC_CONTACT_EMAIL": "operator@example.co",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover.validate_sec_identity",
            return_value=("axaxl", "operator@example.co"),
        ), mock.patch(
            "vnext.cutover.validate_cutover_qualifications",
            return_value=TEST_QUALIFICATION,
        ), mock.patch(
            "vnext.cutover._run_live_sec_acquisition",
            return_value={
                "receipt_id": "sha256:" + "0" * 64,
                "receipt_path": "artifacts/vnext/cutover/sec.json",
            },
        ), mock.patch(
            "vnext.cutover.build_release_input_plan",
            return_value={"release_input_plan_id": "sha256:" + "3" * 64},
        ), mock.patch(
            "vnext.cutover._prepare_runs",
            return_value={
                "batch_run_dirs": [Path(directory) / "runs" / "a"],
                "live_attempts": [{
                    "attempt_id": "attempt:1", "run_id": "run:1",
                }],
                "pending_reviews": [],
                "live_stability_receipt_id": "sha256:" + "4" * 64,
                "live_stability_receipt_path": "receipts/stability.json",
            },
        ), mock.patch(
            "vnext.cutover.write_projection_batch_manifest",
            return_value={"batch_manifest_id": "sha256:" + "5" * 64},
        ), mock.patch(
            "vnext.cutover.write_projection_candidate",
            return_value={"compatibility_status": "PASS"},
        ), mock.patch(
            "vnext.cutover.build_projection_manifest",
            return_value=TEST_PROJECTION_MANIFEST,
        ), mock.patch(
            "vnext.cutover.publication_state_snapshot",
            return_value={"active_publication_id": None, "mirror_hashes": {}},
        ), mock.patch(
            "vnext.cutover._write_cutover_publication_validation_receipt",
            side_effect=(
                {"validation_receipt_id": "sha256:" + "6" * 64},
                {"validation_receipt_id": "sha256:" + "7" * 64},
            ),
        ) as validator, mock.patch(
            "vnext.cutover.prepare_publication_bundle",
            side_effect=lambda **_arguments: next(prepared),
        ), mock.patch(
            "vnext.cutover._write_staging_parity_receipt",
            return_value={
                "receipt_id": "sha256:" + "8" * 64,
                "receipt_path": "staging-parity.json",
                "legacy_invariant_migration_receipt_id": (
                    "sha256:" + "9" * 64
                ),
            },
        ), mock.patch(
            "vnext.cutover.run_cutover_publication_fault_matrix",
            return_value={
                "status": "PASSED",
                "fault_matrix_id": "sha256:" + "a" * 64,
                "fault_receipt_references": [
                    {"fault_receipt_id": "sha256:" + "b" * 64},
                ],
            },
        ), mock.patch(
            "vnext.cutover._write_formal_cutover_receipt",
            return_value={
                "receipt_id": "sha256:" + "c" * 64,
                "receipt_path": "cutover.json",
            },
        ), mock.patch(
            "vnext.cutover._commit_publication",
            side_effect=(
                {"publication_id": predecessor},
                {"publication_id": final},
            ),
        ) as committer:
            with self.assertRaises(CutoverError) as raised:
                run_cutover(
                    repo_root=REPO_ROOT,
                    workspace_dir=Path(directory) / "workspace",
                    legacy_snapshot_dir=REPO_ROOT / "outputs",
                    publication_root=REPO_ROOT,
                    execute_live=True,
                    recorded_response_path=None,
                    recorded_fixture_id=None,
                    commit=True,
                    validated_at_utc="2026-08-06T00:00:00+00:00",
                    committed_at_utc="2026-08-06T00:00:01+00:00",
                )
        self.assertEqual("CUTOVER_EVIDENCE_INCOMPLETE", raised.exception.code)
        validator.assert_not_called()
        committer.assert_not_called()

    @mock.patch("vnext.cutover._validate_live_authority_roots")
    def test_fault_matrix_passes_before_first_official_pointer_mutation(
        self, _authority: mock.Mock,
    ) -> None:
        """Prepare both bundles and pass faults before either official CAS."""
        predecessor = "publication_" + "1" * 64
        final = "publication_" + "2" * 64
        order = []
        official_states = iter((None, final))

        def publication_state(*, publication_root: Path) -> dict:
            """Return fault-source state or ordered official read-back."""
            active = (
                final
                if publication_root.name == "fault_matrix_source"
                else next(official_states)
            )
            return {"active_publication_id": active, "mirror_hashes": {}}

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-only-secret",
                "SEC_CONTACT_EMAIL": "operator@example.co",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover.validate_sec_identity",
            return_value=("axaxl", "operator@example.co"),
        ), mock.patch(
            "vnext.cutover.validate_cutover_qualifications",
            return_value=TEST_QUALIFICATION,
        ), mock.patch(
            "vnext.cutover._run_live_sec_acquisition",
            return_value={
                "receipt_id": "sha256:" + "0" * 64,
                "receipt_path": "artifacts/vnext/cutover/sec.json",
            },
        ), mock.patch(
            "vnext.cutover.build_release_input_plan",
            return_value={"release_input_plan_id": "sha256:" + "3" * 64},
        ), mock.patch(
            "vnext.cutover._prepare_runs",
            return_value={
                "batch_run_dirs": [Path(directory) / "runs" / "a"],
                "live_attempts": [{"attempt_id": "attempt:1"}],
                "pending_reviews": [],
                "live_stability_receipt_id": "sha256:" + "4" * 64,
                "live_stability_receipt_path": "receipts/stability.json",
                "semantic_stability_complete": True,
                "retry_policy": {"retry_count": 2},
            },
        ), mock.patch(
            "vnext.cutover.write_projection_batch_manifest",
            return_value={"batch_manifest_id": "sha256:" + "5" * 64},
        ), mock.patch(
            "vnext.cutover.write_projection_candidate",
            return_value={"compatibility_status": "PASS"},
        ), mock.patch(
            "vnext.cutover.build_projection_manifest",
            return_value=TEST_PROJECTION_MANIFEST,
        ), mock.patch.multiple(
            "vnext.cutover",
            _bind_live_strict_compatibility=mock.Mock(return_value={
                "attempts": [{
                    "attempt_id": "attempt:1", "run_id": "run:1",
                }],
                "stability_receipt_id": "sha256:" + "d" * 64,
                "stability_receipt_path": "final-stability.json",
            }),
            _write_live_attempt_audit_closure=mock.Mock(return_value={
                "audit_closure_id": "sha256:" + "e" * 64,
                "audit_closure_path": "audit",
                "portable_run_paths": {"run:1": "audit/runs/run-1"},
            }),
            prepare_legacy_baseline_predecessor=mock.Mock(return_value={
                "publication_id": predecessor,
            }),
            write_latest_run_status=mock.Mock(),
            _write_committed_cutover_receipt=mock.Mock(
                side_effect=lambda **_arguments: order.append(
                    "committed"
                ) or {
                    "receipt_id": "sha256:" + "f" * 64,
                    "receipt_path": "committed-cutover.json",
                },
            ),
            _commit_initial_publication_chain=mock.Mock(
                side_effect=lambda **_arguments: order.append(
                    "commit-chain:" + predecessor + "->" + final
                ) or {"active_pointer": {"publication_id": final}},
            ),
        ), mock.patch(
            "vnext.cutover.publication_state_snapshot",
            side_effect=publication_state,
        ), mock.patch(
            "vnext.cutover._write_cutover_publication_validation_receipt",
            side_effect=(
                {"validation_receipt_id": "sha256:" + "6" * 64},
                {"validation_receipt_id": "sha256:" + "7" * 64},
            ),
        ), mock.patch(
            "vnext.cutover.prepare_publication_bundle",
            return_value={"publication_id": final},
        ), mock.patch(
            "vnext.cutover._write_staging_parity_receipt",
            return_value={
                "receipt_id": "sha256:" + "a" * 64,
                "receipt_path": "staging-parity.json",
                "legacy_invariant_migration_receipt_id": (
                    "sha256:" + "b" * 64
                ),
            },
        ), mock.patch(
            "vnext.cutover.run_cutover_publication_fault_matrix",
            side_effect=lambda **_arguments: order.append("faults") or {
                "status": "PASSED",
                "fault_matrix_id": "sha256:" + "8" * 64,
                "fault_receipt_references": [
                    {"fault_receipt_id": "sha256:" + "9" * 64},
                ],
            },
        ), mock.patch(
            "vnext.cutover._write_formal_cutover_receipt",
            side_effect=lambda **_arguments: order.append("receipt") or {
                "receipt_id": "sha256:" + "c" * 64,
                "receipt_path": "cutover.json",
            },
        ), mock.patch(
            "vnext.cutover._commit_publication",
            side_effect=lambda **arguments: order.append(
                "commit:" + str(arguments["publication_id"])
            ) or {"publication_id": arguments["publication_id"]},
        ) as ordinary_commit:
            run_cutover(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory) / "workspace",
                legacy_snapshot_dir=REPO_ROOT / "outputs",
                publication_root=REPO_ROOT,
                execute_live=True,
                recorded_response_path=None,
                recorded_fixture_id=None,
                commit=True,
                validated_at_utc="2026-08-06T00:00:00+00:00",
                committed_at_utc="2026-08-06T00:00:01+00:00",
            )
        self.assertEqual(
            [
                "faults",
                "receipt",
                "commit-chain:" + predecessor + "->" + final,
                "committed",
            ],
            order,
        )
        ordinary_commit.assert_not_called()

    def test_failed_compatibility_never_reaches_publication(self) -> None:
        """Keep a complete but incompatible candidate explicitly BLOCKED."""
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "vnext.cutover.build_release_input_plan",
            return_value={"release_input_plan_id": "sha256:" + "a" * 64},
        ), mock.patch(
            "vnext.cutover._prepare_runs",
            return_value={
                "batch_run_dirs": [
                    Path(directory) / "workspace" / "runs" / "a"
                ],
                "live_attempts": [],
                "pending_reviews": [],
            },
        ), mock.patch(
            "vnext.cutover.write_projection_batch_manifest",
            return_value={"batch_manifest_id": "sha256:" + "b" * 64},
        ), mock.patch(
            "vnext.cutover.write_projection_candidate",
            return_value={"compatibility_status": "FAIL"},
        ), mock.patch(
            "vnext.cutover.build_projection_manifest",
            return_value=TEST_PROJECTION_MANIFEST,
        ), mock.patch(
            "vnext.cutover._write_cutover_publication_validation_receipt"
        ) as validator:
            response = Path(directory) / "response.json"
            response.write_text("{}", encoding="utf-8")
            result = run_cutover(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory) / "workspace",
                legacy_snapshot_dir=REPO_ROOT / "outputs",
                publication_root=REPO_ROOT,
                execute_live=False,
                recorded_response_path=response,
                recorded_fixture_id="recorded-layout-v1",
                commit=False,
                validated_at_utc="2026-08-06T00:00:00+00:00",
                committed_at_utc=None,
            )
        self.assertEqual("BLOCKED", result["status"])
        validator.assert_not_called()

    def test_cli_hides_traceback_unless_debug_is_explicit(self) -> None:
        """Return a stable JSON envelope for an expected operator blocker."""
        from tools import vnext_cutover

        error = CutoverError(
            code="HUMAN_REVIEW_REQUIRED",
            message="Explicit review is required.",
            details={"pending_reviews": []},
        )
        standard_output = io.StringIO()
        standard_error = io.StringIO()
        with mock.patch(
            "tools.vnext_cutover.run_cutover", side_effect=error,
        ), redirect_stdout(standard_output), redirect_stderr(standard_error):
            return_code = vnext_cutover.main(argv=["--json"])
        self.assertEqual(2, return_code)
        self.assertIn(
            '"code": "HUMAN_REVIEW_REQUIRED"', standard_output.getvalue()
        )
        self.assertNotIn("Traceback", standard_output.getvalue())
        self.assertEqual("", standard_error.getvalue())

    def test_resume_rejects_run_from_previous_release_input_plan(self) -> None:
        """Reject a FROZEN Run whose identity binds an earlier source plan."""
        plan = build_release_input_plan(
            repo_root=REPO_ROOT,
            legacy_snapshot_dir=REPO_ROOT / "outputs",
        )
        company = next(
            item
            for item in plan["companies"]
            if item["company_id"] == "jpmorgan_chase"
        )
        old_plan_id = str(plan["release_input_plan_id"])
        new_plan_id = "sha256:" + "0" * 64
        if old_plan_id == new_plan_id:
            new_plan_id = "sha256:" + "1" * 64
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "stable-company-workspace"
            _freeze_structured_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                company=company,
                plan_id=old_plan_id,
                execute_live=False,
            )
            with self.assertRaises(CutoverError) as raised:
                _freeze_structured_run(
                    repo_root=REPO_ROOT,
                    run_dir=run_dir,
                    company=company,
                    plan_id=new_plan_id,
                    execute_live=False,
                )
            manifest, _records, _decisions = load_run_for_status(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
        self.assertEqual("RELEASE_INPUT_PLAN_STALE", raised.exception.code)
        self.assertNotEqual(
            _run_identity(
                release_input_plan_id=new_plan_id,
                company_id="jpmorgan_chase",
                role="structured",
                ordinal=1,
            ),
            manifest["run_id"],
        )

    def test_pinned_live_plan_revalidates_without_latest_attempt_drift(
        self,
    ) -> None:
        """Resume the first live plan after an append-only retry attempt."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(workspace=Path(directory))
            request_ledger_fixture(repo_root=repo_root)
            log_path = repo_root / "evidence" / "requests_log.csv"
            with log_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            row = rows[0]
            source = {
                "accession": "0000078003-26-100099",
                "content_sha256": row["content_sha256"],
                "document_name": row["document_name"],
                "repo_relative_path": (
                    "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
                    "CIK0000078003.json"
                ),
                "source_url": row["source_url"],
            }
            source.update(request_attempt_binding(
                repo_root=repo_root,
                source_url=row["source_url"],
                content_sha256=row["content_sha256"],
                accession="0000078003-26-100099",
                document_name=row["document_name"],
            ))
            body = {
                "schema_version": 1,
                "release_id": "pinned-live-plan-test",
                "target_fiscal_year": 2025,
                "legacy_input_hashes": {},
                "companies": [{
                    "company_id": "pinned-company",
                    "companyfacts_source": source,
                }],
            }
            plan = {
                **body,
                "release_input_plan_id": content_hash(value=body),
            }
            workspace = repo_root / "artifacts" / "vnext" / "resume-plan"
            for relative in (
                "outputs/company_resolution.csv",
                "outputs/latest_filings_inventory.csv",
                "outputs/accession_materials_inventory.csv",
                "outputs/concept_inventory/pfizer_companyfacts.csv",
            ):
                path = repo_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture\n")
            ledger_text = log_path.read_text(encoding="utf-8")
            states = (
                {
                    "rows": [],
                    "row_count": 0,
                    "content_sha256": sha256_bytes(
                        content=request_log_prefix_bytes(
                            text=ledger_text, row_count=0,
                        )
                    ),
                },
                {
                    "rows": rows,
                    "row_count": len(rows),
                    "content_sha256": sha256_file(path=log_path),
                },
            )
            completed = mock.Mock(returncode=0, stdout=b"ok", stderr=b"")
            with mock.patch(
                "vnext.cutover._request_ledger_state", side_effect=states,
            ), mock.patch(
                "vnext.cutover.subprocess.run", return_value=completed,
            ):
                sec = _run_live_sec_acquisition(
                    repo_root=repo_root,
                    workspace_dir=workspace,
                    executed_at_utc="2026-08-06T00:00:00+00:00",
                )
            _pin_live_release_input_plan(
                repo_root=repo_root,
                workspace_dir=workspace,
                plan=plan,
                sec_acquisition=sec,
            )
            rows.append(dict(rows[0]))
            write_request_ledger_rows(repo_root=repo_root, rows=rows)
            resumed = _load_pinned_live_release_input_plan(
                repo_root=repo_root, workspace_dir=workspace,
            )
        self.assertIsNotNone(resumed)
        self.assertEqual(plan, resumed["plan"])
        self.assertEqual(sec, resumed["sec_acquisition"])

    def test_preseeded_human_resume_runs_fresh_sec_acquisition(
        self,
    ) -> None:
        """Reacquire SEC while retaining one exact pinned semantic plan."""
        plan_body = {
            "schema_version": 1,
            "release_id": "preseeded-live-plan",
            "target_fiscal_year": 2025,
            "legacy_input_hashes": {},
            "companies": [{"company_id": "preseeded-company"}],
        }
        plan = {
            **plan_body,
            "release_input_plan_id": content_hash(value=plan_body),
        }
        pending = {
            "run_dir": "/tmp/pinned-human-run",
            "review_unit_hash": "sha256:" + "d" * 64,
        }
        fresh = {
            "receipt_id": "sha256:" + "f" * 64,
            "receipt_path": (
                "artifacts/vnext/cutover/receipts/"
                "sec_acquisition_{}.json".format("f" * 64)
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            workspace = repo_root / "artifacts/vnext/cutover"
            legacy = repo_root / "outputs"
            legacy.mkdir()
            with mock.patch(
                "vnext.cutover._validate_live_sec_acquisition_receipt",
                return_value={},
            ):
                preseed = _write_sec_acquisition_receipt(
                    repo_root=repo_root,
                    workspace_dir=workspace,
                    body={
                        "schema_version": 1,
                        "receipt_type": "LIVE_SEC_ACQUISITION",
                        "status": "PASSED",
                    },
                )
                _pin_live_release_input_plan(
                    repo_root=repo_root,
                    workspace_dir=workspace,
                    plan=plan,
                    sec_acquisition=preseed,
                )
            with mock.patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-secret",
                    "SEC_CONTACT_EMAIL": "operator@axaxl.com",
                },
                clear=True,
            ), mock.patch(
                "vnext.cutover._REPOSITORY_ROOT", repo_root,
            ), mock.patch(
                "vnext.cutover._validate_live_prerequisites",
            ), mock.patch(
                "vnext.cutover.validate_cutover_qualifications",
                return_value=TEST_QUALIFICATION,
            ), mock.patch(
                "vnext.cutover._validate_live_sec_acquisition_receipt",
                return_value={},
            ), mock.patch(
                "vnext.cutover._resume_committed_cutover",
                return_value=None,
            ), mock.patch(
                "vnext.cutover._run_live_sec_acquisition",
                return_value=fresh,
            ) as acquisition, mock.patch(
                "vnext.cutover.build_release_input_plan",
            ) as planner, mock.patch(
                "vnext.cutover._prepare_runs",
                return_value={
                    "batch_run_dirs": [],
                    "live_attempts": [],
                    "pending_reviews": [pending],
                    "live_stability_receipt_id": "sha256:" + "e" * 64,
                    "live_stability_receipt_path": "stability.json",
                },
            ), mock.patch(
                "vnext.cutover.write_latest_run_status",
            ):
                with self.assertRaises(CutoverError) as raised:
                    run_cutover(
                        repo_root=repo_root,
                        workspace_dir=workspace,
                        legacy_snapshot_dir=legacy,
                        publication_root=repo_root,
                        execute_live=True,
                        recorded_response_path=None,
                        recorded_fixture_id=None,
                        commit=True,
                        validated_at_utc="2026-08-06T00:00:00Z",
                        committed_at_utc="2026-08-06T00:00:01Z",
                    )
        self.assertEqual("HUMAN_REVIEW_REQUIRED", raised.exception.code)
        acquisition.assert_called_once_with(
            repo_root=repo_root,
            workspace_dir=workspace,
            executed_at_utc="2026-08-06T00:00:00Z",
        )
        planner.assert_not_called()
        self.assertEqual(
            fresh["receipt_id"],
            raised.exception.details["sec_acquisition_receipt_id"],
        )
        self.assertEqual(
            fresh["receipt_path"],
            raised.exception.details["sec_acquisition_receipt_path"],
        )


if __name__ == "__main__":
    unittest.main()
