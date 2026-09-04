"""Validate real SEC contact approval and fully rebound offline mutations."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_issue28_v2 import clone_authority, refresh
from vnext.canonical import atomic_write_json, sha256_bytes, sha256_file, strict_json_file
from vnext.requirement_profile import RequirementProfileError, validate_execution_authority
from vnext.requirements import RequirementError, load_requirement_snapshot


SNAPSHOT = REPO_ROOT / "requirements/issue_28_v2"
DECISION_ID = "S-SEC-CONTACT-AUTHORITY"
SOURCE_ID = "OWNER_SEC_CONTACT_POLICY"
POLICY_KIND = "SEC_CONTACT_AUTHORITY_POLICY"
SECTION = "sec_contact_authority"
EXPECTED_CHOICE = {
    "kind": POLICY_KIND,
    "default_contact_email": "12@qq.com",
    "environment_override": "SEC_CONTACT_EMAIL",
    "precedence": "EXPLICIT_ENVIRONMENT_IF_PRESENT_ELSE_REPOSITORY_DEFAULT",
    "invalid_explicit_environment_override": "FAIL_CLOSED_NO_DEFAULT_FALLBACK",
    "contact_is_public_user_agent_identity": True,
    "provider_calls_authorized": False,
    "paid_model_calls_authorized": False,
    "live_qualification_authorized": False,
    "publication_authorized": False,
}
NO_EXECUTION_GRANTS = (
    "provider_calls_authorized",
    "paid_model_calls_authorized",
    "live_qualification_authorized",
    "publication_authorized",
)


def contact_records(snapshot: Path) -> tuple:
    """Read the actual contact record, embedded comment and bound capture."""
    register = strict_json_file(path=snapshot / "decision_register.json")
    decision = next(d for d in register["decisions"] if d["decision_id"] == DECISION_ID)
    baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
    source = next(s for s in baseline["policy_evidence"] if s["source_id"] == SOURCE_ID)
    capture_path = snapshot.parent.parent / source["evidence_path"]
    capture = strict_json_file(path=capture_path)
    return register, decision, baseline, source, capture_path, capture


def write_rebound_contact(*, snapshot: Path, register: dict, baseline: dict,
                          source: dict, capture_path: Path, capture: dict) -> None:
    """Rebind the disposable capture, execution entry and four outer files."""
    atomic_write_json(path=capture_path, value=capture)
    baseline["execution_authority"]["files"][source["evidence_path"]] = {
        "sha256": sha256_file(path=capture_path),
        "size": capture_path.stat().st_size,
    }
    atomic_write_json(path=snapshot / "decision_register.json", value=register)
    refresh(snapshot, baseline)


def rebound_contact_choice(*, snapshot: Path, changes: dict) -> None:
    """Make forged policy copies agree, so only semantic safety can reject."""
    register, decision, baseline, source, capture_path, capture = contact_records(snapshot)
    decision["choice"].update(changes)
    document = json.loads(source["text"])
    document.update({key: value for key, value in decision["choice"].items() if key != "kind"})
    source["text"] = json.dumps(document, indent=2)
    source["source_sha256"] = sha256_bytes(content=source["text"].encode("utf-8"))
    capture.update(raw_body=source["text"], body_sha256=source["source_sha256"])
    write_rebound_contact(snapshot=snapshot, register=register, baseline=baseline,
                          source=source, capture_path=capture_path, capture=capture)


class SecContactRequirementPolicyTest(unittest.TestCase):
    """Exercise the complete v2 loader without constructing an SEC client."""

    def setUp(self) -> None:
        socket_patch = mock.patch("socket.socket", side_effect=AssertionError("NO_NETWORK"))
        self.socket = socket_patch.start()
        self.addCleanup(socket_patch.stop)
        self.addCleanup(self.socket.assert_not_called)

    def assert_rebound_snapshot_rejected(self, snapshot: Path) -> None:
        """Prove outer bindings agree before testing the inner rejection."""
        baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
        for relative, binding in baseline["snapshot_files"].items():
            path = snapshot / relative
            self.assertEqual(binding, {"sha256": sha256_file(path=path), "size": path.stat().st_size})
        for source in baseline["policy_evidence"]:
            if source["kind"] != "OWNER_ISSUE_COMMENT_POLICY":
                continue
            path = snapshot.parent.parent / source["evidence_path"]
            self.assertEqual(baseline["execution_authority"]["files"][source["evidence_path"]],
                             {"sha256": sha256_file(path=path), "size": path.stat().st_size})
        with self.assertRaises((RequirementError, RequirementProfileError)):
            load_requirement_snapshot(snapshot_dir=snapshot)

    def test_real_owner_comment_is_the_single_policy_only_contact_authority(self) -> None:
        requirement = load_requirement_snapshot(snapshot_dir=SNAPSHOT)
        decision = requirement["effective_decisions"][DECISION_ID]
        _, _, baseline, source, _, capture = contact_records(SNAPSHOT)
        self.assertEqual(EXPECTED_CHOICE, decision["choice"])
        self.assertEqual("APPROVED", decision["status"])
        self.assertEqual("NOT_ACTIVATED", requirement["activation_state"])
        self.assertEqual({"source_id": SOURCE_ID, "section": SECTION,
                          "scope": "POLICY_CONTENT_ONLY"}, decision["policy_provenance"])
        self.assertEqual(
            "https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5536668333",
            source["source_url"],
        )
        self.assertEqual("github:wlvh", source["author"])
        self.assertEqual("2026-09-04T06:33:01Z", source["published_at_utc"])
        self.assertEqual(source["source_url"], capture["owner_comment_url"])
        self.assertEqual(source["author"], capture["author"])
        self.assertEqual(source["published_at_utc"], capture["published_at_utc"])
        self.assertEqual(source["text"], capture["raw_body"])
        self.assertEqual(source["source_sha256"], capture["body_sha256"])
        self.assertEqual(sha256_bytes(content=capture["raw_body"].encode("utf-8")),
                         capture["body_sha256"])
        self.assertEqual(
            {"decision": "APPROVE_SEC_CONTACT_AUTHORITY", "scope": "POLICY_CONTENT_ONLY",
             **{key: value for key, value in EXPECTED_CHOICE.items() if key != "kind"}},
            json.loads(capture["raw_body"]),
        )
        self.assertEqual("NOT_ISSUED", capture["transition_activation"])
        self.assertIs(capture["provider_paid_live_publication_authorization"], False)
        contact_invariants = [
            row for row in requirement["evaluated_invariants"]["by_invariant_id"].values()
            if row["kind"] == POLICY_KIND
        ]
        self.assertEqual([EXPECTED_CHOICE], [row["value"] for row in contact_invariants])
        self.assertIn("config/sec_config.json", baseline["execution_authority"]["files"])

    def test_complete_copied_snapshot_still_loads_and_binds_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            requirement = load_requirement_snapshot(snapshot_dir=snapshot)
            self.assertEqual(EXPECTED_CHOICE, requirement["effective_decisions"][DECISION_ID]["choice"])
            validate_execution_authority(repo_root=snapshot.parent.parent, requirement=requirement)

    def test_missing_policy_invariant_or_owner_source_fails_after_rebind(self) -> None:
        for operation in ("decision_and_invariant", "invariant", "owner_source"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                register, _, baseline, _, _, _ = contact_records(snapshot)
                profile = strict_json_file(path=snapshot / "invariant_profile.json")
                if operation in {"decision_and_invariant", "invariant"}:
                    profile["invariants"] = [r for r in profile["invariants"]
                                             if r["decision_id"] != DECISION_ID]
                if operation == "decision_and_invariant":
                    register["decisions"] = [r for r in register["decisions"]
                                             if r["decision_id"] != DECISION_ID]
                if operation == "owner_source":
                    baseline["policy_evidence"] = [s for s in baseline["policy_evidence"]
                                                    if s["source_id"] != SOURCE_ID]
                atomic_write_json(path=snapshot / "decision_register.json", value=register)
                atomic_write_json(path=snapshot / "invariant_profile.json", value=profile)
                refresh(snapshot, baseline)
                self.assert_rebound_snapshot_rejected(snapshot)

    def test_duplicate_contact_policy_or_provenance_fails_after_rebind(self) -> None:
        for operation in ("same_record", "second_global_instance", "owner_source"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                register, decision, baseline, source, _, _ = contact_records(snapshot)
                if operation == "owner_source":
                    baseline["policy_evidence"].append(deepcopy(source))
                    baseline["policy_evidence"].sort(key=lambda row: row["source_id"])
                else:
                    duplicate = deepcopy(decision)
                    if operation == "second_global_instance":
                        duplicate["decision_id"] += "-DUPLICATE"
                        profile = strict_json_file(path=snapshot / "invariant_profile.json")
                        profile["invariants"].append({
                            "invariant_id": "INV-SEC-CONTACT-AUTHORITY-DUPLICATE",
                            "decision_id": duplicate["decision_id"],
                        })
                        profile["invariants"].sort(key=lambda row: row["invariant_id"])
                        atomic_write_json(path=snapshot / "invariant_profile.json", value=profile)
                    register["decisions"].append(duplicate)
                atomic_write_json(path=snapshot / "decision_register.json", value=register)
                refresh(snapshot, baseline)
                self.assert_rebound_snapshot_rejected(snapshot)

    def test_fully_rebound_precedence_fallback_and_visibility_relaxations_fail(self) -> None:
        changes = (
            {"environment_override": "OTHER_CONTACT_EMAIL"},
            {"precedence": "REPOSITORY_DEFAULT_BEFORE_ENVIRONMENT"},
            {"invalid_explicit_environment_override": "DEFAULT_FALLBACK_ALLOWED"},
            {"contact_is_public_user_agent_identity": False},
            {"contact_is_public_user_agent_identity": 1},
        )
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                rebound_contact_choice(snapshot=snapshot, changes=change)
                self.assert_rebound_snapshot_rejected(snapshot)

    def test_fully_rebound_invalid_default_email_fails(self) -> None:
        for email in (None, 12, [], "", "bad", "ops@example.com", "ops@corp.test",
                      "ops@localhost", "ops@corp.co\nInjected-Header: value"):
            with self.subTest(email=email), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                rebound_contact_choice(snapshot=snapshot, changes={"default_contact_email": email})
                self.assert_rebound_snapshot_rejected(snapshot)

    def test_fully_rebound_execution_grants_fail(self) -> None:
        for field in NO_EXECUTION_GRANTS:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                rebound_contact_choice(snapshot=snapshot, changes={field: True})
                self.assert_rebound_snapshot_rejected(snapshot)

    def test_source_and_capture_metadata_are_checked_after_outer_rebind(self) -> None:
        mutations = (
            ("author", "author", "github:another-user"),
            ("source_url", "owner_comment_url",
             "https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-1"),
            ("published_at_utc", "published_at_utc", "2026-09-04T06:33:02Z"),
            ("text", "raw_body", None),
        )
        for side in ("source", "capture"):
            for source_field, capture_field, forged in mutations:
                with self.subTest(side=side, field=source_field), tempfile.TemporaryDirectory() as directory:
                    snapshot = clone_authority(directory)
                    register, _, baseline, source, capture_path, capture = contact_records(snapshot)
                    value = source["text"] + "\n" if source_field == "text" else forged
                    if side == "source":
                        source[source_field] = value
                        source["source_sha256"] = sha256_bytes(content=source["text"].encode("utf-8"))
                    else:
                        capture[capture_field] = value
                        capture["body_sha256"] = sha256_bytes(content=capture["raw_body"].encode("utf-8"))
                    write_rebound_contact(snapshot=snapshot, register=register, baseline=baseline,
                                          source=source, capture_path=capture_path, capture=capture)
                    self.assert_rebound_snapshot_rejected(snapshot)

    def test_decision_cannot_forge_the_approval_author_url_time_or_body(self) -> None:
        mutations = (
            {"approved_by": "github:another-user"},
            {"evidence": "https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-1"},
            {"approved_at_utc": "2026-09-04T06:33:02Z"},
            {"choice": {**EXPECTED_CHOICE, "default_contact_email": "ops@corp.co"}},
        )
        for change in mutations:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                register, decision, _, _, _, _ = contact_records(snapshot)
                decision.update(change)
                atomic_write_json(path=snapshot / "decision_register.json", value=register)
                refresh(snapshot)
                self.assert_rebound_snapshot_rejected(snapshot)

    def test_contact_config_drift_preserves_history_but_blocks_current_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            requirement = load_requirement_snapshot(snapshot_dir=snapshot)
            config_path = snapshot.parent.parent / "config/sec_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["contact_email"] = "ops@corp.co"
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            historical = load_requirement_snapshot(snapshot_dir=snapshot)
            self.assertEqual(requirement["requirement_closure_hash"],
                             historical["requirement_closure_hash"])
            with self.assertRaises(RequirementProfileError):
                validate_execution_authority(repo_root=snapshot.parent.parent, requirement=historical)


if __name__ == "__main__":
    unittest.main()
