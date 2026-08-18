"""Pinned report-input and active-publication read-only tests."""

from __future__ import annotations

import importlib.util
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vnext.canonical import sha256_bytes
from vnext.publication import REQUIRED_BUNDLE_FILES
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS, PublicationView
from vnext.report import REPORT_INPUT_FILES, load_report_inputs
from vnext.report import read_validated_report, validate_active_publication
from vnext.report import validate_golden_results


def publication_fixture(*, root: Path) -> tuple[PublicationView, dict]:
    """Create one minimal pinned-view fixture plus its exact artifact bytes.

    Args:
        root: Temporary workspace receiving the immutable fixture bundle.

    Returns:
        A manually pinned view and every manifest-listed byte string.
    """
    bundle = root / "outputs" / "publications" / "publication_fixture"
    bundle.mkdir(parents=True)
    files = {
        relative: (relative + "\n").encode("utf-8")
        for relative in REQUIRED_BUNDLE_FILES
    }
    files["golden_results.csv"] = (
        "assertion_id,description,expected,actual,status,evidence_path,notes\n"
        "G1,fixture,1,1,PASS,fixture.json,exact\n"
    ).encode("utf-8")
    files["validation_run_manifest.json"] = (
        b'{"mode":"FULL_VALIDATION","result":"PASSED",'
        b'"run_id":"fixture-run"}\n'
    )
    files["publication_validation_receipt.json"] = (
        b'{"record_type":"VALIDATION_RECEIPT","status":"PASSED",'
        b'"validation_receipt_id":"receipt-fixture"}\n'
    )
    files["REPORT_\u5341\u516c\u53f8\u8d22\u52a1\u6307\u6807.md"] = (
        b"# Fixture active report\n\n"
        b"- run_id: `fixture-run`\n"
        b"- result: `PASSED`\n"
    )
    records = []
    for relative in sorted(files):
        content = files[relative]
        path = bundle / relative
        path.write_bytes(content)
        records.append(
            {
                "path": relative,
                "sha256": sha256_bytes(content=content),
                "size": len(content),
            }
        )
    return (
        PublicationView(
            publication_id="publication_fixture",
            bundle_dir=bundle,
            manifest={
                "files": records,
                "validation_receipt_id": "receipt-fixture",
            },
        ),
        files,
    )


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

    def test_active_stage_inputs_validate_without_network_or_writes(
        self,
    ) -> None:
        """Validate Golden, report, receipt, and mirrors from one view."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view, files = publication_fixture(root=root)
            for relative in sorted(ROOT_MIRROR_RELATIVE_PATHS):
                mirror = root / ROOT_MIRROR_RELATIVE_PATHS[relative]
                mirror.parent.mkdir(parents=True, exist_ok=True)
                mirror.write_bytes(files[relative])
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            with mock.patch.object(
                socket,
                "socket",
                side_effect=AssertionError("active read opened a socket"),
            ):
                self.assertEqual(1, validate_golden_results(
                    publication_view=view,
                ))
                self.assertIn(
                    "# Fixture active report",
                    read_validated_report(publication_view=view),
                )
                result = validate_active_publication(
                    publication_view=view,
                    publication_root=root,
                )
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual("publication_fixture", result["publication_id"])
            self.assertEqual("PASSED", result["validation_result"])
            self.assertEqual(before, after)

    def test_public_stage11_wrapper_has_no_active_write_boundary(self) -> None:
        """Keep the public wrapper read-only when an active view is pinned."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view, _files = publication_fixture(root=root)
            import sec_pipeline

            wrapper_path = (
                Path(__file__).resolve().parents[2]
                / "scripts"
                / "11_build_report.py"
            )
            spec = importlib.util.spec_from_file_location(
                "stage11_public_wrapper", wrapper_path,
            )
            if spec is None or spec.loader is None:
                self.fail("Stage 11 wrapper cannot be loaded")
            wrapper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wrapper)
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            with mock.patch.object(
                sec_pipeline,
                "open_active_publication_view",
                return_value=view,
            ), mock.patch.object(
                socket,
                "socket",
                side_effect=AssertionError("active report opened a socket"),
            ):
                wrapper.main(argv=[])
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_public_stage12_never_rewrites_active_root_mirrors(self) -> None:
        """Publish only sidecar provenance around one pinned active view."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view, files = publication_fixture(root=root)
            for relative in sorted(ROOT_MIRROR_RELATIVE_PATHS):
                mirror = root / ROOT_MIRROR_RELATIVE_PATHS[relative]
                mirror.parent.mkdir(parents=True, exist_ok=True)
                mirror.write_bytes(files[relative])
            pointer = root / "outputs" / "active_publication.json"
            pointer.write_text("{}\n", encoding="utf-8")
            import sec_pipeline

            wrapper_path = (
                Path(__file__).resolve().parents[2]
                / "scripts"
                / "12_validate_repair.py"
            )
            spec = importlib.util.spec_from_file_location(
                "stage12_public_wrapper", wrapper_path,
            )
            if spec is None or spec.loader is None:
                self.fail("Stage 12 wrapper cannot be loaded")
            wrapper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wrapper)
            before = {
                relative: (root / path).read_bytes()
                for relative, path in ROOT_MIRROR_RELATIVE_PATHS.items()
            }
            with mock.patch.object(
                wrapper, "WORKDIR", root,
            ), mock.patch.object(
                sec_pipeline, "WORKDIR", root,
            ), mock.patch.object(
                PublicationView, "open", return_value=view,
            ) as opened, mock.patch.object(
                wrapper, "invalidate_validation_snapshot",
            ), mock.patch.object(
                wrapper, "capture_source_snapshot", return_value=object(),
            ), mock.patch.object(
                wrapper, "publish_validation_snapshot",
            ) as published, mock.patch(
                "vnext.publication.recover_publication_mirrors",
            ), mock.patch.object(
                wrapper,
                "ensure_report_provenance_notice",
                side_effect=AssertionError("active report rewrite"),
            ), mock.patch.object(
                wrapper,
                "fail_validation_snapshot",
                side_effect=AssertionError("active fail rewrite"),
            ):
                wrapper.main()
            after = {
                relative: (root / path).read_bytes()
                for relative, path in ROOT_MIRROR_RELATIVE_PATHS.items()
            }
            self.assertEqual(before, after)
            self.assertEqual(1, opened.call_count)
            transaction = published.call_args.kwargs[
                "publication_transaction"
            ]
            self.assertIs(view, transaction.publication_view)

    def test_public_stage12_recovers_initial_mirror_divergence(
        self,
    ) -> None:
        """Repair roots from the pointer and still fail the tampered attempt."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view, files = publication_fixture(root=root)
            for relative in sorted(ROOT_MIRROR_RELATIVE_PATHS):
                mirror = root / ROOT_MIRROR_RELATIVE_PATHS[relative]
                mirror.parent.mkdir(parents=True, exist_ok=True)
                mirror.write_bytes(files[relative])
            divergent = root / "outputs" / "metrics_matrix.csv"
            divergent.write_bytes(b"tampered\n")
            pointer = root / "outputs" / "active_publication.json"
            pointer.write_text("{}\n", encoding="utf-8")

            wrapper_path = (
                Path(__file__).resolve().parents[2]
                / "scripts"
                / "12_validate_repair.py"
            )
            spec = importlib.util.spec_from_file_location(
                "stage12_recovery_wrapper", wrapper_path,
            )
            if spec is None or spec.loader is None:
                self.fail("Stage 12 wrapper cannot be loaded")
            wrapper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wrapper)

            def recover_from_pointer(*, publication_root: Path) -> str:
                """Model the real recovery write from the pinned bundle."""
                self.assertEqual(root, publication_root)
                for relative in sorted(ROOT_MIRROR_RELATIVE_PATHS):
                    mirror = root / ROOT_MIRROR_RELATIVE_PATHS[relative]
                    mirror.write_bytes(files[relative])
                return view.publication_id

            with mock.patch.object(
                wrapper, "WORKDIR", root,
            ), mock.patch.object(
                PublicationView, "open", return_value=view,
            ), mock.patch.object(
                wrapper, "invalidate_validation_snapshot",
            ), mock.patch.object(
                wrapper, "capture_source_snapshot", return_value=object(),
            ), mock.patch(
                "vnext.publication.recover_publication_mirrors",
                side_effect=recover_from_pointer,
            ), self.assertRaises(SystemExit) as raised:
                wrapper.main()
            self.assertEqual(1, raised.exception.code)
            self.assertEqual(files["metrics_matrix.csv"], divergent.read_bytes())

    def test_active_validation_rejects_one_divergent_root_mirror(self) -> None:
        """Fail closed when a compatibility mirror differs from the view."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view, files = publication_fixture(root=root)
            for relative in sorted(ROOT_MIRROR_RELATIVE_PATHS):
                mirror = root / ROOT_MIRROR_RELATIVE_PATHS[relative]
                mirror.parent.mkdir(parents=True, exist_ok=True)
                mirror.write_bytes(files[relative])
            (root / "outputs" / "metrics_matrix.csv").write_bytes(
                b"tampered\n"
            )
            with self.assertRaisesRegex(
                ValueError,
                r"^ACTIVE_ROOT_MIRROR_MISMATCH:",
            ):
                validate_active_publication(
                    publication_view=view,
                    publication_root=root,
                )

    def test_open_view_stays_pinned_when_pointer_switches_during_read(
        self,
    ) -> None:
        """Keep one consumer on its original bundle after pointer mutation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view, _files = publication_fixture(root=root)
            pointer = root / "active_publication.json"
            pointer.write_text("publication_A\n", encoding="utf-8")
            original_read = PublicationView.read_bytes
            calls = 0

            def switch_after_first_read(
                pinned: PublicationView, *, relative_path: str
            ) -> bytes:
                """Switch external authority after the first pinned read."""
                nonlocal calls
                calls += 1
                content = original_read(
                    pinned,
                    relative_path=relative_path,
                )
                if calls == 1:
                    pointer.write_text("publication_B\n", encoding="utf-8")
                return content

            with mock.patch.object(
                PublicationView,
                "read_bytes",
                autospec=True,
                side_effect=switch_after_first_read,
            ):
                report = read_validated_report(publication_view=view)
            self.assertIn("fixture-run", report)
            self.assertEqual("publication_B\n", pointer.read_text(
                encoding="utf-8"
            ))
            self.assertEqual("publication_fixture", view.publication_id)


if __name__ == "__main__":
    unittest.main()
