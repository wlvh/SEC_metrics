"""Separate successor scoped transport from full local Evidence authority.

No provider constructor/opener is reachable here. Audit answers, references and
synthetic Candidates are deliberately absent from the outbound request body.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
from .evidence import check_evidence, OfflineEvidenceContext, _plain_owned
from .evidence import check_evidence_in_offline_session, RAW_LABEL_POLICY
from .r4_label_policy import label_policy as bound_label_policy, SOURCE_LABEL_POLICY
from .reader import validate_reader_output, validate_source_bound_reader_output
from .reader_input import READER_SYSTEM_CONTRACT
from .records import validate_record
from .source_scope import SourceScopeError, policy_choice, scope_tables
from .source_scope import load_source_scope_manifest, read_scope_repository_bytes
from .source_scope import validate_source_scope_manifest, validate_scope_requirement_identity
from .sources import load_raw_blob_bytes
from .table_payload import _compact_table, _decode_compact_table


class ScopedReaderError(ValueError):
    """Reject a scoped request/response that cannot replay on the full asset."""


IDENTITY_FIELDS = frozenset({
    "artifact_requirement_generation", "requirement_id", "requirement_closure_hash",
    "requirement_hashes", "source_scope_manifest_id", "fixture_id", "fixture_class",
    "source_sha256", "full_derived_asset_id", "full_reader_input_manifest_id",
    "task_contract_id", "task_contract_hash",
})
PLAN_FIELDS = IDENTITY_FIELDS | frozenset({
    "record_type", "schema_version", "scoped_plan_id", "raw_asset_id", "source_reference_ids",
    "window_binding", "task_spec_semantic_hash", "output_schema_hash", "system_prompt_hash",
    "planning_mode", "live_authorization", "provider_paid_sec_authorized",
})
REQUEST_FIELDS = IDENTITY_FIELDS | frozenset({
    "record_type", "schema_version", "scoped_plan_id", "raw_asset_id", "source_reference_ids",
    "system_contract", "task_contract", "window_binding", "untrusted_scoped_table_data",
})
ATTEMPT_FIELDS = IDENTITY_FIELDS | frozenset({
    "record_type", "schema_version", "scoped_attempt_id", "attempt_id", "scoped_plan_id",
    "plan_sha256", "scoped_request_id", "request_sha256", "response_text", "response_sha256",
    "candidate", "evidence", "candidate_evidence_link", "evidence_authority_kind",
    "execution_mode", "provider_call_count", "paid_model_call_count", "sec_call_count",
    "actual_provider_usage", "qualification_credit",
})
V2_IDENTITY_FIELDS = frozenset({"task_contract_generation", "source_bound_proof_id", "task_period"})
V2_REQUEST_FIELDS = REQUEST_FIELDS | V2_IDENTITY_FIELDS | frozenset({"scoped_transport_contract"})
ARTIFACT_FILENAMES = frozenset({
    "source_scope.json", "scoped_plan.json", "scoped_request.json", "scoped_attempt.json",
})
_SCOPED_CONTEXT_FACTORY = object()


def _exact(value: object, fields: frozenset, label: str) -> Mapping:
    if type(value) is not dict or set(value) != fields:
        raise ScopedReaderError(label + " fields are not exact")
    return value


def _identity(scope: Mapping) -> Dict[str, object]:
    identity = {field: scope[field] for field in IDENTITY_FIELDS}
    if scope["schema_version"] == 2:
        proof = scope["source_bound_proof"]
        identity.update(task_contract_generation=scope["task_contract_generation"],
                        source_bound_proof_id=None if proof is None else proof["source_bound_proof_id"],
                        task_period=scope["task_period"])
    return identity


def _window_binding(scope: Mapping) -> Dict[str, object]:
    return {field: scope[field] for field in (
        "windows", "ordered_table_ids", "ordered_table_orders", "ordered_grid_hashes")}


def _plan_body(*, scope: Mapping, raw_blob: Mapping,
               reader_manifest: Mapping, task_contract: Mapping) -> Dict[str, object]:
    body = {
        "record_type": "SCOPED_READER_PLAN", "schema_version": scope["schema_version"], **_identity(scope),
        "raw_asset_id": raw_blob["raw_asset_id"],
        "source_reference_ids": list(reader_manifest["source_reference_ids"]),
        "window_binding": _window_binding(scope),
        "task_spec_semantic_hash": task_contract["task_spec_semantic_hash"],
        "output_schema_hash": task_contract["output_schema_hash"],
        "system_prompt_hash": task_contract["system_prompt_hash"],
        "planning_mode": "OFFLINE_ONLY", "live_authorization": "NOT_AUTHORIZED",
        "provider_paid_sec_authorized": False,
    }
    return {**body, "scoped_plan_id": content_hash(value=body)}


@dataclass(frozen=True)
class PreparedScopedReaderRequest:
    """Immutable request bytes, independent of legacy PreparedReaderRequest."""

    request_bytes: bytes
    request_id: str
    source_scope_manifest_id: str
    requirement_closure_hash: str
    estimated_input_tokens: int
    plan_bytes: bytes
    plan_id: str


class OfflineScopedContext:
    """A source-local set of exact on-disk scope certificates, never a cache API."""

    __slots__ = ("_evidence", "_scope_files", "_scope_bytes", "_factory")

    def __init__(self, *, evidence_context, scope_files, scope_bytes, factory):
        if factory is not _SCOPED_CONTEXT_FACTORY:
            raise ScopedReaderError("Scoped context requires its verified factory")
        self._evidence = evidence_context
        self._scope_files = {key: dict(value) for key, value in scope_files.items()}
        self._scope_bytes = dict(scope_bytes)
        self._factory = factory

    def _scope(self, *, source_scope_manifest_id):
        if self._factory is not _SCOPED_CONTEXT_FACTORY or source_scope_manifest_id not in self._scope_files:
            raise ScopedReaderError("Scope is not in the verified process-local file set")
        binding = self._scope_files[source_scope_manifest_id]
        read_scope_repository_bytes(path=Path(binding["path"]), repo_root=self._evidence._repo_root,
                                    expected_sha256=binding["sha256"], expected_size=binding["size"])
        self._evidence._check_files()
        return strict_json_loads(text=self._scope_bytes[source_scope_manifest_id].decode("utf-8"))

    def _authority(self, *, source_scope_manifest_id):
        scope = self._scope(source_scope_manifest_id=source_scope_manifest_id)
        return scope, self._evidence._scope_authority(task_contract_id=scope["task_contract_id"])

    def _assert_inputs(self, *, scope, expected_manifest_id, requirement, raw_blob,
                       source_reference, full_derived_asset, reader_manifest,
                       task_contract, evidence_authority_payload, source_bytes, repo_root):
        certified = self._scope(source_scope_manifest_id=expected_manifest_id)
        expected = self._evidence._scope_authority(task_contract_id=certified["task_contract_id"])
        if (canonical_json_bytes(value=scope) != self._scope_bytes[expected_manifest_id]
                or requirement is not expected["requirement"]
                or full_derived_asset is not expected["full_derived_asset"]
                or reader_manifest is not expected["reader_manifest"]
                or raw_blob != expected["raw_blob"] or source_reference != expected["source_reference"]
                or task_contract != expected["task_contract"]
                or source_bytes != expected["source_bytes"] or repo_root != expected["repo_root"]):
            raise ScopedReaderError("Scoped session rejects caller-owned or drifting authority")
        self._evidence._owns(derived_asset=full_derived_asset, reader_manifest=reader_manifest,
                              reader_payload_body=evidence_authority_payload)
        return certified


def prepare_offline_scoped_context(*, evidence_context: OfflineEvidenceContext,
                                  scope_files: Mapping) -> OfflineScopedContext:
    """Verify each pinned scope once with the existing native validator/Checker."""
    if type(evidence_context) is not OfflineEvidenceContext or type(scope_files) is not dict or not scope_files:
        raise ScopedReaderError("Scoped context requires one explicit Evidence context and file set")
    encoded = {}
    for identity, binding in scope_files.items():
        _exact(binding, frozenset({"path", "sha256", "size"}), "Scoped session file binding")
        data = read_scope_repository_bytes(path=Path(binding["path"]), repo_root=evidence_context._repo_root,
                                           expected_sha256=binding["sha256"], expected_size=binding["size"])
        scope = strict_json_loads(text=data.decode("utf-8"))
        if type(scope) is not dict or scope.get("task_contract_id") not in evidence_context._tasks:
            raise ScopedReaderError("Scoped file task is not in the source-local context")
        authority = evidence_context._scope_authority(task_contract_id=scope["task_contract_id"])
        verified = validate_source_scope_manifest(manifest=scope, expected_manifest_id=identity,
            _offline_context=evidence_context, **authority)
        encoded[identity] = canonical_json_bytes(value=verified)
    return OfflineScopedContext(evidence_context=evidence_context, scope_files=scope_files,
                                scope_bytes=encoded, factory=_SCOPED_CONTEXT_FACTORY)


def build_scoped_reader_plan(*, source_scope_manifest: Mapping,
                            expected_manifest_id: str, **authority) -> Dict[str, object]:
    """Build an offline eligibility/identity plan, never an execution grant."""
    scope = validate_source_scope_manifest(manifest=source_scope_manifest,
        expected_manifest_id=expected_manifest_id, **authority)
    policy = policy_choice(requirement=authority["requirement"], kind="SOURCE_SCOPE_POLICY")
    if scope["fixture_class"] not in policy["positive_fixture_classes"]:
        raise ScopedReaderError("ZERO_CALL_FIXTURE: scoped provider planning is forbidden")
    return _plan_body(scope=scope, raw_blob=authority["raw_blob"],
                      reader_manifest=authority["reader_manifest"], task_contract=authority["task_contract"])


def prepare_scoped_reader_request(
    *, source_scope_manifest: Mapping, expected_manifest_id: str,
    requirement: Mapping, raw_blob: Mapping, source_reference: Mapping,
    full_derived_asset: Mapping, reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping,
    source_bytes: bytes = None, repo_root: Path = None,
    _verified_scope_context: OfflineScopedContext = None,
    _offline_evidence_context: OfflineEvidenceContext = None,
) -> PreparedScopedReaderRequest:
    """Pack only certified original-order tables; never fall back to a filing."""
    if _verified_scope_context is None:
        scope = validate_source_scope_manifest(manifest=source_scope_manifest, expected_manifest_id=expected_manifest_id,
            requirement=requirement, raw_blob=raw_blob, source_reference=source_reference,
            full_derived_asset=full_derived_asset, reader_manifest=reader_manifest,
            task_contract=task_contract, evidence_authority_payload=evidence_authority_payload,
            source_bytes=source_bytes, repo_root=repo_root, _offline_context=_offline_evidence_context)
    else:
        if type(_verified_scope_context) is not OfflineScopedContext:
            raise ScopedReaderError("Scoped context type is not exact")
        scope = _verified_scope_context._assert_inputs(scope=source_scope_manifest,
            expected_manifest_id=expected_manifest_id, requirement=requirement, raw_blob=raw_blob,
            source_reference=source_reference, full_derived_asset=full_derived_asset,
            reader_manifest=reader_manifest, task_contract=task_contract,
            evidence_authority_payload=evidence_authority_payload, source_bytes=source_bytes, repo_root=repo_root)
    policy = policy_choice(requirement=requirement, kind="SOURCE_SCOPE_POLICY")
    if scope["fixture_class"] not in policy["positive_fixture_classes"]:
        raise ScopedReaderError("ZERO_CALL_FIXTURE: scoped provider planning is forbidden")
    selected = scope_tables(windows=scope["windows"], full_derived_asset=full_derived_asset)
    evidence_session = _offline_evidence_context if _verified_scope_context is None else _verified_scope_context._evidence
    if evidence_session is None:
        compact = [_compact_table(table=t) for t in selected]
        if [_decode_compact_table(compact=t) for t in compact] != selected:
            raise ScopedReaderError("Scoped compact round trip differs from full authority")
    else:
        compact = [_plain_owned(evidence_session._transport["tables"][order])
                   for order in scope["ordered_table_orders"]]
    plan_body = _plan_body(scope=scope, raw_blob=raw_blob, reader_manifest=reader_manifest,
                           task_contract=task_contract)
    plan_bytes = canonical_json_bytes(value=plan_body)
    plan_id = plan_body["scoped_plan_id"]
    body = {
        "record_type": "SCOPED_READER_REQUEST", "schema_version": scope["schema_version"],
        **_identity(scope), "scoped_plan_id": plan_id,
        "raw_asset_id": raw_blob["raw_asset_id"],
        "source_reference_ids": list(reader_manifest["source_reference_ids"]),
        "system_contract": dict(READER_SYSTEM_CONTRACT),
        "task_contract": dict(task_contract),
        "window_binding": _window_binding(scope),
        "untrusted_scoped_table_data": {
            "record_type": "SCOPED_TABLE_TRANSPORT", "schema_version": 1,
            "original_table_coordinates_preserved": True,
            "tables": compact,
        },
    }
    if scope["schema_version"] == 2:
        proof = scope["source_bound_proof"]
        composite = None if proof is None else proof["composite_scope"]
        body["scoped_transport_contract"] = {
            "model_evidence_scope": "ORIGINAL_TABLE_WINDOWS_ONLY",
            "requested_period": scope["task_period"],
            "reported_unit_contract": next(iter(scope["synthetic_candidate"]["selected"].values()))["claimed_reported_unit"],
            "report_only_table_native_scope_locators": True,
            "do_not_fabricate_missing_scope_labels": True,
            "locally_proven_scope_dimensions": [] if composite is None else [
                item["dimension"] for item in composite["selected_scope_spans"]],
            "locally_proven_dimensions_may_be_omitted": True,
            "empty_scope_arrays_are_valid_for_locally_proven_dimensions": True,
            "unproven_scope_omissions_fail_closed": True,
            "missing_scope_instruction": "Omit unavailable table-native scope claims and locators; only the certified local source proof may supply those dimensions.",
            "preserve_exact_raw_value_without_rescaling": True,
            "do_not_invent_reported_unit_labels": True,
            "audit_reference_values_are_not_provider_input": True,
        }
        if bound_label_policy(requirement) == SOURCE_LABEL_POLICY:
            body["scoped_transport_contract"]["scope_label_representation_policy"] = SOURCE_LABEL_POLICY
    request_bytes = canonical_json_bytes(value=body)
    context = policy_choice(requirement=requirement, kind="TRANSPORT_RETRY_POLICY")
    if len(request_bytes) > context["context_ceiling_tokens"]:
        raise ScopedReaderError("SCOPED_CONTEXT_LIMIT: no full-document fallback")
    return PreparedScopedReaderRequest(
        request_bytes=request_bytes, request_id=content_hash(value=body),
        source_scope_manifest_id=expected_manifest_id,
        requirement_closure_hash=str(scope["requirement_closure_hash"]),
        estimated_input_tokens=len(request_bytes),
        plan_bytes=plan_bytes, plan_id=plan_id,
    )


def load_scoped_reader_plan(*, path: Path, repo_root: Path, expected_plan_id: str,
                           **authority) -> Dict[str, object]:
    """Load exact offline plan bytes; no deletion can select a legacy subtype."""
    data = read_scope_repository_bytes(path=path, repo_root=repo_root)
    try:
        body = strict_json_loads(text=data.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ScopedReaderError("Scoped plan is not strict UTF-8 JSON") from error
    _exact(body, PLAN_FIELDS | V2_IDENTITY_FIELDS if body.get("schema_version") == 2 else PLAN_FIELDS, "Scoped Reader plan")
    expected = build_scoped_reader_plan(**authority)
    if (body != expected or body["scoped_plan_id"] != expected_plan_id
            or data != canonical_json_bytes(value=expected)):
        raise ScopedReaderError("Scoped plan bytes/identity differ")
    return body


def load_scoped_reader_request(*, path: Path, repo_root: Path, expected_request_id: str,
                              **authority) -> PreparedScopedReaderRequest:
    """Read the exact scoped request subtype and replay all packing identities."""
    data = read_scope_repository_bytes(path=path, repo_root=repo_root)
    try:
        body = strict_json_loads(text=data.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ScopedReaderError("Scoped request is not strict UTF-8 JSON") from error
    _exact(body, V2_REQUEST_FIELDS if body.get("schema_version") == 2 else REQUEST_FIELDS, "Scoped Reader request")
    expected = prepare_scoped_reader_request(**authority)
    if data != expected.request_bytes or content_hash(value=body) != expected_request_id:
        raise ScopedReaderError("Scoped request bytes/identity differ")
    return expected


def check_scoped_reader_response(
    *, prepared_request: PreparedScopedReaderRequest, response_text: str,
    attempt_id: str, source_scope_manifest: Mapping,
    expected_manifest_id: str, requirement: Mapping, raw_blob: Mapping,
    source_reference: Mapping, full_derived_asset: Mapping,
    reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping,
    source_bytes: bytes = None, repo_root: Path = None,
    _verified_scope_context: OfflineScopedContext = None,
    _offline_evidence_context: OfflineEvidenceContext = None,
    _label_policy: str = None,
) -> Dict[str, object]:
    """Verify scoped Candidate/Evidence without creating execution metadata.

    The exact scoped request is verified separately. The full Reader payload
    passed to check_evidence is explicitly local Evidence authority, not a
    claim that the full filing was sent to a provider. No second value verifier
    or selector is introduced.

    Normal calls select the record-bound Requirement policy. ``_label_policy``
    is retained for explicit historical offline experiments, never model data
    or a live CLI/environment override. Old Requirements remain exact-raw.
    """
    expected_request = prepare_scoped_reader_request(
        source_scope_manifest=source_scope_manifest,
        expected_manifest_id=expected_manifest_id, requirement=requirement,
        raw_blob=raw_blob, source_reference=source_reference,
        full_derived_asset=full_derived_asset, reader_manifest=reader_manifest,
        task_contract=task_contract, evidence_authority_payload=evidence_authority_payload,
        source_bytes=source_bytes, repo_root=repo_root,
        _verified_scope_context=_verified_scope_context,
        _offline_evidence_context=_offline_evidence_context,
    )
    if _label_policy is None:
        _label_policy = bound_label_policy(requirement)
    if (not isinstance(prepared_request, PreparedScopedReaderRequest)
            or expected_request != prepared_request):
        raise ScopedReaderError("Scoped request bytes/identity differ")
    if type(attempt_id) is not str or not attempt_id.strip():
        raise ScopedReaderError("Scoped attempt identity is empty")
    if type(response_text) is not str:
        raise ScopedReaderError("Scoped response is not UTF-8 text")
    source_proof = source_scope_manifest.get("source_bound_proof")
    evidence_context = None
    evidence_session = _offline_evidence_context if _verified_scope_context is None else _verified_scope_context._evidence
    if source_proof is None:
        candidate = validate_reader_output(response_text=response_text, attempt_id=attempt_id,
            required_roles=task_contract["required_roles"], scope_contract=task_contract["scope_contract"],
            source_reference_ids=[source_reference["source_reference_id"]],
            derived_asset_ids=[full_derived_asset["derived_asset_id"]])
    else:
        root = repo_root or Path(__file__).resolve().parents[2]
        exact_source = source_bytes if source_bytes is not None else load_raw_blob_bytes(repo_root=root, raw_blob=raw_blob)
        candidate = validate_source_bound_reader_output(response_text=response_text, attempt_id=attempt_id,
            source_bound_proof=source_proof, expected_proof_id=source_proof["source_bound_proof_id"],
            requirement=requirement, repo_root=root, source_bytes=exact_source, raw_blob=raw_blob,
            source_reference=source_reference, full_derived_asset=full_derived_asset, task_contract=task_contract,
            _offline_context=evidence_session)
        evidence_context = {"proof": source_proof, "expected_proof_id": source_proof["source_bound_proof_id"],
            "requirement": requirement, "repo_root": root, "source_bytes": exact_source,
            "raw_blob": raw_blob, "task_contract": task_contract}
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
        if claim["locator"] != source_scope_manifest["target_locator"]:
            raise ScopedReaderError("SCOPED_CERTIFIED_TARGET_MISMATCH: response selected a different in-window cell")
    if evidence_session is None:
        evidence = check_evidence(candidate=candidate, derived_asset=full_derived_asset,
            reader_manifest=reader_manifest, reader_payload_body=evidence_authority_payload,
            source_references=[source_reference], identity_constraints=task_contract["identity_constraints"],
            scope_contract=task_contract["scope_contract"], source_bound_context=evidence_context,
            _label_policy=_label_policy)
    else:
        evidence = check_evidence_in_offline_session(context=evidence_session,
            candidate=candidate, task_contract_id=task_contract["task_contract_id"],
            source_bound_context=evidence_context, _label_policy=_label_policy)
    if evidence["status"] == "PASS":
        reference = source_scope_manifest["reference"]
        certified = source_scope_manifest["synthetic_candidate"]["selected"]
        if (list(evidence["normalized_values"].values()) != [reference["value"]]
                or evidence["normalized_scope"] != reference["scope"]
                or evidence["system_approval_eligible"] is not True
                or any(claim["claimed_period"] != reference["period"]
                       or claim["claimed_reported_unit"] != certified[role]["claimed_reported_unit"]
                       for role, claim in candidate["selected"].items())):
            raise ScopedReaderError("SCOPED_REFERENCE_RECONCILIATION_FAILED: native Evidence differs from the certified value/unit/period/scope")
    return {"candidate": candidate, "evidence": evidence}


def validate_scoped_reader_response(
    *, prepared_request: PreparedScopedReaderRequest, response_text: str,
    attempt_id: str, source_scope_manifest: Mapping,
    expected_manifest_id: str, requirement: Mapping, raw_blob: Mapping,
    source_reference: Mapping, full_derived_asset: Mapping,
    reader_manifest: Mapping, task_contract: Mapping,
    evidence_authority_payload: Mapping,
    source_bytes: bytes = None, repo_root: Path = None,
    _verified_scope_context: OfflineScopedContext = None,
    _offline_evidence_context: OfflineEvidenceContext = None,
) -> Dict[str, object]:
    """Keep the offline attempt schema and results separate from live execution."""
    checked = check_scoped_reader_response(prepared_request=prepared_request,
        response_text=response_text, attempt_id=attempt_id,
        source_scope_manifest=source_scope_manifest, expected_manifest_id=expected_manifest_id,
        requirement=requirement, raw_blob=raw_blob, source_reference=source_reference,
        full_derived_asset=full_derived_asset, reader_manifest=reader_manifest,
        task_contract=task_contract, evidence_authority_payload=evidence_authority_payload,
        source_bytes=source_bytes, repo_root=repo_root,
        _verified_scope_context=_verified_scope_context,
        _offline_evidence_context=_offline_evidence_context)
    candidate, evidence = checked["candidate"], checked["evidence"]
    link_body = {
        "record_type": "SCOPED_CANDIDATE_EVIDENCE_LINK", "schema_version": source_scope_manifest["schema_version"],
        **_identity(source_scope_manifest), "attempt_id": attempt_id,
        "scoped_plan_id": prepared_request.plan_id,
        "scoped_request_id": prepared_request.request_id,
        "request_sha256": sha256_bytes(content=prepared_request.request_bytes),
        "response_sha256": sha256_bytes(content=response_text.encode("utf-8")),
        "candidate_hash": candidate["candidate_hash"],
        "candidate_record_sha256": sha256_bytes(content=canonical_json_bytes(value=candidate)),
        "evidence_check_id": evidence["evidence_check_id"],
        "evidence_record_sha256": sha256_bytes(content=canonical_json_bytes(value=evidence)),
        "qualification_credit": "NONE",
    }
    body = {
        "record_type": "SCOPED_OFFLINE_EXTRACTION_ATTEMPT", "schema_version": source_scope_manifest["schema_version"],
        **_identity(source_scope_manifest), "attempt_id": attempt_id,
        "scoped_plan_id": prepared_request.plan_id,
        "plan_sha256": sha256_bytes(content=prepared_request.plan_bytes),
        "scoped_request_id": prepared_request.request_id,
        "request_sha256": sha256_bytes(content=prepared_request.request_bytes),
        "response_text": response_text,
        "response_sha256": sha256_bytes(content=response_text.encode("utf-8")),
        "candidate": candidate, "evidence": evidence,
        "candidate_evidence_link": {**link_body, "scoped_evidence_link_id": content_hash(value=link_body)},
        "evidence_authority_kind": "FULL_LOCAL_READER_INPUT_MANIFEST",
        "execution_mode": "OFFLINE_SYNTHETIC",
        "provider_call_count": 0, "paid_model_call_count": 0, "sec_call_count": 0,
        "actual_provider_usage": "NOT_RUN", "qualification_credit": "NONE",
    }
    return {**body, "scoped_attempt_id": content_hash(value=body)}


def replay_scoped_offline_attempt(*, attempt: Mapping,
                                  prepared_request: PreparedScopedReaderRequest,
                                  expected_attempt_id: str = None,
                                  **authority) -> Dict[str, object]:
    """Rebuild the complete attempt, Candidate and Evidence graph from disk data."""
    _exact(attempt, ATTEMPT_FIELDS | V2_IDENTITY_FIELDS if attempt.get("schema_version") == 2 else ATTEMPT_FIELDS,
           "Scoped offline extraction attempt")
    validate_scope_requirement_identity(artifact=attempt, requirement=authority["requirement"])
    if (attempt["record_type"] != "SCOPED_OFFLINE_EXTRACTION_ATTEMPT"
            or type(attempt["schema_version"]) is not int or attempt["schema_version"] not in {1, 2}
            or (expected_attempt_id is not None and attempt["scoped_attempt_id"] != expected_attempt_id)):
        raise ScopedReaderError("Scoped attempt subtype/content identity differs")
    validate_record(record=attempt["candidate"])
    validate_record(record=attempt["evidence"])
    actual = validate_scoped_reader_response(
        prepared_request=prepared_request, response_text=attempt["response_text"],
        attempt_id=attempt["attempt_id"], **authority,
    )
    if dict(attempt) != actual:
        raise ScopedReaderError("Scoped attempt/Candidate/Evidence identity differs")
    return actual


def prepare_scoped_reader_request_in_session(*, context: OfflineScopedContext,
                                            source_scope_manifest_id: str) -> PreparedScopedReaderRequest:
    """Build the same request with certified immutable source-local inputs."""
    if type(context) is not OfflineScopedContext:
        raise ScopedReaderError("Scoped context type is not exact")
    scope, authority = context._authority(source_scope_manifest_id=source_scope_manifest_id)
    return prepare_scoped_reader_request(source_scope_manifest=scope, expected_manifest_id=source_scope_manifest_id,
        _verified_scope_context=context, **authority)


def validate_scoped_reader_response_in_session(*, context: OfflineScopedContext,
                                              source_scope_manifest_id: str,
                                              prepared_request: PreparedScopedReaderRequest,
                                              response_text: str, attempt_id: str) -> Dict[str, object]:
    """Parse a fresh response and run native Evidence; never reuse child results."""
    if type(context) is not OfflineScopedContext:
        raise ScopedReaderError("Scoped context type is not exact")
    scope, authority = context._authority(source_scope_manifest_id=source_scope_manifest_id)
    return validate_scoped_reader_response(prepared_request=prepared_request, response_text=response_text,
        attempt_id=attempt_id, source_scope_manifest=scope, expected_manifest_id=source_scope_manifest_id,
        _verified_scope_context=context, **authority)


def replay_scoped_offline_attempt_in_session(*, context: OfflineScopedContext,
                                            attempt: Mapping, expected_attempt_id: str = None) -> Dict[str, object]:
    """Replay on a fresh disk-built context for the independent final session gate."""
    if type(context) is not OfflineScopedContext:
        raise ScopedReaderError("Scoped context type is not exact")
    identity = attempt["source_scope_manifest_id"]
    scope, authority = context._authority(source_scope_manifest_id=identity)
    prepared = prepare_scoped_reader_request_in_session(context=context, source_scope_manifest_id=identity)
    return replay_scoped_offline_attempt(attempt=attempt, prepared_request=prepared,
        expected_attempt_id=expected_attempt_id, source_scope_manifest=scope, expected_manifest_id=identity,
        _verified_scope_context=context, **authority)


def load_scoped_offline_attempt(*, path: Path, repo_root: Path,
                               expected_attempt_id: str,
                               prepared_request: PreparedScopedReaderRequest,
                               **authority) -> Dict[str, object]:
    """Load a pinned full attempt, then independently replay native Reader/Evidence."""
    data = read_scope_repository_bytes(path=path, repo_root=repo_root)
    try:
        attempt = strict_json_loads(text=data.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ScopedReaderError("Scoped attempt is not strict UTF-8 JSON") from error
    return replay_scoped_offline_attempt(attempt=attempt,
        expected_attempt_id=expected_attempt_id, prepared_request=prepared_request, **authority)


def replay_scoped_offline_artifact_set(*, directory: Path, repo_root: Path,
                                     file_bindings: Mapping,
                                     expected_manifest_id: str,
                                     expected_plan_id: str,
                                     expected_request_id: str,
                                     expected_attempt_id: str,
                                     **authority) -> Dict[str, object]:
    """Replay one exact four-file offline artifact set, without writes or network.

    The containing fixture authority owns the file pins and all content IDs.
    Extra files, alias entries, missing artifacts and even re-signed mutations
    fail before native Evidence can receive qualification credit (always NONE).
    The caller's final replay supplies full assets rebuilt from immutable disk
    source bytes; this API never substitutes a scoped DerivedAsset.
    """
    if (directory.is_symlink() or not directory.is_dir()
            or {item.name for item in directory.iterdir()} != ARTIFACT_FILENAMES
            or type(file_bindings) is not dict or set(file_bindings) != ARTIFACT_FILENAMES):
        raise ScopedReaderError("Scoped artifact directory exact set differs")
    for name, binding in file_bindings.items():
        _exact(binding, frozenset({"sha256", "size"}), "Scoped file binding")
        read_scope_repository_bytes(path=directory / name, repo_root=repo_root,
                                    expected_sha256=binding["sha256"], expected_size=binding["size"])
    scope = load_source_scope_manifest(path=directory / "source_scope.json", repo_root=repo_root,
        expected_manifest_id=expected_manifest_id, **authority)
    scoped_authority = {"source_scope_manifest": scope,
                        "expected_manifest_id": expected_manifest_id, **authority}
    plan = load_scoped_reader_plan(path=directory / "scoped_plan.json", repo_root=repo_root,
                                  expected_plan_id=expected_plan_id, **scoped_authority)
    request = load_scoped_reader_request(path=directory / "scoped_request.json", repo_root=repo_root,
                                        expected_request_id=expected_request_id, **scoped_authority)
    attempt = load_scoped_offline_attempt(path=directory / "scoped_attempt.json", repo_root=repo_root,
        expected_attempt_id=expected_attempt_id, prepared_request=request, **scoped_authority)
    return {"source_scope_manifest": scope, "plan": plan,
            "request": request, "attempt": attempt}
