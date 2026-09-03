"""Bind audited R4 windows to complete, unchanged local Evidence authority.

This additive record is not a legacy ReaderInputManifest, an execution grant,
or a selector. A fixture authority must pin its content ID before it is loaded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping, Sequence

from .canonical import canonical_json_bytes, content_hash, strict_json_file
from .evidence import check_evidence
from .reader_input import verify_reader_table_set
from .records import validate_record
from .sources import load_raw_blob_bytes, resolve_repository_file
from .table_grid import resolve_cell


class SourceScopeError(ValueError):
    """Reject an incomplete, unpinned or drifting source/window certificate."""


SCOPE_FIELDS = frozenset({
    "record_type", "schema_version", "source_scope_manifest_id",
    "artifact_requirement_generation", "requirement_id",
    "requirement_closure_hash", "requirement_hashes", "fixture_id",
    "fixture_class", "metric_id", "raw_blob", "source_reference",
    "source_sha256", "full_derived_asset_id", "full_reader_input_manifest_id",
    "task_contract_id", "task_contract_hash", "windows", "ordered_table_ids",
    "ordered_grid_hashes", "ordered_table_orders", "target_locator",
    "reference", "synthetic_candidate", "check_evidence_result",
    "estimated_tokens", "out_of_window_candidates", "table_audit",
    "material_layout_proof", "navigation_paths", "qualification_credit",
})
AUDIT_FIELDS = frozenset({
    "fixture_id", "fixture_class", "windows", "target_locator", "reference",
    "synthetic_candidate", "out_of_window_candidates", "table_audit",
    "material_layout_proof", "navigation_paths",
})


def _exact(value: object, fields: frozenset, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise SourceScopeError(label + " fields are not exact")
    return value


def policy_choice(*, requirement: Mapping[str, object], kind: str,
                  ratchet_id: str = "R4") -> Mapping[str, object]:
    """Select one evaluated policy instance, never a Python policy mirror."""
    choices = [
        item["choice"] for item in requirement["effective_decisions"].values()
        if item["status"] == "APPROVED" and item["choice"]["kind"] == kind
        and item["choice"].get("ratchet_id", ratchet_id) == ratchet_id
    ]
    if len(choices) != 1:
        raise SourceScopeError("Policy instance is absent or ambiguous: " + kind)
    return choices[0]


def scope_tables(*, windows: Sequence[Mapping[str, int]],
                 full_derived_asset: Mapping[str, object]) -> list:
    """Resolve one/two non-overlapping continuous original-order windows."""
    if type(windows) is not list or not 1 <= len(windows) <= 2:
        raise SourceScopeError("A scope requires one or two continuous windows")
    tables = full_derived_asset["tables"]
    selected = []
    previous_end = -1
    for window in windows:
        _exact(window, frozenset({"start_order", "end_order"}), "Window")
        start, end = window["start_order"], window["end_order"]
        if (type(start) is not int or type(end) is not int
                or not 0 <= start <= end < len(tables)
                or start <= previous_end):
            raise SourceScopeError("Window overlap/order/range differs")
        selected.extend(tables[start:end + 1])
        previous_end = end
    return selected


def _native_evidence(*, candidate: object, full_derived_asset: Mapping,
                     reader_manifest: Mapping, evidence_authority_payload: Mapping,
                     source_reference: Mapping, task_contract: Mapping) -> object:
    if candidate is None:
        return None
    if evidence_authority_payload.get("task_contract") != task_contract:
        raise SourceScopeError("Full Evidence task contract differs")
    return check_evidence(
        candidate=candidate, derived_asset=full_derived_asset,
        reader_manifest=reader_manifest,
        reader_payload_body=evidence_authority_payload,
        source_references=[source_reference],
        identity_constraints=task_contract["identity_constraints"],
        scope_contract=task_contract["scope_contract"],
    )


def build_source_scope_manifest(
    *, requirement: Mapping, raw_blob: Mapping, source_reference: Mapping,
    full_derived_asset: Mapping, reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping, audit: Mapping,
) -> Dict[str, object]:
    """Certify explicit audit coordinates using the existing Evidence Checker.

    The full payload here is a LOCAL_EVIDENCE_AUTHORITY representation. It is
    never labeled as the scoped outbound request and is never sent by this API.
    """
    _exact(audit, AUDIT_FIELDS, "Scope audit")
    selected = scope_tables(windows=audit["windows"],
                            full_derived_asset=full_derived_asset)
    evidence = _native_evidence(
        candidate=audit["synthetic_candidate"], full_derived_asset=full_derived_asset,
        reader_manifest=reader_manifest,
        evidence_authority_payload=evidence_authority_payload,
        source_reference=source_reference, task_contract=task_contract,
    )
    body = {
        "record_type": "SOURCE_SCOPE_MANIFEST", "schema_version": 1,
        "artifact_requirement_generation": requirement["artifact_requirement_generation"],
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "requirement_hashes": dict(requirement["hashes"]),
        **dict(audit), "metric_id": task_contract["metric_ids"][0],
        "raw_blob": dict(raw_blob), "source_reference": dict(source_reference),
        "source_sha256": str(raw_blob["raw_asset_id"])[7:],
        "full_derived_asset_id": full_derived_asset["derived_asset_id"],
        "full_reader_input_manifest_id": reader_manifest["reader_input_manifest_id"],
        "task_contract_id": task_contract["task_contract_id"],
        "task_contract_hash": task_contract["catalog_task_contract_hash"],
        "ordered_table_ids": [t["table_id"] for t in selected],
        "ordered_grid_hashes": [t["grid_sha256"] for t in selected],
        "ordered_table_orders": [t["order"] for t in selected],
        "check_evidence_result": evidence,
        "estimated_tokens": {
            "method": "WINDOW_GRID_UTF8_BYTE_UPPER_BOUND",
            "value": len(canonical_json_bytes(value=selected)),
            "actual_provider_usage": "NOT_RUN",
        },
        "qualification_credit": "NONE_OFFLINE_SYNTHETIC",
    }
    record = {**body, "source_scope_manifest_id": content_hash(value=body)}
    return validate_source_scope_manifest(
        manifest=record, expected_manifest_id=record["source_scope_manifest_id"],
        requirement=requirement, raw_blob=raw_blob, source_reference=source_reference,
        full_derived_asset=full_derived_asset, reader_manifest=reader_manifest,
        task_contract=task_contract,
        evidence_authority_payload=evidence_authority_payload,
    )


def validate_source_scope_manifest(
    *, manifest: Mapping, expected_manifest_id: str, requirement: Mapping,
    raw_blob: Mapping, source_reference: Mapping, full_derived_asset: Mapping,
    reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping,
) -> Dict[str, object]:
    """Replay a pinned scope; re-signing a tampered record cannot change the pin."""
    _exact(manifest, SCOPE_FIELDS, "SourceScopeManifest")
    body = {k: v for k, v in manifest.items() if k != "source_scope_manifest_id"}
    if (manifest["record_type"] != "SOURCE_SCOPE_MANIFEST"
            or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1
            or manifest["source_scope_manifest_id"] != expected_manifest_id
            or content_hash(value=body) != expected_manifest_id):
        raise SourceScopeError("Scope content identity differs from fixture authority")
    for artifact in (raw_blob, source_reference, full_derived_asset, reader_manifest):
        validate_record(record=artifact)
    verify_reader_table_set(manifest=reader_manifest, derived_asset=full_derived_asset)
    bindings = {
        "artifact_requirement_generation": requirement["artifact_requirement_generation"],
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "requirement_hashes": requirement["hashes"],
        "raw_blob": raw_blob, "source_reference": source_reference,
        "source_sha256": str(raw_blob["raw_asset_id"])[7:],
        "full_derived_asset_id": full_derived_asset["derived_asset_id"],
        "full_reader_input_manifest_id": reader_manifest["reader_input_manifest_id"],
        "task_contract_id": task_contract["task_contract_id"],
        "task_contract_hash": task_contract["catalog_task_contract_hash"],
        "qualification_credit": "NONE_OFFLINE_SYNTHETIC",
    }
    if any(manifest[k] != value for k, value in bindings.items()):
        raise SourceScopeError("Scope source/asset/task/Requirement binding differs")
    if (source_reference["raw_asset_id"] != raw_blob["raw_asset_id"]
            or full_derived_asset["parent_raw_asset_ids"] != [raw_blob["raw_asset_id"]]
            or reader_manifest["source_reference_ids"] != [source_reference["source_reference_id"]]):
        raise SourceScopeError("Scope full source authority differs")
    ratchet = policy_choice(requirement=requirement, kind="RATCHET_SCOPE")
    source_policy = policy_choice(requirement=requirement, kind="SOURCE_SCOPE_POLICY")
    if (task_contract["metric_ids"] != [manifest["metric_id"]]
            or manifest["metric_id"] not in ratchet["metric_ids"]):
        raise SourceScopeError("Task is not in the exact R4 metric set")
    classes = source_policy["positive_fixture_classes"] + source_policy["zero_call_fixture_classes"]
    if manifest["fixture_class"] not in classes or not manifest["fixture_id"]:
        raise SourceScopeError("Fixture classification is invalid")
    selected = scope_tables(windows=manifest["windows"], full_derived_asset=full_derived_asset)
    for field, key in (("ordered_table_ids", "table_id"),
                       ("ordered_grid_hashes", "grid_sha256"),
                       ("ordered_table_orders", "order")):
        if manifest[field] != [table[key] for table in selected]:
            raise SourceScopeError("Scope table exact set/order/hash differs")
    expected_estimate = {
        "method": "WINDOW_GRID_UTF8_BYTE_UPPER_BOUND",
        "value": len(canonical_json_bytes(value=selected)),
        "actual_provider_usage": "NOT_RUN",
    }
    if manifest["estimated_tokens"] != expected_estimate:
        raise SourceScopeError("Scope deterministic token estimate differs")
    table_audit = manifest["table_audit"]
    if type(table_audit) is not list or [
        (row.get("table_id"), row.get("grid_sha256")) for row in table_audit
    ] != [(t["table_id"], t["grid_sha256"]) for t in full_derived_asset["tables"]]:
        raise SourceScopeError("Full document audit census is not exact")
    if any(not row.get("disposition") or not row.get("evidence") for row in table_audit):
        raise SourceScopeError("Document audit has an unexplained table")
    if type(manifest["out_of_window_candidates"]) is not list:
        raise SourceScopeError("Out-of-window closure is not an ordered list")
    for item in manifest["out_of_window_candidates"]:
        if (not item.get("disposition") or not item.get("evidence")
                or item.get("unresolved") is not False
                or item["locator"]["table_id"] in manifest["ordered_table_ids"]):
            raise SourceScopeError("Out-of-window candidate remains ambiguous")
        resolve_cell(derived_asset=full_derived_asset, locator=item["locator"])
    positive = manifest["fixture_class"] in source_policy["positive_fixture_classes"]
    if positive:
        locator = manifest["target_locator"]
        resolve_cell(derived_asset=full_derived_asset, locator=locator)
        if locator["table_id"] not in manifest["ordered_table_ids"]:
            raise SourceScopeError("Positive target is outside the certified windows")
        if not isinstance(manifest["reference"], dict) or not manifest["reference"].get("status"):
            raise SourceScopeError("Positive reference status is absent")
        if not isinstance(manifest["material_layout_proof"], dict):
            raise SourceScopeError("Material-layout proof is absent")
        if type(manifest["navigation_paths"]) is not list or len(manifest["navigation_paths"]) != 2:
            raise SourceScopeError("Two independent audit navigation paths are required")
        if len({content_hash(value=p) for p in manifest["navigation_paths"]}) != 2:
            raise SourceScopeError("Audit navigation paths are duplicated")
    expected_evidence = _native_evidence(
        candidate=manifest["synthetic_candidate"], full_derived_asset=full_derived_asset,
        reader_manifest=reader_manifest, evidence_authority_payload=evidence_authority_payload,
        source_reference=source_reference, task_contract=task_contract,
    )
    if manifest["check_evidence_result"] != expected_evidence:
        raise SourceScopeError("Native Evidence replay differs")
    if positive and (expected_evidence is None or expected_evidence["status"] != "PASS"
                     or expected_evidence["system_approval_eligible"] is not True):
        raise SourceScopeError("Positive fixture lacks auto-certified Evidence PASS")
    if positive:
        claims = manifest["synthetic_candidate"]["selected"]
        if (list(claims) != task_contract["required_roles"]
                or any(c["locator"] != manifest["target_locator"] for c in claims.values())):
            raise SourceScopeError("Synthetic Candidate is not the certified target")
    return dict(manifest)


def load_source_scope_manifest(*, path: Path, repo_root: Path,
                               expected_manifest_id: str, **authority) -> Dict[str, object]:
    """Load a regular repository record and recheck actual immutable source bytes."""
    relative = path.relative_to(repo_root).as_posix()
    regular = resolve_repository_file(repo_root=repo_root, repo_relative_path=relative)
    value = strict_json_file(path=regular)
    load_raw_blob_bytes(repo_root=repo_root, raw_blob=authority["raw_blob"])
    return validate_source_scope_manifest(manifest=value,
                                          expected_manifest_id=expected_manifest_id,
                                          **authority)
