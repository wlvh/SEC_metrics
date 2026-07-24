"""Regression for the complete no-Git light-package source closure."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validation_provenance import (  # noqa: E402
    SOURCE_POLICY_RELATIVE_PATH,
    ValidationProvenanceError,
    capture_source_snapshot,
    load_source_policy,
)


class LightPackageSourceClosureTest(unittest.TestCase):
    """A light package must not silently shrink its explicit source closure."""

    def test_missing_explicit_source_file_is_rejected(self) -> None:
        """Deleting one declared singleton source file must fail closed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workdir = Path(tmp_dir)
            policy = load_source_policy(workdir=REPO_ROOT)
            (workdir / "LIGHT_REVIEW_PACKAGE.marker").write_text(
                "light review package\n",
                encoding="utf-8",
            )
            for directory_name in policy.runtime_source_directories:
                directory = workdir / directory_name
                directory.mkdir(parents=True)
                (directory / "fixture.txt").write_text(
                    "fixture\n",
                    encoding="utf-8",
                )
            explicit = policy.acceptance_source_files + (
                SOURCE_POLICY_RELATIVE_PATH.as_posix(),
            )
            for relative in explicit:
                path = workdir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((REPO_ROOT / relative).read_bytes())
            (workdir / "AGENTS.md").unlink()

            with self.assertRaisesRegex(
                ValidationProvenanceError,
                "AGENTS.md",
            ):
                capture_source_snapshot(workdir=workdir)


if __name__ == "__main__":
    unittest.main()
