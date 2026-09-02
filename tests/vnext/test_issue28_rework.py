"""PR #29 authority regressions using rebound snapshots and full artifacts."""

import copy
import itertools
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.issue28_fixture_support import copy_profile_repository
from tests.vnext.issue28_fixture_support import evolve_to_v2, rebind_scoped_parent
from tests.vnext.issue28_fixture_support import refresh_snapshot
from tests.vnext.test_publication import publication_inputs
from tests.vnext.test_replay import create_structured_b01_run
from vnext.canonical import (
    atomic_write_json,
    content_hash,
    sha256_bytes,
    strict_json_file,
)
from vnext.publication import (
    PublicationError,
    PublicationView,
    ROOT_MIRROR_RELATIVE_PATHS,
)
from vnext.publication import prepare_publication_bundle, verify_publication_bundle
from vnext.publication import _commit_recorded_sandbox_publication
from vnext.requirement_profile import (
    EXPLICIT_ARTIFACT_GENERATION,
    LEGACY_ARTIFACT_GENERATION,
)
from vnext.requirement_profile import validate_artifact_requirement_identity
from vnext.requirement_profile import (
    validate_execution_authority,
    validate_transition_activation_receipt,
)
from vnext.requirement_profile_v1 import RequirementProfileError, choice_fragments
from vnext.requirements import (
    RequirementError,
    load_requirement_snapshot,
    load_run_requirement_snapshot,
)
from vnext.run_store import RunStoreError, append_run_record, create_run
from vnext.run_store import load_frozen_run, load_open_run, validate_and_freeze_run
from vnext.replay import replay_frozen_results
from vnext.source_strategy import SourceStrategyError, build_successor_release_plan
from vnext.source_strategy import (
    load_release_plan_artifact,
    write_successor_release_plan,
)


IDENTITY_FIELDS = ("requirement_id", "requirement_closure_hash", "requirement_hashes")
SNAPSHOT = REPO_ROOT / "requirements/issue_28_v1"


def missing_identities(artifact):
    for size in (1, 2, 3):
        for missing in itertools.combinations(IDENTITY_FIELDS, size):
            changed = copy.deepcopy(artifact)
            for field in missing:
                changed.pop(field)
            yield missing, changed
    changed = copy.deepcopy(artifact)
    changed.pop("artifact_requirement_generation")
    yield ("artifact_requirement_generation",), changed


def successor_run(*, root: Path, requirement: dict) -> Path:
    """Build new full recorded data through the production Run constructor."""
    legacy = root / "deterministic_source_fixture"
    create_structured_b01_run(run_dir=legacy, forged_value=None)
    old, records, decisions = load_open_run(run_dir=legacy)
    assert not decisions
    destination = root / "successor_run"
    create_run(
        run_dir=destination,
        run_id="run:successor:identity-round-trip",
        company_id=old["company_id"],
        company_traits=old["company_traits"],
        target_period=old["target_period"],
        source_references=old["source_references"],
        missing_required_source_roles=old["missing_required_source_roles"],
        spec_file_hashes=old["spec_file_hashes"],
        artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
        requirement_id=requirement["requirement_id"],
        requirement_closure_hash=requirement["requirement_closure_hash"],
        requirement_hashes=requirement["hashes"],
    )
    for record in records:
        append_run_record(run_dir=destination, record=record)
    validate_and_freeze_run(run_dir=destination, repo_root=REPO_ROOT)
    return destination


class Issue28SemanticReworkTest(unittest.TestCase):
    def test_coordinated_positive_expansion_and_selector_removal_fail(self):
        for mode in ("extra_positive", "selector_removed"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                snapshot = copy_profile_repository(directory=directory)
                path = snapshot / "decision_register.json"
                register = strict_json_file(path=path)
                for row in register["decisions"]:
                    if (
                        mode == "selector_removed"
                        and row["decision_id"] == "S-SOURCE-SCOPE"
                    ):
                        row["choice"]["forbidden_selector_classes"].remove(
                            "AI_SELECTOR"
                        )
                    if mode == "extra_positive" and row["decision_id"] in (
                        "S-SOURCE-SCOPE",
                        "S-LIVE-CALL-BOUND",
                    ):
                        row["choice"]["positive_fixture_classes"].append(
                            "RESEARCH_ONLY"
                        )
                        row["choice"]["positive_fixture_classes"].sort()
                atomic_write_json(path=path, value=register)
                refresh_snapshot(snapshot=snapshot)
                with self.assertRaises(RequirementError):
                    load_requirement_snapshot(snapshot_dir=snapshot)

    def test_provider_change_requires_and_accepts_an_exact_owner_policy_tip(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = copy_profile_repository(directory=directory)
            register_path = snapshot / "decision_register.json"
            register = strict_json_file(path=register_path)
            root = next(
                d
                for d in register["decisions"]
                if d["decision_id"] == "S-PROVIDER-TRANSPORT"
            )
            tip = copy.deepcopy(root)
            tip["choice"]["model"] = "TEST_ONLY_EXPLICIT_OWNER_MODEL"
            tip["supersedes_decision_id"] = content_hash(value=root)
            approval = {
                "record_type": "OWNER_POLICY_APPROVAL",
                "scope": "POLICY_CONTENT_ONLY",
                "decision_id": tip["decision_id"],
                "choice_hash": content_hash(value=tip["choice"]),
                "supersedes_record_hash": tip["supersedes_decision_id"],
            }
            text = json.dumps(approval, sort_keys=True)
            source = {
                "source_id": "OWNER_TEST_PROVIDER",
                "kind": "OWNER_POLICY_SUCCESSOR",
                "source_url": "https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-9999999999",
                "source_sha256": sha256_bytes(content=text.encode()),
                "text": text,
                "author": "test-only:owner",
                "published_at_utc": "2026-09-03T00:00:00Z",
            }
            tip.update(
                approved_by=source["author"],
                approved_at_utc=source["published_at_utc"],
                evidence=source["source_url"],
                policy_provenance={
                    "source_id": source["source_id"],
                    "section": "POLICY_CONTENT_ONLY",
                    "scope": "POLICY_CONTENT_ONLY",
                },
            )
            register["decisions"].append(tip)
            atomic_write_json(path=register_path, value=register)
            baseline_path = snapshot / "baseline_manifest.json"
            baseline = strict_json_file(path=baseline_path)
            baseline["policy_evidence"].append(source)
            baseline["policy_evidence"].sort(key=lambda item: item["source_id"])
            atomic_write_json(path=baseline_path, value=baseline)
            transfer_path = snapshot / "transfer_manifest.json"
            transfer = strict_json_file(path=transfer_path)
            row = next(
                r
                for r in transfer["fragments"]
                if r["decision_id"] == "D-01" and r["source_path"] == "/model"
            )
            row.update(
                disposition="SUPERSEDED",
                transfer_mode="REPLACED_POLICY",
                rationale="TEST_ONLY explicit owner policy successor",
            )
            transfer["fragment_classification_counts"]["CARRY_FORWARD"] -= 1
            transfer["fragment_classification_counts"]["SUPERSEDED"] += 1
            atomic_write_json(path=transfer_path, value=transfer)
            refresh_snapshot(snapshot=snapshot)
            loaded = load_requirement_snapshot(snapshot_dir=snapshot)
            self.assertEqual("NOT_ACTIVATED", loaded["activation_state"])
            self.assertEqual(tip, loaded["effective_decisions"][tip["decision_id"]])

    def test_rebound_policy_mutations_fail_semantic_bounds(self):
        mutations = [
            ("R4 set", "S-R4-SCOPE", lambda c: c["metric_ids"].pop()),
            (
                "hard 25",
                "S-LIVE-CALL-BOUND",
                lambda c: c.update(hard_maximum_provider_calls=25),
            ),
            (
                "target 11",
                "S-LIVE-CALL-BOUND",
                lambda c: c.update(target_minimum_provider_calls=11),
            ),
            (
                "target 19",
                "S-LIVE-CALL-BOUND",
                lambda c: c.update(target_maximum_provider_calls=19),
            ),
            (
                "zero class",
                "S-LIVE-CALL-BOUND",
                lambda c: c["zero_call_fixture_classes"].pop(),
            ),
            (
                "context",
                "S-TRANSPORT-RETRY",
                lambda c: c.update(context_ceiling_tokens=200001),
            ),
            (
                "performance",
                "S-SESSION-RESOURCE",
                lambda c: c.update(minimum_wall_time_improvement_factor=9),
            ),
            (
                "provider",
                "S-PROVIDER-TRANSPORT",
                lambda c: c.update(provider="unapproved_provider"),
            ),
            (
                "model",
                "S-PROVIDER-TRANSPORT",
                lambda c: c.update(model="unapproved_model"),
            ),
            ("api", "S-PROVIDER-TRANSPORT", lambda c: c.update(api="unapproved_api")),
            (
                "region claim",
                "S-PROVIDER-TRANSPORT",
                lambda c: c.update(region="guaranteed_residency"),
            ),
            (
                "retention claim",
                "S-PROVIDER-TRANSPORT",
                lambda c: c.update(retention="zero_retention"),
            ),
            (
                "fast command",
                "S-TEST-POLICY",
                lambda c: c.update(required_fast_command="true"),
            ),
            (
                "fast timeout",
                "S-TEST-POLICY",
                lambda c: c.update(per_case_timeout_seconds=31),
            ),
            ("fast tier", "S-TEST-POLICY", lambda c: c.update(evidence_tier="FULL")),
            (
                "recorded timeout",
                "S-TEST-POLICY",
                lambda c: c.update(recorded_gate_timeout_seconds=61),
            ),
            (
                "fast class",
                "S-TEST-POLICY",
                lambda c: c["prohibited_required_test_classes"].pop(),
            ),
            (
                "fast invariant",
                "S-TEST-POLICY",
                lambda c: c["required_short_deterministic_invariants"].pop(),
            ),
            (
                "sandbox claim",
                "S-SECURITY-BOUNDARY",
                lambda c: c.update(same_process_strong_sandbox_claim=True),
            ),
        ]
        for label, decision_id, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                snapshot = copy_profile_repository(directory=directory)
                path = snapshot / "decision_register.json"
                register = strict_json_file(path=path)
                mutate(
                    next(
                        d["choice"]
                        for d in register["decisions"]
                        if d["decision_id"] == decision_id
                    )
                )
                atomic_write_json(path=path, value=register)
                refresh_snapshot(snapshot=snapshot)
                with self.assertRaises(RequirementError):
                    load_requirement_snapshot(snapshot_dir=snapshot)

    def test_every_source_scope_binding_is_required(self):
        for field in (
            "source_sha256",
            "full_derived_asset_id",
            "task_contract_hash",
            "ordered_table_ids",
            "ordered_grid_hashes",
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                snapshot = copy_profile_repository(directory=directory)
                path = snapshot / "decision_register.json"
                register = strict_json_file(path=path)
                choice = next(
                    d["choice"]
                    for d in register["decisions"]
                    if d["decision_id"] == "S-SOURCE-SCOPE"
                )
                choice["required_manifest_binding_fields"].remove(field)
                atomic_write_json(path=path, value=register)
                refresh_snapshot(snapshot=snapshot)
                with self.assertRaises(RequirementError):
                    load_requirement_snapshot(snapshot_dir=snapshot)

    def test_test_policy_cannot_be_deleted_with_its_profile_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = copy_profile_repository(directory=directory)
            for name, key in (
                ("decision_register.json", "decisions"),
                ("invariant_profile.json", "invariants"),
            ):
                path = snapshot / name
                value = strict_json_file(path=path)
                value[key] = [
                    d for d in value[key] if d["decision_id"] != "S-TEST-POLICY"
                ]
                atomic_write_json(path=path, value=value)
            refresh_snapshot(snapshot=snapshot)
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=snapshot)

    def test_transfer_covers_every_leaf_once_and_preserves_critical_kinds(self):
        requirement = load_requirement_snapshot(snapshot_dir=SNAPSHOT)
        parent = requirement["parent_snapshot"]
        expected = {
            (did, path)
            for did, d in parent["effective_decisions"].items()
            for path in choice_fragments(value=d["choice"])
        }
        rows = requirement["transfer"]["fragments"]
        actual = [(r["decision_id"], r["source_path"]) for r in rows]
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(expected, set(actual))
        for did, target in (
            ("D-01", "S-PROVIDER-TRANSPORT"),
            ("D-24", "S-SECURITY-BOUNDARY"),
            ("D-26", "S-TEST-POLICY"),
        ):
            self.assertTrue(
                all(
                    r["successor_decision_id"] == target
                    for r in rows
                    if r["decision_id"] == did
                )
            )

    def test_same_boolean_cannot_disguise_a_security_obligation(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = copy_profile_repository(directory=directory)
            path = snapshot / "transfer_manifest.json"
            transfer = strict_json_file(path=path)
            row = next(
                r
                for r in transfer["fragments"]
                if r["decision_id"] == "D-24"
                and r["source_path"] == "/same_process_strong_sandbox_claim"
            )
            row.update(
                successor_decision_id="S-ARTIFACT-IDENTITY",
                successor_path="/successor_missing_identity_allowed",
            )
            atomic_write_json(path=path, value=transfer)
            refresh_snapshot(snapshot=snapshot)
            with self.assertRaisesRegex(RequirementError, "misclassified"):
                load_requirement_snapshot(snapshot_dir=snapshot)

    def test_identifier_comment_is_not_policy_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = copy_profile_repository(directory=directory)
            path = snapshot / "decision_register.json"
            register = strict_json_file(path=path)
            baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
            register["decisions"][0]["evidence"] = baseline["issue"][
                "identifier_comment_url"
            ]
            register["decisions"][0]["approved_at_utc"] = "2026-09-02T11:32:30Z"
            atomic_write_json(path=path, value=register)
            refresh_snapshot(snapshot=snapshot)
            with self.assertRaisesRegex(RequirementError, "provenance"):
                load_requirement_snapshot(snapshot_dir=snapshot)

    def test_activation_is_separate_exact_head_and_not_a_live_grant(self):
        requirement = load_requirement_snapshot(snapshot_dir=SNAPSHOT)
        self.assertEqual("NOT_ACTIVATED", requirement["activation_state"])
        body = {
            "record_type": "REQUIREMENT_TRANSITION_ACTIVATION",
            "schema_version": 1,
            "requirement_id": requirement["requirement_id"],
            "requirement_closure_hash": requirement["requirement_closure_hash"],
            "exact_head": "a" * 40,
            "authorization_scope": "TRANSITION_ONLY",
            "provider_paid_sec_authorized": False,
            "approval_kind": "EXACT_HEAD_TRANSITION_APPROVAL",
            "owner": "github:wlvh",
            "approved_at_utc": "2026-09-03T00:00:00Z",
            "source_url": "https://github.com/wlvh/SEC_metrics/pull/29#issuecomment-9999999999",
        }
        approval_text = json.dumps(
            {
                "decision": "APPROVE_REQUIREMENT_TRANSITION",
                "exact_head": "a" * 40,
                "requirement_id": requirement["requirement_id"],
                "requirement_closure_hash": requirement["requirement_closure_hash"],
                "scope": "TRANSITION_ONLY",
                "provider_paid_sec_authorized": False,
            },
            sort_keys=True,
        )
        body.update(
            approval_text=approval_text,
            approval_text_sha256=sha256_bytes(content=approval_text.encode()),
        )
        receipt = {**body, "receipt_id": content_hash(value=body)}
        self.assertEqual(
            receipt,
            validate_transition_activation_receipt(
                receipt=receipt, requirement=requirement, exact_head="a" * 40
            ),
        )
        for field, value in (
            ("exact_head", "b" * 40),
            ("provider_paid_sec_authorized", True),
            ("source_url", requirement["baseline"]["issue"]["identifier_comment_url"]),
            ("approval_kind", "IDENTIFIER_RESOLUTION"),
            ("approval_text", "identifier resolution only"),
        ):
            changed = {**body, field: value}
            with self.subTest(field=field), self.assertRaises(RequirementProfileError):
                validate_transition_activation_receipt(
                    receipt={**changed, "receipt_id": content_hash(value=changed)},
                    requirement=requirement,
                    exact_head="a" * 40,
                )


class Issue28ArtifactReworkTest(unittest.TestCase):
    def test_real_successor_run_freeze_replay_and_identity_removal(self):
        requirement = load_requirement_snapshot(snapshot_dir=SNAPSHOT)
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "socket.socket", side_effect=AssertionError("NO_NETWORK")
        ):
            run = successor_run(root=Path(directory), requirement=requirement)
            manifest, records, _ = load_frozen_run(run_dir=run, repo_root=REPO_ROOT)
            self.assertEqual("SUCCESSOR_RUN", manifest["record_type"])
            self.assertEqual(
                EXPLICIT_ARTIFACT_GENERATION,
                manifest["artifact_requirement_generation"],
            )
            self.assertTrue(
                replay_frozen_results(run_dir=run, repo_root=REPO_ROOT)["results"]
            )
            for missing, changed in missing_identities(manifest):
                with self.subTest(missing=missing):
                    atomic_write_json(path=run / "manifest.json", value=changed)
                    with self.assertRaises(RunStoreError):
                        load_frozen_run(run_dir=run, repo_root=REPO_ROOT)
            atomic_write_json(path=run / "manifest.json", value=manifest)
            self.assertEqual(
                manifest, load_frozen_run(run_dir=run, repo_root=REPO_ROOT)[0]
            )

    def test_real_successor_release_plan_roundtrip_and_identity_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = copy_profile_repository(directory=directory)
            root = snapshot.parent.parent
            plan = build_successor_release_plan(
                repo_root=root,
                requirement_id="issue_28_v1",
                release_plan_id="test_successor_r4",
                release_stage="R4",
                parent_release_plan_id="issue_15_lodging_r3",
                reader_family_versions={"financial_statement": "TEST_ONLY_SCHEMA_V1"},
            )
            self.assertEqual(
                plan, write_successor_release_plan(repo_root=root, plan=plan)
            )
            path = root / "config/release_plans/test_successor_r4.json"
            for missing, changed in missing_identities(plan):
                with self.subTest(missing=missing):
                    atomic_write_json(path=path, value=changed)
                    with self.assertRaises((SourceStrategyError, RequirementError)):
                        load_release_plan_artifact(
                            repo_root=root, release_plan_id="test_successor_r4"
                        )
            atomic_write_json(path=path, value=plan)
            self.assertEqual(
                plan,
                load_release_plan_artifact(
                    repo_root=root, release_plan_id="test_successor_r4"
                ),
            )
            evolve_to_v2(snapshot=snapshot)
            self.assertEqual(
                plan["requirement_closure_hash"],
                load_release_plan_artifact(
                    repo_root=root, release_plan_id="test_successor_r4"
                )["requirement_closure_hash"],
            )

    def test_all_existing_issue15_release_plans_keep_legacy_schema(self):
        for path in sorted(
            (REPO_ROOT / "config/release_plans").glob("issue_15_*.json")
        ):
            with self.subTest(path=path.name):
                expected = strict_json_file(path=path)
                loaded = load_release_plan_artifact(
                    repo_root=REPO_ROOT, release_plan_id=expected["release_plan_id"]
                )
                self.assertEqual(expected, loaded)
                self.assertEqual("ISSUE_15_RELEASE_PLAN", loaded["record_type"])
                self.assertIn("requirement_id", loaded)
                self.assertIn("requirement_closure_hash", loaded)
                self.assertNotIn("artifact_requirement_generation", loaded)

    def test_real_r3_manifest_rejects_wrong_requirement_and_bogus_hashes(self):
        pointer = strict_json_file(path=REPO_ROOT / "outputs/active_publication.json")
        manifest = strict_json_file(
            path=REPO_ROOT
            / "outputs/publications"
            / pointer["publication_id"]
            / "publication_manifest.json"
        )
        correct = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/ai_first_v3_3_1"
        )
        wrong = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_15_v1"
        )
        self.assertEqual(
            LEGACY_ARTIFACT_GENERATION,
            validate_artifact_requirement_identity(
                artifact=manifest, requirement=correct
            )["generation"],
        )
        with self.assertRaises(RequirementProfileError):
            validate_artifact_requirement_identity(artifact=manifest, requirement=wrong)
        with self.assertRaises(RequirementProfileError):
            validate_artifact_requirement_identity(
                artifact={**manifest, "requirement_hashes": {"bogus": "x"}},
                requirement=correct,
            )

    def test_version_evolution_preserves_old_closure_and_resolves_pending_r5(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = copy_profile_repository(directory=directory)
            root = snapshot.parent.parent
            old = load_requirement_snapshot(snapshot_dir=snapshot)
            run = successor_run(root=Path(directory) / "full_run", requirement=old)
            run_manifest, run_records, _ = load_frozen_run(
                run_dir=run, repo_root=REPO_ROOT
            )
            authority_paths = set(run_manifest["spec_file_hashes"])
            authority_paths.update(
                record["storage_uri"]
                for record in run_records
                if record["record_type"] == "RAW_BLOB"
            )
            for relative in authority_paths:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / relative, destination)
            v1_bytes = {p.name: p.read_bytes() for p in snapshot.iterdir()}
            v2 = evolve_to_v2(snapshot=snapshot)
            new = load_requirement_snapshot(snapshot_dir=v2)
            self.assertEqual("PROFILE_DRIVEN_V2", new["requirement_generation"])
            self.assertEqual([], new["pending_decision_ids"])
            scopes = [
                v
                for v in new["evaluated_invariants"]["by_invariant_id"].values()
                if v["kind"] == "RATCHET_SCOPE"
            ]
            self.assertEqual({"R4", "R5"}, {v["value"]["ratchet_id"] for v in scopes})
            for kind in (
                "RATCHET_SCOPE",
                "LIVE_CALL_BOUND",
                "PUBLICATION_PREDECESSOR",
                "SOURCE_SCOPE_POLICY",
            ):
                rows = [
                    row
                    for row in new["evaluated_invariants"]["by_invariant_id"].values()
                    if row["kind"] == kind
                ]
                self.assertEqual(
                    {"R4", "R5"}, {row["value"]["ratchet_id"] for row in rows}
                )
            self.assertEqual(
                v1_bytes, {p.name: p.read_bytes() for p in snapshot.iterdir()}
            )
            self.assertEqual(
                old["requirement_closure_hash"],
                load_requirement_snapshot(snapshot_dir=snapshot)[
                    "requirement_closure_hash"
                ],
            )
            resolved = load_run_requirement_snapshot(
                repo_root=root,
                task_contract_bindings=[],
                record_type="SUCCESSOR_RUN",
                artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
                requirement_id=old["requirement_id"],
                requirement_closure_hash=old["requirement_closure_hash"],
                requirement_hashes=old["hashes"],
            )
            self.assertEqual(
                old["requirement_closure_hash"], resolved["requirement_closure_hash"]
            )
            self.assertEqual(
                run_manifest, load_frozen_run(run_dir=run, repo_root=root)[0]
            )
            self.assertTrue(
                replay_frozen_results(run_dir=run, repo_root=root)["results"]
            )


class Issue28PublicationReworkTest(unittest.TestCase):
    def test_real_successor_publication_roundtrip_and_identity_removal(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "socket.socket", side_effect=AssertionError("NO_NETWORK")
        ):
            root = Path(directory)
            inputs = publication_inputs(
                root=root, tag="successor-authority", previous_publication_id=None
            )
            snapshot = rebind_scoped_parent(repo_root=inputs["repo_root"])
            requirement = load_requirement_snapshot(snapshot_dir=snapshot)
            manifest = prepare_publication_bundle(
                publication_root=root / "publication",
                **inputs,
                artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
                publication_requirement_id="issue_28_v1",
            )
            bundle = (
                root / "publication/outputs/publications" / manifest["publication_id"]
            )
            self.assertEqual("SUCCESSOR_PUBLICATION_MANIFEST", manifest["record_type"])
            self.assertEqual(
                requirement["requirement_closure_hash"],
                manifest["requirement_closure_hash"],
            )
            self.assertEqual(manifest, verify_publication_bundle(bundle_dir=bundle))
            _commit_recorded_sandbox_publication(
                publication_root=root / "publication",
                publication_id=manifest["publication_id"],
                expected_active_publication_id=None,
                committed_at_utc="2026-09-03T00:00:00Z",
            )
            pinned = PublicationView.open(publication_root=root / "publication")
            self.assertEqual(manifest["publication_id"], pinned.publication_id)
            for relative, mirror in ROOT_MIRROR_RELATIVE_PATHS.items():
                self.assertEqual(
                    pinned.read_bytes(relative_path=relative),
                    (root / "publication" / mirror).read_bytes(),
                )
            for missing, changed in missing_identities(manifest):
                with self.subTest(missing=missing):
                    atomic_write_json(
                        path=bundle / "publication_manifest.json", value=changed
                    )
                    with self.assertRaises(PublicationError):
                        verify_publication_bundle(bundle_dir=bundle)
            atomic_write_json(path=bundle / "publication_manifest.json", value=manifest)
            evolve_to_v2(snapshot=snapshot)
            self.assertEqual(manifest, verify_publication_bundle(bundle_dir=bundle))
            self.assertEqual(
                requirement["requirement_closure_hash"],
                load_requirement_snapshot(
                    snapshot_dir=bundle / "internal/authority/requirements/issue_28_v1"
                )["requirement_closure_hash"],
            )


class Issue28RootIndependenceIntegrationTest(unittest.TestCase):
    def test_future_root_drift_preserves_r1_r3_and_parent_but_not_current_execution(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = copy_profile_repository(directory=directory)
            root = snapshot.parent.parent
            baseline = load_requirement_snapshot(snapshot_dir=snapshot)
            for relative in (
                "outputs/publications",
                "outputs/publication_switch_receipts",
            ):
                shutil.copytree(REPO_ROOT / relative, root / relative)
            shutil.copy2(
                REPO_ROOT / "outputs/active_publication.json",
                root / "outputs/active_publication.json",
            )
            (root / "outputs/active_publication.json.lock").touch()
            for relative in ROOT_MIRROR_RELATIVE_PATHS.values():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / relative, path)
            changed = root / "catalog/event_routes.json"
            changed.write_bytes(changed.read_bytes() + b"\n")
            with mock.patch(
                "vnext.requirements._load_issue_15_snapshot",
                side_effect=AssertionError("NO_LIVE_PARENT_ADAPTER"),
            ):
                current = load_requirement_snapshot(snapshot_dir=snapshot)
            self.assertEqual(
                baseline["parent_requirement_closure_hash"],
                current["parent_requirement_closure_hash"],
            )
            self.assertEqual(
                baseline["requirement_closure_hash"],
                current["requirement_closure_hash"],
            )
            with self.assertRaises(RequirementProfileError):
                validate_execution_authority(repo_root=root, requirement=current)
            view = PublicationView.open(publication_root=root)
            self.assertEqual(
                baseline["baseline"]["active_publication"]["publication_id"],
                view.publication_id,
            )
            r2 = verify_publication_bundle(
                bundle_dir=root
                / "outputs/publications"
                / view.manifest["previous_publication_id"]
            )
            verify_publication_bundle(
                bundle_dir=root / "outputs/publications" / r2["previous_publication_id"]
            )
            for relative, root_relative in ROOT_MIRROR_RELATIVE_PATHS.items():
                self.assertEqual(
                    view.read_bytes(relative_path=relative),
                    (root / root_relative).read_bytes(),
                )
            revision = evolve_to_v2(snapshot=snapshot)
            successor = load_requirement_snapshot(snapshot_dir=revision)
            validate_execution_authority(repo_root=root, requirement=successor)


if __name__ == "__main__":
    unittest.main()
