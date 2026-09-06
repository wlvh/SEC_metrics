"""Retained-engine extension for exactly one owner-approved R4 label policy.

The existing five-file/parent/Decision/transfer machinery is reused. V1-V3
engines and snapshots remain immutable. Task policy content is distinct from
the later exact-head GitHub activation and live authorization.
"""
from pathlib import Path
from . import canonical, requirement_profile_v1 as v1, requirement_profile_v3 as v3
from .canonical import content_hash, sha256_file, sha256_bytes
from .r4_label_policy import approved_label_choice, DECISION_ID

PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V4"
PROFILE_SEMANTIC_VERSION = "4"
POLICY_PATH = "docs/evidence/issue_28_r4_label_policy.json"


def _require(condition, reason):
    if not condition:
        raise v1.RequirementProfileError(reason)


def _label_choice(*, choice):
    _require(choice == approved_label_choice(), "R4 label policy exceeds owner approval")
    return dict(choice)


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    try:
        return _load(snapshot_dir=snapshot_dir, parent_loader=parent_loader)
    except (KeyError, TypeError, IndexError) as error:
        raise v1.RequirementProfileError("Malformed R4 label revision") from error


def _load(*, snapshot_dir, parent_loader):
    _require(not snapshot_dir.is_symlink() and snapshot_dir.is_dir()
        and {p.name for p in snapshot_dir.iterdir()} == v1.PROFILE_SNAPSHOT_FILES,
        "R4 revision snapshot file set differs")
    baseline = v1.read_requirement_object(path=snapshot_dir / "baseline_manifest.json")
    parent = parent_loader(snapshot_dir=snapshot_dir.parent / "issue_28_v2")
    inherited_sources = parent["baseline"]["policy_evidence"]
    _require(baseline["policy_evidence"][:-1] == inherited_sources,
             "R4 revision changes inherited policy provenance")
    core = {**baseline, "policy_evidence": [s for s in inherited_sources
        if s["kind"] != v3.OWNER_COMMENT_KIND]}
    v1._validate_baseline(baseline=core, snapshot_dir=snapshot_dir,
        generation=PROFILE_REQUIREMENT_GENERATION, semantic_version=PROFILE_SEMANTIC_VERSION,
        engine_file=Path(__file__), engine_dependencies=(Path(v1.__file__), Path(v3.__file__),
            Path(canonical.__file__), Path(__file__).with_name("r4_label_policy.py")))
    _require(baseline["requirement_id"] == "issue_28_v3"
        and baseline["supersedes_requirement"] == {"requirement_id": "issue_28_v2",
            "requirement_closure_hash": parent["requirement_closure_hash"]}, "R4 revision parent differs")
    for field in ("active_publication", "historical_archive", "issue"):
        _require(baseline[field] == parent["baseline"][field], "R4 historical baseline differs")
    binding = baseline["parent"]
    _require(binding["requirement_id"] == "issue_28_v2" and binding["hashes"] == parent["hashes"]
        and binding["requirement_closure_hash"] == parent["requirement_closure_hash"]
        and binding["snapshot_binding_hash"] == content_hash(value=binding["snapshot_files"]),
        "R4 exact parent binding differs")
    v1._verify_bound_files(root=snapshot_dir.parent / "issue_28_v2", bindings=binding["snapshot_files"],
        expected_files=v1.PROFILE_SNAPSHOT_FILES, label="R4 parent")
    path = snapshot_dir.parent.parent / POLICY_PATH
    capture = v1.read_requirement_object(path=path)
    source = baseline["policy_evidence"][-1]
    _require(not path.is_symlink() and capture["record_type"] == "OWNER_TASK_POLICY_EVIDENCE"
        and capture["author"] == "repository-owner:current-codex-user"
        and sha256_bytes(content=capture["approval_text"].encode()) ==
            "d9a6ff212099d368a564229f2918754e123dfa4cb536ad16c11fb0e9d18e5c2f"
        and capture["evidence_scope"] == "POLICY_CONTENT_ONLY"
        and capture["source_kind"] == "CURRENT_CODEX_USER_INSTRUCTION"
        and source == {"source_id": "OWNER_R4_LABEL_POLICY", "kind": "OWNER_TASK_POLICY",
            "source_url": "codex-task:" + capture["task_id"],
            "source_sha256": sha256_bytes(content=capture["approval_text"].encode()),
            "author": capture["author"], "published_at_utc": capture["observed_at_utc"],
            "text": capture["approval_text"], "evidence_path": POLICY_PATH}
        and capture["choice"] == approved_label_choice()
        and capture["transition_activation"] == "NOT_ISSUED"
        and capture["provider_paid_sec_publication_authorized"] is False
        and baseline["execution_authority"]["files"][POLICY_PATH] == {
            "sha256": sha256_file(path=path), "size": path.stat().st_size}, "R4 owner instruction binding differs")
    v1.parse_utc_timestamp(value=capture["observed_at_utc"])
    register = v1.read_requirement_object(path=snapshot_dir / "decision_register.json")
    prior = v1.read_requirement_object(path=snapshot_dir.parent / "issue_28_v2/decision_register.json")
    v1._exact_fields(value=register, expected=set(prior), label="R4 Decision register")
    _require(register["requirement_id"] == "issue_28_v3" and register["schema_version"] == 2
        and register["issue_contract_revision"] == baseline["contract_revision"]
        and register["decisions"][:-1] == prior["decisions"]
        and register["pending_decisions"] == prior["pending_decisions"], "R4 inherited Decisions changed")
    decision = register["decisions"][-1]
    _require(decision == {"decision_id": DECISION_ID, "status": "APPROVED",
        "choice": approved_label_choice(), "approved_by": capture["author"],
        "approved_at_utc": capture["observed_at_utc"], "supersedes_decision_id": None,
        "evidence": source["source_url"], "policy_provenance": {"source_id": source["source_id"],
            "section": "scope_label_representation", "scope": "POLICY_CONTENT_ONLY"}},
        "R4 new Decision differs from owner policy")
    decisions, chains = v1.resolve_decision_chains(decisions=register["decisions"] + register["pending_decisions"])
    profile = v1.read_requirement_object(path=snapshot_dir / "invariant_profile.json")
    expected = [{"invariant_id": "INV-" + k.removeprefix("S-"), "decision_id": k}
                for k, d in decisions.items() if d["status"] == "APPROVED"]
    _require(profile["invariants"] == sorted(expected, key=lambda x:x["invariant_id"]),
             "R4 invariant exact set differs")
    evaluated = v1.evaluate_invariant_profile(profile=profile, requirement_id="issue_28_v3",
        effective_decisions=decisions, semantic_version="4",
        evaluators={**v3.EVALUATORS, "R4_SOURCE_LABEL_REPRESENTATION": _label_choice})
    transfer = v1.read_requirement_object(path=snapshot_dir / "transfer_manifest.json")
    view = {k:v for k,v in transfer.items() if k != "pending_decision_transfers"}
    _require(view["schema_version"] == 3, "R4 transfer version differs")
    view["schema_version"] = 2
    transferred = v1._validate_transfer(transfer=view, requirement_id="issue_28_v3",
        parent={**parent,"effective_decisions":{k:d for k,d in parent["effective_decisions"].items()
            if d["status"] == "APPROVED"}}, current_decisions=decisions,
        parent_snapshot_dir=snapshot_dir.parent / "issue_28_v2", parent_snapshot_files=binding["snapshot_files"])
    _require(all(row["disposition"] == "CARRY_FORWARD" for row in transferred["fragments"]),
             "R4 revision changed inherited policy fragments")
    pending = [{"decision_id":k,"disposition":"CARRY_FORWARD","parent_record_hash":v1.decision_record_hash(decision=d),
                "qualification_credit":"NONE"} for k,d in parent["effective_decisions"].items()
               if d["status"] != "APPROVED"]
    _require(transfer["pending_decision_transfers"] == pending, "Pending policy was activated")
    hashes = {key:sha256_file(path=snapshot_dir/name) for key,name in (
        ("baseline_sha256","baseline_manifest.json"),("contract_sha256","CONTRACT.md"),
        ("decision_register_sha256","decision_register.json"),("invariant_profile_sha256","invariant_profile.json"),
        ("transfer_manifest_sha256","transfer_manifest.json"))}
    hashes.update(parent_requirement_closure_hash=parent["requirement_closure_hash"], validator_sha256=baseline["validator"]["sha256"])
    return {"artifact_requirement_generation":baseline["artifact_requirement_generation"], "baseline":baseline,
        "decision_chains":chains,"effective_decisions":decisions,"evaluated_invariants":evaluated,"hashes":hashes,
        "issue_contract_revision":register["issue_contract_revision"],"parent_requirement_id":"issue_28_v2",
        "parent_requirement_closure_hash":parent["requirement_closure_hash"],"pending_decision_ids":[r["decision_id"] for r in pending],
        "requirement_closure_hash":content_hash(value=hashes),"requirement_generation":PROFILE_REQUIREMENT_GENERATION,
        "requirement_id":"issue_28_v3","transfer":{**transferred,"pending_decision_transfers":pending},
        "parent_snapshot":parent,"execution_authority":baseline["execution_authority"],"activation_state":"NOT_ACTIVATED"}
