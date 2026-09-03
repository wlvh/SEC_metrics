"""Prove SEC config defaults and explicit environment overrides are validated.

The production SEC loader and full/live prerequisite gate must both use the
same identity validator.  The repository fixes the organization to ``axaxl``
while ``SEC_CONTACT_EMAIL`` overrides the repository contact address.
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
from sec_http import SecHttpClient, SecIdentityError, load_config  # noqa: E402
from sec_http import validate_sec_identity  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402


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

    def test_missing_contact_has_stable_error_code(self) -> None:
        """Reject contact missing from both config and environment."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            config_path = write_sec_config(root=Path(directory))
            with self.assertRaises(SecIdentityError) as raised:
                load_config(config_path=config_path)
        self.assertEqual("SEC_CONTACT_EMAIL_REQUIRED", raised.exception.code)

    def test_config_contact_is_the_production_default(self) -> None:
        """Read repository config without an export or launcher; do not fetch."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with mock.patch("sec_http.urlopen") as opener:
                client = SecHttpClient(
                    workdir=Path(directory),
                    config_path=REPO_ROOT / "config/sec_config.json",
                    log_path=Path(directory) / "evidence/requests_log.csv",
                )
            self.assertEqual("axaxl 12@qq.com", client.user_agent)
            opener.assert_not_called()
            self.assertNotIn("SEC_CONTACT_EMAIL", os.environ)

    def test_explicit_environment_contact_overrides_config(self) -> None:
        """An explicit override wins, but an invalid override never falls back."""
        config = {"organization": "axaxl", "contact_email": "12@qq.com"}
        for email, error in (
            ("ops@corp.co", None),
            ("", "SEC_CONTACT_EMAIL_REQUIRED"),
            ("bad", "SEC_CONTACT_EMAIL_INVALID"),
        ):
            with self.subTest(email=email), mock.patch.dict(
                os.environ, {"SEC_CONTACT_EMAIL": email}, clear=True,
            ):
                if error:
                    with self.assertRaises(SecIdentityError) as raised:
                        validate_sec_identity(config=config)
                    self.assertEqual(error, raised.exception.code)
                else:
                    self.assertEqual(
                        ("axaxl", email), validate_sec_identity(config=config),
                    )

    def test_invalid_config_contacts_fail_closed(self) -> None:
        """Apply the same validation to configured contacts, including types."""
        for email in (None, 12, [], "bad", "ops@example.com", "ops@corp.test"):
            with self.subTest(email=email), mock.patch.dict(
                os.environ, {}, clear=True,
            ):
                with self.assertRaises(SecIdentityError) as raised:
                    validate_sec_identity(config={
                        "organization": "axaxl", "contact_email": email,
                    })
                self.assertEqual("SEC_CONTACT_EMAIL_INVALID", raised.exception.code)

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
        requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_15_v1",
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            root = Path(directory)
            write_sec_config(root=root)
            with mock.patch(
                "run_acceptance.load_requirement_snapshot",
                return_value=requirement,
            ), mock.patch(
                "run_acceptance.capture_source_snapshot",
                return_value={},
            ):
                blockers = external_blockers(repo_root=root)
                (root / "config/sec_config.json").write_bytes(
                    (REPO_ROOT / "config/sec_config.json").read_bytes()
                )
                configured_blockers = external_blockers(repo_root=root)
        self.assertEqual(
            [
                "DEEPSEEK_API_KEY_REQUIRED",
                "SEC_CONTACT_EMAIL_REQUIRED",
            ],
            [blocker["code"] for blocker in blockers],
        )
        self.assertEqual(
            ["DEEPSEEK_API_KEY_REQUIRED"],
            [blocker["code"] for blocker in configured_blockers],
        )


if __name__ == "__main__":
    unittest.main()
