"""Exercise the formal publication fault matrix only through its public API."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.projection_fixture_support import _write_registry
from tests.vnext.projection_fixture_support import scoped_repository
from tests.vnext.test_publication import complete_projection_fixture
from tests.vnext.test_publication import legacy_baseline_import_fixture
from tools import vnext_fault_matrix
import sec_pipeline
from vnext.batch_workflow import create_companyfacts_release_run
from vnext.batch_workflow import create_structural_release_run
from vnext.batch_workflow import request_attempt_binding
from vnext.canonical import sha256_file
from vnext.fault_matrix import FaultMatrixPreparation
from vnext.fault_matrix import FaultMatrixError
from vnext.fault_matrix import _derive_mixed_fiscal_year_run_dirs
from vnext.fault_matrix import _initialize_precommit_source
from vnext.fault_matrix import resume_formal_publication_fault_matrix
from vnext.fault_matrix import run_cutover_publication_fault_matrix
from vnext.fault_matrix import run_formal_publication_fault_matrix
from vnext.publication import PublicationView
from vnext.publication import _commit_initial_publication_chain
from vnext.publication import prepare_legacy_baseline_predecessor
from vnext.publication import prepare_publication_bundle
from vnext.publication import publication_layout, publication_state_snapshot
from vnext.publication import rollback_publication
from vnext.publication import _write_cutover_publication_validation_receipt
from vnext.projector import ProjectionError, write_projection_batch_manifest
from vnext.run_store import load_run_for_status
from vnext.run_store import validate_and_freeze_run


class FormalFaultMatrixTest(unittest.TestCase):
    """Prove persisted fault receipts come from real isolated transactions."""

    def test_formal_flow_ignores_all_retired_resolvers(self) -> None:
        """Commit a real vNext chain while every legacy resolver explodes."""
        qualification = {"qualification_id": "sha256:" + "a" * 64}

        def retired_resolver(*_args: object, **_kwargs: object) -> object:
            """Fail immediately if a retired producer re-enters production."""
            raise AssertionError("retired legacy resolver was called")

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            stack.enter_context(
                patch(
                    "vnext.publication.validate_cutover_qualifications",
                    return_value=qualification,
                )
            )
            stack.enter_context(
                patch(
                    "vnext.publication.qualification_closure_paths",
                    return_value=(),
                )
            )
            stack.enter_context(
                patch(
                    "vnext.publication.capture_source_snapshot",
                    return_value=SimpleNamespace(source_commit="b" * 40),
                )
            )
            for name in sec_pipeline.RETIRED_LEGACY_PRODUCER_NAMES:
                stack.enter_context(
                    patch.object(
                        sec_pipeline,
                        name,
                        side_effect=retired_resolver,
                    )
                )
            chain = self._formal_chain(root=root)
            view = PublicationView.open(
                publication_root=Path(chain["source_root"]),
            )
            metrics = view.read_bytes(relative_path="metrics_matrix.csv")

        self.assertEqual(
            chain["successor"]["publication_id"], view.publication_id,
        )
        for metric_id in (b"B01", b"B03", b"B10", b"B11"):
            self.assertIn(metric_id, metrics)

    @staticmethod
    def _commit_repository(*, repo_root: Path) -> None:
        """Create the clean Git authority required by formal validation.

        Args:
            repo_root: Scoped repository whose tracked bytes become authority.
        """
        commands = (
            ("init",),
            ("config", "user.name", "Fault Matrix Test"),
            ("config", "user.email", "fault-matrix@example.invalid"),
            ("add", "."),
            ("commit", "-m", "fixture authority"),
        )
        for arguments in commands:
            completed = subprocess.run(
                ["git", "-C", str(repo_root), *arguments],
                check=False,
                capture_output=True,
            )
            if completed.returncode != 0:
                raise AssertionError(completed.stderr.decode("utf-8"))

    def _formal_chain(self, *, root: Path) -> dict[str, object]:
        """Build and commit one formal predecessor/successor chain.

        Args:
            root: Empty scenario root.

        Returns:
            Fixed repository authority, source publication, and preparation
            inputs for both committed publications.
        """
        workspace = root / "authority"
        workspace.mkdir()
        inputs = complete_projection_fixture(
            workspace=workspace, tag="formal-fault-matrix",
        )
        repo_root = Path(inputs["repo_root"])
        self._commit_repository(repo_root=repo_root)
        source_root = root / "formal"
        legacy_fixture_root = root / "legacy-fixture"
        legacy_fixture_root.mkdir()
        legacy = legacy_baseline_import_fixture(
            workspace=legacy_fixture_root,
        )
        predecessor = prepare_legacy_baseline_predecessor(
            publication_root=source_root,
            repo_root=Path(legacy["repo_root"]),
            legacy_root=Path(legacy["legacy_root"]),
        )
        _write_cutover_publication_validation_receipt(
            repo_root=repo_root,
            batch_manifest_path=Path(inputs["batch_manifest_path"]),
            legacy_snapshot_dir=Path(inputs["legacy_snapshot_dir"]),
            staging_dir=Path(inputs["staging_dir"]),
            previous_publication_id=str(predecessor["publication_id"]),
            validated_at_utc="2026-08-06T10:00:00Z",
        )
        successor = prepare_publication_bundle(
            publication_root=source_root,
            repo_root=repo_root,
            batch_manifest_path=Path(inputs["batch_manifest_path"]),
            legacy_snapshot_dir=Path(inputs["legacy_snapshot_dir"]),
            staging_dir=Path(inputs["staging_dir"]),
            previous_publication_id=str(predecessor["publication_id"]),
        )
        _commit_initial_publication_chain(
            publication_root=source_root,
            legacy_predecessor_publication_id=str(
                predecessor["publication_id"]
            ),
            successor_publication_id=str(successor["publication_id"]),
            committed_at_utc="2026-08-06T10:03:00Z",
        )
        preparation = FaultMatrixPreparation(
            batch_manifest_path=Path(inputs["batch_manifest_path"]),
            legacy_snapshot_dir=Path(inputs["legacy_snapshot_dir"]),
            staging_dir=Path(inputs["staging_dir"]),
        )
        successor_preparation = FaultMatrixPreparation(
            batch_manifest_path=Path(inputs["batch_manifest_path"]),
            legacy_snapshot_dir=Path(inputs["legacy_snapshot_dir"]),
            staging_dir=Path(inputs["staging_dir"]),
        )
        return {
            "repo_root": repo_root,
            "source_root": source_root,
            "predecessor": predecessor,
            "successor": successor,
            "preparation": preparation,
            "successor_preparation": successor_preparation,
            "batch_run": Path(inputs["batch_manifest_path"]).parent / "run",
        }

    def _mixed_period_run(
        self, *, root: Path, repo_root: Path,
    ) -> Path:
        """Create a second valid FROZEN Run with a different fiscal year.

        Args:
            root: Parent for the independent negative Run.
            repo_root: Same fixed authority used by the formal chain.

        Returns:
            FROZEN Run path suitable for the public BatchManifest gate.
        """
        run_dir = root / "mixed_period_run"
        source_relative = (
            "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
            "CIK0000078003.json"
        )
        source_url = (
            "https://data.sec.gov/api/xbrl/companyfacts/"
            "CIK0000078003.json"
        )
        binding = request_attempt_binding(
            repo_root=repo_root,
            source_url=source_url,
            content_sha256=sha256_file(
                path=repo_root / source_relative,
            ),
            accession="0000078003-26-100099",
            document_name="CIK0000078003.json",
        )
        create_companyfacts_release_run(
            repo_root=repo_root,
            run_dir=run_dir,
            run_id="run:fault-matrix:mixed-2024",
            company_id="pfizer",
            target_period={
                "fiscal_year": 2024,
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
            },
            source_repo_relative_path=source_relative,
            source_url=source_url,
            accession="0000078003-26-100099",
            document_name="CIK0000078003.json",
            request_attempt_id=binding["request_attempt_id"],
        )
        validate_and_freeze_run(run_dir=run_dir, repo_root=repo_root)
        return run_dir

    def test_public_matrix_persists_every_required_fault_receipt(
        self,
    ) -> None:
        """Keep source active unchanged across all isolated negatives."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qualification = {
                "qualification_id": "sha256:" + "a" * 64,
            }
            with patch(
                "vnext.publication.validate_cutover_qualifications",
                return_value=qualification,
            ), patch(
                "vnext.publication.qualification_closure_paths",
                return_value=(),
            ), patch(
                "vnext.publication.capture_source_snapshot",
                return_value=SimpleNamespace(source_commit="b" * 40),
            ):
                chain = self._formal_chain(root=root)
                mixed_run = self._mixed_period_run(
                    root=root, repo_root=Path(chain["repo_root"]),
                )
                source_view = PublicationView.open(
                    publication_root=Path(chain["source_root"]),
                )
                result = run_formal_publication_fault_matrix(
                    receipt_publication_root=Path(chain["source_root"]),
                    source_publication_root=Path(chain["source_root"]),
                    authority_repo_root=Path(chain["repo_root"]),
                    fault_workspace_root=(
                        root / "persistent_fault_workspace"
                    ),
                    successor=chain["successor_preparation"],
                    mixed_fiscal_year_run_dirs=(
                        Path(chain["batch_run"]), mixed_run,
                    ),
                    executed_at_utc="2026-08-06T10:10:00Z",
                )
                resumed = resume_formal_publication_fault_matrix(
                    receipt_publication_root=Path(chain["source_root"]),
                    source_publication_root=Path(chain["source_root"]),
                    fault_workspace_root=(
                        root / "persistent_fault_workspace"
                    ),
                )
                receipt_reference = result["fault_receipt_references"][0]
                receipt_path = (
                    Path(chain["source_root"])
                    / receipt_reference["fault_receipt_path"]
                )
                receipt_bytes = receipt_path.read_bytes()
                receipt_path.write_bytes(receipt_bytes + b"tamper")
                with self.assertRaises(FaultMatrixError):
                    resume_formal_publication_fault_matrix(
                        receipt_publication_root=Path(chain["source_root"]),
                        source_publication_root=Path(chain["source_root"]),
                        fault_workspace_root=(
                            root / "persistent_fault_workspace"
                        ),
                    )
                receipt_path.write_bytes(receipt_bytes)

            expected = {
                "ISOLATED_ACTIVE_BUNDLE_TAMPER",
                "ISOLATED_CAS_LOSER",
                "ISOLATED_CONCURRENT_PUBLISHERS",
                "ISOLATED_DECISION_TAMPER",
                "ISOLATED_MID_BUNDLE_WRITE",
                "ISOLATED_MID_MIRROR_WRITE",
                "ISOLATED_MIRRORS_BEFORE_POINTER",
                "ISOLATED_MIXED_FISCAL_YEAR",
                "ISOLATED_PINNED_VIEW_POINTER_SWITCH",
                "ISOLATED_RECEIPT_TAMPER",
                "ISOLATED_RUN_TAMPER",
                "ISOLATED_SPEC_TAMPER",
                "ISOLATED_TRACE_TAMPER",
                "ISOLATED_WITHHELD_CANDIDATE",
            }
            receipts = result["fault_receipts"]
            self.assertEqual(
                expected, {item["scenario_id"] for item in receipts}
            )
            receipt_dir = (
                Path(chain["source_root"])
                / "outputs"
                / "publication_fault_receipts"
            )
            self.assertEqual(
                len(expected), len(list(receipt_dir.glob("*.json")))
            )
            references = result["fault_receipt_references"]
            self.assertEqual(
                expected,
                {reference["scenario_id"] for reference in references},
            )
            for reference in references:
                self.assertTrue(
                    (
                        Path(chain["source_root"])
                        / reference["fault_receipt_path"]
                    ).is_file()
                )
            self.assertTrue((root / "persistent_fault_workspace").is_dir())
            self.assertEqual("PASSED", result["status"])
            self.assertEqual(
                result["fault_matrix_id"], resumed["fault_matrix_id"]
            )
            self.assertEqual(
                result["fault_receipt_references"],
                resumed["fault_receipt_references"],
            )
            with patch(
                "vnext.publication.validate_cutover_qualifications",
                return_value=qualification,
            ):
                current_publication_id = PublicationView.open(
                    publication_root=Path(chain["source_root"]),
                ).publication_id
            self.assertEqual(
                source_view.publication_id,
                current_publication_id,
            )

    def test_cutover_wrapper_derives_fixed_authority_and_workspace(
        self,
    ) -> None:
        """Keep publication authority out of the caller-selectable surface."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            workspace = repo_root / "artifacts/vnext/cutover"
            workspace.mkdir(parents=True)
            legacy = repo_root / "outputs"
            legacy.mkdir()
            mixed_a = workspace / "mixed-a"
            mixed_b = workspace / "mixed-b"
            mixed_a.mkdir()
            mixed_b.mkdir()
            expected = {"status": "PASSED"}
            prepared_successor = "publication_" + "a" * 64
            with patch(
                "vnext.fault_matrix._REPOSITORY_ROOT", repo_root,
            ), patch(
                "vnext.fault_matrix.run_formal_publication_fault_matrix",
                return_value=expected,
            ) as run_matrix, patch(
                "vnext.fault_matrix._derive_mixed_fiscal_year_run_dirs",
                return_value=(mixed_a, mixed_b),
            ), patch(
                "vnext.fault_matrix._initialize_precommit_source",
                return_value=("publication_" + "b" * 64, prepared_successor),
            ):
                result = run_cutover_publication_fault_matrix(
                    repo_root=repo_root,
                    cutover_workspace_dir=workspace,
                    legacy_snapshot_dir=legacy,
                    prepared_successor_publication_id=prepared_successor,
                    executed_at_utc="2026-08-06T10:20:00Z",
                )
            self.assertEqual(expected, result)
            arguments = run_matrix.call_args.kwargs
            self.assertEqual(repo_root, arguments["authority_repo_root"])
            self.assertEqual(
                workspace.resolve() / "fault_matrix_source",
                arguments["source_publication_root"],
            )
            self.assertEqual(
                repo_root, arguments["receipt_publication_root"],
            )
            self.assertEqual(
                workspace.resolve() / "publication_fault_matrix",
                arguments["fault_workspace_root"],
            )
            self.assertEqual(
                workspace.resolve() / "batch_manifest.json",
                arguments["successor"].batch_manifest_path,
            )

    def test_fault_matrix_core_rejects_nonfixed_roots_before_read(
        self,
    ) -> None:
        """Reject caller roots before inspecting pointer or workspace bytes."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            exact = {
                "repo_root": repo_root,
                "cutover_workspace_dir": (
                    repo_root / "artifacts/vnext/cutover"
                ),
                "legacy_snapshot_dir": repo_root / "outputs",
            }
            mutations = {
                "repo_root": repo_root / "caller-repository",
                "cutover_workspace_dir": repo_root / "caller-workspace",
                "legacy_snapshot_dir": repo_root / "caller-legacy",
            }
            for field, value in mutations.items():
                with self.subTest(field=field), patch(
                    "vnext.fault_matrix._REPOSITORY_ROOT", repo_root,
                ), patch(
                    "vnext.fault_matrix.publication_state_snapshot",
                    side_effect=AssertionError(
                        "caller root reached authority read"
                    ),
                ) as state:
                    arguments = dict(exact)
                    arguments[field] = value
                    with self.assertRaises(FaultMatrixError) as raised:
                        run_cutover_publication_fault_matrix(
                            **arguments,
                            prepared_successor_publication_id=(
                                "publication_" + "a" * 64
                            ),
                            executed_at_utc="2026-08-07T08:10:00Z",
                        )
                    self.assertEqual(
                        "FAULT_MATRIX_AUTHORITY_ROOT_MISMATCH",
                        raised.exception.code,
                    )
                    state.assert_not_called()
                    self.assertFalse(value.exists())

    def test_public_fault_matrix_rejects_caller_root_before_core(
        self,
    ) -> None:
        """Remove caller-selected fault workspace authority from the CLI."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch(
            "tools.vnext_fault_matrix.run_cutover_publication_fault_matrix",
            side_effect=AssertionError("caller root reached matrix core"),
        ) as matrix, contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                return_code = vnext_fault_matrix.main(argv=[
                    "--json",
                    "--cutover-workspace-dir",
                    "artifacts/vnext/caller-selected",
                    "--prepared-successor-publication-id",
                    "publication_" + "a" * 64,
                ])
        self.assertEqual(2, return_code, stderr.getvalue())
        self.assertEqual(
            "FAULT_MATRIX_AUTHORITY_OVERRIDE_FORBIDDEN",
            json.loads(stdout.getvalue())["error"]["code"],
        )
        matrix.assert_not_called()
        self.assertNotIn("Traceback", stdout.getvalue() + stderr.getvalue())

    def test_cutover_wrapper_resumes_without_replaying_scenarios(
        self,
    ) -> None:
        """Revalidate retained proof and skip every fresh matrix action."""
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            workspace = repo_root / "artifacts/vnext/cutover"
            workspace.mkdir(parents=True)
            legacy = repo_root / "outputs"
            legacy.mkdir()
            fault_workspace = workspace / "publication_fault_matrix"
            fault_workspace.mkdir()
            (fault_workspace / "fault_matrix_manifest.json").write_text(
                "retained", encoding="utf-8",
            )
            prepared_successor = "publication_" + "a" * 64
            expected = {
                "status": "PASSED",
                "successor_publication_id": prepared_successor,
            }
            with patch(
                "vnext.fault_matrix._REPOSITORY_ROOT", repo_root,
            ), patch(
                "vnext.fault_matrix.resume_formal_publication_fault_matrix",
                return_value=expected,
            ) as resume, patch(
                "vnext.fault_matrix._initialize_precommit_source",
            ) as initialize, patch(
                "vnext.fault_matrix.run_formal_publication_fault_matrix",
            ) as run_matrix:
                result = run_cutover_publication_fault_matrix(
                    repo_root=repo_root,
                    cutover_workspace_dir=workspace,
                    legacy_snapshot_dir=legacy,
                    prepared_successor_publication_id=prepared_successor,
                    executed_at_utc="2026-08-06T10:25:00Z",
                )
            self.assertEqual(expected, result)
            resume.assert_called_once_with(
                receipt_publication_root=repo_root,
                source_publication_root=(
                    workspace.resolve() / "fault_matrix_source"
                ),
                fault_workspace_root=(
                    workspace.resolve() / "publication_fault_matrix"
                ),
            )
            initialize.assert_not_called()
            run_matrix.assert_not_called()

    def test_mixed_year_probe_is_a_real_structural_frozen_run(self) -> None:
        """Derive a valid negative Run without a company-specific branch."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_root = root / "fixture"
            fixture_root.mkdir()
            repo_root = scoped_repository(workspace=fixture_root)
            source_registry = REPO_ROOT / "config" / "company_registry.csv"
            with source_registry.open(
                mode="r", encoding="utf-8", newline=""
            ) as file_obj:
                reader = csv.DictReader(file_obj)
                rows = [
                    row for row in reader
                    if row["company_id"] == "jpmorgan_chase"
                ]
                fieldnames = tuple(reader.fieldnames or ())
            self.assertEqual(1, len(rows))
            _write_registry(
                path=repo_root / "config" / "company_registry.csv",
                rows=rows,
                fieldnames=fieldnames,
            )
            cutover_workspace = root / "cutover"
            original_run = cutover_workspace / "runs" / "structural"
            create_structural_release_run(
                repo_root=repo_root,
                run_dir=original_run,
                run_id="run:fault-matrix:structural-source",
                company_id="jpmorgan_chase",
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )
            validate_and_freeze_run(
                run_dir=original_run, repo_root=repo_root,
            )
            write_projection_batch_manifest(
                repo_root=repo_root,
                batch_manifest_path=(
                    cutover_workspace / "batch_manifest.json"
                ),
                run_dirs=(original_run,),
            )

            source, shifted = _derive_mixed_fiscal_year_run_dirs(
                repo_root=repo_root,
                cutover_workspace_dir=cutover_workspace,
            )
            shifted_manifest, _records, _decisions = load_run_for_status(
                run_dir=shifted, repo_root=repo_root,
            )
            self.assertEqual(original_run, source)
            self.assertEqual("FROZEN", shifted_manifest["status"])
            self.assertEqual(
                2026, shifted_manifest["target_period"]["fiscal_year"]
            )
            with self.assertRaisesRegex(
                ProjectionError, "periods differ",
            ):
                write_projection_batch_manifest(
                    repo_root=repo_root,
                    batch_manifest_path=(
                        cutover_workspace / "mixed_probe.json"
                    ),
                    run_dirs=(source, shifted),
                )

    def test_precommit_source_never_switches_official_pointer(self) -> None:
        """Build isolated P-to-B and bootstrap A-to-B committed chains."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qualification = {
                "qualification_id": "sha256:" + "a" * 64,
            }
            with patch(
                "vnext.publication.validate_cutover_qualifications",
                return_value=qualification,
            ), patch(
                "vnext.publication.qualification_closure_paths",
                return_value=(),
            ), patch(
                "vnext.publication.capture_source_snapshot",
                return_value=SimpleNamespace(source_commit="b" * 40),
            ):
                chain = self._formal_chain(root=root)
                official_root = Path(chain["source_root"])
                predecessor_id = str(
                    chain["predecessor"]["publication_id"]
                )
                successor_id = str(chain["successor"]["publication_id"])
                rollback_publication(
                    publication_root=official_root,
                    target_publication_id=predecessor_id,
                    expected_active_publication_id=successor_id,
                    committed_at_utc="2026-08-06T10:30:00Z",
                )
                official_before = publication_state_snapshot(
                    publication_root=official_root
                )
                _initialize_precommit_source(
                    official_publication_root=official_root,
                    isolated_source_root=root / "isolated-existing",
                    prepared_successor_publication_id=successor_id,
                    executed_at_utc="2026-08-06T10:31:00Z",
                )
                self.assertEqual(
                    official_before,
                    publication_state_snapshot(
                        publication_root=official_root
                    ),
                )
                self.assertEqual(
                    successor_id,
                    PublicationView.open(
                        publication_root=root / "isolated-existing"
                    ).publication_id,
                )

                layout = publication_layout(
                    publication_root=official_root
                )
                Path(layout["pointer_path"]).unlink()
                for mirror in layout["mirror_paths"].values():
                    Path(mirror).unlink()
                empty_before = publication_state_snapshot(
                    publication_root=official_root
                )
                _initialize_precommit_source(
                    official_publication_root=official_root,
                    isolated_source_root=root / "isolated-bootstrap",
                    prepared_successor_publication_id=successor_id,
                    executed_at_utc="2026-08-06T10:32:00Z",
                )
                self.assertEqual(
                    empty_before,
                    publication_state_snapshot(
                        publication_root=official_root
                    ),
                )
                self.assertEqual(
                    successor_id,
                    PublicationView.open(
                        publication_root=root / "isolated-bootstrap"
                    ).publication_id,
                )


if __name__ == "__main__":
    unittest.main()
