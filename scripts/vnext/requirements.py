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
SNAPSHOT_FILES = {
    "baseline": "baseline_manifest.json",
    "decisions": "decision_register.json",
    "fsd": "FSD.md",
    "issue": "ISSUE_CONTRACT.md",
    "r3_addendum": "ISSUE_CONTRACT_R3_ADDENDUM.md",
    "legacy_inventory": "legacy_path_inventory.json",
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


def load_requirement_snapshot(*, snapshot_dir: Path) -> Dict[str, object]:
    """Verify exact Requirement bytes and return their closure identity.

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
