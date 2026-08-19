"""AST semantic-boundary and publishable secret-token audit tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT


TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from check_vnext_semantics import audit_python_file  # noqa: E402
from check_vnext_semantics import compile_business_literal_pattern  # noqa: E402
from check_vnext_semantics import run_audit, scan_secret_token  # noqa: E402


class SemanticAuditTest(unittest.TestCase):
    """Prove executable business literals and leaked tokens fail the gate."""

    def test_repository_vnext_and_bridge_boundary_is_clean(self) -> None:
        """Audit production and review/acceptance bridge executables."""
        receipt = run_audit(
            repo_root=REPO_ROOT, secret_roots=[], secret_token="",
        )
        self.assertEqual("PASS", receipt["status"])
        self.assertIn("tools/vnext_review.py", receipt["source_hashes"])
        self.assertIn(
            "tools/check_vnext_semantics.py", receipt["source_hashes"],
        )
        self.assertIn(
            "tools/check_no_company_literals.py",
            receipt["source_hashes"],
        )
        self.assertIn(
            "scripts/sec_pipeline.py", receipt["source_hashes"],
        )
        self.assertIn(
            "config/source_strategy_registry.json", receipt["source_hashes"],
        )

    def test_business_literal_in_executable_is_reported(self) -> None:
        """Reject a metric/company parser branch by AST literal."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "scripts/vnext/example.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                '"""Example."""\nVALUE = "occupancy company parser"\n',
                encoding="utf-8",
            )
            hits = audit_python_file(
                path=path,
                repo_root=root,
                business_literal_pattern=compile_business_literal_pattern(
                    repo_root=REPO_ROOT
                ),
            )
        self.assertEqual("BUSINESS_LITERAL", hits[0]["type"])
        self.assertFalse(hits[0]["allowed"])

    def test_ai_adapter_direct_network_import_is_reported(self) -> None:
        """Keep broad network ownership outside the approved callback."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "scripts/vnext/ai_adapter.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                '"""Bad adapter."""\nimport socket\n', encoding="utf-8",
            )
            hits = audit_python_file(
                path=path,
                repo_root=root,
                business_literal_pattern=compile_business_literal_pattern(
                    repo_root=REPO_ROOT
                ),
            )
        self.assertIn("AI_FORBIDDEN_IMPORT", [hit["type"] for hit in hits])

    def test_fixed_openai_transport_is_narrowly_allowed(self) -> None:
        """Allow only the repository-pinned Responses transport boundary."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "scripts/vnext/ai_adapter.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                '"""Pinned transport."""\n'
                "import socket\n"
                "from urllib.request import Request\n"
                '_OPENAI_API_KEY_ENV = "OPENAI_API_KEY"\n'
                '_OPENAI_ENDPOINT_HOST = "api.openai.com"\n'
                "_OPENAI_RESPONSES_URL = "
                '"https://api.openai.com/v1/responses"\n'
                "_OPENAI_OPENER.open(fullurl=Request("
                "url=_OPENAI_RESPONSES_URL))\n",
                encoding="utf-8",
            )
            hits = audit_python_file(
                path=path,
                repo_root=root,
                business_literal_pattern=compile_business_literal_pattern(
                    repo_root=REPO_ROOT
                ),
            )
        self.assertEqual([], hits)

    def test_generic_terms_are_not_semantic_literal_hits(self) -> None:
        """Allow ordinary shared-engine words excluded by the registry."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "scripts/vnext/example.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                '"""Shared engine."""\n'
                'VALUE = "risk value event income current"\n',
                encoding="utf-8",
            )
            hits = audit_python_file(
                path=path,
                repo_root=root,
                business_literal_pattern=compile_business_literal_pattern(
                    repo_root=REPO_ROOT
                ),
            )
        self.assertEqual([], hits)

    def test_secret_like_token_scan_reports_hash_not_token(self) -> None:
        """Detect leaked bytes without copying a secret into receipts."""
        token = "sk-test-never-publish-123456"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "outputs/report.txt"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "prefix " + token + " suffix", encoding="utf-8"
            )
            hits = scan_secret_token(roots=[root], secret_token=token)
        self.assertEqual(1, len(hits))
        self.assertEqual("SECRET_TOKEN", hits[0]["type"])
        self.assertNotIn(token, str(hits[0]))

    def test_secret_scan_fails_closed_for_every_symlink_shape(self) -> None:
        """Reject root, nested, broken, and looping artifact aliases."""
        token = "sk-test-never-publish-symlink-123456"
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            secret_dir = base / "secret"
            secret_dir.mkdir()
            secret_file = secret_dir / "token.txt"
            secret_file.write_text(token, encoding="utf-8")

            root_link = base / "root-link"
            root_link.symlink_to(secret_dir, target_is_directory=True)

            nested_file_root = base / "nested-file"
            nested_file_root.mkdir()
            (nested_file_root / "token.txt").symlink_to(secret_file)

            nested_dir_root = base / "nested-dir"
            nested_dir_root.mkdir()
            (nested_dir_root / "alias").symlink_to(
                secret_dir, target_is_directory=True,
            )

            broken_root = base / "broken"
            broken_root.mkdir()
            (broken_root / "missing").symlink_to(base / "absent")

            loop_root = base / "loop"
            loop_root.mkdir()
            (loop_root / "self").symlink_to("self")

            for label, root in (
                ("root", root_link),
                ("nested_file", nested_file_root),
                ("nested_directory", nested_dir_root),
                ("broken", broken_root),
                ("loop", loop_root),
            ):
                with self.subTest(label=label):
                    hits = scan_secret_token(
                        roots=[root], secret_token=token,
                    )
                    self.assertEqual(1, len(hits))
                    self.assertEqual(
                        "SECRET_SCAN_SYMLINK", hits[0]["type"],
                    )
                    self.assertFalse(hits[0]["allowed"])
                    self.assertNotIn(token, str(hits[0]))

            receipt = run_audit(
                repo_root=REPO_ROOT,
                secret_roots=[root_link],
                secret_token=token,
            )
            self.assertEqual("FAIL", receipt["status"])
            self.assertEqual(
                "SECRET_ARTIFACT_SCAN_FAILED", receipt["failure_code"],
            )


if __name__ == "__main__":
    unittest.main()
