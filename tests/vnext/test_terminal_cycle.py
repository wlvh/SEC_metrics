"""Single-transaction formal terminal consumer tests."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.test_report_read_only import publication_fixture
from validation_provenance import SourceSnapshot
from validation_provenance import ValidationProvenanceError
from validation_provenance import ValidationPublicationTransaction
from validation_provenance import VerificationResult
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS
from vnext.report import read_validated_report
from vnext.terminal_cycle import TERMINAL_GATE_IDS
from vnext.terminal_cycle import TerminalCycleError
from vnext.terminal_cycle import execute_terminal_publication_cycle


REPO_ROOT = Path(__file__).resolve().parents[2]


class TerminalCycleTest(unittest.TestCase):
    """Prove every formal terminal consumer retains one pointer authority."""

    def _fixture(
        self, *, root: Path
    ) -> tuple[ValidationPublicationTransaction, SourceSnapshot]:
        """Create a pinned view, real pointer bytes, mirrors, and source.

        Args:
            root: Temporary formal publication root.

        Returns:
            Transaction and deterministic clean source observation.
        """
        view, files = publication_fixture(root=root)
        pointer = root / "outputs" / "active_publication.json"
        pointer.write_bytes(b"publication_A\n")
        for relative, mirror_relative in ROOT_MIRROR_RELATIVE_PATHS.items():
            mirror = root / mirror_relative
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_bytes(files[relative])
        transaction = ValidationPublicationTransaction(
            publication_view=view,
            pointer_bytes=pointer.read_bytes(),
        )
        source = SourceSnapshot(
            checkout_status="GIT_CLEAN",
            source_commit="1" * 40,
            tree_sha256="2" * 64,
            file_count=1,
            dirty_paths=(),
        )
        return transaction, source

    @staticmethod
    def _publish_fixture(*, workdir: Path, **_arguments: object) -> dict:
        """Persist the one permitted generated sidecar for the cycle.

        Args:
            workdir: Formal publication root.
            _arguments: Remaining production publication arguments.

        Returns:
            Minimal run binding consumed by the terminal result.
        """
        path = workdir / "outputs" / "validation_snapshot_provenance.json"
        path.write_bytes(b'{"fixture":"pinned"}\n')
        return {"run_id": "fixture-run"}

    def test_all_consumers_share_one_view_and_leave_authority_unchanged(
        self,
    ) -> None:
        """Bind Stage10/11/12 and snapshot checks to one transaction."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transaction, source = self._fixture(root=root)
            pointer_before = (
                root / "outputs" / "active_publication.json"
            ).read_bytes()
            mirrors_before = {
                relative: (root / mirror).read_bytes()
                for relative, mirror in ROOT_MIRROR_RELATIVE_PATHS.items()
            }
            with mock.patch(
                "vnext.terminal_cycle.capture_source_snapshot",
                return_value=source,
            ), mock.patch(
                "vnext.terminal_cycle.pin_validation_publication_transaction",
                return_value=transaction,
            ) as pin, mock.patch(
                "vnext.terminal_cycle.publish_validation_snapshot",
                side_effect=self._publish_fixture,
            ), mock.patch(
                "vnext.terminal_cycle.verify_validation_snapshot",
                return_value=VerificationResult(errors=(), warnings=()),
            ), mock.patch.object(
                socket,
                "socket",
                side_effect=AssertionError("terminal cycle opened a socket"),
            ):
                result = execute_terminal_publication_cycle(
                    publication_root=root,
                    expected_publication_id="publication_fixture",
                )
            self.assertEqual(1, pin.call_count)
            self.assertEqual(
                TERMINAL_GATE_IDS,
                tuple(gate["gate_id"] for gate in result["gates"]),
            )
            self.assertTrue(all(
                gate["outcome"] == "PASSED" for gate in result["gates"]
            ))
            self.assertEqual(
                "publication_fixture", result["publication_id"]
            )
            self.assertEqual(
                result["authority_hashes_before"],
                result["authority_hashes_after"],
            )
            self.assertEqual(
                pointer_before,
                (root / "outputs" / "active_publication.json").read_bytes(),
            )
            self.assertEqual(
                mirrors_before,
                {
                    relative: (root / mirror).read_bytes()
                    for relative, mirror in (
                        ROOT_MIRROR_RELATIVE_PATHS.items()
                    )
                },
            )

    def test_real_pointer_switch_after_report_fails_before_stage12(
        self,
    ) -> None:
        """Reject report(A) plus Stage12/checker(B) in one public cycle."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transaction, source = self._fixture(root=root)
            pointer = root / "outputs" / "active_publication.json"

            def read_then_switch(*, publication_view: object) -> str:
                """Read the real pinned report, then mutate real authority."""
                report = read_validated_report(
                    publication_view=publication_view,
                )
                pointer.write_bytes(b"publication_B\n")
                return report

            with mock.patch(
                "vnext.terminal_cycle.capture_source_snapshot",
                return_value=source,
            ), mock.patch(
                "vnext.terminal_cycle.pin_validation_publication_transaction",
                return_value=transaction,
            ), mock.patch(
                "vnext.terminal_cycle.read_validated_report",
                side_effect=read_then_switch,
            ):
                with self.assertRaisesRegex(
                    ValidationProvenanceError,
                    "ACTIVE_POINTER_CHANGED_DURING_VALIDATION_TRANSACTION",
                ):
                    execute_terminal_publication_cycle(
                        publication_root=root,
                        expected_publication_id="publication_fixture",
                    )
            self.assertEqual(b"publication_B\n", pointer.read_bytes())
            self.assertFalse(
                (
                    root
                    / "outputs"
                    / "validation_snapshot_provenance.json"
                ).exists()
            )

    def test_public_cli_rejects_output_overlapping_active_pointer(
        self,
    ) -> None:
        """Fail with structured output and no default traceback on overwrite."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outputs").mkdir()
            completed = subprocess.run(
                args=[
                    sys.executable,
                    str(REPO_ROOT / "tools" / "vnext_terminal_cycle.py"),
                    "--publication-root",
                    str(root),
                    "--expected-publication-id",
                    "publication_fixture",
                    "--output",
                    str(root / "outputs" / "active_publication.json"),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(1, completed.returncode)
        self.assertEqual("", completed.stderr)
        envelope = json.loads(completed.stdout)
        self.assertFalse(envelope["ok"])
        self.assertEqual(
            "TERMINAL_CYCLE_FAILED", envelope["error"]["code"]
        )
        self.assertIn(
            "TERMINAL_OUTPUT_OVERLAPS_AUTHORITY",
            envelope["error"]["message"],
        )

    def test_partial_snapshot_publication_is_removed_on_failure(self) -> None:
        """Leave no successful-looking sidecar after a post-write exception."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transaction, source = self._fixture(root=root)
            sidecar = (
                root / "outputs" / "validation_snapshot_provenance.json"
            )

            def write_then_fail(**_arguments: object) -> dict:
                """Model a real mid-publication sidecar write failure."""
                sidecar.write_bytes(b'{"partial":true}\n')
                raise ValidationProvenanceError("fixture postflight failure")

            with mock.patch(
                "vnext.terminal_cycle.capture_source_snapshot",
                return_value=source,
            ), mock.patch(
                "vnext.terminal_cycle.pin_validation_publication_transaction",
                return_value=transaction,
            ), mock.patch(
                "vnext.terminal_cycle.publish_validation_snapshot",
                side_effect=write_then_fail,
            ):
                with self.assertRaisesRegex(
                    TerminalCycleError,
                    "SNAPSHOT_PUBLICATION_FAILED",
                ):
                    execute_terminal_publication_cycle(
                        publication_root=root,
                        expected_publication_id="publication_fixture",
                    )
            self.assertFalse(sidecar.exists())


if __name__ == "__main__":
    unittest.main()
