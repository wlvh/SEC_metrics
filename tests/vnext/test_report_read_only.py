"""Pinned report-input read-only and no-network tests."""

from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vnext.canonical import sha256_bytes
from vnext.publication import PublicationView
from vnext.report import REPORT_INPUT_FILES, load_report_inputs


class ReportReadOnlyTest(unittest.TestCase):
    """Prove report input loading has one view and no write/network effects."""

    def test_report_inputs_use_one_view_without_network_or_writes(
        self,
    ) -> None:
        """Read exact pinned bytes while leaving the source tree unchanged."""
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "publication_fixture"
            bundle.mkdir()
            files = {}
            records = []
            for relative in REPORT_INPUT_FILES:
                content = (relative + "\n").encode("utf-8")
                path = bundle / relative
                path.write_bytes(content)
                files[relative] = content
                records.append(
                    {
                        "path": relative,
                        "sha256": sha256_bytes(content=content),
                        "size": len(content),
                    }
                )
            view = PublicationView(
                publication_id="publication_fixture",
                bundle_dir=bundle,
                manifest={"files": records},
            )
            before = {
                path.relative_to(bundle).as_posix(): path.read_bytes()
                for path in bundle.rglob("*")
                if path.is_file()
            }
            with mock.patch.object(
                socket,
                "socket",
                side_effect=AssertionError("report opened a socket"),
            ):
                loaded = load_report_inputs(publication_view=view)
            after = {
                path.relative_to(bundle).as_posix(): path.read_bytes()
                for path in bundle.rglob("*")
                if path.is_file()
            }
            self.assertEqual(files, loaded)
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
