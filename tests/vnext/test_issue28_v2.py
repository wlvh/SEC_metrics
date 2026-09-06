"""Real v2 snapshot, rebound policy negatives and historical compatibility."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from vnext.canonical import atomic_write_json, content_hash, sha256_bytes, sha256_file, strict_json_file
from vnext.requirements import RequirementError, load_requirement_snapshot
from vnext.requirement_profile import RequirementProfileError, validate_execution_authority
from vnext.requirement_profile_v1 import choice_fragments, decision_record_hash
from vnext.run_store import RunStoreError, load_frozen_run
from vnext.replay import replay_frozen_results
from vnext.source_strategy import build_successor_release_plan, load_release_plan_artifact, write_successor_release_plan

SNAPSHOT = REPO_ROOT / "requirements/issue_28_v2"
PARENT_CLOSURE = "sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac"


def clone_authority(directory: str) -> Path:
    """Copy real snapshots/bound inputs only, without Runs or SEC bodies."""
    root = Path(directory) / "repo"
    for name in ("ai_first_v3_3_1", "issue_15_v1", "issue_28_v1", "issue_28_v2"):
        shutil.copytree(REPO_ROOT / "requirements" / name, root / "requirements" / name)
    baseline = strict_json_file(path=SNAPSHOT / "baseline_manifest.json")
    paths = set(baseline["execution_authority"]["files"])
    paths.update(("scripts/vnext/requirement_profile_v1.py", "scripts/vnext/requirement_profile_v2.py",
                  "scripts/vnext/requirement_profile_v3.py", "config/issue_15_release_plan.json"))
    paths.update(p.relative_to(REPO_ROOT).as_posix() for p in (REPO_ROOT / "config/release_plans").glob("issue_15_*.json"))
    foundation = strict_json_file(path=REPO_ROOT / "requirements/issue_15_v1/foundation_verification_receipt.json")
    paths.update(row["path"] for row in foundation["receipt_bindings"])
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    return root / "requirements/issue_28_v2"


def refresh(snapshot: Path, baseline: dict | None = None) -> None:
    """Rebind only a disposable candidate's outer snapshot hashes."""
    if baseline is None:
        baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
    for name in baseline["snapshot_files"]:
        path = snapshot / name
        baseline["snapshot_files"][name] = {"sha256": sha256_file(path=path), "size": path.stat().st_size}
    atomic_write_json(path=snapshot / "baseline_manifest.json", value=baseline)


def rebound_owner_choice(snapshot: Path, decision_id: str, mutate) -> None:
    """Even re-signed outer/comment copies must obey immutable engine bounds."""
    register = strict_json_file(path=snapshot / "decision_register.json")
    decision = next(d for d in reversed(register["decisions"]) if d["decision_id"] == decision_id)
    mutate(decision["choice"])
    baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
    provenance = decision["policy_provenance"]
    source = next(s for s in baseline["policy_evidence"] if s["source_id"] == provenance["source_id"])
    policy = json.loads(source["text"])
    value = {k: v for k, v in decision["choice"].items() if k != "kind"}
    if provenance["section"] == "a03_alternate_period_policy":
        value.pop("metric_id")
    policy[provenance["section"]] = value
    source["text"] = json.dumps(policy, indent=2)
    source["source_sha256"] = sha256_bytes(content=source["text"].encode())
    capture_path = snapshot.parent.parent / source["evidence_path"]
    capture = strict_json_file(path=capture_path)
    capture.update(raw_body=source["text"], body_sha256=source["source_sha256"])
    atomic_write_json(path=capture_path, value=capture)
    baseline["execution_authority"]["files"][source["evidence_path"]] = {
        "sha256": sha256_file(path=capture_path), "size": capture_path.stat().st_size}
    atomic_write_json(path=snapshot / "decision_register.json", value=register)
    refresh(snapshot, baseline)


class Issue28V2FastTest(unittest.TestCase):
    def test_real_five_file_revision_has_exact_parent_and_no_activation(self):
        requirement = load_requirement_snapshot(snapshot_dir=SNAPSHOT)
        self.assertEqual("issue_28_v2", requirement["requirement_id"])
        self.assertEqual("PROFILE_DRIVEN_V3", requirement["requirement_generation"])
        self.assertEqual(PARENT_CLOSURE, requirement["parent_requirement_closure_hash"])
        self.assertEqual("NOT_ACTIVATED", requirement["activation_state"])
        self.assertEqual(["S-R5-B06-B13-MEANING"], requirement["pending_decision_ids"])
        self.assertEqual(5, len(list(SNAPSHOT.iterdir())))
        self.assertEqual({"CARRY_FORWARD": 619, "SUPERSEDED": 3, "HISTORICAL_ONLY": 0},
                         requirement["transfer"]["fragment_classification_counts"])


class Issue28V2PolicyTest(unittest.TestCase):
    def test_rebound_new_policy_safety_mutations_are_rejected(self):
        mutations = [
            ("A12 dims", "S-A12-COMPOSITE-SCOPE", lambda c: c["scope_dimensions_allowed_from_text_span"].pop()),
            ("A12 scale", "S-A12-COMPOSITE-SCOPE", lambda c: c.update(amount_scale_locator="NARRATIVE")),
            ("cross source", "S-A12-COMPOSITE-SCOPE", lambda c: c.update(cross_source_scope_evidence_allowed=True)),
            ("payload", "S-A12-COMPOSITE-SCOPE", lambda c: c.update(provider_payload_remains_table_window_only=False)),
            ("conflict", "S-A12-COMPOSITE-SCOPE", lambda c: c["text_span_requirements"].update(conflicting_scope_blocks_auto_certification=False)),
            ("span", "S-A03-COMPOSITE-SCOPE", lambda c: c["text_span_requirements"].update(exact_byte_offsets_and_span_sha256=False)),
            ("fuzzy", "S-A03-COMPOSITE-SCOPE", lambda c: c.update(ai_or_fuzzy_span_selection_allowed=True)),
            ("annual", "S-A03-ALTERNATE-PERIOD", lambda c: c.update(must_not_claim_annual_average=False)),
            ("production period", "S-A03-ALTERNATE-PERIOD", lambda c: c.update(fixture_class="POSITIVE_PRODUCTION")),
            ("income", "S-A13-INTERNATIONAL-NET-REVENUE", lambda c: c.update(economic_measure="NET_INCOME")),
            ("instant", "S-A13-INTERNATIONAL-NET-REVENUE", lambda c: c.update(period="INSTANT")),
            ("geo overlap", "S-A13-INTERNATIONAL-NET-REVENUE", lambda c: c["regional_sum_allowed_only_when"].update(no_parent_child_geography_overlap=False)),
            ("sum reconciliation", "S-A13-INTERNATIONAL-NET-REVENUE", lambda c: c["regional_sum_allowed_only_when"].update(reconciles_to_global_total_minus_us_total=False)),
            ("excluded measure", "S-A13-INTERNATIONAL-NET-REVENUE", lambda c: c["excluded_measure_families"].pop()),
            ("cap", "S-BOUNDED-PARSER-RESOURCE", lambda c: c.update(maximum_authorized_total_cells=250001)),
            ("override", "S-BOUNDED-PARSER-RESOURCE", lambda c: c.update(runtime_or_caller_limit_override_allowed=True)),
            ("other limits", "S-BOUNDED-PARSER-RESOURCE", lambda c: c.update(other_resource_limits_must_remain_unchanged=False)),
            ("third filing", "S-OFFLINE-FIXTURE-ACQUISITION", lambda c: c["sources"].append("third_issuer")),
            ("retry", "S-OFFLINE-FIXTURE-ACQUISITION", lambda c: c.update(automatic_retry_count=1)),
        ]
        for label, decision_id, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                rebound_owner_choice(snapshot, decision_id, mutate)
                with self.assertRaises((RequirementError, RequirementProfileError)):
                    load_requirement_snapshot(snapshot_dir=snapshot)

    def test_policy_provenance_cannot_point_to_identifier_only_comment(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
            source = next(s for s in baseline["policy_evidence"] if s["source_id"] == "OWNER_A03_POLICY")
            source["source_url"] = baseline["issue"]["identifier_comment_url"]
            refresh(snapshot, baseline)
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=snapshot)

    def test_fully_rebound_identifier_comment_is_not_policy_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
            source = next(s for s in baseline["policy_evidence"] if s["source_id"] == "OWNER_A03_POLICY")
            source["source_url"] = baseline["issue"]["identifier_comment_url"]
            capture_path = snapshot.parent.parent / source["evidence_path"]
            capture = strict_json_file(path=capture_path)
            capture["owner_comment_url"] = source["source_url"]
            atomic_write_json(path=capture_path, value=capture)
            baseline["execution_authority"]["files"][source["evidence_path"]] = {
                "sha256": sha256_file(path=capture_path), "size": capture_path.stat().st_size}
            register = strict_json_file(path=snapshot / "decision_register.json")
            for record in register["decisions"]:
                if record.get("policy_provenance", {}).get("source_id") == "OWNER_A03_POLICY":
                    record["evidence"] = source["source_url"]
            atomic_write_json(path=snapshot / "decision_register.json", value=register)
            refresh(snapshot, baseline)
            with self.assertRaisesRegex(RequirementError, "Owner comment identity differs"):
                load_requirement_snapshot(snapshot_dir=snapshot)

    def test_symlinked_requirement_container_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            container = snapshot.parent
            renamed = container.with_name("requirements-real")
            container.rename(renamed)
            container.symlink_to(renamed, target_is_directory=True)
            with self.assertRaisesRegex(RequirementError, "container/root"):
                load_requirement_snapshot(snapshot_dir=snapshot)

    def test_invented_non_effective_policy_history_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            path = snapshot / "decision_register.json"
            register = strict_json_file(path=path)
            tip = next(d for d in register["decisions"] if d["decision_id"] == "S-A03-COMPOSITE-SCOPE")
            ancestor = deepcopy(tip)
            ancestor.update(approved_by="github:intruder", supersedes_decision_id=None)
            ancestor.pop("policy_provenance")
            ancestor["choice"]["ai_or_fuzzy_span_selection_allowed"] = True
            tip["supersedes_decision_id"] = decision_record_hash(decision=ancestor)
            register["decisions"].append(ancestor)
            atomic_write_json(path=path, value=register)
            refresh(snapshot)
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=snapshot)

    def test_parent_fragment_removal_duplicate_and_false_carry_fail_after_rebind(self):
        for operation in ("remove", "duplicate", "false_carry"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                path = snapshot / "transfer_manifest.json"
                transfer = strict_json_file(path=path)
                if operation == "remove":
                    transfer["fragments"].pop()
                elif operation == "duplicate":
                    transfer["fragments"].append(deepcopy(transfer["fragments"][0]))
                else:
                    row = next(r for r in transfer["fragments"] if r["disposition"] == "SUPERSEDED")
                    row.update(disposition="CARRY_FORWARD", transfer_mode="EXACT_VALUE")
                atomic_write_json(path=path, value=transfer)
                refresh(snapshot)
                with self.assertRaises(RequirementError):
                    load_requirement_snapshot(snapshot_dir=snapshot)

    def test_extra_file_symlink_and_partial_owner_identity_fail(self):
        for operation in ("extra", "symlink", "author"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                snapshot = clone_authority(directory)
                if operation == "extra":
                    (snapshot / "unexpected.json").write_text("{}")
                elif operation == "symlink":
                    path = snapshot / "CONTRACT.md"
                    target = snapshot.parent.parent / "contract-copy.md"
                    path.rename(target); path.symlink_to(target)
                else:
                    baseline = strict_json_file(path=snapshot / "baseline_manifest.json")
                    source = next(s for s in baseline["policy_evidence"] if s["source_id"] == "OWNER_A03_POLICY")
                    source["author"] = "github:another-user"
                    refresh(snapshot, baseline)
                with self.assertRaises(RequirementError):
                    load_requirement_snapshot(snapshot_dir=snapshot)

    def test_root_drift_preserves_policy_history_but_blocks_current_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            before = load_requirement_snapshot(snapshot_dir=snapshot)
            path = snapshot.parent.parent / "catalog/company_traits.yaml"
            path.write_bytes(path.read_bytes() + b"\n")
            after = load_requirement_snapshot(snapshot_dir=snapshot)
            self.assertEqual(before["requirement_closure_hash"], after["requirement_closure_hash"])
            self.assertEqual(PARENT_CLOSURE, after["parent_requirement_closure_hash"])
            with self.assertRaises(RequirementProfileError):
                validate_execution_authority(repo_root=snapshot.parent.parent, requirement=after)


class Issue28V2ArtifactTest(unittest.TestCase):
    def test_real_v2_run_freeze_and_replay_rejects_identity_downgrade(self):
        from tests.vnext.test_issue28_rework import missing_identities, successor_run
        requirement = load_requirement_snapshot(snapshot_dir=SNAPSHOT)
        with tempfile.TemporaryDirectory() as directory, mock.patch("socket.socket", side_effect=AssertionError("NO_NETWORK")):
            run = successor_run(root=Path(directory), requirement=requirement)
            manifest = load_frozen_run(run_dir=run, repo_root=REPO_ROOT)[0]
            self.assertEqual("SUCCESSOR_RUN", manifest["record_type"])
            self.assertEqual("issue_28_v2", manifest["requirement_id"])
            self.assertTrue(replay_frozen_results(run_dir=run, repo_root=REPO_ROOT)["results"])
            for missing, changed in missing_identities(manifest):
                with self.subTest(missing=missing):
                    atomic_write_json(path=run / "manifest.json", value=changed)
                    with self.assertRaises(RunStoreError):
                        load_frozen_run(run_dir=run, repo_root=REPO_ROOT)

    def test_real_v2_six_metric_release_plan_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            root = snapshot.parent.parent
            plan = build_successor_release_plan(repo_root=root, requirement_id="issue_28_v2",
                release_plan_id="test_r4_v2", release_stage="R4", parent_release_plan_id="issue_15_lodging_r3",
                reader_family_versions={"financial_statement": "R4_OFFLINE_V2"})
            write_successor_release_plan(repo_root=root, plan=plan)
            loaded = load_release_plan_artifact(repo_root=root, release_plan_id="test_r4_v2")
            self.assertEqual(plan, loaded)
            self.assertEqual(["A03", "A04", "A09", "A11", "A12", "A13"], plan["added_metric_ids"])
            self.assertNotIn("B06", plan["cumulative_metric_ids"])
            self.assertNotIn("B13", plan["cumulative_metric_ids"])

    def test_later_same_engine_revision_keeps_old_artifact_closure(self):
        """A Requirement revision is not an engine generation or a live grant."""
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            root = snapshot.parent.parent
            parent = load_requirement_snapshot(snapshot_dir=snapshot)
            plan = build_successor_release_plan(repo_root=root, requirement_id="issue_28_v2",
                release_plan_id="test_old_r4_v2", release_stage="R4", parent_release_plan_id="issue_15_lodging_r3",
                reader_family_versions={"financial_statement": "R4_OFFLINE_V2"})
            write_successor_release_plan(repo_root=root, plan=plan)
            revision = snapshot.parent / "issue_28_v3"
            shutil.copytree(snapshot, revision)
            baseline = strict_json_file(path=revision / "baseline_manifest.json")
            bindings = {p.name: {"sha256": sha256_file(path=p), "size": p.stat().st_size}
                        for p in sorted(snapshot.iterdir())}
            # Compute the actual five-file Git tree, without writing Git objects.
            tree = b""
            for path in sorted(snapshot.iterdir()):
                raw = path.read_bytes()
                blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).digest()
                tree += b"100644 " + path.name.encode() + b"\0" + blob
            tree_id = hashlib.sha1(b"tree " + str(len(tree)).encode() + b"\0" + tree).hexdigest()
            baseline.update(requirement_id="issue_28_v3", contract_revision="ISSUE_28_V3_TEST_ONLY",
                parent={"requirement_id": "issue_28_v2", "requirement_closure_hash": parent["requirement_closure_hash"],
                    "hashes": parent["hashes"], "snapshot_files": bindings,
                    "snapshot_binding_hash": content_hash(value=bindings), "snapshot_git_tree": tree_id},
                supersedes_requirement={"requirement_id": "issue_28_v2",
                    "requirement_closure_hash": parent["requirement_closure_hash"]})
            register = strict_json_file(path=revision / "decision_register.json")
            register.update(requirement_id="issue_28_v3", issue_contract_revision="ISSUE_28_V3_TEST_ONLY")
            atomic_write_json(path=revision / "decision_register.json", value=register)
            profile = strict_json_file(path=revision / "invariant_profile.json")
            profile["requirement_id"] = "issue_28_v3"
            atomic_write_json(path=revision / "invariant_profile.json", value=profile)
            transfer = strict_json_file(path=revision / "transfer_manifest.json")
            fragments = [{"decision_id": key, "source_path": path,
                "source_value_hash": content_hash(value=value),
                "parent_effective_record_hash": decision_record_hash(decision=row),
                "disposition": "CARRY_FORWARD", "successor_decision_id": key,
                "successor_path": path, "transfer_mode": "EXACT_VALUE",
                "rationale": "Test-only same-policy revision retains the exact semantic leaf."}
                for key, row in sorted(parent["effective_decisions"].items()) if row["status"] == "APPROVED"
                for path, value in sorted(choice_fragments(value=row["choice"]).items())]
            transfer.update(requirement_id="issue_28_v3", parent_requirement_id="issue_28_v2",
                parent_requirement_closure_hash=parent["requirement_closure_hash"], parent_snapshot_files=bindings,
                parent_snapshot_binding_hash=content_hash(value=bindings), fragments=fragments,
                fragment_classification_counts={"CARRY_FORWARD": len(fragments), "SUPERSEDED": 0, "HISTORICAL_ONLY": 0})
            atomic_write_json(path=revision / "transfer_manifest.json", value=transfer)
            refresh(revision, baseline)
            later = load_requirement_snapshot(snapshot_dir=revision)
            self.assertEqual("PROFILE_DRIVEN_V3", later["requirement_generation"])
            self.assertEqual("NOT_ACTIVATED", later["activation_state"])
            self.assertNotEqual(parent["requirement_closure_hash"], later["requirement_closure_hash"])
            self.assertEqual(parent["requirement_closure_hash"], load_requirement_snapshot(snapshot_dir=snapshot)["requirement_closure_hash"])
            self.assertEqual(plan, load_release_plan_artifact(repo_root=root, release_plan_id="test_old_r4_v2"))
            validate_execution_authority(repo_root=root, requirement=later)


class Issue28V2OfflineGovernanceTest(unittest.TestCase):
    def test_consumed_two_filing_quota_stops_before_native_sec_fetch(self):
        """The real configured acquisition entrypoint cannot repeat either filing."""
        from tools.acquire_r4_fixture_filings import acquire, preflight, SecHttpClient
        ledger = (REPO_ROOT / "evidence/requests_log.csv").read_bytes()
        with mock.patch.object(SecHttpClient, "fetch", side_effect=AssertionError("FORBIDDEN_SEC")) as fetch, \
                mock.patch("socket.socket", side_effect=AssertionError("FORBIDDEN_NETWORK")) as network:
            state = preflight(repo_root=REPO_ROOT)
            self.assertEqual(2, len(state["sources"]))
            self.assertTrue(all(any(row["source_url"] == source["source_url"] for row in state["rows"])
                                for source in state["sources"]))
            with self.assertRaisesRegex(ValueError, "already has a terminal attempt"):
                acquire(repo_root=REPO_ROOT)
            self.assertEqual(0, fetch.call_count)
            self.assertEqual(0, network.call_count)
        self.assertEqual(ledger, (REPO_ROOT / "evidence/requests_log.csv").read_bytes())

    def test_arbitrary_nonempty_owner_token_never_opens_financial_provider(self):
        """Real public legacy executor remains unauthorized despite policy approval."""
        from vnext import ai_adapter, qualification
        legacy = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_15_v1")
        self.assertFalse(legacy["effective_decisions"]["D-07"]["choice"]["live_qualification_scope"]["financial_qualification_authorized"])
        ledger = (REPO_ROOT / "evidence/requests_log.csv").read_bytes()
        with mock.patch.object(ai_adapter, "_open_provider_request", side_effect=AssertionError("FORBIDDEN_PROVIDER")) as opener, \
                mock.patch("socket.socket", side_effect=AssertionError("FORBIDDEN_NETWORK")) as network:
            with self.assertRaises(qualification.QualificationError) as failure:
                qualification.execute_table_qualification_task(repo_root=REPO_ROOT,
                    family_id="financial_statement", task_contract_id="financial_liquidity_coverage_ratio_table_v1",
                    qualification_ordinal=1, qualification_phase="SECOND_LAYOUT",
                    target_period={"kind": "INSTANT", "fiscal_year": 2025, "instant": "2025-12-31"},
                    owner_token="arbitrary-nonempty-not-a-live-grant")
            self.assertEqual("TABLE_QUALIFICATION_NOT_AUTHORIZED", failure.exception.code)
            self.assertEqual(0, opener.call_count)
            self.assertEqual(0, network.call_count)
        self.assertEqual(ledger, (REPO_ROOT / "evidence/requests_log.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
