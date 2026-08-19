"""Load and verify the immutable AI-first Requirement Snapshot.

The loader binds exact FSD, Issue Contract, Decision Register, legacy
inventory, and baseline bytes. Runtime callers receive explicit hashes and the
single effective decision for each decision ID; comments or live issue state
are never consulted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from .canonical import CanonicalError, SEMANTIC_VERSIONS, content_hash
from .canonical import parse_utc_timestamp
from .canonical import sha256_file, strict_json_file


FSD_SHA256 = "1cf091812629648095119692c1742d12015e1012ccabf2173820e585e1d42b2b"
PARENT_REQUIREMENT_ID = "ai_first_v3_3_1"
ISSUE_15_REQUIREMENT_ID = "issue_15_v1"
ISSUE_15_CONTRACT_SHA256 = (
    "9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec"
)
ISSUE_15_FOUNDATION_SOURCE_COMMIT = (
    "f1cc44342e6814522ec2688cf3674f7ec442be8d"
)
ISSUE_15_FOUNDATION_MERGE_COMMIT = (
    "4d02db6a474f93eec9e058d780e206b4504ab24d"
)
ISSUE_15_FOUNDATION_TAG = "issue-15-foundation-v1"
SNAPSHOT_FILES = {
    "baseline": "baseline_manifest.json",
    "decisions": "decision_register.json",
    "fsd": "FSD.md",
    "issue": "ISSUE_CONTRACT.md",
    "r3_addendum": "ISSUE_CONTRACT_R3_ADDENDUM.md",
    "legacy_inventory": "legacy_path_inventory.json",
}
ISSUE_15_SNAPSHOT_FILES = {
    "baseline": "baseline_manifest.json",
    "contract": "CONTRACT.md",
    "decisions": "decision_register.json",
    "foundation_verification": "foundation_verification_receipt.json",
    "legacy_inventory": "legacy_semantic_producer_inventory.json",
    "source_strategy": "source_strategy_baseline_receipt.json",
    "transfer": "transfer_manifest.json",
}
ISSUE_15_EFFECTIVE_DECISION_IDS = {
    "D-01", "D-03", "D-04", "D-05", "D-06", "D-07", "D-08",
    "D-24", "D-26", "D-30", "D-31", "D-32", "D-33", "D-34",
    "D-35", "D-36", "D-37", "D-38",
}


class RequirementError(ValueError):
    """Report missing, changed, ambiguous, or malformed requirement bytes."""


def _read_object(*, path: Path) -> Dict[str, object]:
    """Read a strict JSON object from one Requirement file.

    Args:
        path: Existing regular JSON file.

    Returns:
        Isolated root mapping.
    """
    parsed = strict_json_file(path=path)
    if not isinstance(parsed, dict):
        raise RequirementError("Requirement JSON root must be an object")
    return dict(parsed)


def _decision_record_hash(*, decision: Mapping[str, object]) -> str:
    """Return the audit identity used by a later superseding decision.

    Args:
        decision: Exact immutable decision record.

    Returns:
        Canonical content hash.
    """
    return content_hash(value=dict(decision))


def _validate_decision(*, decision: Mapping[str, object]) -> Dict[str, object]:
    """Validate one historical pending or terminal decision-chain record.

    Args:
        decision: Candidate decision mapping.

    Returns:
        Isolated record.

    Raises:
        RequirementError: On schema, state, identity, or UTC drift.
    """
    pending = {
        "decision_id",
        "effect",
        "evidence",
        "required_choice_fields",
        "status",
    }
    if set(decision) == pending:
        if decision["status"] != "PENDING_EXTERNAL_APPROVAL":
            raise RequirementError("Pending Decision status is invalid")
        for key in ("decision_id", "effect", "evidence"):
            if not isinstance(decision[key], str) or not decision[key]:
                raise RequirementError(
                    "Pending Decision field is empty: {}".format(key)
                )
        fields = decision["required_choice_fields"]
        if (
            not isinstance(fields, list)
            or not fields
            or any(not isinstance(item, str) or not item for item in fields)
            or len(fields) != len(set(fields))
        ):
            raise RequirementError(
                "Pending Decision required fields are invalid"
            )
        return dict(decision)
    required = {
        "approved_at_utc",
        "approved_by",
        "choice",
        "decision_id",
        "evidence",
        "status",
        "supersedes_decision_id",
    }
    if set(decision) != required:
        raise RequirementError("Decision fields are not exact")
    for key in ("approved_at_utc", "approved_by", "decision_id", "evidence"):
        if not isinstance(decision[key], str) or not decision[key]:
            raise RequirementError("Decision field is empty: {}".format(key))
    try:
        parse_utc_timestamp(value=str(decision["approved_at_utc"]))
    except CanonicalError as error:
        raise RequirementError("Decision timestamp must be UTC") from error
    if decision["status"] not in {"APPROVED", "REJECTED", "SUPERSEDED"}:
        raise RequirementError("Decision status is invalid")
    if not isinstance(decision["choice"], dict):
        raise RequirementError("Decision choice must be an object")
    parent = decision["supersedes_decision_id"]
    if parent is not None and (not isinstance(parent, str) or not parent):
        raise RequirementError("Decision supersedes identity is invalid")
    return dict(decision)


def _decision_parent(*, decision: Mapping[str, object]) -> Optional[str]:
    """Return the predecessor hash for either supported history record.

    Args:
        decision: Validated pending or terminal record.

    Returns:
        ``None`` for the historical pending root, otherwise the named parent.
    """
    if decision["status"] == "PENDING_EXTERNAL_APPROVAL":
        return None
    return decision["supersedes_decision_id"]


def _resolve_decisions(
    *, decisions: Sequence[Mapping[str, object]]
) -> tuple[Dict[str, Dict[str, object]], Dict[str, List[Dict[str, object]]]]:
    """Resolve unique effective tips and preserve every ordered chain.

    Args:
        decisions: Historical pending roots plus terminal records.

    Returns:
        Effective tips and root-to-tip audit chains by Decision ID.
    """
    groups: Dict[str, List[Dict[str, object]]] = {}
    for candidate in decisions:
        decision = _validate_decision(decision=candidate)
        groups.setdefault(str(decision["decision_id"]), []).append(decision)
    effective: Dict[str, Dict[str, object]] = {}
    chains: Dict[str, List[Dict[str, object]]] = {}
    for decision_id, records in groups.items():
        by_hash = {
            _decision_record_hash(decision=record): record
            for record in records
        }
        if len(by_hash) != len(records):
            raise RequirementError("Decision chain contains duplicate bytes")
        children: Dict[Optional[str], List[str]] = {}
        for record_hash, record in by_hash.items():
            parent = _decision_parent(decision=record)
            if parent is not None and parent not in by_hash:
                raise RequirementError("Decision chain has a detached parent")
            children.setdefault(parent, []).append(record_hash)
        roots = children[None] if None in children else []
        if len(roots) != 1:
            raise RequirementError("Decision chain must have one root")
        current = roots[0]
        visited = set()
        ordered = []
        while True:
            if current in visited:
                raise RequirementError("Decision chain contains a cycle")
            visited.add(current)
            ordered.append(by_hash[current])
            next_records = (
                children[current] if current in children else []
            )
            if len(next_records) > 1:
                raise RequirementError(
                    "Parallel effective decisions fail closed"
                )
            if not next_records:
                break
            current = next_records[0]
        if len(visited) != len(records):
            raise RequirementError("Decision chain is disconnected")
        tip = by_hash[current]
        if tip["status"] == "SUPERSEDED":
            raise RequirementError("Effective decision cannot be SUPERSEDED")
        effective[decision_id] = tip
        chains[decision_id] = ordered
    return effective, chains


def effective_decisions(
    *, decisions: Sequence[Mapping[str, object]]
) -> Dict[str, Dict[str, object]]:
    """Resolve one effective tip for every Decision Register decision ID.

    Args:
        decisions: Immutable records in register order. A superseding record
            names the canonical hash of the exact previous record.

    Returns:
        Decision ID to unique effective non-superseded record.

    Raises:
        RequirementError: On detached, cyclic, duplicate, or parallel chains.
    """
    effective, _chains = _resolve_decisions(decisions=decisions)
    return effective


def _load_ai_first_snapshot(*, snapshot_dir: Path) -> Dict[str, object]:
    """Verify the immutable parent AI-first Requirement Snapshot.

    Args:
        snapshot_dir: ``requirements/ai_first_v3_3_1`` directory.

    Returns:
        Hashes, baseline, effective decisions, pending D-01 state, and one
        requirement closure hash.

    Raises:
        RequirementError: On unsafe files, changed bytes, or invalid register.
    """
    paths = {
        key: snapshot_dir / relative
        for key, relative in SNAPSHOT_FILES.items()
    }
    for key in paths:
        if paths[key].is_symlink() or not paths[key].is_file():
            raise RequirementError(
                "Requirement file is unsafe: {}".format(key)
            )
    baseline = _read_object(path=paths["baseline"])
    register = _read_object(path=paths["decisions"])
    if baseline["fsd_sha256"] != sha256_file(path=paths["fsd"]):
        raise RequirementError("FSD bytes differ from baseline")
    if baseline["fsd_sha256"] != FSD_SHA256:
        raise RequirementError("FSD bytes differ from approved v3.3.1")
    if baseline["issue_body_sha256"] != sha256_file(path=paths["issue"]):
        raise RequirementError("Issue Contract bytes differ from baseline")
    if baseline["r3_addendum_sha256"] != sha256_file(
        path=paths["r3_addendum"]
    ):
        raise RequirementError("R3 Addendum bytes differ from baseline")
    if baseline["decision_register_sha256"] != sha256_file(
        path=paths["decisions"]
    ):
        raise RequirementError("Decision Register bytes differ from baseline")
    if baseline["legacy_path_inventory_sha256"] != sha256_file(
        path=paths["legacy_inventory"]
    ):
        raise RequirementError("Legacy inventory bytes differ from baseline")
    required_register = {
        "decisions",
        "issue_contract_revision",
        "pending_decisions",
        "requirement_id",
        "schema_version",
    }
    if set(register) != required_register:
        raise RequirementError("Decision Register fields are not exact")
    if not isinstance(register["decisions"], list):
        raise RequirementError("Decision Register decisions must be an array")
    if not isinstance(register["pending_decisions"], list):
        raise RequirementError("Pending decisions must be an array")
    all_decisions = list(register["decisions"])
    all_decisions.extend(register["pending_decisions"])
    decisions, chains = _resolve_decisions(decisions=all_decisions)
    pending_ids = sorted(
        decision_id
        for decision_id, decision in decisions.items()
        if decision["status"] == "PENDING_EXTERNAL_APPROVAL"
    )
    repo_root = snapshot_dir.parents[1]
    release_plan_path = repo_root / "config" / "vnext_release_plan.json"
    if not release_plan_path.is_file():
        release_plan_path = Path(__file__).resolve().parents[2] / (
            "config/vnext_release_plan.json"
        )
    if (
        release_plan_path.is_symlink()
        or not release_plan_path.is_file()
        or baseline["release_plan_sha256"]
        != sha256_file(path=release_plan_path)
    ):
        raise RequirementError("Release plan bytes differ from baseline")
    if baseline["semantic_runtime_versions"] != SEMANTIC_VERSIONS:
        raise RequirementError("Semantic runtime versions differ")
    semantic_versions_hash = content_hash(value=SEMANTIC_VERSIONS)
    if baseline["semantic_runtime_versions_hash"] != semantic_versions_hash:
        raise RequirementError("Semantic runtime version hash differs")
    hashes = {
        "baseline_sha256": sha256_file(path=paths["baseline"]),
        "decision_register_sha256": sha256_file(path=paths["decisions"]),
        "fsd_sha256": sha256_file(path=paths["fsd"]),
        "issue_body_sha256": sha256_file(path=paths["issue"]),
        "r3_addendum_sha256": sha256_file(path=paths["r3_addendum"]),
        "legacy_path_inventory_sha256": sha256_file(
            path=paths["legacy_inventory"]
        ),
        "release_plan_sha256": sha256_file(path=release_plan_path),
        "semantic_runtime_versions_hash": semantic_versions_hash,
    }
    return {
        "requirement_id": register["requirement_id"],
        "issue_contract_revision": register["issue_contract_revision"],
        "hashes": hashes,
        "requirement_closure_hash": content_hash(value=hashes),
        "baseline": baseline,
        "effective_decisions": decisions,
        "decision_chains": chains,
        "pending_decision_ids": pending_ids,
    }


def _require_exact_fields(
    *, value: Mapping[str, object], fields: set[str], label: str,
) -> None:
    """Require one mapping to expose an exact field set.

    Args:
        value: Mapping whose schema is frozen by the Requirement contract.
        fields: Exact allowed and required keys.
        label: Stable diagnostic name for the mapping.

    Raises:
        RequirementError: When a required field is missing or extra.
    """
    if set(value) != fields:
        raise RequirementError("{} fields are not exact".format(label))


def _issue_15_paths(*, snapshot_dir: Path) -> Dict[str, Path]:
    """Return and validate every Issue #15 snapshot file locator.

    Args:
        snapshot_dir: Candidate ``requirements/issue_15_v1`` directory.

    Returns:
        Stable role-to-path mapping for the seven frozen WB-1 files.
    """
    paths = {
        key: snapshot_dir / relative
        for key, relative in ISSUE_15_SNAPSHOT_FILES.items()
    }
    for key in paths:
        if paths[key].is_symlink() or not paths[key].is_file():
            raise RequirementError(
                "Issue #15 Requirement file is unsafe: {}".format(key)
            )
    return paths


def _load_issue_15_snapshot(*, snapshot_dir: Path) -> Dict[str, object]:
    """Verify the exact Issue #15 WB-1 authority snapshot.

    Args:
        snapshot_dir: ``requirements/issue_15_v1`` or an exact test copy.

    Returns:
        Child closure, parent binding, effective Decisions, frozen baseline,
        and the complete decision chains.

    Raises:
        RequirementError: On parent drift, byte drift, detached Decisions,
        incomplete producer coverage, or overstated foundation evidence.
    """
    paths = _issue_15_paths(snapshot_dir=snapshot_dir)
    baseline = _read_object(path=paths["baseline"])
    register = _read_object(path=paths["decisions"])
    transfer = _read_object(path=paths["transfer"])
    inventory = _read_object(path=paths["legacy_inventory"])
    source_strategy = _read_object(path=paths["source_strategy"])
    foundation = _read_object(path=paths["foundation_verification"])

    baseline_fields = {
        "contract_sha256", "created_at_utc", "effective_decision_ids",
        "foundation_merge_commit", "foundation_merge_tree",
        "foundation_source_commit", "foundation_source_tree",
        "foundation_tag", "foundation_tag_object",
        "foundation_tag_peeled_commit", "issue_body_sha256",
        "issue_contract_revision", "issue_number", "issue_url",
        "metrics_matrix_sha256", "parent_requirement_closure_hash",
        "parent_requirement_hashes", "parent_requirement_id",
        "pending_decision_ids", "record_type", "repository_commit",
        "repository_identity", "repository_tree", "requirement_id",
        "root_business_artifacts", "schema_version",
        "semantic_runtime_versions", "semantic_runtime_versions_hash",
        "snapshot_files", "source_input_role",
    }
    _require_exact_fields(
        value=baseline,
        fields=baseline_fields,
        label="Issue #15 baseline",
    )
    if baseline["requirement_id"] != ISSUE_15_REQUIREMENT_ID:
        raise RequirementError("Issue #15 baseline identity differs")
    if baseline["issue_number"] != 15:
        raise RequirementError("Issue #15 number differs")
    contract_sha256 = sha256_file(path=paths["contract"])
    if (
        contract_sha256 != ISSUE_15_CONTRACT_SHA256
        or baseline["contract_sha256"] != contract_sha256
        or baseline["issue_body_sha256"] != contract_sha256
    ):
        raise RequirementError("Issue #15 Contract bytes differ")

    bound_files = baseline["snapshot_files"]
    if not isinstance(bound_files, dict):
        raise RequirementError("Issue #15 snapshot file bindings are invalid")
    expected_bound = {
        relative
        for key, relative in ISSUE_15_SNAPSHOT_FILES.items()
        if key != "baseline"
    }
    if set(bound_files) != expected_bound:
        raise RequirementError("Issue #15 snapshot file set differs")
    for relative in sorted(expected_bound):
        binding = bound_files[relative]
        if not isinstance(binding, dict):
            raise RequirementError("Issue #15 file binding is invalid")
        _require_exact_fields(
            value=binding,
            fields={"sha256", "size"},
            label="Issue #15 file binding",
        )
        path = snapshot_dir / relative
        if (
            binding["sha256"] != sha256_file(path=path)
            or binding["size"] != path.stat().st_size
        ):
            raise RequirementError(
                "Issue #15 snapshot file bytes differ: {}".format(relative)
            )

    parent_dir = snapshot_dir.parent / PARENT_REQUIREMENT_ID
    parent = _load_ai_first_snapshot(snapshot_dir=parent_dir)
    if (
        baseline["parent_requirement_id"] != PARENT_REQUIREMENT_ID
        or baseline["parent_requirement_closure_hash"]
        != parent["requirement_closure_hash"]
        or baseline["parent_requirement_hashes"] != parent["hashes"]
    ):
        raise RequirementError("Issue #15 parent Requirement binding differs")
    if baseline["semantic_runtime_versions"] != SEMANTIC_VERSIONS:
        raise RequirementError("Issue #15 semantic runtime versions differ")
    if (
        baseline["semantic_runtime_versions_hash"]
        != content_hash(value=SEMANTIC_VERSIONS)
    ):
        raise RequirementError("Issue #15 semantic runtime hash differs")

    required_register = {
        "decisions", "issue_contract_revision", "pending_decisions",
        "requirement_id", "schema_version",
    }
    _require_exact_fields(
        value=register,
        fields=required_register,
        label="Issue #15 Decision Register",
    )
    if register["requirement_id"] != ISSUE_15_REQUIREMENT_ID:
        raise RequirementError("Issue #15 Decision Register identity differs")
    if not isinstance(register["decisions"], list):
        raise RequirementError("Issue #15 decisions must be an array")
    if not isinstance(register["pending_decisions"], list):
        raise RequirementError("Issue #15 pending decisions must be an array")
    parent_register = _read_object(path=parent_dir / "decision_register.json")
    parent_decisions = parent_register["decisions"]
    parent_pending = parent_register["pending_decisions"]
    if not isinstance(parent_decisions, list) or not isinstance(
        parent_pending, list,
    ):
        raise RequirementError("Parent Decision history is invalid")
    if (
        register["decisions"][:len(parent_decisions)] != parent_decisions
        or register["pending_decisions"] != parent_pending
    ):
        raise RequirementError("Issue #15 historical Decision bytes differ")
    all_decisions = list(register["decisions"])
    all_decisions.extend(register["pending_decisions"])
    decisions, chains = _resolve_decisions(decisions=all_decisions)
    pending_ids = sorted(
        decision_id
        for decision_id, decision in decisions.items()
        if decision["status"] == "PENDING_EXTERNAL_APPROVAL"
    )
    if set(decisions) != ISSUE_15_EFFECTIVE_DECISION_IDS:
        raise RequirementError("Issue #15 effective Decision set differs")
    if pending_ids or baseline["pending_decision_ids"] != []:
        raise RequirementError("Issue #15 has an effective pending Decision")
    if sorted(baseline["effective_decision_ids"]) != sorted(decisions):
        raise RequirementError("Issue #15 baseline Decision set differs")
    if (
        len(chains["D-01"]) != 4
        or len(chains["D-26"]) != 2
        or decisions["D-01"]["supersedes_decision_id"]
        != _decision_record_hash(decision=parent["effective_decisions"]["D-01"])
        or decisions["D-26"]["supersedes_decision_id"]
        != _decision_record_hash(decision=parent["effective_decisions"]["D-26"])
    ):
        raise RequirementError("Issue #15 Decision tip binding differs")
    expected_d01_choice = dict(parent["effective_decisions"]["D-01"]["choice"])
    expected_d01_choice["retry_count"] = 0
    d26_choice = decisions["D-26"]["choice"]
    if (
        decisions["D-01"]["choice"] != expected_d01_choice
        or "freeze_replay" in d26_choice["prohibited_required_test_classes"]
        or not d26_choice["required_short_deterministic_invariants"]
    ):
        raise RequirementError("Issue #15 superseding Decision content differs")

    if (
        transfer["parent_requirement_closure_hash"]
        != parent["requirement_closure_hash"]
        or transfer["contract_sha256"] != contract_sha256
        or transfer["requirement_id"] != ISSUE_15_REQUIREMENT_ID
    ):
        raise RequirementError("Issue #15 authority transfer differs")
    if (
        inventory["parent_legacy_inventory_sha256"]
        != parent["hashes"]["legacy_path_inventory_sha256"]
        or inventory["baseline_source_commit"]
        != baseline["repository_commit"]
    ):
        raise RequirementError("Issue #15 producer inventory parent differs")
    producers = inventory["producers"]
    if not isinstance(producers, list):
        raise RequirementError("Issue #15 producer inventory is invalid")
    semantic_producers = [
        producer
        for producer in producers
        if producer["kind"] == "SEMANTIC_PRODUCER"
    ]
    semantic_producer_ids = sorted(
        producer["producer_id"] for producer in semantic_producers
    )
    if (
        inventory["producer_exact_set_hash"]
        != content_hash(value=semantic_producer_ids)
        or inventory["producer_record_set_hash"]
        != content_hash(value=producers)
        or inventory["semantic_producer_record_set_hash"]
        != content_hash(value=semantic_producers)
        or inventory["covered_metric_ids"]
        != source_strategy["metric_id_set"]
        or inventory["mutable_legacy_retirement_config_ledger"] is not False
    ):
        raise RequirementError("Issue #15 semantic producer closure differs")
    mode_metrics = sorted(
        metric_id
        for mode in source_strategy["metrics_by_target_source_mode"].values()
        for metric_id in mode
    )
    if (
        source_strategy["row_count"] != 230
        or source_strategy["metric_id_count"] != 39
        or mode_metrics != source_strategy["metric_id_set"]
        or source_strategy["matrix_sha256"]
        != baseline["metrics_matrix_sha256"]
    ):
        raise RequirementError("Issue #15 source baseline differs")
    if (
        foundation["foundation_source_commit"]
        != ISSUE_15_FOUNDATION_SOURCE_COMMIT
        or baseline["foundation_source_commit"]
        != ISSUE_15_FOUNDATION_SOURCE_COMMIT
        or foundation["foundation_merge_commit"]
        != ISSUE_15_FOUNDATION_MERGE_COMMIT
        or baseline["foundation_merge_commit"]
        != ISSUE_15_FOUNDATION_MERGE_COMMIT
        or foundation["foundation_tag"] != ISSUE_15_FOUNDATION_TAG
        or baseline["foundation_tag"] != ISSUE_15_FOUNDATION_TAG
        or foundation["highest_evidence_level"] != "FAST_LOCAL_ONLY"
        or foundation["real_external_provider_egress_count"] != 0
        or foundation["paid_provider_call_count"] != 0
        or len(foundation["verification_commands"]) != 4
        or any(
            command["return_code"] != 0
            for command in foundation["verification_commands"]
        )
    ):
        raise RequirementError("Issue #15 foundation evidence differs")

    hashes = {
        "baseline_sha256": sha256_file(path=paths["baseline"]),
        "contract_sha256": contract_sha256,
        "decision_register_sha256": sha256_file(path=paths["decisions"]),
        "foundation_verification_receipt_sha256": sha256_file(
            path=paths["foundation_verification"]
        ),
        "issue_body_sha256": contract_sha256,
        "legacy_semantic_producer_inventory_sha256": sha256_file(
            path=paths["legacy_inventory"]
        ),
        "parent_requirement_closure_hash": parent[
            "requirement_closure_hash"
        ],
        "semantic_runtime_versions_hash": content_hash(
            value=SEMANTIC_VERSIONS
        ),
        "source_strategy_baseline_receipt_sha256": sha256_file(
            path=paths["source_strategy"]
        ),
        "transfer_manifest_sha256": sha256_file(path=paths["transfer"]),
    }
    return {
        "requirement_id": register["requirement_id"],
        "issue_contract_revision": register["issue_contract_revision"],
        "hashes": hashes,
        "requirement_closure_hash": content_hash(value=hashes),
        "parent_requirement_id": PARENT_REQUIREMENT_ID,
        "parent_requirement_closure_hash": parent[
            "requirement_closure_hash"
        ],
        "baseline": baseline,
        "effective_decisions": decisions,
        "decision_chains": chains,
        "pending_decision_ids": pending_ids,
    }


def load_requirement_snapshot(*, snapshot_dir: Path) -> Dict[str, object]:
    """Load one of the two explicit supported Requirement snapshots.

    Args:
        snapshot_dir: Exact parent ``ai_first_v3_3_1`` or child
            ``issue_15_v1`` snapshot directory. Test copies may use another
            directory name because dispatch is by the bound requirement ID.

    Returns:
        Verified Requirement closure and effective Decision chains.

    Raises:
        RequirementError: On an unknown Requirement ID or invalid bytes.
    """
    baseline = _read_object(path=snapshot_dir / "baseline_manifest.json")
    if "requirement_id" not in baseline:
        raise RequirementError("Requirement baseline identity is missing")
    requirement_id = baseline["requirement_id"]
    if requirement_id == PARENT_REQUIREMENT_ID:
        return _load_ai_first_snapshot(snapshot_dir=snapshot_dir)
    if requirement_id == ISSUE_15_REQUIREMENT_ID:
        return _load_issue_15_snapshot(snapshot_dir=snapshot_dir)
    raise RequirementError(
        "Unsupported Requirement Snapshot: {}".format(requirement_id)
    )
