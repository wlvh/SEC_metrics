"""Persist immutable Run records, decisions, validation, and freeze hashes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .ai_adapter import AIAdapterError, AttemptPayloads, TransportObservation
from .ai_adapter import _output_schema_for_reader_request
from .ai_adapter import approved_transport_policy
from .ai_adapter import build_provider_request_body
from .ai_adapter import transport_observation_mismatch
from .canonical import atomic_write_bytes, atomic_write_json, content_hash
from .canonical import canonical_json_bytes
from .canonical import execution_semantics_hash, sha256_file, strict_json_file
from .canonical import sha256_bytes, strict_json_loads
from .calculator import calculate_metric, calculate_observation_metric
from .calculator import metric_is_applicable, withheld_metric_result
from .constraints import ConstraintError, verify_trace_observation_values
from .evidence import check_evidence
from .observations import ObservationError, reviewed_observation
from .records import RecordError, metric_result_contract_hash
from .records import validate_identifier, validate_record
from .records import validate_run_coordinates
from .render import RenderError, build_review_context
from .render import render_review_markdown
from .reader import validate_reader_output
from .reader_input import build_reader_payload, build_reader_shard_payload
from .reader_input import build_reader_task_contract
from .requirements import load_run_requirement_snapshot
from .review import effective_review_decision, system_review_allowed
from .review import SYSTEM_REVIEWER_ID, SYSTEM_REVIEW_REASON
from .review import validate_decision_binding
from .sources import companyfacts_structured_facts, load_raw_blob_bytes
from .specs import SpecError, compile_spec_files
from .states import FREEZEABLE_VALIDATION_STATUSES, validate_transition
from .table_grid import TableGridError, build_table_grid
from .table_payload import build_contiguous_table_shard
from .table_payload import encode_compact_table_payload
from .table_task_contracts import table_task_execution_plan
from .table_task_contracts import table_task_run_binding
from .table_task_contracts import TableTaskContractError
from .traits import TraitError, repository_company_ciks
from .traits import repository_company_traits


MANIFEST_FIELDS = {
    "audit_manifest_hash",
    "company_id",
    "company_traits",
    "content_manifest_hash",
    "execution_semantics_hash",
    "missing_required_source_roles",
    "record_type",
    "records_file_hash",
    "review_decisions_file_hash",
    "qualification_authorization",
    "requirement_hashes",
    "run_id",
    "source_references",
    "spec_file_hashes",
    "status",
    "target_period",
    "task_contract_bindings",
    "validation_file_hash",
}
RUN_VALIDATION_VIEW_FIELDS = (
    "company_id",
    "company_traits",
    "execution_semantics_hash",
    "missing_required_source_roles",
    "qualification_authorization",
    "requirement_hashes",
    "run_id",
    "source_references",
    "spec_file_hashes",
    "target_period",
    "task_contract_bindings",
)
_QUALIFICATION_RUN_PREFIX = "run:qualification:"
_QUALIFICATION_FIXTURE_FIELDS = {
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
FORMAL_RUN_VALIDATION_CHECKS = (
    "REVIEW_BINDINGS",
    "REVIEW_ASSETS",
    "REPOSITORY_BINDINGS",
    "RESULT_EXACT_SET",
    "RECORD_GRAPH_REPLAY",
    "EXECUTION_SEMANTICS",
    "ARTIFACT_EXACT_SET",
)


class RunStoreError(RuntimeError):
    """Report unsafe Run writes, freeze binding failures, or tampering."""


def _run_paths(*, run_dir: Path) -> Dict[str, Path]:
    """Return the fixed explicit file contract for one Run directory.

    Args:
        run_dir: Run root.

    Returns:
        Named paths for manifest, records, decisions, and validation.
    """
    return {
        "manifest": run_dir / "manifest.json",
        "records": run_dir / "records.jsonl",
        "decisions": run_dir / "review_decisions.jsonl",
        "validation": run_dir / "validation.json",
    }


def _read_manifest(*, run_dir: Path) -> Dict[str, object]:
    """Read one strict Run manifest.

    Args:
        run_dir: Run root.

    Returns:
        Validated RUN record.
    """
    payload = strict_json_file(
        path=_run_paths(run_dir=run_dir)["manifest"],
        allowed_fields=MANIFEST_FIELDS,
    )
    if not isinstance(payload, dict):
        raise RunStoreError("Run manifest root must be an object")
    try:
        return validate_record(record=payload)
    except ValueError as error:
        raise RunStoreError("Run manifest record is invalid") from error


def _read_jsonl(*, path: Path) -> List[Dict[str, object]]:
    """Read strict non-empty JSON objects from one immutable sequence.

    Args:
        path: JSONL file.

    Returns:
        Ordered validated records.

    Raises:
        RunStoreError: On unsafe path, blank interior line, non-object, or
            invalid record.
    """
    if path.is_symlink() or not path.is_file():
        raise RunStoreError(
            "Run JSONL must be a regular file: {}".format(path)
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise RunStoreError("Run JSONL must be UTF-8") from error
    if not text:
        return []
    lines = text.splitlines()
    if any(not line for line in lines):
        raise RunStoreError("Run JSONL contains an empty record")
    records = []
    for line in lines:
        parsed = strict_json_loads(text=line)
        if not isinstance(parsed, dict):
            raise RunStoreError("Run JSONL record must be an object")
        try:
            records.append(validate_record(record=parsed))
        except ValueError as error:
            raise RunStoreError("Run JSONL record is invalid") from error
    return records


def _run_validation_view_id(*, manifest: Mapping[str, object]) -> str:
    """Return the non-self-referential immutable Run validation view.

    Args:
        manifest: RUN identity fields before or after freeze.

    Returns:
        Content-addressed view ID stable across the OPEN-to-FROZEN update.
    """
    return "run:" + content_hash(
        value={
            field: manifest[field]
            for field in RUN_VALIDATION_VIEW_FIELDS
            if field in manifest
        }
    )


def _jsonl_bytes(*, records: Sequence[Mapping[str, object]]) -> bytes:
    """Serialize ordered records as stable audit JSONL.

    Args:
        records: Valid record sequence.

    Returns:
        UTF-8 JSONL with one LF per record.
    """
    lines = []
    for record in records:
        validate_record(record=record)
        lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def create_run(
    *,
    run_dir: Path,
    run_id: str,
    company_id: str,
    company_traits: Sequence[str],
    target_period: Mapping[str, object],
    source_references: Sequence[Mapping[str, object]],
    missing_required_source_roles: Sequence[str],
    spec_file_hashes: Mapping[str, str],
    requirement_hashes: Mapping[str, str],
    task_contract_bindings: Sequence[Mapping[str, object]] = (),
    qualification_authorization: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    """Create a new OPEN Run with explicit empty data files.

    Args:
        run_dir: New Run directory; it must not already exist.
        run_id: Opaque Run identity.
        company_id: Logical company identity.
        company_traits: Exact traits used for applicability in this Run.
        target_period: Explicit period object.
        source_references: Bound SourceReference records.
        missing_required_source_roles: Explicit missing roles.
        spec_file_hashes: Spec path/hash mapping.
        requirement_hashes: Exact immutable Requirement Snapshot hashes.
        task_contract_bindings: Explicit catalog task identities for this Run;
            retained historical disclosure Runs use an empty sequence.
        qualification_authorization: Exact LIVE table qualification authority,
            or ``None`` for recorded and retained historical Runs.

    Returns:
        Initial strict RUN manifest.

    Raises:
        RunStoreError: When the directory exists or input identities are not
            unique and explicit.
    """
    if run_dir.exists():
        raise RunStoreError("Run directory already exists")
    try:
        validate_identifier(value=run_id, field="run_id")
        validate_identifier(value=company_id, field="company_id")
    except RecordError as error:
        raise RunStoreError("Run identity is invalid") from error
    try:
        normalized_traits = list(company_traits)
    except TypeError as error:
        raise RunStoreError("Run company traits must be an array") from error
    if isinstance(company_traits, (str, bytes)):
        raise RunStoreError("Run company traits must be an array")
    try:
        validate_run_coordinates(
            target_period=target_period,
            company_traits=normalized_traits,
        )
    except RecordError as error:
        raise RunStoreError("Run business coordinates are invalid") from error
    content_hash(value=dict(target_period))
    if (
        any(
            not isinstance(role, str) or not role
            for role in missing_required_source_roles
        )
        or len(missing_required_source_roles)
        != len(set(missing_required_source_roles))
    ):
        raise RunStoreError("Missing source roles must be unique strings")
    for label, hashes in (
        ("Spec", spec_file_hashes),
        ("Requirement", requirement_hashes),
    ):
        if not isinstance(hashes, dict) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(hashes[key], str)
            or not hashes[key]
            for key in hashes
        ):
            raise RunStoreError("{} hashes are invalid".format(label))
    normalized_task_bindings = []
    binding_ids = set()
    for binding in task_contract_bindings:
        if not isinstance(binding, Mapping):
            raise RunStoreError("Run task contract binding is invalid")
        try:
            normalized = table_task_run_binding(runtime=binding)
        except (KeyError, TableTaskContractError) as error:
            raise RunStoreError("Run task contract binding is invalid") from error
        task_contract_id = str(normalized["task_contract_id"])
        if task_contract_id in binding_ids:
            raise RunStoreError("Run task contract identity is duplicated")
        binding_ids.add(task_contract_id)
        normalized_task_bindings.append(normalized)
    if normalized_task_bindings != sorted(
        normalized_task_bindings,
        key=lambda value: str(value["task_contract_id"]),
    ):
        raise RunStoreError("Run task contract bindings are not ordered")
    if qualification_authorization is not None and not isinstance(
        qualification_authorization, Mapping,
    ):
        raise RunStoreError("Run qualification authorization is invalid")
    validated_references = []
    for reference in source_references:
        validated = validate_record(record=reference)
        if validated["record_type"] != "SOURCE_REFERENCE":
            raise RunStoreError("Run source is not a SourceReference")
        validated_references.append(validated)
    reference_ids = [
        str(reference["source_reference_id"])
        for reference in validated_references
    ]
    if len(reference_ids) != len(set(reference_ids)):
        raise RunStoreError("Run SourceReference identities are duplicated")
    if any(
        reference["company_id"] != company_id
        for reference in validated_references
    ):
        raise RunStoreError("Run SourceReference company differs")
    stable_manifest = {
        "run_id": run_id,
        "company_id": company_id,
        "company_traits": normalized_traits,
        "target_period": dict(target_period),
        "source_references": [
            dict(reference) for reference in validated_references
        ],
        "missing_required_source_roles": list(missing_required_source_roles),
        "spec_file_hashes": dict(spec_file_hashes),
        "requirement_hashes": dict(requirement_hashes),
        "task_contract_bindings": normalized_task_bindings,
        **(
            {"qualification_authorization": dict(qualification_authorization)}
            if qualification_authorization is not None
            else {}
        ),
        "execution_semantics_hash": execution_semantics_hash(),
    }
    run_dir.mkdir(parents=True)
    paths = _run_paths(run_dir=run_dir)
    atomic_write_bytes(path=paths["records"], content=b"")
    atomic_write_bytes(path=paths["decisions"], content=b"")
    validation_body = {
        "status": "NOT_RUN",
        "view_id": _run_validation_view_id(manifest=stable_manifest),
        "checks": [],
        "artifact_hashes": {},
    }
    validation = dict(validation_body)
    validation.update(
        {
            "record_type": "VALIDATION_RECEIPT",
            "validation_receipt_id": content_hash(value=validation_body),
        }
    )
    validate_record(record=validation)
    atomic_write_json(path=paths["validation"], value=validation)
    manifest = {
        "record_type": "RUN",
        "status": "OPEN",
        "records_file_hash": sha256_file(path=paths["records"]),
        "review_decisions_file_hash": sha256_file(path=paths["decisions"]),
        "validation_file_hash": sha256_file(path=paths["validation"]),
        "content_manifest_hash": content_hash(value=[]),
        "audit_manifest_hash": content_hash(value=[]),
    }
    manifest.update(stable_manifest)
    validate_record(record=manifest)
    atomic_write_json(path=paths["manifest"], value=manifest)
    return manifest


def _run_validation_artifacts(*, run_dir: Path) -> Dict[str, object]:
    """Hash the exact non-self-referential Run artifacts validation covers.

    Args:
        run_dir: OPEN or FROZEN Run root.

    Returns:
        Relative path to SHA-256 and byte-size binding.

    Raises:
        RunStoreError: On an extra, missing, or unsafe Run artifact.
    """
    paths = _run_paths(run_dir=run_dir)
    records = _read_jsonl(path=paths["records"])
    expected = {"records.jsonl", "review_decisions.jsonl"}
    for record in records:
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT":
            expected.add(str(record["request_body_path"]))
            expected.add(str(record["reader_payload_path"]))
            expected.add(str(record["task_contract_path"]))
            expected.add(str(record["output_schema_path"]))
            if record["assistant_output_path"]:
                expected.add(str(record["assistant_output_path"]))
            if record["raw_response_path"]:
                expected.add(str(record["raw_response_path"]))
        elif record["record_type"] == "REVIEW_UNIT":
            review_root = "review/{}".format(record["review_unit_hash"])
            expected.add(review_root + "/review_context.json")
            expected.add(review_root + "/review.md")
    actual = set()
    for path in run_dir.rglob("*"):
        relative = path.relative_to(run_dir).as_posix()
        if path.is_symlink():
            raise RunStoreError("Run validation namespace contains a symlink")
        if path.is_file() and relative not in {
            "manifest.json",
            "validation.json",
        }:
            actual.add(relative)
    if actual != expected:
        raise RunStoreError("Run validation artifact exact set differs")
    return {
        relative: {
            "sha256": sha256_file(path=run_dir / relative),
            "size": (run_dir / relative).stat().st_size,
        }
        for relative in sorted(expected)
    }


def _write_validation_receipt(
    *,
    run_dir: Path,
    status: str,
    checks: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Replace NOT_RUN with one internally authorized terminal receipt.

    Args:
        run_dir: OPEN Run root.
        status: PASSED or FAILED.
        checks: Ordered gate results.

    Returns:
        Strict terminal ValidationReceipt.

    Raises:
        RunStoreError: On a non-OPEN Run or repeated/invalid transition.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "OPEN":
        raise RunStoreError("Only an OPEN Run can receive validation")
    paths = _run_paths(run_dir=run_dir)
    current_payload = strict_json_file(path=paths["validation"])
    if not isinstance(current_payload, dict):
        raise RunStoreError("Run validation root must be an object")
    current = validate_record(record=current_payload)
    try:
        validate_transition(
            object_type="VALIDATION_RECEIPT",
            current_status=str(current["status"]),
            target_status=status,
        )
    except ValueError as error:
        raise RunStoreError("Run validation transition is invalid") from error
    body = {
        "status": status,
        "view_id": _run_validation_view_id(manifest=manifest),
        "checks": [dict(check) for check in checks],
        "artifact_hashes": _run_validation_artifacts(run_dir=run_dir),
    }
    receipt = dict(body)
    receipt.update(
        {
            "record_type": "VALIDATION_RECEIPT",
            "validation_receipt_id": content_hash(value=body),
        }
    )
    validate_record(record=receipt)
    atomic_write_json(path=paths["validation"], value=receipt)
    return receipt


def write_validation_receipt(
    *,
    run_dir: Path,
    status: str,
    checks: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Persist only a caller-described FAILED audit conclusion.

    Args:
        run_dir: OPEN Run root.
        status: Must be ``FAILED``; PASSED is mechanically derived only.
        checks: Ordered failure details retained for audit.

    Returns:
        Strict FAILED ValidationReceipt.

    Raises:
        RunStoreError: When a caller attempts to self-sign PASSED or names any
            non-failure terminal state.
    """
    if status != "FAILED":
        raise RunStoreError(
            "PASSED requires public mechanical Run validation"
        )
    return _write_validation_receipt(
        run_dir=run_dir, status=status, checks=checks,
    )


def _verify_run_validation_receipt(
    *,
    run_dir: Path,
    manifest: Mapping[str, object],
    receipt: Mapping[str, object],
) -> None:
    """Rebind a terminal Run receipt to current exact audit-input bytes.

    Args:
        run_dir: Run root.
        manifest: RUN record naming the validated view.
        receipt: Strict ValidationReceipt reloaded from disk.

    Raises:
        RunStoreError: On stale view or artifact byte drift.
    """
    if receipt["view_id"] != _run_validation_view_id(manifest=manifest):
        raise RunStoreError("Run validation receipt view differs")
    if receipt["status"] == "NOT_RUN":
        return
    if receipt["artifact_hashes"] != _run_validation_artifacts(
        run_dir=run_dir
    ):
        raise RunStoreError("Run validation artifact bytes differ")


def write_attempt_payloads(
    *,
    run_dir: Path,
    attempt: Mapping[str, object],
    payloads: AttemptPayloads,
) -> None:
    """Persist exact AI request/task/response bytes at declared hash paths.

    Args:
        run_dir: OPEN Run root.
        attempt: Terminal AIExtractionAttempt record.
        payloads: Exact outbound, Reader, schema, task, and response bytes.

    Expected output:
        Each content-addressed path is created once; existing divergent bytes
        fail before the attempt record can be appended.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "OPEN":
        raise RunStoreError("Only an OPEN Run accepts attempt payloads")
    validated = validate_record(record=attempt)
    if validated["record_type"] != "AI_EXTRACTION_ATTEMPT":
        raise RunStoreError("Attempt payload owner is not an AI attempt")
    if not isinstance(payloads, AttemptPayloads):
        raise RunStoreError("Attempt payload bundle type is invalid")
    if (
        validated["transport_observation"]["request_body_bytes"]
        != len(payloads.request_body_bytes)
    ):
        raise RunStoreError("Attempt observed request byte count differs")
    content_by_field = {
        "request_body_path": payloads.request_body_bytes,
        "reader_payload_path": payloads.reader_payload_bytes,
        "task_contract_path": payloads.task_contract_bytes,
        "output_schema_path": payloads.output_schema_bytes,
    }
    if payloads.assistant_output_bytes is not None:
        content_by_field[
            "assistant_output_path"
        ] = payloads.assistant_output_bytes
    if payloads.raw_response_bytes is not None:
        content_by_field["raw_response_path"] = payloads.raw_response_bytes
    for field, content in content_by_field.items():
        relative = Path(str(validated[field]))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] != "attempt_payloads"
        ):
            raise RunStoreError("Attempt payload path is unsafe")
        path = run_dir / relative
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise RunStoreError("Attempt payload path is unsafe")
            if path.read_bytes() != content:
                raise RunStoreError(
                    "Attempt payload hash path has other bytes"
                )
            continue
        atomic_write_bytes(path=path, content=content)


def append_run_record(*, run_dir: Path, record: Mapping[str, object]) -> None:
    """Append one record only while the Run remains OPEN.

    Args:
        run_dir: Run root.
        record: Strict record.

    Expected output:
        The complete JSONL is atomically replaced; a FROZEN/FAILED Run remains
        byte-immutable.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "OPEN":
        raise RunStoreError("Frozen or failed Run cannot be modified")
    validated = validate_record(record=record)
    paths = _run_paths(run_dir=run_dir)
    records = _read_jsonl(path=paths["records"])
    records.append(validated)
    atomic_write_bytes(
        path=paths["records"], content=_jsonl_bytes(records=records)
    )


def append_run_records_atomically(
    *,
    run_dir: Path,
    records: Sequence[Mapping[str, object]],
    expected_records_file_hash: str,
    expected_review_decisions_file_hash: str,
) -> None:
    """Append one complete finalization batch through a byte-level CAS.

    Args:
        run_dir: OPEN Run root.
        records: Complete ordered records produced by one finalization.
        expected_records_file_hash: Records hash observed before calculation.
        expected_review_decisions_file_hash: Decision hash whose effective tip
            authorized the calculated batch.

    Expected output:
        Either the complete validated batch replaces ``records.jsonl`` once,
        or the prior bytes remain authoritative. A changed record stream or
        HUMAN decision chain fails before the atomic replacement.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "OPEN":
        raise RunStoreError("Frozen or failed Run cannot be modified")
    if not records:
        raise RunStoreError("Atomic finalization batch cannot be empty")
    paths = _run_paths(run_dir=run_dir)
    if (
        sha256_file(path=paths["records"])
        != expected_records_file_hash
        or sha256_file(path=paths["decisions"])
        != expected_review_decisions_file_hash
    ):
        raise RunStoreError("Run finalization input bytes changed")
    existing = _read_jsonl(path=paths["records"])
    try:
        validated = [validate_record(record=record) for record in records]
    except ValueError as error:
        raise RunStoreError("Finalization batch record is invalid") from error
    atomic_write_bytes(
        path=paths["records"],
        content=_jsonl_bytes(records=[*existing, *validated]),
    )


def load_open_run(
    *, run_dir: Path
) -> Tuple[
    Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]
]:
    """Read records and decisions from one still-mutable Run.

    Args:
        run_dir: OPEN Run root.

    Returns:
        Manifest, records, and decisions reloaded from disk.

    Raises:
        RunStoreError: When the Run is not OPEN or any record is invalid.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "OPEN":
        raise RunStoreError("Review CLI requires an OPEN Run")
    paths = _run_paths(run_dir=run_dir)
    return (
        manifest,
        _read_jsonl(path=paths["records"]),
        _read_jsonl(path=paths["decisions"]),
    )


def append_review_decision(
    *, run_dir: Path, decision: Mapping[str, object]
) -> None:
    """Append one immutable decision before Run freeze.

    Args:
        run_dir: Run root.
        decision: Strict REVIEW_DECISION record.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "OPEN":
        raise RunStoreError("Frozen or failed Run cannot accept a decision")
    try:
        validated = validate_record(record=decision)
    except ValueError as error:
        raise RunStoreError("ReviewDecision record is invalid") from error
    if validated["record_type"] != "REVIEW_DECISION":
        raise RunStoreError("Decision file accepts REVIEW_DECISION only")
    paths = _run_paths(run_dir=run_dir)
    records = _read_jsonl(path=paths["records"])
    if any(
        record["record_type"] in {
            "VERIFIED_OBSERVATION",
            "EXECUTION_TRACE",
            "METRIC_RESULT",
        }
        for record in records
    ):
        raise RunStoreError(
            "Review decision cannot change after finalization"
        )
    units = [
        record
        for record in records
        if record["record_type"] == "REVIEW_UNIT"
        and record["review_unit_hash"] == validated["review_unit_hash"]
    ]
    if len(units) != 1:
        raise RunStoreError(
            "Review decision requires one matching ReviewUnit"
        )
    try:
        validate_decision_binding(
            review_unit=units[0], decision=validated,
        )
    except ValueError as error:
        raise RunStoreError(
            "Review decision semantic binding failed"
        ) from error
    decisions = _read_jsonl(path=paths["decisions"])
    decisions.append(validated)
    atomic_write_bytes(
        path=paths["decisions"], content=_jsonl_bytes(records=decisions)
    )


def write_review_assets(
    *,
    run_dir: Path,
    review_unit: Mapping[str, object],
    review_context_bytes: bytes,
    rendered_review_bytes: bytes,
) -> None:
    """Persist immutable review inputs while a Run is OPEN.

    Args:
        run_dir: Run root.
        review_unit: Unit carrying canonical/rendered hashes.
        review_context_bytes: Exact canonical JSON shown through the renderer.
        rendered_review_bytes: Exact review Markdown shown to the human.

    Expected output:
        Both assets are hash-bound under the unit identity and later re-read by
        ``freeze_run`` to close the review TOCTOU window.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "OPEN":
        raise RunStoreError("Frozen or failed Run cannot accept review assets")
    unit = validate_record(record=review_unit)
    if unit["record_type"] != "REVIEW_UNIT":
        raise RunStoreError("Review assets require a REVIEW_UNIT")
    if (
        sha256_bytes(content=review_context_bytes)
        != unit["review_context_hash"]
    ):
        raise RunStoreError("Review context bytes differ from ReviewUnit")
    if (
        sha256_bytes(content=rendered_review_bytes)
        != unit["rendered_review_hash"]
    ):
        raise RunStoreError("Rendered review bytes differ from ReviewUnit")
    review_dir = run_dir / "review" / str(unit["review_unit_hash"])
    if review_dir.exists():
        raise RunStoreError("Review assets already exist")
    review_dir.mkdir(parents=True)
    atomic_write_bytes(
        path=review_dir / "review_context.json", content=review_context_bytes,
    )
    atomic_write_bytes(
        path=review_dir / "review.md", content=rendered_review_bytes,
    )


def _verify_review_assets(
    *, run_dir: Path, review_units: Sequence[Mapping[str, object]]
) -> None:
    """Re-read the exact context and rendered bytes for every review unit.

    Args:
        run_dir: Run root.
        review_units: REVIEW_UNIT records from disk.

    Raises:
        RunStoreError: On missing, extra, unsafe, or changed review assets.
    """
    review_root = run_dir / "review"
    expected_dirs = {str(unit["review_unit_hash"]) for unit in review_units}
    if not expected_dirs:
        if review_root.exists():
            raise RunStoreError("Run has review assets without ReviewUnit")
        return
    if review_root.is_symlink() or not review_root.is_dir():
        raise RunStoreError("Run review root is unsafe")
    actual_dirs = {
        path.name
        for path in review_root.iterdir()
        if path.is_dir() and not path.is_symlink()
    }
    if actual_dirs != expected_dirs:
        raise RunStoreError("Run review-unit directory exact set differs")
    for unit in review_units:
        review_dir = review_root / str(unit["review_unit_hash"])
        expected_files = {"review_context.json", "review.md"}
        actual_files = {
            path.name
            for path in review_dir.iterdir()
            if path.is_file() and not path.is_symlink()
        }
        if actual_files != expected_files:
            raise RunStoreError("Review asset exact set differs")
        if (
            sha256_file(path=review_dir / "review_context.json")
            != unit["review_context_hash"]
        ):
            raise RunStoreError("Review context changed before freeze")
        if (
            sha256_file(path=review_dir / "review.md")
            != unit["rendered_review_hash"]
        ):
            raise RunStoreError("Rendered review changed before freeze")


def load_run_bound_specs(
    *, repo_root: Path, manifest: Mapping[str, object]
) -> Dict[str, Dict[str, object]]:
    """Compile only the exact repository Spec bytes frozen by one Run.

    Args:
        repo_root: Repository root containing the declared relative paths.
        manifest: OPEN or FROZEN RUN record.

    Returns:
        Authoritative compiled wrappers keyed by metric ID.

    Raises:
        RunStoreError: On path escape, byte drift, missing dependency, or
            duplicate/cyclic Spec identity.
    """
    paths = []
    for relative in manifest["spec_file_hashes"]:
        path = repo_root / str(relative)
        try:
            path.resolve().relative_to(repo_root.resolve())
        except ValueError as error:
            raise RunStoreError("Run Spec path escapes repository") from error
        if path.is_symlink() or not path.is_file():
            raise RunStoreError("Run Spec file is unsafe")
        if sha256_file(path=path) != manifest["spec_file_hashes"][relative]:
            raise RunStoreError("Run Spec bytes changed before freeze/replay")
        paths.append(path)
    try:
        return compile_spec_files(paths=paths)
    except SpecError as error:
        raise RunStoreError("Run Spec closure cannot be compiled") from error


def _run_table_task_plans(
    *, repo_root: Path, manifest: Mapping[str, object],
) -> Dict[str, Dict[str, object]]:
    """Rebuild every catalog task declared by one formal Run manifest.

    Args:
        repo_root: Repository authority used for catalog/MetricSpec replay.
        manifest: Reloaded Run manifest carrying optional task bindings.

    Returns:
        Task-contract ID to fully rebuilt execution-plan mapping.

    Why:
        The attempt record alone cannot choose an unreviewed catalog revision.
        Persisting and revalidating the complete task binding makes the Run
        manifest, request bytes, response validation, and replay share one
        single-table authority.
    """
    bindings = (
        manifest["task_contract_bindings"]
        if "task_contract_bindings" in manifest
        else []
    )
    if not isinstance(bindings, list):
        raise RunStoreError("Run task contract bindings are invalid")
    plans = {}
    previous_id = ""
    for binding in bindings:
        if not isinstance(binding, Mapping):
            raise RunStoreError("Run task contract binding is invalid")
        if "task_contract_id" not in binding:
            raise RunStoreError("Run task contract ID is absent")
        task_contract_id = binding["task_contract_id"]
        if type(task_contract_id) is not str or not task_contract_id:
            raise RunStoreError("Run task contract ID is invalid")
        if previous_id and task_contract_id <= previous_id:
            raise RunStoreError("Run task contract bindings are not ordered")
        previous_id = task_contract_id
        if task_contract_id in plans:
            raise RunStoreError("Run task contract identity is duplicated")
        try:
            plan = table_task_execution_plan(
                repo_root=repo_root,
                task_contract_id=task_contract_id,
            )
        except TableTaskContractError as error:
            raise RunStoreError("Run catalog task cannot be rebuilt") from error
        if dict(binding) != plan["run_binding"]:
            raise RunStoreError("Run catalog task binding differs")
        plans[task_contract_id] = plan
    return plans


def load_run_bound_task_specs(
    *, repo_root: Path, manifest: Mapping[str, object],
) -> Dict[str, Dict[str, object]]:
    """Return catalog task Specs whose identities are bound by one Run.

    Args:
        repo_root: Repository authority used to rebuild catalog tasks.
        manifest: Reloaded Run manifest.

    Returns:
        Task semantic hash to executable single-table Spec wrapper.
    """
    plans = _run_table_task_plans(repo_root=repo_root, manifest=manifest)
    specs = {
        str(plan["task_spec"]["spec_semantic_hash"]): plan["task_spec"]
        for plan in plans.values()
    }
    if len(specs) != len(plans):
        raise RunStoreError("Run task Spec semantic identity is duplicated")
    return specs


def _qualification_fixture_traits(
    *, repo_root: Path, manifest: Mapping[str, object],
) -> Tuple[List[str], List[str]]:
    """Derive traits for one non-production qualification Run from its fixture.

    Args:
        repo_root: Repository containing the fixed qualification fixture tree.
        manifest: Persisted Run whose identity must name one safe fixture.

    Returns:
        Exact fixture-owned traits and its single external CIK.

    Raises:
        TraitError: When the Run is not a qualification Run or its fixture,
            company, period, source identity, or bytes do not bind exactly.

    This is the sole registry exception: production Runs still use only the
    configured company registry.  Qualification issuers are deliberately
    outside that registry, so their traits must be reconstructed from the
    source-bound fixture rather than supplied by a caller.
    """
    authorization = manifest.get("qualification_authorization")
    if authorization is not None:
        if type(authorization) is not dict:
            raise TraitError("Qualification authorization is invalid")
        fixture_id = authorization.get("qualification_fixture_id")
    else:
        run_id = manifest["run_id"]
        if type(run_id) is not str or not run_id.startswith(
            _QUALIFICATION_RUN_PREFIX
        ):
            raise TraitError("Run is not a qualification fixture Run")
        fixture_id = run_id[len(_QUALIFICATION_RUN_PREFIX):]
    if (
        type(fixture_id) is not str
        or not fixture_id
        or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
            for character in fixture_id
        )
    ):
        raise TraitError("Qualification fixture identity is invalid")
    fixture_root = repo_root / "fixtures/vnext/layouts" / fixture_id
    fixture_path = fixture_root / "fixture_manifest.json"
    if (
        fixture_root.is_symlink()
        or fixture_path.is_symlink()
        or not fixture_path.is_file()
    ):
        raise TraitError("Qualification fixture is absent or unsafe")
    fixture = strict_json_file(path=fixture_path)
    if (
        not isinstance(fixture, dict)
        or "source_repo_relative_path" not in fixture
        or type(fixture["source_repo_relative_path"]) is not str
    ):
        raise TraitError("Qualification fixture fields are invalid")
    source_relative = Path(str(fixture["source_repo_relative_path"]))
    source_path = repo_root / source_relative
    if (
        source_relative.is_absolute()
        or ".." in source_relative.parts
        or fixture_root not in source_path.parents
        or source_path.is_symlink()
        or not source_path.is_file()
    ):
        raise TraitError("Qualification fixture source is absent or unsafe")
    if (
        not isinstance(fixture, dict)
        or set(fixture) != _QUALIFICATION_FIXTURE_FIELDS
        or fixture["schema_version"] != 1
        or fixture["fixture_id"] != fixture_id
        or fixture["qualification_role"]
        not in {"SECOND_LAYOUT", "POST_FREEZE_HOLDOUT"}
        or fixture["company_id"] != manifest["company_id"]
        or fixture["company_traits"] != manifest["company_traits"]
        or fixture["target_period"] != manifest["target_period"]
        or fixture["source_repo_relative_path"]
        != source_path.relative_to(repo_root).as_posix()
        or fixture["source_sha256"] != sha256_file(path=source_path)
        or type(fixture["cik"]) is not str
        or not fixture["cik"].isdigit()
        or int(fixture["cik"]) <= 0
    ):
        raise TraitError("Qualification fixture binding differs from Run")
    references = manifest["source_references"]
    if (
        not isinstance(references, list)
        or len(references) != 1
        or references[0]["company_id"] != fixture["company_id"]
        or references[0]["source_url"] != fixture["source_url"]
        or references[0]["accession"] != fixture["accession"]
        or references[0]["document_name"] != fixture["document_name"]
        or references[0]["source_role"] != fixture["source_role"]
        or references[0]["request_attempt_id"]
        != fixture["request_attempt_id"]
        or references[0]["raw_asset_id"]
        != "sha256:" + fixture["source_sha256"]
    ):
        raise TraitError("Qualification SourceReference differs from fixture")
    return list(fixture["company_traits"]), [str(int(fixture["cik"]))]


def _run_company_authority(
    *, repo_root: Path, manifest: Mapping[str, object],
) -> Tuple[List[str], List[str]]:
    """Resolve traits/CIKs without letting registry membership mask a fixture.

    A LIVE SECOND_LAYOUT or POST_FREEZE_HOLDOUT authorization binds its
    matrix-owned fixture even when that fixture happens to name a company in
    the production registry.  FRESH_STABILITY and ordinary production Runs
    still use the registry first; historical external fixture Runs without an
    authorization retain the existing registry-miss fallback.
    """
    authorization = manifest.get("qualification_authorization")
    if (
        type(authorization) is dict
        and authorization.get("qualification_phase")
        in {"SECOND_LAYOUT", "POST_FREEZE_HOLDOUT"}
    ):
        return _qualification_fixture_traits(
            repo_root=repo_root,
            manifest=manifest,
        )
    try:
        return (
            repository_company_traits(
                repo_root=repo_root,
                company_id=str(manifest["company_id"]),
            ),
            repository_company_ciks(
                repo_root=repo_root,
                company_id=str(manifest["company_id"]),
            ),
        )
    except TraitError:
        return _qualification_fixture_traits(
            repo_root=repo_root,
            manifest=manifest,
        )


def _verify_repository_bindings(
    *,
    repo_root: Path,
    run_dir: Path,
    manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
) -> Tuple[
    Dict[str, Dict[str, object]],
    Dict[str, bytes],
    List[str],
    Dict[str, object],
]:
    """Revalidate Requirement-adjacent Spec and raw source bytes.

    Args:
        repo_root: Repository containing source bytes and Spec files.
        manifest: RUN record.
        records: Disk-reloaded Run records.

    Raises:
        RunStoreError: On unsafe paths, hash drift, or parent/source mismatch.

    Returns:
        Authoritative compiled Specs, raw bytes keyed by asset ID,
        registry-authorized CIKs, and exact Requirement Snapshot.
    """
    compiled_by_id = load_run_bound_specs(
        repo_root=repo_root, manifest=manifest,
    )
    compiled_by_hash = {
        str(wrapper["spec_semantic_hash"]): wrapper["compiled"]
        for wrapper in compiled_by_id.values()
    }
    task_specs_by_hash = load_run_bound_task_specs(
        repo_root=repo_root,
        manifest=manifest,
    )
    for spec_hash, wrapper in task_specs_by_hash.items():
        if spec_hash in compiled_by_hash:
            raise RunStoreError("Run task Spec identity is duplicated")
        compiled_by_hash[spec_hash] = wrapper["compiled"]
    for unit in (
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ):
        # Missing repository semantics must fail at the exact trust boundary,
        # before comparing caller-supplied compiled bytes.
        spec_hash = str(unit["spec_semantic_hash"])
        if spec_hash not in compiled_by_hash:
            raise RunStoreError("ReviewUnit Spec is absent from repository")
        if compiled_by_hash[spec_hash] != unit["compiled_spec"]:
            raise RunStoreError("ReviewUnit Spec differs from repository")
    task_contract_bindings = (
        manifest["task_contract_bindings"]
        if "task_contract_bindings" in manifest
        else []
    )
    try:
        requirement = load_run_requirement_snapshot(
            repo_root=repo_root,
            task_contract_bindings=task_contract_bindings,
        )
    except ValueError as error:
        raise RunStoreError("Run Requirement Snapshot is invalid") from error
    if manifest["requirement_hashes"] != requirement["hashes"]:
        if task_contract_bindings:
            raise RunStoreError(
                "Catalog task Run Requirement hashes differ from Issue #15"
            )
        raise RunStoreError("Run Requirement Snapshot hashes changed")
    raw_blobs = [
        record for record in records if record["record_type"] == "RAW_BLOB"
    ]
    raw_ids = {str(record["raw_asset_id"]) for record in raw_blobs}
    if len(raw_ids) != len(raw_blobs):
        raise RunStoreError("Run contains duplicate RawBlob identity")
    raw_bytes_by_id = {}
    for raw_blob in raw_blobs:
        try:
            raw_bytes_by_id[str(raw_blob["raw_asset_id"])] = (
                load_raw_blob_bytes(
                    repo_root=repo_root, raw_blob=dict(raw_blob),
                )
            )
        except ValueError as error:
            raise RunStoreError("Run RawBlob bytes changed") from error
    source_references = manifest["source_references"]
    for reference in source_references:
        validate_record(record=reference)
        if reference["raw_asset_id"] not in raw_ids:
            raise RunStoreError("Run SourceReference RawBlob is absent")
    derived_assets = [
        record
        for record in records
        if record["record_type"] == "DERIVED_ASSET"
    ]
    for asset in derived_assets:
        parent_ids = asset["parent_raw_asset_ids"]
        if not set(parent_ids).issubset(raw_ids):
            raise RunStoreError("DerivedAsset parent RawBlob is absent")
        if len(parent_ids) != 1:
            raise RunStoreError("Table-grid requires one parent RawBlob")
        try:
            replayed = build_table_grid(
                html_bytes=raw_bytes_by_id[str(parent_ids[0])],
                parent_raw_asset_ids=list(parent_ids),
                storage_uri=str(asset["storage_uri"]),
            )
        except (TableGridError, ValueError) as error:
            raise RunStoreError("DerivedAsset cannot be replayed") from error
        if replayed != asset:
            raise RunStoreError("DerivedAsset bytes differ from parent")
    try:
        repository_traits, repository_ciks = _run_company_authority(
            repo_root=repo_root,
            manifest=manifest,
        )
    except TraitError as qualification_error:
        raise RunStoreError(
            "Run company traits cannot be derived from repository"
        ) from qualification_error
    if manifest["company_traits"] != repository_traits:
        raise RunStoreError("Run company traits differ from repository")
    if (
        "qualification_authorization" in manifest
        or manifest.get("task_contract_bindings")
    ):
        try:
            from .qualification import QualificationError
            from .qualification import validate_table_qualification_run_bindings

            validate_table_qualification_run_bindings(
                repo_root=repo_root,
                run_dir=run_dir,
                manifest=manifest,
                records=records,
            )
        except QualificationError as error:
            raise RunStoreError(
                "Run qualification authority is invalid: {}".format(
                    error.code
                )
            ) from error
    return compiled_by_id, raw_bytes_by_id, repository_ciks, requirement


def _load_attempt_payloads(
    *,
    run_dir: Path,
    attempts: Mapping[str, Mapping[str, object]],
) -> Dict[str, Dict[str, bytes]]:
    """Read and hash-check the exact content-addressed AI payload set.

    Args:
        run_dir: Run root containing ``attempt_payloads``.
        attempts: AI attempts keyed by attempt ID.

    Returns:
        Request/task/optional response bytes keyed by attempt ID.

    Raises:
        RunStoreError: On missing, extra, unsafe, or digest-mismatched bytes.
    """
    payload_root = run_dir / "attempt_payloads"
    expected_paths = set()
    for attempt in attempts.values():
        expected_paths.add(str(attempt["request_body_path"]))
        expected_paths.add(str(attempt["reader_payload_path"]))
        expected_paths.add(str(attempt["task_contract_path"]))
        expected_paths.add(str(attempt["output_schema_path"]))
        if attempt["assistant_output_path"]:
            expected_paths.add(str(attempt["assistant_output_path"]))
        if attempt["raw_response_path"]:
            expected_paths.add(str(attempt["raw_response_path"]))
    if not expected_paths:
        if payload_root.exists():
            raise RunStoreError("Run has attempt payloads without attempts")
        return {}
    if payload_root.is_symlink() or not payload_root.is_dir():
        raise RunStoreError("Run attempt payload root is unsafe")
    actual_paths = set()
    for path in payload_root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            raise RunStoreError("Run attempt payload namespace is unsafe")
        actual_paths.add(path.relative_to(run_dir).as_posix())
    if actual_paths != expected_paths:
        raise RunStoreError("Run attempt payload exact set differs")
    loaded = {}
    for attempt_id in attempts:
        attempt = attempts[attempt_id]
        fields = {
            "request_body": (
                "request_body_path",
                "request_body_sha256",
            ),
            "reader_payload": (
                "reader_payload_path",
                "reader_payload_sha256",
            ),
            "task_contract": (
                "task_contract_path",
                "task_contract_sha256",
            ),
            "output_schema": (
                "output_schema_path",
                "output_schema_sha256",
            ),
        }
        if attempt["assistant_output_path"]:
            fields["assistant_output"] = (
                "assistant_output_path",
                "assistant_output_sha256",
            )
        if attempt["raw_response_path"]:
            fields["raw_response"] = (
                "raw_response_path",
                "raw_response_sha256",
            )
        payloads = {}
        for label in fields:
            path_field, digest_field = fields[label]
            path = run_dir / str(attempt[path_field])
            content = path.read_bytes()
            if sha256_bytes(content=content) != attempt[digest_field]:
                raise RunStoreError("AI attempt payload digest differs")
            payloads[label] = content
        if (
            attempt["transport_observation"]["request_body_bytes"]
            != len(payloads["request_body"])
        ):
            raise RunStoreError("AI attempt observed request size differs")
        loaded[attempt_id] = payloads
    return loaded


def _structured_concepts(
    *, compiled_spec: Mapping[str, object]
) -> List[str]:
    """Return every Company Facts concept visible in one compiled Spec.

    Args:
        compiled_spec: Repository-compiled MetricSpec wrapper.

    Returns:
        Sorted unique qualified or local concept names.

    Raises:
        RunStoreError: When compiled concept semantics are malformed.
    """
    semantic = compiled_spec["compiled"]
    pending = [semantic["inputs"]]
    concepts = []
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key in value:
                if key != "approved_concepts":
                    pending.append(value[key])
                    continue
                approved = value[key]
                if not isinstance(approved, list) or any(
                    type(concept) is not str or not concept
                    for concept in approved
                ):
                    raise RunStoreError(
                        "Compiled structured concepts are invalid"
                    )
                concepts.extend(str(concept) for concept in approved)
        elif isinstance(value, list):
            pending.extend(value)
    return sorted(set(concepts))


def _validate_successful_attempt_transport(
    *,
    attempt: Mapping[str, object],
    request_bytes: bytes,
    requirement: Mapping[str, object],
) -> None:
    """Reapply successful transport authority at freeze/replay.

    Args:
        attempt: Strict disk-reloaded AI attempt.
        request_bytes: Exact hash-verified request payload.
        requirement: Repository-reloaded Requirement Snapshot.

    Raises:
        RunStoreError: When a successful attempt bypasses recorded or approved
            remote transport policy.
    """
    if attempt["status"] != "SUCCEEDED":
        return
    try:
        observation = TransportObservation.from_mapping(
            value=attempt["transport_observation"],
        )
    except AIAdapterError as error:
        raise RunStoreError(
            "Successful AI transport observation is invalid"
        ) from error
    if not observation.egress_attempted:
        expected = {
            "egress_attempted": False,
            "provider": "recorded",
            "model": "recorded-response-v1",
            "model_requested": "recorded-response-v1",
            "model_returned": "none",
            "api": "recorded",
            "store": False,
            "endpoint_host": "none",
            "region": "local",
            "retention": "immutable-fixture",
            "data_use": "none",
            "timeout_seconds": 0,
            "retry_count": 0,
            "retries_performed": 0,
            "maximum_payload_bytes": len(request_bytes),
            "filing_egress_policy": "none",
            "request_body_bytes": len(request_bytes),
        }
        if observation.as_mapping() != expected:
            raise RunStoreError(
                "Successful recorded transport observation differs"
            )
        return
    try:
        policy = approved_transport_policy(requirement=requirement)
    except AIAdapterError as error:
        raise RunStoreError(
            "Successful remote attempt lacks approved D-01"
        ) from error
    mismatch = transport_observation_mismatch(
        policy=policy,
        observation=observation,
        request_bytes=request_bytes,
    )
    if mismatch is not None:
        raise RunStoreError(
            "Successful remote transport differs from D-01: {}".format(
                mismatch
            )
        )


def _structured_facts_from_sources(
    *,
    compiled_spec: Mapping[str, object],
    source_ids: Sequence[str],
    source_references: Mapping[str, Mapping[str, object]],
    raw_bytes_by_id: Mapping[str, bytes],
    company_ciks: Sequence[str],
) -> List[Dict[str, object]]:
    """Rebuild one MetricSpec's complete fact set from bound source bytes.

    Args:
        compiled_spec: Repository-compiled structured MetricSpec.
        source_ids: SourceReferences available to the calculation target.
        source_references: Run source identities keyed by content identity.
        raw_bytes_by_id: Hash-verified raw bytes keyed by RawBlob identity.
        company_ciks: Registry-authorized CIKs for the Run company.

    Returns:
        Deterministic Company Facts candidates for all declared concepts.

    Raises:
        RunStoreError: On absent source bytes or unreconstructable facts.
    """
    concepts = _structured_concepts(compiled_spec=compiled_spec)
    if not concepts:
        raise RunStoreError("Structured MetricSpec has no source concepts")
    facts = []
    for source_id in sorted(source_ids):
        if source_id not in source_references:
            raise RunStoreError("Structured SourceReference is absent")
        reference = source_references[source_id]
        raw_id = str(reference["raw_asset_id"])
        if raw_id not in raw_bytes_by_id:
            raise RunStoreError("Structured RawBlob bytes are absent")
        try:
            facts.extend(
                companyfacts_structured_facts(
                    raw_bytes=raw_bytes_by_id[raw_id],
                    source_reference=reference,
                    approved_concepts=concepts,
                    allowed_ciks=company_ciks,
                    include_instant=False,
                )
            )
        except ValueError as error:
            raise RunStoreError(
                "Structured source facts cannot be reconstructed"
            ) from error
    return facts


def _verify_structured_dependencies(
    *,
    manifest: Mapping[str, object],
    result_metric_id: str,
    input_observations: Sequence[Mapping[str, object]],
    target: Mapping[str, object],
    source_ids: Sequence[str],
    compiled_specs: Mapping[str, Mapping[str, object]],
    source_references: Mapping[str, Mapping[str, object]],
    raw_bytes_by_id: Mapping[str, bytes],
    company_ciks: Sequence[str],
) -> List[Dict[str, object]]:
    """Re-execute each reused structured dependency from its own raw facts.

    Args:
        manifest: Run business coordinates and repository-derived traits.
        result_metric_id: Metric consuming the dependency observations.
        input_observations: Exact observations consumed by its Trace.
        target: Trace-bound calculation coordinates.
        source_ids: SourceReferences available to that calculation.
        compiled_specs: Repository-compiled Run Spec closure.
        source_references: Run source identities keyed by content identity.
        raw_bytes_by_id: Hash-verified raw bytes keyed by RawBlob identity.
        company_ciks: Registry-authorized CIKs for the Run company.

    Raises:
        RunStoreError: When a reused observation is not the deterministic
            output of its own repository Spec and exact raw bytes.

    Returns:
        Exact dependency observations rebuilt for the consumer calculation.
    """
    consumer = compiled_specs[result_metric_id]["compiled"]
    dependency_ids = set(consumer["dependencies"])
    actual_dependencies = [
        observation
        for observation in input_observations
        if observation["metric_id"] != result_metric_id
    ]
    if any(
        observation["metric_id"] not in dependency_ids
        for observation in actual_dependencies
    ):
        raise RunStoreError(
            "Structured input is not a declared MetricSpec dependency"
        )
    expected_dependencies = []
    for metric_id in sorted(dependency_ids):
        if metric_id not in compiled_specs:
            raise RunStoreError("Structured dependency MetricSpec is absent")
        wrapper = compiled_specs[metric_id]
        semantic = wrapper["compiled"]
        if semantic["source_mode"] != "structured":
            raise RunStoreError(
                "Structured dependency source mode is unsupported"
            )
        # No current migrated dependency is nested. Refuse a future chain
        # until its lower-level observations can be replayed first.
        if semantic["dependencies"]:
            raise RunStoreError(
                "Nested structured dependency replay is unsupported"
            )
        facts = _structured_facts_from_sources(
            compiled_spec=wrapper,
            source_ids=source_ids,
            source_references=source_references,
            raw_bytes_by_id=raw_bytes_by_id,
            company_ciks=company_ciks,
        )
        try:
            _result, _trace, expected_observations = calculate_metric(
                compiled_spec=wrapper,
                target=target,
                company_traits=list(manifest["company_traits"]),
                structured_facts=facts,
                verified_observations=[],
            )
        except ValueError as error:
            raise RunStoreError(
                "Structured dependency replay cannot be reconstructed"
            ) from error
        expected_dependencies.extend(expected_observations)
    actual_by_id = {
        str(observation["observation_id"]): observation
        for observation in actual_dependencies
    }
    expected_by_id = {
        str(observation["observation_id"]): observation
        for observation in expected_dependencies
    }
    if actual_by_id != expected_by_id:
        raise RunStoreError(
            "Observation differs from structured dependency replay"
        )
    return [dict(observation) for observation in expected_dependencies]


def _structured_source_ids(
    *,
    target: Mapping[str, object],
    source_references: Mapping[str, Mapping[str, object]],
) -> List[str]:
    """Select exact Company Facts references for one trace-bound target.

    Args:
        target: Calculation target containing accession and numeric entity.
        source_references: Run source identities keyed by content identity.

    Returns:
        Deterministically ordered matching SourceReference identities.

    Raises:
        RunStoreError: When the target is incomplete or has no exact SEC
            Company Facts locator.
    """
    accession = target["accession"]
    entity = target["entity"]
    if (
        type(accession) is not str
        or not accession
        or type(entity) is not str
        or not entity.isdigit()
        or int(entity) <= 0
    ):
        raise RunStoreError("Structured calculation target is incomplete")
    document_name = "CIK{}.json".format(str(int(entity)).zfill(10))
    source_url = (
        "https://data.sec.gov/api/xbrl/companyfacts/" + document_name
    )
    source_ids = sorted(
        source_id
        for source_id in source_references
        if source_references[source_id]["accession"] == accession
        and source_references[source_id]["document_name"] == document_name
        and source_references[source_id]["source_url"] == source_url
    )
    if not source_ids:
        raise RunStoreError("Structured Company Facts source is absent")
    return source_ids


def _replay_structured_result(
    *,
    manifest: Mapping[str, object],
    result: Mapping[str, object],
    trace: Mapping[str, object],
    compiled_spec: Mapping[str, object],
    compiled_specs: Mapping[str, Mapping[str, object]],
    observations: Mapping[str, Mapping[str, object]],
    source_references: Mapping[str, Mapping[str, object]],
    raw_bytes_by_id: Mapping[str, bytes],
    company_ciks: Sequence[str],
) -> None:
    """Re-execute one structured result from repository Spec and raw bytes.

    Args:
        manifest: Run business coordinates and repository-derived traits.
        result: Stored MetricResult under review.
        trace: Stored ExecutionTrace bound to that result.
        compiled_spec: Repository-compiled structured MetricSpec.
        compiled_specs: Complete repository-compiled Run Spec closure.
        observations: Run observations keyed by content identity.
        source_references: Run source identities keyed by content identity.
        raw_bytes_by_id: Hash-verified raw source bytes.
        company_ciks: Registry-authorized CIKs for the Run company.

    Expected output:
        Numeric, evaluated-null, and fail-closed structured outputs exactly
        equal a fresh calculator execution from the trace-bound target.

    Raises:
        RunStoreError: On an unbound source fact, ambiguous target, or any
            Observation/Trace/Result difference from deterministic replay.
    """
    target = dict(trace["calculation_target"])
    if not metric_is_applicable(
        applicability=compiled_spec["compiled"]["applicability"],
        traits=list(manifest["company_traits"]),
    ):
        # Structural inapplicability is proven from repository traits and Spec
        # before any source lookup; requiring invented source coordinates here
        # would make a genuine no-source result impossible to replay.
        if trace["input_observation_ids"]:
            raise RunStoreError(
                "Structural result unexpectedly consumes observations"
            )
        try:
            expected_result, expected_trace, expected_observations = (
                calculate_metric(
                    compiled_spec=compiled_spec,
                    target=target,
                    company_traits=list(manifest["company_traits"]),
                    structured_facts=[],
                    verified_observations=[],
                )
            )
        except ValueError as error:
            raise RunStoreError(
                "Structural calculator replay cannot be reconstructed"
            ) from error
        if expected_observations:
            raise RunStoreError(
                "Structural calculator replay produced observations"
            )
        if result != expected_result or trace != expected_trace:
            raise RunStoreError(
                "Result/Trace differs from structural calculator replay"
            )
        return
    source_ids = _structured_source_ids(
        target=target, source_references=source_references,
    )
    input_ids = list(trace["input_observation_ids"])
    inputs = [
        observations[str(observation_id)] for observation_id in input_ids
    ]
    if any(observation["approval_effect_hash"] for observation in inputs):
        raise RunStoreError("Structured calculator input requires no approval")
    for observation in inputs:
        binding = observation["source_binding"]
        if (
            "entity" not in binding
            or type(binding["entity"]) is not str
            or not binding["entity"]
        ):
            raise RunStoreError("Structured observation entity is absent")
        if (
            observation["scope"] != target["scope"]
            or observation["scope_key"] != target["scope_key"]
            or binding["accession"] != target["accession"]
            or binding["entity"] != target["entity"]
            or binding["source_reference_id"] not in source_ids
        ):
            raise RunStoreError(
                "Structured observation calculation target differs"
            )
    result_metric_id = str(result["metric_id"])
    dependency_observations = _verify_structured_dependencies(
        manifest=manifest,
        result_metric_id=result_metric_id,
        input_observations=inputs,
        target=target,
        source_ids=source_ids,
        compiled_specs=compiled_specs,
        source_references=source_references,
        raw_bytes_by_id=raw_bytes_by_id,
        company_ciks=company_ciks,
    )
    facts = _structured_facts_from_sources(
        compiled_spec=compiled_spec,
        source_ids=source_ids,
        source_references=source_references,
        raw_bytes_by_id=raw_bytes_by_id,
        company_ciks=company_ciks,
    )
    try:
        expected_result, expected_trace, expected_observations = (
            calculate_metric(
                compiled_spec=compiled_spec,
                target=target,
                company_traits=list(manifest["company_traits"]),
                structured_facts=facts,
                verified_observations=dependency_observations,
            )
        )
    except ValueError as error:
        raise RunStoreError(
            "Structured calculator replay cannot be reconstructed"
        ) from error
    if result != expected_result or trace != expected_trace:
        raise RunStoreError(
            "Result/Trace differs from structured calculator replay"
        )
    for expected in expected_observations:
        observation_id = str(expected["observation_id"])
        if (
            observation_id not in observations
            or observations[observation_id] != expected
        ):
            raise RunStoreError(
                "Observation differs from structured calculator replay"
            )


def _expected_numeric_result_quality(
    *,
    trace: Mapping[str, object],
    observations: Mapping[str, Mapping[str, object]],
) -> str:
    """Derive conservative quality from inputs and accepted Spec branches.

    Args:
        trace: Repository-replayed ExecutionTrace for one numeric result.
        observations: Complete Run observations keyed by identity.

    Returns:
        ``APPROX`` when any input or accepted derived branch is approximate;
        otherwise ``EXACT``.

    Raises:
        RunStoreError: When a numeric result has no quality-bearing input or
            contains a quality outside the executable Spec contract.
    """
    qualities = [
        observations[str(observation_id)]["quality"]
        for observation_id in trace["input_observation_ids"]
    ]
    qualities.extend(
        step["quality"]
        for step in trace["steps"]
        if step["event"] == "DERIVED_BRANCH_SELECTED"
    )
    if not qualities or any(
        quality not in {"EXACT", "APPROX"} for quality in qualities
    ):
        raise RunStoreError("MetricResult quality inputs are invalid")
    return "APPROX" if "APPROX" in qualities else "EXACT"


def _validate_record_graph(
    *,
    repo_root: Path,
    run_dir: Path,
    manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
    effective_decisions: Mapping[str, Mapping[str, object]],
    compiled_specs: Mapping[str, Mapping[str, object]],
    raw_bytes_by_id: Mapping[str, bytes],
    company_ciks: Sequence[str],
    requirement: Mapping[str, object],
) -> None:
    """Validate cross-record identities used by calculation and review.

    Args:
        repo_root: Repository authority used to rebuild catalog task plans.
        run_dir: Run root containing exact AI attempt bytes.
        manifest: RUN record with SourceReference bindings.
        records: Strict disk-reloaded records.
        effective_decisions: Effective HUMAN or authorized SYSTEM decisions
            keyed by effect hash.
        compiled_specs: Repository-compiled Run-bound Specs by metric ID.
        raw_bytes_by_id: Hash-verified Run raw bytes keyed by asset ID.
        company_ciks: Registry-authorized CIKs for the logical company.
        requirement: Repository-reloaded exact Requirement Snapshot.

    Raises:
        RunStoreError: On duplicate primary IDs, detached trace/evidence,
        missing source/asset binding, or Candidate/ReviewUnit drift.
    """
    system_decisions = [
        decision
        for decision in effective_decisions.values()
        if decision["reviewer_type"] == "SYSTEM"
    ]
    if system_decisions and not system_review_allowed(
        requirement=requirement,
    ):
        raise RunStoreError("SYSTEM review is not authorized by D-06")
    for decision in system_decisions:
        if (
            decision["decision"] != "APPROVE"
            or decision["reviewer_id"] != SYSTEM_REVIEWER_ID
            or decision["reason"] != SYSTEM_REVIEW_REASON
        ):
            raise RunStoreError("SYSTEM review record differs from D-06")
    primary_fields = {
        "AI_EXTRACTION_ATTEMPT": "attempt_id",
        "DETERMINISTIC_VERIFIED_CLAIM": "verified_claim_id",
        "DERIVED_ASSET": "derived_asset_id",
        "EVIDENCE_CHECK": "evidence_check_id",
        "EXECUTION_TRACE": "trace_id",
        "METRIC_RESULT": "result_id",
        "OBSERVATION_CANDIDATE": "candidate_hash",
        "RAW_BLOB": "raw_asset_id",
        "READER_INPUT_MANIFEST": "reader_input_manifest_id",
        "REVIEW_UNIT": "review_unit_hash",
        "SOURCE_REFERENCE": "source_reference_id",
        "VERIFIED_OBSERVATION": "observation_id",
    }
    identifiers = []
    for record in records:
        record_type = str(record["record_type"])
        if record_type in primary_fields:
            identifiers.append(
                (record_type, str(record[primary_fields[record_type]]),)
            )
    if len(identifiers) != len(set(identifiers)):
        raise RunStoreError("Run record graph contains duplicate identity")
    source_references = {
        str(reference["source_reference_id"]): reference
        for reference in manifest["source_references"]
    }
    if len(source_references) != len(manifest["source_references"]):
        raise RunStoreError("Run SourceReference identity is duplicated")
    if any(
        reference["company_id"] != manifest["company_id"]
        for reference in source_references.values()
    ):
        raise RunStoreError("Run SourceReference company differs")
    source_ids = set(source_references)
    derived_assets = {
        str(record["derived_asset_id"]): record
        for record in records
        if record["record_type"] == "DERIVED_ASSET"
    }
    derived_ids = set(derived_assets)
    observations = {
        str(record["observation_id"]): record
        for record in records
        if record["record_type"] == "VERIFIED_OBSERVATION"
    }
    deterministic_claims = {
        str(record["verified_claim_id"]): record
        for record in records
        if record["record_type"] == "DETERMINISTIC_VERIFIED_CLAIM"
    }
    if any(
        claim["source_reference_id"] not in source_ids
        or claim["company_id"] != manifest["company_id"]
        for claim in deterministic_claims.values()
    ):
        raise RunStoreError("Deterministic claim source binding differs")
    for observation in observations.values():
        binding = observation["source_binding"]
        if "matched_verified_claim_ids" not in binding:
            continue
        claim_ids = binding["matched_verified_claim_ids"]
        if (
            not isinstance(claim_ids, list)
            or any(
                not isinstance(claim_id, str)
                or claim_id not in deterministic_claims
                for claim_id in claim_ids
            )
        ):
            raise RunStoreError(
                "Observation deterministic claim binding differs"
            )
    traces = {
        str(record["trace_id"]): record
        for record in records
        if record["record_type"] == "EXECUTION_TRACE"
    }
    results = {
        str(record["result_id"]): record
        for record in records
        if record["record_type"] == "METRIC_RESULT"
    }
    if manifest["missing_required_source_roles"] and any(
        result["publication"] == "PUBLISHED"
        for result in results.values()
    ):
        # A Run may retain incomplete evidence for audit, but an explicit
        # missing-source declaration cannot coexist with a published claim.
        raise RunStoreError(
            "Run with missing source roles cannot contain PUBLISHED results"
        )
    candidates = {
        str(record["candidate_hash"]): record
        for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
    }
    evidence_checks = {
        str(record["evidence_check_id"]): record
        for record in records
        if record["record_type"] == "EVIDENCE_CHECK"
    }
    attempts = {
        str(record["attempt_id"]): record
        for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    }
    if len(attempts) != len([
        record
        for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]):
        raise RunStoreError("AI attempt identity is duplicated")
    if any(
        attempt["status"] not in {"SUCCEEDED", "FAILED"}
        for attempt in attempts.values()
    ):
        # STARTED is useful only while a Run is mutable. Freezing it would
        # turn an unfinished snapshot into a permanent audit conclusion.
        raise RunStoreError("FROZEN Run requires terminal AI attempts")
    attempt_payloads = _load_attempt_payloads(
        run_dir=run_dir, attempts=attempts,
    )
    review_units = {
        str(record["review_unit_hash"]): record
        for record in records
        if record["record_type"] == "REVIEW_UNIT"
    }
    table_task_plans = _run_table_task_plans(
        repo_root=repo_root,
        manifest=manifest,
    )
    specs_by_semantic_hash = {
        str(wrapper["spec_semantic_hash"]): wrapper
        for wrapper in compiled_specs.values()
    }
    for plan in table_task_plans.values():
        task_spec = plan["task_spec"]
        task_hash = str(task_spec["spec_semantic_hash"])
        if task_hash in specs_by_semantic_hash:
            raise RunStoreError("Run task Spec identity is duplicated")
        specs_by_semantic_hash[task_hash] = task_spec
    reader_manifests = [
        record
        for record in records
        if record["record_type"] == "READER_INPUT_MANIFEST"
    ]
    reader_manifests_by_id = {
        str(reader_manifest["reader_input_manifest_id"]): reader_manifest
        for reader_manifest in reader_manifests
    }
    attempt_contexts = {}
    replayed_attempt_candidates = {}
    for attempt_id in attempts:
        # Every attempt, including a failed one, must bind independently
        # reproducible request bytes to one repository-owned task authority.
        attempt = attempts[attempt_id]
        catalog_task_id = (
            attempt["task_contract_id"]
            if "task_contract_id" in attempt
            else ""
        )
        if catalog_task_id:
            if catalog_task_id not in table_task_plans:
                raise RunStoreError("AI attempt catalog task is absent from Run")
            plan = table_task_plans[catalog_task_id]
            task_contract = plan["runtime_task_contract"]
            task_spec = plan["task_spec"]
            if (
                attempt["task_spec_semantic_hash"]
                != task_spec["spec_semantic_hash"]
                or attempt["catalog_task_contract_hash"]
                != task_contract["catalog_task_contract_hash"]
                or attempt["catalog_output_schema_hash"]
                != task_contract["output_schema_hash"]
                or attempt["system_prompt_hash"]
                != task_contract["system_prompt_hash"]
            ):
                raise RunStoreError("AI attempt catalog task binding differs")
        else:
            spec_hash = str(attempt["task_spec_semantic_hash"])
            if spec_hash not in specs_by_semantic_hash:
                raise RunStoreError("AI attempt task Spec is absent")
            task_spec = specs_by_semantic_hash[spec_hash]
            if task_spec["compiled"]["kind"] != "disclosure_group":
                raise RunStoreError("AI attempt task Spec is not a disclosure")
            task_contract = build_reader_task_contract(
                compiled_spec=task_spec,
            )
        reader_id = str(attempt["reader_input_manifest_hash"])
        if reader_id not in reader_manifests_by_id:
            raise RunStoreError("AI attempt ReaderInputManifest is absent")
        reader_manifest = reader_manifests_by_id[reader_id]
        derived_id = str(reader_manifest["derived_asset_id"])
        if derived_id not in derived_assets:
            raise RunStoreError("AI attempt DerivedAsset is absent")
        sharded = "table_shard_id" in attempt
        if sharded:
            parent_transport = encode_compact_table_payload(
                derived_asset=derived_assets[derived_id],
            )
            table_shard = build_contiguous_table_shard(
                parent_transport=parent_transport,
                shard_index=attempt["table_shard_index"],
                shard_count=attempt["table_shard_count"],
                start_table_order=attempt["start_table_order"],
                end_table_order=attempt["end_table_order"],
            )
            if (
                table_shard["shard_id"] != attempt["table_shard_id"]
                or table_shard["shard_payload_sha256"]
                != attempt["table_shard_payload_sha256"]
            ):
                raise RunStoreError("AI attempt table shard binding differs")
            payload = build_reader_shard_payload(
                manifest=reader_manifest,
                derived_asset=derived_assets[derived_id],
                task_contract=task_contract,
                table_shard=table_shard,
                table_shard_set_id=attempt["table_shard_set_id"],
            )
        else:
            payload = build_reader_payload(
                manifest=reader_manifest,
                derived_asset=derived_assets[derived_id],
                task_contract=task_contract,
            )
        stored = attempt_payloads[attempt_id]
        if (
            stored["task_contract"]
            != canonical_json_bytes(value=task_contract)
            or stored["reader_payload"] != payload["request_bytes"]
        ):
            raise RunStoreError("AI request bytes differ from repository Spec")
        observation = TransportObservation.from_mapping(
            value=attempt["transport_observation"]
        )
        if observation.egress_attempted:
            policy = approved_transport_policy(requirement=requirement)
            expected_request, expected_schema = (
                build_provider_request_body(
                    policy=policy,
                    reader_request_bytes=stored["reader_payload"],
                )
            )
        else:
            expected_request = stored["reader_payload"]
            expected_schema = canonical_json_bytes(
                value=_output_schema_for_reader_request(
                    reader_request_bytes=stored["reader_payload"],
                )
            )
        if (
            stored["request_body"] != expected_request
            or stored["output_schema"] != expected_schema
        ):
            raise RunStoreError("AI provider envelope or schema differs")
        _validate_successful_attempt_transport(
            attempt=attempt,
            request_bytes=stored["request_body"],
            requirement=requirement,
        )
        if attempt["status"] == "SUCCEEDED":
            if "assistant_output" not in stored:
                raise RunStoreError(
                    "Successful AI attempt response bytes are absent"
                )
            try:
                replayed = validate_reader_output(
                    response_text=stored["assistant_output"].decode("utf-8"),
                    attempt_id=attempt_id,
                    required_roles=task_contract["required_roles"],
                    scope_contract=task_contract["scope_contract"],
                    source_reference_ids=list(
                        reader_manifest["source_reference_ids"]
                    ),
                    derived_asset_ids=[derived_id],
                    table_shard_contract=(
                        payload["table_shard_contract"] if sharded else None
                    ),
                )
            except (UnicodeDecodeError, ValueError) as error:
                # Candidate reachability cannot be the schema gate: every
                # successful transport result must independently be usable.
                raise RunStoreError(
                    "Successful AI response bytes cannot be replayed"
                ) from error
            if replayed["disclosure_group"] != task_contract[
                "disclosure_group"
            ]:
                raise RunStoreError(
                    "Successful AI response bytes name another disclosure"
                )
            replayed_attempt_candidates[attempt_id] = replayed
        attempt_contexts[attempt_id] = {
            "task_contract": task_contract,
            "task_spec": task_spec,
            "payload": payload,
            "reader_manifest": reader_manifest,
        }
    candidate_manifests = {}
    candidate_payload_bodies = {}
    for observation in observations.values():
        binding = observation["source_binding"]
        if binding["source_reference_id"] not in source_ids:
            raise RunStoreError("Observation SourceReference is absent")
        reference = source_references[str(binding["source_reference_id"])]
        if observation["company_id"] != manifest["company_id"]:
            raise RunStoreError("Observation company differs from Run")
        if (
            observation["period_start"]
            != manifest["target_period"]["period_start"]
            or observation["period_end"]
            != manifest["target_period"]["period_end"]
        ):
            raise RunStoreError("Observation period differs from Run")
        for field in (
            "raw_asset_id",
            "accession",
            "document_name",
            "source_role",
        ):
            if binding[field] != reference[field]:
                raise RunStoreError(
                    "Observation SourceReference field differs: {}".format(
                        field
                    )
                )
        approval_effect = str(observation["approval_effect_hash"])
        if approval_effect and approval_effect not in effective_decisions:
            raise RunStoreError(
                "Observation approval effect is not effective"
            )
        if not approval_effect and "derived_asset_id" in binding:
            raise RunStoreError(
                "Reviewed observation lacks an approval effect"
            )
        if not approval_effect:
            metric_id = str(observation["metric_id"])
            if metric_id not in compiled_specs:
                raise RunStoreError(
                    "Structured observation MetricSpec is absent"
                )
            source_mode = compiled_specs[metric_id]["compiled"][
                "source_mode"
            ]
            if source_mode not in {
                "structured",
                "structured_and_derived",
            }:
                raise RunStoreError(
                    "AI-table observation lacks HUMAN approval"
                )
        if approval_effect:
            decision = effective_decisions[approval_effect]
            reviewed_source_ids = {
                str(source["source_reference_id"])
                for source in decision["reviewed_source_bindings"]
            }
            if binding["source_reference_id"] not in reviewed_source_ids:
                raise RunStoreError(
                    "Observation approval source binding differs"
                )
            unit_hash = str(decision["reviewed_spec_semantic_hash"])
            if unit_hash not in specs_by_semantic_hash:
                raise RunStoreError("Reviewed observation Spec is absent")
            if decision["review_unit_hash"] not in review_units:
                raise RunStoreError("Reviewed observation unit is absent")
            review_unit = review_units[str(decision["review_unit_hash"])]
            disclosure_spec = specs_by_semantic_hash[unit_hash]
            projection = disclosure_spec["compiled"]["legacy_projection"]
            role = str(observation["semantic_role"])
            if role in projection["roles"]:
                expected_metric_id = str(
                    projection["role_metric_ids"][role]
                )
                if expected_metric_id not in compiled_specs:
                    raise RunStoreError("Reviewed role MetricSpec is absent")
                metric_semantic = compiled_specs[expected_metric_id][
                    "compiled"
                ]
                expected_unit = str(metric_semantic["canonical_unit"])
                expected_reported_unit = str(
                    metric_semantic["reported_unit"]
                )
            elif role in projection["supporting_roles"]:
                expected_metric_id = str(
                    disclosure_spec["compiled"]["metric_id"]
                )
                expected_unit = str(
                    projection["supporting_role_units"][role]
                )
                expected_reported_unit = expected_unit
            else:
                raise RunStoreError("Reviewed observation role is unknown")
            if (
                observation["metric_id"] != expected_metric_id
                or observation["unit"] != expected_unit
            ):
                raise RunStoreError(
                    "Reviewed observation metric/unit differs from Spec"
                )
            evidence_id = str(review_unit["evidence_check_id"])
            if evidence_id not in evidence_checks:
                raise RunStoreError(
                    "Reviewed observation EvidenceCheck is absent"
                )
            evidence = evidence_checks[evidence_id]
            candidate_hash = str(evidence["candidate_hash"])
            if candidate_hash not in candidates:
                raise RunStoreError(
                    "Reviewed observation Candidate is absent"
                )
            candidate = candidates[candidate_hash]
            if candidate["selected"][role][
                "claimed_reported_unit"
            ] != expected_reported_unit:
                raise RunStoreError(
                    "Reviewed observation Candidate unit is incompatible"
                )
            if (
                "derived_asset_id" not in binding
                or not binding["derived_asset_id"]
            ):
                raise RunStoreError(
                    "Reviewed observation DerivedAsset is absent"
                )
            try:
                expected_observation = reviewed_observation(
                    metric_id=expected_metric_id,
                    role=role,
                    company_id=str(manifest["company_id"]),
                    period_start=str(
                        manifest["target_period"]["period_start"]
                    ),
                    period_end=str(
                        manifest["target_period"]["period_end"]
                    ),
                    canonical_unit=expected_unit,
                    candidate=candidate,
                    evidence_check=evidence,
                    review_unit=review_unit,
                    decision=decision,
                    source_reference=reference,
                    derived_asset_id=str(binding["derived_asset_id"]),
                    quality="EXACT",
                )
            except (ObservationError, ValueError) as error:
                raise RunStoreError(
                    "Reviewed observation cannot be reconstructed"
                ) from error
            if expected_observation != observation:
                raise RunStoreError(
                    "Reviewed observation differs from Candidate"
                )
        if "derived_asset_id" in binding and binding["derived_asset_id"]:
            if binding["derived_asset_id"] not in derived_ids:
                raise RunStoreError("Observation DerivedAsset is absent")
    result_expectations = []
    supporting_observation_ids = set()
    for effect_hash in effective_decisions:
        # A HUMAN decision covers one complete role and output set. Rebinding
        # only surviving records would let a caller silently drop an approved
        # claim or a fail-closed result before freeze.
        decision = effective_decisions[effect_hash]
        unit = review_units[str(decision["review_unit_hash"])]
        evidence_id = str(unit["evidence_check_id"])
        if evidence_id not in evidence_checks:
            raise RunStoreError("Reviewed EvidenceCheck is absent")
        candidate_hash = str(evidence_checks[evidence_id]["candidate_hash"])
        if candidate_hash not in candidates:
            raise RunStoreError("Reviewed Candidate is absent")
        candidate = candidates[candidate_hash]
        spec_hash = str(decision["reviewed_spec_semantic_hash"])
        if spec_hash not in specs_by_semantic_hash:
            raise RunStoreError("Reviewed disclosure Spec is absent")
        projection = specs_by_semantic_hash[spec_hash]["compiled"][
            "legacy_projection"
        ]
        expected_units = {}
        for role in projection["roles"]:
            metric_id = str(projection["role_metric_ids"][role])
            if metric_id not in compiled_specs:
                raise RunStoreError("Reviewed role MetricSpec is absent")
            expected_units[role] = str(
                compiled_specs[metric_id]["compiled"]["reported_unit"]
            )
        for role in projection["supporting_roles"]:
            expected_units[role] = str(
                projection["supporting_role_units"][role]
            )
        no_candidate_shard = (
            candidate.get("shard_disposition") == "NO_CANDIDATE_IN_SHARD"
        )
        if (
            not no_candidate_shard
            and set(candidate["selected"]) != set(expected_units)
        ):
            raise RunStoreError("Reviewed Candidate role exact set differs")
        units_match = (
            True
            if no_candidate_shard
            else not any(
                candidate["selected"][role]["claimed_reported_unit"]
                != expected_units[role]
                for role in expected_units
            )
        )
        expected_roles = (
            set(expected_units)
            if (
                decision["decision"] == "APPROVE"
                and units_match
                and not no_candidate_shard
            )
            else set()
        )
        actual_by_role = {
            str(observation["semantic_role"]): str(
                observation["observation_id"]
            )
            for observation in observations.values()
            if observation["approval_effect_hash"] == effect_hash
        }
        actual_roles = [
            str(observation["semantic_role"])
            for observation in observations.values()
            if observation["approval_effect_hash"] == effect_hash
        ]
        if (
            len(actual_roles) != len(set(actual_roles))
            or set(actual_roles) != expected_roles
        ):
            raise RunStoreError(
                "Approved observation role exact set differs"
            )
        expected_reason = "PASS"
        if decision["decision"] == "REJECT":
            expected_reason = "HUMAN_REVIEW_REJECTED"
        elif no_candidate_shard:
            expected_reason = "SHARD_NO_CANDIDATE"
        elif not units_match:
            expected_reason = "REPORTED_UNIT_MISMATCH"
        if expected_reason == "PASS":
            supporting_observation_ids.update(
                actual_by_role[str(role)]
                for role in projection["supporting_roles"]
            )
        target_scope = (
            dict(decision["approved_claims"])
            if decision["decision"] == "APPROVE"
            else dict(unit["required_claims"])
        )
        target = {
            "company_id": manifest["company_id"],
            "period_start": manifest["target_period"]["period_start"],
            "period_end": manifest["target_period"]["period_end"],
            "scope": target_scope,
            "scope_key": content_hash(value=target_scope),
        }
        for role in projection["roles"]:
            metric_id = str(projection["role_metric_ids"][role])
            wrapper = compiled_specs[metric_id]
            try:
                if expected_reason == "PASS":
                    expected_result, expected_trace = (
                        calculate_observation_metric(
                            compiled_spec=wrapper,
                            target=target,
                            company_traits=list(manifest["company_traits"]),
                            observation=observations[
                                actual_by_role[role]
                            ],
                        )
                    )
                else:
                    expected_result, expected_trace = (
                        withheld_metric_result(
                            compiled_spec=wrapper,
                            target=target,
                            reason_code=expected_reason,
                        )
                    )
            except ValueError as error:
                raise RunStoreError(
                    "Reviewed calculator replay cannot be reconstructed"
                ) from error
            result_expectations.append(
                {
                    "metric_id": metric_id,
                    "scope_key": target["scope_key"],
                    "result": expected_result,
                    "trace": expected_trace,
                }
            )
    for trace in traces.values():
        if trace["execution_semantics_hash"] != manifest[
            "execution_semantics_hash"
        ]:
            raise RunStoreError("ExecutionTrace semantics differ from Run")
        metric_id = str(trace["metric_id"])
        if metric_id not in compiled_specs:
            raise RunStoreError("ExecutionTrace MetricSpec is absent")
        if trace["spec_closure_hash"] != compiled_specs[metric_id][
            "spec_closure_hash"
        ]:
            raise RunStoreError("ExecutionTrace Spec closure differs")
        missing = set(trace["input_observation_ids"]) - set(observations)
        if missing:
            raise RunStoreError("ExecutionTrace input observation is absent")
        try:
            verify_trace_observation_values(
                trace=trace, observations=observations,
            )
        except ConstraintError as error:
            raise RunStoreError(str(error)) from error
    for record in records:
        if record["record_type"] == "METRIC_RESULT":
            if record["trace_id"] not in traces:
                raise RunStoreError("MetricResult ExecutionTrace is absent")
            trace = traces[str(record["trace_id"])]
            if trace["metric_id"] != record["metric_id"]:
                raise RunStoreError("MetricResult Trace metric differs")
            calculation_target = trace["calculation_target"]
            if (
                calculation_target["company_id"] != record["company_id"]
                or calculation_target["period_start"]
                != record["period_start"]
                or calculation_target["period_end"] != record["period_end"]
                or calculation_target["scope_key"] != record["scope_key"]
            ):
                raise RunStoreError(
                    "MetricResult calculation target differs from Trace"
                )
            if trace["result"] != record["value"]:
                raise RunStoreError("MetricResult Trace value differs")
            if trace["quality"] != record["quality"]:
                raise RunStoreError("MetricResult Trace quality differs")
            if record["publication"] == "WITHHELD":
                withheld_steps = [
                    step
                    for step in trace["steps"]
                    if step["event"] == "WITHHELD"
                ]
                if (
                    len(withheld_steps) != 1
                    or set(withheld_steps[0]) != {"event", "reason_code"}
                    or withheld_steps[0]["reason_code"]
                    != record["reason_code"]
                ):
                    raise RunStoreError(
                        "WITHHELD Result reason differs from Trace"
                    )
            if record["applicability"] == "N_A_STRUCTURAL" and (
                trace["input_observation_ids"]
                or trace["steps"] != [{"event": "N_A_STRUCTURAL"}]
            ):
                raise RunStoreError(
                    "Structural Result state differs from Trace"
                )
            if (
                record["quality"] == "NOT_MEANINGFUL"
                and (
                    not trace["input_observation_ids"]
                    or any(
                        step["event"] == "WITHHELD"
                        for step in trace["steps"]
                    )
                )
            ):
                raise RunStoreError(
                    "NOT_MEANINGFUL Result lacks evaluated inputs"
                )
            if trace["result_contract_hash"] != metric_result_contract_hash(
                result=record,
            ):
                raise RunStoreError("MetricResult Trace contract differs")
            if record["company_id"] != manifest["company_id"]:
                raise RunStoreError("MetricResult company differs from Run")
            input_scope_keys = {
                observations[str(observation_id)]["scope_key"]
                for observation_id in trace["input_observation_ids"]
            }
            if input_scope_keys and input_scope_keys != {
                record["scope_key"]
            }:
                raise RunStoreError(
                    "MetricResult scope differs from input observations"
                )
            if record["value"] is not None:
                expected_quality = _expected_numeric_result_quality(
                    trace=trace, observations=observations,
                )
                if record["quality"] != expected_quality:
                    raise RunStoreError(
                        "MetricResult quality differs from inputs/Spec branch"
                    )
            if (
                record["period_start"]
                != manifest["target_period"]["period_start"]
                or record["period_end"]
                != manifest["target_period"]["period_end"]
            ):
                raise RunStoreError("MetricResult period differs from Run")
            metric_id = str(record["metric_id"])
            if metric_id not in compiled_specs:
                raise RunStoreError("MetricResult MetricSpec is absent")
            wrapper = compiled_specs[metric_id]
            if record["spec_closure_hash"] != wrapper["spec_closure_hash"]:
                raise RunStoreError("MetricResult Spec closure differs")
            expected_applicability = (
                "APPLICABLE"
                if metric_is_applicable(
                    applicability=wrapper["compiled"]["applicability"],
                    traits=list(manifest["company_traits"]),
                )
                else "N_A_STRUCTURAL"
            )
            if record["applicability"] != expected_applicability:
                raise RunStoreError(
                    "MetricResult applicability differs from Spec/traits"
                )
            if record["value"] is not None:
                semantic = wrapper["compiled"]
                if semantic["unit_policy"] == "fixed_canonical":
                    if record["unit"] != semantic["canonical_unit"]:
                        raise RunStoreError(
                            "MetricResult unit differs from Spec"
                        )
                else:
                    input_units = {
                        observations[str(observation_id)]["unit"]
                        for observation_id in trace["input_observation_ids"]
                        if observations[str(observation_id)]["metric_id"]
                        == metric_id
                    }
                    if input_units != {record["unit"]}:
                        raise RunStoreError(
                            "MetricResult reported unit differs from input"
                        )
    for expected in result_expectations:
        matches = [
            result
            for result in results.values()
            if result["metric_id"] == expected["metric_id"]
            and result["company_id"] == manifest["company_id"]
            and result["period_start"]
            == manifest["target_period"]["period_start"]
            and result["period_end"]
            == manifest["target_period"]["period_end"]
            and result["scope_key"] == expected["scope_key"]
        ]
        if len(matches) != 1:
            raise RunStoreError("Reviewed Result exact set differs")
        result = matches[0]
        trace = traces[str(result["trace_id"])]
        if result != expected["result"] or trace != expected["trace"]:
            raise RunStoreError(
                "Result/Trace differs from reviewed calculator replay"
            )
    for result in results.values():
        metric_id = str(result["metric_id"])
        wrapper = compiled_specs[metric_id]
        if wrapper["compiled"]["source_mode"] not in {
            "structured",
            "structured_and_derived",
        }:
            continue
        _replay_structured_result(
            manifest=manifest,
            result=result,
            trace=traces[str(result["trace_id"])],
            compiled_spec=wrapper,
            compiled_specs=compiled_specs,
            observations=observations,
            source_references=source_references,
            raw_bytes_by_id=raw_bytes_by_id,
            company_ciks=company_ciks,
        )
    referenced_observation_ids = {
        str(observation_id)
        for trace in traces.values()
        for observation_id in trace["input_observation_ids"]
    }
    if (
        set(observations) - referenced_observation_ids
        != supporting_observation_ids
    ):
        raise RunStoreError("Observation exact consumption set differs")
    for candidate in candidates.values():
        if set(candidate["source_reference_ids"]) - source_ids:
            raise RunStoreError("Candidate SourceReference is absent")
        if set(candidate["derived_asset_ids"]) - derived_ids:
            raise RunStoreError("Candidate DerivedAsset is absent")
        attempt_id = str(candidate["attempt_id"])
        if attempt_id not in attempts:
            raise RunStoreError("Candidate AI attempt is absent")
        attempt = attempts[attempt_id]
        if attempt["status"] != "SUCCEEDED" or attempt[
            "assistant_output_sha256"
        ] != candidate["assistant_output_sha256"]:
            raise RunStoreError("Candidate AI attempt binding differs")
        attempt_context = attempt_contexts[attempt_id]
        reader_manifest = attempt_context["reader_manifest"]
        if (
            candidate["derived_asset_ids"]
            != [reader_manifest["derived_asset_id"]]
            or candidate["source_reference_ids"]
            != reader_manifest["source_reference_ids"]
        ):
            raise RunStoreError("Candidate ReaderInputManifest differs")
        task_spec = attempt_context["task_spec"]
        if candidate["disclosure_group"] != task_spec["compiled"][
            "disclosure_group"
        ]:
            raise RunStoreError("Candidate task Spec differs")
        payload = attempt_context["payload"]
        replayed_candidate = replayed_attempt_candidates[attempt_id]
        if replayed_candidate != candidate:
            raise RunStoreError("Candidate differs from raw AI response bytes")
        candidate_manifests[str(candidate["candidate_hash"])] = (
            reader_manifest
        )
        candidate_payload_bodies[str(candidate["candidate_hash"])] = payload[
            "body"
        ]
    for evidence in evidence_checks.values():
        if evidence["candidate_hash"] not in candidates:
            raise RunStoreError("EvidenceCheck Candidate is absent")
        candidate = candidates[str(evidence["candidate_hash"])]
        reader_manifest = candidate_manifests[
            str(candidate["candidate_hash"])
        ]
        derived_asset = derived_assets[
            str(reader_manifest["derived_asset_id"])
        ]
        source_bindings = [
            source_references[str(source_id)]
            for source_id in candidate["source_reference_ids"]
        ]
        reader_payload_body = candidate_payload_bodies[
            str(candidate["candidate_hash"])
        ]
        try:
            replayed_evidence = check_evidence(
                candidate=candidate,
                derived_asset=derived_asset,
                reader_manifest=reader_manifest,
                reader_payload_body=reader_payload_body,
                source_references=source_bindings,
                identity_constraints=evidence["identity_constraints"],
                scope_contract=attempt_contexts[
                    str(candidate["attempt_id"])
                ]["task_contract"]["scope_contract"],
            )
        except ValueError as error:
            raise RunStoreError("EvidenceCheck cannot be replayed") from error
        if replayed_evidence != evidence:
            raise RunStoreError("EvidenceCheck differs from mechanical replay")
    for unit in (
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ):
        evidence_id = str(unit["evidence_check_id"])
        if evidence_id not in evidence_checks:
            raise RunStoreError("ReviewUnit EvidenceCheck is absent")
        candidate_hash = evidence_checks[evidence_id]["candidate_hash"]
        candidate = candidates[str(candidate_hash)]
        if unit["status"] != "PENDING" or evidence_checks[evidence_id][
            "status"
        ] != "PASS":
            raise RunStoreError("ReviewUnit entered from an invalid state")
        for field in (
            "selected",
            "competing_candidates",
            "unresolved_competing_claims",
        ):
            if unit[field] != candidate[field]:
                raise RunStoreError("ReviewUnit Candidate content differs")
        candidate_shard_fields = {
            "examined_table_ids",
            "shard_disposition",
            "table_shard_binding",
        } & set(candidate)
        unit_shard_fields = {
            "examined_table_ids",
            "shard_disposition",
            "table_shard_binding",
        } & set(unit)
        if (
            candidate_shard_fields != unit_shard_fields
            or any(unit[field] != candidate[field]
                   for field in candidate_shard_fields)
        ):
            raise RunStoreError("ReviewUnit Candidate shard binding differs")
        expected_sources = [
            source_references[str(source_id)]
            for source_id in candidate["source_reference_ids"]
        ]
        if unit["source_bindings"] != expected_sources:
            raise RunStoreError("ReviewUnit SourceReference binding differs")
        compiled_spec = unit["compiled_spec"]
        if (
            candidate["disclosure_group"]
            != compiled_spec["disclosure_group"]
            or evidence_checks[evidence_id]["identity_constraints"]
            != compiled_spec["identity_constraints"]
        ):
            raise RunStoreError("ReviewUnit executable Spec binding differs")
        expected_candidate_hashes = [
            content_hash(value=candidate["selected"][role])
            for role in sorted(candidate["selected"])
        ]
        if unit["candidate_hashes"] != expected_candidate_hashes:
            raise RunStoreError("ReviewUnit Candidate hashes differ")
        candidate_derived_ids = candidate["derived_asset_ids"]
        if (
            len(candidate_derived_ids) != 1
            or candidate_derived_ids[0] not in derived_assets
        ):
            raise RunStoreError("ReviewUnit DerivedAsset is ambiguous")
        try:
            context = build_review_context(
                candidate=candidate,
                evidence_check=evidence_checks[evidence_id],
                derived_asset=derived_assets[str(candidate_derived_ids[0])],
                source_bindings=unit["source_bindings"],
                spec_semantic_hash=str(unit["spec_semantic_hash"]),
                required_claims=unit["required_claims"],
            )
            rendered = render_review_markdown(
                review_context=context["review_context"],
            )
        except (RenderError, ValueError) as error:
            raise RunStoreError(
                "ReviewUnit context cannot be reconstructed"
            ) from error
        if (
            context["review_context_hash"] != unit["review_context_hash"]
            or rendered["rendered_review_hash"]
            != unit["rendered_review_hash"]
            or rendered["review_renderer_semantic_version"]
            != unit["review_renderer_semantic_version"]
        ):
            raise RunStoreError("ReviewUnit context differs from records")


def _run_content_and_audit_hashes(
    *,
    manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
    validation: Mapping[str, object],
) -> Tuple[str, str]:
    """Compute stable business-content and complete audit identities.

    Args:
        manifest: RUN record excluding self-referential hash interpretation.
        records: Ordered Run records.
        decisions: Ordered ReviewDecision audit records.
        validation: Terminal or NOT_RUN ValidationReceipt.

    Returns:
        ``(content_manifest_hash, audit_manifest_hash)``.
    """
    content_types = {
        "DETERMINISTIC_VERIFIED_CLAIM",
        "DERIVED_ASSET",
        "EXECUTION_TRACE",
        "METRIC_RESULT",
        "RAW_BLOB",
        "SOURCE_REFERENCE",
        "VERIFIED_OBSERVATION",
    }
    content_records = [
        record for record in records if record["record_type"] in content_types
    ]
    approval_effects = [
        decision["approval_effect_hash"]
        for decision in decisions
        if decision["decision"] == "APPROVE"
    ]
    content_value = {
        "records": content_records,
        "source_references": manifest["source_references"],
        "company_traits": manifest["company_traits"],
        "approval_effect_hashes": approval_effects,
        "spec_file_hashes": manifest["spec_file_hashes"],
        "requirement_hashes": manifest["requirement_hashes"],
        "execution_semantics_hash": manifest["execution_semantics_hash"],
    }
    audit_value = {
        "run_id": manifest["run_id"],
        "company_id": manifest["company_id"],
        "company_traits": manifest["company_traits"],
        "target_period": manifest["target_period"],
        "source_references": manifest["source_references"],
        "missing_required_source_roles": manifest[
            "missing_required_source_roles"
        ],
        "spec_file_hashes": manifest["spec_file_hashes"],
        "requirement_hashes": manifest["requirement_hashes"],
        "execution_semantics_hash": manifest["execution_semantics_hash"],
        "records": list(records),
        "decisions": list(decisions),
        "validation": dict(validation),
    }
    return content_hash(value=content_value), content_hash(value=audit_value)


def _validate_review_bindings(
    *,
    records: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
) -> Dict[str, Mapping[str, object]]:
    """Recompute every decision chain and rendered binding before freeze.

    Args:
        records: Run records.
        decisions: Run decisions.

    Returns:
        Effective HUMAN or authorized SYSTEM decisions keyed by approval-effect
        hash.

    Raises:
        RunStoreError: On detached, parallel, or stale decisions.
    """
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    unit_hashes = {str(unit["review_unit_hash"]) for unit in units}
    foreign = [
        decision
        for decision in decisions
        if decision["review_unit_hash"] not in unit_hashes
    ]
    if foreign:
        raise RunStoreError("Review decisions contain a foreign unit binding")
    effective_decisions: Dict[str, Mapping[str, object]] = {}
    for unit in units:
        bound = [
            decision
            for decision in decisions
            if decision["review_unit_hash"] == unit["review_unit_hash"]
        ]
        if not bound:
            raise RunStoreError("Review unit has no effective decision")
        try:
            effective = effective_review_decision(
                review_unit=unit, decisions=bound,
            )
        except ValueError as error:
            raise RunStoreError(
                "Review binding failed before freeze"
            ) from error
        effect_hash = str(effective["approval_effect_hash"])
        if effect_hash in effective_decisions:
            raise RunStoreError("Decision effect identity is duplicated")
        effective_decisions[effect_hash] = effective
    return effective_decisions


def _validate_formal_result_exact_set(
    *,
    records: Sequence[Mapping[str, object]],
    compiled_specs: Mapping[str, Mapping[str, object]],
) -> None:
    """Require a non-empty terminal result set after graph replay.

    Args:
        records: Mechanically replayed Run records.
        compiled_specs: Exact repository-bound Spec closure used to reject
            results for unknown metrics in the preceding graph replay.

    Raises:
        RunStoreError: When an incomplete attempt-only Run could otherwise be
            caller-labelled PASSED. Per-target and per-review exactness is
            enforced by the graph replay; batch release exactness is enforced
            by BatchManifest validation.
    """
    if not compiled_specs or not any(
        record["record_type"] == "METRIC_RESULT"
        for record in records
    ):
        raise RunStoreError("Formal Run result exact set differs")


def _mechanically_replay_open_run(
    *,
    run_dir: Path,
    repo_root: Path,
    require_complete_results: bool,
) -> Tuple[
    Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]
]:
    """Reapply every repository and record-graph gate to one OPEN Run.

    Args:
        run_dir: OPEN Run root.
        repo_root: Repository carrying exact Requirement, Spec, and source
            bytes.
        require_complete_results: Whether to enforce formal terminal output
            exactness instead of permitting an audit-only incomplete freeze.

    Returns:
        Reloaded manifest, records, and decisions proven by current bytes.
    """
    manifest = _read_manifest(run_dir=run_dir)
    try:
        validate_transition(
            object_type="RUN",
            current_status=str(manifest["status"]),
            target_status="FROZEN",
        )
    except ValueError as error:
        message = "Mechanical validation requires an OPEN Run"
        raise RunStoreError(message) from error
    paths = _run_paths(run_dir=run_dir)
    records = _read_jsonl(path=paths["records"])
    decisions = _read_jsonl(path=paths["decisions"])
    effective_decisions = _validate_review_bindings(
        records=records, decisions=decisions,
    )
    review_units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    _verify_review_assets(run_dir=run_dir, review_units=review_units)
    compiled_specs, raw_bytes_by_id, company_ciks, requirement = (
        _verify_repository_bindings(
            repo_root=repo_root,
            run_dir=run_dir,
            manifest=manifest,
            records=records,
        )
    )
    _validate_record_graph(
        repo_root=repo_root,
        run_dir=run_dir,
        manifest=manifest,
        records=records,
        effective_decisions=effective_decisions,
        compiled_specs=compiled_specs,
        raw_bytes_by_id=raw_bytes_by_id,
        company_ciks=company_ciks,
        requirement=requirement,
    )
    if require_complete_results:
        _validate_formal_result_exact_set(
            records=records, compiled_specs=compiled_specs,
        )
    if manifest["execution_semantics_hash"] != execution_semantics_hash():
        raise RunStoreError("Run semantic runtime changed before freeze")
    return manifest, records, decisions


def validate_run(*, run_dir: Path, repo_root: Path) -> Dict[str, object]:
    """Mechanically validate one complete OPEN Run and issue PASSED.

    Args:
        run_dir: Complete OPEN Run root.
        repo_root: Repository carrying exact frozen authority bytes.

    Returns:
        Content-bound PASSED ValidationReceipt derived without caller status
        or caller-authored checks.
    """
    manifest, _records, _decisions = _mechanically_replay_open_run(
        run_dir=run_dir,
        repo_root=repo_root,
        require_complete_results=True,
    )
    paths = _run_paths(run_dir=run_dir)
    current_payload = strict_json_file(path=paths["validation"])
    if not isinstance(current_payload, dict):
        raise RunStoreError("Run validation root must be an object")
    current = validate_record(record=current_payload)
    checks = [
        {"check": check, "status": "PASS"}
        for check in FORMAL_RUN_VALIDATION_CHECKS
    ]
    if current["status"] == "PASSED":
        if current["checks"] != checks:
            raise RunStoreError("PASSED Run validation checks differ")
        _verify_run_validation_receipt(
            run_dir=run_dir, manifest=manifest, receipt=current,
        )
        return current
    if current["status"] != "NOT_RUN":
        raise RunStoreError("Failed Run cannot be re-labelled PASSED")
    return _write_validation_receipt(
        run_dir=run_dir, status="PASSED", checks=checks,
    )


def validate_and_freeze_run(
    *, run_dir: Path, repo_root: Path
) -> Dict[str, object]:
    """Validate complete current bytes and atomically freeze their receipt.

    Args:
        run_dir: Complete OPEN Run root.
        repo_root: Repository carrying exact frozen authority bytes.

    Returns:
        FROZEN manifest bound to the mechanically issued PASSED receipt.
    """
    validate_run(run_dir=run_dir, repo_root=repo_root)
    return freeze_run(run_dir=run_dir, repo_root=repo_root)


def freeze_run(*, run_dir: Path, repo_root: Path) -> Dict[str, object]:
    """Revalidate disk bytes and atomically freeze one Run.

    Args:
        run_dir: OPEN Run root.
        repo_root: Repository used to revalidate raw source and Spec bytes.

    Returns:
        FROZEN manifest.

    Raises:
        RunStoreError: On file/hash drift, invalid review chain, unresolved
            source role, or invalid record graph. A NOT_RUN/FAILED validation
            receipt and WITHHELD metric results may freeze for audit/replay,
            but publication rejects them.
    """
    manifest, records, decisions = _mechanically_replay_open_run(
        run_dir=run_dir,
        repo_root=repo_root,
        require_complete_results=False,
    )
    paths = _run_paths(run_dir=run_dir)
    validation_payload = strict_json_file(path=paths["validation"])
    if not isinstance(validation_payload, dict):
        raise RunStoreError("Run validation root must be an object")
    validation = validate_record(record=validation_payload)
    if validation["status"] not in FREEZEABLE_VALIDATION_STATUSES:
        raise RunStoreError("Run validation status is invalid")
    _verify_run_validation_receipt(
        run_dir=run_dir, manifest=manifest, receipt=validation,
    )
    content_manifest_hash, audit_manifest_hash = _run_content_and_audit_hashes(
        manifest=manifest,
        records=records,
        decisions=decisions,
        validation=validation,
    )
    frozen = dict(manifest)
    frozen.update(
        {
            "status": "FROZEN",
            "records_file_hash": sha256_file(path=paths["records"]),
            "review_decisions_file_hash": sha256_file(path=paths["decisions"]),
            "validation_file_hash": sha256_file(path=paths["validation"]),
            "content_manifest_hash": content_manifest_hash,
            "audit_manifest_hash": audit_manifest_hash,
        }
    )
    validate_record(record=frozen)
    atomic_write_json(path=paths["manifest"], value=frozen)
    return _read_manifest(run_dir=run_dir)


def fail_run(*, run_dir: Path) -> Dict[str, object]:
    """Seal one incomplete OPEN Run as FAILED audit evidence.

    Args:
        run_dir: OPEN Run whose validation receipt already records FAILED.

    Returns:
        Immutable FAILED manifest bound to current records and decisions.

    Raises:
        RunStoreError: When the transition or FAILED receipt is invalid.
    """
    manifest = _read_manifest(run_dir=run_dir)
    validate_transition(
        object_type="RUN",
        current_status=str(manifest["status"]),
        target_status="FAILED",
    )
    paths = _run_paths(run_dir=run_dir)
    records = _read_jsonl(path=paths["records"])
    decisions = _read_jsonl(path=paths["decisions"])
    validation_payload = strict_json_file(path=paths["validation"])
    if not isinstance(validation_payload, dict):
        raise RunStoreError("Failed Run validation root must be an object")
    validation = validate_record(record=validation_payload)
    if validation["status"] != "FAILED":
        raise RunStoreError("FAILED Run requires a FAILED validation receipt")
    _verify_run_validation_receipt(
        run_dir=run_dir, manifest=manifest, receipt=validation,
    )
    content_hash_value, audit_hash_value = _run_content_and_audit_hashes(
        manifest=manifest,
        records=records,
        decisions=decisions,
        validation=validation,
    )
    failed = dict(manifest)
    failed.update(
        {
            "status": "FAILED",
            "records_file_hash": sha256_file(path=paths["records"]),
            "review_decisions_file_hash": sha256_file(
                path=paths["decisions"]
            ),
            "validation_file_hash": sha256_file(path=paths["validation"]),
            "content_manifest_hash": content_hash_value,
            "audit_manifest_hash": audit_hash_value,
        }
    )
    validate_record(record=failed)
    atomic_write_json(path=paths["manifest"], value=failed)
    return _read_manifest(run_dir=run_dir)


def load_failed_run(
    *, run_dir: Path
) -> Tuple[
    Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]
]:
    """Load one immutable FAILED Run for status reporting.

    Args:
        run_dir: FAILED Run root.

    Returns:
        Manifest, records, and review decisions with all local hashes checked.

    Raises:
        RunStoreError: On state, file, receipt, or terminal hash drift.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "FAILED":
        raise RunStoreError("Failed-run loader requires FAILED state")
    paths = _run_paths(run_dir=run_dir)
    expected = {
        "records_file_hash": sha256_file(path=paths["records"]),
        "review_decisions_file_hash": sha256_file(path=paths["decisions"]),
        "validation_file_hash": sha256_file(path=paths["validation"]),
    }
    if any(manifest[field] != expected[field] for field in expected):
        raise RunStoreError("FAILED Run file hash differs")
    records = _read_jsonl(path=paths["records"])
    decisions = _read_jsonl(path=paths["decisions"])
    validation_payload = strict_json_file(path=paths["validation"])
    if not isinstance(validation_payload, dict):
        raise RunStoreError("Failed Run validation root must be an object")
    validation = validate_record(record=validation_payload)
    if validation["status"] != "FAILED":
        raise RunStoreError("FAILED Run receipt state differs")
    _verify_run_validation_receipt(
        run_dir=run_dir, manifest=manifest, receipt=validation,
    )
    expected_content, expected_audit = _run_content_and_audit_hashes(
        manifest=manifest,
        records=records,
        decisions=decisions,
        validation=validation,
    )
    if (
        manifest["content_manifest_hash"] != expected_content
        or manifest["audit_manifest_hash"] != expected_audit
    ):
        raise RunStoreError("FAILED Run terminal manifest hash differs")
    return manifest, records, decisions


def load_frozen_run(
    *, run_dir: Path, repo_root: Path
) -> Tuple[
    Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]
]:
    """Load and hash-verify one FROZEN Run for offline replay.

    Args:
        run_dir: Frozen Run root.
        repo_root: Repository containing exact frozen source/Spec bytes.

    Returns:
        Manifest, records, and decisions.

    Raises:
        RunStoreError: On non-frozen state or any file hash mismatch.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] != "FROZEN":
        raise RunStoreError("Replay requires a FROZEN Run")
    paths = _run_paths(run_dir=run_dir)
    expected = {
        "records_file_hash": sha256_file(path=paths["records"]),
        "review_decisions_file_hash": sha256_file(path=paths["decisions"]),
        "validation_file_hash": sha256_file(path=paths["validation"]),
    }
    for key in expected:
        if manifest[key] != expected[key]:
            raise RunStoreError(
                "Frozen Run file hash mismatch: {}".format(key)
            )
    records = _read_jsonl(path=paths["records"])
    decisions = _read_jsonl(path=paths["decisions"])
    effective_decisions = _validate_review_bindings(
        records=records, decisions=decisions,
    )
    review_units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    _verify_review_assets(run_dir=run_dir, review_units=review_units)
    compiled_specs, raw_bytes_by_id, company_ciks, requirement = (
        _verify_repository_bindings(
            repo_root=repo_root,
            run_dir=run_dir,
            manifest=manifest,
            records=records,
        )
    )
    _validate_record_graph(
        repo_root=repo_root,
        run_dir=run_dir,
        manifest=manifest,
        records=records,
        effective_decisions=effective_decisions,
        compiled_specs=compiled_specs,
        raw_bytes_by_id=raw_bytes_by_id,
        company_ciks=company_ciks,
        requirement=requirement,
    )
    if manifest["execution_semantics_hash"] != execution_semantics_hash():
        raise RunStoreError("Frozen Run semantic runtime differs")
    validation_payload = strict_json_file(path=paths["validation"])
    if not isinstance(validation_payload, dict):
        raise RunStoreError("Frozen validation root must be an object")
    validation = validate_record(record=validation_payload)
    _verify_run_validation_receipt(
        run_dir=run_dir, manifest=manifest, receipt=validation,
    )
    content_manifest_hash, audit_manifest_hash = _run_content_and_audit_hashes(
        manifest=manifest,
        records=records,
        decisions=decisions,
        validation=validation,
    )
    if manifest["content_manifest_hash"] != content_manifest_hash:
        raise RunStoreError("Frozen Run content manifest hash differs")
    if manifest["audit_manifest_hash"] != audit_manifest_hash:
        raise RunStoreError("Frozen Run audit manifest hash differs")
    return manifest, records, decisions


def load_run_for_status(
    *, run_dir: Path, repo_root: Path
) -> Tuple[
    Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]
]:
    """Load a persisted Run through the verifier for its actual state.

    Args:
        run_dir: Stable latest-Run locator.
        repo_root: Repository required for full FROZEN replay.

    Returns:
        Verified manifest, records, and decisions for OPEN, FAILED, or FROZEN.
    """
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["status"] == "OPEN":
        return load_open_run(run_dir=run_dir)
    if manifest["status"] == "FAILED":
        return load_failed_run(run_dir=run_dir)
    if manifest["status"] == "FROZEN":
        return load_frozen_run(run_dir=run_dir, repo_root=repo_root)
    raise RunStoreError("Run status is not loadable")
