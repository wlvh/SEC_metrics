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
    SOURCE_FILES,
    ValidationProvenanceError,
    capture_source_snapshot,
)


class LightPackageSourceClosureTest(unittest.TestCase):
    """A light package must not silently shrink its explicit source closure."""

    def test_missing_explicit_source_file_is_rejected(self) -> None:
        """Deleting one declared singleton source file must fail closed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workdir = Path(tmp_dir)
            (workdir / "LIGHT_REVIEW_PACKAGE.marker").write_text(
                "light review package\n",
                encoding="utf-8",
            )
            for directory_name in ("scripts", "tools", "config", "tests"):
                directory = workdir / directory_name
                directory.mkdir(parents=True)
                (directory / "fixture.txt").write_text(
                    "fixture\n",
                    encoding="utf-8",
                )
            for relative in SOURCE_FILES:
                path = workdir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            (workdir / "AGENTS.md").unlink()

            with self.assertRaisesRegex(
                ValidationProvenanceError,
                "AGENTS.md",
            ):
                capture_source_snapshot(workdir=workdir)


if __name__ == "__main__":
    unittest.main()
