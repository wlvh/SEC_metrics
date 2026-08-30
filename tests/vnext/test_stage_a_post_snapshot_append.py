"""Verify Stage-A accepts only exact committed SEC-ledger appends."""

from __future__ import annotations

import json
import subprocess
import unittest
from unittest import mock

import vnext.stage_a_snapshot as stage_a_module
from sec_http import parse_request_log_rows
from tests.vnext.common import REPO_ROOT
from vnext.stage_a_snapshot import (
    _current_jpm_materialization_matches_historical_receipt,
)
from vnext.stage_a_snapshot import _qualification_evidence_append_is_valid
from vnext.stage_a_snapshot import _request_ledger_append_is_valid


class StageAPostSnapshotAppendTest(unittest.TestCase):
    """Bind post-snapshot attempt files to the exact appended ledger rows."""

    def test_current_request_attempt_append_is_complete_and_committed(self) -> None:
        """Accept all four audited rows and reject an incomplete file set."""
        manifest = json.loads((
            REPO_ROOT / "outputs/validation_run_manifest.json"
        ).read_text(encoding="utf-8"))
        historical = subprocess.run(
            [
                "git", "show",
                manifest["source_commit"] + ":evidence/requests_log.csv",
            ],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
        ).stdout
        historical_rows = parse_request_log_rows(
            text=historical.decode("utf-8"),
        )
        current_rows = parse_request_log_rows(text=(
            REPO_ROOT / "evidence/requests_log.csv"
        ).read_text(encoding="utf-8"))
        appended_paths = sorted({
            row[field]
            for row in current_rows[len(historical_rows):]
            for field in (
                "repo_relative_path", "headers_repo_relative_path",
            )
        })
        self.assertEqual(8, len(appended_paths))
        self.assertTrue(_request_ledger_append_is_valid(
            repo_root=REPO_ROOT,
            missing_artifact_paths=appended_paths,
        ))
        self.assertFalse(_request_ledger_append_is_valid(
            repo_root=REPO_ROOT,
            missing_artifact_paths=appended_paths[:-1],
        ))

    def test_financial_qualification_append_is_one_terminal_dag(self) -> None:
        """Accept the complete first shard cycle and reject a partial commit."""
        cycle = (
            "artifacts/vnext/qualification/cycles/"
            "4b299e648b801e0160c98b9358db143e8a72405b00eb02503a706c01e7ff017c"
        )
        paths = subprocess.run(
            ["git", "ls-files", "--", cycle],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
            encoding="utf-8",
        ).stdout.splitlines()
        self.assertEqual(22, len(paths))
        self.assertTrue(_qualification_evidence_append_is_valid(
            repo_root=REPO_ROOT,
            missing_artifact_paths=paths,
        ))
        self.assertFalse(_qualification_evidence_append_is_valid(
            repo_root=REPO_ROOT,
            missing_artifact_paths=paths[:-1],
        ))

    def test_canonical_speedup_preserves_guarded_jpm_materialization(
        self,
    ) -> None:
        """Keep every historical materialization byte under source drift."""
        self.assertTrue(
            _current_jpm_materialization_matches_historical_receipt(
                repo_root=REPO_ROOT,
            )
        )
        serialize = stage_a_module.canonical_json_bytes
        with mock.patch.object(
            stage_a_module,
            "canonical_json_bytes",
            side_effect=lambda **kwargs: serialize(**kwargs) + b"drift",
        ):
            self.assertFalse(
                _current_jpm_materialization_matches_historical_receipt(
                    repo_root=REPO_ROOT,
                )
            )


if __name__ == "__main__":
    unittest.main()
