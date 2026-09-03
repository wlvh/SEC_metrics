"""Bind audited R4 windows to complete, unchanged local Evidence authority.

This additive record is not a legacy ReaderInputManifest, an execution grant,
or a selector. A fixture authority must pin its content ID before it is loaded.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Dict, Mapping, Sequence

from .canonical import canonical_json_bytes, content_hash
from .canonical import sha256_bytes, strict_json_loads
from .evidence import check_evidence, _verify_payload
from .reader import validate_reader_output
from .reader_input import verify_reader_table_set
from .records import EXPLICIT_ARTIFACT_GENERATION, validate_record
from .requirement_profile import validate_execution_authority
from .scope_contract import scope_contract_hash
from .sources import load_raw_blob_bytes, resolve_repository_file
from .specs import compile_spec_file
from .table_grid import resolve_cell
from .table_payload import _validate_expanded_table
from .table_task_contracts import RUNTIME_TASK_CONTRACT_FIELDS
from .table_task_contracts import resolve_table_task_contract


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
REFERENCE_FIELDS = frozenset({"status", "value", "unit", "period", "scope", "evidence"})
TABLE_AUDIT_FIELDS = frozenset({
    "table_id", "grid_sha256", "disposition", "evidence",
    "candidate_locator_ids", "candidate_dispositions",
})
CANDIDATE_DISPOSITION_FIELDS = frozenset({"locator", "disposition", "evidence", "unresolved"})
NAVIGATION_FIELDS = frozenset({
    "path_id", "method", "source_sha256", "anchor", "evidence", "target_locator",
})
LAYOUT_FIELDS = frozenset({
    "kind", "source_cik", "source_sha256", "comparison_source_cik",
    "comparison_source_sha256", "differences", "evidence",
})
CLOSED_CANDIDATE_DISPOSITIONS = frozenset({
    "TARGET", "DIFFERENT_PERIOD", "DIFFERENT_SCOPE", "DIFFERENT_UNIT",
    "QUALITATIVE_ONLY", "NOT_TARGET_METRIC", "AMBIGUOUS_EXCLUDED",
    "DUPLICATE_EQUIVALENT", "REFERENCE_ONLY",
})
POSITIVE_REFERENCE_STATUSES = frozenset({
    "INDEPENDENT_LEGACY_ANCHOR", "NO_INDEPENDENT_LEGACY_ANCHOR",
    "SYNTHETIC_INTERFACE_REFERENCE",
})


def _exact(value: object, fields: frozenset, label: str) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise SourceScopeError(label + " fields are not exact")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise SourceScopeError(label + " is empty or is not text")
    return value


def _hash(value: object, label: str, *, content_id: bool = True) -> str:
    pattern = r"sha256:[0-9a-f]{64}" if content_id else r"[0-9a-f]{64}"
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise SourceScopeError(label + " is not an exact SHA-256 identity")
    return value


def validate_scope_requirement_identity(*, artifact: Mapping,
                                        requirement: Mapping) -> None:
    """Bind the additive subtype without invoking historical type dispatch."""
    identity = {
        "artifact_requirement_generation": EXPLICIT_ARTIFACT_GENERATION,
        "requirement_id": requirement.get("requirement_id"),
        "requirement_closure_hash": requirement.get("requirement_closure_hash"),
        "requirement_hashes": requirement.get("hashes"),
    }
    if (requirement.get("artifact_requirement_generation") != EXPLICIT_ARTIFACT_GENERATION
            or type(identity["requirement_id"]) is not str
            or re.fullmatch(r"issue_[0-9]+_v[1-9][0-9]*", identity["requirement_id"]) is None
            or type(identity["requirement_hashes"]) is not dict
            or not identity["requirement_hashes"]
            or content_hash(value=identity["requirement_hashes"])
            != identity["requirement_closure_hash"]
            or any(artifact.get(key) != value for key, value in identity.items())):
        raise SourceScopeError("Scope successor generation/Requirement identity differs")


def read_scope_repository_bytes(*, path: Path, repo_root: Path,
                                expected_sha256: str = None,
                                expected_size: int = None) -> bytes:
    """Read an exact regular repository file, rejecting every symlink component.

    Optional byte pins belong to a separately validated containing artifact;
    they cannot be supplied by the file they claim to authenticate.
    """
    absolute = path if path.is_absolute() else repo_root / path
    try:
        relative = absolute.relative_to(repo_root).as_posix()
        regular = resolve_repository_file(repo_root=repo_root, repo_relative_path=relative)
        before = regular.stat()
        data = regular.read_bytes()
        after = regular.stat()
    except (ValueError, OSError) as error:
        raise SourceScopeError("Scope artifact is not a regular repository file") from error
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise SourceScopeError("Scope artifact changed during read")
    if expected_sha256 is not None:
        _hash(expected_sha256, "Scope file hash", content_id=False)
        if sha256_bytes(content=data) != expected_sha256:
            raise SourceScopeError("Scope file byte hash differs")
    if expected_size is not None and (type(expected_size) is not int
                                      or expected_size < 0 or len(data) != expected_size):
        raise SourceScopeError("Scope file byte size differs")
    return data


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
    if (type(tables) is not list or not tables
            or any(type(table) is not dict or type(table.get("order")) is not int
                   or table["order"] != index for index, table in enumerate(tables))
            or len({table.get("table_id") for table in tables}) != len(tables)):
        raise SourceScopeError("Full DerivedAsset original table order is invalid")
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


def _validate_audit_closure(*, manifest: Mapping, full_derived_asset: Mapping,
                            source_reference: Mapping, positive: bool) -> None:
    """Close every explicitly audited candidate, including in-window duplicates.

    This is an integrity check over source-specific audit facts, not a generic
    discovery algorithm or an alternative economic-value verifier. The parent
    fixture authority must independently pin the complete audit's content ID.
    """
    table_audit = manifest["table_audit"]
    if type(table_audit) is not list or len(table_audit) != len(full_derived_asset["tables"]):
        raise SourceScopeError("Full document audit census is not exact")
    outside, targets, seen = [], [], set()
    for row, table in zip(table_audit, full_derived_asset["tables"]):
        _exact(row, TABLE_AUDIT_FIELDS, "Table audit")
        if (row["table_id"] != table["table_id"] or row["grid_sha256"] != table["grid_sha256"]
                or row["disposition"] not in {"TARGET", "CANDIDATES_CLOSED", "NO_TARGET_CANDIDATE"}):
            raise SourceScopeError("Table audit order/hash/disposition differs")
        _text(row["evidence"], "Table audit evidence")
        if type(row["candidate_dispositions"]) is not list or type(row["candidate_locator_ids"]) is not list:
            raise SourceScopeError("Table candidate census is not an ordered array")
        identities = []
        row_targets = []
        for item in row["candidate_dispositions"]:
            _exact(item, CANDIDATE_DISPOSITION_FIELDS, "Candidate disposition")
            if item["disposition"] not in CLOSED_CANDIDATE_DISPOSITIONS or item["unresolved"] is not False:
                raise SourceScopeError("Candidate remains unresolved or has no typed disposition")
            _text(item["evidence"], "Candidate disposition evidence")
            resolve_cell(derived_asset=full_derived_asset, locator=item["locator"])
            if item["locator"]["table_id"] != table["table_id"]:
                raise SourceScopeError("Candidate census names a different table")
            locator_id = content_hash(value=item["locator"])
            if locator_id in seen:
                raise SourceScopeError("Candidate audit contains duplicate locators")
            seen.add(locator_id)
            identities.append(locator_id)
            if item["disposition"] == "TARGET":
                row_targets.append(item["locator"])
                targets.append(item["locator"])
            if table["table_id"] not in manifest["ordered_table_ids"]:
                outside.append(item)
        if row["candidate_locator_ids"] != identities:
            raise SourceScopeError("Table candidate locator exact set/order differs")
        expected = "TARGET" if row_targets else "CANDIDATES_CLOSED" if identities else "NO_TARGET_CANDIDATE"
        if row["disposition"] != expected:
            raise SourceScopeError("Table audit summary differs from its candidate census")
    if (type(manifest["out_of_window_candidates"]) is not list
            or manifest["out_of_window_candidates"] != outside):
        raise SourceScopeError("Out-of-window candidate closure is not the exact audited projection")
    if targets != ([manifest["target_locator"]] if positive else []):
        raise SourceScopeError("Table audit target exact set differs")
    reference = _exact(manifest["reference"], REFERENCE_FIELDS, "Reference")
    _text(reference["evidence"], "Reference evidence")
    if type(reference["scope"]) is not dict or any(type(k) is not str or type(v) is not str
                                                   for k, v in reference["scope"].items()):
        raise SourceScopeError("Reference scope is invalid")
    if positive:
        if reference["status"] not in POSITIVE_REFERENCE_STATUSES:
            raise SourceScopeError("Positive reference status is invalid")
        for field in ("value", "unit", "period"):
            _text(reference[field], "Reference " + field)
    elif (reference["status"] != "NOT_APPLICABLE" or reference["scope"] != {}
          or any(reference[field] is not None for field in ("value", "unit", "period"))):
        raise SourceScopeError("Zero-call reference cannot claim a certified value")
    paths = manifest["navigation_paths"]
    if type(paths) is not list or len(paths) != 2:
        raise SourceScopeError("Two independent audit navigation paths are required")
    for path, path_id in zip(paths, ("A", "B")):
        _exact(path, NAVIGATION_FIELDS, "Navigation path")
        if (path["path_id"] != path_id or path["source_sha256"] != manifest["source_sha256"]
                or path["target_locator"] != manifest["target_locator"]):
            raise SourceScopeError("Navigation source/path/target identity differs")
        for field in ("method", "anchor", "evidence"):
            _text(path[field], "Navigation " + field)
    if paths[0]["method"] == paths[1]["method"]:
        raise SourceScopeError("Audit navigation methods are not independent")
    layout = _exact(manifest["material_layout_proof"], LAYOUT_FIELDS, "Material layout proof")
    _text(layout["evidence"], "Material layout evidence")
    url_match = re.fullmatch(r"https://www\.sec\.gov/Archives/edgar/data/([0-9]+)/[0-9]{18}/[^/?#]+",
                            source_reference["source_url"])
    if (url_match is None or layout["source_cik"] != str(int(url_match.group(1)))
            or layout["source_sha256"] != manifest["source_sha256"]
            or type(layout["differences"]) is not list
            or any(type(item) is not str or not item for item in layout["differences"])
            or len(set(layout["differences"])) != len(layout["differences"])):
        raise SourceScopeError("Material layout source/difference binding differs")
    if layout["kind"] == "MATERIAL_ALTERNATE_LAYOUT":
        if (not positive or type(layout["comparison_source_cik"]) is not str
                or not layout["comparison_source_cik"].isdigit()
                or int(layout["comparison_source_cik"]) <= 0
                or str(int(layout["comparison_source_cik"])) == layout["source_cik"]
                or layout["comparison_source_sha256"] == manifest["source_sha256"]
                or len(layout["differences"]) < 2):
            raise SourceScopeError("Alternate layout is not a materially different issuer/source")
        _hash(layout["comparison_source_sha256"], "Comparison source", content_id=False)
    elif layout["kind"] in {"PRODUCTION_BASELINE", "SYNTHETIC_INTERFACE_ONLY", "ZERO_CALL_CLASSIFICATION"}:
        if (layout["comparison_source_cik"] is not None
                or layout["comparison_source_sha256"] is not None or layout["differences"]):
            raise SourceScopeError("Non-alternate fixture cannot claim a comparison source")
        if positive != (layout["kind"] != "ZERO_CALL_CLASSIFICATION"):
            raise SourceScopeError("Fixture class and layout proof kind differ")
    else:
        raise SourceScopeError("Material layout proof kind is invalid")
    if manifest["fixture_class"] == "POSITIVE_ALTERNATE_LAYOUT" and layout["kind"] != "MATERIAL_ALTERNATE_LAYOUT":
        raise SourceScopeError("Alternate positive lacks material-layout proof")


def _native_evidence(*, candidate: object, full_derived_asset: Mapping,
                     reader_manifest: Mapping, evidence_authority_payload: Mapping,
                     source_reference: Mapping, task_contract: Mapping) -> object:
    if evidence_authority_payload.get("task_contract") != task_contract:
        raise SourceScopeError("Full Evidence task contract differs")
    if candidate is None:
        _verify_payload(reader_manifest=reader_manifest,
                        reader_payload_body=evidence_authority_payload,
                        derived_asset=full_derived_asset)
        return None
    validate_record(record=candidate)
    if candidate["disclosure_group"] != task_contract["disclosure_group"]:
        raise SourceScopeError("Synthetic Candidate task/disclosure group differs")
    claims = list(candidate["selected"].values())
    if not claims:
        raise SourceScopeError("Synthetic Candidate has no selected claim")
    # Reuse the native Reader for its complete nested schema. The source audit
    # stores a synthetic Candidate, not a claimed provider response, so this
    # canonical reconstruction verifies shape/semantics but never claims to
    # reproduce the audit producer's assistant-output byte hash.
    native = validate_reader_output(
        response_text=canonical_json_bytes(value={
            "disclosure_group": candidate["disclosure_group"],
            "table_locator": {key: claims[0]["locator"][key]
                              for key in ("derived_asset_id", "table_id")},
            "candidates": claims,
            "unresolved_competing_claims": candidate["unresolved_competing_claims"],
        }).decode("utf-8"),
        attempt_id=candidate["attempt_id"], required_roles=task_contract["required_roles"],
        scope_contract=task_contract["scope_contract"],
        source_reference_ids=[source_reference["source_reference_id"]],
        derived_asset_ids=[full_derived_asset["derived_asset_id"]],
    )
    if any(native[key] != value for key, value in candidate.items()
           if key != "assistant_output_sha256"):
        raise SourceScopeError("Synthetic Candidate differs from native Reader semantics")
    return check_evidence(
        candidate=candidate, derived_asset=full_derived_asset,
        reader_manifest=reader_manifest,
        reader_payload_body=evidence_authority_payload,
        source_references=[source_reference],
        identity_constraints=task_contract["identity_constraints"],
        scope_contract=task_contract["scope_contract"],
    )


def _task_canonical_unit(*, task_contract: Mapping, repo_root: Path) -> str:
    """Use the existing MetricSpec compiler, not a second unit interpretation."""
    if len(task_contract["metric_spec_paths"]) != 1:
        raise SourceScopeError("Scoped task requires one bound MetricSpec")
    path = resolve_repository_file(repo_root=repo_root,
                                   repo_relative_path=task_contract["metric_spec_paths"][0])
    compiled = compile_spec_file(path=path, dependency_specs={})
    if (task_contract["metric_spec_semantic_hashes"] != [compiled["spec_semantic_hash"]]
            or task_contract["metric_spec_closure_hashes"] != [compiled["spec_closure_hash"]]
            or task_contract["metric_ids"] != [compiled["compiled"]["metric_id"]]):
        raise SourceScopeError("Task MetricSpec semantic/closure identity differs")
    return compiled["compiled"]["canonical_unit"]


def build_source_scope_manifest(
    *, requirement: Mapping, raw_blob: Mapping, source_reference: Mapping,
    full_derived_asset: Mapping, reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping, audit: Mapping, repo_root: Path = None,
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
        repo_root=repo_root,
    )


def validate_source_scope_manifest(
    *, manifest: Mapping, expected_manifest_id: str, requirement: Mapping,
    raw_blob: Mapping, source_reference: Mapping, full_derived_asset: Mapping,
    reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping, repo_root: Path = None,
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
    _hash(expected_manifest_id, "Scope manifest")
    validate_scope_requirement_identity(artifact=manifest, requirement=requirement)
    for artifact, record_type in ((raw_blob, "RAW_BLOB"), (source_reference, "SOURCE_REFERENCE"),
                                   (full_derived_asset, "DERIVED_ASSET"),
                                   (reader_manifest, "READER_INPUT_MANIFEST")):
        validate_record(record=artifact)
        if artifact["record_type"] != record_type:
            raise SourceScopeError("Scope local Evidence authority subtype differs")
    _exact(task_contract, frozenset(RUNTIME_TASK_CONTRACT_FIELDS), "Runtime task contract")
    if (task_contract["system_prompt_hash"] != content_hash(value=task_contract["system_prompt"])
            or task_contract["scope_contract_hash"] != scope_contract_hash(contract=task_contract["scope_contract"])
            or evidence_authority_payload.get("task_contract") != task_contract):
        raise SourceScopeError("Full Evidence task contract differs")
    for table in full_derived_asset["tables"]:
        _validate_expanded_table(table=table)
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
    if manifest["fixture_class"] not in classes:
        raise SourceScopeError("Fixture classification is invalid")
    _text(manifest["fixture_id"], "Fixture identity")
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
    positive = manifest["fixture_class"] in source_policy["positive_fixture_classes"]
    if positive:
        locator = manifest["target_locator"]
        resolve_cell(derived_asset=full_derived_asset, locator=locator)
        if locator["table_id"] not in manifest["ordered_table_ids"]:
            raise SourceScopeError("Positive target is outside the certified windows")
    elif manifest["target_locator"] is not None or manifest["synthetic_candidate"] is not None:
        raise SourceScopeError("Zero-call fixture cannot retain a certified Candidate/target")
    _validate_audit_closure(manifest=manifest, full_derived_asset=full_derived_asset,
                            source_reference=source_reference, positive=positive)
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
        claim = next(iter(claims.values()))
        if (list(expected_evidence["normalized_values"].values()) != [manifest["reference"]["value"]]
                or manifest["reference"]["period"] != claim["claimed_period"]
                or manifest["reference"]["scope"] != expected_evidence["normalized_scope"]):
            raise SourceScopeError("Reference value/period/scope differs from native Evidence")
        if manifest["reference"]["unit"] != _task_canonical_unit(
                task_contract=task_contract,
                repo_root=repo_root or Path(__file__).resolve().parents[2]):
            raise SourceScopeError("Reference canonical unit differs from bound MetricSpec")
    return deepcopy(dict(manifest))


def load_source_scope_manifest(*, path: Path, repo_root: Path,
                               expected_manifest_id: str,
                               expected_sha256: str = None,
                               expected_size: int = None, **authority) -> Dict[str, object]:
    """Load a strict regular scope record and recheck current execution inputs.

    The caller supplies its once-loaded Requirement and full source/asset data;
    loading a child scope never reconstructs historical parent authority. The
    separate final disk replay owns full source-to-asset reconstruction.
    """
    data = read_scope_repository_bytes(path=path, repo_root=repo_root,
                                       expected_sha256=expected_sha256, expected_size=expected_size)
    try:
        value = strict_json_loads(text=data.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise SourceScopeError("Scope artifact is not strict UTF-8 JSON") from error
    load_raw_blob_bytes(repo_root=repo_root, raw_blob=authority["raw_blob"])
    validate_execution_authority(repo_root=repo_root, requirement=authority["requirement"])
    expected_task = resolve_table_task_contract(
        repo_root=repo_root, task_contract_id=authority["task_contract"]["task_contract_id"])
    if authority["task_contract"] != expected_task:
        raise SourceScopeError("Scope task contract differs from repository authority")
    return validate_source_scope_manifest(manifest=value,
                                          expected_manifest_id=expected_manifest_id,
                                          repo_root=repo_root,
                                          **authority)
