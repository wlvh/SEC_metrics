"""Verify Stage-A accepts only exact committed SEC-ledger appends."""

from __future__ import annotations

import json
import subprocess
import unittest

from sec_http import parse_request_log_rows
from tests.vnext.common import REPO_ROOT
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


if __name__ == "__main__":
    unittest.main()
