"""Prove formal Cutover cannot bypass second-layout and holdout evidence."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.vnext import qualification
from scripts.vnext.canonical import content_hash
from scripts.vnext.canonical import sha256_file
from scripts.vnext.qualification import SEMANTIC_DIRECTORIES
from scripts.vnext.qualification import SEMANTIC_FILES
from scripts.vnext.qualification import QualificationError
from scripts.vnext.qualification import production_semantic_tree
from scripts.vnext.qualification import reset_qualification_chain
from scripts.vnext.qualification import validate_cutover_qualifications
from scripts.vnext.qualification import write_production_freeze_receipt
from scripts.vnext.review import system_review_allowed
from tools import vnext_qualification
from vnext.requirements import load_requirement_snapshot
from vnext.run_store import _qualification_fixture_traits
from vnext.run_store import _run_company_authority
from vnext.traits import TraitError
from vnext.traits import repository_company_traits


def run_qualification_cli(*arguments: str) -> tuple[int, str, str]:
    """Run the qualification CLI while isolating its terminal output.

    Args:
        arguments: Exact CLI tokens excluding the executable and script path.

    Returns:
        Return code, stdout, and stderr captured from one command boundary.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        with contextlib.redirect_stderr(stderr):
            return_code = vnext_qualification.main(argv=list(arguments))
    return return_code, stdout.getvalue(), stderr.getvalue()


class CutoverQualificationTest(unittest.TestCase):
    """Exercise the fixed repository-owned qualification authority."""

    def test_layout_terminal_requires_approval_publish_and_validation(
        self,
    ) -> None:
        """Reject audit-only layout outcomes before they become Cutover proof."""
        approved = {
            "reviewer_type": "HUMAN",
            "decision": "APPROVE",
        }
        published = (
            {"metric_id": "B10", "publication": "PUBLISHED"},
            {"metric_id": "B11", "publication": "PUBLISHED"},
        )
        passed = {
            "record_type": "VALIDATION_RECEIPT",
            "status": "PASSED",
        }
        qualification._require_qualified_layout_terminal(
            decision=approved,
            results=published,
            validation=passed,
            expected_metric_ids=("B10", "B11"),
        )
        qualification._require_qualified_layout_terminal(
            decision={"reviewer_type": "SYSTEM", "decision": "APPROVE"},
            results=published,
            validation=passed,
            expected_metric_ids=("B10", "B11"),
        )

        cases = (
            (
                "rejected decision",
                {"reviewer_type": "HUMAN", "decision": "REJECT"},
                published,
                passed,
                "LAYOUT_REVIEW_APPROVAL_REQUIRED",
            ),
            (
                "withheld result",
                approved,
                (
                    {"metric_id": "B10", "publication": "WITHHELD"},
                    {"metric_id": "B11", "publication": "PUBLISHED"},
                ),
                passed,
                "LAYOUT_RESULTS_NOT_PUBLISHED",
            ),
            (
                "failed validation",
                approved,
                published,
                {
                    "record_type": "VALIDATION_RECEIPT",
                    "status": "FAILED",
                },
                "LAYOUT_VALIDATION_NOT_PASSED",
            ),
        )
        for label, decision, results, validation, code in cases:
            with self.subTest(label=label), self.assertRaisesRegex(
                QualificationError, code,
            ):
                qualification._require_qualified_layout_terminal(
                    decision=decision,
                    results=results,
                    validation=validation,
                    expected_metric_ids=("B10", "B11"),
                )

    def test_qualification_cli_keeps_unexpected_errors_structured(
        self,
    ) -> None:
        """Hide unexpected tracebacks unless the operator opts into debug."""
        failure = RuntimeError("unexpected qualification fixture state")
        with mock.patch(
            "tools.vnext_qualification.prepare_layout",
            side_effect=failure,
        ):
            return_code, stdout, stderr = run_qualification_cli(
                "prepare", "--fixture-id", "second-layout",
            )
        self.assertEqual(2, return_code)
        self.assertEqual("", stderr)
        payload = json.loads(stdout)
        self.assertEqual("BLOCKED", payload["status"])
        self.assertEqual(
            "QUALIFICATION_COMMAND_FAILED", payload["error_code"],
        )
        self.assertEqual("Qualification command failed", payload["message"])
        self.assertEqual("RuntimeError", payload["details"]["error_class"])
        self.assertNotIn("Traceback", stdout)

        with mock.patch(
            "tools.vnext_qualification.prepare_layout",
            side_effect=failure,
        ):
            return_code, stdout, stderr = run_qualification_cli(
                "--debug", "prepare", "--fixture-id", "second-layout",
            )
        self.assertEqual(2, return_code)
        self.assertEqual("QUALIFICATION_COMMAND_FAILED", json.loads(
            stdout,
        )["error_code"])
        self.assertIn("Traceback", stderr)

    def test_table_execute_surfaces_remote_failure_as_nonzero(self) -> None:
        """Stop the CLI on a persisted failed terminal before phase advance."""
        binding = {
            "target_period": {
                "fiscal_year": 2024,
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
            },
            "qualification_terminal_id": "sha256:" + "a" * 64,
            "qualification_task_plan_id": "sha256:" + "b" * 64,
        }

        class Authorization:
            """Return the exact fake binding needed by the CLI boundary."""

            def as_mapping(self) -> dict:
                """Return an isolated binding copy."""
                return dict(binding)

        result = {
            "run_id": "run:qualification:failed",
            "status": "FAILED_TERMINAL",
            "attempt_id": "attempt:failed",
        }
        with mock.patch(
            "tools.vnext_qualification.issue_table_qualification_authorization",
            return_value=Authorization(),
        ), mock.patch(
            "tools.vnext_qualification.execute_table_qualification_task",
            return_value=result,
        ), mock.patch(
            "tools.vnext_qualification.load_run_for_status",
            side_effect=AssertionError("failed terminal advanced to Run reload"),
        ):
            return_code, stdout, stderr = run_qualification_cli(
                "table-execute",
                "--family-id", "lodging_kpi_table",
                "--task-contract-id", "lodging_occupancy_table_v2",
                "--phase", "SECOND_LAYOUT",
                "--ordinal", "1",
                "--owner-token", "test-owner",
            )
        self.assertEqual(2, return_code)
        self.assertEqual("", stderr)
        payload = json.loads(stdout)
        self.assertEqual("BLOCKED", payload["status"])
        self.assertEqual(
            "TABLE_QUALIFICATION_FAILED_TERMINAL",
            payload["error_code"],
        )
        self.assertEqual(
            "FAILED_TERMINAL",
            payload["details"]["execution_status"],
        )
        self.assertEqual(
            binding["qualification_task_plan_id"],
            payload["details"]["qualification_task_plan_id"],
        )

    def test_qualification_system_review_is_explicit(
        self,
    ) -> None:
        """Accept an auditable SYSTEM approval without calling it HUMAN."""
        repo_root = Path(__file__).resolve().parents[2]
        requirement = load_requirement_snapshot(
            snapshot_dir=repo_root / "requirements/ai_first_v3_3_1",
        )
        self.assertTrue(system_review_allowed(requirement=requirement))

    def test_qualification_traits_are_bound_outside_registry(self) -> None:
        """Allow only the fixture-bound external issuer trait exception."""
        repo_root = Path(__file__).resolve().parents[2]
        fixture_id = "hilton-2024-sec-layout-v4"
        fixture = json.loads(
            (
                repo_root / "fixtures/vnext/layouts" / fixture_id
                / "fixture_manifest.json"
            ).read_text(encoding="utf-8")
        )
        manifest = {
            "run_id": "run:qualification:" + fixture_id,
            "company_id": fixture["company_id"],
            "company_traits": fixture["company_traits"],
            "target_period": fixture["target_period"],
            "source_references": [
                {
                    "company_id": fixture["company_id"],
                    "source_url": fixture["source_url"],
                    "accession": fixture["accession"],
                    "document_name": fixture["document_name"],
                    "source_role": fixture["source_role"],
                    "request_attempt_id": fixture["request_attempt_id"],
                    "raw_asset_id": "sha256:" + fixture["source_sha256"],
                }
            ],
        }
        traits, ciks = _qualification_fixture_traits(
            repo_root=repo_root, manifest=manifest,
        )
        self.assertEqual(fixture["company_traits"], traits)
        self.assertEqual([fixture["cik"]], ciks)
        manifest["company_traits"] = []
        with self.assertRaises(TraitError):
            _qualification_fixture_traits(
                repo_root=repo_root, manifest=manifest,
            )

    def test_registered_qualification_still_uses_fixture_traits(self) -> None:
        """Do not let Marriott registry traits mask its exact layout fixture."""
        repo_root = Path(__file__).resolve().parents[2]
        run_path = (
            repo_root
            / "artifacts/vnext/qualification/cycles/"
            "b63c68a8551ffa1ec49760d82874384869e5a621aa28e156ed9195e32920a651/"
            "runs/c330373bb347f8280560004e5fcd2eba2c053d2772364b752c208ee1e80c9c7a/"
            "manifest.json"
        )
        manifest = json.loads(run_path.read_text(encoding="utf-8"))
        self.assertNotEqual(
            manifest["company_traits"],
            repository_company_traits(
                repo_root=repo_root,
                company_id=str(manifest["company_id"]),
            ),
        )
        traits, ciks = _run_company_authority(
            repo_root=repo_root,
            manifest=manifest,
        )
        self.assertEqual(["lodging"], traits)
        self.assertEqual(["1048286"], ciks)

    def test_failed_qualification_chain_can_reset_with_audit(self) -> None:
        """Archive only a failed pre-active chain before requalification."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            manifest_path = repo_root / "artifacts/vnext/qualification/manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            previous = {
                "schema_version": 1,
                "production_freeze_receipt": {"stale": "freeze"},
                "second_layout_receipt": {"stale": "second"},
                "holdout_receipt": {"stale": "holdout"},
            }
            manifest_path.write_text(
                json.dumps(previous), encoding="utf-8",
            )
            with mock.patch.object(
                qualification,
                "validate_cutover_qualifications",
                side_effect=QualificationError(
                    code="POST_FREEZE_PRODUCTION_DRIFT",
                    message="drift",
                ),
            ):
                receipt = reset_qualification_chain(
                    repo_root=repo_root,
                    reset_at_utc="2026-08-17T00:00:00Z",
                    reason="SOURCE_PATH_NORMALIZATION",
                )
            self.assertEqual(
                "POST_FREEZE_PRODUCTION_DRIFT",
                receipt["prior_blocker_code"],
            )
            self.assertTrue(
                (repo_root / receipt["receipt_path"]).is_file(),
            )
            self.assertEqual(
                {
                    "schema_version": 1,
                    "production_freeze_receipt": None,
                    "second_layout_receipt": None,
                    "holdout_receipt": None,
                },
                json.loads(manifest_path.read_text(encoding="utf-8")),
            )

    def test_registry_identity_rejects_company_id_cik_alias(self) -> None:
        """Treat primary, related, and role CIK as production identity."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            registry = repo_root / "config/company_registry.csv"
            registry.parent.mkdir(parents=True, exist_ok=True)
            registry.write_text(
                "company_id,primary_cik,related_ciks,roles\n"
                "issuer_a,0000000123,456;0000000789,"
                "successor:123;predecessor:456\n",
                encoding="utf-8",
            )
            identities = qualification._registry_identities(
                repo_root=repo_root,
            )
        self.assertEqual(("issuer_a",), identities["company_ids"])
        self.assertEqual(("123", "456", "789"), identities["ciks"])

    def test_identical_marriott_grid_cannot_self_declare_differences(
        self,
    ) -> None:
        """Reject novelty labels when the replayed grid is identical."""
        repo_root = Path(__file__).resolve().parents[2]
        provenance = json.loads(
            (
                repo_root
                / "fixtures/vnext/recorded/"
                "marriott_2025_fixture_provenance.json"
            ).read_text(encoding="utf-8")
        )
        fixture = {
            "selection_reason": "Adversarial identical-grid fixture.",
            "layout_differences": ["column_order", "scope_wording"],
            "excerpt_repo_relative_path": provenance["excerpt_path"],
            "excerpt_sha256": provenance["excerpt_sha256"],
            "recorded_response_repo_relative_path": provenance[
                "response_path"
            ],
            "recorded_response_sha256": provenance["response_sha256"],
        }
        with self.assertRaisesRegex(
            QualificationError,
            "LAYOUT_DIFFERENCE_NOT_REPLAYABLE",
        ):
            qualification._mechanical_layout_comparison(
                repo_root=repo_root,
                fixture=fixture,
            )

    def test_layout_differences_are_replayed_against_marriott_bytes(
        self,
    ) -> None:
        """Persist only dimensions derived from changed grid/response bytes."""
        source_root = Path(__file__).resolve().parents[2]
        source_provenance_path = (
            source_root
            / "fixtures/vnext/recorded/"
            "marriott_2025_fixture_provenance.json"
        )
        provenance = json.loads(
            source_provenance_path.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            for relative in (
                "fixtures/vnext/recorded/layout_reference.json",
                "fixtures/vnext/recorded/"
                "marriott_2025_fixture_provenance.json",
                provenance["excerpt_path"],
                provenance["response_path"],
            ):
                target = repo_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((source_root / relative).read_bytes())
            excerpt = json.loads(
                (source_root / provenance["excerpt_path"]).read_text(
                    encoding="utf-8"
                )
            )
            response = json.loads(
                (source_root / provenance["response_path"]).read_text(
                    encoding="utf-8"
                )
            )
            excerpt["cells"][0]["text"] = "Fiscal 2025"
            for candidate in response["candidates"]:
                candidate["scope_evidence_locators"][0]["text"] = (
                    "Fiscal 2025"
                )
                candidate["scope_evidence_locators"][1]["text"] = (
                    "Comparable owned and managed hotels"
                )
            candidate_root = repo_root / "fixtures/vnext/layouts/candidate"
            candidate_root.mkdir(parents=True, exist_ok=True)
            excerpt_path = candidate_root / "excerpt.json"
            response_path = candidate_root / "response.json"
            excerpt_path.write_text(
                json.dumps(excerpt, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            response_path.write_text(
                json.dumps(response, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            comparison = qualification._mechanical_layout_comparison(
                repo_root=repo_root,
                fixture={
                    "selection_reason": "Independent header and scope.",
                    "layout_differences": [
                        "scope_wording", "table_header",
                    ],
                    "excerpt_repo_relative_path": excerpt_path.relative_to(
                        repo_root
                    ).as_posix(),
                    "excerpt_sha256": sha256_file(path=excerpt_path),
                    "recorded_response_repo_relative_path": (
                        response_path.relative_to(repo_root).as_posix()
                    ),
                    "recorded_response_sha256": sha256_file(
                        path=response_path,
                    ),
                },
            )
        self.assertEqual(
            ["scope_wording", "table_header"],
            comparison["verified_declared_differences"],
        )
        self.assertNotEqual(
            comparison["reference"]["grid_id"],
            comparison["candidate"]["grid_id"],
        )

    def test_second_and_holdout_require_independent_source_identity(
        self,
    ) -> None:
        """Reject CIK, accession, and source-byte aliases independently."""
        base = {
            "company_id": "second_company",
            "cik": "0000000123",
            "accession": "0000000123-26-000001",
            "source_sha256": "1" * 64,
        }
        holdout = {
            "company_id": "holdout_company",
            "cik": "0000000456",
            "accession": "0000000456-26-000002",
            "source_sha256": "2" * 64,
        }
        for field in ("cik", "accession", "source_sha256"):
            aliased = dict(holdout)
            aliased[field] = (
                "123" if field == "cik" else base[field]
            )
            with self.subTest(field=field), self.assertRaisesRegex(
                QualificationError,
                "HOLDOUT_NOT_INDEPENDENT",
            ):
                qualification._validate_independent_layouts(
                    second=base,
                    holdout=aliased,
                )

    def test_freeze_inventory_rejects_preexisting_holdout_bytes_and_run(
        self,
    ) -> None:
        """Prove holdout fixture bytes and Run namespace start after freeze."""
        for preexisting in ("fixture_bytes", "run"):
            with self.subTest(preexisting=preexisting):
                self._assert_preexisting_holdout_rejected(
                    preexisting=preexisting,
                )

    def _assert_preexisting_holdout_rejected(
        self, *, preexisting: str,
    ) -> None:
        """Freeze one adversarial namespace and verify ordering rejection.

        Args:
            preexisting: ``fixture_bytes`` or ``run`` alias introduced before
                the production freeze.
        """
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._semantic_repository(root=repo_root)
            self._write_second_layout_reference(repo_root=repo_root)
            fixture_root = (
                repo_root / "fixtures/vnext/layouts/holdout_fixture"
            )
            source_path = fixture_root / "holdout.htm"
            excerpt_path = fixture_root / "excerpt.json"
            response_path = fixture_root / "response.json"
            if preexisting == "fixture_bytes":
                fixture_root.mkdir(parents=True, exist_ok=True)
                for path, value in (
                    (source_path, "source"),
                    (excerpt_path, "excerpt"),
                    (response_path, "response"),
                ):
                    path.write_text(value, encoding="utf-8")
            run_path = (
                repo_root
                / "artifacts/vnext/qualification/runs/holdout_fixture"
            )
            if preexisting == "run":
                run_path.mkdir(parents=True, exist_ok=True)
                (run_path / "manifest.json").write_text(
                    "{}\n", encoding="utf-8",
                )
            freeze = write_production_freeze_receipt(
                repo_root=repo_root,
                frozen_at_utc="2026-08-06T10:39:00Z",
            )
            if preexisting == "run":
                fixture_root.mkdir(parents=True, exist_ok=True)
                for path, value in (
                    (source_path, "new source"),
                    (excerpt_path, "new excerpt"),
                    (response_path, "new response"),
                ):
                    path.write_text(value, encoding="utf-8")
            holdout = {
                "fixture_id": "holdout_fixture",
                "source_repo_relative_path": source_path.relative_to(
                    repo_root
                ).as_posix(),
                "source_sha256": sha256_file(path=source_path),
                "excerpt_repo_relative_path": excerpt_path.relative_to(
                    repo_root
                ).as_posix(),
                "excerpt_sha256": sha256_file(path=excerpt_path),
                "recorded_response_repo_relative_path": (
                    response_path.relative_to(repo_root).as_posix()
                ),
                "recorded_response_sha256": sha256_file(
                    path=response_path,
                ),
                "run_repo_relative_path": run_path.relative_to(
                    repo_root
                ).as_posix(),
            }
            with self.assertRaisesRegex(
                QualificationError,
                "HOLDOUT_EXISTED_BEFORE_FREEZE",
            ):
                qualification._validate_post_freeze_holdout(
                    freeze=freeze, holdout=holdout,
                )

    def test_freeze_requires_preexisting_second_layout_receipt(self) -> None:
        """Prevent a post-freeze fixture from posing as the second layout."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._semantic_repository(root=repo_root)
            with self.assertRaisesRegex(
                QualificationError,
                "SECOND_LAYOUT_REQUIRED_BEFORE_FREEZE",
            ):
                write_production_freeze_receipt(
                    repo_root=repo_root,
                    frozen_at_utc="2026-08-06T10:39:00Z",
                )

    def _semantic_repository(self, *, root: Path) -> None:
        """Create the smallest complete semantic tree for freeze tests.

        Args:
            root: Empty temporary repository root.
        """
        for relative in SEMANTIC_DIRECTORIES:
            directory = root / relative
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "authority.txt").write_text(
                relative.as_posix(), encoding="utf-8",
            )
        for relative in SEMANTIC_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative.as_posix(), encoding="utf-8")

    def _write_second_layout_reference(self, *, repo_root: Path) -> str:
        """Persist a minimal addressed second-layout ordering witness.

        Args:
            repo_root: Semantic fixture repository receiving the witness.

        Returns:
            Content-addressed receipt identity bound by the later freeze.

        The full qualification validator still replays the real layout Run;
        this fixture isolates only the pre-freeze ordering invariant.
        """
        tree = production_semantic_tree(repo_root=repo_root)
        body = {
            "schema_version": 1,
            "receipt_type": "SECOND_LAYOUT",
            "production_semantic_tree_id": tree["semantic_tree_id"],
        }
        receipt_id = content_hash(value=body)
        relative = (
            Path("artifacts/vnext/qualification/receipts")
            / (receipt_id.split(":", maxsplit=1)[1] + ".json")
        )
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {**body, "receipt_id": receipt_id},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 1,
            "production_freeze_receipt": None,
            "second_layout_receipt": {
                "receipt_id": receipt_id,
                "receipt_path": relative.as_posix(),
            },
            "holdout_receipt": None,
        }
        manifest_path = (
            repo_root / "artifacts/vnext/qualification/manifest.json"
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return receipt_id

    def test_missing_qualification_manifest_blocks_formal_cutover(
        self,
    ) -> None:
        """Reject live publication before any layout evidence is inspected."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            with self.assertRaisesRegex(
                QualificationError,
                "CUTOVER_QUALIFICATION_REQUIRED",
            ):
                validate_cutover_qualifications(repo_root=repo_root)

    def test_freeze_receipt_is_addressed_and_detects_semantic_drift(
        self,
    ) -> None:
        """Bind exact production bytes and reject a post-freeze edit."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._semantic_repository(root=repo_root)
            second_layout_id = self._write_second_layout_reference(
                repo_root=repo_root,
            )
            receipt = write_production_freeze_receipt(
                repo_root=repo_root,
                frozen_at_utc="2026-08-06T10:40:00Z",
            )
            receipt_path = repo_root / str(receipt["receipt_path"])
            persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["receipt_id"], persisted["receipt_id"])
            self.assertEqual(
                second_layout_id,
                persisted["second_layout_receipt_id"],
            )
            self.assertIn(
                receipt["receipt_id"].split(":", maxsplit=1)[1],
                receipt_path.name,
            )
            semantic_file = repo_root / SEMANTIC_FILES[0]
            semantic_file.write_text("drift", encoding="utf-8")
            with mock.patch.object(
                qualification,
                "load_table_task_contracts",
                return_value={"authorized_family_ids": []},
            ), self.assertRaisesRegex(
                QualificationError,
                "POST_FREEZE_PRODUCTION_DRIFT",
            ):
                validate_cutover_qualifications(repo_root=repo_root)

    def test_production_freeze_covers_bridge_operator_and_stage_wrappers(
        self,
    ) -> None:
        """Include every supported production entrypoint in holdout freeze."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._semantic_repository(root=repo_root)
            production_files = (
                Path("scripts/sec_pipeline.py"),
                Path("scripts/11_build_report.py"),
                Path("scripts/12_validate_repair.py"),
                Path("tools/vnext_operator.py"),
                Path("tools/vnext_cutover.py"),
                Path("tools/run_acceptance.py"),
                Path("config/company_registry.csv"),
            )
            for relative in production_files:
                path = repo_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative.as_posix(), encoding="utf-8")
            before = production_semantic_tree(repo_root=repo_root)
            for relative in production_files:
                path = repo_root / relative
                original = path.read_text(encoding="utf-8")
                path.write_text(original + "\ndrift\n", encoding="utf-8")
                after = production_semantic_tree(repo_root=repo_root)
                self.assertNotEqual(
                    before["semantic_tree_id"],
                    after["semantic_tree_id"],
                    relative.as_posix(),
                )
                path.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
