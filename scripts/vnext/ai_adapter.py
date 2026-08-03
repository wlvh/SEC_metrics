"""Run isolated recorded or explicitly approved AI transport attempts.

The adapter never imports or reuses ``SecHttpClient``. It receives complete
request bytes and returns response bytes; persistence remains an explicit Run
boundary owned by the caller.
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Dict, Mapping, Optional, Tuple

from .canonical import CanonicalError, canonical_json_bytes, content_hash
from .canonical import sha256_bytes
from .canonical import strict_json_loads
from .reader import validate_reader_output
from .reader_input import PreparedReaderRequest, READER_SYSTEM_CONTRACT
from .records import validate_record
from .requirements import RequirementError, load_requirement_snapshot


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_TRANSPORT_FACTORIES: Mapping[str, Callable[..., object]] = MappingProxyType(
    {}
)
_ADAPTER_AUTHORITY = object()


class AIAdapterError(RuntimeError):
    """Report disabled, failed, or policy-incompatible model transport."""


@dataclass(frozen=True)
class TransportPolicy:
    """Represent every field of the effective approved D-01 choice.

    Attributes:
        provider: Repository-selected provider identifier.
        model: Repository-selected model identifier.
        endpoint_host: Exact allowed remote host.
        region: Approved processing region.
        retention: Approved retention mode.
        data_use: Approved provider data-use mode.
        timeout_seconds: Per-attempt transport timeout.
        retry_count: Maximum transport retries.
        maximum_payload_bytes: Maximum outbound body size.
        filing_egress_policy: Approved filing-egress classification.
    """

    provider: str
    model: str
    endpoint_host: str
    region: str
    retention: str
    data_use: str
    timeout_seconds: int
    retry_count: int
    maximum_payload_bytes: int
    filing_egress_policy: str

    @classmethod
    def from_mapping(cls, *, value: Mapping[str, object]) -> "TransportPolicy":
        """Compile one exact validated D-01 choice.

        Args:
            value: Effective Decision ``choice`` mapping.

        Returns:
            Immutable transport policy.

        Raises:
            AIAdapterError: On an extra, missing, empty, or invalid field.
        """
        required = {
            "provider",
            "model",
            "endpoint_host",
            "region",
            "retention",
            "data_use",
            "timeout_seconds",
            "retry_count",
            "maximum_payload_bytes",
            "filing_egress_policy",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise AIAdapterError("D-01 choice fields are not exact")
        for key in (
            "provider",
            "model",
            "endpoint_host",
            "region",
            "retention",
            "data_use",
            "filing_egress_policy",
        ):
            if not isinstance(value[key], str) or not value[key]:
                raise AIAdapterError("D-01 field is empty: {}".format(key))
        if (
            type(value["timeout_seconds"]) is not int
            or value["timeout_seconds"] <= 0
        ):
            raise AIAdapterError(
                "D-01 numeric field is invalid: timeout_seconds"
            )
        if type(value["retry_count"]) is not int or value["retry_count"] < 0:
            raise AIAdapterError("D-01 numeric field is invalid: retry_count")
        if (
            type(value["maximum_payload_bytes"]) is not int
            or value["maximum_payload_bytes"] <= 0
        ):
            raise AIAdapterError(
                "D-01 numeric field is invalid: maximum_payload_bytes"
            )
        return cls(
            provider=str(value["provider"]),
            model=str(value["model"]),
            endpoint_host=str(value["endpoint_host"]),
            region=str(value["region"]),
            retention=str(value["retention"]),
            data_use=str(value["data_use"]),
            timeout_seconds=int(value["timeout_seconds"]),
            retry_count=int(value["retry_count"]),
            maximum_payload_bytes=int(value["maximum_payload_bytes"]),
            filing_egress_policy=str(value["filing_egress_policy"]),
        )

    def as_mapping(self) -> Dict[str, object]:
        """Return the exact JSON-like D-01 field mapping."""
        return {
            "provider": self.provider,
            "model": self.model,
            "endpoint_host": self.endpoint_host,
            "region": self.region,
            "retention": self.retention,
            "data_use": self.data_use,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "maximum_payload_bytes": self.maximum_payload_bytes,
            "filing_egress_policy": self.filing_egress_policy,
        }


@dataclass(frozen=True)
class TransportObservation:
    """Record facts reported by one repository-owned transport execution.

    Attributes mirror applied D-01 controls and add whether egress occurred,
    actual retries, and exact outbound byte length. ``endpoint_host`` is
    ``none`` when preflight blocks before transport.
    """

    egress_attempted: bool
    provider: str
    model: str
    endpoint_host: str
    region: str
    retention: str
    data_use: str
    timeout_seconds: int
    retry_count: int
    retries_performed: int
    maximum_payload_bytes: int
    filing_egress_policy: str
    request_body_bytes: int

    @classmethod
    def from_mapping(
        cls, *, value: Mapping[str, object]
    ) -> "TransportObservation":
        """Rebuild exact persisted transport facts without coercion.

        Args:
            value: Attempt ``transport_observation`` mapping.

        Returns:
            Strict immutable transport observation.

        Raises:
            AIAdapterError: On missing, extra, or invalid fields.
        """
        required = {
            "egress_attempted",
            "provider",
            "model",
            "endpoint_host",
            "region",
            "retention",
            "data_use",
            "timeout_seconds",
            "retry_count",
            "retries_performed",
            "maximum_payload_bytes",
            "filing_egress_policy",
            "request_body_bytes",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise AIAdapterError("Transport observation fields are not exact")
        return cls(
            egress_attempted=value["egress_attempted"],
            provider=value["provider"],
            model=value["model"],
            endpoint_host=value["endpoint_host"],
            region=value["region"],
            retention=value["retention"],
            data_use=value["data_use"],
            timeout_seconds=value["timeout_seconds"],
            retry_count=value["retry_count"],
            retries_performed=value["retries_performed"],
            maximum_payload_bytes=value["maximum_payload_bytes"],
            filing_egress_policy=value["filing_egress_policy"],
            request_body_bytes=value["request_body_bytes"],
        )

    def __post_init__(self) -> None:
        """Reject ambiguous or internally contradictory transport facts."""
        for value in (
            self.provider,
            self.model,
            self.endpoint_host,
            self.region,
            self.retention,
            self.data_use,
            self.filing_egress_policy,
        ):
            if not isinstance(value, str) or not value:
                raise AIAdapterError("Transport observation text is empty")
        if type(self.egress_attempted) is not bool:
            raise AIAdapterError("Transport egress fact must be boolean")
        for value in (
            self.timeout_seconds,
            self.retry_count,
            self.retries_performed,
            self.maximum_payload_bytes,
            self.request_body_bytes,
        ):
            if type(value) is not int or value < 0:
                raise AIAdapterError("Transport observation count is invalid")
        if self.request_body_bytes < 1:
            raise AIAdapterError("Transport request byte count is invalid")
        if self.retries_performed > self.retry_count:
            raise AIAdapterError("Transport retries exceed the applied limit")
        if self.egress_attempted and self.endpoint_host == "none":
            raise AIAdapterError("Attempted egress lacks an actual host")
        if not self.egress_attempted and self.endpoint_host != "none":
            raise AIAdapterError("Non-egress observation claims a remote host")

    def as_mapping(self) -> Dict[str, object]:
        """Return exact JSON-like facts for the attempt record."""
        return {
            "egress_attempted": self.egress_attempted,
            "provider": self.provider,
            "model": self.model,
            "endpoint_host": self.endpoint_host,
            "region": self.region,
            "retention": self.retention,
            "data_use": self.data_use,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "retries_performed": self.retries_performed,
            "maximum_payload_bytes": self.maximum_payload_bytes,
            "filing_egress_policy": self.filing_egress_policy,
            "request_body_bytes": self.request_body_bytes,
        }


@dataclass(frozen=True)
class TransportResult:
    """Return raw provider bytes, request identity, and execution facts."""

    response_bytes: bytes
    provider_request_id: str
    observation: TransportObservation

    def __post_init__(self) -> None:
        """Reject result types that cannot form an immutable attempt."""
        if not isinstance(self.response_bytes, bytes):
            raise AIAdapterError("Transport response must be bytes")
        if not isinstance(self.provider_request_id, str):
            raise AIAdapterError("Transport request ID must be text")
        if not isinstance(self.observation, TransportObservation):
            raise AIAdapterError("Transport observation type is invalid")


class TransportAttemptError(AIAdapterError):
    """Carry actual transport facts across a failed attempt boundary."""

    def __init__(
        self,
        message: str,
        *,
        observation: TransportObservation,
        provider_request_id: str,
        raw_response_bytes: Optional[bytes],
        error_class: str,
    ) -> None:
        """Create one auditable transport failure.

        Args:
            message: Human-readable diagnostic.
            observation: Actual execution facts, including no-egress preflight.
            provider_request_id: Provider request identity when available.
            raw_response_bytes: Exact returned bytes when available.
            error_class: Underlying stable failure class.
        """
        super().__init__(message)
        if not isinstance(observation, TransportObservation):
            raise AIAdapterError("Transport failure observation is invalid")
        if not isinstance(provider_request_id, str) or not error_class:
            raise AIAdapterError("Transport failure audit fields are invalid")
        if raw_response_bytes is not None and not isinstance(
            raw_response_bytes, bytes
        ):
            raise AIAdapterError("Transport failure raw response is invalid")
        self.observation = observation
        self.provider_request_id = provider_request_id
        self.raw_response_bytes = raw_response_bytes
        self.error_class = error_class


class AIAdapter(ABC):
    """Define the provider-neutral transport surface."""

    provider: str
    model: str
    endpoint_host: str

    def __init__(self, *, authority: object) -> None:
        """Bind one adapter to the module-owned construction authority.

        Args:
            authority: Private token available only to repository factories.
        """
        if authority is not _ADAPTER_AUTHORITY:
            raise AIAdapterError(
                "AI adapter must come from a repository factory"
            )
        self._authority = authority

    @abstractmethod
    def complete(self, *, request_bytes: bytes) -> TransportResult:
        """Return raw response bytes, provider request ID, and transport facts.

        Args:
            request_bytes: Exact payload bytes bound by the attempt record.

        Returns:
            Complete auditable transport result.
        """
        raise NotImplementedError


class _RecordedAdapter(AIAdapter):
    """Return immutable recorded bytes without opening a network socket."""

    def __init__(
        self, *, response_bytes: bytes, fixture_id: str, authority: object
    ) -> None:
        """Create a deterministic recorded adapter.

        Args:
            response_bytes: Frozen response payload.
            fixture_id: Opaque test/recording identity.
            authority: Module-owned construction token.
        """
        super().__init__(authority=authority)
        if not response_bytes or not fixture_id:
            raise AIAdapterError(
                "Recorded response and fixture_id are required"
            )
        self._response_bytes = response_bytes
        self._fixture_id = fixture_id
        self.provider = "recorded"
        self.model = "recorded-response-v1"
        self.endpoint_host = "none"

    def complete(self, *, request_bytes: bytes) -> TransportResult:
        """Return the frozen response and make no external call.

        Args:
            request_bytes: Non-empty exact request bytes.

        Returns:
            Frozen response, fixture identity, and explicit no-egress facts.
        """
        if not request_bytes:
            raise AIAdapterError("Reader request body is empty")
        observation = TransportObservation(
            egress_attempted=False,
            provider=self.provider,
            model=self.model,
            endpoint_host="none",
            region="local",
            retention="immutable-fixture",
            data_use="none",
            timeout_seconds=0,
            retry_count=0,
            retries_performed=0,
            maximum_payload_bytes=len(request_bytes),
            filing_egress_policy="none",
            request_body_bytes=len(request_bytes),
        )
        return TransportResult(
            response_bytes=self._response_bytes,
            provider_request_id=self._fixture_id,
            observation=observation,
        )


def build_recorded_adapter(
    *, response_bytes: bytes, fixture_id: str
) -> AIAdapter:
    """Build the only repository-authorized no-egress adapter.

    Args:
        response_bytes: Frozen response payload.
        fixture_id: Opaque test/recording identity.

    Returns:
        Exact private recorded adapter accepted by ``run_ai_attempt``.
    """
    return _RecordedAdapter(
        response_bytes=response_bytes,
        fixture_id=fixture_id,
        authority=_ADAPTER_AUTHORITY,
    )


def approved_transport_policy(
    *, requirement: Mapping[str, object]
) -> TransportPolicy:
    """Compile the unique effective APPROVED D-01 from one Requirement.

    Args:
        requirement: Strict Requirement Snapshot result.

    Returns:
        Exact immutable remote transport policy.

    Raises:
        AIAdapterError: When D-01 is pending, absent, or not approved.
    """
    if (
        "D-01" in requirement["pending_decision_ids"]
        or "D-01" not in requirement["effective_decisions"]
    ):
        raise AIAdapterError("Remote transport requires approved D-01")
    decision = requirement["effective_decisions"]["D-01"]
    if decision["status"] != "APPROVED":
        raise AIAdapterError("Remote transport requires approved D-01")
    return TransportPolicy.from_mapping(value=decision["choice"])


def _load_transport_policy() -> Tuple[TransportPolicy, str]:
    """Load effective D-01 only from the module-fixed repository authority.

    Returns:
        Immutable policy and Requirement closure hash.

    Raises:
        AIAdapterError: When authority is unsafe, invalid, or not approved.
    """
    # Authority must follow this module's repository, because a caller-
    # selected root could replace the pending Decision Register wholesale.
    repo_root = _REPOSITORY_ROOT
    if not isinstance(repo_root, Path) or repo_root.is_symlink():
        raise AIAdapterError("D-01 repository root is unsafe")
    snapshot_dir = repo_root / "requirements" / "ai_first_v3_3_1"
    current = repo_root
    for part in ("requirements", "ai_first_v3_3_1"):
        current /= part
        if current.is_symlink():
            raise AIAdapterError("D-01 Requirement path is unsafe")
    try:
        requirement = load_requirement_snapshot(
            snapshot_dir=snapshot_dir,
        )
    except (CanonicalError, RequirementError) as error:
        raise AIAdapterError(
            "D-01 Requirement Snapshot is invalid"
        ) from error
    return (
        approved_transport_policy(requirement=requirement),
        str(requirement["requirement_closure_hash"]),
    )


def _no_egress_policy_observation(
    *, policy: TransportPolicy, request_bytes: bytes
) -> TransportObservation:
    """Build exact no-egress facts for an adapter-owned preflight failure.

    Args:
        policy: Exact effective D-01 policy.
        request_bytes: Exact outbound bytes.

    Returns:
        Deterministic observation proving transport was not invoked.
    """
    return TransportObservation(
        egress_attempted=False,
        provider=policy.provider,
        model=policy.model,
        endpoint_host="none",
        region=policy.region,
        retention=policy.retention,
        data_use=policy.data_use,
        timeout_seconds=policy.timeout_seconds,
        retry_count=policy.retry_count,
        retries_performed=0,
        maximum_payload_bytes=policy.maximum_payload_bytes,
        filing_egress_policy=policy.filing_egress_policy,
        request_body_bytes=len(request_bytes),
    )


def transport_observation_mismatch(
    *,
    policy: TransportPolicy,
    observation: TransportObservation,
    request_bytes: bytes,
) -> Optional[str]:
    """Return the first policy/actual mismatch, if any.

    Args:
        policy: Effective D-01 controls.
        observation: Facts returned by repository transport.
        request_bytes: Exact payload supplied to it.

    Returns:
        Mismatched field name or ``None`` when every enforced field agrees.
    """
    expected = policy.as_mapping()
    actual = observation.as_mapping()
    expected["request_body_bytes"] = len(request_bytes)
    for field in (
        "provider",
        "model",
        "endpoint_host",
        "region",
        "retention",
        "data_use",
        "timeout_seconds",
        "retry_count",
        "maximum_payload_bytes",
        "filing_egress_policy",
        "request_body_bytes",
    ):
        if actual[field] != expected[field]:
            return field
    if not observation.egress_attempted:
        return "egress_attempted"
    return None


def _build_repository_transport(*, policy: TransportPolicy) -> object:
    """Construct one fresh repository transport bound to exact D-01.

    Args:
        policy: Current immutable effective D-01 policy.

    Returns:
        Repository-factory transport with the exact policy and API.

    Raises:
        AIAdapterError: When no factory exists or its result is invalid.
    """
    if policy.provider not in _TRANSPORT_FACTORIES:
        raise AIAdapterError(
            "D-01 provider has no repository transport factory"
        )
    transport = _TRANSPORT_FACTORIES[policy.provider](policy=policy)
    if not hasattr(transport, "policy") or transport.policy != policy:
        raise AIAdapterError(
            "Repository transport policy differs from D-01"
        )
    if not hasattr(transport, "complete") or not callable(
        transport.complete
    ):
        raise AIAdapterError(
            "Repository transport implementation is invalid"
        )
    return transport


class _ApprovedTransportAdapter(AIAdapter):
    """Resolve a fresh repository transport for each approved attempt."""

    def __init__(self, *, authority: object) -> None:
        """Compile D-01 and verify its repository factory is available.

        Args:
            authority: Module-owned construction token.

        Raises:
            AIAdapterError: When D-01 is unavailable or its provider has no
                committed factory.
        """
        super().__init__(authority=authority)
        policy, requirement_closure_hash = _load_transport_policy()
        if policy.provider not in _TRANSPORT_FACTORIES:
            raise AIAdapterError(
                "D-01 provider has no repository transport factory"
            )
        self.provider = policy.provider
        self.model = policy.model
        self.endpoint_host = policy.endpoint_host
        self.requirement_closure_hash = requirement_closure_hash
        self.policy = policy

    def complete(self, *, request_bytes: bytes) -> TransportResult:
        """Execute one exact-policy transport and verify returned facts.

        Args:
            request_bytes: Exact outbound body without secret headers.

        Returns:
            Raw response and actual transport facts.

        Raises:
            AIAdapterError: On invalid input, changed D-01 authority, or an
                invoked transport that omits actual observation facts.
            TransportAttemptError: On an observed preflight, transport,
                response, or policy mismatch failure.
        """
        if not isinstance(request_bytes, bytes) or not request_bytes:
            raise AIAdapterError("Reader request body is empty or invalid")
        current_policy, current_closure_hash = _load_transport_policy()
        if (
            current_policy != self.policy
            or current_closure_hash != self.requirement_closure_hash
        ):
            raise AIAdapterError("D-01 changed before transport")
        if len(request_bytes) > self.policy.maximum_payload_bytes:
            raise TransportAttemptError(
                "Reader payload exceeds D-01 maximum",
                observation=_no_egress_policy_observation(
                    policy=self.policy,
                    request_bytes=request_bytes,
                ),
                provider_request_id="",
                raw_response_bytes=None,
                error_class="AIAdapterError",
            )
        transport = _build_repository_transport(policy=current_policy)
        try:
            result = transport.complete(request_bytes=request_bytes)
        except TransportAttemptError:
            raise
        except (AIAdapterError, OSError, TimeoutError, ValueError) as error:
            raise AIAdapterError(
                "Repository transport failed without auditable observation"
            ) from error
        if not isinstance(result, TransportResult):
            raise AIAdapterError(
                "Repository transport returned without transport observation"
            )
        mismatch = transport_observation_mismatch(
            policy=self.policy,
            observation=result.observation,
            request_bytes=request_bytes,
        )
        if mismatch is not None:
            raise TransportAttemptError(
                "Transport observation differs from D-01: {}".format(
                    mismatch
                ),
                observation=result.observation,
                provider_request_id=result.provider_request_id,
                raw_response_bytes=result.response_bytes,
                error_class="AIAdapterError",
            )
        if not result.response_bytes:
            raise TransportAttemptError(
                "Model returned an empty response",
                observation=result.observation,
                provider_request_id=result.provider_request_id,
                raw_response_bytes=None,
                error_class="AIAdapterError",
            )
        return result


def build_approved_transport_adapter() -> AIAdapter:
    """Build the only repository-authorized remote transport adapter.

    Returns:
        Exact private adapter compiled from effective approved D-01.
    """
    return _ApprovedTransportAdapter(authority=_ADAPTER_AUTHORITY)


def _authorized_adapter_implementation(
    *, adapter: AIAdapter
) -> Callable[..., TransportResult]:
    """Select only a factory-built repository adapter implementation.

    Args:
        adapter: Candidate adapter supplied to the workflow.

    Returns:
        Exact class-owned implementation safe to invoke for this adapter.

    Raises:
        AIAdapterError: Before invocation when type or factory authority
            differs.
    """
    if type(adapter) is _RecordedAdapter:
        implementation = _RecordedAdapter.complete
    elif type(adapter) is _ApprovedTransportAdapter:
        implementation = _ApprovedTransportAdapter.complete
    else:
        raise AIAdapterError(
            "AI attempt requires a repository-constructed adapter"
        )
    if (
        not hasattr(adapter, "_authority")
        or adapter._authority is not _ADAPTER_AUTHORITY
    ):
        raise AIAdapterError(
            "AI attempt requires a repository-constructed adapter"
        )
    return implementation


def validate_adapter_repository_authority(
    *, adapter: AIAdapter, repo_root: Path
) -> None:
    """Require approved payload bytes and D-01 to share one repository root.

    Args:
        adapter: Recorded or repository-approved adapter.
        repo_root: Repository from which the workflow will load payload bytes.

    Expected output:
        Recorded fixtures remain portable. An approved adapter is accepted
        only for the physical repository that owns its D-01 authority.

    Raises:
        AIAdapterError: Before repository payload reads when the adapter is
            unauthorized or an approved workflow names another repository.
    """
    _authorized_adapter_implementation(adapter=adapter)
    if type(adapter) is _RecordedAdapter:
        return
    if not isinstance(repo_root, Path) or repo_root.is_symlink():
        raise AIAdapterError(
            "Approved workflow repository authority is unsafe"
        )
    authority = _REPOSITORY_ROOT
    if not isinstance(authority, Path) or authority.is_symlink():
        raise AIAdapterError(
            "Approved workflow repository authority is unsafe"
        )
    try:
        workflow_root = repo_root.resolve(strict=True)
        authority_root = authority.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise AIAdapterError(
            "Approved workflow repository authority is unavailable"
        ) from error
    # The transport policy and every outbound byte must come from one
    # physical repository; accepting two caller-composable roots would make
    # an APPROVED decision govern unrelated payload content.
    if workflow_root != authority_root:
        raise AIAdapterError(
            "Approved workflow repository authority differs from D-01"
        )


def _utc_now(*, clock: Optional[Callable[[], datetime]] = None) -> str:
    """Return an explicit UTC ISO-8601 timestamp.

    Args:
        clock: Optional deterministic test clock.

    Returns:
        UTC timestamp.
    """
    current = clock() if clock is not None else datetime.now(tz=timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise AIAdapterError("Attempt clock must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat()


def _validate_prepared_request(
    *, prepared_request: PreparedReaderRequest
) -> Dict[str, object]:
    """Validate the factory-produced Reader request as one joined object.

    Args:
        prepared_request: Exact output of ``prepare_reader_request``.

    Returns:
        Isolated request bytes, task contract, manifest, and Spec identity.

    Raises:
        AIAdapterError: When any request component is missing, substituted, or
            not canonically bound to the request body.
    """
    if type(prepared_request) is not PreparedReaderRequest:
        raise AIAdapterError("Reader request must come from the factory")
    request_bytes = prepared_request.request_bytes
    task_contract_bytes = prepared_request.task_contract_bytes
    spec_hash = prepared_request.task_spec_semantic_hash
    if (
        type(request_bytes) is not bytes
        or not request_bytes
        or type(task_contract_bytes) is not bytes
        or not task_contract_bytes
    ):
        raise AIAdapterError("Prepared Reader request bytes are invalid")
    if (
        type(spec_hash) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", spec_hash) is None
    ):
        raise AIAdapterError("Prepared Reader task Spec identity is invalid")
    try:
        task_contract = strict_json_loads(
            text=task_contract_bytes.decode("utf-8")
        )
        request_body = strict_json_loads(text=request_bytes.decode("utf-8"))
    except (UnicodeDecodeError, CanonicalError, ValueError) as error:
        raise AIAdapterError("Prepared Reader request is invalid") from error
    task_fields = {
        "disclosure_group",
        "forbidden_confusions",
        "output_schema_version",
        "prompt_bundle",
        "required_claims",
        "required_roles",
    }
    if (
        not isinstance(task_contract, dict)
        or set(task_contract) != task_fields
        or not isinstance(task_contract["required_roles"], list)
        or not task_contract["required_roles"]
        or len(task_contract["required_roles"])
        != len(set(task_contract["required_roles"]))
        or any(
            type(role) is not str or not role
            for role in task_contract["required_roles"]
        )
        or type(task_contract["disclosure_group"]) is not str
        or not task_contract["disclosure_group"]
    ):
        raise AIAdapterError("Prepared Reader task contract is invalid")
    body_fields = {
        "reader_input_manifest",
        "system_contract",
        "task_contract",
        "untrusted_table_data",
    }
    if (
        not isinstance(request_body, dict)
        or set(request_body) != body_fields
        or request_body["system_contract"] != READER_SYSTEM_CONTRACT
    ):
        raise AIAdapterError("Prepared Reader request binding differs")
    try:
        manifest = validate_record(
            record=request_body["reader_input_manifest"]
        )
    except ValueError as error:
        raise AIAdapterError("Prepared Reader manifest is invalid") from error
    tables = request_body["untrusted_table_data"]
    if type(tables) is not list:
        raise AIAdapterError("Prepared Reader table payload is invalid")
    table_bindings = []
    table_fields = {
        "caption",
        "caption_raw_text",
        "column_count",
        "grid_sha256",
        "order",
        "row_count",
        "rows",
        "table_id",
    }
    for table in tables:
        if type(table) is not dict or set(table) != table_fields:
            raise AIAdapterError("Prepared Reader table payload is invalid")
        table_body = {
            key: table[key] for key in table if key != "grid_sha256"
        }
        if table["grid_sha256"] != content_hash(value=table_body):
            raise AIAdapterError("Prepared Reader table digest differs")
        table_bindings.append(
            {
                "table_id": table["table_id"],
                "grid_sha256": table["grid_sha256"],
                "order": table["order"],
            }
        )
    if (
        manifest["record_type"] != "READER_INPUT_MANIFEST"
        or manifest["reader_input_manifest_id"]
        != prepared_request.reader_input_manifest_id
        or tuple(manifest["source_reference_ids"])
        != prepared_request.source_reference_ids
        or manifest["derived_asset_id"] != prepared_request.derived_asset_id
        or manifest["tables"] != table_bindings
        or request_body["task_contract"] != task_contract
        or canonical_json_bytes(value=task_contract) != task_contract_bytes
        or canonical_json_bytes(value=request_body) != request_bytes
    ):
        raise AIAdapterError("Prepared Reader request binding differs")
    return {
        "manifest": manifest,
        "request_bytes": request_bytes,
        "task_contract": task_contract,
        "task_contract_bytes": task_contract_bytes,
        "task_spec_semantic_hash": spec_hash,
    }


def run_ai_attempt(
    *,
    adapter: AIAdapter,
    prepared_request: PreparedReaderRequest,
    clock: Optional[Callable[[], datetime]] = None,
) -> Tuple[Optional[bytes], Optional[bytes], Dict[str, object]]:
    """Run one immutable transport attempt and return its audit record.

    Args:
        adapter: Recorded or explicitly approved transport.
        prepared_request: Complete factory-produced Reader request whose task,
            manifest, request bytes, and Spec identity are jointly validated.
        clock: Optional deterministic UTC test clock.

    Returns:
        Usable response, raw response, and terminal attempt record. A schema
        failure returns ``None`` for the usable response while preserving raw
        bytes. Every retry receives a new attempt ID.
    """
    prepared = _validate_prepared_request(
        prepared_request=prepared_request,
    )
    adapter_implementation = _authorized_adapter_implementation(
        adapter=adapter,
    )
    request_bytes = prepared["request_bytes"]
    task_contract_bytes = prepared["task_contract_bytes"]
    task_contract = prepared["task_contract"]
    reader_manifest = prepared["manifest"]
    attempt_id = "attempt:" + uuid.uuid4().hex
    started = _utc_now(clock=clock)
    response: Optional[bytes] = None
    raw_response: Optional[bytes] = None
    observation: Optional[TransportObservation] = None
    provider_request_id = ""
    error_class = ""
    status = "SUCCEEDED"
    try:
        result = adapter_implementation(
            self=adapter,
            request_bytes=request_bytes
        )
        response = result.response_bytes
        raw_response = response
        provider_request_id = result.provider_request_id
        observation = result.observation
        candidate = validate_reader_output(
            response_text=response.decode("utf-8"),
            attempt_id=attempt_id,
            required_roles=task_contract["required_roles"],
            source_reference_ids=reader_manifest["source_reference_ids"],
            derived_asset_ids=[reader_manifest["derived_asset_id"]],
        )
        if candidate["disclosure_group"] != task_contract[
            "disclosure_group"
        ]:
            raise ValueError("Reader response disclosure group differs")
    except TransportAttemptError as error:
        status = "FAILED"
        error_class = error.error_class
        provider_request_id = error.provider_request_id
        raw_response = error.raw_response_bytes
        observation = error.observation
        response = None
    except (AIAdapterError, TimeoutError, OSError, ValueError) as error:
        if observation is None:
            raise AIAdapterError(
                "Attempt failed without transport observation"
            ) from error
        status = "FAILED"
        error_class = type(error).__name__
        response = None
    if observation is None:
        raise AIAdapterError("Attempt completed without transport observation")
    finished = _utc_now(clock=clock)
    request_digest = sha256_bytes(content=request_bytes)
    task_contract_digest = sha256_bytes(content=task_contract_bytes)
    response_digest = (
        sha256_bytes(content=raw_response)
        if raw_response is not None
        else ""
    )
    record = {
        "record_type": "AI_EXTRACTION_ATTEMPT",
        "attempt_id": attempt_id,
        "status": status,
        "provider": observation.provider,
        "model": observation.model,
        "endpoint_host": observation.endpoint_host,
        "transport_observation": observation.as_mapping(),
        "sampling_parameters": {"temperature": 0},
        "reader_input_manifest_hash": reader_manifest[
            "reader_input_manifest_id"
        ],
        "request_body_sha256": request_digest,
        "request_body_path": (
            "attempt_payloads/request_{}.bin".format(request_digest)
        ),
        "task_contract_sha256": task_contract_digest,
        "task_spec_semantic_hash": prepared["task_spec_semantic_hash"],
        "task_contract_path": (
            "attempt_payloads/task_contract_{}.json".format(
                task_contract_digest
            )
        ),
        "raw_response_sha256": response_digest,
        "raw_response_path": (
            "attempt_payloads/response_{}.bin".format(response_digest)
            if response_digest
            else ""
        ),
        "provider_request_id": provider_request_id,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "error_class": error_class,
    }
    return response, raw_response, validate_record(record=record)
