"""Control exact model invocations with single-flight immutable audit state.

The controller separates release-input, AI-invocation, and execution identity;
reuses successful exact responses; reserves provider egress with ``O_EXCL``;
and writes immutable egress, attempt, execution, and response receipts. It has
no repository-enforced monetary caps or monetary preflight blocker.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from .canonical import CanonicalError, canonical_json_bytes, content_hash
from .canonical import decimal_text, parse_decimal, parse_utc_timestamp
from .canonical import sha256_bytes, strict_json_file
from .requirements import load_requirement_snapshot


PLAN_FIELDS = {
    "ai_invocation_plan_id",
    "api",
    "invocation_policy",
    "model",
    "observability",
    "output_schema_hash",
    "provider",
    "provider_request_body_sha256",
    "provider_request_identity",
    "record_type",
    "release_input_plan_id",
    "resource_limits",
    "schema_version",
    "selected_representation_hash",
    "semantic_invocation_id",
    "serialization_version",
    "source_identity_hash",
    "task_contract_hash",
}
RESOURCE_LIMIT_FIELDS = {"maximum_context_tokens", "maximum_payload_bytes"}
OBSERVABILITY_FIELDS = {
    "estimated_context_tokens",
    "estimated_cost",
    "pricing_snapshot_hash",
}
ACCEPTANCE_DRAFT_FIELDS = {
    "candidate_hash",
    "candidate_record",
    "derived_asset_id",
    "evidence_candidate_hash",
    "evidence_check_id",
    "evidence_record",
    "evidence_status",
    "reader_input_manifest_id",
    "source_reference_ids",
    "spec_semantic_hash",
    "task_contract_hash",
    "validator_semantic_hash",
    "validator_semantic_version",
}
ACCEPTANCE_RECEIPT_FIELDS = ACCEPTANCE_DRAFT_FIELDS | {
    "acceptance_receipt_id",
    "ai_invocation_plan_id",
    "provider_request_identity",
    "record_type",
    "response_body_sha256",
    "schema_version",
}
TRANSPORT_RESULT_FIELDS = {
    "error_class",
    "paid_call",
    "provider_request_id",
    "response_body",
    "status_code",
    "usage",
}
USAGE_FIELDS = {
    "actual_cost",
    "cache_hit_input_tokens",
    "cache_miss_input_tokens",
    "input_tokens",
    "output_tokens",
}
TERMINAL_HTTP_STATUS = {400, 401, 402, 422}
TERMINAL_ERROR_CLASSES = {
    "SCHEMA_VIOLATION",
    "EVIDENCE_FAILURE",
    "PAYLOAD_LIMIT",
    "CONTEXT_LIMIT",
    "RESOURCE_LIMIT",
}
RETRYABLE_ERROR_CLASSES = {"HTTP_429", "TIMEOUT", "RECOVERABLE_5XX"}
FORBIDDEN_MONETARY_FIELDS = {
    "owner_absolute_total_cap",
    "owner_absolute_per_request_cap",
    "remaining_owner_cap",
    "maximum_authorized_cost",
    "per_call_monetary_cap",
    "batch_monetary_cap",
    "monetary_budget_preflight",
}
COUNTER_FIELDS = {
    "mock_transport_invocation_count",
    "paid_model_provider_call_count",
    "real_model_provider_egress_count",
}
INVOCATION_POLICY_FIELDS = {
    "d35_record_hash",
    "d36_record_hash",
    "requirement_closure_hash",
}
SUCCESS_RESPONSE_FIELDS = {
    "acceptance_receipt_id",
    "ai_invocation_plan_id",
    "api",
    "attempt_receipt_id",
    "model",
    "paid_call",
    "provider",
    "provider_request_body_sha256",
    "provider_request_id",
    "provider_request_identity",
    "record_type",
    "response_body_path",
    "response_body_sha256",
    "response_body_size",
    "schema_version",
    "success_response_receipt_id",
    "usage",
}


class InvocationControlError(ValueError):
    """Report malformed identities, unsafe state, or forbidden policy."""


class UnknownRemoteOutcomeError(RuntimeError):
    """Signal that egress occurred but no terminal provider outcome exists."""


class SchemaViolationError(ValueError):
    """Signal a terminal structured-response schema violation."""


class EvidenceFailureError(ValueError):
    """Signal a terminal post-response evidence validation failure."""


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def effective_invocation_policy() -> Dict[str, object]:
    """Load and validate effective Issue #15 D-35/D-36 authority.

    Returns:
        Requirement closure and exact effective Decision record hashes.
    """
    requirement = load_requirement_snapshot(
        snapshot_dir=_REPOSITORY_ROOT / "requirements" / "issue_15_v1"
    )
    d35 = requirement["effective_decisions"]["D-35"]
    d36 = requirement["effective_decisions"]["D-36"]
    d35_choice = d35["choice"]
    d36_choice = d36["choice"]
    if (
        d35_choice["maximum_retries"] != 1
        or d35_choice["http_402_automatic_retries"] != 0
        or not d35_choice["http_402_stops_execution"]
        or not d35_choice["http_402_stops_batch"]
        or d36_choice["repository_monetary_budget_enforcement"] != "DISABLED"
        or d36_choice["monetary_budget_preflight"]
        or d36_choice["estimated_or_actual_cost_may_block_provider_call"]
    ):
        raise InvocationControlError("Effective invocation policy differs")
    return {
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "d35_record_hash": content_hash(value=d35),
        "d36_record_hash": content_hash(value=d36),
    }


def _object(*, value: object, label: str) -> Dict[str, object]:
    """Return one isolated mapping or fail fast.

    Args:
        value: Candidate object.
        label: Stable diagnostic location.

    Returns:
        Shallow isolated mapping.
    """
    if not isinstance(value, dict):
        raise InvocationControlError("{} must be an object".format(label))
    return dict(value)


def _text(*, value: object, label: str) -> str:
    """Return one required non-empty text scalar."""
    if not isinstance(value, str) or not value:
        raise InvocationControlError("{} must be non-empty text".format(label))
    return value


def _sha256_identity(*, value: object, label: str) -> str:
    """Return one required ``sha256:`` identity."""
    text = _text(value=value, label=label)
    if (
        len(text) != 71
        or not text.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in text[7:])
    ):
        raise InvocationControlError("{} is not a SHA-256 identity".format(label))
    return text


def _utc(*, value: object, label: str) -> str:
    """Return one required UTC timestamp."""
    text = _text(value=value, label=label)
    try:
        parse_utc_timestamp(value=text)
    except CanonicalError as error:
        raise InvocationControlError("{} must be UTC".format(label)) from error
    return text


def _exact_fields(
    *, value: Mapping[str, object], expected: set[str], label: str
) -> None:
    """Require one exact mapping schema."""
    if set(value) != expected:
        raise InvocationControlError("{} fields are not exact".format(label))


def _reject_monetary_fields(*, value: object, path: str) -> None:
    """Reject every repository monetary-cap or hard-stop field recursively.

    Args:
        value: Candidate plan or observability structure.
        path: Stable diagnostic path.

    Raises:
        InvocationControlError: When a forbidden field appears at any depth.
    """
    if isinstance(value, dict):
        forbidden = FORBIDDEN_MONETARY_FIELDS.intersection(value)
        if forbidden:
            raise InvocationControlError(
                "Forbidden monetary field at {}: {}".format(
                    path, sorted(forbidden)[0]
                )
            )
        for key in value:
            _reject_monetary_fields(
                value=value[key], path="{}.{}".format(path, key)
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_monetary_fields(
                value=item, path="{}[{}]".format(path, index)
            )


def _decimal_observation(*, value: object, label: str) -> str:
    """Return canonical non-negative monetary observability text.

    Monetary observations are recorded but never compared with a cap.
    """
    if not isinstance(value, str):
        raise InvocationControlError("{} must be decimal text".format(label))
    try:
        normalized = decimal_text(value=parse_decimal(value=value))
    except CanonicalError as error:
        raise InvocationControlError("{} is invalid".format(label)) from error
    if normalized != value or Decimal(normalized) < 0:
        raise InvocationControlError(
            "{} is not canonical non-negative text".format(label)
        )
    return normalized


def build_ai_invocation_plan(
    *,
    release_input_plan_id: str,
    source_identity_hash: str,
    selected_representation_hash: str,
    task_contract_hash: str,
    output_schema_hash: str,
    serialization_version: str,
    provider: str,
    model: str,
    api: str,
    request_body: bytes,
    maximum_payload_bytes: int,
    maximum_context_tokens: int,
    estimated_context_tokens: int,
    pricing_snapshot_hash: str,
    estimated_cost: str,
) -> Dict[str, object]:
    """Build one exact AI invocation plan without a monetary hard stop.

    Args:
        release_input_plan_id: Complete source/result/authority plan identity.
        source_identity_hash: Exact selected SEC source identity.
        selected_representation_hash: Exact serialized source representation.
        task_contract_hash: Exact task contract identity.
        output_schema_hash: Exact structured output schema identity.
        serialization_version: Explicit request serialization version.
        provider: Provider identity.
        model: Requested model identity.
        api: Provider API identity.
        request_body: Exact outbound provider request bytes.
        maximum_payload_bytes: Non-monetary hard payload limit.
        maximum_context_tokens: Non-monetary hard context limit.
        estimated_context_tokens: Deterministic pre-egress token estimate.
        pricing_snapshot_hash: Non-blocking pricing observability identity.
        estimated_cost: Non-blocking canonical cost estimate.

    Returns:
        Content-addressed three-layer invocation plan.
    """
    for label, identity in (
        ("release input plan id", release_input_plan_id),
        ("source identity hash", source_identity_hash),
        ("selected representation hash", selected_representation_hash),
        ("task contract hash", task_contract_hash),
        ("output schema hash", output_schema_hash),
        ("pricing snapshot hash", pricing_snapshot_hash),
    ):
        _sha256_identity(value=identity, label=label)
    for label, value in (
        ("serialization version", serialization_version),
        ("provider", provider),
        ("model", model),
        ("api", api),
    ):
        _text(value=value, label=label)
    if not isinstance(request_body, bytes) or not request_body:
        raise InvocationControlError("Provider request body must be bytes")
    if (
        type(maximum_payload_bytes) is not int
        or maximum_payload_bytes <= 0
        or type(maximum_context_tokens) is not int
        or maximum_context_tokens <= 0
        or type(estimated_context_tokens) is not int
        or estimated_context_tokens < 0
    ):
        raise InvocationControlError("Invocation resource limits are invalid")
    request_sha256 = sha256_bytes(content=request_body)
    provider_request_identity = content_hash(
        value={
            "provider_request_body_sha256": request_sha256,
            "provider": provider,
            "model": model,
            "api": api,
        }
    )
    semantic_invocation_id = content_hash(
        value={
            "source_identity_hash": source_identity_hash,
            "selected_representation_hash": selected_representation_hash,
            "task_contract_hash": task_contract_hash,
            "output_schema_hash": output_schema_hash,
            "serialization_version": serialization_version,
            "model": model,
        }
    )
    body = {
        "schema_version": 1,
        "record_type": "AI_INVOCATION_PLAN",
        "release_input_plan_id": release_input_plan_id,
        "source_identity_hash": source_identity_hash,
        "selected_representation_hash": selected_representation_hash,
        "task_contract_hash": task_contract_hash,
        "output_schema_hash": output_schema_hash,
        "serialization_version": serialization_version,
        "provider": provider,
        "model": model,
        "api": api,
        "invocation_policy": effective_invocation_policy(),
        "provider_request_body_sha256": request_sha256,
        "provider_request_identity": provider_request_identity,
        "semantic_invocation_id": semantic_invocation_id,
        "resource_limits": {
            "maximum_payload_bytes": maximum_payload_bytes,
            "maximum_context_tokens": maximum_context_tokens,
        },
        "observability": {
            "estimated_context_tokens": estimated_context_tokens,
            "pricing_snapshot_hash": pricing_snapshot_hash,
            "estimated_cost": _decimal_observation(
                value=estimated_cost, label="estimated cost"
            ),
        },
    }
    _reject_monetary_fields(value=body, path="ai_invocation_plan")
    plan = dict(body)
    plan["ai_invocation_plan_id"] = content_hash(value=body)
    return validate_ai_invocation_plan(plan=plan)


def validate_ai_invocation_plan(*, plan: Mapping[str, object]) -> Dict[str, object]:
    """Validate one exact AI invocation plan and all three identities."""
    value = _object(value=plan, label="AI invocation plan")
    _exact_fields(value=value, expected=PLAN_FIELDS, label="AI invocation plan")
    _reject_monetary_fields(value=value, path="ai_invocation_plan")
    if value["schema_version"] != 1 or value["record_type"] != "AI_INVOCATION_PLAN":
        raise InvocationControlError("AI invocation plan identity differs")
    for field in (
        "ai_invocation_plan_id",
        "release_input_plan_id",
        "source_identity_hash",
        "selected_representation_hash",
        "task_contract_hash",
        "output_schema_hash",
        "provider_request_identity",
        "semantic_invocation_id",
    ):
        _sha256_identity(value=value[field], label=field)
    for field in ("serialization_version", "provider", "model", "api"):
        _text(value=value[field], label=field)
    invocation_policy = _object(
        value=value["invocation_policy"], label="invocation policy"
    )
    _exact_fields(
        value=invocation_policy,
        expected=INVOCATION_POLICY_FIELDS,
        label="invocation policy",
    )
    for field in INVOCATION_POLICY_FIELDS:
        _sha256_identity(value=invocation_policy[field], label=field)
    if invocation_policy != effective_invocation_policy():
        raise InvocationControlError("Invocation policy binding differs")
    request_hash = _text(
        value=value["provider_request_body_sha256"],
        label="provider request body SHA-256",
    )
    if len(request_hash) != 64 or any(
        character not in "0123456789abcdef" for character in request_hash
    ):
        raise InvocationControlError("Provider request body digest is invalid")
    limits = _object(value=value["resource_limits"], label="resource limits")
    _exact_fields(
        value=limits, expected=RESOURCE_LIMIT_FIELDS, label="resource limits"
    )
    if any(type(limits[field]) is not int or limits[field] <= 0 for field in limits):
        raise InvocationControlError("Resource limits are invalid")
    observability = _object(value=value["observability"], label="observability")
    _exact_fields(
        value=observability,
        expected=OBSERVABILITY_FIELDS,
        label="observability",
    )
    if (
        type(observability["estimated_context_tokens"]) is not int
        or observability["estimated_context_tokens"] < 0
    ):
        raise InvocationControlError("Estimated context tokens are invalid")
    _sha256_identity(
        value=observability["pricing_snapshot_hash"],
        label="pricing snapshot hash",
    )
    _decimal_observation(
        value=observability["estimated_cost"], label="estimated cost"
    )
    request_identity = content_hash(
        value={
            "provider_request_body_sha256": request_hash,
            "provider": value["provider"],
            "model": value["model"],
            "api": value["api"],
        }
    )
    semantic_identity = content_hash(
        value={
            "source_identity_hash": value["source_identity_hash"],
            "selected_representation_hash": value[
                "selected_representation_hash"
            ],
            "task_contract_hash": value["task_contract_hash"],
            "output_schema_hash": value["output_schema_hash"],
            "serialization_version": value["serialization_version"],
            "model": value["model"],
        }
    )
    body = {field: value[field] for field in value if field != "ai_invocation_plan_id"}
    if (
        value["provider_request_identity"] != request_identity
        or value["semantic_invocation_id"] != semantic_identity
        or value["ai_invocation_plan_id"] != content_hash(value=body)
    ):
        raise InvocationControlError("AI invocation plan content identity differs")
    return value


def execution_identity(
    *, ai_invocation_plan_id: str, owner_token: str, authorized_at_utc: str
) -> str:
    """Derive one explicit execution identity from authorization data."""
    _sha256_identity(value=ai_invocation_plan_id, label="AI invocation plan id")
    owner = _text(value=owner_token, label="execution owner token")
    authorized = _utc(value=authorized_at_utc, label="execution authorization time")
    return content_hash(
        value={
            "ai_invocation_plan_id": ai_invocation_plan_id,
            "owner_token_hash": content_hash(value=owner),
            "authorized_at_utc": authorized,
        }
    )


def _state_root(*, workspace_dir: Path) -> Path:
    """Create and validate the local invocation-control namespace."""
    if workspace_dir.is_symlink():
        raise InvocationControlError("Invocation workspace is a symlink")
    workspace_dir.mkdir(parents=True, exist_ok=True)
    if not workspace_dir.is_dir():
        raise InvocationControlError("Invocation workspace is not a directory")
    root = workspace_dir / "invocation_control"
    root.mkdir(exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise InvocationControlError("Invocation state root is unsafe")
    for name in (
        "acceptances",
        "abandoned",
        "attempts",
        "egress",
        "executions",
        "plans",
        "reservation_archive",
        "reservations",
        "requests",
        "responses",
    ):
        path = root / name
        path.mkdir(exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise InvocationControlError("Invocation state namespace is unsafe")
    return root


def _identity_name(*, identity: str) -> str:
    """Return the lowercase digest component of one content identity."""
    return _sha256_identity(value=identity, label="content identity").split(
        ":", maxsplit=1
    )[1]


def _exclusive_write_bytes(*, path: Path, content: bytes) -> None:
    """Publish exact bytes once with ``O_CREAT|O_EXCL``.

    Args:
        path: New immutable file below a validated namespace.
        content: Exact bytes to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise InvocationControlError("Immutable receipt parent is unsafe")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise InvocationControlError("Immutable receipt bytes differ")
        return
    try:
        offset = 0
        while offset < len(content):
            written = os.write(descriptor, content[offset:])
            if written <= 0:
                raise InvocationControlError("Immutable receipt write stopped")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_write_json(*, path: Path, value: Mapping[str, object]) -> None:
    """Publish one canonical JSON object once."""
    _exclusive_write_bytes(path=path, content=canonical_json_bytes(value=dict(value)))


def _empty_counters() -> Dict[str, int]:
    """Return isolated zeroed provider-call counters."""
    return {
        "real_model_provider_egress_count": 0,
        "paid_model_provider_call_count": 0,
        "mock_transport_invocation_count": 0,
    }


def _add_counters(
    *, target: Dict[str, int], source: Mapping[str, object]
) -> None:
    """Add one exact counter mapping into an aggregate."""
    if set(source) != COUNTER_FIELDS or any(
        type(source[field]) is not int or source[field] < 0 for field in source
    ):
        raise InvocationControlError("Provider call counters are invalid")
    for field in COUNTER_FIELDS:
        target[field] += int(source[field])


def _validate_request_resources(
    *, plan: Mapping[str, object], request_body: bytes
) -> None:
    """Fail before reservation when payload or context exceeds hard limits."""
    if sha256_bytes(content=request_body) != plan["provider_request_body_sha256"]:
        raise InvocationControlError("Provider request body differs from plan")
    limits = plan["resource_limits"]
    observability = plan["observability"]
    if len(request_body) > limits["maximum_payload_bytes"]:
        raise InvocationControlError("PAYLOAD_LIMIT")
    if observability["estimated_context_tokens"] > limits[
        "maximum_context_tokens"
    ]:
        raise InvocationControlError("CONTEXT_LIMIT")


def _reservation_path(*, root: Path, request_identity: str) -> Path:
    """Return the unique provider-request reservation path."""
    return root / "reservations" / (_identity_name(identity=request_identity) + ".json")


def _execution_path(*, root: Path, execution_id: str) -> Path:
    """Return the immutable terminal execution receipt path."""
    return root / "executions" / (_identity_name(identity=execution_id) + ".json")


def _persist_invocation_input(
    *, root: Path, plan: Mapping[str, object], request_body: bytes,
) -> None:
    """Persist the exact immutable plan and provider request bytes."""
    plan_path = (
        root / "plans"
        / (_identity_name(identity=str(plan["ai_invocation_plan_id"])) + ".json")
    )
    request_path = (
        root / "requests"
        / (
            _identity_name(identity=str(plan["provider_request_identity"]))
            + ".bin"
        )
    )
    _exclusive_write_json(path=plan_path, value=plan)
    _exclusive_write_bytes(path=request_path, content=request_body)


def _process_is_alive(*, process_id: object) -> bool:
    """Return whether one positive local reservation-owner PID still exists."""
    if type(process_id) is not int or process_id <= 0:
        raise InvocationControlError("Reservation owner process id is invalid")
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _archive_reservation(
    *, root: Path, reservation_path: Path,
    reservation: Mapping[str, object], terminal_status: str,
) -> Dict[str, object]:
    """Archive one completed active reservation and release single-flight.

    Args:
        root: Validated invocation-control namespace.
        reservation_path: Active request-identity reservation.
        reservation: Exact immutable reservation bytes.
        terminal_status: Execution state that permits release.

    Returns:
        Immutable reservation lifecycle receipt.
    """
    if terminal_status not in {
        "FAILED_RETRYABLE_FINAL",
        "FAILED_TERMINAL",
        "SUCCEEDED",
        "UNKNOWN_REMOTE_OUTCOME",
    }:
        raise InvocationControlError("Reservation terminal status is invalid")
    execution_id = _text(
        value=reservation["execution_id"], label="reservation execution id",
    )
    request_identity = _text(
        value=reservation["provider_request_identity"],
        label="reservation request identity",
    )
    body = {
        "schema_version": 1,
        "record_type": "SINGLE_FLIGHT_RESERVATION_ARCHIVE",
        "execution_id": execution_id,
        "provider_request_identity": request_identity,
        "reservation_hash": content_hash(value=dict(reservation)),
        "terminal_status": terminal_status,
    }
    receipt = {
        **body,
        "reservation_archive_id": content_hash(value=body),
    }
    destination = (
        root / "reservation_archive"
        / _identity_name(identity=request_identity)
        / (_identity_name(identity=execution_id) + ".json")
    )
    _exclusive_write_json(path=destination, value=receipt)
    if reservation_path.is_symlink() or not reservation_path.is_file():
        raise InvocationControlError("Active reservation disappeared")
    if _read_json_object(
        path=reservation_path, label="active reservation",
    ) != dict(reservation):
        raise InvocationControlError("Active reservation bytes differ")
    reservation_path.unlink()
    return receipt


def _terminal_and_release(
    *, root: Path, reservation_path: Path,
    reservation: Mapping[str, object], body: Mapping[str, object],
) -> Dict[str, object]:
    """Persist terminal execution before releasing its exact reservation."""
    receipt = _terminal_execution(root=root, body=body)
    _archive_reservation(
        root=root,
        reservation_path=reservation_path,
        reservation=reservation,
        terminal_status=str(receipt["status"]),
    )
    return receipt


def _read_json_object(*, path: Path, label: str) -> Dict[str, object]:
    """Read one existing strict JSON object from a safe regular file."""
    if path.is_symlink() or not path.is_file():
        raise InvocationControlError("{} path is unsafe".format(label))
    return _object(value=strict_json_file(path=path), label=label)


def _attempt_receipt(
    *, root: Path, execution_id: str, body: Mapping[str, object]
) -> Dict[str, object]:
    """Persist one immutable terminal/retryable attempt receipt."""
    attempt_body = dict(body)
    receipt = dict(attempt_body)
    receipt["attempt_receipt_id"] = content_hash(value=attempt_body)
    directory = root / "attempts" / _identity_name(identity=execution_id)
    path = directory / (
        "{:02d}_{}.json".format(
            int(receipt["attempt_ordinal"]),
            _identity_name(identity=str(receipt["attempt_receipt_id"])),
        )
    )
    _exclusive_write_json(path=path, value=receipt)
    return receipt


def _usage(*, value: object) -> Dict[str, object]:
    """Validate provider usage/token/cache/cost observability."""
    usage = _object(value=value, label="provider usage")
    _exact_fields(value=usage, expected=USAGE_FIELDS, label="provider usage")
    for field in (
        "input_tokens",
        "output_tokens",
        "cache_hit_input_tokens",
        "cache_miss_input_tokens",
    ):
        if type(usage[field]) is not int or usage[field] < 0:
            raise InvocationControlError("Provider usage tokens are invalid")
    _decimal_observation(value=usage["actual_cost"], label="actual cost")
    return usage


def _transport_result(*, value: object) -> Dict[str, object]:
    """Validate one injected transport observation."""
    result = _object(value=value, label="transport result")
    _exact_fields(
        value=result,
        expected=TRANSPORT_RESULT_FIELDS,
        label="transport result",
    )
    if type(result["status_code"]) is not int or result["status_code"] < 0:
        raise InvocationControlError("Transport status code is invalid")
    if not isinstance(result["error_class"], str):
        raise InvocationControlError("Transport error class is invalid")
    if not isinstance(result["response_body"], bytes):
        raise InvocationControlError("Transport response body must be bytes")
    if not isinstance(result["provider_request_id"], str):
        raise InvocationControlError("Provider request id is invalid")
    if type(result["paid_call"]) is not bool:
        raise InvocationControlError("Paid-call observation must be bool")
    result["usage"] = _usage(value=result["usage"])
    return result


def _classify(*, result: Mapping[str, object]) -> str:
    """Return SUCCESS, TERMINAL, or RETRYABLE from effective D-35 policy."""
    status_code = int(result["status_code"])
    error_class = str(result["error_class"])
    if status_code == 200 and not error_class:
        return "SUCCESS"
    if status_code in TERMINAL_HTTP_STATUS or error_class in TERMINAL_ERROR_CLASSES:
        return "TERMINAL"
    if (
        status_code == 429
        or 500 <= status_code <= 599
        or error_class in RETRYABLE_ERROR_CLASSES
    ):
        return "RETRYABLE"
    return "TERMINAL"


def _error_class(*, result: Mapping[str, object]) -> str:
    """Return one stable attempt error class."""
    if result["error_class"]:
        return str(result["error_class"])
    status_code = int(result["status_code"])
    return "HTTP_{}".format(status_code) if status_code else "TRANSPORT_FAILURE"


def _egress_marker(
    *, root: Path, execution_id: str, plan: Mapping[str, object],
    attempt_ordinal: int, egress_started_at_utc: str, transport_kind: str,
) -> Dict[str, object]:
    """Persist proof that provider outcome may now be remote."""
    if transport_kind not in {"MOCK", "REAL_MODEL_PROVIDER"}:
        raise InvocationControlError("Transport kind is invalid")
    body = {
        "schema_version": 1,
        "record_type": "PROVIDER_EGRESS_MARKER",
        "execution_id": execution_id,
        "ai_invocation_plan_id": plan["ai_invocation_plan_id"],
        "provider_request_identity": plan["provider_request_identity"],
        "attempt_ordinal": attempt_ordinal,
        "egress_started_at_utc": _utc(
            value=egress_started_at_utc, label="egress start time"
        ),
        "transport_kind": transport_kind,
    }
    marker = dict(body)
    marker["egress_marker_id"] = content_hash(value=body)
    directory = root / "egress" / _identity_name(identity=execution_id)
    path = directory / "{:02d}.json".format(attempt_ordinal)
    _exclusive_write_json(path=path, value=marker)
    return marker


def _validate_acceptance_draft(
    *, value: object, plan: Mapping[str, object], response_body: bytes,
) -> Dict[str, object]:
    """Validate the full Candidate/Evidence closure before success.

    Args:
        value: Module-owned acceptance result from the production validator.
        plan: Exact invocation plan whose response was checked.
        response_body: Exact structured assistant bytes.

    Returns:
        Isolated acceptance fields safe to persist content-addressably.
    """
    draft = _object(value=value, label="acceptance draft")
    _exact_fields(
        value=draft,
        expected=ACCEPTANCE_DRAFT_FIELDS,
        label="acceptance draft",
    )
    for field in (
        "candidate_hash",
        "derived_asset_id",
        "evidence_candidate_hash",
        "evidence_check_id",
        "reader_input_manifest_id",
        "spec_semantic_hash",
        "task_contract_hash",
        "validator_semantic_hash",
    ):
        _sha256_identity(value=draft[field], label=field)
    _text(
        value=draft["validator_semantic_version"],
        label="validator semantic version",
    )
    source_ids = draft["source_reference_ids"]
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or len(source_ids) != len(set(source_ids))
    ):
        raise InvocationControlError(
            "Acceptance SourceReference identities are invalid"
        )
    for source_id in source_ids:
        _sha256_identity(value=source_id, label="source reference id")
    candidate = _object(
        value=draft["candidate_record"], label="accepted Candidate"
    )
    evidence = _object(
        value=draft["evidence_record"], label="accepted Evidence"
    )
    try:
        from .records import validate_record

        validate_record(record=candidate)
        validate_record(record=evidence)
    except ValueError as error:
        raise InvocationControlError(
            "Accepted Candidate/Evidence record is invalid"
        ) from error
    if (
        draft["evidence_status"] != "PASS"
        or draft["candidate_hash"] != draft["evidence_candidate_hash"]
        or candidate["candidate_hash"] != draft["candidate_hash"]
        or candidate["assistant_output_sha256"]
        != sha256_bytes(content=response_body)
        or candidate["source_reference_ids"] != source_ids
        or candidate["derived_asset_ids"] != [draft["derived_asset_id"]]
        or evidence["candidate_hash"] != draft["candidate_hash"]
        or evidence["evidence_check_id"] != draft["evidence_check_id"]
        or evidence["status"] != draft["evidence_status"]
        or draft["reader_input_manifest_id"] != plan["source_identity_hash"]
        or draft["derived_asset_id"]
        != plan["selected_representation_hash"]
        or draft["task_contract_hash"] != plan["task_contract_hash"]
    ):
        raise InvocationControlError("Acceptance binding differs")
    return draft


def _validate_acceptance_receipt(
    *, value: object, plan: Mapping[str, object], response_body: bytes,
) -> Dict[str, object]:
    """Recompute one persisted full-acceptance identity and bindings."""
    receipt = _object(value=value, label="acceptance receipt")
    _exact_fields(
        value=receipt,
        expected=ACCEPTANCE_RECEIPT_FIELDS,
        label="acceptance receipt",
    )
    if (
        receipt["schema_version"] != 1
        or receipt["record_type"] != "INVOCATION_ACCEPTANCE_RECEIPT"
        or receipt["ai_invocation_plan_id"]
        != plan["ai_invocation_plan_id"]
        or receipt["provider_request_identity"]
        != plan["provider_request_identity"]
        or receipt["response_body_sha256"]
        != sha256_bytes(content=response_body)
    ):
        raise InvocationControlError("Acceptance receipt binding differs")
    draft = {
        field: receipt[field] for field in ACCEPTANCE_DRAFT_FIELDS
    }
    _validate_acceptance_draft(
        value=draft, plan=plan, response_body=response_body,
    )
    body = {
        field: receipt[field]
        for field in receipt
        if field != "acceptance_receipt_id"
    }
    if receipt["acceptance_receipt_id"] != content_hash(value=body):
        raise InvocationControlError("Acceptance receipt identity differs")
    return receipt


def _persist_acceptance_receipt(
    *, root: Path, plan: Mapping[str, object], response_body: bytes,
    acceptance_draft: object,
) -> Dict[str, object]:
    """Persist full Evidence PASS before any successful attempt receipt."""
    draft = _validate_acceptance_draft(
        value=acceptance_draft, plan=plan, response_body=response_body,
    )
    body = {
        "schema_version": 1,
        "record_type": "INVOCATION_ACCEPTANCE_RECEIPT",
        "ai_invocation_plan_id": plan["ai_invocation_plan_id"],
        "provider_request_identity": plan["provider_request_identity"],
        "response_body_sha256": sha256_bytes(content=response_body),
        **draft,
    }
    receipt = {**body, "acceptance_receipt_id": content_hash(value=body)}
    request_name = _identity_name(
        identity=str(plan["provider_request_identity"])
    )
    _exclusive_write_json(
        path=root / "acceptances" / request_name / "receipt.json",
        value=receipt,
    )
    return receipt


def _load_acceptance_receipt(
    *, root: Path, plan: Mapping[str, object], response_body: bytes,
    acceptance_receipt_id: str,
) -> Dict[str, object]:
    """Load and revalidate Candidate/Evidence acceptance for exact reuse."""
    request_name = _identity_name(
        identity=str(plan["provider_request_identity"])
    )
    receipt = _read_json_object(
        path=root / "acceptances" / request_name / "receipt.json",
        label="acceptance receipt",
    )
    validated = _validate_acceptance_receipt(
        value=receipt, plan=plan, response_body=response_body,
    )
    if validated["acceptance_receipt_id"] != acceptance_receipt_id:
        raise InvocationControlError("Success acceptance identity differs")
    return validated


def _persist_success_response(
    *, root: Path, plan: Mapping[str, object], result: Mapping[str, object],
    attempt_receipt_id: str, acceptance_receipt: Mapping[str, object],
) -> Dict[str, object]:
    """Persist one exact reusable response only after full acceptance."""
    request_name = _identity_name(identity=str(plan["provider_request_identity"]))
    directory = root / "responses" / request_name
    body_path = directory / "response.bin"
    response_bytes = result["response_body"]
    accepted = _validate_acceptance_receipt(
        value=acceptance_receipt,
        plan=plan,
        response_body=response_bytes,
    )
    _exclusive_write_bytes(path=body_path, content=response_bytes)
    body = {
        "schema_version": 1,
        "record_type": "SUCCESS_RESPONSE_RECEIPT",
        "provider_request_identity": plan["provider_request_identity"],
        "ai_invocation_plan_id": plan["ai_invocation_plan_id"],
        "provider_request_body_sha256": plan["provider_request_body_sha256"],
        "provider": plan["provider"],
        "model": plan["model"],
        "api": plan["api"],
        "provider_request_id": result["provider_request_id"],
        "response_body_sha256": sha256_bytes(content=response_bytes),
        "response_body_size": len(response_bytes),
        "response_body_path": "responses/{}/response.bin".format(request_name),
        "usage": dict(result["usage"]),
        "paid_call": result["paid_call"],
        "attempt_receipt_id": attempt_receipt_id,
        "acceptance_receipt_id": accepted["acceptance_receipt_id"],
    }
    receipt = dict(body)
    receipt["success_response_receipt_id"] = content_hash(value=body)
    _exclusive_write_json(path=directory / "receipt.json", value=receipt)
    return receipt


def _load_success_response(
    *, root: Path, plan: Mapping[str, object]
) -> Optional[Dict[str, object]]:
    """Load and byte-verify a reusable exact success response if present."""
    request_name = _identity_name(identity=str(plan["provider_request_identity"]))
    directory = root / "responses" / request_name
    receipt_path = directory / "receipt.json"
    if not receipt_path.exists():
        return None
    receipt = _read_json_object(path=receipt_path, label="success response receipt")
    _exact_fields(
        value=receipt,
        expected=SUCCESS_RESPONSE_FIELDS,
        label="success response receipt",
    )
    if (
        receipt["schema_version"] != 1
        or receipt["record_type"] != "SUCCESS_RESPONSE_RECEIPT"
        or type(receipt["paid_call"]) is not bool
    ):
        raise InvocationControlError("Success response receipt fields differ")
    receipt_body = {
        field: receipt[field]
        for field in receipt
        if field != "success_response_receipt_id"
    }
    if receipt["success_response_receipt_id"] != content_hash(
        value=receipt_body
    ):
        raise InvocationControlError("Success response receipt identity differs")
    body_path = directory / "response.bin"
    if body_path.is_symlink() or not body_path.is_file():
        raise InvocationControlError("Success response body is unsafe")
    response_bytes = body_path.read_bytes()
    if (
        receipt["provider_request_identity"] != plan["provider_request_identity"]
        or receipt["provider_request_body_sha256"]
        != plan["provider_request_body_sha256"]
        or receipt["provider"] != plan["provider"]
        or receipt["model"] != plan["model"]
        or receipt["api"] != plan["api"]
        or receipt["response_body_sha256"] != sha256_bytes(content=response_bytes)
        or receipt["response_body_size"] != len(response_bytes)
        or receipt["response_body_path"]
        != "responses/{}/response.bin".format(request_name)
    ):
        raise InvocationControlError("Success response binding differs")
    _usage(value=receipt["usage"])
    acceptance = _load_acceptance_receipt(
        root=root,
        plan=plan,
        response_body=response_bytes,
        acceptance_receipt_id=str(receipt["acceptance_receipt_id"]),
    )
    return {
        **receipt,
        "acceptance_receipt": acceptance,
        "response_body": response_bytes,
    }


def load_successful_response(
    *, workspace_dir: Path, plan: Mapping[str, object],
) -> Dict[str, object]:
    """Return one verified exact reusable response after execution.

    Args:
        workspace_dir: Invocation-control workspace used by execution.
        plan: Exact AI invocation plan whose response is required.

    Returns:
        Receipt metadata plus exact response bytes.
    """
    validated_plan = validate_ai_invocation_plan(plan=plan)
    response = _load_success_response(
        root=_state_root(workspace_dir=workspace_dir),
        plan=validated_plan,
    )
    if response is None:
        raise InvocationControlError("Successful exact response is absent")
    return response


def _terminal_execution(
    *, root: Path, body: Mapping[str, object]
) -> Dict[str, object]:
    """Persist one immutable execution summary over its attempt sequence."""
    execution_body = dict(body)
    receipt = dict(execution_body)
    receipt["execution_receipt_id"] = content_hash(value=execution_body)
    _exclusive_write_json(
        path=_execution_path(
            root=root, execution_id=str(receipt["execution_id"])
        ),
        value=receipt,
    )
    return receipt


def _load_execution_receipt(
    *, root: Path, path: Path, execution_id: str
) -> Dict[str, object]:
    """Reload one terminal execution and every immutable attempt receipt."""
    receipt = _read_json_object(path=path, label="execution receipt")
    if (
        receipt["execution_id"] != execution_id
        or "execution_receipt_id" not in receipt
        or "attempts" not in receipt
        or "counters" not in receipt
    ):
        raise InvocationControlError("Execution receipt fields are incomplete")
    body = {
        field: receipt[field] for field in receipt if field != "execution_receipt_id"
    }
    if receipt["execution_receipt_id"] != content_hash(value=body):
        raise InvocationControlError("Execution receipt identity differs")
    _add_counters(target=_empty_counters(), source=receipt["counters"])
    if not isinstance(receipt["attempts"], list):
        raise InvocationControlError("Execution attempts must be an array")
    directory = root / "attempts" / _identity_name(identity=execution_id)
    for attempt in receipt["attempts"]:
        if not isinstance(attempt, dict) or "attempt_receipt_id" not in attempt:
            raise InvocationControlError("Execution attempt receipt is invalid")
        attempt_body = {
            field: attempt[field]
            for field in attempt
            if field != "attempt_receipt_id"
        }
        if attempt["attempt_receipt_id"] != content_hash(value=attempt_body):
            raise InvocationControlError("Attempt receipt identity differs")
        attempt_path = directory / (
            "{:02d}_{}.json".format(
                int(attempt["attempt_ordinal"]),
                _identity_name(identity=str(attempt["attempt_receipt_id"])),
            )
        )
        persisted = _read_json_object(path=attempt_path, label="attempt receipt")
        if persisted != attempt:
            raise InvocationControlError("Attempt receipt bytes differ")
    return receipt


def _egress_markers_for_execution(
    *, root: Path, execution_id: str,
) -> List[Dict[str, object]]:
    """Load the exact ordered egress marker set for one execution."""
    directory = root / "egress" / _identity_name(identity=execution_id)
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise InvocationControlError("Egress marker directory is unsafe")
    markers = []
    for path in sorted(directory.iterdir()):
        marker = _read_json_object(path=path, label="egress marker")
        if (
            marker["record_type"] != "PROVIDER_EGRESS_MARKER"
            or marker["execution_id"] != execution_id
            or marker["egress_marker_id"] != content_hash(
                value={
                    field: marker[field]
                    for field in marker
                    if field != "egress_marker_id"
                }
            )
        ):
            raise InvocationControlError("Egress marker identity differs")
        markers.append(marker)
    ordinals = [int(marker["attempt_ordinal"]) for marker in markers]
    if ordinals != list(range(1, len(markers) + 1)):
        raise InvocationControlError("Egress marker sequence differs")
    return markers


def _unknown_remote_outcome_from_markers(
    *, root: Path, reservation_path: Path,
    reservation: Mapping[str, object], requested_execution_id: str,
    clock: Callable[[], str],
) -> Dict[str, object]:
    """Persist crash recovery from egress markers without another call."""
    abandoned_execution_id = str(reservation["execution_id"])
    markers = _egress_markers_for_execution(
        root=root, execution_id=abandoned_execution_id,
    )
    if not markers:
        raise InvocationControlError("Unknown outcome requires egress proof")
    counters = _empty_counters()
    for marker in markers:
        if marker["transport_kind"] == "MOCK":
            counters["mock_transport_invocation_count"] += 1
        elif marker["transport_kind"] == "REAL_MODEL_PROVIDER":
            counters["real_model_provider_egress_count"] += 1
        else:
            raise InvocationControlError("Egress transport kind differs")
    receipt = _terminal_and_release(
        root=root,
        reservation_path=reservation_path,
        reservation=reservation,
        body={
            "schema_version": 1,
            "record_type": "AI_EXECUTION_RECEIPT",
            "execution_id": abandoned_execution_id,
            "ai_invocation_plan_id": reservation["ai_invocation_plan_id"],
            "provider_request_identity": reservation[
                "provider_request_identity"
            ],
            "status": "UNKNOWN_REMOTE_OUTCOME",
            "batch_terminal": True,
            "attempts": [],
            "success_response_receipt_id": None,
            "counters": counters,
            "authorized_at_utc": reservation["reserved_at_utc"],
            "finished_at_utc": _utc(value=clock(), label="recovery time"),
            "unknown_egress_marker_id": markers[-1]["egress_marker_id"],
        },
    )
    if requested_execution_id == abandoned_execution_id:
        return receipt
    return {
        "schema_version": 1,
        "record_type": "AI_EXECUTION_RESULT",
        "execution_id": requested_execution_id,
        "ai_invocation_plan_id": reservation["ai_invocation_plan_id"],
        "provider_request_identity": reservation[
            "provider_request_identity"
        ],
        "status": "UNKNOWN_REMOTE_OUTCOME",
        "batch_terminal": True,
        "attempts": [],
        "success_response_receipt_id": None,
        "unknown_execution_receipt_id": receipt["execution_receipt_id"],
        "counters": counters,
    }


def execute_invocation(
    *,
    workspace_dir: Path,
    plan: Mapping[str, object],
    request_body: bytes,
    execution_id: str,
    owner_token: str,
    authorized_at_utc: str,
    clock: Callable[[], str],
    transport: object,
    response_validator: Callable[[bytes], None],
    evidence_validator: Callable[[bytes], Mapping[str, object]],
) -> Dict[str, object]:
    """Execute or reuse one exact request under single-flight control.

    Args:
        workspace_dir: Local invocation-control workspace.
        plan: Exact AI invocation plan.
        request_body: Exact outbound provider request bytes.
        execution_id: Explicit authorization identity.
        owner_token: Reservation owner identity.
        authorized_at_utc: UTC authorization time bound into execution ID.
        clock: Injected UTC clock for egress/terminal audit timestamps.
        transport: Injected object exposing ``transport_kind`` and ``send``.
        response_validator: Injected strict response-schema validator.
        evidence_validator: Injected full Candidate/Evidence validator that
            returns the exact acceptance closure only when Evidence is PASS.

    Returns:
        Immutable execution receipt or reusable/single-flight result.
    """
    validated_plan = validate_ai_invocation_plan(plan=plan)
    expected_execution_id = execution_identity(
        ai_invocation_plan_id=str(validated_plan["ai_invocation_plan_id"]),
        owner_token=owner_token,
        authorized_at_utc=authorized_at_utc,
    )
    if execution_id != expected_execution_id:
        raise InvocationControlError("Execution identity differs")
    _validate_request_resources(plan=validated_plan, request_body=request_body)
    root = _state_root(workspace_dir=workspace_dir)
    _persist_invocation_input(
        root=root, plan=validated_plan, request_body=request_body,
    )
    execution_path = _execution_path(root=root, execution_id=execution_id)
    if execution_path.exists():
        return _load_execution_receipt(
            root=root, path=execution_path, execution_id=execution_id,
        )
    counters = _empty_counters()
    reusable = _load_success_response(root=root, plan=validated_plan)
    if reusable is not None:
        return _terminal_execution(
            root=root,
            body={
                "schema_version": 1,
                "record_type": "AI_EXECUTION_RECEIPT",
                "execution_id": execution_id,
                "ai_invocation_plan_id": validated_plan["ai_invocation_plan_id"],
                "provider_request_identity": validated_plan[
                    "provider_request_identity"
                ],
                "status": "REUSED_SUCCESS",
                "batch_terminal": False,
                "attempts": [],
                "success_response_receipt_id": reusable[
                    "success_response_receipt_id"
                ],
                "counters": counters,
                "authorized_at_utc": authorized_at_utc,
                "finished_at_utc": _utc(value=clock(), label="finish time"),
            },
        )
    owner_hash = content_hash(value=_text(value=owner_token, label="owner token"))
    reservation = {
        "schema_version": 1,
        "record_type": "SINGLE_FLIGHT_RESERVATION",
        "execution_id": execution_id,
        "ai_invocation_plan_id": validated_plan["ai_invocation_plan_id"],
        "provider_request_identity": validated_plan["provider_request_identity"],
        "owner_token_hash": owner_hash,
        "owner_process_id": os.getpid(),
        "reserved_at_utc": _utc(
            value=authorized_at_utc, label="reservation time"
        ),
        "egress_started_at_utc": None,
        "attempt_ordinal": 1,
    }
    reservation_path = _reservation_path(
        root=root,
        request_identity=str(validated_plan["provider_request_identity"]),
    )
    try:
        descriptor = os.open(
            reservation_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        try:
            existing_reservation = _read_json_object(
                path=reservation_path, label="single-flight reservation",
            )
        except InvocationControlError:
            if reservation_path.exists():
                raise
            return execute_invocation(
                workspace_dir=workspace_dir,
                plan=validated_plan,
                request_body=request_body,
                execution_id=execution_id,
                owner_token=owner_token,
                authorized_at_utc=authorized_at_utc,
                clock=clock,
                transport=transport,
                response_validator=response_validator,
                evidence_validator=evidence_validator,
            )
        if (
            existing_reservation["provider_request_identity"]
            != validated_plan["provider_request_identity"]
            or existing_reservation["ai_invocation_plan_id"]
            != validated_plan["ai_invocation_plan_id"]
        ):
            raise InvocationControlError("Single-flight reservation differs")
        reusable = _load_success_response(root=root, plan=validated_plan)
        if reusable is not None:
            _archive_reservation(
                root=root,
                reservation_path=reservation_path,
                reservation=existing_reservation,
                terminal_status="SUCCEEDED",
            )
            return _terminal_execution(
                root=root,
                body={
                    "schema_version": 1,
                    "record_type": "AI_EXECUTION_RECEIPT",
                    "execution_id": execution_id,
                    "ai_invocation_plan_id": validated_plan[
                        "ai_invocation_plan_id"
                    ],
                    "provider_request_identity": validated_plan[
                        "provider_request_identity"
                    ],
                    "status": "REUSED_SUCCESS",
                    "batch_terminal": False,
                    "attempts": [],
                    "success_response_receipt_id": reusable[
                        "success_response_receipt_id"
                    ],
                    "counters": counters,
                    "authorized_at_utc": authorized_at_utc,
                    "finished_at_utc": _utc(
                        value=clock(), label="finish time"
                    ),
                },
            )
        abandoned_execution_id = str(existing_reservation["execution_id"])
        abandoned_execution_path = _execution_path(
            root=root, execution_id=abandoned_execution_id,
        )
        if abandoned_execution_path.exists():
            abandoned_receipt = _load_execution_receipt(
                root=root,
                path=abandoned_execution_path,
                execution_id=abandoned_execution_id,
            )
            _archive_reservation(
                root=root,
                reservation_path=reservation_path,
                reservation=existing_reservation,
                terminal_status=str(abandoned_receipt["status"]),
            )
            return execute_invocation(
                workspace_dir=workspace_dir,
                plan=validated_plan,
                request_body=request_body,
                execution_id=execution_id,
                owner_token=owner_token,
                authorized_at_utc=authorized_at_utc,
                clock=clock,
                transport=transport,
                response_validator=response_validator,
                evidence_validator=evidence_validator,
            )
        if (
            _egress_markers_for_execution(
                root=root, execution_id=abandoned_execution_id,
            )
            and not _process_is_alive(
                process_id=existing_reservation["owner_process_id"]
            )
        ):
            return _unknown_remote_outcome_from_markers(
                root=root,
                reservation_path=reservation_path,
                reservation=existing_reservation,
                requested_execution_id=execution_id,
                clock=clock,
            )
        return {
            "schema_version": 1,
            "record_type": "AI_EXECUTION_RESULT",
            "execution_id": execution_id,
            "ai_invocation_plan_id": validated_plan["ai_invocation_plan_id"],
            "provider_request_identity": validated_plan[
                "provider_request_identity"
            ],
            "status": "SINGLE_FLIGHT_HELD",
            "batch_terminal": False,
            "attempts": [],
            "success_response_receipt_id": None,
            "counters": counters,
        }
    try:
        content = canonical_json_bytes(value=reservation)
        offset = 0
        while offset < len(content):
            written = os.write(descriptor, content[offset:])
            if written <= 0:
                raise InvocationControlError("Reservation write stopped")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

    transport_kind = _text(
        value=getattr(transport, "transport_kind", None),
        label="transport kind",
    )
    if transport_kind not in {"MOCK", "REAL_MODEL_PROVIDER"}:
        raise InvocationControlError("Transport kind is invalid")
    attempts = []
    for attempt_ordinal in (1, 2):
        marker = _egress_marker(
            root=root,
            execution_id=execution_id,
            plan=validated_plan,
            attempt_ordinal=attempt_ordinal,
            egress_started_at_utc=clock(),
            transport_kind=transport_kind,
        )
        if transport_kind == "MOCK":
            counters["mock_transport_invocation_count"] += 1
        else:
            counters["real_model_provider_egress_count"] += 1
        try:
            raw_result = transport.send(
                request_body=request_body,
                plan=validated_plan,
                execution_id=execution_id,
                attempt_ordinal=attempt_ordinal,
            )
        except UnknownRemoteOutcomeError:
            return _terminal_and_release(
                root=root,
                reservation_path=reservation_path,
                reservation=reservation,
                body={
                    "schema_version": 1,
                    "record_type": "AI_EXECUTION_RECEIPT",
                    "execution_id": execution_id,
                    "ai_invocation_plan_id": validated_plan[
                        "ai_invocation_plan_id"
                    ],
                    "provider_request_identity": validated_plan[
                        "provider_request_identity"
                    ],
                    "status": "UNKNOWN_REMOTE_OUTCOME",
                    "batch_terminal": True,
                    "attempts": attempts,
                    "success_response_receipt_id": None,
                    "counters": counters,
                    "authorized_at_utc": authorized_at_utc,
                    "finished_at_utc": _utc(
                        value=clock(), label="finish time"
                    ),
                    "unknown_egress_marker_id": marker["egress_marker_id"],
                },
            )
        result = _transport_result(value=raw_result)
        if result["paid_call"]:
            counters["paid_model_provider_call_count"] += 1
        classification = _classify(result=result)
        acceptance_draft: Optional[Mapping[str, object]] = None
        if classification == "SUCCESS":
            try:
                response_validator(response_body=result["response_body"])
            except SchemaViolationError:
                classification = "TERMINAL"
                result["error_class"] = "SCHEMA_VIOLATION"
            if classification == "SUCCESS":
                try:
                    acceptance_draft = evidence_validator(
                        response_body=result["response_body"]
                    )
                except EvidenceFailureError:
                    classification = "TERMINAL"
                    result["error_class"] = "EVIDENCE_FAILURE"
        acceptance_receipt: Optional[Dict[str, object]] = None
        if classification == "SUCCESS":
            try:
                acceptance_receipt = _persist_acceptance_receipt(
                    root=root,
                    plan=validated_plan,
                    response_body=result["response_body"],
                    acceptance_draft=acceptance_draft,
                )
            except InvocationControlError:
                classification = "TERMINAL"
                result["error_class"] = "EVIDENCE_FAILURE"
        if classification == "SUCCESS":
            if acceptance_receipt is None:
                raise InvocationControlError(
                    "Successful invocation lacks acceptance receipt"
                )
            attempt = _attempt_receipt(
                root=root,
                execution_id=execution_id,
                body={
                    "schema_version": 1,
                    "record_type": "AI_INVOCATION_ATTEMPT_RECEIPT",
                    "execution_id": execution_id,
                    "ai_invocation_plan_id": validated_plan[
                        "ai_invocation_plan_id"
                    ],
                    "provider_request_identity": validated_plan[
                        "provider_request_identity"
                    ],
                    "attempt_ordinal": attempt_ordinal,
                    "status": "SUCCEEDED",
                    "error_class": "",
                    "status_code": result["status_code"],
                    "egress_marker_id": marker["egress_marker_id"],
                    "response_body_sha256": sha256_bytes(
                        content=result["response_body"]
                    ),
                    "provider_request_id": result["provider_request_id"],
                    "paid_call": result["paid_call"],
                    "transport_kind": transport_kind,
                    "usage": dict(result["usage"]),
                    "finished_at_utc": _utc(
                        value=clock(), label="attempt finish time"
                    ),
                },
            )
            attempts.append(attempt)
            success = _persist_success_response(
                root=root,
                plan=validated_plan,
                result=result,
                attempt_receipt_id=str(attempt["attempt_receipt_id"]),
                acceptance_receipt=acceptance_receipt,
            )
            return _terminal_and_release(
                root=root,
                reservation_path=reservation_path,
                reservation=reservation,
                body={
                    "schema_version": 1,
                    "record_type": "AI_EXECUTION_RECEIPT",
                    "execution_id": execution_id,
                    "ai_invocation_plan_id": validated_plan[
                        "ai_invocation_plan_id"
                    ],
                    "provider_request_identity": validated_plan[
                        "provider_request_identity"
                    ],
                    "status": "SUCCEEDED",
                    "batch_terminal": False,
                    "attempts": attempts,
                    "success_response_receipt_id": success[
                        "success_response_receipt_id"
                    ],
                    "counters": counters,
                    "authorized_at_utc": authorized_at_utc,
                    "finished_at_utc": _utc(
                        value=clock(), label="finish time"
                    ),
                },
            )
        retryable = classification == "RETRYABLE" and attempt_ordinal == 1
        attempt_status = (
            "FAILED_RETRYABLE"
            if retryable
            else "FAILED_RETRYABLE_FINAL"
            if classification == "RETRYABLE"
            else "FAILED_TERMINAL"
        )
        attempt = _attempt_receipt(
            root=root,
            execution_id=execution_id,
            body={
                "schema_version": 1,
                "record_type": "AI_INVOCATION_ATTEMPT_RECEIPT",
                "execution_id": execution_id,
                "ai_invocation_plan_id": validated_plan[
                    "ai_invocation_plan_id"
                ],
                "provider_request_identity": validated_plan[
                    "provider_request_identity"
                ],
                "attempt_ordinal": attempt_ordinal,
                "status": attempt_status,
                "error_class": _error_class(result=result),
                "status_code": result["status_code"],
                "egress_marker_id": marker["egress_marker_id"],
                "response_body_sha256": sha256_bytes(
                    content=result["response_body"]
                ),
                "provider_request_id": result["provider_request_id"],
                "paid_call": result["paid_call"],
                "transport_kind": transport_kind,
                "usage": dict(result["usage"]),
                "finished_at_utc": _utc(
                    value=clock(), label="attempt finish time"
                ),
            },
        )
        attempts.append(attempt)
        if retryable:
            continue
        return _terminal_and_release(
            root=root,
            reservation_path=reservation_path,
            reservation=reservation,
            body={
                "schema_version": 1,
                "record_type": "AI_EXECUTION_RECEIPT",
                "execution_id": execution_id,
                "ai_invocation_plan_id": validated_plan[
                    "ai_invocation_plan_id"
                ],
                "provider_request_identity": validated_plan[
                    "provider_request_identity"
                ],
                "status": attempt_status,
                "batch_terminal": True,
                "attempts": attempts,
                "success_response_receipt_id": None,
                "counters": counters,
                "authorized_at_utc": authorized_at_utc,
                "finished_at_utc": _utc(value=clock(), label="finish time"),
            },
        )
    raise InvocationControlError("Invocation retry loop did not terminate")


def execute_batch(
    *, workspace_dir: Path, invocations: Sequence[Mapping[str, object]],
    clock: Callable[[], str], transport: object,
    response_validator: Callable[[bytes], None],
    evidence_validator: Callable[[bytes], Mapping[str, object]],
) -> Dict[str, object]:
    """Execute ordered stability ordinals and stop on the first terminal.

    Args:
        workspace_dir: Local invocation-control workspace.
        invocations: Ordered exact execution inputs with stability ordinals.
        clock: Injected UTC clock.
        transport: Injected mock or approved real transport.
        response_validator: Strict response validator.
        evidence_validator: Full Candidate/Evidence acceptance validator.

    Returns:
        Batch status, completed/skipped ordinals, receipts, and counters.
    """
    counters = _empty_counters()
    receipts = []
    completed = []
    skipped = []
    batch_status = "SUCCEEDED"
    for index, invocation_value in enumerate(invocations):
        invocation = _object(value=invocation_value, label="batch invocation")
        expected_fields = {
            "authorized_at_utc",
            "execution_id",
            "owner_token",
            "plan",
            "request_body",
            "stability_ordinal",
        }
        _exact_fields(
            value=invocation,
            expected=expected_fields,
            label="batch invocation",
        )
        if type(invocation["stability_ordinal"]) is not int or invocation[
            "stability_ordinal"
        ] <= 0:
            raise InvocationControlError("Stability ordinal is invalid")
        receipt = execute_invocation(
            workspace_dir=workspace_dir,
            plan=invocation["plan"],
            request_body=invocation["request_body"],
            execution_id=str(invocation["execution_id"]),
            owner_token=str(invocation["owner_token"]),
            authorized_at_utc=str(invocation["authorized_at_utc"]),
            clock=clock,
            transport=transport,
            response_validator=response_validator,
            evidence_validator=evidence_validator,
        )
        receipts.append(receipt)
        _add_counters(target=counters, source=receipt["counters"])
        completed.append(int(invocation["stability_ordinal"]))
        if receipt["batch_terminal"]:
            batch_status = "TERMINATED"
            skipped = [
                int(remaining["stability_ordinal"])
                for remaining in invocations[index + 1:]
            ]
            break
        if receipt["status"] == "SINGLE_FLIGHT_HELD":
            batch_status = "BLOCKED_SINGLE_FLIGHT"
            skipped = [
                int(remaining["stability_ordinal"])
                for remaining in invocations[index + 1:]
            ]
            break
    return {
        "schema_version": 1,
        "record_type": "AI_INVOCATION_BATCH_RESULT",
        "status": batch_status,
        "completed_stability_ordinals": completed,
        "skipped_stability_ordinals": skipped,
        "execution_receipts": receipts,
        "counters": counters,
    }


def structured_only_result(
    *, repo_root: Path, workspace_dir: Path, release_input_plan_id: str,
    cumulative_metric_ids: Sequence[str], result_coordinate_count: int,
) -> Dict[str, object]:
    """Derive zero-provider counts from routes and the exact disk namespace.

    Args:
        repo_root: Repository containing SourceStrategy authority.
        workspace_dir: Release-specific invocation observation workspace.
        release_input_plan_id: Exact release input plan identity.
        cumulative_metric_ids: Exact structured-only release metric set.
        result_coordinate_count: Complete deterministic result count.

    Returns:
        Content-addressed empty invocation closure and derived counters.
    """
    from .source_strategy import load_source_strategy_registry

    _sha256_identity(value=release_input_plan_id, label="release input plan id")
    if type(result_coordinate_count) is not int or result_coordinate_count < 0:
        raise InvocationControlError("Structured-only result count is invalid")
    if (
        not isinstance(cumulative_metric_ids, (list, tuple))
        or not cumulative_metric_ids
        or any(
            not isinstance(metric_id, str) or not metric_id
            for metric_id in cumulative_metric_ids
        )
        or len(cumulative_metric_ids) != len(set(cumulative_metric_ids))
    ):
        raise InvocationControlError("Structured-only metric set is invalid")
    registry = load_source_strategy_registry(repo_root=repo_root)
    metrics = registry["metrics"]
    if any(metric_id not in metrics for metric_id in cumulative_metric_ids):
        raise InvocationControlError("Structured-only metric route is absent")
    source_mode_by_metric = {
        metric_id: metrics[metric_id]["source_mode"]
        for metric_id in sorted(cumulative_metric_ids)
    }
    if set(source_mode_by_metric.values()) != {"structured_only"}:
        raise InvocationControlError("Release contains a model-provider route")
    root = _state_root(workspace_dir=workspace_dir)
    observed_files = {}
    for namespace in sorted(
        path.name for path in root.iterdir() if path.is_dir()
    ):
        bindings = []
        directory = root / namespace
        for path in sorted(directory.rglob("*")):
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise InvocationControlError(
                    "Invocation observation namespace is unsafe"
                )
            if not path.is_file():
                continue
            content = path.read_bytes()
            bindings.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_bytes(content=content),
                    "size": len(content),
                }
            )
        observed_files[namespace] = bindings
    emitted = [
        binding
        for bindings in observed_files.values()
        for binding in bindings
    ]
    if emitted:
        raise InvocationControlError(
            "Structured-only release emitted invocation state"
        )
    counters = _empty_counters()
    body = {
        "schema_version": 1,
        "record_type": "STRUCTURED_ONLY_INVOCATION_RESULT",
        "release_input_plan_id": release_input_plan_id,
        "source_mode_by_metric": source_mode_by_metric,
        "result_coordinate_count": result_coordinate_count,
        "status": "SUCCEEDED_ZERO_PROVIDER",
        "observed_invocation_files": observed_files,
        "observed_ai_invocation_plan_ids": [],
        "observed_provider_request_identities": [],
        "counters": counters,
    }
    return {
        **body,
        "invocation_observation_id": content_hash(value=body),
    }


def recover_abandoned_before_egress(
    *, workspace_dir: Path, request_identity: str,
    expected_execution_id: str, recovered_at_utc: str,
) -> Dict[str, object]:
    """Archive a proven pre-egress orphan so a new execution may reserve.

    Args:
        workspace_dir: Invocation-control workspace.
        request_identity: Exact provider request identity.
        expected_execution_id: Orphaned execution identity.
        recovered_at_utc: Explicit UTC recovery time.

    Returns:
        Immutable ABANDONED_BEFORE_EGRESS recovery receipt.
    """
    root = _state_root(workspace_dir=workspace_dir)
    reservation_path = _reservation_path(
        root=root, request_identity=request_identity,
    )
    reservation = _read_json_object(
        path=reservation_path, label="single-flight reservation"
    )
    if reservation["execution_id"] != expected_execution_id:
        raise InvocationControlError("Abandoned reservation execution differs")
    egress_dir = root / "egress" / _identity_name(identity=expected_execution_id)
    if egress_dir.exists() and any(egress_dir.iterdir()):
        raise InvocationControlError("UNKNOWN_REMOTE_OUTCOME")
    body = {
        "schema_version": 1,
        "record_type": "ABANDONED_BEFORE_EGRESS_RECEIPT",
        "execution_id": expected_execution_id,
        "provider_request_identity": request_identity,
        "reservation_hash": content_hash(value=reservation),
        "status": "ABANDONED_BEFORE_EGRESS",
        "recovered_at_utc": _utc(
            value=recovered_at_utc, label="recovery time"
        ),
    }
    receipt = dict(body)
    receipt["recovery_receipt_id"] = content_hash(value=body)
    destination = (
        root
        / "abandoned"
        / (
            _identity_name(identity=str(receipt["recovery_receipt_id"]))
            + ".json"
        )
    )
    _exclusive_write_json(path=destination, value=receipt)
    os.replace(reservation_path, destination.with_suffix(".reservation.json"))
    return receipt
