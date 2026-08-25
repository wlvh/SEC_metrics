"""Build decision-neutral exact request comparison evidence offline."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

from .ai_adapter import approved_transport_policy, build_provider_request_body
from .canonical import atomic_write_json, canonical_json_bytes, content_hash
from .canonical import sha256_bytes, sha256_file, strict_json_file
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .requirements import load_requirement_snapshot
from .sources import load_raw_blob_bytes, raw_blob_record
from .sources import source_reference_record
from .table_context_attestation import ATTESTATION_POINTER
from .table_context_attestation import ATTESTATION_ROOT
from .table_context_attestation import ATTESTATION_RECORD_TYPE
from .table_context_attestation import (
    validate_table_context_feasibility_attestation,
)
from .table_context_measurement import _source_binding
from .table_grid import build_table_grid
from .table_payload import TABLE_PAYLOAD_SERIALIZATION_VERSION
from .table_qualification_freeze import load_table_qualification_matrix
from .table_task_contracts import resolve_table_task_contract


ANALYSIS_ROOT = Path(
    "artifacts/vnext/table_stage_c_evidence/"
    "sibling_request_context_analysis"
)
ANALYSIS_POINTER = Path(
    "artifacts/vnext/table_stage_c_evidence/"
    "current_sibling_request_context_analysis.json"
)
ANALYSIS_RECORD_TYPE = "LODGING_EXACT_REQUEST_CONTEXT_COMPARISON"
ANALYSIS_POINTER_TYPE = "LODGING_EXACT_REQUEST_CONTEXT_COMPARISON_POINTER"
_STATUS_KEY_SUFFIX = "_CONTEXT_STATUS"


class TableContextComparisonError(RuntimeError):
    """Report incomplete or non-exact offline comparison authority."""


def _fail(message: str) -> None:
    """Raise one fail-closed comparison error."""
    raise TableContextComparisonError(message)


def _minimal_differing_ranges(
    *, attested: bytes, sibling: bytes,
) -> Dict[str, object]:
    """Return the minimal enclosing unequal range in each exact byte string."""
    prefix = 0
    shared_limit = min(len(attested), len(sibling))
    while prefix < shared_limit and attested[prefix] == sibling[prefix]:
        prefix += 1
    suffix = 0
    suffix_limit = shared_limit - prefix
    while (
        suffix < suffix_limit
        and attested[len(attested) - suffix - 1]
        == sibling[len(sibling) - suffix - 1]
    ):
        suffix += 1
    attested_end = len(attested) - suffix
    sibling_end = len(sibling) - suffix

    def span(*, body: bytes, end: int) -> Dict[str, object]:
        """Describe one half-open exact byte span."""
        differing = body[prefix:end]
        return {
            "start": prefix,
            "end_exclusive": end,
            "length": len(differing),
            "sha256": sha256_bytes(content=differing),
        }

    return {
        "shared_prefix_bytes": prefix,
        "shared_prefix_sha256": sha256_bytes(content=attested[:prefix]),
        "shared_suffix_bytes": suffix,
        "shared_suffix_sha256": sha256_bytes(
            content=attested[len(attested) - suffix:] if suffix else b"",
        ),
        "attested_request_range": span(body=attested, end=attested_end),
        "sibling_request_range": span(body=sibling, end=sibling_end),
        "range_semantics": "MINIMAL_ENCLOSING_UNEQUAL_BYTE_RANGE",
    }


def _current_request_objects(
    *, repo_root: Path,
) -> Tuple[
    Dict[str, object], Dict[str, Dict[str, object]], Dict[str, bytes]
]:
    """Rebuild both current lodging task requests from shared source bytes."""
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    d07 = requirement["effective_decisions"]["D-07"]
    attestation = validate_table_context_feasibility_attestation(
        repo_root=repo_root,
    )
    family_id = str(attestation["family_id"])
    matrix = load_table_qualification_matrix(
        repo_root=repo_root, family_id=family_id,
    )
    entry = matrix["entries"][family_id]
    task_ids = list(entry["task_contract_ids"])
    if (
        len(task_ids) != 2
        or attestation["task_contract_id"] not in task_ids
    ):
        _fail("Lodging task comparison set is not exact")
    sibling_ids = [
        task_id for task_id in task_ids
        if task_id != attestation["task_contract_id"]
    ]
    if len(sibling_ids) != 1:
        _fail("Lodging sibling task is ambiguous")
    exception = d07["choice"]["measurement_exception"]
    source = _source_binding(
        repo_root=repo_root,
        matrix_entry=entry,
        exception=exception,
    )
    declaration = source["source_declaration"]
    raw = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=str(source["request_repo_relative_path"]),
        media_type=str(entry["source_media_type"]),
    )
    reference = source_reference_record(
        raw_blob=raw,
        company_id=str(declaration["company_id"]),
        source_url=str(source["source_url"]),
        accession=str(declaration["accession"]),
        document_name=str(declaration["document_name"]),
        source_role=str(source["source_role"]),
        request_attempt_id=str(source["request_attempt_id"]),
    )
    asset = build_table_grid(
        html_bytes=load_raw_blob_bytes(repo_root=repo_root, raw_blob=raw),
        parent_raw_asset_ids=[str(raw["raw_asset_id"])],
        storage_uri=(
            "artifacts/vnext/table_stage_c_evidence/"
            "lodging_context_comparison_derived_asset.json"
        ),
    )
    manifest = build_reader_input_manifest(
        derived_asset=asset,
        source_reference_ids=[str(reference["source_reference_id"])],
    )
    policy = approved_transport_policy(requirement=requirement)
    requests = {}
    bodies = {}
    for task_id in task_ids:
        task = resolve_table_task_contract(
            repo_root=repo_root,
            task_contract_id=str(task_id),
            family_id=family_id,
        )
        prepared = prepare_reader_request(
            manifest=manifest,
            derived_asset=asset,
            repo_root=repo_root,
            task_contract_id=str(task_id),
        )
        provider_body, provider_schema = build_provider_request_body(
            policy=policy,
            reader_request_bytes=prepared.request_bytes,
        )
        task_bytes = canonical_json_bytes(value=task)
        bodies[str(task_id)] = provider_body
        requests[str(task_id)] = {
            "task_contract_id": task_id,
            "task_contract_hash": task["catalog_task_contract_hash"],
            "task_contract_bytes_sha256": sha256_bytes(
                content=task_bytes,
            ),
            "task_contract_bytes": len(task_bytes),
            "task_spec_semantic_hash": task["task_spec_semantic_hash"],
            "prompt_hash": task["system_prompt_hash"],
            "output_schema_hash": task["output_schema_hash"],
            "reader_input_manifest_id": prepared.reader_input_manifest_id,
            "derived_asset_id": prepared.derived_asset_id,
            "expanded_grid_sha256": prepared.expanded_grid_sha256,
            "compact_payload_sha256": prepared.compact_payload_sha256,
            "serializer_version": prepared.table_payload_serialization_version,
            "serializer_hash": sha256_file(
                path=repo_root / "scripts/vnext/table_payload.py",
            ),
            "reader_request_body_sha256": sha256_bytes(
                content=prepared.request_bytes,
            ),
            "reader_request_body_bytes": len(prepared.request_bytes),
            "provider_output_schema_sha256": sha256_bytes(
                content=provider_schema,
            ),
            "provider_request_body_sha256": sha256_bytes(
                content=provider_body,
            ),
            "provider_request_body_bytes": len(provider_body),
            "provider": policy.provider,
            "model": policy.model,
            "api": policy.api,
        }
    attested_task_id = str(attestation["task_contract_id"])
    if (
        requests[attested_task_id]["provider_request_body_sha256"]
        != attestation["exact_provider_request_body_sha256"]
        or requests[attested_task_id]["provider_request_body_bytes"]
        != attestation["exact_provider_request_body_bytes"]
    ):
        _fail("Attested request no longer equals Stage C-B")
    authority = {
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "effective_d07_record_hash": content_hash(value=d07),
        "context_feasibility_attestation_id": attestation[
            "attestation_id"
        ],
        "source_measurement_evidence_id": attestation[
            "source_measurement_evidence_id"
        ],
        "family_id": family_id,
        "attested_task_contract_id": attested_task_id,
        "sibling_task_contract_id": str(sibling_ids[0]),
        "source_identity": copy.deepcopy(dict(declaration)),
        "source_id": reference["source_reference_id"],
        "source_repo_relative_path": source["request_repo_relative_path"],
        "source_sha256": source["request_body_sha256"],
        "table_payload_serialization_version": (
            TABLE_PAYLOAD_SERIALIZATION_VERSION
        ),
    }
    return authority, requests, bodies


def _component_comparison(
    *, attested: Mapping[str, object], sibling: Mapping[str, object],
) -> Sequence[Dict[str, object]]:
    """Compare exact shared and changed request-authority components."""
    components = (
        "reader_input_manifest_id",
        "derived_asset_id",
        "expanded_grid_sha256",
        "compact_payload_sha256",
        "serializer_version",
        "serializer_hash",
        "task_contract_hash",
        "task_contract_bytes_sha256",
        "task_spec_semantic_hash",
        "prompt_hash",
        "output_schema_hash",
        "provider_output_schema_sha256",
        "reader_request_body_sha256",
        "provider_request_body_sha256",
        "provider",
        "model",
        "api",
    )
    return [
        {
            "component": component,
            "status": (
                "SHARED_EXACT"
                if attested[component] == sibling[component]
                else "CHANGED_EXACT"
            ),
            "attested_value": attested[component],
            "sibling_value": sibling[component],
        }
        for component in components
    ]


def _attestation_inventory(*, repo_root: Path) -> Sequence[Dict[str, object]]:
    """List every immutable context attestation without treating stale as current."""
    root = repo_root / ATTESTATION_ROOT
    if root.is_symlink() or not root.is_dir():
        _fail("Context attestation inventory is unsafe")
    rows = []
    for path in sorted(root.iterdir(), key=lambda value: value.name):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            _fail("Context attestation inventory entry is unsafe")
        value = strict_json_file(path=path)
        if type(value) is not dict:
            _fail("Context attestation inventory entry is invalid")
        body = {
            key: item for key, item in value.items()
            if key != "attestation_id"
        }
        if (
            value.get("record_type") != ATTESTATION_RECORD_TYPE
            or value.get("attestation_id") != content_hash(value=body)
        ):
            _fail("Context attestation inventory identity differs")
        rows.append({
            "attestation_id": value["attestation_id"],
            "task_contract_id": value["task_contract_id"],
            "provider_request_body_sha256": value[
                "exact_provider_request_body_sha256"
            ],
            "source_measurement_evidence_id": value[
                "source_measurement_evidence_id"
            ],
        })
    return rows


def build_sibling_request_context_analysis(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Build the exact no-egress sibling-task comparison and honest status."""
    authority, requests, bodies = _current_request_objects(repo_root=repo_root)
    attested_id = str(authority["attested_task_contract_id"])
    sibling_id = str(authority["sibling_task_contract_id"])
    attested = requests[attested_id]
    sibling = requests[sibling_id]
    inventory = _attestation_inventory(repo_root=repo_root)
    matching_sibling_attestations = [
        row["attestation_id"]
        for row in inventory
        if row["task_contract_id"] == sibling_id
        and row["provider_request_body_sha256"]
        == sibling["provider_request_body_sha256"]
    ]
    sibling_task = resolve_table_task_contract(
        repo_root=repo_root,
        task_contract_id=sibling_id,
        family_id=str(authority["family_id"]),
    )
    roles = sibling_task["required_roles"]
    if type(roles) is not list or len(roles) != 1:
        _fail("Sibling task role identity is invalid")
    status_key = str(roles[0]).upper() + _STATUS_KEY_SUFFIX
    if not status_key.endswith(_STATUS_KEY_SUFFIX):
        _fail("Sibling context status key is invalid")
    comparison = _component_comparison(
        attested=attested, sibling=sibling,
    )
    changed = [
        row["component"] for row in comparison
        if row["status"] == "CHANGED_EXACT"
    ]
    body = {
        "schema_version": 1,
        "record_type": ANALYSIS_RECORD_TYPE,
        "analysis_status": "DECISION_NEUTRAL_OFFLINE_COMPLETE",
        "authority": authority,
        "requests": {
            "ATTESTED_MEASUREMENT_REQUEST": attested,
            "UNATTESTED_SIBLING_REQUEST": sibling,
        },
        "exact_request_comparison": {
            "provider_request_hash_equal": False,
            "provider_request_byte_length_equal": (
                attested["provider_request_body_bytes"]
                == sibling["provider_request_body_bytes"]
            ),
            "component_comparison": comparison,
            "changed_component_names": changed,
            "minimal_differing_byte_ranges": _minimal_differing_ranges(
                attested=bodies[attested_id],
                sibling=bodies[sibling_id],
            ),
            "task_contract_equal": (
                attested["task_contract_hash"]
                == sibling["task_contract_hash"]
            ),
            "prompt_equal": (
                attested["prompt_hash"] == sibling["prompt_hash"]
            ),
            "output_schema_equal": (
                attested["output_schema_hash"]
                == sibling["output_schema_hash"]
            ),
        },
        "context_attestation_inventory": {
            "current_pointer_path": ATTESTATION_POINTER.as_posix(),
            "available_attestations": inventory,
            "matching_sibling_attestation_ids": (
                matching_sibling_attestations
            ),
        },
        status_key: "EXACT_CONTEXT_EVIDENCE_REQUIRED",
        "reason": "NO_SOUND_CROSS_TASK_TOKEN_BOUND",
        "token_upper_bound_assessment": {
            "repository_authorized_sound_cross_task_upper_bound_exists": False,
            "sibling_actual_prompt_tokens": "NOT_MEASURED",
            "inference_from_attested_task": "FORBIDDEN",
            "inference_from_byte_length": "FORBIDDEN",
            "inference_from_shared_source_or_family": "FORBIDDEN",
            "second_measurement_selected": False,
            "family_wide_exception_selected": False,
        },
        "authorization_state": {
            "measurement_authorization_permanently_consumed": True,
            "additional_measurement_authorized": False,
            "qualification_authorized": False,
        },
        "egress_counts": {
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_SEC_egress_count": 0,
        },
    }
    return {**body, "analysis_id": content_hash(value=body)}


def write_sibling_request_context_analysis(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Persist immutable comparison evidence and its current pointer."""
    analysis = build_sibling_request_context_analysis(repo_root=repo_root)
    digest = str(analysis["analysis_id"]).split(":", maxsplit=1)[1]
    relative = ANALYSIS_ROOT / (digest + ".json")
    path = repo_root / relative
    if path.exists():
        if strict_json_file(path=path) != analysis:
            _fail("Sibling context analysis content-address collision")
    else:
        atomic_write_json(path=path, value=analysis)
    pointer_body = {
        "schema_version": 1,
        "record_type": ANALYSIS_POINTER_TYPE,
        "analysis_id": analysis["analysis_id"],
        "analysis_path": relative.as_posix(),
        "source_measurement_evidence_id": analysis["authority"][
            "source_measurement_evidence_id"
        ],
    }
    pointer = {**pointer_body, "pointer_id": content_hash(value=pointer_body)}
    atomic_write_json(path=repo_root / ANALYSIS_POINTER, value=pointer)
    return {
        "analysis_id": analysis["analysis_id"],
        "analysis_path": relative.as_posix(),
        "pointer_id": pointer["pointer_id"],
        "status": next(
            value for key, value in analysis.items()
            if key.endswith(_STATUS_KEY_SUFFIX)
        ),
        "reason": analysis["reason"],
        "egress_counts": analysis["egress_counts"],
    }


def validate_sibling_request_context_analysis(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Rebuild and validate the current comparison without network action."""
    pointer = strict_json_file(path=repo_root / ANALYSIS_POINTER)
    if type(pointer) is not dict:
        _fail("Sibling context analysis pointer is invalid")
    pointer_body = {
        key: value for key, value in pointer.items() if key != "pointer_id"
    }
    if pointer.get("pointer_id") != content_hash(value=pointer_body):
        _fail("Sibling context analysis pointer identity differs")
    relative = Path(str(pointer.get("analysis_path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        _fail("Sibling context analysis path is unsafe")
    analysis = strict_json_file(path=repo_root / relative)
    if type(analysis) is not dict:
        _fail("Sibling context analysis is invalid")
    body = {
        key: value for key, value in analysis.items() if key != "analysis_id"
    }
    if (
        analysis.get("analysis_id") != content_hash(value=body)
        or pointer.get("analysis_id") != analysis.get("analysis_id")
        or analysis != build_sibling_request_context_analysis(
            repo_root=repo_root,
        )
    ):
        _fail("Sibling context analysis differs from current authority")
    return copy.deepcopy(dict(analysis))
