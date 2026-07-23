"""Regression tests for source/artifact validation snapshot provenance."""

from __future__ import annotations

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
    ValidationProvenanceError,
    capture_source_snapshot,
    ensure_readme_routes,
    ensure_report_provenance_notice,
    fail_validation_snapshot,
    invalidate_validation_snapshot,
    publish_validation_snapshot,
    verify_validation_snapshot,
)


class ValidationProvenanceTest(unittest.TestCase):
    """Exercise clean, stale, tampered, equivalent-tree and light snapshots."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workdir = Path(self.temp_dir.name)

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

    def _initialize_source_repo(self) -> str:
        self._git("init")
        self._git("config", "user.email", "tests@example.com")
        self._git("config", "user.name", "SEC metrics tests")
        source_files = {
            "scripts/app.py": "VALUE = 1\n",
            "tools/check.py": "print('ok')\n",
            "config/settings.json": "{}\n",
            "tests/test_dummy.py": "# fixture\n",
            "capability_contract.json": "{}\n",
            "02_指标定义_SEC_10公司单年指标.md": "# metrics\n",
            "AGENTS.md": "# agents\n",
            "SOP.md": "# sop\n",
            "TESTING.md": "# testing\n",
            "architecture.md": "# architecture\n",
            "interact.md": "# interact\n",
            "docs/business_user_guide.md": "# guide\n",
            "docs/validation_snapshot_provenance.md": "# provenance\n",
            "docs/concepts/sec_xbrl_and_evidence_model.md": "# concepts\n",
        }
        for path, content in source_files.items():
            self._write(path, content)
        self._git("add", ".")
        self._git("commit", "-m", "initial source")
        return self._git("rev-parse", "HEAD")

    def _write_success_artifacts(self, *, mode: str, source_commit: str) -> None:
        refreshed = ["repair_validation_results.csv", "stratified_audit.csv"]
        result = "PASSED" if mode == "FULL_VALIDATION" else "PASSED_WITH_CAVEATS"
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
                '{"schema_version": 1, "row_count": 1, "content_sha256": "x"}\n',
            )
        else:
            self._write("LIGHT_REVIEW_PACKAGE.marker", "light\n")

    def test_clean_full_snapshot_round_trip(self) -> None:
        head = self._initialize_source_repo()
        self._write_success_artifacts(mode="FULL_VALIDATION", source_commit=head)
        source = capture_source_snapshot(workdir=self.workdir)
        publish_validation_snapshot(workdir=self.workdir, source_snapshot=source)
        result = verify_validation_snapshot(workdir=self.workdir)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.warnings, ())

    def test_dirty_source_is_rejected_before_terminal_validation(self) -> None:
        self._initialize_source_repo()
        self._write("scripts/app.py", "VALUE = 2\n")
        with self.assertRaisesRegex(
            ValidationProvenanceError,
            "Source-input files are dirty",
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
        for path, content in {
            "scripts/app.py": "VALUE = 1\n",
            "tools/check.py": "print('ok')\n",
            "config/settings.json": "{}\n",
            "tests/test_dummy.py": "# fixture\n",
            "capability_contract.json": "{}\n",
            "02_指标定义_SEC_10公司单年指标.md": "# metrics\n",
            "AGENTS.md": "# agents\n",
            "SOP.md": "# sop\n",
            "TESTING.md": "# testing\n",
            "architecture.md": "# architecture\n",
            "interact.md": "# interact\n",
            "docs/business_user_guide.md": "# guide\n",
            "docs/validation_snapshot_provenance.md": "# provenance\n",
            "docs/concepts/sec_xbrl_and_evidence_model.md": "# concepts\n",
        }.items():
            self._write(path, content)
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
