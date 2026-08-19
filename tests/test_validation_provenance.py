"""Regression tests for source/artifact validation snapshot provenance."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[1]
REQUEST_ATTEMPT_BODY = (
    "evidence/request_attempts/aa/"
    + "a" * 64
    + "/sample.json"
)
REQUEST_ATTEMPT_HEADERS = (
    REQUEST_ATTEMPT_BODY
    + "."
    + "b" * 64
    + ".headers.json"
)

if "git_workspace" not in sys.modules:
    fake_git_workspace = types.ModuleType("git_workspace")

    def fake_git_checkout_metadata_error(*, repo_root: Path) -> str:
        return "" if (repo_root / ".git").exists() else "Git metadata unavailable"

    def fake_sanitized_git_environment() -> dict[str, str]:
        environment = dict(os.environ)
        for key in list(environment):
            if key.startswith("GIT_"):
                environment.pop(key, None)
        environment["GIT_NO_REPLACE_OBJECTS"] = "1"
        return environment

    fake_git_workspace.git_checkout_metadata_error = (
        fake_git_checkout_metadata_error
    )
    fake_git_workspace.sanitized_git_environment = (
        fake_sanitized_git_environment
    )
    sys.modules["git_workspace"] = fake_git_workspace

SCRIPTS_DIR = TEST_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validation_provenance import (  # noqa: E402
    PROVENANCE_RELATIVE_PATH,
    SOURCE_POLICY_RELATIVE_PATH,
    ValidationProvenanceError,
    capture_source_snapshot,
    ensure_readme_routes,
    ensure_report_provenance_notice,
    fail_validation_snapshot,
    invalidate_validation_snapshot,
    load_source_policy,
    pin_validation_publication_transaction,
    publish_validation_snapshot,
    verify_validation_snapshot,
)
from vnext import publication as publication_module  # noqa: E402
from vnext.publication import (  # noqa: E402
    PublicationView,
    REQUIRED_BUNDLE_FILES,
    ROOT_MIRROR_RELATIVE_PATHS,
)


class ValidationProvenanceTest(unittest.TestCase):
    """Exercise clean, stale, tampered, equivalent-tree and light snapshots."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workdir = Path(self.temp_dir.name)

    def test_vnext_requirement_and_catalog_are_source_inputs(self) -> None:
        """Prevent Requirement or Spec deletion from shrinking the closure."""
        policy = load_source_policy(workdir=TEST_ROOT)
        self.assertIn("catalog", policy.runtime_source_directories)
        self.assertIn("requirements", policy.runtime_source_directories)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, relative_path: str, content: str) -> None:
        path = self.workdir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.workdir), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _write_source_inputs(self) -> None:
        """Create policy-defined source fixtures."""
        policy = load_source_policy(workdir=TEST_ROOT)
        fixtures = {
            "catalog/spec.md": "---\n{}\n---\n",
            "scripts/app.py": "VALUE = 1\n",
            "tools/check.py": "print('ok')\n",
            "config/settings.json": "{}\n",
            "tests/test_dummy.py": "# fixture\n",
            "requirements/snapshot.md": "# requirement fixture\n",
            "fixtures/source_fixture.json": "{}\n",
        }
        for path, content in fixtures.items():
            self._write(path, content)
        self._write(
            SOURCE_POLICY_RELATIVE_PATH.as_posix(),
            (TEST_ROOT / SOURCE_POLICY_RELATIVE_PATH).read_text(
                encoding="utf-8"
            ),
        )
        for relative in policy.acceptance_source_files:
            content = "# fixture\n"
            if relative == "capability_contract.json":
                content = "{}\n"
            elif relative == "SOP.md":
                content = (
                    "# SOP\n\n"
                    "| 步骤 | 动作 | 权威引用 | 验收 |\n"
                    "|---|---|---|---|\n"
                    "| 1 | run | "
                    "`01_SOP_SEC_10公司单年指标计算_直接SEC.md` | pass |\n"
                )
            self._write(relative, content)

    def _initialize_source_repo(self) -> str:
        """Initialize and commit one complete policy-defined source tree."""
        self._git("init")
        self._git("config", "user.email", "tests@example.com")
        self._git("config", "user.name", "SEC metrics tests")
        self._write_source_inputs()
        self._git("add", ".")
        self._git("commit", "-m", "initial source")
        return self._git("rev-parse", "HEAD")

    def _write_success_artifacts(
        self, *, mode: str, source_commit: str
    ) -> None:
        refreshed = ["repair_validation_results.csv", "stratified_audit.csv"]
        result = (
            "PASSED"
            if mode == "FULL_VALIDATION"
            else "PASSED_WITH_CAVEATS"
        )
        manifest = {
            "run_id": "run-1",
            "source_commit": source_commit,
            "started_at_utc": "2026-07-23T00:00:00+00:00",
            "mode": mode,
            "refreshed_artifacts": refreshed,
            "not_refreshed_artifacts": [],
            "result": result,
        }
        self._write(
            "outputs/validation_run_manifest.json",
            json.dumps(manifest, indent=2) + "\n",
        )
        self._write(
            "REPORT_十公司财务指标.md",
            "# REPORT\n\n- Verdict: **GO**。\n- result: `{}`\n".format(result),
        )
        self._write("README_RUN.md", "# README_RUN\n\n## 配置\n")
        for path in [
            "outputs/golden_results.csv",
            "outputs/metrics_matrix.csv",
            "outputs/metric_evidence.csv",
            "outputs/coverage_matrix.csv",
            "outputs/events.csv",
            "outputs/repair_validation_results.csv",
            "outputs/stratified_audit.csv",
        ]:
            self._write(path, "header\nrow\n")
        if mode == "FULL_VALIDATION":
            self._write("evidence/requests_log.csv", "header\nrow\n")
            self._write(
                "evidence/requests_log_manifest.json",
                '{"schema_version": 1, "row_count": 1, '
                '"content_sha256": "x"}\n',
            )
            self._write(REQUEST_ATTEMPT_BODY, "body\n")
            self._write(REQUEST_ATTEMPT_HEADERS, "headers\n")
            self._write(
                "outputs/failure_first_receipts/fixture.json",
                '{"evidence":"failure-first"}\n',
            )
            self._write(
                "artifacts/vnext/qualification/fixture.json",
                '{"evidence":"qualification"}\n',
            )
            self._write(
                "outputs/publication_fault_receipts/fixture.json",
                '{"evidence":"fault-matrix"}\n',
            )
            self._write(
                "outputs/vnext_cutover_audits/fixture.json",
                '{"evidence":"live-cutover-audit"}\n',
            )
        else:
            self._write("LIGHT_REVIEW_PACKAGE.marker", "light\n")

    def _write_active_publication(self) -> tuple[str, dict[str, object]]:
        """Persist one minimal hash-bound active bundle and exact mirrors.

        Returns:
            Active publication ID and the synthetic manifest used to isolate
            provenance closure behavior from publication semantic validation.
        """
        publication_id = "publication_" + "a" * 64
        bundle_dir = (
            self.workdir / "outputs" / "publications" / publication_id
        )
        bundle_dir.mkdir(parents=True)
        file_records = []
        for relative in sorted(REQUIRED_BUNDLE_FILES):
            mirror_relative = ROOT_MIRROR_RELATIVE_PATHS[relative]
            mirror = self.workdir / mirror_relative
            if mirror.exists():
                content = mirror.read_bytes()
            else:
                content = "active:{}\n".format(relative).encode("utf-8")
                self._write(mirror_relative, content.decode("utf-8"))
            destination = bundle_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            file_records.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                }
            )
        internal_relative = "internal/closure_manifest.json"
        internal_content = b'{"synthetic":"transitive-closure"}\n'
        internal_path = bundle_dir / internal_relative
        internal_path.parent.mkdir()
        internal_path.write_bytes(internal_content)
        file_records.append(
            {
                "path": internal_relative,
                "sha256": hashlib.sha256(internal_content).hexdigest(),
                "size": len(internal_content),
            }
        )
        manifest = {
            "publication_id": publication_id,
            "files": file_records,
            "previous_publication_id": None,
        }
        manifest_bytes = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        (bundle_dir / "publication_manifest.json").write_bytes(
            manifest_bytes
        )
        # Exercise the real lock, mirrors, pointer, and committed-edge order.
        # Deep bundle semantics remain mocked because this fixture isolates
        # provenance behavior rather than PublicationManifest validation.
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ), mock.patch(
            "vnext.publication._publication_commit_authority",
            return_value="FORMAL",
        ), mock.patch(
            "vnext.publication._require_existing_active_for_forward_commit",
        ):
            publication_module._commit_publication(
                publication_root=self.workdir,
                publication_id=publication_id,
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00+00:00",
            )
        return publication_id, manifest

    def _publish_active_snapshot(
        self, *, manifest: dict[str, object]
    ) -> None:
        """Publish provenance while isolating deep bundle semantics."""
        source = capture_source_snapshot(workdir=self.workdir)
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ):
            publish_validation_snapshot(
                workdir=self.workdir,
                source_snapshot=source,
            )

    def test_clean_full_snapshot_round_trip(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION",
            source_commit=head,
        )
        source = capture_source_snapshot(workdir=self.workdir)
        publish_validation_snapshot(
            workdir=self.workdir,
            source_snapshot=source,
        )
        result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.warnings, ())

    def test_active_pointer_bundle_and_mirrors_are_exactly_bound(self) -> None:
        """Bind only the pointer-selected complete bundle and its mirrors."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION", source_commit=head,
        )
        publication_id, manifest = self._write_active_publication()
        self._publish_active_snapshot(manifest=manifest)

        provenance = json.loads(
            (self.workdir / PROVENANCE_RELATIVE_PATH).read_text(
                encoding="utf-8"
            )
        )
        keys = set(provenance["artifact_digests"])
        bundle_prefix = "outputs/publications/{}/".format(publication_id)
        expected_bundle = {
            bundle_prefix + relative
            for relative in REQUIRED_BUNDLE_FILES
        } | {bundle_prefix + "publication_manifest.json"}
        self.assertIn("outputs/active_publication.json", keys)
        self.assertTrue(expected_bundle.issubset(keys))
        self.assertIn(
            bundle_prefix + "internal/closure_manifest.json", keys
        )
        self.assertTrue(
            set(ROOT_MIRROR_RELATIVE_PATHS.values()).issubset(keys)
        )

        sibling = self.workdir / "outputs" / "publications" / (
            "publication_" + "b" * 64
        )
        sibling.mkdir()
        (sibling / "unrelated.bin").write_bytes(b"not active\n")
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ):
            result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(result.ok, result.errors)

    def test_publish_cycle_never_reopens_pointer_after_internal_switch(
        self,
    ) -> None:
        """Keep provenance reads on one view when active changes mid-cycle."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION", source_commit=head,
        )
        _publication_id, manifest = self._write_active_publication()
        source = capture_source_snapshot(workdir=self.workdir)
        pointer = self.workdir / "outputs" / "active_publication.json"
        original_open = PublicationView.open
        original_read = PublicationView.read_bytes
        read_count = 0

        def read_then_switch(
            pinned: PublicationView, *, relative_path: str
        ) -> bytes:
            """Move authority only after the pinned bundle starts reading."""
            nonlocal read_count
            content = original_read(
                pinned,
                relative_path=relative_path,
            )
            read_count += 1
            if read_count == 1:
                switched = json.loads(pointer.read_text(encoding="utf-8"))
                switched["publication_id"] = "publication_" + "b" * 64
                pointer.write_text(
                    json.dumps(
                        switched,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n",
                    encoding="utf-8",
                )
            return content

        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ), mock.patch.object(
            PublicationView,
            "open",
            side_effect=lambda *, publication_root: original_open(
                publication_root=publication_root,
            ),
        ) as opened, mock.patch.object(
            PublicationView,
            "read_bytes",
            autospec=True,
            side_effect=read_then_switch,
        ), self.assertRaisesRegex(
            ValidationProvenanceError,
            "ACTIVE_POINTER_CHANGED_DURING_VALIDATION_TRANSACTION",
        ):
            publish_validation_snapshot(
                workdir=self.workdir,
                source_snapshot=source,
            )
        self.assertEqual(1, opened.call_count)
        self.assertGreater(read_count, 0)

    def test_publish_self_check_opens_active_pointer_once(self) -> None:
        """Reuse one active transaction through sidecar self-verification."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION", source_commit=head,
        )
        _publication_id, manifest = self._write_active_publication()
        source = capture_source_snapshot(workdir=self.workdir)
        original_open = PublicationView.open
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ), mock.patch.object(
            PublicationView,
            "open",
            side_effect=lambda *, publication_root: original_open(
                publication_root=publication_root,
            ),
        ) as opened:
            publish_validation_snapshot(
                workdir=self.workdir,
                source_snapshot=source,
            )
        self.assertEqual(1, opened.call_count)

    def test_independent_checker_uses_supplied_pinned_transaction(
        self,
    ) -> None:
        """Reject a pointer race without reopening authority in checker."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION", source_commit=head,
        )
        _publication_id, manifest = self._write_active_publication()
        self._publish_active_snapshot(manifest=manifest)
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ):
            transaction = pin_validation_publication_transaction(
                workdir=self.workdir,
            )
        pointer = self.workdir / "outputs" / "active_publication.json"
        original_read = PublicationView.read_bytes
        read_count = 0

        def read_then_switch(
            pinned: PublicationView, *, relative_path: str
        ) -> bytes:
            """Switch pointer after checker starts reading its fixed view."""
            nonlocal read_count
            content = original_read(
                pinned,
                relative_path=relative_path,
            )
            read_count += 1
            if read_count == 1:
                switched = json.loads(pointer.read_text(encoding="utf-8"))
                switched["publication_id"] = "publication_" + "b" * 64
                pointer.write_text(
                    json.dumps(
                        switched,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n",
                    encoding="utf-8",
                )
            return content

        with mock.patch.object(
            PublicationView,
            "open",
            side_effect=AssertionError("checker reopened active pointer"),
        ), mock.patch.object(
            PublicationView,
            "read_bytes",
            autospec=True,
            side_effect=read_then_switch,
        ):
            result = verify_validation_snapshot(
                workdir=self.workdir,
                publication_transaction=transaction,
            )
        self.assertFalse(result.ok)
        self.assertIn(
            "ACTIVE_POINTER_CHANGED_DURING_VALIDATION_TRANSACTION",
            result.errors,
        )
        self.assertGreater(read_count, 0)

    def test_checker_cli_forwards_one_pinned_transaction(self) -> None:
        """Keep the public checker wrapper inside its one opened cycle."""
        checker_path = TEST_ROOT / "tools" / "check_validation_snapshot.py"
        spec = importlib.util.spec_from_file_location(
            "validation_snapshot_checker_fixture",
            checker_path,
        )
        if spec is None or spec.loader is None:
            self.fail("Validation snapshot checker cannot be loaded")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        transaction = object()
        verified = types.SimpleNamespace(errors=(), warnings=())
        with mock.patch.object(
            checker,
            "WORKDIR",
            self.workdir,
        ), mock.patch.object(
            checker,
            "pin_validation_publication_transaction",
            return_value=transaction,
        ) as pinned, mock.patch.object(
            checker,
            "verify_validation_snapshot",
            return_value=verified,
        ) as verify:
            return_code = checker.main()
        self.assertEqual(0, return_code)
        pinned.assert_called_once_with(workdir=self.workdir)
        verify.assert_called_once_with(
            workdir=self.workdir,
            allow_equivalent_source_tree=True,
            publication_transaction=transaction,
        )

    def test_active_bundle_tamper_missing_and_extra_fail_closed(self) -> None:
        """Reject every namespace or byte drift inside the active bundle."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION", source_commit=head,
        )
        publication_id, manifest = self._write_active_publication()
        self._publish_active_snapshot(manifest=manifest)
        bundle_dir = (
            self.workdir / "outputs" / "publications" / publication_id
        )
        target = bundle_dir / "semantic_audit_receipt.json"
        original = target.read_bytes()

        target.write_bytes(b"tampered\n")
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ):
            tampered = verify_validation_snapshot(workdir=self.workdir)
        self.assertFalse(tampered.ok)

        target.write_bytes(original)
        target.unlink()
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ):
            missing = verify_validation_snapshot(workdir=self.workdir)
        self.assertFalse(missing.ok)

        target.write_bytes(original)
        (bundle_dir / "unexpected.bin").write_bytes(b"unexpected\n")
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ):
            extra = verify_validation_snapshot(workdir=self.workdir)
        self.assertFalse(extra.ok)

    def test_active_root_mirror_drift_fails_closed(self) -> None:
        """Reject a root compatibility mirror that differs from active."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION", source_commit=head,
        )
        _, manifest = self._write_active_publication()
        self._publish_active_snapshot(manifest=manifest)
        self._write("outputs/semantic_audit_receipt.json", "drift\n")
        with mock.patch(
            "vnext.publication.verify_publication_bundle",
            return_value=manifest,
        ):
            result = verify_validation_snapshot(workdir=self.workdir)
        self.assertFalse(result.ok)

    def test_dirty_source_is_rejected_before_terminal_validation(self) -> None:
        self._initialize_source_repo()
        self._write("scripts/app.py", "VALUE = 2\n")
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "Source-input files are dirty",
        ):
            capture_source_snapshot(workdir=self.workdir)

    def test_authoritative_method_change_is_rejected(self) -> None:
        """Changing the SOP authority input must not remain falsely clean."""
        self._initialize_source_repo()
        self._write(
            "01_SOP_SEC_10公司单年指标计算_直接SEC.md",
            "# changed method\n",
        )
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "01_SOP_SEC_10公司单年指标计算_直接SEC.md",
        ):
            capture_source_snapshot(workdir=self.workdir)

    def test_sop_authority_reference_must_be_classified(self) -> None:
        """Removing an SOP authority input from policy must fail closed."""
        self._initialize_source_repo()
        self._write(
            "SOP.md",
            (
                "# SOP\n\n"
                "| 步骤 | 动作 | 权威引用 | 验收 |\n"
                "|---|---|---|---|\n"
                "| 1 | run | "
                "01_SOP_SEC_10公司单年指标计算_直接SEC.md | pass |\n"
            ),
        )
        policy_path = self.workdir / SOURCE_POLICY_RELATIVE_PATH
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        payload["acceptance_source_files"].remove(
            "01_SOP_SEC_10公司单年指标计算_直接SEC.md"
        )
        policy_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "not classified by source policy",
        ):
            capture_source_snapshot(workdir=self.workdir)
        result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any(
                "not classified by source policy" in error
                for error in result.errors
            ),
            result.errors,
        )
        self.assertIn(
            "validation snapshot provenance is missing",
            result.errors,
        )

    def test_document_roles_are_explicit(self) -> None:
        """Keep AGENTS file-map roles aligned with the machine policy."""
        policy = load_source_policy(workdir=TEST_ROOT)
        self.assertIn(
            "01_SOP_SEC_10公司单年指标计算_直接SEC.md",
            policy.acceptance_source_files,
        )
        self.assertIn(
            "CIK变更应对方案.md",
            policy.acceptance_source_files,
        )
        self.assertIn(
            "SEC_metrics_Project_Overview_and_Expert_Guide.md",
            policy.explanatory_non_authoritative,
        )
        self.assertIn(
            "PR_Checklist.md",
            policy.publication_governance_files,
        )
        self.assertIn(
            "evidence/request_attempts", policy.full_artifact_directories
        )
        self.assertIn(
            "outputs/failure_first_receipts",
            policy.full_artifact_directories,
        )
        self.assertIn(
            "artifacts/vnext/qualification",
            policy.full_artifact_directories,
        )
        self.assertIn(
            "artifacts/vnext/zero_ai_release",
            policy.full_artifact_directories,
        )
        self.assertIn(
            "outputs/publication_fault_receipts",
            policy.full_artifact_directories,
        )
        self.assertIn(
            "outputs/vnext_cutover_audits",
            policy.full_artifact_directories,
        )
        self.assertIn(
            "outputs/zero_ai_release_receipts",
            policy.full_artifact_directories,
        )

    def test_explanatory_document_cannot_be_sop_authority(self) -> None:
        """An explanatory role must not silently become a run authority."""
        self._initialize_source_repo()
        self._write(
            "SOP.md",
            (
                "# SOP\n\n"
                "| 步骤 | 动作 | 权威引用 | 验收 |\n"
                "|---|---|---|---|\n"
                "| 1 | run | "
                "`SEC_metrics_Project_Overview_and_Expert_Guide.md` | pass |\n"
            ),
        )
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "explanatory non-authoritative",
        ):
            capture_source_snapshot(workdir=self.workdir)


    def test_staged_untracked_and_ignored_source_files_are_rejected(self) -> None:
        self._initialize_source_repo()

        self._write("tools/check.py", "print('changed')\n")
        self._git("add", "tools/check.py")
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "Source-input files are dirty",
        ):
            capture_source_snapshot(workdir=self.workdir)

        self._git("reset", "--hard", "HEAD")
        self._write("scripts/untracked_rule.py", "VALUE = 1\n")
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "untracked_rule.py",
        ):
            capture_source_snapshot(workdir=self.workdir)

        (self.workdir / "scripts/untracked_rule.py").unlink()
        self._write(".gitignore", "scripts/ignored_rule.py\n")
        self._git("add", ".gitignore")
        self._git("commit", "-m", "ignore probe")
        self._write("scripts/ignored_rule.py", "VALUE = 2\n")
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "ignored_rule.py",
        ):
            capture_source_snapshot(workdir=self.workdir)


    def test_manifest_dirty_suffix_binds_same_clean_source_tree(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION",
            source_commit=head + "+dirty",
        )
        source = capture_source_snapshot(workdir=self.workdir)
        payload = publish_validation_snapshot(
            workdir=self.workdir,
            source_snapshot=source,
        )
        self.assertEqual(payload["source_commit"], head)
        self.assertEqual(payload["manifest_source_commit"], head + "+dirty")
        result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(result.ok, result.errors)

    def test_manifest_source_commit_must_identify_captured_source(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION",
            source_commit="0" * 40 + "+dirty",
        )
        source = capture_source_snapshot(workdir=self.workdir)
        self.assertEqual(source.source_commit, head)
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "does not identify the captured source commit",
        ):
            publish_validation_snapshot(
                workdir=self.workdir,
                source_snapshot=source,
            )

    def test_unbound_legacy_marker_cannot_authorize_old_source_commit(
        self,
    ) -> None:
        """Reject a marker claim without its active exact-digest closure."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION",
            source_commit="0" * 40,
        )
        source = capture_source_snapshot(workdir=self.workdir)
        self.assertEqual(head, source.source_commit)
        fake_proof = {
            "record_type": "LEGACY_BASELINE_IMPORT",
            "publication_id": "publication_" + "a" * 64,
            "validation_manifest_sha256": "b" * 64,
            "validation_manifest_size": 1,
        }
        with mock.patch(
            "validation_provenance._active_legacy_import_proof",
            return_value=fake_proof,
        ), self.assertRaisesRegex(
            ValidationProvenanceError,
            "does not identify the captured source commit",
        ):
            publish_validation_snapshot(
                workdir=self.workdir,
                source_snapshot=source,
            )

    def test_artifact_digest_key_set_is_exact(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(mode="FULL_VALIDATION", source_commit=head)
        source = capture_source_snapshot(workdir=self.workdir)
        publish_validation_snapshot(workdir=self.workdir, source_snapshot=source)

        path = self.workdir / PROVENANCE_RELATIVE_PATH
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["artifact_digests"].pop("outputs/metrics_matrix.csv")
        payload["artifact_digests"]["outputs/unexpected.csv"] = {
            "sha256": "0" * 64,
            "size_bytes": 0,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any("artifact digest key set mismatch" in item for item in result.errors)
        )
        self.assertTrue(
            any("outputs/metrics_matrix.csv" in item for item in result.errors)
        )
        self.assertTrue(
            any("outputs/unexpected.csv" in item for item in result.errors)
        )

    def test_full_request_attempt_directory_is_exactly_bound(self) -> None:
        """Tamper, set drift, and aliases break the full artifact closure."""
        head = self._initialize_source_repo()
        self._write_success_artifacts(
            mode="FULL_VALIDATION",
            source_commit=head,
        )
        source = capture_source_snapshot(workdir=self.workdir)
        publish_validation_snapshot(
            workdir=self.workdir,
            source_snapshot=source,
        )
        body_path = self.workdir / REQUEST_ATTEMPT_BODY

        self._write(REQUEST_ATTEMPT_BODY, "tampered\n")
        tampered = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any(
                REQUEST_ATTEMPT_BODY in error
                and "artifact SHA-256 mismatch" in error
                for error in tampered.errors
            ),
            tampered.errors,
        )

        self._write(REQUEST_ATTEMPT_BODY, "body\n")
        body_path.unlink()
        deleted = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any(
                REQUEST_ATTEMPT_BODY in error
                and "artifact digest key set mismatch" in error
                for error in deleted.errors
            ),
            deleted.errors,
        )

        self._write(REQUEST_ATTEMPT_BODY, "body\n")
        added_path = "evidence/request_attempts/ff/unexpected.bin"
        self._write(added_path, "unexpected\n")
        added = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any(
                added_path in error
                and "artifact digest key set mismatch" in error
                for error in added.errors
            ),
            added.errors,
        )

        (self.workdir / added_path).unlink()
        body_path.unlink()
        body_path.symlink_to(self.workdir / REQUEST_ATTEMPT_HEADERS)
        symlinked = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any("Full artifact path is a symlink" in error
                for error in symlinked.errors),
            symlinked.errors,
        )

        body_path.unlink()
        os.link(
            src=self.workdir / REQUEST_ATTEMPT_HEADERS,
            dst=body_path,
        )
        hardlinked = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any("Full artifact path is not single-link" in error
                for error in hardlinked.errors),
            hardlinked.errors,
        )

    def test_stage_invalidation_removes_only_regular_provenance(self) -> None:
        self._write(PROVENANCE_RELATIVE_PATH.as_posix(), '{"stale": true}\n')
        invalidate_validation_snapshot(workdir=self.workdir)
        self.assertFalse((self.workdir / PROVENANCE_RELATIVE_PATH).exists())

        target = self.workdir / "outside.json"
        target.write_text("victim\n", encoding="utf-8")
        provenance = self.workdir / PROVENANCE_RELATIVE_PATH
        provenance.parent.mkdir(parents=True, exist_ok=True)
        provenance.symlink_to(target)
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "symlink component",
        ):
            invalidate_validation_snapshot(workdir=self.workdir)
        self.assertEqual(target.read_text(encoding="utf-8"), "victim\n")

    def test_source_and_artifact_tampering_are_detected(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(mode="FULL_VALIDATION", source_commit=head)
        source = capture_source_snapshot(workdir=self.workdir)
        publish_validation_snapshot(workdir=self.workdir, source_snapshot=source)

        self._write("outputs/metrics_matrix.csv", "header\ntampered\n")
        artifact_result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any(
                "artifact SHA-256 mismatch" in error
                for error in artifact_result.errors
            )
        )

        self._write("outputs/metrics_matrix.csv", "header\nrow\n")
        self._write("scripts/app.py", "VALUE = 2\n")
        source_result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(
            any(
                "Source-input files are dirty" in error
                for error in source_result.errors
            )
        )

    def test_equivalent_source_tree_allows_merge_commit_sha_change(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(mode="FULL_VALIDATION", source_commit=head)
        source = capture_source_snapshot(workdir=self.workdir)
        publish_validation_snapshot(workdir=self.workdir, source_snapshot=source)

        self._write("docs/history/merge-note.md", "non-source history note\n")
        self._git("add", "docs/history/merge-note.md")
        self._git("commit", "-m", "merge-equivalent metadata")

        result = verify_validation_snapshot(
            workdir=self.workdir,
            allow_equivalent_source_tree=True,
        )
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(
            any(
                "source-input tree is equivalent" in warning
                for warning in result.warnings
            )
        )
        strict_result = verify_validation_snapshot(
            workdir=self.workdir,
            allow_equivalent_source_tree=False,
        )
        self.assertIn("source commit mismatch", strict_result.errors)

    def test_light_package_publishes_limited_non_git_provenance(self) -> None:
        self._write_source_inputs()
        self._write_success_artifacts(
            mode="LIGHT_REVIEW_MODE",
            source_commit="UNAVAILABLE_NON_GIT_WORKSPACE",
        )
        source = capture_source_snapshot(workdir=self.workdir)
        self.assertEqual(source.checkout_status, "LIGHT_PACKAGE_NO_GIT")
        publish_validation_snapshot(workdir=self.workdir, source_snapshot=source)
        result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(result.ok, result.errors)

    def test_postflight_failure_rewrites_manifest_and_report_no_go(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(mode="FULL_VALIDATION", source_commit=head)
        self._write(
            PROVENANCE_RELATIVE_PATH.as_posix(),
            '{"stale": true}\n',
        )
        fail_validation_snapshot(
            workdir=self.workdir,
            reason="artifact digest publication failed",
        )
        manifest = json.loads(
            (self.workdir / "outputs/validation_run_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        report = (self.workdir / "REPORT_十公司财务指标.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(manifest["result"], "FAILED")
        self.assertIn("- Verdict: **NO-GO**。", report)
        self.assertIn("snapshot_provenance: `FAILED`", report)
        self.assertFalse((self.workdir / PROVENANCE_RELATIVE_PATH).exists())


    def test_fail_closed_downgrades_manifest_even_if_sidecar_is_unsafe(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(mode="FULL_VALIDATION", source_commit=head)
        target = self.workdir / "outside.json"
        target.write_text("victim\n", encoding="utf-8")
        provenance = self.workdir / PROVENANCE_RELATIVE_PATH
        provenance.parent.mkdir(parents=True, exist_ok=True)
        provenance.symlink_to(target)

        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "sidecar_cleanup",
        ):
            fail_validation_snapshot(
                workdir=self.workdir,
                reason="publication failure",
            )
        manifest = json.loads(
            (self.workdir / "outputs/validation_run_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        report = (self.workdir / "REPORT_十公司财务指标.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(manifest["result"], "FAILED")
        self.assertIn("- Verdict: **NO-GO**。", report)
        self.assertEqual(target.read_text(encoding="utf-8"), "victim\n")


    def test_stage12_wrapper_downgrades_on_unexpected_postflight_error(self) -> None:
        wrapper_path = TEST_ROOT / "scripts" / "12_validate_repair.py"
        fake_pipeline = types.ModuleType("sec_pipeline")
        fake_pipeline.run_stage = lambda *, stage_name: None
        spec = importlib.util.spec_from_file_location(
            "stage12_wrapper_test",
            wrapper_path,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"sec_pipeline": fake_pipeline}):
            spec.loader.exec_module(module)

        calls = []
        module.WORKDIR = self.workdir
        module.invalidate_validation_snapshot = (
            lambda *, workdir: calls.append(("invalidate", workdir))
        )
        module.capture_source_snapshot = (
            lambda *, workdir: "source-snapshot"
        )
        fake_pipeline.run_stage = (
            lambda *, stage_name: calls.append(("run", stage_name))
        )

        def raise_unexpected(*, workdir, source_snapshot):
            self.assertEqual(source_snapshot, "source-snapshot")
            raise OSError("disk full")

        module.ensure_report_provenance_notice = (
            lambda *, workdir: calls.append(("report_notice", workdir))
        )
        module.publish_validation_snapshot = raise_unexpected
        module.fail_validation_snapshot = (
            lambda *, workdir, reason: calls.append(("fail", reason))
        )
        with mock.patch.dict(sys.modules, {"sec_pipeline": fake_pipeline}):
            with self.assertRaises(SystemExit) as raised:
                module.main()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn(("run", "12_validate_repair"), calls)
        self.assertIn(("fail", "disk full"), calls)


    def test_report_provenance_notice_is_idempotent(self) -> None:
        self._write(
            "REPORT_十公司财务指标.md",
            "# REPORT_十公司财务指标\n\n## Executive Summary\n",
        )
        ensure_report_provenance_notice(workdir=self.workdir)
        first = (self.workdir / "REPORT_十公司财务指标.md").read_text(
            encoding="utf-8"
        )
        ensure_report_provenance_notice(workdir=self.workdir)
        second = (self.workdir / "REPORT_十公司财务指标.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(first, second)
        self.assertEqual(first.count("## Validation snapshot provenance"), 1)
        self.assertIn("tools/check_validation_snapshot.py", first)

    def test_readme_routes_are_idempotent(self) -> None:
        self._write("README_RUN.md", "# README_RUN\n\n## 配置\n\n- item\n")
        ensure_readme_routes(workdir=self.workdir)
        first = (self.workdir / "README_RUN.md").read_text(encoding="utf-8")
        ensure_readme_routes(workdir=self.workdir)
        second = (self.workdir / "README_RUN.md").read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertEqual(first.count("## 只读取现有结果"), 1)
        self.assertIn("tools/check_validation_snapshot.py", first)


if __name__ == "__main__":
    unittest.main()
