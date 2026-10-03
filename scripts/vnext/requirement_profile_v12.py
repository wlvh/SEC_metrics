"""Delegated normal saved-input candidates; no external or production grant."""

from pathlib import Path

from . import requirement_profile_v1 as v1
from .canonical import content_hash, sha256_file, strict_json_file
from .sources import resolve_repository_file


PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V12"
REQUIREMENT_ID = "issue_28_v11"
PARENT_ID = "issue_28_v10"
POLICY_PATH = "config/issue28_normal_candidates_v1.json"


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    def need(condition, reason):
        if not condition:
            raise v1.RequirementProfileError(reason)

    root = snapshot_dir.parent.parent
    code_root = Path(__file__).resolve().parents[2]
    need(snapshot_dir.name == REQUIREMENT_ID and snapshot_dir.parent.name == "requirements"
         and not snapshot_dir.is_symlink()
         and {p.name for p in snapshot_dir.iterdir()} == v1.PROFILE_SNAPSHOT_FILES,
         "Normal candidate snapshot files differ")
    # This is one installed development policy, not a caller-authored profile.
    # Comparing only listed execution files would let an importer delete the
    # list, rehash its closure and substitute unapproved traits or rules.
    for name in sorted(v1.PROFILE_SNAPSHOT_FILES):
        relative = "requirements/" + REQUIREMENT_ID + "/" + name
        installed = resolve_repository_file(repo_root=code_root, repo_relative_path=relative)
        imported = resolve_repository_file(repo_root=root, repo_relative_path=relative)
        need(imported.read_bytes() == installed.read_bytes(),
             "Normal candidate installed snapshot differs: " + name)
    baseline = strict_json_file(path=snapshot_dir / "baseline_manifest.json")
    policy = strict_json_file(path=root / POLICY_PATH)
    need(policy == strict_json_file(path=code_root / POLICY_PATH),
         "Caller cannot redefine installed candidate policy")
    index = strict_json_file(path=root / policy["frozen_parent_index"])
    need(sha256_file(path=root / policy["frozen_parent_index"]) == policy["frozen_parent_index_sha256"],
         "Frozen parent authority index differs")
    parent_root = root / policy["frozen_parent_root"]
    for relative, binding in index["files"].items():
        path = resolve_repository_file(repo_root=parent_root, repo_relative_path=relative)
        need(sha256_file(path=path) == binding["sha256"] and path.stat().st_size == binding["size"],
             "Frozen parent authority bytes differ: " + relative)
    parent = parent_loader(snapshot_dir=parent_root / "requirements" / PARENT_ID)
    need(parent["requirement_closure_hash"] == policy["parent_requirement_closure_hash"]
         == index["requirement_closure_hash"], "Frozen parent closure differs")
    need(baseline["requirement_id"] == REQUIREMENT_ID
         and baseline["requirement_generation"] == PROFILE_REQUIREMENT_GENERATION
         and baseline["parent"]["requirement_id"] == PARENT_ID
         and baseline["parent"]["requirement_closure_hash"] == parent["requirement_closure_hash"],
         "Normal candidate parent binding differs")
    for name, binding in baseline["parent"]["snapshot_files"].items():
        path = parent_root / "requirements" / PARENT_ID / name
        need(sha256_file(path=path) == binding["sha256"]
             and path.stat().st_size == binding["size"], "Normal candidate parent bytes differ")
    validator = baseline["validator"]
    need(validator["path"] == "scripts/vnext/requirement_profile_v12.py"
         and sha256_file(path=root / validator["path"]) == validator["sha256"]
         and sha256_file(path=code_root / validator["path"]) == validator["sha256"],
         "Normal candidate validator differs")
    decision = strict_json_file(path=snapshot_dir / "decision_register.json")
    need(decision == {"status": "USER_DELEGATED_DEVELOPMENT_ONLY", "policy": policy},
         "Normal candidate policy differs")
    need(policy["policy_id"] == "issue28_normal_candidates_v1"
         and policy["production_authorized"] is False
         and policy["provider_enabled"] is False and policy["sec_fetch_enabled"] is False
         and policy["new_business_budget"] == "NOT_GRANTED_BY_THIS_POLICY"
         and policy["metric_ids"] == ["B06", "C03", "C04", "D01"]
         and policy["native_deterministic_text_methods"] == ["RISK_FACTOR_HEADINGS_V1"],
         "Normal candidate development boundary differs")
    transfer = strict_json_file(path=snapshot_dir / "transfer_manifest.json")
    need(transfer == {"parent_requirement_id": PARENT_ID,
         "parent_requirement_closure_hash": parent["requirement_closure_hash"],
         "disposition": "CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION",
         "pending_decision_ids": parent["pending_decision_ids"]},
         "Normal candidate inherited responsibilities differ")
    invariants = strict_json_file(path=snapshot_dir / "invariant_profile.json")
    need(invariants == {"historical_bytes_unchanged": True,
         "source_set_from_discovery_not_selected_values": True,
         "saved_sources_require_independent_baseline": True,
         "text_requires_source_replay_and_whole_review": True,
         "old_closed_budgets_unavailable": True, "production_authorized": False},
         "Normal candidate invariant profile differs")
    need(set(baseline["new_rule_files"]) == set(policy["rule_paths"]),
         "Normal candidate rule set differs")
    for relative, binding in baseline["new_rule_files"].items():
        path = root / relative
        need(path.is_file() and not path.is_symlink()
             and sha256_file(path=path) == binding["sha256"]
             and sha256_file(path=code_root / relative) == binding["sha256"]
             and path.stat().st_size == binding["size"],
             "Normal candidate rule bytes differ: " + relative)
    hashes = {key: sha256_file(path=snapshot_dir / name) for key, name in (
        ("baseline_sha256", "baseline_manifest.json"), ("contract_sha256", "CONTRACT.md"),
        ("decision_register_sha256", "decision_register.json"),
        ("invariant_profile_sha256", "invariant_profile.json"),
        ("transfer_manifest_sha256", "transfer_manifest.json"))}
    hashes.update(parent_requirement_closure_hash=parent["requirement_closure_hash"],
                  validator_sha256=validator["sha256"])
    return {"artifact_requirement_generation": "EXPLICIT_REQUIREMENT_V1", "baseline": baseline,
        "requirement_generation": PROFILE_REQUIREMENT_GENERATION, "requirement_id": REQUIREMENT_ID,
        "requirement_closure_hash": content_hash(value=hashes), "hashes": hashes,
        "execution_authority": baseline["execution_authority"], "activation_state": "NOT_ACTIVATED",
        "effective_decisions": parent["effective_decisions"], "decision_chains": parent["decision_chains"],
        "pending_decision_ids": parent["pending_decision_ids"], "parent_snapshot": parent,
        "parent_requirement_id": PARENT_ID, "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "transfer": transfer, "evaluated_invariants": invariants,
        "issue_contract_revision": "normal-saved-candidates-v1", "policy": policy}
