"""Compose the metric-neutral table-review shadow workflow.

This module wires SourceReference, complete table-grid input, an approved or
recorded AI attempt, strict Candidate, mechanical Evidence, safe review
context, and ReviewUnit into one OPEN Run. It never publishes, calls SEC, or
creates a HUMAN decision; those remain explicit later transitions.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Sequence

from .ai_adapter import AIAdapter, AIAdapterError, AttemptPayloads
from .ai_adapter import TransportObservation
from .ai_adapter import run_ai_attempt
from .ai_adapter import build_invocation_acceptance_context
from .ai_adapter import validate_workflow_acceptance_binding
from .ai_adapter import validate_adapter_repository_authority
from .batch_workflow import BatchWorkflowError
from .batch_workflow import validate_request_attempt_binding
from .calculator import calculate_metric, calculate_observation_metric
from .calculator import withheld_metric_result
from .canonical import atomic_write_json, content_hash, sha256_file
from .canonical import strict_json_file, strict_json_loads
from .evidence import check_evidence
from .reader import validate_reader_output
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .reader_input import prepare_live_reader_request
from .reader_input import required_reader_roles
from .render import build_review_context, render_review_markdown
from .review import build_review_unit, create_system_review_decision
from .review import effective_review_decision
from .observations import reviewed_observation, scope_key
from .qualification import QualificationError
from .qualification import record_table_qualification_execution
from .qualification import validate_live_table_qualification_authorization
from .qualification import validate_table_qualification_run_bindings
from .requirements import load_run_requirement_snapshot
from .scope_contract import scope_satisfies_contract
from .run_store import append_review_decision, append_run_record
from .run_store import append_run_records_atomically
from .run_store import create_run, load_open_run
from .run_store import load_run_bound_specs
from .run_store import load_run_bound_task_specs
from .run_store import RunStoreError
from .run_store import write_review_assets
from .run_store import write_attempt_payloads
from .sources import load_raw_blob_bytes, raw_blob_record
from .sources import SourceError, source_reference_record
from .sources import validate_public_sec_filing_identity
from .specs import SpecError, compile_spec_file, compile_spec_files
from .specs import parse_spec_document
from .table_grid import build_table_grid
from .table_task_contracts import TABLE_TASK_CATALOG_PATH
from .table_task_contracts import load_table_task_contracts
from .table_task_contracts import table_task_execution_plan
from .table_task_contracts import TableTaskContractError
from .table_qualification_freeze import require_table_qualification_freeze
from .table_qualification_freeze import TableQualificationFreezeError
from .traits import TraitError, repository_company_ciks
from .traits import repository_company_traits
from .records import validate_record


class WorkflowError(RuntimeError):
    """Report incomplete compiled semantics or inconsistent Reader output."""


class LiveSourceAuthorityError(WorkflowError):
    """Report a live source not proven by immutable public SEC authority."""


# This hook is deliberately module-private and is only patched by the focused
# crash-recovery tests.  Production callers cannot select a recovery phase or
# turn a normal qualification Run into a partial one.
_TABLE_QUALIFICATION_RECOVERY_HOOK: Optional[Callable[[str], None]] = None
_TABLE_QUALIFICATION_RECOVERY_FILE = "qualification_recovery.json"
_TABLE_QUALIFICATION_RECOVERY_FIELDS = {
    "attempt",
    "checkpoint_id",
    "payloads",
    "qualification_authorization",
    "record_type",
    "run_id",
    "schema_version",
}


def _recovery_checkpoint_path(*, run_dir: Path) -> Path:
    """Return the transient, run-owned recovery checkpoint path."""
    return run_dir / _TABLE_QUALIFICATION_RECOVERY_FILE


def _recovery_payload_mapping(*, payloads: AttemptPayloads) -> Dict[str, object]:
    """Encode exact attempt bytes without relying on host-local paths."""
    def encode(value: Optional[bytes]) -> Optional[str]:
        return (
            base64.b64encode(value).decode("ascii")
            if value is not None
            else None
        )

    return {
        "request_body_b64": encode(payloads.request_body_bytes),
        "reader_payload_b64": encode(payloads.reader_payload_bytes),
        "task_contract_b64": encode(payloads.task_contract_bytes),
        "output_schema_b64": encode(payloads.output_schema_bytes),
        "assistant_output_b64": encode(payloads.assistant_output_bytes),
        "raw_response_b64": encode(payloads.raw_response_bytes),
        "acceptance_receipt": (
            dict(payloads.acceptance_receipt)
            if payloads.acceptance_receipt is not None
            else None
        ),
    }


def _payloads_from_recovery_mapping(*, value: object) -> AttemptPayloads:
    """Decode and validate one exact transient recovery payload bundle."""
    fields = {
        "request_body_b64",
        "reader_payload_b64",
        "task_contract_b64",
        "output_schema_b64",
        "assistant_output_b64",
        "raw_response_b64",
        "acceptance_receipt",
    }
    if type(value) is not dict or set(value) != fields:
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")

    def decode(name: str, *, required: bool) -> Optional[bytes]:
        encoded = value[name]
        if encoded is None:
            if required:
                raise WorkflowError(
                    "TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID"
                )
            return None
        if type(encoded) is not str:
            raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
        try:
            return base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as error:
            raise WorkflowError(
                "TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID"
            ) from error

    acceptance = value["acceptance_receipt"]
    if acceptance is not None and type(acceptance) is not dict:
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
    try:
        return AttemptPayloads(
            request_body_bytes=decode("request_body_b64", required=True),
            reader_payload_bytes=decode("reader_payload_b64", required=True),
            task_contract_bytes=decode("task_contract_b64", required=True),
            output_schema_bytes=decode("output_schema_b64", required=True),
            assistant_output_bytes=decode(
                "assistant_output_b64", required=False,
            ),
            raw_response_bytes=decode("raw_response_b64", required=False),
            acceptance_receipt=(
                dict(acceptance) if acceptance is not None else None
            ),
        )
    except (TypeError, ValueError) as error:
        raise WorkflowError(
            "TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID"
        ) from error


def _write_table_qualification_recovery_checkpoint(
    *, run_dir: Path, run_id: str, qualification_authorization: Mapping[str, object],
    attempt: Mapping[str, object], payloads: AttemptPayloads,
) -> None:
    """Durably retain one exact-success materialization bundle.

    The checkpoint is written after WB-3 has accepted the exact response and
    before any Run-owned payload bytes are written.  It is intentionally
    transient: a complete OPEN Run removes it before review, so a FROZEN Run
    still has the regular exact artifact set only.
    """
    validated_attempt = validate_record(record=dict(attempt))
    if validated_attempt["record_type"] != "AI_EXTRACTION_ATTEMPT":
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
    body = {
        "schema_version": 1,
        "record_type": "TABLE_QUALIFICATION_RECOVERY_CHECKPOINT",
        "run_id": run_id,
        "qualification_authorization": dict(qualification_authorization),
        "attempt": validated_attempt,
        "payloads": _recovery_payload_mapping(payloads=payloads),
    }
    value = {**body, "checkpoint_id": content_hash(value=body)}
    path = _recovery_checkpoint_path(run_dir=run_dir)
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
        current = strict_json_file(path=path)
        if current != value:
            raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
        return
    atomic_write_json(path=path, value=value)


def _load_table_qualification_recovery_checkpoint(
    *, run_dir: Path, run_id: str,
    qualification_authorization: Mapping[str, object],
) -> Optional[tuple[Dict[str, object], AttemptPayloads]]:
    """Reload one authenticated transient exact-success bundle, if present."""
    path = _recovery_checkpoint_path(run_dir=run_dir)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
    value = strict_json_file(path=path)
    if type(value) is not dict or set(value) != _TABLE_QUALIFICATION_RECOVERY_FIELDS:
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
    body = {key: value[key] for key in value if key != "checkpoint_id"}
    if value["checkpoint_id"] != content_hash(value=body):
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
    if (
        value["schema_version"] != 1
        or value["record_type"] != "TABLE_QUALIFICATION_RECOVERY_CHECKPOINT"
        or value["run_id"] != run_id
        or value["qualification_authorization"]
        != qualification_authorization
    ):
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
    try:
        attempt = validate_record(record=value["attempt"])
    except ValueError as error:
        raise WorkflowError(
            "TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID"
        ) from error
    if attempt["record_type"] != "AI_EXTRACTION_ATTEMPT":
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
    return dict(attempt), _payloads_from_recovery_mapping(
        value=value["payloads"],
    )


def _remove_table_qualification_recovery_checkpoint(*, run_dir: Path) -> None:
    """Remove only a validated transient checkpoint after full materialization."""
    path = _recovery_checkpoint_path(run_dir=run_dir)
    if not path.exists():
        return
    if path.is_symlink() or not path.is_file():
        raise WorkflowError("TABLE_QUALIFICATION_RECOVERY_CHECKPOINT_INVALID")
    path.unlink()


def _checkpoint_recovery_phase(*, phase: str) -> None:
    """Invoke a test-only crash injection after a durable stage boundary."""
    hook = _TABLE_QUALIFICATION_RECOVERY_HOOK
    if hook is not None:
        hook(phase)


def _ensure_open_run_record(
    *, run_dir: Path, existing_records: list[Dict[str, object]],
    record: Mapping[str, object],
) -> None:
    """Append an expected recovery record once, or reject any divergence."""
    expected = validate_record(record=dict(record))
    same_type = [
        value for value in existing_records
        if value["record_type"] == expected["record_type"]
    ]
    if not same_type:
        append_run_record(run_dir=run_dir, record=expected)
        existing_records.append(expected)
        return
    if len(same_type) != 1 or same_type[0] != expected:
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")


def _restore_reused_remote_attempt(
    *, attempt: Mapping[str, object], adapter: AIAdapter,
) -> Dict[str, object]:
    """Restore the historical egress fact when WB-3 returns an exact reuse.

    A controlled adapter intentionally exposes reusable success as a fresh
    no-egress observation.  For a previously interrupted qualification
    terminal, the durable WB-3 response proves one earlier remote egress; the
    Run record must preserve that fact so the qualification ledger/evidence
    closure remains one-to-one rather than silently turning it into recorded
    evidence.
    """
    observation = attempt.get("transport_observation")
    if type(observation) is not dict:
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
    try:
        current = TransportObservation.from_mapping(value=observation)
    except AIAdapterError as error:
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT") from error
    if current.egress_attempted:
        return dict(attempt)
    policy = getattr(adapter, "policy", None)
    if policy is None:
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
    restored = TransportObservation(
        egress_attempted=True,
        provider=policy.provider,
        model=policy.model,
        model_requested=policy.model,
        model_returned=policy.model,
        api=policy.api,
        store=False,
        endpoint_host=policy.endpoint_host,
        region=policy.region,
        retention=policy.retention,
        data_use=policy.data_use,
        timeout_seconds=policy.timeout_seconds,
        retry_count=policy.retry_count,
        retries_performed=0,
        maximum_payload_bytes=policy.maximum_payload_bytes,
        filing_egress_policy=policy.filing_egress_policy,
        request_body_bytes=current.request_body_bytes,
    )
    value = {
        **attempt,
        "provider": restored.provider,
        "model": restored.model,
        "model_requested": restored.model_requested,
        "model_returned": restored.model_returned,
        "api": restored.api,
        "endpoint_host": restored.endpoint_host,
        "transport_observation": restored.as_mapping(),
    }
    try:
        return dict(validate_record(record=value))
    except ValueError as error:
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT") from error


def _validate_live_source_authority(
    *,
    repo_root: Path,
    company_id: str,
    raw_blob: Mapping[str, object],
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    request_attempt_id: str,
) -> Dict[str, object]:
    """Rebuild the registry, filing, ledger, body, and header proof pre-egress.

    Args:
        repo_root: Fixed repository containing registry and SEC audit authority.
        company_id: Registry logical company identity.
        raw_blob: Exact candidate filing bytes and media type.
        source_url: Claimed official SEC primary-document URL.
        accession: Claimed filing accession.
        document_name: Claimed filing document identity.
        source_role: Claimed Run source role.
        request_attempt_id: Pinned immutable request-ledger row identity.

    Returns:
        Exact immutable body/header locator proof for transport replay.

    Raises:
        LiveSourceAuthorityError: Before any AI attempt when the complete public
        SEC source proof cannot be rebuilt from current repository bytes.
    """
    try:
        validate_public_sec_filing_identity(
            raw_blob=raw_blob,
            source_url=source_url,
            accession=accession,
            document_name=document_name,
            source_role=source_role,
            allowed_ciks=repository_company_ciks(
                repo_root=repo_root, company_id=company_id,
            ),
        )
        binding = validate_request_attempt_binding(
            repo_root=repo_root,
            source_url=source_url,
            content_sha256=str(raw_blob["raw_asset_id"]).split(
                ":", maxsplit=1
            )[1],
            accession=accession,
            document_name=document_name,
            request_attempt_id=request_attempt_id,
            require_immutable=True,
        )
    except (BatchWorkflowError, SourceError, TraitError) as error:
        raise LiveSourceAuthorityError(
            "Live Reader source lacks immutable public SEC authority"
        ) from error
    if binding["request_attempt_id"] != request_attempt_id:
        raise LiveSourceAuthorityError(
            "Live Reader request attempt identity differs"
        )
    return binding


def create_review_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    company_id: str,
    target_period: Mapping[str, object],
    source_repo_relative_path: str,
    source_media_type: str,
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    request_attempt_id: str,
    disclosure_spec_path: str,
    adapter: AIAdapter,
    clock: Optional[Callable[[], datetime]],
    task_contract_id: Optional[str] = None,
    qualification_authorization: Optional[object] = None,
) -> Dict[str, object]:
    """Create one registry-authorized OPEN Run through HUMAN review.

    Args:
        repo_root: Repository containing exact raw bytes and Specs.
        run_dir: New run-scoped directory.
        run_id: Opaque Run identity.
        company_id: Logical company identity from the production registry.
        target_period: Explicit target-period mapping.
        source_repo_relative_path: Existing raw filing path.
        source_media_type: Raw filing media type.
        source_url: Official SEC source URL.
        accession: Filing accession.
        document_name: Filing document name.
        source_role: Run source role.
        request_attempt_id: Existing SEC ledger attempt identity.
        disclosure_spec_path: Repository-relative disclosure Spec locator.
        adapter: Recorded or repository-approved AI transport.
        clock: Explicit UTC clock or ``None`` for real UTC audit time.
        task_contract_id: Explicit catalog single-table task, or ``None`` for
            the retained historical disclosure workflow.
        qualification_authorization: Opaque current qualification authority
            required only for a LIVE catalog task.

    Returns:
        Run, attempt, Candidate, Evidence, and ReviewUnit identities.
    """
    try:
        company_traits = repository_company_traits(
            repo_root=repo_root, company_id=company_id,
        )
    except TraitError as error:
        raise WorkflowError(
            "Repository company traits are invalid"
        ) from error
    return _create_review_run_with_traits(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=run_id,
        company_id=company_id,
        company_traits=company_traits,
        target_period=target_period,
        source_repo_relative_path=source_repo_relative_path,
        source_media_type=source_media_type,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id=request_attempt_id,
        disclosure_spec_path=disclosure_spec_path,
        adapter=adapter,
        clock=clock,
        task_contract_id=task_contract_id,
        qualification_authorization=qualification_authorization,
    )


def create_table_task_review_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    company_id: str,
    target_period: Mapping[str, object],
    source_repo_relative_path: str,
    source_media_type: str,
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    request_attempt_id: str,
    task_contract_id: str,
    adapter: AIAdapter,
    clock: Optional[Callable[[], datetime]],
    qualification_authorization: Optional[object] = None,
    resume_existing: bool = False,
) -> Dict[str, object]:
    """Create one formal single-table catalog task Run.

    Args:
        repo_root: Repository containing task, MetricSpec, and source bytes.
        run_dir: New Run-scoped directory.
        run_id: Opaque Run identity.
        company_id: Registry logical company identity.
        target_period: Explicit Run period mapping.
        source_repo_relative_path: Existing immutable or recorded source path.
        source_media_type: Exact source media type.
        source_url: Exact source URL.
        accession: Exact filing accession.
        document_name: Exact source document identity.
        source_role: Source role for the Run.
        request_attempt_id: Existing immutable SEC ledger attempt identity.
        task_contract_id: Explicit matrix-authorized catalog single-table task.
        adapter: Recorded or repository-approved AI transport.
        clock: Explicit UTC clock or ``None`` for real UTC audit time.
        qualification_authorization: Opaque authority required for LIVE use.
        resume_existing: Internal executor-only opt-in to materialize an
            interrupted deterministic LIVE qualification Run in place.

    Returns:
        Run, attempt, Candidate, Evidence, and ReviewUnit identities.

    Why:
        This is the production Workflow entrypoint for WB-6 tasks.  It never
        derives a task from a metric, company, table ID, or response role; the
        caller must name a catalog contract that is recorded in the Run.
    """
    try:
        company_traits = repository_company_traits(
            repo_root=repo_root,
            company_id=company_id,
        )
    except TraitError as error:
        raise WorkflowError(
            "Repository company traits are invalid"
        ) from error
    return _create_review_run_with_traits(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=run_id,
        company_id=company_id,
        company_traits=company_traits,
        target_period=target_period,
        source_repo_relative_path=source_repo_relative_path,
        source_media_type=source_media_type,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id=request_attempt_id,
        disclosure_spec_path=TABLE_TASK_CATALOG_PATH.as_posix(),
        adapter=adapter,
        clock=clock,
        task_contract_id=task_contract_id,
        qualification_authorization=qualification_authorization,
        resume_existing=resume_existing,
    )


def create_layout_qualification_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    fixture_id: str,
    adapter: AIAdapter,
    clock: Optional[Callable[[], datetime]],
) -> Dict[str, object]:
    """Run a repository fixture company through the production review path.

    Args:
        repo_root: Repository containing the fixed fixture authority.
        run_dir: New qualification Run directory.
        run_id: Opaque Run identity.
        fixture_id: Safe directory identity below ``fixtures/vnext/layouts``.
        adapter: Repository-created recorded adapter; live transport is barred.
        clock: Explicit UTC clock or ``None`` for real UTC audit time.

    Returns:
        The same Run/Candidate/Evidence/ReviewUnit result as production.
    """
    try:
        task_contracts = load_table_task_contracts(repo_root=repo_root)
        for family_id in task_contracts["authorized_family_ids"]:
            require_table_qualification_freeze(
                repo_root=repo_root,
                family_id=family_id,
            )
    except (TableQualificationFreezeError, TableTaskContractError) as error:
        raise WorkflowError(
            "Table qualification requires a valid catalog task plan"
        ) from error
    # A historical fixture only names a disclosure group, so it cannot choose
    # a catalog single-table task without reintroducing the v1 multi-role path.
    raise WorkflowError(
        "Table qualification requires explicit catalog task identity"
    )


def _create_legacy_layout_qualification_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    fixture_id: str,
    adapter: AIAdapter,
    clock: Optional[Callable[[], datetime]],
) -> Dict[str, object]:
    """Retain the historical fixture parser behind the catalog-task barrier.

    Args:
        repo_root: Repository containing the fixed fixture authority.
        run_dir: New qualification Run directory.
        run_id: Opaque Run identity.
        fixture_id: Safe directory identity below ``fixtures/vnext/layouts``.
        adapter: Repository-created recorded adapter; live transport is barred.
        clock: Explicit UTC clock or ``None`` for real UTC audit time.

    Returns:
        The historical fixture Run result for non-table legacy migrations.

    Why:
        Keeping parsing code separate makes the public table-qualification
        entrypoint fail closed instead of quietly using its schema-v1 request.
    """
    if (
        not fixture_id
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
               for character in fixture_id)
        or adapter.provider != "recorded"
    ):
        raise WorkflowError(
            "Layout qualification requires a safe fixture and "
            "socket-zero adapter"
        )
    relative_root = Path("fixtures/vnext/layouts") / fixture_id
    manifest_path = repo_root / relative_root / "fixture_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise WorkflowError("Layout fixture manifest is absent or unsafe")
    manifest = strict_json_file(path=manifest_path)
    required = {
        "accession",
        "cik",
        "company_id",
        "company_traits",
        "disclosure_spec_path",
        "document_name",
        "excerpt_repo_relative_path",
        "excerpt_sha256",
        "fixture_id",
        "layout_differences",
        "qualification_role",
        "recorded_response_repo_relative_path",
        "recorded_response_sha256",
        "request_attempt_id",
        "schema_version",
        "selection_reason",
        "source_media_type",
        "source_repo_relative_path",
        "source_role",
        "source_sha256",
        "source_url",
        "target_period",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or manifest["schema_version"] != 1
        or manifest["fixture_id"] != fixture_id
        or type(manifest["selection_reason"]) is not str
        or not manifest["selection_reason"].strip()
        or not isinstance(manifest["company_traits"], list)
        or not manifest["company_traits"]
        or len(manifest["company_traits"])
        != len(set(manifest["company_traits"]))
        or any(
            type(trait) is not str or not trait
            for trait in manifest["company_traits"]
        )
    ):
        raise WorkflowError("Layout fixture manifest fields are not exact")
    source_path = repo_root / Path(str(manifest["source_repo_relative_path"]))
    response_path = repo_root / Path(
        str(manifest["recorded_response_repo_relative_path"])
    )
    excerpt_path = repo_root / Path(
        str(manifest["excerpt_repo_relative_path"])
    )
    fixture_root = repo_root / relative_root
    if (
        Path(str(manifest["source_repo_relative_path"])).is_absolute()
        or ".." in Path(str(manifest["source_repo_relative_path"])).parts
        or fixture_root not in source_path.parents
        or source_path.is_symlink()
        or not source_path.is_file()
        or sha256_file(path=source_path) != manifest["source_sha256"]
        or Path(
            str(manifest["recorded_response_repo_relative_path"])
        ).is_absolute()
        or ".." in Path(
            str(manifest["recorded_response_repo_relative_path"])
        ).parts
        or fixture_root not in response_path.parents
        or response_path.is_symlink()
        or not response_path.is_file()
        or sha256_file(path=response_path)
        != manifest["recorded_response_sha256"]
        or Path(str(manifest["excerpt_repo_relative_path"])).is_absolute()
        or ".." in Path(str(manifest["excerpt_repo_relative_path"])).parts
        or fixture_root not in excerpt_path.parents
        or excerpt_path.is_symlink()
        or not excerpt_path.is_file()
        or sha256_file(path=excerpt_path) != manifest["excerpt_sha256"]
    ):
        raise WorkflowError("Layout fixture byte binding differs")
    return _create_review_run_with_traits(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=run_id,
        company_id=str(manifest["company_id"]),
        company_traits=list(manifest["company_traits"]),
        target_period=manifest["target_period"],
        source_repo_relative_path=str(manifest["source_repo_relative_path"]),
        source_media_type=str(manifest["source_media_type"]),
        source_url=str(manifest["source_url"]),
        accession=str(manifest["accession"]),
        document_name=str(manifest["document_name"]),
        source_role=str(manifest["source_role"]),
        request_attempt_id=str(manifest["request_attempt_id"]),
        disclosure_spec_path=str(manifest["disclosure_spec_path"]),
        adapter=adapter,
        clock=clock,
        task_contract_id=None,
    )


def _required_roles(*, compiled_spec: Mapping[str, object]) -> Sequence[str]:
    """Read ordered disclosure roles from compiled projection semantics.

    Args:
        compiled_spec: Compiled disclosure-group Spec.

    Returns:
        Ordered selected plus supporting roles.

    Raises:
        WorkflowError: On absent, empty, or duplicated role declaration.
    """
    try:
        return required_reader_roles(compiled_spec=compiled_spec)
    except ValueError as error:
        raise WorkflowError("Disclosure role contract is invalid") from error


def _load_disclosure_plan(
    *, repo_root: Path, disclosure_spec_path: str,
) -> tuple[
    Dict[str, object], Sequence[str], Dict[str, Dict[str, object]]
]:
    """Load one disclosure Spec and derive its exact metric Spec paths.

    Args:
        repo_root: Repository containing the authoritative catalog.
        disclosure_spec_path: Repository-relative disclosure Spec locator.

    Returns:
        Compiled disclosure wrapper, ordered closure paths, and authoritative
        metric wrappers keyed by metric ID.

    Raises:
        WorkflowError: When the locator escapes the disclosure catalog or its
            role metrics cannot be resolved exactly from repository files.
    """
    relative = Path(disclosure_spec_path)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[:2] != ("catalog", "disclosures")
    ):
        raise WorkflowError("Disclosure Spec locator is invalid")
    try:
        compiled_spec = compile_spec_file(
            path=repo_root / relative,
            dependency_specs={},
        )
    except SpecError as error:
        raise WorkflowError("Disclosure Spec cannot be compiled") from error
    semantic = compiled_spec["compiled"]
    if semantic["kind"] != "disclosure_group":
        raise WorkflowError("Workflow requires a disclosure-group Spec")
    required_metric_ids = set(
        semantic["legacy_projection"]["role_metric_ids"].values()
    )
    metric_paths = {}
    for candidate in sorted((repo_root / "catalog" / "metrics").glob("*.md")):
        if candidate.is_symlink() or not candidate.is_file():
            raise WorkflowError("Metric Spec catalog entry is unsafe")
        try:
            front, _body = parse_spec_document(
                text=candidate.read_text(encoding="utf-8")
            )
        except (UnicodeDecodeError, SpecError) as error:
            raise WorkflowError("Metric Spec catalog is invalid") from error
        metric_id = front["metric_id"]
        if type(metric_id) is not str or not metric_id:
            raise WorkflowError("Metric Spec identity is invalid")
        if metric_id in required_metric_ids:
            if metric_id in metric_paths:
                raise WorkflowError("Disclosure metric Spec is duplicated")
            metric_paths[metric_id] = candidate
    if set(metric_paths) != required_metric_ids:
        raise WorkflowError("Disclosure metric Spec exact set differs")
    paths = [repo_root / relative]
    paths.extend(metric_paths[metric_id] for metric_id in sorted(metric_paths))
    try:
        metric_specs = compile_spec_files(
            paths=[metric_paths[metric_id] for metric_id in metric_paths],
        )
    except SpecError as error:
        raise WorkflowError(
            "Disclosure metric Spec closure cannot be compiled"
        ) from error
    if set(metric_specs) != required_metric_ids:
        raise WorkflowError("Disclosure metric Spec exact set differs")
    return (
        compiled_spec,
        [path.relative_to(repo_root).as_posix() for path in paths],
        metric_specs,
    )


def _create_review_run_with_traits(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    company_id: str,
    company_traits: Sequence[str],
    target_period: Mapping[str, object],
    source_repo_relative_path: str,
    source_media_type: str,
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    request_attempt_id: str,
    disclosure_spec_path: str,
    adapter: AIAdapter,
    clock: Optional[Callable[[], datetime]],
    task_contract_id: Optional[str],
    qualification_authorization: Optional[object] = None,
    resume_existing: bool = False,
) -> Dict[str, object]:
    """Create one OPEN Run from already repository-resolved company traits.

    Args:
        repo_root: Repository containing exact raw bytes and Specs.
        run_dir: New run-scoped directory.
        run_id: Opaque Run identity.
        company_id: Logical company identity.
        company_traits: Registry- or fixture-manifest-derived traits.
        target_period: Explicit target-period mapping.
        source_repo_relative_path: Existing raw filing path.
        source_media_type: Raw filing media type.
        source_url: Official SEC source URL.
        accession: Filing accession.
        document_name: Filing document name.
        source_role: Run source role.
        request_attempt_id: Existing SEC ledger attempt identity.
        disclosure_spec_path: Repository-relative disclosure Spec locator.
        adapter: Recorded or repository-approved AI transport.
        clock: Explicit UTC clock or ``None`` for real UTC audit time.
        task_contract_id: Explicit catalog task identity, or ``None`` only for
            the retained historical disclosure-group path.
        qualification_authorization: Opaque current repository authorization
            required before a LIVE catalog task can read source bytes.
        resume_existing: Internal deterministic-terminal recovery mode.  It
            is accepted only for a LIVE catalog task carrying the same
            module-revalidated qualification authorization.

    Returns:
        Run, attempt, Candidate, Evidence, and ReviewUnit identities. Rejection
        returns without creating a ReviewUnit and never invokes a fallback.
    """
    # Close the only joint remote boundary before loading Spec or filing
    # bytes, so D-01 cannot authorize a payload assembled from another tree.
    adapter_mode = validate_adapter_repository_authority(
        adapter=adapter, repo_root=repo_root,
    )
    if type(resume_existing) is not bool:
        raise WorkflowError("Qualification recovery mode is invalid")
    task_run_bindings = []
    qualification_binding = None
    if task_contract_id is None:
        compiled_spec, spec_paths, metric_specs = _load_disclosure_plan(
            repo_root=repo_root,
            disclosure_spec_path=disclosure_spec_path,
        )
    else:
        if disclosure_spec_path != TABLE_TASK_CATALOG_PATH.as_posix():
            raise WorkflowError("Catalog task path differs from authority")
        try:
            task_plan = table_task_execution_plan(
                repo_root=repo_root,
                task_contract_id=task_contract_id,
            )
        except TableTaskContractError as error:
            raise WorkflowError("Catalog task execution plan is invalid") from error
        compiled_spec = task_plan["task_spec"]
        metric_specs = task_plan["metric_specs"]
        spec_paths = list(
            task_plan["runtime_task_contract"]["metric_spec_paths"]
        )
        task_run_bindings = [task_plan["run_binding"]]
        if adapter_mode == "LIVE":
            try:
                qualification_binding = (
                    validate_live_table_qualification_authorization(
                        repo_root=repo_root,
                        authorization=qualification_authorization,
                        task_contract_id=task_contract_id,
                        run_dir=run_dir,
                        run_id=run_id,
                        company_id=company_id,
                        target_period=target_period,
                        source_repo_relative_path=source_repo_relative_path,
                        source_media_type=source_media_type,
                        source_url=source_url,
                        accession=accession,
                        document_name=document_name,
                        source_role=source_role,
                        request_attempt_id=request_attempt_id,
                        adapter=adapter,
                    )
                )
            except QualificationError as error:
                raise WorkflowError(error.code) from error
    if resume_existing and (
        task_contract_id is None
        or adapter_mode != "LIVE"
        or qualification_binding is None
    ):
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
    if (
        not isinstance(company_traits, list)
        or not company_traits
        or any(type(trait) is not str or not trait for trait in company_traits)
        or len(company_traits) != len(set(company_traits))
    ):
        raise WorkflowError("Resolved company traits are invalid")
    semantic = compiled_spec["compiled"]
    required_traits = set(semantic["applicability"]["all"])
    forbidden_traits = set(semantic["applicability"]["none"])
    supplied_traits = set(company_traits)
    spec_file_hashes = {
        relative: sha256_file(path=repo_root / relative)
        for relative in spec_paths
    }
    requirement = load_run_requirement_snapshot(
        repo_root=repo_root,
        task_contract_bindings=task_run_bindings,
    )
    if not required_traits.issubset(supplied_traits) or (
        forbidden_traits & supplied_traits
    ):
        # Structural inapplicability is a durable business fact. Persist the
        # Run and Calculator output while deliberately omitting source and AI
        # records so freeze/replay can prove both the result and zero egress.
        records = []
        result_ids = []
        trace_ids = []
        for metric_id in sorted(metric_specs):
            metric_spec = metric_specs[metric_id]
            target_scope = dict(metric_spec["compiled"]["required_claims"])
            target = {
                "company_id": company_id,
                "period_start": target_period["period_start"],
                "period_end": target_period["period_end"],
                "accession": None,
                "entity": None,
                "scope": target_scope,
                "scope_key": scope_key(scope=target_scope),
            }
            result, trace, observations = calculate_metric(
                compiled_spec=metric_spec,
                target=target,
                company_traits=company_traits,
                structured_facts=[],
                verified_observations=[],
            )
            if observations or result["applicability"] != "N_A_STRUCTURAL":
                raise WorkflowError(
                    "Inapplicable disclosure metric did not produce N/A"
                )
            records.extend((trace, result))
            result_ids.append(result["result_id"])
            trace_ids.append(trace["trace_id"])
        create_run(
            run_dir=run_dir,
            run_id=run_id,
            company_id=company_id,
            company_traits=company_traits,
            target_period=target_period,
            source_references=[],
            missing_required_source_roles=[],
            spec_file_hashes=spec_file_hashes,
            requirement_hashes=requirement["hashes"],
            task_contract_bindings=task_run_bindings,
            qualification_authorization=qualification_binding,
        )
        for record in records:
            append_run_record(run_dir=run_dir, record=record)
        return {
            "run_id": run_id,
            "status": "N_A_STRUCTURAL",
            "attempt_count": 0,
            "result_ids": result_ids,
            "trace_ids": trace_ids,
        }
    roles = _required_roles(compiled_spec=compiled_spec)
    raw_blob = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=source_repo_relative_path,
        media_type=source_media_type,
    )
    live_source_binding = None
    if adapter_mode == "LIVE":
        live_source_binding = _validate_live_source_authority(
            repo_root=repo_root,
            company_id=company_id,
            raw_blob=raw_blob,
            source_url=source_url,
            accession=accession,
            document_name=document_name,
            source_role=source_role,
            request_attempt_id=request_attempt_id,
        )
    source_reference = source_reference_record(
        raw_blob=raw_blob,
        company_id=company_id,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id=request_attempt_id,
    )
    existing_records: list[Dict[str, object]] = []
    if run_dir.exists():
        if not resume_existing:
            raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
        try:
            existing_manifest, existing_records, _decisions = load_open_run(
                run_dir=run_dir,
            )
        except RunStoreError as error:
            raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT") from error
        expected_manifest = {
            "run_id": run_id,
            "company_id": company_id,
            "company_traits": list(company_traits),
            "target_period": dict(target_period),
            "source_references": [source_reference],
            "missing_required_source_roles": [],
            "spec_file_hashes": spec_file_hashes,
            "requirement_hashes": requirement["hashes"],
            "task_contract_bindings": task_run_bindings,
            "qualification_authorization": qualification_binding,
        }
        if any(
            existing_manifest.get(field) != expected
            for field, expected in expected_manifest.items()
        ):
            raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
    else:
        create_run(
            run_dir=run_dir,
            run_id=run_id,
            company_id=company_id,
            company_traits=company_traits,
            target_period=target_period,
            source_references=[source_reference],
            missing_required_source_roles=[],
            spec_file_hashes=spec_file_hashes,
            requirement_hashes=requirement["hashes"],
            task_contract_bindings=task_run_bindings,
            qualification_authorization=qualification_binding,
        )
    _ensure_open_run_record(
        run_dir=run_dir, existing_records=existing_records, record=raw_blob,
    )
    _ensure_open_run_record(
        run_dir=run_dir,
        existing_records=existing_records,
        record=source_reference,
    )
    # Re-read through the RawBlob verifier so review input cannot race away
    # from the exact source identity created above.
    raw_bytes = load_raw_blob_bytes(repo_root=repo_root, raw_blob=raw_blob)
    derived_asset = build_table_grid(
        html_bytes=raw_bytes,
        parent_raw_asset_ids=[str(raw_blob["raw_asset_id"])],
        storage_uri=(
            "artifacts/vnext/derived/{}.json".format(
                str(raw_blob["raw_asset_id"]).split(":", maxsplit=1)[1]
            )
        ),
    )
    _ensure_open_run_record(
        run_dir=run_dir,
        existing_records=existing_records,
        record=derived_asset,
    )
    reader_manifest = build_reader_input_manifest(
        derived_asset=derived_asset,
        source_reference_ids=[str(source_reference["source_reference_id"])],
    )
    _ensure_open_run_record(
        run_dir=run_dir,
        existing_records=existing_records,
        record=reader_manifest,
    )
    prepared_request = prepare_reader_request(
        manifest=reader_manifest,
        derived_asset=derived_asset,
        compiled_spec=compiled_spec if task_contract_id is None else None,
        repo_root=repo_root if task_contract_id is not None else None,
        task_contract_id=task_contract_id,
    )
    attempt_request = (
        prepare_live_reader_request(
            prepared_request=prepared_request,
            raw_blob=raw_blob,
            source_reference=source_reference,
            derived_asset=derived_asset,
            reader_manifest=reader_manifest,
            disclosure_spec_path=disclosure_spec_path,
            immutable_source_repo_relative_path=str(
                live_source_binding["request_repo_relative_path"]
            ),
        )
        if adapter_mode == "LIVE"
        else prepared_request
    )
    reader_payload_body = strict_json_loads(
        text=prepared_request.request_bytes.decode("utf-8")
    )
    acceptance_context = build_invocation_acceptance_context(
        compiled_spec=compiled_spec,
        derived_asset=derived_asset,
        reader_manifest=reader_manifest,
        reader_payload_body=reader_payload_body,
        source_references=[source_reference],
    )

    _checkpoint_recovery_phase(phase="AFTER_CREATE_RUN")
    existing_attempts = [
        record for record in existing_records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    if len(existing_attempts) > 1:
        raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
    reused_wb3_success = False
    checkpoint = (
        _load_table_qualification_recovery_checkpoint(
            run_dir=run_dir,
            run_id=run_id,
            qualification_authorization=qualification_binding,
        )
        if qualification_binding is not None
        else None
    )
    if checkpoint is not None:
        checkpoint_attempt, attempt_payloads = checkpoint
        if existing_attempts and existing_attempts[0] != checkpoint_attempt:
            raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
        attempt = checkpoint_attempt
        response = attempt_payloads.assistant_output_bytes
    else:
        response, _raw_response, attempt, attempt_payloads = run_ai_attempt(
            adapter=adapter,
            prepared_request=attempt_request,
            acceptance_context=acceptance_context,
            clock=clock,
        )
        if qualification_binding is not None:
            attempt = {
                **attempt,
                "qualification_authorization": qualification_binding,
            }
            if response is not None:
                reused_wb3_success = (
                    type(attempt.get("transport_observation")) is dict
                    and attempt["transport_observation"].get(
                        "egress_attempted"
                    ) is False
                )
                attempt = _restore_reused_remote_attempt(
                    attempt=attempt,
                    adapter=adapter,
                )
        if existing_attempts:
            # WB-3 may already have retained an exact success while a process
            # died after appending the attempt.  Re-entering the controller is
            # a response reuse, never a second socket invocation; its fresh
            # bundle must still match the originally persisted attempt bytes.
            attempt = existing_attempts[0]
            response = attempt_payloads.assistant_output_bytes
        if qualification_binding is not None and response is not None:
            _write_table_qualification_recovery_checkpoint(
                run_dir=run_dir,
                run_id=run_id,
                qualification_authorization=qualification_binding,
                attempt=attempt,
                payloads=attempt_payloads,
            )
    _checkpoint_recovery_phase(phase="AFTER_EXACT_SUCCESS")
    write_attempt_payloads(
        run_dir=run_dir,
        attempt=attempt,
        payloads=attempt_payloads,
    )
    _checkpoint_recovery_phase(phase="AFTER_ATTEMPT_PAYLOAD")
    _ensure_open_run_record(
        run_dir=run_dir, existing_records=existing_records, record=attempt,
    )
    _checkpoint_recovery_phase(phase="AFTER_ATTEMPT_RECORD")
    unknown_remote_outcome = (
        qualification_binding is not None
        and type(attempt.get("transport_observation")) is dict
        and attempt["transport_observation"].get("egress_attempted") is True
        and attempt.get("status") == "FAILED"
        and attempt.get("error_class") == "UNKNOWN_REMOTE_OUTCOME"
    )
    remote_failure_terminal = (
        qualification_binding is not None
        and type(attempt.get("transport_observation")) is dict
        and attempt["transport_observation"].get("egress_attempted") is True
        and attempt.get("status") == "FAILED"
        and not unknown_remote_outcome
    )
    if qualification_binding is not None:
        try:
            qualification_evidence = record_table_qualification_execution(
                repo_root=repo_root,
                authorization=qualification_binding,
                run_id=run_id,
                attempt=attempt,
            )
        except QualificationError as error:
            raise WorkflowError(error.code) from error
        _checkpoint_recovery_phase(phase="AFTER_LEDGER")
        _ensure_open_run_record(
            run_dir=run_dir,
            existing_records=existing_records,
            record=qualification_evidence,
        )
        _checkpoint_recovery_phase(phase="AFTER_QUALIFICATION_EVIDENCE")
    if unknown_remote_outcome:
        return {
            "run_id": run_id,
            "status": "UNKNOWN_REMOTE_OUTCOME",
            "attempt_id": attempt["attempt_id"],
        }
    if response is None:
        return {
            "run_id": run_id,
            "status": (
                "REMOTE_FAILURE_TERMINAL"
                if remote_failure_terminal
                else "FAILED_ATTEMPT"
            ),
            "attempt_id": attempt["attempt_id"],
        }
    candidate = validate_reader_output(
        response_text=response.decode("utf-8"),
        attempt_id=str(attempt["attempt_id"]),
        required_roles=roles,
        scope_contract=semantic["scope_contract"],
        source_reference_ids=[str(source_reference["source_reference_id"])],
        derived_asset_ids=[str(derived_asset["derived_asset_id"])],
    )
    if candidate["disclosure_group"] != semantic["disclosure_group"]:
        raise WorkflowError("Reader disclosure group differs from Spec")
    evidence = check_evidence(
        candidate=candidate,
        derived_asset=derived_asset,
        reader_manifest=reader_manifest,
        reader_payload_body=reader_payload_body,
        source_references=[source_reference],
        identity_constraints=semantic["identity_constraints"],
        scope_contract=semantic["scope_contract"],
    )
    validate_workflow_acceptance_binding(
        adapter=adapter,
        acceptance_receipt=attempt_payloads.acceptance_receipt,
        context=acceptance_context,
        candidate=candidate,
        evidence=evidence,
    )
    _ensure_open_run_record(
        run_dir=run_dir, existing_records=existing_records, record=candidate,
    )
    _ensure_open_run_record(
        run_dir=run_dir, existing_records=existing_records, record=evidence,
    )
    _checkpoint_recovery_phase(phase="AFTER_CANDIDATE_EVIDENCE")
    if evidence["status"] != "PASS":
        return {
            "run_id": run_id,
            "status": "EVIDENCE_REJECTED",
            "attempt_id": attempt["attempt_id"],
            "candidate_hash": candidate["candidate_hash"],
            "evidence_check_id": evidence["evidence_check_id"],
        }
    context = build_review_context(
        candidate=candidate,
        evidence_check=evidence,
        derived_asset=derived_asset,
        source_bindings=[source_reference],
        spec_semantic_hash=str(compiled_spec["spec_semantic_hash"]),
        required_claims=semantic["required_claims"],
    )
    rendered = render_review_markdown(
        review_context=context["review_context"],
    )
    review_unit = build_review_unit(
        candidate=candidate,
        evidence_check=evidence,
        source_bindings=[source_reference],
        compiled_spec=compiled_spec,
        review_context_hash=str(context["review_context_hash"]),
        rendered_review_hash=str(rendered["rendered_review_hash"]),
        renderer_semantic_version=str(
            rendered["review_renderer_semantic_version"]
        ),
    )
    _ensure_open_run_record(
        run_dir=run_dir,
        existing_records=existing_records,
        record=review_unit,
    )
    _checkpoint_recovery_phase(phase="AFTER_REVIEW_UNIT")
    review_dir = run_dir / "review" / str(review_unit["review_unit_hash"])
    if review_dir.exists():
        expected_assets = {
            "review_context.json": context["review_context_bytes"],
            "review.md": rendered["bytes"],
        }
        if (
            review_dir.is_symlink()
            or not review_dir.is_dir()
            or {
                path.name for path in review_dir.iterdir()
                if path.is_file() and not path.is_symlink()
            } != set(expected_assets)
            or any(
                (review_dir / name).is_symlink()
                or not (review_dir / name).is_file()
                or (review_dir / name).read_bytes() != content
                for name, content in expected_assets.items()
            )
        ):
            raise WorkflowError("TABLE_QUALIFICATION_TERMINAL_DIVERGENT")
    else:
        write_review_assets(
            run_dir=run_dir,
            review_unit=review_unit,
            review_context_bytes=context["review_context_bytes"],
            rendered_review_bytes=rendered["bytes"],
        )
    _checkpoint_recovery_phase(phase="AFTER_REVIEW_ASSETS")
    if qualification_binding is not None:
        _remove_table_qualification_recovery_checkpoint(run_dir=run_dir)
        _checkpoint_recovery_phase(phase="AFTER_CHECKPOINT_REMOVAL")
    return {
        "run_id": run_id,
        "status": "PENDING_HUMAN_REVIEW",
        "attempt_id": attempt["attempt_id"],
        "candidate_hash": candidate["candidate_hash"],
        "evidence_check_id": evidence["evidence_check_id"],
        "review_unit_hash": review_unit["review_unit_hash"],
        "terminal_recovery_state": (
            "EXACT_SUCCESS_NOT_MATERIALIZED"
            if reused_wb3_success
            else ""
        ),
    }


def finalize_reviewed_direct_results(
    *,
    run_dir: Path,
    repo_root: Path,
) -> Dict[str, object]:
    """Turn one effective whole-unit decision into observations/results.

    Args:
        run_dir: OPEN Run after HUMAN decision or optional D-06 SYSTEM path.
        repo_root: Repository whose Run-bound Specs are authoritative.

    Returns:
        Ordered created observation/result/trace identities and decision.

    Raises:
        WorkflowError: On ambiguous/stale review content, repository drift,
        period mismatch, or incomplete role classification.
    """
    manifest, records, decisions = load_open_run(run_dir=run_dir)
    if manifest.get("task_contract_bindings"):
        try:
            validate_table_qualification_run_bindings(
                repo_root=repo_root,
                run_dir=run_dir,
                manifest=manifest,
                records=records,
            )
        except QualificationError as error:
            raise WorkflowError(error.code) from error
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    if len(units) != 1:
        raise WorkflowError("Finalization requires one ReviewUnit")
    unit = units[0]
    bound_decisions = [
        decision
        for decision in decisions
        if decision["review_unit_hash"] == unit["review_unit_hash"]
    ]
    if not bound_decisions:
        attempts = [
            record
            for record in records
            if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
        ]
        if len(attempts) != 1:
            raise WorkflowError(
                "SYSTEM review requires one terminal AI attempt"
            )
        try:
            task_contract_bindings = (
                manifest["task_contract_bindings"]
                if "task_contract_bindings" in manifest
                else []
            )
            requirement = load_run_requirement_snapshot(
                repo_root=repo_root,
                task_contract_bindings=task_contract_bindings,
            )
            system_decision = create_system_review_decision(
                review_unit=unit,
                required_claims=unit["required_claims"],
                decided_at_utc=attempts[0]["finished_at_utc"],
                requirement=requirement,
            )
            append_review_decision(run_dir=run_dir, decision=system_decision)
        except (RunStoreError, ValueError) as error:
            raise WorkflowError(
                "Optional SYSTEM review policy cannot finalize the Run"
            ) from error
        manifest, records, decisions = load_open_run(run_dir=run_dir)
        units = [
            record
            for record in records
            if record["record_type"] == "REVIEW_UNIT"
        ]
        if len(units) != 1:
            raise WorkflowError("Finalization requires one ReviewUnit")
        unit = units[0]
        bound_decisions = [
            decision
            for decision in decisions
            if decision["review_unit_hash"] == unit["review_unit_hash"]
        ]
    records_file_hash = sha256_file(path=run_dir / "records.jsonl")
    decisions_file_hash = sha256_file(
        path=run_dir / "review_decisions.jsonl"
    )
    try:
        decision = effective_review_decision(
            review_unit=unit, decisions=bound_decisions,
        )
    except ValueError as error:
        raise WorkflowError(
            "Review decision semantic binding is invalid"
        ) from error
    evidence_matches = [
        record
        for record in records
        if record["record_type"] == "EVIDENCE_CHECK"
        and record["evidence_check_id"] == unit["evidence_check_id"]
    ]
    candidate_matches = [
        record
        for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
        and evidence_matches
        and record["candidate_hash"] == evidence_matches[0]["candidate_hash"]
    ]
    if len(evidence_matches) != 1 or len(candidate_matches) != 1:
        raise WorkflowError("Review Candidate/Evidence binding is ambiguous")
    candidate = candidate_matches[0]
    try:
        compiled_by_id = load_run_bound_specs(
            repo_root=repo_root, manifest=manifest,
        )
    except RunStoreError as error:
        raise WorkflowError(
            "Run-bound repository Specs are invalid"
        ) from error
    disclosure_matches = [
        wrapper
        for wrapper in compiled_by_id.values()
        if wrapper["spec_semantic_hash"] == unit["spec_semantic_hash"]
    ]
    try:
        task_specs_by_hash = load_run_bound_task_specs(
            repo_root=repo_root,
            manifest=manifest,
        )
    except RunStoreError as error:
        raise WorkflowError("Run-bound catalog task is invalid") from error
    if unit["spec_semantic_hash"] in task_specs_by_hash:
        disclosure_matches.append(task_specs_by_hash[
            str(unit["spec_semantic_hash"])
        ])
    if len(disclosure_matches) != 1:
        raise WorkflowError("Reviewed task Spec is not authoritative")
    disclosure_spec = disclosure_matches[0]
    if disclosure_spec["compiled"] != unit["compiled_spec"]:
        raise WorkflowError("Reviewed disclosure Spec differs from repository")
    roles = _required_roles(compiled_spec=disclosure_spec)
    projection = disclosure_spec["compiled"]["legacy_projection"]
    published_roles = list(projection["roles"])
    supporting_roles = list(projection["supporting_roles"])
    if set(roles) != set(candidate["selected"]):
        raise WorkflowError("Reviewed role classification exact set differs")
    role_metric_specs = {}
    for role in published_roles:
        metric_id = str(projection["role_metric_ids"][role])
        if metric_id not in compiled_by_id:
            raise WorkflowError("Published role MetricSpec is absent from Run")
        role_metric_specs[role] = compiled_by_id[metric_id]
    target_scope = (
        dict(decision["approved_claims"])
        if decision["decision"] == "APPROVE"
        else dict(unit["required_claims"])
    )
    for role in role_metric_specs:
        metric_semantic = role_metric_specs[role]["compiled"]
        metric_claims = metric_semantic["required_claims"]
        scope_contract = metric_semantic["scope_contract"]
        if scope_contract is None and dict(metric_claims) != target_scope:
            raise WorkflowError(
                "Reviewed metric required claims differ from ReviewUnit"
            )
        if scope_contract is not None:
            allowed_dimensions = set(scope_contract["allowed_dimensions"])
            non_scope_expected = {
                key: metric_claims[key]
                for key in metric_claims
                if key not in allowed_dimensions
            }
            non_scope_target = {
                key: target_scope[key]
                for key in target_scope
                if key not in allowed_dimensions
            }
            normalized_scope = {
                key: target_scope[key]
                for key in target_scope
                if key in allowed_dimensions
            }
            if (
                non_scope_target != non_scope_expected
                or not scope_satisfies_contract(
                    contract=scope_contract,
                    normalized_scope=normalized_scope,
                )
            ):
                raise WorkflowError(
                    "Reviewed metric scope differs from its contract"
                )
    target = {
        "company_id": manifest["company_id"],
        "period_start": manifest["target_period"]["period_start"],
        "period_end": manifest["target_period"]["period_end"],
        "scope": target_scope,
        "scope_key": scope_key(scope=target_scope),
    }
    expected_claimed_period = "FY{}".format(
        manifest["target_period"]["fiscal_year"]
    )
    if any(
        candidate["selected"][role]["claimed_period"]
        != expected_claimed_period
        for role in candidate["selected"]
    ):
        raise WorkflowError("Reviewed Candidate period differs from Run")
    created_observations = []
    created_results = []
    created_traces = []
    finalization_records = []
    if decision["decision"] == "REJECT":
        for role in published_roles:
            result, trace = withheld_metric_result(
                compiled_spec=role_metric_specs[role],
                target=target,
                reason_code="HUMAN_REVIEW_REJECTED",
            )
            finalization_records.extend([trace, result])
            created_results.append(result["result_id"])
            created_traces.append(trace["trace_id"])
        append_run_records_atomically(
            run_dir=run_dir,
            records=finalization_records,
            expected_records_file_hash=records_file_hash,
            expected_review_decisions_file_hash=decisions_file_hash,
        )
        return {
            "decision_id": decision["review_decision_id"],
            "observation_ids": [],
            "result_ids": created_results,
            "trace_ids": created_traces,
        }
    unit_mismatches = []
    for role in published_roles:
        expected_unit = role_metric_specs[role]["compiled"]["reported_unit"]
        if (
            candidate["selected"][role]["claimed_reported_unit"]
            != expected_unit
        ):
            unit_mismatches.append(role)
    for role in supporting_roles:
        expected_unit = projection["supporting_role_units"][role]
        if (
            candidate["selected"][role]["claimed_reported_unit"]
            != expected_unit
        ):
            unit_mismatches.append(role)
    if unit_mismatches:
        for role in published_roles:
            result, trace = withheld_metric_result(
                compiled_spec=role_metric_specs[role],
                target=target,
                reason_code="REPORTED_UNIT_MISMATCH",
            )
            finalization_records.extend([trace, result])
            created_results.append(result["result_id"])
            created_traces.append(trace["trace_id"])
        append_run_records_atomically(
            run_dir=run_dir,
            records=finalization_records,
            expected_records_file_hash=records_file_hash,
            expected_review_decisions_file_hash=decisions_file_hash,
        )
        return {
            "decision_id": decision["review_decision_id"],
            "observation_ids": [],
            "result_ids": created_results,
            "trace_ids": created_traces,
        }
    source_bindings = unit["source_bindings"]
    if len(source_bindings) != 1:
        raise WorkflowError("Phase 1 reviewed observation requires one source")
    source_reference = source_bindings[0]
    derived_ids = candidate["derived_asset_ids"]
    if len(derived_ids) != 1:
        raise WorkflowError("Phase 1 reviewed observation requires one grid")
    for role in candidate["selected"]:
        if role in published_roles:
            metric_spec = role_metric_specs[role]
            metric_id = str(metric_spec["compiled"]["metric_id"])
            canonical_unit = str(metric_spec["compiled"]["canonical_unit"])
        else:
            metric_spec = None
            metric_id = str(disclosure_spec["compiled"]["metric_id"])
            canonical_unit = str(projection["supporting_role_units"][role])
        observation = reviewed_observation(
            metric_id=metric_id,
            role=role,
            company_id=str(manifest["company_id"]),
            period_start=str(manifest["target_period"]["period_start"]),
            period_end=str(manifest["target_period"]["period_end"]),
            canonical_unit=canonical_unit,
            candidate=candidate,
            evidence_check=evidence_matches[0],
            review_unit=unit,
            decision=decision,
            source_reference=source_reference,
            derived_asset_id=str(derived_ids[0]),
            quality="EXACT",
        )
        finalization_records.append(observation)
        created_observations.append(observation["observation_id"])
        if metric_spec is None:
            continue
        result, trace = calculate_observation_metric(
            compiled_spec=metric_spec,
            target=target,
            company_traits=list(manifest["company_traits"]),
            observation=observation,
        )
        finalization_records.extend([trace, result])
        created_results.append(result["result_id"])
        created_traces.append(trace["trace_id"])
    append_run_records_atomically(
        run_dir=run_dir,
        records=finalization_records,
        expected_records_file_hash=records_file_hash,
        expected_review_decisions_file_hash=decisions_file_hash,
    )
    return {
        "decision_id": decision["review_decision_id"],
        "observation_ids": created_observations,
        "result_ids": created_results,
        "trace_ids": created_traces,
    }
