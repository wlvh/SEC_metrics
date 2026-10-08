"""Installed successor Requirement for pinned historical annual periods.

Same shape as the engines before it and bound to one Requirement id, which is
this repository's convention: an engine and the Requirement it validates are
written together. What it adds over ``issue_28_v13`` is the historical layer's
own rule files and its period-selection policy; everything the parent binds is
carried forward by loading the parent and comparing its bytes.

It exists so a historical Run can declare a Requirement that actually covers
the code that produced it. Running an ordinary Run's Requirement for a
historical period would record an execution authority that does not name the
historical modules at all.
"""
from pathlib import Path

from . import requirement_profile_v1 as v1
from .canonical import content_hash, sha256_file, strict_json_file
from .sources import resolve_repository_file


PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V16"
REQUIREMENT_ID = "issue_47_v1"
PARENT_ID = "issue_28_v13"
POLICY_PATH = "config/normal_period_selection_v1.json"
PARENT_POLICY_PATH = "config/issue28_normal_results_v2.json"


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    def need(condition, reason):
        if not condition:
            raise v1.RequirementProfileError(reason)

    root = snapshot_dir.parent.parent
    installed = Path(__file__).resolve().parents[2]
    need(snapshot_dir.name == REQUIREMENT_ID and snapshot_dir.parent.name == "requirements"
         and not snapshot_dir.is_symlink()
         and {p.name for p in snapshot_dir.iterdir()} == v1.PROFILE_SNAPSHOT_FILES,
         "Historical successor snapshot directory differs")
    for name in sorted(v1.PROFILE_SNAPSHOT_FILES):
        relative = "requirements/" + REQUIREMENT_ID + "/" + name
        here = resolve_repository_file(repo_root=root, repo_relative_path=relative)
        source = resolve_repository_file(repo_root=installed, repo_relative_path=relative)
        need(here.read_bytes() == source.read_bytes(),
             "Historical successor installed snapshot differs: " + name)
    baseline = strict_json_file(path=snapshot_dir / "baseline_manifest.json")
    policy = strict_json_file(path=root / POLICY_PATH)
    need(policy == strict_json_file(path=installed / POLICY_PATH),
         "Historical successor installed policy differs")
    # The parent is loaded, not summarised: its own engine re-checks its own
    # rule bytes on both roots, so this successor never re-states them.
    parent = parent_loader(snapshot_dir=root / "requirements" / PARENT_ID)
    need(baseline["requirement_id"] == REQUIREMENT_ID
         and baseline["requirement_generation"] == PROFILE_REQUIREMENT_GENERATION
         and baseline["parent"]["requirement_id"] == PARENT_ID
         and baseline["parent"]["requirement_closure_hash"] == parent["requirement_closure_hash"],
         "Historical successor parent identity differs")
    need(set(baseline["parent"]["snapshot_files"]) == v1.PROFILE_SNAPSHOT_FILES,
         "Historical successor parent file set differs")
    for name, binding in baseline["parent"]["snapshot_files"].items():
        path = root / "requirements" / PARENT_ID / name
        need(sha256_file(path=path) == binding["sha256"]
             and path.stat().st_size == binding["size"],
             "Historical successor parent bytes differ: " + name)
    validator = baseline["validator"]
    need(validator["path"] == "scripts/vnext/requirement_profile_v16.py"
         and sha256_file(path=root / validator["path"]) == validator["sha256"]
         and sha256_file(path=installed / validator["path"]) == validator["sha256"],
         "Historical successor validator differs")
    need(policy["policy_id"] == "ordinary_period_selection_v1"
         and policy["production_authorized"] is False
         and policy["caller_supplied_accession_authorized"] is False
         and policy["caller_supplied_period_dates_authorized"] is False
         and policy["latest_restated_view_authorized"] is False
         and policy["point_in_time_view_authorized"] is False,
         "Historical successor development boundary differs")
    parent_policy = strict_json_file(path=root / PARENT_POLICY_PATH)
    need(parent_policy == strict_json_file(path=installed / PARENT_POLICY_PATH)
         and parent_policy["production_authorized"] is False
         and parent_policy["provider_enabled"] is False
         and parent_policy["sec_fetch_enabled"] is False
         and parent_policy["new_business_budget"] == "NOT_GRANTED_BY_THIS_POLICY",
         "Historical successor inherited development boundary differs")
    decision = strict_json_file(path=snapshot_dir / "decision_register.json")
    need(decision == {"status": "USER_DELEGATED_DEVELOPMENT_ONLY", "policy": policy,
                      "inherited_policy": parent_policy},
         "Historical successor decision differs")
    transfer = strict_json_file(path=snapshot_dir / "transfer_manifest.json")
    need(transfer == {"parent_requirement_id": PARENT_ID,
                      "parent_requirement_closure_hash": parent["requirement_closure_hash"],
                      "disposition": "CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION",
                      "pending_decision_ids": parent["pending_decision_ids"]},
         "Historical successor inherited obligations differ")
    # The historical rule files are byte-checked on both roots, exactly as the
    # parent checks its own. A data root that carries different historical
    # bytes than the runtime cannot load this Requirement.
    for relative, binding in baseline["new_rule_files"].items():
        here = resolve_repository_file(repo_root=root, repo_relative_path=relative)
        source = resolve_repository_file(repo_root=installed, repo_relative_path=relative)
        need(sha256_file(path=here) == binding["sha256"] == sha256_file(path=source)
             and here.stat().st_size == binding["size"],
             "Historical successor rule bytes differ: " + relative)
    need(POLICY_PATH in baseline["new_rule_files"],
         "Historical successor must bind its own selection policy")
    hashes = {key: sha256_file(path=snapshot_dir / name) for key, name in (
        ("baseline_sha256", "baseline_manifest.json"), ("contract_sha256", "CONTRACT.md"),
        ("decision_register_sha256", "decision_register.json"),
        ("invariant_profile_sha256", "invariant_profile.json"),
        ("transfer_manifest_sha256", "transfer_manifest.json"))}
    hashes.update(parent_requirement_closure_hash=parent["requirement_closure_hash"],
                  validator_sha256=validator["sha256"])
    return {"artifact_requirement_generation": "EXPLICIT_REQUIREMENT_V1", "baseline": baseline,
            "requirement_generation": PROFILE_REQUIREMENT_GENERATION,
            "requirement_id": REQUIREMENT_ID,
            "requirement_closure_hash": content_hash(value=hashes), "hashes": hashes,
            "execution_authority": baseline["execution_authority"],
            "activation_state": "NOT_ACTIVATED",
            "effective_decisions": parent["effective_decisions"],
            "decision_chains": parent["decision_chains"],
            "pending_decision_ids": parent["pending_decision_ids"], "parent_snapshot": parent,
            "parent_requirement_id": PARENT_ID,
            "parent_requirement_closure_hash": parent["requirement_closure_hash"],
            "transfer": transfer,
            "evaluated_invariants": strict_json_file(path=snapshot_dir / "invariant_profile.json"),
            "issue_contract_revision": "historical-pinned-period-v1", "policy": policy}
