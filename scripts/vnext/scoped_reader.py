"""Separate successor scoped transport from full local Evidence authority.

No provider constructor/opener is reachable here. Audit answers, references and
synthetic Candidates are deliberately absent from the outbound request body.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from .canonical import canonical_json_bytes, content_hash, sha256_bytes
from .evidence import check_evidence
from .reader import validate_reader_output
from .reader_input import READER_SYSTEM_CONTRACT
from .source_scope import SourceScopeError, policy_choice, scope_tables
from .source_scope import validate_source_scope_manifest
from .table_payload import _compact_table, _decode_compact_table


class ScopedReaderError(ValueError):
    """Reject a scoped request/response that cannot replay on the full asset."""


@dataclass(frozen=True)
class PreparedScopedReaderRequest:
    """Immutable request bytes, independent of legacy PreparedReaderRequest."""

    request_bytes: bytes
    request_id: str
    source_scope_manifest_id: str
    requirement_closure_hash: str
    estimated_input_tokens: int


def prepare_scoped_reader_request(
    *, source_scope_manifest: Mapping, expected_manifest_id: str,
    requirement: Mapping, raw_blob: Mapping, source_reference: Mapping,
    full_derived_asset: Mapping, reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping,
) -> PreparedScopedReaderRequest:
    """Pack only certified original-order tables; never fall back to a filing."""
    scope = validate_source_scope_manifest(
        manifest=source_scope_manifest, expected_manifest_id=expected_manifest_id,
        requirement=requirement, raw_blob=raw_blob, source_reference=source_reference,
        full_derived_asset=full_derived_asset, reader_manifest=reader_manifest,
        task_contract=task_contract, evidence_authority_payload=evidence_authority_payload,
    )
    policy = policy_choice(requirement=requirement, kind="SOURCE_SCOPE_POLICY")
    if scope["fixture_class"] not in policy["positive_fixture_classes"]:
        raise ScopedReaderError("ZERO_CALL_FIXTURE: scoped provider planning is forbidden")
    selected = scope_tables(windows=scope["windows"], full_derived_asset=full_derived_asset)
    compact = [_compact_table(table=t) for t in selected]
    if [_decode_compact_table(compact=t) for t in compact] != selected:
        raise ScopedReaderError("Scoped compact round trip differs from full authority")
    body = {
        "record_type": "SCOPED_READER_REQUEST", "schema_version": 1,
        "artifact_requirement_generation": scope["artifact_requirement_generation"],
        "requirement_id": scope["requirement_id"],
        "requirement_closure_hash": scope["requirement_closure_hash"],
        "requirement_hashes": scope["requirement_hashes"],
        "source_scope_manifest_id": expected_manifest_id,
        "full_reader_input_manifest_id": reader_manifest["reader_input_manifest_id"],
        "source_reference_ids": list(reader_manifest["source_reference_ids"]),
        "full_derived_asset_id": full_derived_asset["derived_asset_id"],
        "system_contract": dict(READER_SYSTEM_CONTRACT),
        "task_contract": dict(task_contract),
        "window_binding": {
            "windows": scope["windows"],
            "ordered_table_ids": scope["ordered_table_ids"],
            "ordered_table_orders": scope["ordered_table_orders"],
            "ordered_grid_hashes": scope["ordered_grid_hashes"],
        },
        "untrusted_scoped_table_data": {
            "record_type": "SCOPED_TABLE_TRANSPORT", "schema_version": 1,
            "original_table_coordinates_preserved": True,
            "tables": compact,
        },
    }
    request_bytes = canonical_json_bytes(value=body)
    context = policy_choice(requirement=requirement, kind="TRANSPORT_RETRY_POLICY")
    if len(request_bytes) > context["context_ceiling_tokens"]:
        raise ScopedReaderError("SCOPED_CONTEXT_LIMIT: no full-document fallback")
    return PreparedScopedReaderRequest(
        request_bytes=request_bytes, request_id=content_hash(value=body),
        source_scope_manifest_id=expected_manifest_id,
        requirement_closure_hash=str(scope["requirement_closure_hash"]),
        estimated_input_tokens=len(request_bytes),
    )


def validate_scoped_reader_response(
    *, prepared_request: PreparedScopedReaderRequest, response_text: str,
    attempt_id: str, source_scope_manifest: Mapping,
    expected_manifest_id: str, requirement: Mapping, raw_blob: Mapping,
    source_reference: Mapping, full_derived_asset: Mapping,
    reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping,
) -> Dict[str, object]:
    """Certify an offline synthetic response with the existing native checker.

    The exact scoped request is verified separately. The full Reader payload
    passed to check_evidence is explicitly local Evidence authority, not a
    claim that the full filing was sent to a provider. No second value verifier
    or selector is introduced.
    """
    expected_request = prepare_scoped_reader_request(
        source_scope_manifest=source_scope_manifest,
        expected_manifest_id=expected_manifest_id, requirement=requirement,
        raw_blob=raw_blob, source_reference=source_reference,
        full_derived_asset=full_derived_asset, reader_manifest=reader_manifest,
        task_contract=task_contract, evidence_authority_payload=evidence_authority_payload,
    )
    if expected_request != prepared_request:
        raise ScopedReaderError("Scoped request bytes/identity differ")
    candidate = validate_reader_output(
        response_text=response_text, attempt_id=attempt_id,
        required_roles=task_contract["required_roles"],
        scope_contract=task_contract["scope_contract"],
        source_reference_ids=[source_reference["source_reference_id"]],
        derived_asset_ids=[full_derived_asset["derived_asset_id"]],
    )
    if candidate["disclosure_group"] != task_contract["disclosure_group"]:
        raise ScopedReaderError("Scoped response task/disclosure group differs")
    for claim in candidate["selected"].values():
        locators = [claim["locator"]]
        locators.extend(c["locator"] for c in claim["competing_candidates"])
        locators.extend(c["locator"] for c in claim["scope_evidence_locators"])
        if any(l["table_id"] not in source_scope_manifest["ordered_table_ids"]
               or l["derived_asset_id"] != full_derived_asset["derived_asset_id"]
               for l in locators):
            raise ScopedReaderError("Response locator leaves certified windows")
    evidence = check_evidence(
        candidate=candidate, derived_asset=full_derived_asset,
        reader_manifest=reader_manifest,
        reader_payload_body=evidence_authority_payload,
        source_references=[source_reference],
        identity_constraints=task_contract["identity_constraints"],
        scope_contract=task_contract["scope_contract"],
    )
    identity = {
        key: source_scope_manifest[key] for key in (
            "artifact_requirement_generation", "requirement_id",
            "requirement_closure_hash", "requirement_hashes",
            "task_contract_id", "task_contract_hash", "full_derived_asset_id",
        )
    }
    body = {
        "record_type": "SCOPED_OFFLINE_EXTRACTION_ATTEMPT", "schema_version": 1,
        **identity, "attempt_id": attempt_id,
        "source_scope_manifest_id": expected_manifest_id,
        "scoped_request_id": prepared_request.request_id,
        "request_sha256": sha256_bytes(content=prepared_request.request_bytes),
        "response_text": response_text,
        "response_sha256": sha256_bytes(content=response_text.encode("utf-8")),
        "candidate": candidate, "evidence": evidence,
        "evidence_authority_kind": "FULL_LOCAL_READER_INPUT_MANIFEST",
        "execution_mode": "OFFLINE_SYNTHETIC",
        "provider_call_count": 0, "paid_model_call_count": 0, "sec_call_count": 0,
        "actual_provider_usage": "NOT_RUN", "qualification_credit": "NONE",
    }
    return {**body, "scoped_attempt_id": content_hash(value=body)}


def replay_scoped_offline_attempt(*, attempt: Mapping,
                                  prepared_request: PreparedScopedReaderRequest,
                                  **authority) -> Dict[str, object]:
    """Rebuild the complete attempt, Candidate and Evidence graph from disk data."""
    actual = validate_scoped_reader_response(
        prepared_request=prepared_request, response_text=attempt["response_text"],
        attempt_id=attempt["attempt_id"], **authority,
    )
    if dict(attempt) != actual:
        raise ScopedReaderError("Scoped attempt/Candidate/Evidence identity differs")
    return actual
