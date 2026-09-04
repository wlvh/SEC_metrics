"""Mechanically generate the unactivated five-file v2 policy proposal.

This generator reads immutable parent bytes and recorded owner comments. It
does not edit any historical snapshot, activate a closure, or call a network.
Derived transfer rows and hash bindings are rebuilt together; CONTRACT.md is
maintained separately and must already exist at the one allowed destination.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from git_workspace import sanitized_git_environment  # noqa: E402
from vnext.canonical import atomic_write_json, content_hash, sha256_file, strict_json_file  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402
from vnext import requirement_profile_v1 as v1  # noqa: E402
from vnext import requirement_profile_v3 as v3  # noqa: E402

REQUIREMENT_ID = "issue_28_v2"
PARENT_ID = "issue_28_v1"
BASE_COMMIT = "c45338567700e3048f4cf32d251369e4521e9444"
BASE_TREE = "0b8ccaf6b6b708b2c07b8f4ce1d5dd178638493a"
NEW_COMPONENTS = (
    ("S-A03-COMPOSITE-SCOPE", "OWNER_A03_POLICY", "a03_scope_policy"),
    ("S-A03-ALTERNATE-PERIOD", "OWNER_A03_POLICY", "a03_alternate_period_policy"),
    ("S-A12-COMPOSITE-SCOPE", "OWNER_PRB_POLICY", "a12_scope_policy"),
    ("S-A13-INTERNATIONAL-NET-REVENUE", "OWNER_PRB_POLICY", "a13_product_semantics"),
    ("S-BOUNDED-PARSER-RESOURCE", "OWNER_PRB_POLICY", "parser_resource_policy"),
    ("S-OFFLINE-FIXTURE-ACQUISITION", "OWNER_PRB_POLICY", "sec_acquisition"),
    ("S-SEC-CONTACT-AUTHORITY", "OWNER_SEC_CONTACT_POLICY", "sec_contact_authority"),
)


def binding(path: Path) -> dict:
    return {"sha256": sha256_file(path=path), "size": path.stat().st_size}


def approved_record(*, decision_id: str, choice: dict, source: dict,
                    section: str, supersedes=None) -> dict:
    return {"decision_id": decision_id, "status": "APPROVED", "choice": choice,
        "approved_by": source["author"], "approved_at_utc": source["published_at_utc"],
        "supersedes_decision_id": supersedes, "evidence": source["source_url"],
        "policy_provenance": {"source_id": source["source_id"], "section": section,
                              "scope": "POLICY_CONTENT_ONLY"}}


def execution_python_dependencies(*, repo_root: Path, seeds) -> set[str]:
    """Bind local static imports, including imports inside guarded entrypoints.

    Subprocess workers are explicit seeds. This is a closure inventory, not a
    claim that all imported modules are reachable provider callers.
    """
    pending, paths = list(seeds), set()
    while pending:
        relative = pending.pop()
        if relative in paths:
            continue
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("Execution Python dependency is absent or unsafe: " + relative)
        paths.add(relative)
        syntax = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(syntax):
            candidates = []
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    parent = path.parent
                    for _ in range(node.level - 1):
                        parent = parent.parent
                    if node.module:
                        candidates.append(parent.joinpath(*node.module.split(".")))
                    else:
                        candidates.extend(parent / alias.name for alias in node.names)
                elif node.module:
                    candidates.extend((repo_root / "scripts").joinpath(*node.module.split("."))
                                      for _ in [None])
                    candidates.append(repo_root.joinpath(*node.module.split(".")))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    candidates.append((repo_root / "scripts").joinpath(*alias.name.split(".")))
                    candidates.append(repo_root.joinpath(*alias.name.split(".")))
            for candidate in candidates:
                for local in (candidate.with_suffix(".py"), candidate / "__init__.py"):
                    if local.is_file() and local.is_relative_to(repo_root):
                        pending.append(local.relative_to(repo_root).as_posix())
    return paths


def write_proposal(*, repo_root: Path) -> dict:
    """Write only the unactivated issue_28_v2 generated files; return closure."""
    destination = repo_root / "requirements" / REQUIREMENT_ID
    if destination.is_symlink() or not (destination / "CONTRACT.md").is_file():
        raise ValueError("The explicit v2 contract directory is absent or unsafe")
    for path in (repo_root / "docs/evidence").glob("*.json"):
        document = strict_json_file(path=path)
        if (document.get("record_type") == "REQUIREMENT_TRANSITION_ACTIVATION"
                and document.get("requirement_id") == REQUIREMENT_ID):
            raise ValueError("An activated Requirement cannot be regenerated")
    parent_dir = repo_root / "requirements" / PARENT_ID
    parent = load_requirement_snapshot(snapshot_dir=parent_dir)
    old_register = strict_json_file(path=parent_dir / "decision_register.json")
    sources = deepcopy(parent["baseline"]["policy_evidence"])
    for source_id, filename in (("OWNER_PRB_POLICY", "issue_28_prb_policy_revision.json"),
                                ("OWNER_A03_POLICY", "issue_28_a03_policy_revision.json"),
                                ("OWNER_SEC_CONTACT_POLICY", "issue_28_sec_contact_authority.json")):
        evidence = strict_json_file(path=repo_root / "docs/evidence" / filename)
        sources.append({"source_id": source_id, "kind": v3.OWNER_COMMENT_KIND,
            "source_url": evidence["owner_comment_url"], "source_sha256": evidence["body_sha256"],
            "author": evidence["author"], "published_at_utc": evidence["published_at_utc"],
            "text": evidence["raw_body"], "evidence_path": "docs/evidence/" + filename})
    sources.sort(key=lambda row: row["source_id"])
    by_source = {s["source_id"]: s for s in sources}
    records = deepcopy(old_register["decisions"])
    for decision_id, source_id, component in NEW_COMPONENTS:
        source = by_source[source_id]
        document = json.loads(source["text"])
        choice = (v3.sec_contact_policy_choice(document=document) if component == "sec_contact_authority"
                  else {"kind": v3.COMMENT_COMPONENT_KINDS[component], **document[component]})
        if component == "a03_alternate_period_policy":
            choice["metric_id"] = "A03"
        records.append(approved_record(decision_id=decision_id, choice=choice,
                                       source=source, section=component))
    inherited = parent["effective_decisions"]["S-INHERITED-SEMANTICS"]
    obligations = [r for r in inherited["choice"]["obligations"]
                   if not (r["decision_id"] == "D-32" and r["source_path"] == "/single_table_locator_invariant")]
    records.append(approved_record(decision_id="S-INHERITED-SEMANTICS",
        choice={"kind": "PARENT_POLICY_CARRY_FORWARD", "obligations": obligations,
                "single_table_scope_rule": v3.single_table_scope_rule()},
        source=by_source["OWNER_A03_POLICY"], section="a03_scope_policy",
        supersedes=v1.decision_record_hash(decision=inherited)))
    register = {"schema_version": 2, "record_type": "REQUIREMENT_DECISION_REGISTER",
        "requirement_id": REQUIREMENT_ID, "issue_contract_revision": "ISSUE_28_V2",
        "decisions": records, "pending_decisions": deepcopy(old_register["pending_decisions"])}
    effective, _ = v1.resolve_decision_chains(decisions=records + register["pending_decisions"])
    profile = {"schema_version": 1, "record_type": "REQUIREMENT_INVARIANT_PROFILE",
        "requirement_id": REQUIREMENT_ID, "profile_semantic_version": "3",
        "invariants": sorted([{"invariant_id": "INV-" + decision_id.removeprefix("S-"),
                                "decision_id": decision_id} for decision_id, row in effective.items()
                               if row["status"] == "APPROVED"], key=lambda row: row["invariant_id"])}
    parent_files = {name: binding(parent_dir / name) for name in sorted(v1.PROFILE_SNAPSHOT_FILES)}
    fragments = []
    for decision_id, decision in sorted(parent["effective_decisions"].items()):
        if decision["status"] != "APPROVED":
            continue
        for source_path, value in sorted(v1.choice_fragments(value=decision["choice"]).items()):
            target_path, disposition, mode = source_path, "CARRY_FORWARD", "EXACT_VALUE"
            rationale = "Preserve the exact parent effective policy fragment."
            if decision_id == "S-INHERITED-SEMANTICS" and source_path.startswith("/obligations/"):
                pieces = source_path.split("/")
                obligation = decision["choice"]["obligations"][int(pieces[2])]
                if obligation not in obligations:
                    disposition, mode = "SUPERSEDED", "REPLACED_POLICY"
                    target_path = "/single_table_scope_rule"
                    rationale = ("Replace only the unconditional D-32 scope clause with an explicit default-same-table rule "
                                 "and owner-approved A03/A12 dimensional exceptions; values and scales stay in-table.")
                else:
                    pieces[2] = str(obligations.index(obligation))
                    target_path = "/".join(pieces)
            fragments.append({"decision_id": decision_id, "source_path": source_path,
                "source_value_hash": content_hash(value=value),
                "parent_effective_record_hash": v1.decision_record_hash(decision=decision),
                "disposition": disposition, "successor_decision_id": decision_id,
                "successor_path": target_path, "transfer_mode": mode, "rationale": rationale})
    counts = Counter(row["disposition"] for row in fragments)
    transfer = {"schema_version": 3, "record_type": "REQUIREMENT_TRANSFER_MANIFEST",
        "requirement_id": REQUIREMENT_ID, "parent_requirement_id": PARENT_ID,
        "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "parent_snapshot_files": parent_files,
        "parent_snapshot_binding_hash": content_hash(value=parent_files),
        "fragments": fragments,
        "fragment_classification_counts": {key: counts[key] for key in sorted(v1.TRANSFER_DISPOSITIONS)},
        "historical_material": deepcopy(parent["transfer"]["historical_material"]),
        "pending_decision_transfers": [{"decision_id": key, "disposition": "CARRY_FORWARD",
            "parent_record_hash": v1.decision_record_hash(decision=row), "qualification_credit": "NONE"}
            for key, row in parent["effective_decisions"].items() if row["status"] == "PENDING_EXTERNAL_APPROVAL"]}
    baseline = deepcopy(parent["baseline"])
    baseline.update({"requirement_id": REQUIREMENT_ID, "requirement_generation": v3.PROFILE_REQUIREMENT_GENERATION,
        "contract_revision": "ISSUE_28_V2", "created_at_utc": by_source["OWNER_SEC_CONTACT_POLICY"]["published_at_utc"],
        "repository": {"identity": "wlvh/SEC_metrics", "commit": BASE_COMMIT, "tree": BASE_TREE},
        "parent": {"requirement_id": PARENT_ID, "requirement_closure_hash": parent["requirement_closure_hash"],
            "hashes": parent["hashes"], "snapshot_files": parent_files,
            "snapshot_binding_hash": content_hash(value=parent_files),
            "snapshot_git_tree": subprocess.run(["git", "--no-replace-objects", "-C", str(repo_root),
                "rev-parse", "HEAD:requirements/" + PARENT_ID], env=sanitized_git_environment(),
                capture_output=True, text=True, check=True).stdout.strip()},
        "supersedes_requirement": {"requirement_id": PARENT_ID,
                                   "requirement_closure_hash": parent["requirement_closure_hash"]},
        "activation_state": "NOT_ACTIVATED", "policy_evidence": sources,
        "validator": {"path": "scripts/vnext/requirement_profile_v3.py", "semantic_version": "3",
            "sha256": sha256_file(path=repo_root / "scripts/vnext/requirement_profile_v3.py"),
            "dependencies": {relative: binding(repo_root / relative) for relative in (
                "scripts/vnext/requirement_profile_v1.py", "scripts/vnext/canonical.py")}}})
    execution_paths = set(parent["execution_authority"]["files"])
    execution_paths.update({"config/r4_task_contracts_v2.json", "config/r4_numeric_normalization_v1.json",
        "config/r4_fixture_acquisitions_v1.json", "docs/evidence/issue_28_prb_policy_revision.json",
        "docs/evidence/issue_28_a03_policy_revision.json", "docs/r4_offline/fixture_acquisition_receipt.json",
        "config/r4_fixture_company_authority_v1.json", "config/sec_config.json",
        "docs/evidence/issue_28_sec_contact_authority.json"})
    execution_paths.update(path.relative_to(repo_root).as_posix() for path in (repo_root / "catalog/r4_v2").glob("*.md"))
    for name in ("composite_scope", "source_scope", "scoped_reader", "offline_execution_session", "r4_materialization",
                 "r4_task_contracts", "r4_structured_sources", "r4_source_audit", "r4_fixture_authority",
                 "r4_offline_qualification", "resource_limits", "table_grid", "records", "reader", "evidence", "deterministic_router"):
        relative = "scripts/vnext/" + name + ".py"
        if (repo_root / relative).is_file():
            execution_paths.add(relative)
    for relative in ("config/r4_fixture_matrix_v1.json",):
        if (repo_root / relative).is_file():
            execution_paths.add(relative)
            matrix = strict_json_file(path=repo_root / relative)
            execution_paths.update(row["recipe_path"] for row in matrix["fixtures"])
    execution_paths.update(execution_python_dependencies(repo_root=repo_root, seeds={
        "scripts/vnext/live_scoped_reader.py", "scripts/vnext/r4_live_plan.py",
        "scripts/vnext/r4_live_authority.py", "scripts/vnext/r4_live_qualification.py",
        "scripts/vnext/r4_run_store.py", "scripts/vnext/requirement_profile_v3.py",
        "tools/vnext_r4_qualification.py", "tools/r4_materialization_worker.py",
    }))
    baseline["execution_authority"]["files"] = {name: binding(repo_root / name) for name in sorted(execution_paths)}
    for filename, payload in (("decision_register.json", register), ("invariant_profile.json", profile),
                              ("transfer_manifest.json", transfer)):
        atomic_write_json(path=destination / filename, value=payload)
    baseline["snapshot_files"] = {name: binding(destination / name) for name in sorted(v1.PROFILE_BOUND_FILES)}
    atomic_write_json(path=destination / "baseline_manifest.json", value=baseline)
    result = load_requirement_snapshot(snapshot_dir=destination)
    return {"requirement_id": REQUIREMENT_ID, "requirement_closure_hash": result["requirement_closure_hash"],
            "activation_state": result["activation_state"], "fragments": len(fragments),
            "fragment_counts": transfer["fragment_classification_counts"], "execution_files": len(execution_paths)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-proposal", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(write_proposal(repo_root=REPO_ROOT), sort_keys=True))


if __name__ == "__main__":
    main()
