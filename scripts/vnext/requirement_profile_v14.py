"""Installed successor for ordinary financial and disclosure-text candidates."""
from pathlib import Path

from . import requirement_profile_v1 as v1
from .canonical import content_hash, sha256_file, strict_json_file
from .sources import resolve_repository_file


PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V14"
REQUIREMENT_ID = "issue_28_v13"
PARENT_ID = "issue_28_v12"
POLICY_PATH = "config/issue28_normal_results_v2.json"


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    def need(condition, reason):
        if not condition:
            raise v1.RequirementProfileError(reason)

    root = snapshot_dir.parent.parent
    installed = Path(__file__).resolve().parents[2]
    need(snapshot_dir.name == REQUIREMENT_ID and snapshot_dir.parent.name == "requirements"
         and not snapshot_dir.is_symlink()
         and {p.name for p in snapshot_dir.iterdir()} == v1.PROFILE_SNAPSHOT_FILES,
         "Normal successor snapshot directory differs")
    for name in sorted(v1.PROFILE_SNAPSHOT_FILES):
        relative = "requirements/" + REQUIREMENT_ID + "/" + name
        here = resolve_repository_file(repo_root=root, repo_relative_path=relative)
        source = resolve_repository_file(repo_root=installed, repo_relative_path=relative)
        need(here.read_bytes() == source.read_bytes(), "Normal successor installed snapshot differs: " + name)
    baseline = strict_json_file(path=snapshot_dir / "baseline_manifest.json")
    policy = strict_json_file(path=root / POLICY_PATH)
    need(policy == strict_json_file(path=installed / POLICY_PATH), "Normal successor installed policy differs")
    parent = parent_loader(snapshot_dir=root / "requirements" / PARENT_ID)
    need(baseline["requirement_id"] == REQUIREMENT_ID
         and baseline["requirement_generation"] == PROFILE_REQUIREMENT_GENERATION
         and baseline["parent"]["requirement_id"] == PARENT_ID
         and baseline["parent"]["requirement_closure_hash"] == parent["requirement_closure_hash"],
         "Normal successor parent identity differs")
    need(set(baseline["parent"]["snapshot_files"]) == v1.PROFILE_SNAPSHOT_FILES,
         "Normal successor parent file set differs")
    for name, binding in baseline["parent"]["snapshot_files"].items():
        path = root / "requirements" / PARENT_ID / name
        need(sha256_file(path=path) == binding["sha256"] and path.stat().st_size == binding["size"],
             "Normal successor parent bytes differ: " + name)
    validator = baseline["validator"]
    need(validator["path"] == "scripts/vnext/requirement_profile_v14.py"
         and sha256_file(path=root / validator["path"]) == validator["sha256"]
         and sha256_file(path=installed / validator["path"]) == validator["sha256"],
         "Normal successor validator differs")
    need(policy["policy_id"] == "issue28_normal_results_v2"
         and policy["production_authorized"] is False
         and policy["provider_enabled"] is False and policy["sec_fetch_enabled"] is False
         and policy["new_business_budget"] == "NOT_GRANTED_BY_THIS_POLICY",
         "Normal successor development boundary differs")
    decision = strict_json_file(path=snapshot_dir / "decision_register.json")
    need(decision == {"status": "USER_DELEGATED_DEVELOPMENT_ONLY", "policy": policy},
         "Normal successor decision differs")
    transfer = strict_json_file(path=snapshot_dir / "transfer_manifest.json")
    need(transfer == {"parent_requirement_id": PARENT_ID,
         "parent_requirement_closure_hash": parent["requirement_closure_hash"],
         "disposition": "CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION",
         "pending_decision_ids": parent["pending_decision_ids"]},
         "Normal successor inherited obligations differ")
    need(set(baseline["new_rule_files"]) == set(policy["rule_paths"]),
         "Normal successor rule set differs")
    for relative, binding in baseline["new_rule_files"].items():
        here = resolve_repository_file(repo_root=root, repo_relative_path=relative)
        source = resolve_repository_file(repo_root=installed, repo_relative_path=relative)
        need(sha256_file(path=here) == binding["sha256"] == sha256_file(path=source)
             and here.stat().st_size == binding["size"], "Normal successor rule bytes differ: " + relative)
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
        "transfer": transfer, "evaluated_invariants": strict_json_file(path=snapshot_dir / "invariant_profile.json"),
        "issue_contract_revision": "ordinary-integrated-results-v2", "policy": policy}
