"""Successor Requirement transition and historical compatibility gates."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_issue15_authority import copy_test_repository
from tests.vnext.issue28_fixture_support import copy_profile_repository, evolve_to_v2
from vnext.canonical import atomic_write_json, content_hash, sha256_file
from vnext.canonical import strict_json_file
from vnext.publication import PublicationView, ROOT_MIRROR_RELATIVE_PATHS
from vnext.publication import verify_publication_bundle
from vnext.requirement_profile import EXPLICIT_ARTIFACT_GENERATION
from vnext.requirement_profile import LEGACY_ARTIFACT_GENERATION
from vnext.requirement_profile import RequirementProfileError
from vnext.requirement_profile import validate_artifact_requirement_identity
from vnext.requirements import RequirementError, load_requirement_snapshot
from vnext.requirements import load_run_requirement_snapshot
from vnext.records import RecordError, validate_record
from vnext.run_store import RunStoreError, create_run


ISSUE_15_DIR = REPO_ROOT / "requirements" / "issue_15_v1"
ISSUE_28_DIR = REPO_ROOT / "requirements" / "issue_28_v1"
ISSUE_15_CLOSURE = (
    "sha256:e4b1d8141196fae9bb5da904692fd0d495ec69b89101b8304e12f6cb2640b7c7"
)
ISSUE_28_CLOSURE = (
    "sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac"
)
ACTIVE_R3 = (
    "publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8"
)
EXACT_R2 = (
    "publication_fe01e227848d6a4212318b4942742d06b0a2861df55e0b268df2062a441c438f"
)
ISSUE_15_FILE_BINDINGS = {
    "CONTRACT.md": (
        "9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec",
        47898,
    ),
    "baseline_manifest.json": (
        "f6dac7b0c37aeba77e477dfbb3539fa0bc8226b00843ee0e538406aa9911c25f",
        6137,
    ),
    "decision_register.json": (
        "c77d35f72ab87e75c1982baaa3522d48bb6b20b25822822ea2edd0578171ec0f",
        210918,
    ),
    "foundation_verification_receipt.json": (
        "fe6476db361607d6197f2d7145a1717a94d0ad98190dc08d17ece680933a0763",
        5136,
    ),
    "legacy_semantic_producer_inventory.json": (
        "78d2732a19ac838b00cb878e085bad2976b1dc16f2632438cf38276e64a442a1",
        143195,
    ),
    "source_strategy_baseline_receipt.json": (
        "fcd4e0e975a451834ffac4cefae071770531120ca767f9162d68e9079260198b",
        42147,
    ),
    "transfer_manifest.json": (
        "18f162d48131b3f6d56941dd446ec18089c7a336a50df8cb2c669e3b63711274",
        3906,
    ),
}


def _copied_issue28_repository(*, directory: str) -> Path:
    """Copy exact historical fixtures plus the successor five-file snapshot."""
    return copy_profile_repository(directory=directory)


def _rebind_snapshot_file(*, issue28: Path, relative: str) -> None:
    """Re-sign one tampered child file so semantic gates see the attack."""
    baseline_path = issue28 / "baseline_manifest.json"
    baseline = strict_json_file(path=baseline_path)
    path = issue28 / relative
    baseline["snapshot_files"][relative] = {
        "sha256": sha256_file(path=path),
        "size": path.stat().st_size,
    }
    atomic_write_json(path=baseline_path, value=baseline)


class Issue28RequirementTransitionFastTest(unittest.TestCase):
    """Keep successor and historical loader dispatch in the fast tier."""

    def test_profile_snapshot_loads_with_historical_parent_fast_smoke(self) -> None:
        """Load profile authority and its exact Issue #15 parent locally."""
        parent = load_requirement_snapshot(snapshot_dir=ISSUE_15_DIR)
        successor = load_requirement_snapshot(snapshot_dir=ISSUE_28_DIR)

        self.assertEqual("issue_15_v1", parent["requirement_id"])
        self.assertEqual(ISSUE_15_CLOSURE, parent["requirement_closure_hash"])
        self.assertEqual("issue_28_v1", successor["requirement_id"])
        self.assertEqual(ISSUE_28_CLOSURE, successor["requirement_closure_hash"])
        self.assertEqual("PROFILE_DRIVEN_V1", successor["requirement_generation"])
        self.assertEqual(
            EXPLICIT_ARTIFACT_GENERATION, successor["artifact_requirement_generation"],
        )
        self.assertEqual(
            parent["requirement_closure_hash"],
            successor["parent_requirement_closure_hash"],
        )
        self.assertEqual(["S-R5-B06-B13-MEANING"], successor["pending_decision_ids"])
        self.assertEqual(14, len(successor["evaluated_invariants"]["by_invariant_id"]))
        self.assertEqual(477, len(successor["transfer"]["fragments"]))
        self.assertEqual(5, len(successor["transfer"]["historical_material"]))
        self.assertEqual(
            {"CARRY_FORWARD": 189, "HISTORICAL_ONLY": 278, "SUPERSEDED": 10},
            strict_json_file(path=ISSUE_28_DIR / "transfer_manifest.json")[
                "fragment_classification_counts"
            ],
        )
        historical = successor["effective_decisions"]["S-HISTORICAL-EVIDENCE"]["choice"]
        self.assertEqual("NONE", historical["qualification_credit"])
        self.assertEqual("NOT_AUTHORIZED", historical["response_reuse"])
        self.assertEqual(
            "https://github.com/wlvh/SEC_metrics/issues/24",
            successor["effective_decisions"]["S-SESSION-RESOURCE"]["choice"][
                "source_issue_url"
            ],
        )


class Issue28RequirementTransitionTest(unittest.TestCase):
    """Reject successor tamper while preserving legacy artifact semantics."""

    def test_issue15_snapshot_bytes_remain_exact(self) -> None:
        """Freeze all seven Issue #15 files independently of child metadata."""
        self.assertEqual(
            set(ISSUE_15_FILE_BINDINGS),
            {path.name for path in ISSUE_15_DIR.iterdir() if path.is_file()},
        )
        for relative, (expected_hash, expected_size) in ISSUE_15_FILE_BINDINGS.items():
            path = ISSUE_15_DIR / relative
            self.assertFalse(path.is_symlink())
            self.assertEqual(expected_hash, sha256_file(path=path))
            self.assertEqual(expected_size, path.stat().st_size)

    def test_baseline_binds_exact_merged_main_and_parent_tree(self) -> None:
        """Resolve recorded Git objects without treating live HEAD as authority."""
        baseline = strict_json_file(path=ISSUE_28_DIR / "baseline_manifest.json")
        commit = baseline["repository"]["commit"]
        repository_tree = subprocess.check_output(
            ["git", "rev-parse", commit + "^{tree}"], cwd=REPO_ROOT, text=True,
        ).strip()
        parent_tree = subprocess.check_output(
            ["git", "rev-parse", commit + ":requirements/issue_15_v1"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
        self.assertEqual(baseline["repository"]["tree"], repository_tree)
        self.assertEqual(baseline["parent"]["snapshot_git_tree"], parent_tree)
        pointer = strict_json_file(
            path=REPO_ROOT / "outputs" / "active_publication.json"
        )
        self.assertEqual(
            baseline["active_publication"]["publication_id"], pointer["publication_id"],
        )
        self.assertEqual(
            baseline["active_publication"]["predecessor_publication_id"],
            pointer["previous_publication_id"],
        )

    def test_invariant_profile_contains_references_not_policy_values(self) -> None:
        """Keep policy content in the Decision Register, not a JSON DSL."""
        profile = strict_json_file(path=ISSUE_28_DIR / "invariant_profile.json")
        self.assertTrue(profile["invariants"])
        self.assertTrue(
            all(
                set(entry) == {"decision_id", "invariant_id"}
                for entry in profile["invariants"]
            )
        )
        profile_text = json.dumps(profile, sort_keys=True)
        for forbidden in (
            "expression",
            "json_path",
            "maximum_provider_calls",
            "metric_ids",
            "required_predecessor",
        ):
            self.assertNotIn(forbidden, profile_text)

    def test_profile_dispatch_is_generation_driven_not_issue_branch(self) -> None:
        """Load a later revision through a retained engine, not an Issue branch."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            later = evolve_to_v2(snapshot=issue28)
            loaded = load_requirement_snapshot(snapshot_dir=later)
            self.assertEqual("issue_28_v2", loaded["requirement_id"])
            self.assertEqual("PROFILE_DRIVEN_V2", loaded["requirement_generation"])

    def test_contract_byte_drift_fails_closed(self) -> None:
        """Reject one changed snapshot byte before semantic evaluation."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            with (issue28 / "CONTRACT.md").open(mode="ab") as file_obj:
                file_obj.write(b"\n")
            with self.assertRaisesRegex(RequirementError, "bytes differ"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_extra_snapshot_file_fails_closed(self) -> None:
        """Reject a structurally valid but unbound sixth file."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            (issue28 / "extra.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RequirementError, "file set"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_snapshot_symlink_fails_closed(self) -> None:
        """Reject a child file that redirects outside the five-file snapshot."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            contract_path = issue28 / "CONTRACT.md"
            contract_path.unlink()
            contract_path.symlink_to(ISSUE_28_DIR / "CONTRACT.md")
            with self.assertRaisesRegex(RequirementError, "file set"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_parent_snapshot_symlink_fails_closed(self) -> None:
        """Reject a redirected parent directory before historical dispatch."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            parent_dir = issue28.parent / "issue_15_v1"
            shutil.rmtree(parent_dir)
            parent_dir.symlink_to(ISSUE_15_DIR, target_is_directory=True)
            with self.assertRaisesRegex(RequirementError, "directory is unsafe"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_parent_closure_drift_fails_after_child_rebinding(self) -> None:
        """Reject a coordinated fake parent hash in baseline and transfer."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            baseline_path = issue28 / "baseline_manifest.json"
            baseline = strict_json_file(path=baseline_path)
            baseline["parent"]["requirement_closure_hash"] = "sha256:" + "0" * 64
            atomic_write_json(path=baseline_path, value=baseline)
            transfer_path = issue28 / "transfer_manifest.json"
            transfer = strict_json_file(path=transfer_path)
            transfer["parent_requirement_closure_hash"] = "sha256:" + "0" * 64
            atomic_write_json(path=transfer_path, value=transfer)
            _rebind_snapshot_file(issue28=issue28, relative="transfer_manifest.json")
            with self.assertRaisesRegex(RequirementError, "Parent Requirement"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_decision_fork_fails_after_outer_rebinding(self) -> None:
        """Reject two otherwise valid children of one Decision root."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            register_path = issue28 / "decision_register.json"
            register = strict_json_file(path=register_path)
            root = register["decisions"][0]
            parent_hash = content_hash(value=root)
            first = copy.deepcopy(root)
            first["evidence"] += "#fork-a"
            first["supersedes_decision_id"] = parent_hash
            second = copy.deepcopy(root)
            second["evidence"] += "#fork-b"
            second["supersedes_decision_id"] = parent_hash
            register["decisions"].extend([first, second])
            atomic_write_json(path=register_path, value=register)
            _rebind_snapshot_file(issue28=issue28, relative="decision_register.json")
            with self.assertRaisesRegex(RequirementError, "Parallel effective"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_unknown_invariant_kind_fails_after_outer_rebinding(self) -> None:
        """Reject an attempted arbitrary rule-engine extension."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            register_path = issue28 / "decision_register.json"
            register = strict_json_file(path=register_path)
            register["decisions"][0]["choice"] = {"kind": "ARBITRARY_JSON_EXPRESSION"}
            atomic_write_json(path=register_path, value=register)
            _rebind_snapshot_file(issue28=issue28, relative="decision_register.json")
            with self.assertRaisesRegex(RequirementError, "Unknown invariant kind"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_retry_safety_fails_after_outer_rebinding(self) -> None:
        """Reject a policy-content change that enables automatic retry."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            register_path = issue28 / "decision_register.json"
            register = strict_json_file(path=register_path)
            transport = [
                row
                for row in register["decisions"]
                if row["decision_id"] == "S-TRANSPORT-RETRY"
            ][0]
            transport["choice"]["automatic_retry_count"] = 1
            atomic_write_json(path=register_path, value=register)
            _rebind_snapshot_file(issue28=issue28, relative="decision_register.json")
            with self.assertRaisesRegex(RequirementError, "retry safety"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_validator_identity_drift_fails_closed(self) -> None:
        """Bind the generic evaluator implementation used by this snapshot."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            baseline_path = issue28 / "baseline_manifest.json"
            baseline = strict_json_file(path=baseline_path)
            baseline["validator"]["sha256"] = "0" * 64
            atomic_write_json(path=baseline_path, value=baseline)
            with self.assertRaisesRegex(RequirementError, "validator identity"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_incomplete_transfer_fails_after_outer_rebinding(self) -> None:
        """Require one and only one disposition for every parent Decision."""
        with tempfile.TemporaryDirectory() as directory:
            issue28 = _copied_issue28_repository(directory=directory)
            transfer_path = issue28 / "transfer_manifest.json"
            transfer = strict_json_file(path=transfer_path)
            removed = transfer["fragments"].pop()
            transfer["fragment_classification_counts"][removed["disposition"]] -= 1
            atomic_write_json(path=transfer_path, value=transfer)
            _rebind_snapshot_file(issue28=issue28, relative="transfer_manifest.json")
            with self.assertRaisesRegex(RequirementError, "incomplete"):
                load_requirement_snapshot(snapshot_dir=issue28)

    def test_successor_artifact_identity_is_all_or_nothing(self) -> None:
        """Reject missing or forged identity for every successor artifact type."""
        requirement = load_requirement_snapshot(snapshot_dir=ISSUE_28_DIR)
        for record_type in (
            "SUCCESSOR_PUBLICATION_MANIFEST",
            "SUCCESSOR_RELEASE_PLAN",
            "SUCCESSOR_RUN",
        ):
            artifact = {
                "record_type": record_type,
                "artifact_requirement_generation": EXPLICIT_ARTIFACT_GENERATION,
                "requirement_id": requirement["requirement_id"],
                "requirement_closure_hash": requirement["requirement_closure_hash"],
                "requirement_hashes": requirement["hashes"],
            }
            self.assertEqual(
                EXPLICIT_ARTIFACT_GENERATION,
                validate_artifact_requirement_identity(
                    artifact=artifact, requirement=requirement,
                )["generation"],
            )
            for missing in (
                "requirement_id",
                "requirement_closure_hash",
                "requirement_hashes",
            ):
                tampered = dict(artifact)
                tampered.pop(missing)
                with self.subTest(record_type=record_type, missing=missing):
                    with self.assertRaises(RequirementProfileError):
                        validate_artifact_requirement_identity(
                            artifact=tampered, requirement=requirement,
                        )
            forged = dict(artifact)
            forged["requirement_closure_hash"] = "sha256:" + "0" * 64
            with self.assertRaises(RequirementProfileError):
                validate_artifact_requirement_identity(
                    artifact=forged, requirement=requirement,
                )
            forged_id = dict(artifact)
            forged_id["requirement_id"] = "issue_29_v1"
            with self.assertRaises(RequirementProfileError):
                validate_artifact_requirement_identity(
                    artifact=forged_id, requirement=requirement,
                )
            forged_hashes = dict(artifact)
            forged_hashes["requirement_hashes"] = {}
            with self.assertRaises(RequirementProfileError):
                validate_artifact_requirement_identity(
                    artifact=forged_hashes, requirement=requirement,
                )

    def test_legacy_publication_keeps_hash_only_identity(self) -> None:
        """Accept R3's historical shape but never relabel it as successor."""
        pointer = strict_json_file(
            path=REPO_ROOT / "outputs" / "active_publication.json"
        )
        manifest = strict_json_file(
            path=(
                REPO_ROOT
                / "outputs"
                / "publications"
                / pointer["publication_id"]
                / "publication_manifest.json"
            )
        )
        parent = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/ai_first_v3_3_1"
        )
        self.assertNotIn("requirement_id", manifest)
        self.assertNotIn("requirement_closure_hash", manifest)
        self.assertEqual(
            LEGACY_ARTIFACT_GENERATION,
            validate_artifact_requirement_identity(
                artifact=manifest, requirement=parent,
            )["generation"],
        )
        forged = dict(manifest)
        forged["requirement_id"] = "issue_28_v1"
        with self.assertRaises(RequirementProfileError):
            validate_artifact_requirement_identity(
                artifact=forged, requirement=parent,
            )

    def test_run_requirement_dispatch_requires_explicit_successor_identity(
        self,
    ) -> None:
        """Route new Runs by bound identity while retaining old dispatch."""
        successor = load_requirement_snapshot(snapshot_dir=ISSUE_28_DIR)
        resolved = load_run_requirement_snapshot(
            repo_root=REPO_ROOT,
            task_contract_bindings=[],
            requirement_id=successor["requirement_id"],
            requirement_closure_hash=successor["requirement_closure_hash"],
            requirement_hashes=successor["hashes"],
            record_type="SUCCESSOR_RUN",
            artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
        )
        self.assertEqual("issue_28_v1", resolved["requirement_id"])
        with self.assertRaisesRegex(RequirementError, "incomplete"):
            load_run_requirement_snapshot(
                repo_root=REPO_ROOT,
                task_contract_bindings=[],
                requirement_id="issue_28_v1",
                requirement_hashes=successor["hashes"],
                record_type="SUCCESSOR_RUN",
                artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
            )
        legacy = load_run_requirement_snapshot(
            repo_root=REPO_ROOT, task_contract_bindings=[],
        )
        self.assertEqual("ai_first_v3_3_1", legacy["requirement_id"])

    def test_create_run_binds_explicit_successor_identity(self) -> None:
        """Persist successor fields without changing the legacy RUN subtype."""
        successor = load_requirement_snapshot(snapshot_dir=ISSUE_28_DIR)
        with tempfile.TemporaryDirectory() as directory:
            manifest = create_run(
                run_dir=Path(directory) / "run",
                run_id="run:issue28:identity-test",
                company_id="test_company",
                company_traits=[],
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
                source_references=[],
                missing_required_source_roles=[],
                spec_file_hashes={"fixture": "sha256:fixture"},
                requirement_hashes=successor["hashes"],
                requirement_id=successor["requirement_id"],
                artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
                requirement_closure_hash=successor["requirement_closure_hash"],
            )
            self.assertEqual("issue_28_v1", manifest["requirement_id"])
            self.assertEqual(
                successor["requirement_closure_hash"],
                manifest["requirement_closure_hash"],
            )
            incomplete_manifest = dict(manifest)
            incomplete_manifest.pop("requirement_closure_hash")
            with self.assertRaisesRegex(RecordError, "Missing record fields"):
                validate_record(record=incomplete_manifest)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RunStoreError, "incomplete"):
                create_run(
                    run_dir=Path(directory) / "run",
                    run_id="run:issue28:missing-closure",
                    company_id="test_company",
                    company_traits=[],
                    target_period={
                        "fiscal_year": 2025,
                        "period_start": "2025-01-01",
                        "period_end": "2025-12-31",
                    },
                    source_references=[],
                    missing_required_source_roles=[],
                    spec_file_hashes={"fixture": "sha256:fixture"},
                    requirement_hashes=successor["hashes"],
                    requirement_id=successor["requirement_id"],
                    artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
                )


class Issue28HistoricalReadBackIntegrationTest(unittest.TestCase):
    """Fully reopen R3 and its R2/R1 predecessors after loader transition."""

    @classmethod
    def setUpClass(cls) -> None:
        """Pin one fully verified active R3 chain for all assertions."""
        cls.active = PublicationView.open(publication_root=REPO_ROOT)
        r2_id = str(cls.active.manifest["previous_publication_id"])
        r2_dir = REPO_ROOT / "outputs" / "publications" / r2_id
        r2_manifest = verify_publication_bundle(bundle_dir=r2_dir)
        cls.r2 = PublicationView(
            publication_id=r2_id, bundle_dir=r2_dir, manifest=r2_manifest,
        )
        r1_id = str(r2_manifest["previous_publication_id"])
        r1_dir = REPO_ROOT / "outputs" / "publications" / r1_id
        r1_manifest = verify_publication_bundle(bundle_dir=r1_dir)
        cls.r1 = PublicationView(
            publication_id=r1_id, bundle_dir=r1_dir, manifest=r1_manifest,
        )

    def test_r1_r3_historical_chain_and_root_mirrors_remain_exact(self) -> None:
        """Preserve R3 active, exact R2, R1 availability and 14 mirrors."""
        self.assertEqual(ACTIVE_R3, self.active.publication_id)
        self.assertEqual(EXACT_R2, self.r2.publication_id)
        self.assertEqual(
            self.r2.publication_id, self.active.manifest["previous_publication_id"]
        )
        self.assertEqual(
            self.r1.publication_id, self.r2.manifest["previous_publication_id"]
        )
        r3_index = strict_json_file(
            path=REPO_ROOT / "outputs/ratchet_release_receipts/r3/index.json"
        )
        self.assertEqual("PASSED", r3_index["status"])
        for relative, root_relative in ROOT_MIRROR_RELATIVE_PATHS.items():
            self.assertEqual(
                self.active.read_bytes(relative_path=relative),
                (REPO_ROOT / root_relative).read_bytes(),
            )
        parent = load_requirement_snapshot(snapshot_dir=ISSUE_15_DIR)
        self.assertEqual(ISSUE_15_CLOSURE, parent["requirement_closure_hash"])


if __name__ == "__main__":
    unittest.main()
