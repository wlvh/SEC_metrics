"""Pending candidate-specific adoption extension of the retained Requirement machinery.

The new Decision remains pending; external activation and publication approval are separate. Parent engines, Decisions, pending
obligations and historical records retain their exact bytes and meaning.
"""
from pathlib import Path
from . import canonical, requirement_profile_v1 as v1, requirement_profile_v3 as v3
from . import requirement_profile_v4 as v4
from . import requirement_profile_v5 as v5
from . import requirement_profile_v6 as v6
from . import requirement_profile_v7 as v7
from .annual_adoption_policy import V2, POLICIES, policy, pending_decision
from .canonical import content_hash, sha256_file, strict_json_file

PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V8"
PROFILE_SEMANTIC_VERSION = "8"
REQUIREMENT_ID = "issue_28_v7"
PARENT_ID = "issue_28_v6"
DECISION_ID = "S-ANNUAL-ADOPTION"
POLICY_PATH, POLICY_SHA256 = POLICIES[V2]
DEPENDENCIES = (Path(v1.__file__), Path(v3.__file__), Path(v4.__file__), Path(v5.__file__), Path(v6.__file__), Path(v7.__file__), Path(canonical.__file__))


def _require(condition, reason):
    if not condition:
        raise v1.RequirementProfileError(reason)


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    try:
        return _load(snapshot_dir=snapshot_dir, parent_loader=parent_loader)
    except (KeyError, TypeError, IndexError) as error:
        raise v1.RequirementProfileError("Malformed annual candidate revision") from error


def _load(*, snapshot_dir, parent_loader):
    _require(not snapshot_dir.is_symlink() and snapshot_dir.is_dir()
        and {p.name for p in snapshot_dir.iterdir()} == v1.PROFILE_SNAPSHOT_FILES,
        "Annual candidate snapshot file set differs")
    root = snapshot_dir.parent.parent
    baseline = v1.read_requirement_object(path=snapshot_dir / "baseline_manifest.json")
    parent = parent_loader(snapshot_dir=snapshot_dir.parent / PARENT_ID)
    inherited = parent["baseline"]["policy_evidence"]
    _require(baseline["policy_evidence"] == inherited, "Inherited policy provenance changed")
    # The retained base validator validates its original evidence kinds; the
    # captured current-task source is separately byte-verified below.
    core = {**baseline, "policy_evidence": [s for s in inherited
        if s["kind"] in {"ISSUE_BODY_POLICY", "OWNER_POLICY_SUCCESSOR", "PARENT_DECISION_POLICY"}]}
    v1._validate_baseline(baseline=core, snapshot_dir=snapshot_dir,
        generation=PROFILE_REQUIREMENT_GENERATION, semantic_version=PROFILE_SEMANTIC_VERSION,
        engine_file=Path(__file__), engine_dependencies=DEPENDENCIES)
    _require(baseline["requirement_id"] == REQUIREMENT_ID
        and baseline["supersedes_requirement"] == {"requirement_id": PARENT_ID,
            "requirement_closure_hash": parent["requirement_closure_hash"]}, "Annual candidate parent differs")
    for field in ("active_publication", "historical_archive", "issue"):
        _require(baseline[field] == parent["baseline"][field], "Historical baseline changed")
    binding = baseline["parent"]
    _require(binding["requirement_id"] == PARENT_ID and binding["hashes"] == parent["hashes"]
        and binding["requirement_closure_hash"] == parent["requirement_closure_hash"]
        and binding["snapshot_binding_hash"] == content_hash(value=binding["snapshot_files"]),
        "Annual candidate exact parent differs")
    v1._verify_bound_files(root=snapshot_dir.parent / PARENT_ID, bindings=binding["snapshot_files"],
        expected_files=v1.PROFILE_SNAPSHOT_FILES, label="Annual candidate parent")
    chosen = policy(root, V2)
    _require(chosen["adoption_requirement_id"] == REQUIREMENT_ID,
        "Adoption Requirement policy differs")
    for relative in (POLICY_PATH, chosen["content_review"]["path"]):
        path = v1._regular_file(path=root / relative, label="Adoption policy evidence")
        _require(baseline["execution_authority"]["files"].get(relative) == {
            "sha256": sha256_file(path=path), "size": path.stat().st_size},
            "Adoption policy evidence is not execution-bound")
    prior = v1.read_requirement_object(path=snapshot_dir.parent / PARENT_ID / "decision_register.json")
    register = v1.read_requirement_object(path=snapshot_dir / "decision_register.json")
    v1._exact_fields(value=register, expected=set(prior), label="Candidate Decision register")
    _require(register["requirement_id"] == REQUIREMENT_ID
        and register["schema_version"] == prior["schema_version"]
        and register["issue_contract_revision"] == baseline["contract_revision"]
        and register["decisions"] == prior["decisions"]
        and register["pending_decisions"] == prior["pending_decisions"] + [pending_decision(chosen)], "Inherited Decisions changed")
    decisions, chains = v1.resolve_decision_chains(decisions=register["decisions"] + register["pending_decisions"])
    profile = v1.read_requirement_object(path=snapshot_dir / "invariant_profile.json")
    evaluated = v1.evaluate_invariant_profile(profile=profile, requirement_id=REQUIREMENT_ID,
        effective_decisions=decisions, semantic_version=PROFILE_SEMANTIC_VERSION,
        evaluators={**v3.EVALUATORS, "R4_SOURCE_LABEL_REPRESENTATION": v4._label_choice,
                    "ORDINARY_ANNUAL_CANDIDATE_POLICY": v5.candidate_choice,
                    "ANNUAL_CANDIDATE_RUNTIME_POLICY": v6.candidate_choice,
                    "ANNUAL_CANDIDATE_REPAIR_POLICY": v7.candidate_choice})
    transfer = v1.read_requirement_object(path=snapshot_dir / "transfer_manifest.json")
    view = {k:v for k,v in transfer.items() if k != "pending_decision_transfers"}
    _require(view["schema_version"] == 3, "Candidate transfer version differs")
    view["schema_version"] = 2
    transferred = v1._validate_transfer(transfer=view, requirement_id=REQUIREMENT_ID,
        parent={**parent,"effective_decisions":{k:d for k,d in parent["effective_decisions"].items()
            if d["status"] == "APPROVED"}}, current_decisions=decisions,
        parent_snapshot_dir=snapshot_dir.parent / PARENT_ID, parent_snapshot_files=binding["snapshot_files"])
    _require(all(r["disposition"] == "CARRY_FORWARD" for r in transferred["fragments"]),
        "Candidate policy changed a historical fragment")
    pending = [{"decision_id":k,"disposition":"CARRY_FORWARD","parent_record_hash":v1.decision_record_hash(decision=d),
                "qualification_credit":"NONE"} for k,d in parent["effective_decisions"].items() if d["status"] != "APPROVED"]
    _require(transfer["pending_decision_transfers"] == pending, "Pending policy was activated")
    hashes = {key:sha256_file(path=snapshot_dir/name) for key,name in (
        ("baseline_sha256","baseline_manifest.json"),("contract_sha256","CONTRACT.md"),
        ("decision_register_sha256","decision_register.json"),("invariant_profile_sha256","invariant_profile.json"),
        ("transfer_manifest_sha256","transfer_manifest.json"))}
    hashes.update(parent_requirement_closure_hash=parent["requirement_closure_hash"], validator_sha256=baseline["validator"]["sha256"])
    return {"artifact_requirement_generation":baseline["artifact_requirement_generation"], "baseline":baseline,
        "decision_chains":chains,"effective_decisions":decisions,"evaluated_invariants":evaluated,"hashes":hashes,
        "issue_contract_revision":register["issue_contract_revision"],"parent_requirement_id":PARENT_ID,
        "parent_requirement_closure_hash":parent["requirement_closure_hash"],"pending_decision_ids":[r["decision_id"] for r in pending] + [DECISION_ID],
        "requirement_closure_hash":content_hash(value=hashes),"requirement_generation":PROFILE_REQUIREMENT_GENERATION,
        "requirement_id":REQUIREMENT_ID,"transfer":{**transferred,"pending_decision_transfers":pending},
        "parent_snapshot":parent,"execution_authority":baseline["execution_authority"],"activation_state":"NOT_ACTIVATED", "adoption_policy":chosen}
