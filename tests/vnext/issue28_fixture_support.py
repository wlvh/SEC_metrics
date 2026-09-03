"""Temporary authority fixtures for PR #29 rework; no live fixtures or credit."""

import copy
import json
import shutil
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_issue15_authority import copy_test_repository
from vnext.canonical import atomic_write_json, content_hash, sha256_file
from vnext.canonical import sha256_bytes, strict_json_file
from vnext.requirements import load_requirement_snapshot
from vnext import requirement_profile_v1, requirement_profile_v2


def file_binding(path: Path) -> dict:
    return {"sha256": sha256_file(path=path), "size": path.stat().st_size}


def copy_profile_repository(*, directory: str) -> Path:
    parent = copy_test_repository(temp_dir=directory)
    root = parent.parent.parent
    source = REPO_ROOT / "requirements/issue_28_v1"
    destination = root / "requirements/issue_28_v1"
    shutil.copytree(source, destination)
    baseline = strict_json_file(path=destination / "baseline_manifest.json")
    for relative in [
        *baseline["execution_authority"]["files"],
        "scripts/vnext/requirement_profile.py",
        "scripts/vnext/requirement_profile_v1.py",
        "scripts/vnext/requirement_profile_v2.py",
    ]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, path)
    return destination


def refresh_snapshot(*, snapshot: Path, bind_execution: bool = False) -> None:
    baseline_path = snapshot / "baseline_manifest.json"
    baseline = strict_json_file(path=baseline_path)
    for relative in baseline["snapshot_files"]:
        baseline["snapshot_files"][relative] = file_binding(snapshot / relative)
    engine = (
        requirement_profile_v2
        if baseline["requirement_generation"] == "PROFILE_DRIVEN_V2"
        else requirement_profile_v1
    )
    engine_file = Path(engine.__file__)
    baseline["validator"] = {
        "path": "scripts/vnext/" + engine_file.name,
        "semantic_version": engine.PROFILE_SEMANTIC_VERSION,
        "sha256": sha256_file(path=engine_file),
        "dependencies": (
            {
                "scripts/vnext/requirement_profile_v1.py": file_binding(
                    Path(requirement_profile_v1.__file__)
                )
            }
            if engine is requirement_profile_v2
            else {}
        ),
    }
    if bind_execution:
        root = snapshot.parent.parent
        baseline["execution_authority"]["files"] = {
            relative: file_binding(root / relative)
            for relative in baseline["execution_authority"]["files"]
        }
    atomic_write_json(path=baseline_path, value=baseline)


def rebind_scoped_parent(*, repo_root: Path) -> Path:
    """Rebind only a disposable one-company fixture, never repository history."""
    snapshot = repo_root / "requirements/issue_28_v1"
    parent_dir = repo_root / "requirements/issue_15_v1"
    parent = load_requirement_snapshot(snapshot_dir=parent_dir)
    baseline_path = snapshot / "baseline_manifest.json"
    baseline = strict_json_file(path=baseline_path)
    bindings = {path.name: file_binding(path) for path in sorted(parent_dir.iterdir())}
    baseline["parent"].update(
        hashes=parent["hashes"],
        requirement_closure_hash=parent["requirement_closure_hash"],
        snapshot_files=bindings,
        snapshot_binding_hash=content_hash(value=bindings),
    )
    atomic_write_json(path=baseline_path, value=baseline)
    transfer_path = snapshot / "transfer_manifest.json"
    transfer = strict_json_file(path=transfer_path)
    transfer.update(
        parent_requirement_closure_hash=parent["requirement_closure_hash"],
        parent_snapshot_files=bindings,
        parent_snapshot_binding_hash=content_hash(value=bindings),
    )
    for row in transfer["fragments"]:
        row["parent_effective_record_hash"] = content_hash(
            value=parent["effective_decisions"][row["decision_id"]]
        )
    atomic_write_json(path=transfer_path, value=transfer)
    refresh_snapshot(snapshot=snapshot, bind_execution=True)
    return snapshot


def evolve_to_v2(*, snapshot: Path, successor_requirement_id: str = "issue_28_v2") -> Path:
    """Add synthetic R5 policy using V2 engine and a separate revision identity."""
    old = load_requirement_snapshot(snapshot_dir=snapshot)
    successor = snapshot.parent / successor_requirement_id
    shutil.copytree(snapshot, successor)
    contract = successor / "CONTRACT.md"
    contract.write_text(
        contract.read_text().replace("issue_28_v1", successor_requirement_id), encoding="utf-8"
    )
    baseline_path = successor / "baseline_manifest.json"
    baseline = strict_json_file(path=baseline_path)
    baseline.update(
        requirement_id=successor_requirement_id,
        requirement_generation="PROFILE_DRIVEN_V2",
        contract_revision=successor_requirement_id.upper(),
        supersedes_requirement={
            "requirement_id": old["requirement_id"],
            "requirement_closure_hash": old["requirement_closure_hash"],
        },
    )
    register_path = successor / "decision_register.json"
    register = strict_json_file(path=register_path)
    register.update(requirement_id=successor_requirement_id,
                    issue_contract_revision=successor_requirement_id.upper())
    scope = copy.deepcopy(
        next(d for d in register["decisions"] if d["decision_id"] == "S-R4-SCOPE")
    )
    scope["decision_id"] = "S-R5-SCOPE"
    scope["choice"].update(ratchet_id="R5", metric_ids=["B06", "B13", "C03", "C04"])
    register["decisions"].append(scope)
    pending = register["pending_decisions"][0]
    choice = {
        "kind": "METRIC_PRODUCT_SEMANTICS",
        "b06_economic_meaning": "TEST_ONLY_APPROVED_B06",
        "b13_economic_meaning": "TEST_ONLY_APPROVED_B13",
    }
    approval = {
        "record_type": "OWNER_POLICY_APPROVAL",
        "scope": "POLICY_CONTENT_ONLY",
        "decision_id": pending["decision_id"],
        "choice_hash": content_hash(value=choice),
        "supersedes_record_hash": content_hash(value=pending),
    }
    text = json.dumps(approval, sort_keys=True)
    source = {
        "source_id": "OWNER_R5_TEST_ONLY",
        "kind": "OWNER_POLICY_SUCCESSOR",
        "source_url": "https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-9999999999",
        "source_sha256": sha256_bytes(content=text.encode()),
        "author": "test-only:owner",
        "published_at_utc": "2026-09-03T00:00:00Z",
        "text": text,
    }
    baseline["policy_evidence"].append(source)
    baseline["policy_evidence"].sort(key=lambda row: row["source_id"])
    register["decisions"].append(
        {
            "decision_id": pending["decision_id"],
            "status": "APPROVED",
            "choice": choice,
            "approved_by": source["author"],
            "approved_at_utc": source["published_at_utc"],
            "supersedes_decision_id": content_hash(value=pending),
            "evidence": source["source_url"],
            "policy_provenance": {
                "source_id": source["source_id"],
                "section": "POLICY_CONTENT_ONLY",
                "scope": "POLICY_CONTENT_ONLY",
            },
        }
    )
    extra_invariants = []
    for old_id, new_id in (
        ("S-LIVE-CALL-BOUND", "S-R5-LIVE-CALL-BOUND"),
        ("S-PUBLICATION-PREDECESSOR", "S-R5-PUBLICATION-PREDECESSOR"),
        ("S-SOURCE-SCOPE", "S-R5-SOURCE-SCOPE"),
    ):
        # These are synthetic evolution-test policies, not real R5 grants.
        later_choice = copy.deepcopy(
            next(
                d["choice"] for d in register["decisions"] if d["decision_id"] == old_id
            )
        )
        later_choice["ratchet_id"] = "R5"
        if "required_predecessor" in later_choice:
            later_choice.update(
                required_predecessor="publication_" + "d" * 64,
                failure_active_publication="publication_" + "d" * 64,
            )
        root = {
            "decision_id": new_id,
            "status": "PENDING_EXTERNAL_APPROVAL",
            "effect": "TEST_ONLY_EVOLUTION_POLICY",
            "required_choice_fields": ["kind"],
            "evidence": "TEST_ONLY",
        }
        register["pending_decisions"].append(root)
        later_approval = {
            "record_type": "OWNER_POLICY_APPROVAL",
            "scope": "POLICY_CONTENT_ONLY",
            "decision_id": new_id,
            "choice_hash": content_hash(value=later_choice),
            "supersedes_record_hash": content_hash(value=root),
        }
        later_text = json.dumps(later_approval, sort_keys=True)
        later_source = {
            **source,
            "source_id": "OWNER_TEST_" + new_id,
            "text": later_text,
            "source_sha256": sha256_bytes(content=later_text.encode()),
        }
        baseline["policy_evidence"].append(later_source)
        register["decisions"].append(
            {
                "decision_id": new_id,
                "status": "APPROVED",
                "choice": later_choice,
                "approved_by": later_source["author"],
                "approved_at_utc": later_source["published_at_utc"],
                "supersedes_decision_id": content_hash(value=root),
                "evidence": later_source["source_url"],
                "policy_provenance": {
                    "source_id": later_source["source_id"],
                    "section": "POLICY_CONTENT_ONLY",
                    "scope": "POLICY_CONTENT_ONLY",
                },
            }
        )
        extra_invariants.append(
            {"invariant_id": "INV-" + new_id[2:], "decision_id": new_id}
        )
    baseline["policy_evidence"].sort(key=lambda row: row["source_id"])
    atomic_write_json(path=register_path, value=register)
    profile_path = successor / "invariant_profile.json"
    profile = strict_json_file(path=profile_path)
    profile.update(requirement_id=successor_requirement_id, profile_semantic_version="2")
    profile["invariants"].extend(
        [
            {"invariant_id": "INV-R5-SCOPE", "decision_id": "S-R5-SCOPE"},
            {
                "invariant_id": "INV-R5-B06-B13-MEANING",
                "decision_id": pending["decision_id"],
            },
        ]
    )
    profile["invariants"].extend(extra_invariants)
    profile["invariants"].sort(key=lambda row: row["invariant_id"])
    atomic_write_json(path=profile_path, value=profile)
    transfer_path = successor / "transfer_manifest.json"
    transfer = strict_json_file(path=transfer_path)
    transfer["requirement_id"] = successor_requirement_id
    atomic_write_json(path=transfer_path, value=transfer)
    atomic_write_json(path=baseline_path, value=baseline)
    refresh_snapshot(snapshot=successor, bind_execution=True)
    return successor
