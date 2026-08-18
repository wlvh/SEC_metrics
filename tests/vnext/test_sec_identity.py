"""Prove the R3 SEC identity is fixed and environment-owned.

The production SEC loader and full/live prerequisite gate must both use the
same identity validator.  The repository fixes the organization to ``axaxl``
while the accountable contact address exists only in ``SEC_CONTACT_EMAIL``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT


SCRIPTS_DIR = REPO_ROOT / "scripts"
TOOLS_DIR = REPO_ROOT / "tools"
for import_path in (SCRIPTS_DIR, TOOLS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from run_acceptance import external_blockers  # noqa: E402
from sec_http import SecIdentityError, load_config  # noqa: E402


def write_sec_config(*, root: Path, organization: str = "axaxl") -> Path:
    """Write a contact-free SEC config and return its path.

    Args:
        root: Isolated repository-like directory.
        organization: Organization value being exercised.

    Returns:
        UTF-8 JSON config path with no contact-email field.
    """
    config_path = root / "config" / "sec_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "organization": organization,
                "rate_limit_per_sec": 5,
                "max_retries": 4,
                "backoff_initial_seconds": 1.0,
            }
        ),
        encoding="utf-8",
    )
    return config_path


class SecIdentityR3Test(unittest.TestCase):
    """Exercise fail-fast identity rules at both production entry points."""

    def test_missing_environment_contact_has_stable_error_code(self) -> None:
        """Reject an absent environment contact before any SEC request."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            config_path = write_sec_config(root=Path(directory))
            with self.assertRaises(SecIdentityError) as raised:
                load_config(config_path=config_path)
        self.assertEqual("SEC_CONTACT_EMAIL_REQUIRED", raised.exception.code)

    def test_config_contact_is_never_a_production_fallback(self) -> None:
        """Ignore neither authority nor failure by accepting a config email."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            config_path = write_sec_config(root=Path(directory))
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            payload["contact_email"] = "ops@corp.co"
            config_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(SecIdentityError) as raised:
                load_config(config_path=config_path)
        self.assertEqual("SEC_CONTACT_EMAIL_REQUIRED", raised.exception.code)

    def test_environment_contact_and_fixed_organization_load(self) -> None:
        """Build the runtime User-Agent identity only from approved sources."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"SEC_CONTACT_EMAIL": "ops@corp.co"},
            clear=True,
        ):
            config = load_config(
                config_path=write_sec_config(root=Path(directory))
            )
        self.assertEqual("axaxl", config["organization"])
        self.assertEqual("ops@corp.co", config["contact_email"])

    def test_nonfixed_organization_fails_closed(self) -> None:
        """Reject a config that changes the approved organization."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"SEC_CONTACT_EMAIL": "ops@corp.co"},
            clear=True,
        ):
            config_path = write_sec_config(
                root=Path(directory),
                organization="another-org",
            )
            with self.assertRaises(SecIdentityError) as raised:
                load_config(config_path=config_path)
        self.assertEqual("SEC_ORGANIZATION_INVALID", raised.exception.code)

    def test_reserved_environment_contact_fails_closed(self) -> None:
        """Reject example and reserved-domain contacts from the environment."""
        for email in ("test@example.com", "ops@corp.test", "ops@x.invalid"):
            with self.subTest(email=email), tempfile.TemporaryDirectory(
            ) as directory, mock.patch.dict(
                os.environ,
                {"SEC_CONTACT_EMAIL": email},
                clear=True,
            ):
                config_path = write_sec_config(root=Path(directory))
                with self.assertRaises(SecIdentityError) as raised:
                    load_config(config_path=config_path)
                self.assertEqual(
                    "SEC_CONTACT_EMAIL_INVALID",
                    raised.exception.code,
                )

    def test_full_prerequisite_reuses_missing_contact_code(self) -> None:
        """Expose the production identity error unchanged in full readiness."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            root = Path(directory)
            write_sec_config(root=root)
            with mock.patch(
                "run_acceptance.load_requirement_snapshot",
                return_value={"pending_decision_ids": []},
            ), mock.patch(
                "run_acceptance.capture_source_snapshot",
                return_value={},
            ):
                blockers = external_blockers(repo_root=root)
        self.assertEqual(
            [
                "OPENAI_API_KEY_REQUIRED",
                "SEC_CONTACT_EMAIL_REQUIRED",
            ],
            [blocker["code"] for blocker in blockers],
        )


if __name__ == "__main__":
    unittest.main()
