"""Bind the formal Cutover to real-layout and post-freeze evidence.

``write_production_freeze_receipt`` records the exact production semantic
tree before an independent holdout is added. The validation entrypoint then
reads only the module-owned qualification manifest, verifies its
content-addressed receipts and persisted FROZEN Runs, and returns their exact
identities to the Cutover receipt.  Missing evidence is a stable blocker; this
module never creates a synthetic layout PASS.
"""

from __future__ import annotations

import csv
import fcntl
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

from sec_http import parse_request_log_rows, request_log_attempt_id
from validation_provenance import ValidationProvenanceError

from .ai_adapter import AIAdapterError, approved_transport_policy
from .ai_adapter import TransportObservation
from .ai_adapter import transport_observation_mismatch
from .ai_adapter import build_invocation_controlled_transport_adapter
from .batch_workflow import BatchWorkflowError, validate_request_attempt_binding
from .canonical import atomic_write_bytes, atomic_write_json, canonical_json_bytes
from .canonical import content_hash, parse_utc_timestamp, sha256_bytes, sha256_file
from .invocation_control import InvocationControlError
from .invocation_control import qualification_remote_egress_terminals
from .canonical import strict_json_file, strict_json_loads
from .requirements import load_requirement_snapshot
from .records import RecordError, validate_record, validate_run_coordinates
from .review import effective_review_decision
from .run_store import load_run_for_status, RunStoreError
from .stage_a_snapshot import StageASnapshotError, validate_stage_a_snapshot
from .table_grid import TableGridError, resolve_cell
from .table_payload import TABLE_PAYLOAD_SERIALIZATION_VERSION
from .table_qualification_freeze import TableQualificationFreezeError
from .table_qualification_freeze import FREEZE_CYCLE_ROOT
from .table_qualification_freeze import load_table_qualification_matrix
from .table_qualification_freeze import require_table_qualification_freeze
from .table_task_contracts import load_table_task_contracts
from .table_task_contracts import resolve_table_task_contract
from .table_task_contracts import TableTaskContractError


QUALIFICATION_ROOT = Path("artifacts/vnext/qualification")
QUALIFICATION_MANIFEST = QUALIFICATION_ROOT / "manifest.json"
LAYOUT_REFERENCE_INDEX = Path(
    "fixtures/vnext/recorded/layout_reference.json"
)
LAYOUT_FIXTURE_ROOT = Path("fixtures/vnext/layouts")
QUALIFICATION_RUN_ROOT = QUALIFICATION_ROOT / "runs"
TABLE_QUALIFICATION_CYCLE_ROOT = QUALIFICATION_ROOT / "cycles"
LAYOUT_FIXTURE_FIELDS = frozenset({
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
})
SEMANTIC_DIRECTORIES = (
    Path("scripts"),
    Path("catalog"),
    Path("config"),
    Path("tools"),
)
SEMANTIC_FILES = (
    Path("requirements/ai_first_v3_3_1/FSD.md"),
    Path("requirements/ai_first_v3_3_1/ISSUE_CONTRACT.md"),
    Path("requirements/ai_first_v3_3_1/ISSUE_CONTRACT_R3_ADDENDUM.md"),
    Path("requirements/ai_first_v3_3_1/baseline_manifest.json"),
    Path("requirements/ai_first_v3_3_1/decision_register.json"),
)
LAYOUT_DIFFERENCE_KINDS = {
    "column_order",
    "rowspan_colspan",
    "scope_wording",
    "table_header",
    "year_layout",
}
_SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_ACCESSION = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
_RESET_REASON = re.compile(r"^[A-Z][A-Z0-9_]{2,80}$")
_SEC_ARCHIVE_SOURCE = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/"
    r"([0-9]{1,10})/([0-9]{18})/([^/?#]+)$"
)
_QUALIFICATION_AUTHORIZATION_CAPABILITY = object()
_QUALIFICATION_AUTHORIZATION_FIELDS = {
    "api",
    "catalog_task_contract_hash",
    "family_id",
    "freeze_receipt_id",
    "matrix_entry_hash",
    "model",
    "output_schema_hash",
    "provider",
    "qualification_authorization_id",
    "qualification_cycle_id",
    "qualification_ordinal",
    "qualification_provider_ledger_before_row_count",
    "qualification_provider_ledger_before_sha256",
    "qualification_provider_ledger_path",
    "qualification_terminal_id",
    "qualification_task_plan_id",
    "requirement_closure_hash",
    "source_binding",
    "source_binding_hash",
    "source_media_type",
    "system_prompt_hash",
    "table_payload_serialization_version",
    "task_contract_id",
    "task_spec_semantic_hash",
    "target_period",
    "target_period_hash",
    "wb3_workspace_relative_path",
    "run_directory_relative_path",
    "run_id",
}
_SOURCE_BINDING_FIELDS = {
    "request_attempt_id",
    "request_body_sha256",
    "request_body_size",
    "request_headers_repo_relative_path",
    "request_headers_sha256",
    "request_headers_size",
    "request_locator_kind",
    "request_repo_relative_path",
    "source_declaration",
    "source_role",
    "source_url",
    "source_binding_hash",
}
_TARGET_PERIOD_FIELDS = {
    "fiscal_year",
    "period_start",
    "period_end",
}
_PROVIDER_LEDGER_ENTRY_FIELDS = {
    "attempt_id",
    "family_id",
    "freeze_receipt_id",
    "provider_request_id",
    "qualification_authorization",
    "qualification_authorization_id",
    "qualification_cycle_id",
    "qualification_ordinal",
    "qualification_provider_ledger_entry_id",
    "qualification_task_plan_id",
    "record_type",
    "request_body_sha256",
    "run_id",
    "source_binding_hash",
    "task_contract_id",
    "transport_observation",
}
_TERMINAL_RECOVERY_STATES = {
    "NEW",
    "OPEN_BEFORE_EGRESS",
    "EXACT_SUCCESS_NOT_MATERIALIZED",
    "UNKNOWN_REMOTE_OUTCOME",
    "COMPLETE_OPEN_PENDING_REVIEW",
    "FROZEN",
    "FAILED_TERMINAL",
    "DIVERGENT",
}


class QualificationError(RuntimeError):
    """Report one stable formal-Cutover qualification failure."""

    def __init__(self, *, code: str, message: str) -> None:
        """Create a qualification error whose code is visible to operators.

        Args:
            code: Stable uppercase machine code.
            message: Concise failure explanation without sensitive values.
        """
        super().__init__("{}: {}".format(code, message))
        self.code = code


@dataclass(frozen=True, init=False)
class TableQualificationAuthorization:
    """Carry one module-issued, repository-revalidated LIVE task authority.

    The object deliberately cannot be constructed with a public constructor.
    Its private marker is only a first boundary: every use also rebuilds the
    same binding from the current matrix, freeze, Stage-A snapshot, source,
    task catalog, Requirement, and provider policy.
    """

    _binding: Dict[str, object]
    _capability: object

    def __init__(
        self, *, binding: Mapping[str, object], capability: object,
    ) -> None:
        """Create an opaque authorization only for this module's issuer."""
        if capability is not _QUALIFICATION_AUTHORIZATION_CAPABILITY:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_REQUIRED",
                message="Table qualification authorization is module-owned",
            )
        object.__setattr__(self, "_binding", _copy_authorization_binding(
            value=binding,
        ))
        object.__setattr__(self, "_capability", capability)

    def as_mapping(self) -> Dict[str, object]:
        """Return an isolated copy suitable for persisted audit records."""
        return _copy_authorization_binding(value=self._binding)


def _copy_authorization_binding(*, value: Mapping[str, object]) -> Dict[str, object]:
    """Copy one nested authorization mapping without sharing mutable state."""
    copied = dict(value)
    source = copied.get("source_binding")
    if isinstance(source, Mapping):
        copied_source = dict(source)
        declaration = copied_source.get("source_declaration")
        if isinstance(declaration, Mapping):
            copied_source["source_declaration"] = dict(declaration)
        copied["source_binding"] = copied_source
    return copied


def _text(*, value: object, label: str) -> str:
    """Return one non-empty string or raise a stable authorization error."""
    if type(value) is not str or not value:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="{} is invalid".format(label),
        )
    return value


def _target_period_mapping(*, value: object) -> Dict[str, object]:
    """Return one exact, valid qualification target-period mapping.

    The matrix owns this coordinate for an immutable development source.  A
    future caller may repeat it to the executor, but cannot widen or replace
    it with another fiscal-year range.
    """
    if type(value) is not dict or set(value) != _TARGET_PERIOD_FIELDS:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification target period fields are invalid",
        )
    try:
        validate_run_coordinates(
            target_period=value,
            company_traits=[],
        )
    except RecordError as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification target period is invalid",
        ) from error
    return dict(value)


def _source_media_type(*, value: object) -> str:
    """Return the one source media type declared by the qualification matrix."""
    media_type = _text(value=value, label="qualification source media type")
    if media_type != "text/html":
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification source media type is unsupported",
        )
    return media_type


def _source_url_from_declaration(*, declaration: Mapping[str, object]) -> str:
    """Derive the only allowed SEC Archives URL from matrix source identity."""
    cik = _text(value=declaration["cik"], label="source CIK")
    accession = _text(value=declaration["accession"], label="source accession")
    document_name = _text(
        value=declaration["document_name"], label="source document",
    )
    if not cik.isdigit() or not _ACCESSION.fullmatch(accession):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix source filing identity is invalid",
        )
    return (
        "https://www.sec.gov/Archives/edgar/data/{}/{}{}".format(
            str(int(cik)),
            accession.replace("-", ""),
            "/" + document_name,
        )
    )


def _matrix_source_binding(
    *, repo_root: Path, matrix_entry: Mapping[str, object],
) -> Dict[str, object]:
    """Rebuild one matrix-owned immutable SEC source and ledger binding."""
    declaration = matrix_entry.get("development_source")
    required = {
        "accession",
        "cik",
        "company_id",
        "document_name",
        "source_kind",
        "source_repo_relative_path",
        "source_sha256",
    }
    if type(declaration) is not dict or set(declaration) != required:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source fields are invalid",
        )
    source = dict(declaration)
    if source["source_kind"] != "IMMUTABLE_ATTEMPT":
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source is not immutable",
        )
    for label, field in (
        ("source company", "company_id"),
        ("source path", "source_repo_relative_path"),
        ("source digest", "source_sha256"),
    ):
        _text(value=source[field], label=label)
    relative = Path(str(source["source_repo_relative_path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source path is unsafe",
        )
    source_path = repo_root / relative
    if source_path.is_symlink() or not source_path.is_file():
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source bytes are absent",
        )
    if sha256_file(path=source_path) != source["source_sha256"]:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source bytes differ",
        )
    source_url = _source_url_from_declaration(declaration=source)
    try:
        rows = parse_request_log_rows(
            text=(repo_root / "evidence/requests_log.csv").read_text(
                encoding="utf-8",
            )
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Request ledger is unavailable",
        ) from error
    matches = [
        (index, row)
        for index, row in enumerate(rows)
        if row["source_url"] == source_url
        and row["content_sha256"] == source["source_sha256"]
        and row["accession"] == source["accession"]
        and row["document_name"] == source["document_name"]
        and row["repo_relative_path"]
        == source["source_repo_relative_path"]
        and row["headers_repo_relative_path"].startswith(
            "evidence/request_attempts/"
        )
    ]
    if len(matches) != 1:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source ledger binding is ambiguous",
        )
    index, row = matches[0]
    request_attempt_id = request_log_attempt_id(row_index=index, row=row)
    try:
        proof = validate_request_attempt_binding(
            repo_root=repo_root,
            source_url=source_url,
            content_sha256=str(source["source_sha256"]),
            accession=str(source["accession"]),
            document_name=str(source["document_name"]),
            request_attempt_id=request_attempt_id,
            require_immutable=True,
        )
    except BatchWorkflowError as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source ledger proof differs",
        ) from error
    if proof["request_repo_relative_path"] != source[
        "source_repo_relative_path"
    ]:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Matrix development source locator differs",
        )
    body = {
        "source_declaration": source,
        "source_url": source_url,
        "source_role": "target_primary",
        **proof,
    }
    return {
        **body,
        "source_binding_hash": content_hash(value=body),
    }


def _qualification_workspace_relative_path(*, cycle_id: str) -> str:
    """Derive the only WB-3 workspace allowed for one qualification cycle."""
    if not _SHA256_ID.fullmatch(cycle_id):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification cycle identity is invalid",
        )
    return (
        TABLE_QUALIFICATION_CYCLE_ROOT
        / cycle_id.split(":", maxsplit=1)[1]
        / "invocation_control"
    ).as_posix()


def _authorization_mapping(
    *, repo_root: Path, family_id: str, task_contract_id: str,
    qualification_ordinal: int,
) -> Dict[str, object]:
    """Mechanically rebuild every current authority field for one LIVE task."""
    plan = table_qualification_task_plan(
        repo_root=repo_root,
        family_id=family_id,
        task_contract_id=task_contract_id,
        qualification_ordinal=qualification_ordinal,
        include_freeze_status=True,
    )
    try:
        freeze = plan["_freeze_status"]
        if type(freeze) is not dict:
            raise ValueError("Qualification freeze status is invalid")
        snapshot = validate_stage_a_snapshot(repo_root=repo_root)
        contracts = load_table_task_contracts(repo_root=repo_root)
        runtime = resolve_table_task_contract(
            repo_root=repo_root,
            task_contract_id=task_contract_id,
        )
        requirement = load_requirement_snapshot(
            snapshot_dir=repo_root / "requirements/issue_15_v1",
        )
    except (StageASnapshotError, TableQualificationFreezeError,
            TableTaskContractError, ValidationProvenanceError, ValueError) as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Current qualification authority cannot be rebuilt",
        ) from error
    if (
        plan["freeze_receipt_id"] != freeze["receipt_id"]
        or snapshot["freeze_receipt_id"] != freeze["receipt_id"]
        or runtime["reader_family_id"] != family_id
        or contracts["requirement_closure_hash"]
        != requirement["requirement_closure_hash"]
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification authority closure differs",
        )
    matrix = load_table_qualification_matrix(repo_root=repo_root)
    matrix_entry = matrix["entries"].get(family_id)
    if type(matrix_entry) is not dict:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification matrix family is absent",
        )
    source_binding = _matrix_source_binding(
        repo_root=repo_root,
        matrix_entry=matrix_entry,
    )
    target_period = _target_period_mapping(
        value=matrix_entry.get("target_period"),
    )
    source_media_type = _source_media_type(
        value=matrix_entry.get("source_media_type"),
    )
    ledger_before = freeze.get("provider_ledger_before")
    if (
        type(ledger_before) is not dict
        or set(ledger_before) != {"path", "row_count", "sha256"}
        or type(ledger_before["row_count"]) is not int
        or ledger_before["row_count"] < 0
        or type(ledger_before["sha256"]) is not str
        or _SHA256_HEX.fullmatch(ledger_before["sha256"]) is None
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger baseline is invalid",
        )
    policy = approved_transport_policy(requirement=requirement)
    terminal_body = {
        "qualification_task_plan_id": plan["qualification_task_plan_id"],
        "qualification_cycle_id": freeze["qualification_cycle_id"],
        "family_id": family_id,
        "task_contract_id": task_contract_id,
        "qualification_ordinal": qualification_ordinal,
        "source_binding_hash": source_binding["source_binding_hash"],
        "target_period": target_period,
        "source_media_type": source_media_type,
    }
    qualification_terminal_id = content_hash(value=terminal_body)
    terminal_digest = qualification_terminal_id.split(":", maxsplit=1)[1]
    body = {
        "qualification_task_plan_id": plan["qualification_task_plan_id"],
        "qualification_cycle_id": freeze["qualification_cycle_id"],
        "freeze_receipt_id": freeze["receipt_id"],
        "family_id": family_id,
        "task_contract_id": task_contract_id,
        "qualification_ordinal": qualification_ordinal,
        "matrix_entry_hash": plan["matrix_entry_hash"],
        "catalog_task_contract_hash": runtime["catalog_task_contract_hash"],
        "task_spec_semantic_hash": runtime["task_spec_semantic_hash"],
        "output_schema_hash": runtime["output_schema_hash"],
        "system_prompt_hash": runtime["system_prompt_hash"],
        "source_binding": source_binding,
        "source_binding_hash": source_binding["source_binding_hash"],
        "target_period": target_period,
        "target_period_hash": content_hash(value=target_period),
        "source_media_type": source_media_type,
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "table_payload_serialization_version": (
            TABLE_PAYLOAD_SERIALIZATION_VERSION
        ),
        "provider": policy.provider,
        "model": policy.model,
        "api": policy.api,
        "wb3_workspace_relative_path": (
            _qualification_workspace_relative_path(
                cycle_id=str(freeze["qualification_cycle_id"]),
            )
        ),
        "qualification_provider_ledger_path": ledger_before["path"],
        "qualification_provider_ledger_before_sha256": ledger_before["sha256"],
        "qualification_provider_ledger_before_row_count": ledger_before[
            "row_count"
        ],
        "qualification_terminal_id": qualification_terminal_id,
        "run_id": "run:qualification:table:" + terminal_digest,
        "run_directory_relative_path": (
            TABLE_QUALIFICATION_CYCLE_ROOT
            / str(freeze["qualification_cycle_id"]).split(
                ":", maxsplit=1,
            )[1]
            / "runs"
            / terminal_digest
        ).as_posix(),
    }
    return {
        **body,
        "qualification_authorization_id": content_hash(value=body),
    }


def issue_table_qualification_authorization(
    *, repo_root: Path, family_id: str, task_contract_id: str,
    qualification_ordinal: int,
) -> TableQualificationAuthorization:
    """Issue one opaque authorization only after all current gates revalidate.

    This is intentionally the sole constructor for an authorization consumed
    by a LIVE catalog Workflow.  The current Stage-A D-07 state therefore
    rejects here before any source parsing, reservation, or transport call.
    """
    binding = _authorization_mapping(
        repo_root=repo_root,
        family_id=family_id,
        task_contract_id=task_contract_id,
        qualification_ordinal=qualification_ordinal,
    )
    return TableQualificationAuthorization(
        binding=binding,
        capability=_QUALIFICATION_AUTHORIZATION_CAPABILITY,
    )


def _rebuild_authorization_binding(
    *, repo_root: Path, actual: object,
) -> Dict[str, object]:
    """Rebuild a persisted authorization without trusting copied fields."""
    if type(actual) is not dict or set(actual) != _QUALIFICATION_AUTHORIZATION_FIELDS:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification authorization fields differ",
        )
    family_id = _text(value=actual["family_id"], label="authorization family")
    task_contract_id = _text(
        value=actual["task_contract_id"], label="authorization task",
    )
    ordinal = actual["qualification_ordinal"]
    if type(ordinal) is not int:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification authorization ordinal is invalid",
        )
    fresh = _authorization_mapping(
        repo_root=repo_root,
        family_id=family_id,
        task_contract_id=task_contract_id,
        qualification_ordinal=ordinal,
    )
    if actual != fresh:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification authorization differs from repository",
        )
    return fresh


def validate_live_table_qualification_authorization(
    *, repo_root: Path, authorization: object, task_contract_id: str,
    run_dir: Path, run_id: str, company_id: str,
    target_period: Mapping[str, object], source_repo_relative_path: str,
    source_media_type: str, source_url: str, accession: str,
    document_name: str, source_role: str, request_attempt_id: str,
    adapter: object,
) -> Dict[str, object]:
    """Rebuild and compare the sole authorization before LIVE table execution."""
    if (
        type(authorization) is not TableQualificationAuthorization
        or authorization._capability is not _QUALIFICATION_AUTHORIZATION_CAPABILITY
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_REQUIRED",
            message="LIVE catalog task lacks qualification authorization",
        )
    actual = authorization.as_mapping()
    if actual["task_contract_id"] != task_contract_id:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification task differs from Workflow task",
        )
    fresh = _rebuild_authorization_binding(
        repo_root=repo_root,
        actual=actual,
    )
    source = fresh["source_binding"]
    declaration = source["source_declaration"]
    if (
        dict(target_period) != fresh["target_period"]
        or source_media_type != fresh["source_media_type"]
        or run_id != fresh["run_id"]
        or company_id != declaration["company_id"]
        or source_repo_relative_path
        != declaration["source_repo_relative_path"]
        or source_url != source["source_url"]
        or accession != declaration["accession"]
        or document_name != declaration["document_name"]
        or source_role != source["source_role"]
        or request_attempt_id != source["request_attempt_id"]
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Workflow source differs from qualification authority",
        )
    expected_run_dir = (
        repo_root / str(fresh["run_directory_relative_path"])
    ).resolve()
    if run_dir.resolve() != expected_run_dir:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Workflow Run directory differs from qualification authority",
        )
    policy = getattr(adapter, "policy", None)
    context = getattr(adapter, "invocation_context", None)
    if (
        policy is None
        or getattr(policy, "provider", None) != fresh["provider"]
        or getattr(policy, "model", None) != fresh["model"]
        or getattr(policy, "api", None) != fresh["api"]
        or context is None
        or getattr(context, "release_input_plan_id", None)
        != fresh["qualification_task_plan_id"]
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="WB-3 context differs from qualification authority",
        )
    workspace = getattr(context, "workspace_dir", None)
    if not isinstance(workspace, Path):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="WB-3 qualification workspace is invalid",
        )
    expected_workspace = (
        repo_root / str(fresh["wb3_workspace_relative_path"])
    ).resolve()
    if workspace.resolve() != expected_workspace:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="WB-3 workspace differs from qualification cycle",
        )
    return fresh


def _qualification_ledger_path(
    *, repo_root: Path, binding: Mapping[str, object],
) -> Path:
    """Resolve the one freeze-receipt-owned provider ledger for an authority.

    Runtime code may not choose a ``qualification/`` sibling ledger.  The
    receipt's frozen-before binding supplies the only ledger pathname, and the
    path must mechanically agree with its qualification cycle.
    """
    text = _text(
        value=binding.get("qualification_provider_ledger_path"),
        label="qualification provider ledger path",
    )
    cycle_id = _text(
        value=binding.get("qualification_cycle_id"),
        label="qualification cycle",
    )
    if not _SHA256_ID.fullmatch(cycle_id):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger cycle is invalid",
        )
    expected = (
        FREEZE_CYCLE_ROOT
        / cycle_id.split(":", maxsplit=1)[1]
        / "provider_ledger.jsonl"
    )
    path = Path(text)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path != expected
        or not path.is_relative_to(FREEZE_CYCLE_ROOT)
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger path is unsafe",
        )
    return repo_root / path


def _expected_ledger_entry_identifier(*, entry: Mapping[str, object]) -> str:
    """Recompute one provider-ledger entry identity from exact semantic bytes."""
    body = {
        key: entry[key]
        for key in _PROVIDER_LEDGER_ENTRY_FIELDS
        if key != "qualification_provider_ledger_entry_id"
    }
    return content_hash(value=body)


def _require_duplicated_authority_fields(
    *, value: Mapping[str, object], binding: Mapping[str, object],
    label: str,
) -> None:
    """Require a record's top-level authority facts to equal its nested copy."""
    for field in (
        "qualification_authorization_id",
        "qualification_task_plan_id",
        "qualification_cycle_id",
        "freeze_receipt_id",
        "family_id",
        "task_contract_id",
        "qualification_ordinal",
        "source_binding_hash",
    ):
        if value.get(field) != binding.get(field):
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="{} authority field differs".format(label),
            )


def validate_table_qualification_provider_ledger_entry(
    *, entry: object, binding: Optional[Mapping[str, object]] = None,
    run_id: Optional[str] = None, attempt: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    """Strictly validate one first-class qualification provider ledger row.

    The ledger is an evidence authority, not a debug trace.  Its identifier,
    duplicated top-level facts, nested authorization, request body, provider
    request ID, and transport observation are therefore all exact bindings.
    """
    if type(entry) is not dict or set(entry) != _PROVIDER_LEDGER_ENTRY_FIELDS:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger entry fields differ",
        )
    value = dict(entry)
    if value["record_type"] != "TABLE_QUALIFICATION_PROVIDER_LEDGER_ENTRY":
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger entry type differs",
        )
    nested = value["qualification_authorization"]
    if type(nested) is not dict:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger authority is invalid",
        )
    _require_duplicated_authority_fields(
        value=value,
        binding=nested,
        label="Qualification provider ledger",
    )
    expected_id = _expected_ledger_entry_identifier(entry=value)
    if value["qualification_provider_ledger_entry_id"] != expected_id:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger identity differs",
        )
    if binding is not None:
        if nested != binding:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification provider ledger authority differs",
            )
        _require_duplicated_authority_fields(
            value=value,
            binding=binding,
            label="Qualification provider ledger",
        )
    if run_id is not None and value["run_id"] != run_id:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger Run differs",
        )
    if attempt is not None and (
        value["attempt_id"] != attempt.get("attempt_id")
        or value["request_body_sha256"] != attempt.get("request_body_sha256")
        or value["provider_request_id"] != attempt.get("provider_request_id")
        or value["transport_observation"]
        != attempt.get("transport_observation")
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger attempt differs",
        )
    return value


def _parse_qualification_ledger(*, content: bytes) -> list[Dict[str, object]]:
    """Parse strict JSONL ledger bytes while retaining the frozen line prefix."""
    if content and not content.endswith(b"\n"):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger is malformed",
        )
    rows = []
    seen = set()
    for line in content.splitlines():
        try:
            parsed = strict_json_loads(text=line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification provider ledger row is malformed",
            ) from error
        value = validate_table_qualification_provider_ledger_entry(entry=parsed)
        entry_id = str(value["qualification_provider_ledger_entry_id"])
        if entry_id in seen:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification provider ledger identity is duplicated",
            )
        seen.add(entry_id)
        rows.append(value)
    return rows


def _validate_frozen_ledger_prefix(
    *, content: bytes, binding: Mapping[str, object],
) -> None:
    """Verify the receipt's immutable ledger-before bytes as an exact prefix."""
    row_count = binding.get("qualification_provider_ledger_before_row_count")
    expected_sha256 = binding.get("qualification_provider_ledger_before_sha256")
    if (
        type(row_count) is not int
        or row_count < 0
        or type(expected_sha256) is not str
        or _SHA256_HEX.fullmatch(expected_sha256) is None
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger baseline is invalid",
        )
    lines = content.splitlines(keepends=True)
    if any(not line.endswith(b"\n") for line in lines) or len(lines) < row_count:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger prefix is malformed",
        )
    prefix = b"".join(lines[:row_count])
    if sha256_bytes(content=prefix) != expected_sha256:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger prefix differs",
        )


def _append_qualification_ledger_entry(
    *, repo_root: Path, binding: Mapping[str, object], entry: Mapping[str, object],
) -> None:
    """Append one exact ledger row with a process-wide exclusive lock.

    Before every append, the frozen ledger-before hash/count is rechecked as a
    byte prefix.  Different task/ordinal workers can therefore append without
    racing away from the one receipt-owned ledger.
    """
    value = validate_table_qualification_provider_ledger_entry(
        entry=entry,
        binding=binding,
    )
    path = _qualification_ledger_path(repo_root=repo_root, binding=binding)
    if path.is_symlink() or not path.is_file():
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger is absent or unsafe",
        )
    lock_path = path.with_name(path.name + ".lock")
    if lock_path.exists() and (lock_path.is_symlink() or not lock_path.is_file()):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger lock is unsafe",
        )
    with lock_path.open(mode="a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if path.is_symlink() or not path.is_file():
                raise QualificationError(
                    code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                    message="Qualification provider ledger is absent or unsafe",
                )
            existing = path.read_bytes()
            _validate_frozen_ledger_prefix(content=existing, binding=binding)
            rows = _parse_qualification_ledger(content=existing)
            entry_id = str(value["qualification_provider_ledger_entry_id"])
            for prior in rows:
                prior_id = str(prior["qualification_provider_ledger_entry_id"])
                if prior_id == entry_id:
                    if prior != value:
                        raise QualificationError(
                            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                            message="Qualification provider ledger entry differs",
                        )
                    return
                if (
                    prior["qualification_authorization"].get(
                        "qualification_terminal_id"
                    )
                    == binding["qualification_terminal_id"]
                ):
                    raise QualificationError(
                        code="TABLE_QUALIFICATION_TERMINAL_ALREADY_RECORDED",
                        message="Qualification ordinal already has terminal evidence",
                    )
            encoded = canonical_json_bytes(value=value)
            if not encoded.endswith(b"\n"):
                raise QualificationError(
                    code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                    message="Qualification provider ledger serialization is invalid",
                )
            atomic_write_bytes(path=path, content=existing + encoded)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def record_table_qualification_execution(
    *, repo_root: Path, authorization: Mapping[str, object], run_id: str,
    attempt: Mapping[str, object],
) -> Dict[str, object]:
    """Persist first-class qualification evidence for one LIVE attempt."""
    binding = _rebuild_authorization_binding(
        repo_root=repo_root,
        actual=dict(authorization),
    )
    if run_id != binding["run_id"]:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification evidence Run differs from authorization",
        )
    for field in (
        "attempt_id",
        "task_contract_id",
        "catalog_task_contract_hash",
        "catalog_output_schema_hash",
        "system_prompt_hash",
        "request_body_sha256",
        "provider_request_id",
        "transport_observation",
    ):
        if field not in attempt:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification attempt binding is absent",
            )
    if (
        attempt["task_contract_id"] != binding["task_contract_id"]
        or attempt["catalog_task_contract_hash"]
        != binding["catalog_task_contract_hash"]
        or attempt["catalog_output_schema_hash"]
        != binding["output_schema_hash"]
        or attempt["system_prompt_hash"] != binding["system_prompt_hash"]
        or type(attempt["transport_observation"]) is not dict
        or attempt["transport_observation"].get("egress_attempted") is not True
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification attempt binding differs",
        )
    ledger_body = {
        "record_type": "TABLE_QUALIFICATION_PROVIDER_LEDGER_ENTRY",
        "qualification_authorization": binding,
        "qualification_authorization_id": binding[
            "qualification_authorization_id"
        ],
        "qualification_task_plan_id": binding["qualification_task_plan_id"],
        "qualification_cycle_id": binding["qualification_cycle_id"],
        "freeze_receipt_id": binding["freeze_receipt_id"],
        "family_id": binding["family_id"],
        "task_contract_id": binding["task_contract_id"],
        "qualification_ordinal": binding["qualification_ordinal"],
        "source_binding_hash": binding["source_binding_hash"],
        "run_id": run_id,
        "attempt_id": attempt["attempt_id"],
        "request_body_sha256": attempt["request_body_sha256"],
        "provider_request_id": attempt["provider_request_id"],
        "transport_observation": attempt["transport_observation"],
    }
    ledger_entry = {
        **ledger_body,
        "qualification_provider_ledger_entry_id": content_hash(value=ledger_body),
    }
    _append_qualification_ledger_entry(
        repo_root=repo_root,
        binding=binding,
        entry=ledger_entry,
    )
    evidence_body = {
        "record_type": "TABLE_QUALIFICATION_EVIDENCE",
        "qualification_authorization": binding,
        "qualification_authorization_id": binding[
            "qualification_authorization_id"
        ],
        "qualification_task_plan_id": binding["qualification_task_plan_id"],
        "qualification_cycle_id": binding["qualification_cycle_id"],
        "freeze_receipt_id": binding["freeze_receipt_id"],
        "family_id": binding["family_id"],
        "task_contract_id": binding["task_contract_id"],
        "qualification_ordinal": binding["qualification_ordinal"],
        "source_binding_hash": binding["source_binding_hash"],
        "run_id": run_id,
        "attempt_id": attempt["attempt_id"],
        "provider_ledger_entry_id": ledger_entry[
            "qualification_provider_ledger_entry_id"
        ],
    }
    return {
        **evidence_body,
        "qualification_evidence_id": content_hash(value=evidence_body),
    }


def validate_table_qualification_run_bindings(
    *, repo_root: Path, run_dir: Path, manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
) -> None:
    """Revalidate persisted catalog-LIVE authority and its sole evidence path."""
    authorization = manifest.get("qualification_authorization")
    attempts = [
        record for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    task_bindings = manifest.get("task_contract_bindings")
    catalog_task = type(task_bindings) is list and bool(task_bindings)
    remote_attempts = [
        attempt for attempt in attempts
        if type(attempt.get("transport_observation")) is dict
        and attempt["transport_observation"].get("egress_attempted") is True
    ]
    if authorization is None:
        if catalog_task and remote_attempts:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_REQUIRED",
                message="Remote catalog evidence lacks qualification authorization",
            )
        if any("qualification_authorization" in attempt for attempt in attempts):
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Attempt has qualification authority without Run binding",
        )
        return
    binding = _rebuild_authorization_binding(
        repo_root=repo_root,
        actual=authorization,
    )
    if (
        type(task_bindings) is not list
        or len(task_bindings) != 1
        or task_bindings[0].get("task_contract_id")
        != binding["task_contract_id"]
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Run task binding differs from qualification authority",
        )
    if (
        manifest.get("run_id") != binding["run_id"]
        or manifest.get("target_period") != binding["target_period"]
        or run_dir.resolve()
        != (repo_root / str(binding["run_directory_relative_path"])).resolve()
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Run terminal identity differs from qualification authority",
        )
    references = manifest.get("source_references")
    source = binding["source_binding"]
    declaration = source["source_declaration"]
    if (
        type(references) is not list
        or len(references) != 1
        or references[0].get("company_id") != declaration["company_id"]
        or references[0].get("source_url") != source["source_url"]
        or references[0].get("accession") != declaration["accession"]
        or references[0].get("document_name") != declaration["document_name"]
        or references[0].get("source_role") != source["source_role"]
        or references[0].get("request_attempt_id")
        != source["request_attempt_id"]
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Run source differs from qualification authority",
        )
    raw_blobs = [
        record for record in records if record["record_type"] == "RAW_BLOB"
    ]
    if (
        len(raw_blobs) != 1
        or raw_blobs[0].get("media_type") != binding["source_media_type"]
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Run source media differs from qualification authority",
        )
    if not attempts:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification Run has no AI attempt",
        )
    evidence_by_attempt = {}
    for record in records:
        if record["record_type"] != "TABLE_QUALIFICATION_EVIDENCE":
            continue
        if record["qualification_authorization"] != binding:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification evidence authority differs",
            )
        attempt_id = record["attempt_id"]
        if attempt_id in evidence_by_attempt:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification evidence attempt is duplicated",
            )
        evidence_by_attempt[attempt_id] = record
    ledger_path = _qualification_ledger_path(
        repo_root=repo_root,
        binding=binding,
    )
    if ledger_path.is_symlink() or not ledger_path.is_file():
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger is absent",
        )
    ledger_rows = {}
    ledger_content = ledger_path.read_bytes()
    _validate_frozen_ledger_prefix(content=ledger_content, binding=binding)
    rows = _parse_qualification_ledger(content=ledger_content)
    for value in rows:
        entry_id = str(value["qualification_provider_ledger_entry_id"])
        ledger_rows[entry_id] = value
    for attempt in remote_attempts:
        if attempt.get("qualification_authorization") != binding:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification attempt authority differs",
            )
        evidence = evidence_by_attempt.get(attempt["attempt_id"])
        if evidence is None:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification attempt evidence is absent",
            )
        entry_id = evidence["provider_ledger_entry_id"]
        entry = ledger_rows.get(entry_id)
        if entry is None:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification provider ledger binding differs",
            )
        validate_table_qualification_provider_ledger_entry(
            entry=entry,
            binding=binding,
            run_id=str(manifest["run_id"]),
            attempt=attempt,
        )
    validate_table_qualification_cycle_exact_set(
        repo_root=repo_root,
        binding=binding,
    )


def _ledger_rows_for_terminal(
    *, repo_root: Path, binding: Mapping[str, object],
) -> list[Dict[str, object]]:
    """Return the receipt-owned ledger rows for one deterministic terminal."""
    path = _qualification_ledger_path(repo_root=repo_root, binding=binding)
    if path.is_symlink() or not path.is_file():
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification provider ledger is absent",
        )
    content = path.read_bytes()
    _validate_frozen_ledger_prefix(content=content, binding=binding)
    return [
        row for row in _parse_qualification_ledger(content=content)
        if row["qualification_authorization"].get(
            "qualification_terminal_id"
        ) == binding["qualification_terminal_id"]
    ]


def _attempt_payloads_match(*, run_dir: Path, attempt: Mapping[str, object]) -> bool:
    """Require every declared attempt payload to exist with its declared hash."""
    fields = (
        ("request_body_path", "request_body_sha256"),
        ("reader_payload_path", "reader_payload_sha256"),
        ("task_contract_path", "task_contract_sha256"),
        ("output_schema_path", "output_schema_sha256"),
        ("assistant_output_path", "assistant_output_sha256"),
        ("raw_response_path", "raw_response_sha256"),
    )
    for path_field, hash_field in fields:
        relative = attempt.get(path_field)
        expected = attempt.get(hash_field)
        if relative == "" or expected == "":
            if relative == "" and expected == "":
                continue
            return False
        if type(relative) is not str or type(expected) is not str:
            return False
        path = run_dir / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or sha256_file(path=path) != expected
        ):
            return False
    return True


def _review_tail_is_complete(
    *, repo_root: Path, run_dir: Path, manifest: Mapping[str, object],
    attempt: Mapping[str, object], candidate: Mapping[str, object],
    evidence_check: Mapping[str, object], review_unit: Mapping[str, object],
    binding: Mapping[str, object],
) -> bool:
    """Verify the final review-tail handoff before declaring an OPEN Run complete."""
    checkpoint = run_dir / "qualification_recovery.json"
    if checkpoint.exists():
        if checkpoint.is_symlink() or not checkpoint.is_file():
            raise QualificationError(
                code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
                message="Qualification recovery checkpoint is unsafe",
            )
        return False
    if (
        candidate.get("attempt_id") != attempt.get("attempt_id")
        or evidence_check.get("candidate_hash") != candidate.get("candidate_hash")
        or review_unit.get("evidence_check_id")
        != evidence_check.get("evidence_check_id")
        or review_unit.get("selected") != candidate.get("selected")
        or review_unit.get("competing_candidates")
        != candidate.get("competing_candidates")
        or review_unit.get("unresolved_competing_claims")
        != candidate.get("unresolved_competing_claims")
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
            message="Qualification review-tail record binding differs",
        )
    expected_candidate_hashes = [
        content_hash(value=candidate["selected"][role])
        for role in sorted(candidate["selected"])
    ]
    if review_unit.get("candidate_hashes") != expected_candidate_hashes:
        raise QualificationError(
            code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
            message="Qualification ReviewUnit candidate hashes differ",
        )
    source_ids = [
        source.get("source_reference_id")
        for source in review_unit.get("source_bindings", [])
    ]
    if source_ids != candidate.get("source_reference_ids") or source_ids != [
        source.get("source_reference_id")
        for source in manifest.get("source_references", [])
    ]:
        raise QualificationError(
            code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
            message="Qualification ReviewUnit source binding differs",
        )
    review_dir = run_dir / "review" / str(review_unit["review_unit_hash"])
    expected_assets = {
        "review_context.json": review_unit["review_context_hash"],
        "review.md": review_unit["rendered_review_hash"],
    }
    if not review_dir.exists():
        return False
    if review_dir.is_symlink() or not review_dir.is_dir():
        raise QualificationError(
            code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
            message="Qualification review assets are unsafe",
        )
    actual_names = set()
    for path in review_dir.iterdir():
        if path.is_symlink() or not path.is_file():
            raise QualificationError(
                code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
                message="Qualification review asset entry is unsafe",
            )
        actual_names.add(path.name)
    if actual_names != set(expected_assets):
        return False
    if any(
        sha256_file(path=review_dir / name) != expected
        for name, expected in expected_assets.items()
    ):
        return False
    validate_table_qualification_cycle_exact_set(
        repo_root=repo_root,
        binding=binding,
    )
    return True


def _table_qualification_recovery_state(
    *, repo_root: Path, run_dir: Path, manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]], binding: Mapping[str, object],
) -> str:
    """Classify a deterministic table terminal without making an egress call."""
    status = manifest.get("status")
    if status == "FROZEN":
        return "FROZEN"
    if status == "FAILED":
        return "FAILED_TERMINAL"
    if status != "OPEN":
        return "DIVERGENT"
    attempts = [
        record for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    evidence = [
        record for record in records
        if record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
    ]
    candidates = [
        record for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
    ]
    checks = [
        record for record in records if record["record_type"] == "EVIDENCE_CHECK"
    ]
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    ledger_rows = _ledger_rows_for_terminal(repo_root=repo_root, binding=binding)
    if len(attempts) > 1 or len(evidence) > 1 or len(ledger_rows) > 1:
        return "DIVERGENT"
    if not attempts:
        checkpoint = run_dir / "qualification_recovery.json"
        if checkpoint.exists():
            return (
                "EXACT_SUCCESS_NOT_MATERIALIZED"
                if not checkpoint.is_symlink() and checkpoint.is_file()
                else "DIVERGENT"
            )
        return "DIVERGENT" if ledger_rows or evidence else "OPEN_BEFORE_EGRESS"
    attempt = attempts[0]
    observation = attempt.get("transport_observation")
    if type(observation) is not dict:
        return "DIVERGENT"
    if attempt.get("status") == "FAILED":
        if (
            observation.get("egress_attempted") is True
            and attempt.get("error_class") == "UNKNOWN_REMOTE_OUTCOME"
        ):
            return "UNKNOWN_REMOTE_OUTCOME"
        return "FAILED_TERMINAL"
    if observation.get("egress_attempted") is not True:
        return "DIVERGENT"
    if attempt.get("qualification_authorization") != binding:
        return "DIVERGENT"
    if (
        not _attempt_payloads_match(run_dir=run_dir, attempt=attempt)
        or len(ledger_rows) != 1
        or len(evidence) != 1
        or evidence[0].get("attempt_id") != attempt.get("attempt_id")
    ):
        return "EXACT_SUCCESS_NOT_MATERIALIZED"
    if len(candidates) == 1 and len(checks) == 1 and len(units) == 1:
        if _review_tail_is_complete(
            repo_root=repo_root,
            run_dir=run_dir,
            manifest=manifest,
            attempt=attempt,
            candidate=candidates[0],
            evidence_check=checks[0],
            review_unit=units[0],
            binding=binding,
        ):
            return "COMPLETE_OPEN_PENDING_REVIEW"
        return "EXACT_SUCCESS_NOT_MATERIALIZED"
    if len(candidates) > 1 or len(checks) > 1 or len(units) > 1:
        return "DIVERGENT"
    return "EXACT_SUCCESS_NOT_MATERIALIZED"


def _expected_evidence_identifier(*, evidence: Mapping[str, object]) -> str:
    """Recompute one TABLE_QUALIFICATION_EVIDENCE content identity."""
    fields = (
        "record_type",
        "qualification_authorization",
        "qualification_authorization_id",
        "qualification_task_plan_id",
        "qualification_cycle_id",
        "freeze_receipt_id",
        "family_id",
        "task_contract_id",
        "qualification_ordinal",
        "source_binding_hash",
        "run_id",
        "attempt_id",
        "provider_ledger_entry_id",
    )
    return content_hash(value={field: evidence[field] for field in fields})


def _validate_table_qualification_evidence(
    *, evidence: object, binding: Optional[Mapping[str, object]] = None,
    run_id: Optional[str] = None, attempt: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    """Validate semantic evidence identity and every duplicated authority fact."""
    try:
        value = validate_record(record=evidence)
    except (RecordError, ValueError) as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification evidence record is invalid",
        ) from error
    if value["record_type"] != "TABLE_QUALIFICATION_EVIDENCE":
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification evidence type differs",
        )
    if value["qualification_evidence_id"] != _expected_evidence_identifier(
        evidence=value,
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification evidence identity differs",
        )
    nested = value["qualification_authorization"]
    if type(nested) is not dict:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification evidence authority is invalid",
        )
    _require_duplicated_authority_fields(
        value=value,
        binding=nested,
        label="Qualification evidence",
    )
    if binding is not None:
        if nested != binding:
            raise QualificationError(
                code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
                message="Qualification evidence authority differs",
            )
        _require_duplicated_authority_fields(
            value=value,
            binding=binding,
            label="Qualification evidence",
        )
    if run_id is not None and value["run_id"] != run_id:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification evidence Run differs",
        )
    if attempt is not None and value["attempt_id"] != attempt.get("attempt_id"):
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification evidence attempt differs",
        )
    return dict(value)


def _read_cycle_run_records(*, run_dir: Path) -> tuple[Dict[str, object], list[Dict[str, object]]]:
    """Read one cycle Run without recursively invoking FROZEN replay gates."""
    manifest_path = run_dir / "manifest.json"
    records_path = run_dir / "records.jsonl"
    if (
        run_dir.is_symlink()
        or not run_dir.is_dir()
        or manifest_path.is_symlink()
        or not manifest_path.is_file()
        or records_path.is_symlink()
        or not records_path.is_file()
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle Run is unsafe",
        )
    try:
        manifest = validate_record(record=strict_json_file(path=manifest_path))
    except (RecordError, ValueError) as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle Run manifest is invalid",
        ) from error
    if manifest["record_type"] != "RUN":
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle Run manifest type differs",
        )
    content = records_path.read_bytes()
    if content and not content.endswith(b"\n"):
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle Run records are malformed",
        )
    records = []
    for line in content.splitlines():
        try:
            value = strict_json_loads(text=line.decode("utf-8"))
            records.append(validate_record(record=value))
        except (UnicodeDecodeError, RecordError, ValueError) as error:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle Run record is invalid",
            ) from error
    return dict(manifest), [dict(record) for record in records]


def validate_table_qualification_cycle_exact_set(
    *, repo_root: Path, binding: Mapping[str, object],
) -> None:
    """Require a one-to-one remote-attempt, ledger, and evidence set per cycle.

    Per-Run validation proves that a remote attempt can find a ledger row.  It
    cannot prove the inverse: an extra ledger/evidence row can otherwise hide
    in the shared cycle namespace.  This gate derives all three sets from
    repository-owned Run directories and rejects any non-bijective closure.
    """
    cycle_id = _text(
        value=binding.get("qualification_cycle_id"), label="qualification cycle",
    )
    if _SHA256_ID.fullmatch(cycle_id) is None:
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle identity is invalid",
        )
    run_root = (
        repo_root / TABLE_QUALIFICATION_CYCLE_ROOT
        / cycle_id.split(":", maxsplit=1)[1] / "runs"
    )
    if run_root.is_symlink() or not run_root.is_dir():
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle Run root is absent or unsafe",
        )
    attempts_by_terminal: Dict[str, tuple[Dict[str, object], Dict[str, object]]] = {}
    evidence_by_terminal: Dict[str, Dict[str, object]] = {}
    bindings_by_task_plan: Dict[str, Dict[str, object]] = {}
    seen_run_ids = set()
    seen_attempt_ids = set()
    seen_evidence_ids = set()
    for run_dir in sorted(run_root.iterdir(), key=lambda path: path.name):
        if run_dir.is_symlink() or not run_dir.is_dir():
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle Run entry is unsafe",
            )
        manifest, records = _read_cycle_run_records(run_dir=run_dir)
        authorization = manifest.get("qualification_authorization")
        if authorization is None:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle Run lacks authority",
            )
        current = _rebuild_authorization_binding(
            repo_root=repo_root,
            actual=authorization,
        )
        if current["qualification_cycle_id"] != cycle_id or (
            run_dir.resolve()
            != (repo_root / str(current["run_directory_relative_path"])).resolve()
        ):
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle Run identity differs",
            )
        run_id = str(manifest["run_id"])
        if run_id in seen_run_ids:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle Run identity is duplicated",
            )
        seen_run_ids.add(run_id)
        terminal_id = str(current["qualification_terminal_id"])
        task_plan_id = str(current["qualification_task_plan_id"])
        prior_binding = bindings_by_task_plan.get(task_plan_id)
        if prior_binding is not None and prior_binding != current:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification task plan authority is duplicated",
            )
        bindings_by_task_plan[task_plan_id] = current
        if terminal_id in attempts_by_terminal or terminal_id in evidence_by_terminal:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle terminal is duplicated",
            )
        remote_attempts = [
            record for record in records
            if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            and type(record.get("transport_observation")) is dict
            and record["transport_observation"].get("egress_attempted") is True
        ]
        evidences = [
            record for record in records
            if record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
        ]
        if len(remote_attempts) > 1 or len(evidences) > 1:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle terminal has duplicate evidence",
            )
        if bool(remote_attempts) != bool(evidences):
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle Run closure is incomplete",
            )
        if not remote_attempts:
            continue
        attempt = remote_attempts[0]
        if attempt.get("qualification_authorization") != current:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle attempt authority differs",
            )
        attempt_id = str(attempt["attempt_id"])
        if attempt_id in seen_attempt_ids:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle attempt identity is duplicated",
            )
        seen_attempt_ids.add(attempt_id)
        try:
            observation = TransportObservation.from_mapping(
                value=attempt["transport_observation"],
            )
            requirement = load_requirement_snapshot(
                snapshot_dir=repo_root / "requirements/issue_15_v1",
            )
            policy = approved_transport_policy(requirement=requirement)
        except (AIAdapterError, OSError, ValueError, TypeError) as error:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle transport observation is invalid",
            ) from error
        request_bytes = (run_dir / str(attempt["request_body_path"])).read_bytes()
        if attempt.get("status") == "SUCCEEDED":
            transport_mismatch = transport_observation_mismatch(
                policy=policy,
                observation=observation,
                request_bytes=request_bytes,
            )
        else:
            transport_mismatch = next(
                (
                    field for field, expected in (
                        ("provider", policy.provider),
                        ("model", policy.model),
                        ("model_requested", policy.model),
                        ("api", policy.api),
                        ("endpoint_host", policy.endpoint_host),
                        ("region", policy.region),
                        ("retention", policy.retention),
                        ("data_use", policy.data_use),
                        ("timeout_seconds", policy.timeout_seconds),
                        ("retry_count", policy.retry_count),
                        ("maximum_payload_bytes", policy.maximum_payload_bytes),
                        ("filing_egress_policy", policy.filing_egress_policy),
                        ("request_body_bytes", len(request_bytes)),
                    )
                    if getattr(observation, field) != expected
                ),
                None,
            )
            if (
                not observation.egress_attempted
                or observation.store
                or observation.model_returned not in {policy.model, "none"}
            ):
                transport_mismatch = transport_mismatch or "failed_observation"
        if (
            attempt.get("provider") != current["provider"]
            or attempt.get("model") != current["model"]
            or attempt.get("api") != current["api"]
            or transport_mismatch is not None
        ):
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle transport differs from authority",
            )
        evidence = _validate_table_qualification_evidence(
            evidence=evidences[0],
            binding=current,
            run_id=str(manifest["run_id"]),
            attempt=attempt,
        )
        evidence_id = str(evidence["qualification_evidence_id"])
        if evidence_id in seen_evidence_ids:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle evidence identity is duplicated",
            )
        seen_evidence_ids.add(evidence_id)
        attempts_by_terminal[terminal_id] = (current, attempt)
        evidence_by_terminal[terminal_id] = evidence
    ledger_path = _qualification_ledger_path(repo_root=repo_root, binding=binding)
    if ledger_path.is_symlink() or not ledger_path.is_file():
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle ledger is absent or unsafe",
        )
    ledger_content = ledger_path.read_bytes()
    _validate_frozen_ledger_prefix(content=ledger_content, binding=binding)
    ledger_by_terminal: Dict[str, Dict[str, object]] = {}
    seen_ledger_entry_ids = set()
    for row in _parse_qualification_ledger(content=ledger_content):
        nested = row["qualification_authorization"]
        rebuilt = _rebuild_authorization_binding(
            repo_root=repo_root,
            actual=nested,
        )
        if rebuilt["qualification_cycle_id"] != cycle_id:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification ledger cycle differs",
            )
        terminal_id = str(rebuilt["qualification_terminal_id"])
        ledger_entry_id = str(row["qualification_provider_ledger_entry_id"])
        if ledger_entry_id in seen_ledger_entry_ids:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification ledger entry identity is duplicated",
            )
        seen_ledger_entry_ids.add(ledger_entry_id)
        if terminal_id in ledger_by_terminal:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification ledger terminal is duplicated",
            )
        ledger_by_terminal[terminal_id] = row
    if set(attempts_by_terminal) != set(ledger_by_terminal) or (
        set(attempts_by_terminal) != set(evidence_by_terminal)
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle remote evidence exact set differs",
        )
    workspaces = {
        str(value["wb3_workspace_relative_path"])
        for value in bindings_by_task_plan.values()
    }
    if workspaces != {str(binding["wb3_workspace_relative_path"])}:
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification cycle WB-3 workspace differs",
        )
    try:
        wb3_terminals = qualification_remote_egress_terminals(
            workspace_dir=repo_root / str(binding["wb3_workspace_relative_path"]),
            qualification_task_plan_ids=sorted(bindings_by_task_plan),
        )
    except InvocationControlError as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Qualification WB-3 egress authority is invalid",
        ) from error
    wb3_by_terminal: Dict[str, Dict[str, object]] = {}
    for terminal in wb3_terminals:
        current = bindings_by_task_plan.get(
            str(terminal["qualification_task_plan_id"]),
        )
        if current is None:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification WB-3 task plan is unknown",
            )
        terminal_id = str(current["qualification_terminal_id"])
        if terminal_id in wb3_by_terminal:
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification WB-3 terminal is duplicated",
            )
        wb3_by_terminal[terminal_id] = terminal
    if set(wb3_by_terminal) != set(attempts_by_terminal):
        if set(wb3_by_terminal).difference(attempts_by_terminal):
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_PENDING_MATERIALIZATION",
                message="WB-3 remote egress lacks complete Run materialization",
            )
        raise QualificationError(
            code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
            message="Run remote attempt lacks WB-3 egress authority",
        )
    for terminal_id, (current, attempt) in attempts_by_terminal.items():
        ledger = ledger_by_terminal[terminal_id]
        evidence = evidence_by_terminal[terminal_id]
        wb3 = wb3_by_terminal[terminal_id]
        if (
            attempt["request_body_sha256"]
            != wb3["provider_request_body_sha256"]
            or attempt["provider"] != wb3["provider"]
            or attempt["model"] != wb3["model"]
            or attempt["api"] != wb3["api"]
            or (
                wb3["provider_request_ids"]
                and attempt["provider_request_id"]
                not in wb3["provider_request_ids"]
            )
        ):
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Run attempt differs from WB-3 terminal",
            )
        validate_table_qualification_provider_ledger_entry(
            entry=ledger,
            binding=current,
            run_id=str(current["run_id"]),
            attempt=attempt,
        )
        if (
            evidence["provider_ledger_entry_id"]
            != ledger["qualification_provider_ledger_entry_id"]
            or evidence["attempt_id"] != attempt["attempt_id"]
        ):
            raise QualificationError(
                code="TABLE_QUALIFICATION_CYCLE_EXACT_SET_INVALID",
                message="Qualification cycle evidence linkage differs",
            )


def execute_table_qualification_task(
    *, repo_root: Path, family_id: str, task_contract_id: str,
    qualification_ordinal: int, target_period: Mapping[str, object],
    owner_token: str, clock: Optional[object] = None,
) -> Dict[str, object]:
    """Run the sole future LIVE table-qualification executor.

    The executor derives source, workspace, plan, and authorization from the
    repository.  It deliberately accepts no adapter, source locator, freeze
    ID, cycle ID, or workspace override from callers.
    """
    if type(owner_token) is not str or not owner_token:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification execution owner is invalid",
        )
    authorization = issue_table_qualification_authorization(
        repo_root=repo_root,
        family_id=family_id,
        task_contract_id=task_contract_id,
        qualification_ordinal=qualification_ordinal,
    )
    binding = authorization.as_mapping()
    supplied_period = _target_period_mapping(value=target_period)
    if supplied_period != binding["target_period"]:
        raise QualificationError(
            code="TABLE_QUALIFICATION_AUTHORIZATION_INVALID",
            message="Qualification target period differs from frozen task plan",
        )
    source = binding["source_binding"]
    declaration = source["source_declaration"]
    run_dir = repo_root / str(binding["run_directory_relative_path"])
    existing_state = "NEW"
    if run_dir.exists():
        try:
            manifest, records, _decisions = load_run_for_status(
                run_dir=run_dir,
                repo_root=repo_root,
            )
        except RunStoreError as error:
            raise QualificationError(
                code="TABLE_QUALIFICATION_TERMINAL_INVALID",
                message="Existing qualification terminal cannot be resumed",
            ) from error
        if manifest.get("qualification_authorization") != binding:
            raise QualificationError(
                code="TABLE_QUALIFICATION_TERMINAL_INVALID",
                message="Existing qualification terminal authority differs",
            )
        existing_state = _table_qualification_recovery_state(
            repo_root=repo_root,
            run_dir=run_dir,
            manifest=manifest,
            records=records,
            binding=binding,
        )
        if existing_state == "DIVERGENT":
            raise QualificationError(
                code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
                message="Existing qualification terminal closure differs",
            )
        if existing_state == "UNKNOWN_REMOTE_OUTCOME":
            raise QualificationError(
                code="TABLE_QUALIFICATION_UNKNOWN_REMOTE_OUTCOME",
                message="Qualification terminal has an unknown remote outcome",
            )
        if existing_state in {"FROZEN", "FAILED_TERMINAL", "COMPLETE_OPEN_PENDING_REVIEW"}:
            evidence_ids = sorted(
                str(record["qualification_evidence_id"])
                for record in records
                if record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
            )
            return {
                "run_id": binding["run_id"],
                "status": existing_state,
                "qualification_terminal_id": binding[
                    "qualification_terminal_id"
                ],
                "qualification_evidence_ids": evidence_ids,
            }
    # A receipt-owned ledger row is a pre-egress terminal gate, not an
    # append-time duplicate check.  A matching row with no complete Run is
    # necessarily a divergent closure and must never cause another socket
    # invocation.
    terminal_rows = _ledger_rows_for_terminal(
        repo_root=repo_root,
        binding=binding,
    )
    if terminal_rows and existing_state in {"NEW", "OPEN_BEFORE_EGRESS"}:
        raise QualificationError(
            code="TABLE_QUALIFICATION_TERMINAL_DIVERGENT",
            message="Qualification terminal ledger exists without a Run closure",
        )
    adapter = build_invocation_controlled_transport_adapter(
        release_input_plan_id=str(binding["qualification_task_plan_id"]),
        workspace_dir=repo_root / str(binding["wb3_workspace_relative_path"]),
        owner_token=owner_token,
    )
    from .workflow import create_table_task_review_run

    result = create_table_task_review_run(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=str(binding["run_id"]),
        company_id=str(declaration["company_id"]),
        target_period=binding["target_period"],
        source_repo_relative_path=str(
            declaration["source_repo_relative_path"],
        ),
        source_media_type=str(binding["source_media_type"]),
        source_url=str(source["source_url"]),
        accession=str(declaration["accession"]),
        document_name=str(declaration["document_name"]),
        source_role=str(source["source_role"]),
        request_attempt_id=str(source["request_attempt_id"]),
        task_contract_id=task_contract_id,
        adapter=adapter,
        clock=clock,
        qualification_authorization=authorization,
        resume_existing=(existing_state != "NEW"),
    )
    if result.get("status") == "UNKNOWN_REMOTE_OUTCOME":
        raise QualificationError(
            code="TABLE_QUALIFICATION_UNKNOWN_REMOTE_OUTCOME",
            message="Qualification terminal has an unknown remote outcome",
        )
    if result.get("status") == "REMOTE_FAILURE_TERMINAL":
        return {
            "run_id": binding["run_id"],
            "status": "FAILED_TERMINAL",
            "attempt_id": result["attempt_id"],
            "qualification_terminal_id": binding[
                "qualification_terminal_id"
            ],
        }
    if existing_state != "NEW":
        recovered_state = result.pop("terminal_recovery_state", "")
        return {
            **result,
            "recovery_state": (
                recovered_state if recovered_state else existing_state
            ),
            "qualification_terminal_id": binding[
                "qualification_terminal_id"
            ],
        }
    result.pop("terminal_recovery_state", None)
    return result


def table_qualification_task_plan(
    *,
    repo_root: Path,
    family_id: str,
    task_contract_id: str,
    qualification_ordinal: int,
    include_freeze_status: bool = False,
) -> Dict[str, object]:
    """Resolve one future qualification ordinal to one catalog table task.

    Args:
        repo_root: Repository holding the frozen matrix and task catalog.
        family_id: Matrix-derived table family identity.
        task_contract_id: Explicit matrix-listed single-table task identity.
        qualification_ordinal: One-based fresh-sample ordinal owned by this
            family/task qualification plan.
        include_freeze_status: Internal authorization issuer opt-in for the
            exact already-revalidated freeze status; public callers receive
            only the portable task-plan identity.

    Returns:
        A task plan whose matrix entry, runtime contract, output schema, and
        prompt all name the same catalog task.

    Raises:
        QualificationError: Before any future source/provider action when the
        freeze is invalid, D-07 still requires a decision, or the requested
        task is not owned by the requested family.

    Why:
        Qualification may schedule ordinals, but it may not use a disclosure
        group as an implicit multi-role request.  This joins the frozen matrix
        entry to the one concrete catalog task before Workflow is reached.
    """
    if type(qualification_ordinal) is not int or qualification_ordinal < 1:
        raise QualificationError(
            code="TABLE_QUALIFICATION_TASK_PLAN_INVALID",
            message="Qualification ordinal is invalid",
        )
    try:
        freeze = require_table_qualification_freeze(
            repo_root=repo_root,
            family_id=family_id,
        )
        matrix = load_table_qualification_matrix(repo_root=repo_root)
        contracts = load_table_task_contracts(repo_root=repo_root)
        runtime = resolve_table_task_contract(
            repo_root=repo_root,
            task_contract_id=task_contract_id,
        )
    except TableQualificationFreezeError as error:
        code = (
            "D07_DECISION_REQUIRED"
            if str(error) == "D07_DECISION_REQUIRED"
            else "TABLE_QUALIFICATION_TASK_PLAN_INVALID"
        )
        raise QualificationError(
            code=code,
            message="Frozen table task plan cannot be rebuilt",
        ) from error
    except TableTaskContractError as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_TASK_PLAN_INVALID",
            message="Frozen table task plan cannot be rebuilt",
        ) from error
    if family_id not in matrix["entries"]:
        raise QualificationError(
            code="TABLE_QUALIFICATION_TASK_PLAN_INVALID",
            message="Table family is absent from the qualification matrix",
        )
    entry = matrix["entries"][family_id]
    if (
        task_contract_id not in entry["task_contract_ids"]
        or runtime["reader_family_id"] != family_id
        or runtime["reader_contract_id"] != entry["reader_contract_id"]
        or family_id not in contracts["authorized_family_ids"]
    ):
        raise QualificationError(
            code="TABLE_QUALIFICATION_TASK_PLAN_INVALID",
            message="Matrix task does not bind the requested table family",
        )
    if qualification_ordinal > entry["fresh_samples_required"]:
        raise QualificationError(
            code="TABLE_QUALIFICATION_TASK_PLAN_INVALID",
            message="Qualification ordinal exceeds the frozen sample policy",
        )
    body = {
        "family_id": family_id,
        "task_contract_id": task_contract_id,
        "qualification_ordinal": qualification_ordinal,
        "matrix_entry_hash": content_hash(value=entry),
        "task_contract_hash": runtime["catalog_task_contract_hash"],
        "task_spec_semantic_hash": runtime["task_spec_semantic_hash"],
        "output_schema_hash": runtime["output_schema_hash"],
        "system_prompt_hash": runtime["system_prompt_hash"],
        "freeze_receipt_id": freeze["receipt_id"],
    }
    plan = {**body, "qualification_task_plan_id": content_hash(value=body)}
    if include_freeze_status:
        return {**plan, "_freeze_status": freeze}
    return plan


def _portable_file(*, repo_root: Path, relative: str, label: str) -> Path:
    """Resolve one repository-relative regular file without following aliases.

    Args:
        repo_root: Fixed physical repository root.
        relative: Portable POSIX locator from an audited receipt.
        label: Operator-facing field description.

    Returns:
        Existing regular path below ``repo_root``.
    """
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise QualificationError(
            code="QUALIFICATION_LOCATOR_INVALID",
            message="{} is not repository-relative".format(label),
        )
    path = repo_root / candidate
    if path.is_symlink() or not path.is_file():
        raise QualificationError(
            code="QUALIFICATION_ARTIFACT_MISSING",
            message="{} is absent or unsafe".format(label),
        )
    return path


def production_semantic_tree(*, repo_root: Path) -> Dict[str, object]:
    """Hash every production bridge, entrypoint, config, and Requirement byte.

    Args:
        repo_root: Repository whose production semantics are being frozen.

    Returns:
        Canonical file map and tree identity suitable for later comparison.

    The holdout is meaningful only if it cannot prompt a change in a nearby
    bridge or operator that changes what production executes.  The closure
    therefore includes all production scripts and supported tools as well as
    the catalog/config trees; tests, fixtures, receipts, and documentation stay
    outside so the independent holdout may be added after this freeze.
    """
    paths = []
    for relative_root in SEMANTIC_DIRECTORIES:
        root = repo_root / relative_root
        if root.is_symlink() or not root.is_dir():
            raise QualificationError(
                code="PRODUCTION_SEMANTIC_TREE_INVALID",
                message="Semantic directory is absent or unsafe",
            )
        for path in sorted(root.rglob("*")):
            if "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                raise QualificationError(
                    code="PRODUCTION_SEMANTIC_TREE_INVALID",
                    message="Semantic tree contains a symlink",
                )
            if path.is_file():
                paths.append(path)
    for relative in SEMANTIC_FILES:
        paths.append(
            _portable_file(
                repo_root=repo_root,
                relative=relative.as_posix(),
                label="semantic file",
            )
        )
    relative_paths = [path.relative_to(repo_root).as_posix() for path in paths]
    if len(relative_paths) != len(set(relative_paths)) or not relative_paths:
        raise QualificationError(
            code="PRODUCTION_SEMANTIC_TREE_INVALID",
            message="Semantic file set is empty or duplicated",
        )
    files = {
        relative: {
            "sha256": sha256_file(path=repo_root / relative),
            "size": (repo_root / relative).stat().st_size,
        }
        for relative in sorted(relative_paths)
    }
    body = {"schema_version": 1, "files": files}
    return {**body, "semantic_tree_id": content_hash(value=body)}


def _namespace_state(
    *, repo_root: Path, relative_root: Path, label: str,
) -> Dict[str, object]:
    """Capture one optional qualification namespace without aliases.

    Args:
        repo_root: Fixed physical repository root.
        relative_root: Qualification-owned fixture or Run directory.
        label: Stable diagnostic namespace name.

    Returns:
        Exact directory set plus content-addressed regular-file inventory.
    """
    root = repo_root / relative_root
    if root.is_symlink():
        raise QualificationError(
            code="QUALIFICATION_NAMESPACE_INVALID",
            message="{} namespace is a symlink".format(label),
        )
    if not root.exists():
        return {"directories": [], "files": {}}
    if not root.is_dir():
        raise QualificationError(
            code="QUALIFICATION_NAMESPACE_INVALID",
            message="{} namespace is not a directory".format(label),
        )
    directories = [relative_root.as_posix()]
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise QualificationError(
                code="QUALIFICATION_NAMESPACE_INVALID",
                message="{} namespace contains a symlink".format(label),
            )
        relative = path.relative_to(repo_root).as_posix()
        if path.is_dir():
            directories.append(relative)
        elif path.is_file():
            files[relative] = {
                "sha256": sha256_file(path=path),
                "size": path.stat().st_size,
            }
        else:
            raise QualificationError(
                code="QUALIFICATION_NAMESPACE_INVALID",
                message="{} namespace contains a special file".format(label),
            )
    return {
        "directories": sorted(directories),
        "files": files,
    }


def _qualification_namespace_inventory(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Freeze exact fixture and Run namespaces before holdout introduction.

    Args:
        repo_root: Repository whose qualification ordering is frozen.

    Returns:
        Content-addressed pre-holdout inventory.  The later holdout must use
        paths and bytes absent from both captured namespaces.
    """
    body = {
        "schema_version": 1,
        "fixture_namespace": _namespace_state(
            repo_root=repo_root,
            relative_root=LAYOUT_FIXTURE_ROOT,
            label="layout fixture",
        ),
        "run_namespace": _namespace_state(
            repo_root=repo_root,
            relative_root=QUALIFICATION_RUN_ROOT,
            label="layout Run",
        ),
    }
    return {**body, "inventory_id": content_hash(value=body)}


def _validated_pre_holdout_inventory(
    *, inventory: Mapping[str, object],
) -> Dict[str, object]:
    """Validate the freeze-bound inventory exact shape and identity.

    Args:
        inventory: Receipt-owned pre-holdout namespace snapshot.

    Returns:
        Plain verified inventory mapping.
    """
    required = {
        "fixture_namespace",
        "inventory_id",
        "run_namespace",
        "schema_version",
    }
    if (
        not isinstance(inventory, dict)
        or set(inventory) != required
        or inventory["schema_version"] != 1
        or type(inventory["inventory_id"]) is not str
        or _SHA256_ID.fullmatch(str(inventory["inventory_id"])) is None
    ):
        raise QualificationError(
            code="PRODUCTION_FREEZE_RECEIPT_INVALID",
            message="Pre-holdout inventory root is invalid",
        )
    for namespace_name in ("fixture_namespace", "run_namespace"):
        namespace = inventory[namespace_name]
        if (
            not isinstance(namespace, dict)
            or set(namespace) != {"directories", "files"}
            or not isinstance(namespace["directories"], list)
            or namespace["directories"]
            != sorted(set(namespace["directories"]))
            or any(
                type(relative) is not str
                for relative in namespace["directories"]
            )
            or not isinstance(namespace["files"], dict)
        ):
            raise QualificationError(
                code="PRODUCTION_FREEZE_RECEIPT_INVALID",
                message="Pre-holdout namespace inventory is invalid",
            )
        for relative, file_binding in namespace["files"].items():
            if (
                type(relative) is not str
                or not isinstance(file_binding, dict)
                or set(file_binding) != {"sha256", "size"}
                or type(file_binding["sha256"]) is not str
                or _SHA256_HEX.fullmatch(file_binding["sha256"]) is None
                or type(file_binding["size"]) is not int
                or file_binding["size"] < 0
            ):
                raise QualificationError(
                    code="PRODUCTION_FREEZE_RECEIPT_INVALID",
                    message="Pre-holdout file binding is invalid",
                )
    body = {
        field: inventory[field]
        for field in inventory
        if field != "inventory_id"
    }
    if content_hash(value=body) != inventory["inventory_id"]:
        raise QualificationError(
            code="PRODUCTION_FREEZE_RECEIPT_INVALID",
            message="Pre-holdout inventory identity differs",
        )
    return dict(inventory)


def write_production_freeze_receipt(
    *, repo_root: Path, frozen_at_utc: str,
) -> Dict[str, object]:
    """Persist a content-addressed pre-holdout production tree receipt.

    Args:
        repo_root: Repository containing the finalized primary implementation.
        frozen_at_utc: Explicit UTC audit timestamp.

    Returns:
        Receipt including its repository-relative content-addressed path.
    """
    try:
        parse_utc_timestamp(value=frozen_at_utc)
    except ValueError as error:
        raise QualificationError(
            code="PRODUCTION_FREEZE_TIME_INVALID",
            message="Production freeze timestamp must be UTC",
        ) from error
    tree = production_semantic_tree(repo_root=repo_root)
    manifest_path = repo_root / QUALIFICATION_MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise QualificationError(
            code="SECOND_LAYOUT_REQUIRED_BEFORE_FREEZE",
            message="Production freeze requires the second-layout receipt",
        )
    manifest = strict_json_file(path=manifest_path)
    expected_manifest_fields = {
        "holdout_receipt",
        "production_freeze_receipt",
        "schema_version",
        "second_layout_receipt",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != expected_manifest_fields
        or manifest["schema_version"] != 1
        or not isinstance(manifest["second_layout_receipt"], dict)
    ):
        raise QualificationError(
            code="SECOND_LAYOUT_REQUIRED_BEFORE_FREEZE",
            message="Second-layout qualification reference is unavailable",
        )
    second = _validate_addressed_receipt(
        repo_root=repo_root,
        reference=manifest["second_layout_receipt"],
        label="second layout before freeze",
    )
    if (
        "receipt_type" not in second
        or "production_semantic_tree_id" not in second
        or second["receipt_type"] != "SECOND_LAYOUT"
        or second["production_semantic_tree_id"]
        != tree["semantic_tree_id"]
    ):
        raise QualificationError(
            code="SECOND_LAYOUT_REQUIRED_BEFORE_FREEZE",
            message="Second-layout receipt does not bind frozen semantics",
        )
    body = {
        "schema_version": 1,
        "receipt_type": "PRODUCTION_SEMANTIC_FREEZE",
        "frozen_at_utc": frozen_at_utc,
        "semantic_tree_id": tree["semantic_tree_id"],
        "semantic_files": tree["files"],
        "second_layout_receipt_id": second["receipt_id"],
        "pre_holdout_inventory": _qualification_namespace_inventory(
            repo_root=repo_root,
        ),
    }
    receipt_id = content_hash(value=body)
    receipt = {**body, "receipt_id": receipt_id}
    relative = QUALIFICATION_ROOT / "receipts" / (
        receipt_id.split(":", maxsplit=1)[1] + ".json"
    )
    atomic_write_json(path=repo_root / relative, value=receipt)
    _write_qualification_reference(
        repo_root=repo_root,
        role="production_freeze_receipt",
        receipt_id=receipt_id,
        receipt_path=relative.as_posix(),
    )
    return {**receipt, "receipt_path": relative.as_posix()}


def reset_qualification_chain(
    *, repo_root: Path, reset_at_utc: str, reason: str,
) -> Dict[str, object]:
    """Archive one failed qualification chain before a clean requalification.

    Args:
        repo_root: Repository owning the formal qualification namespace.
        reset_at_utc: Explicit UTC audit time for the reset receipt.
        reason: Stable uppercase failure reason supplied by the operator.

    Returns:
        Content-addressed reset receipt and a fresh unqualified manifest.

    Raises:
        QualificationError: When no failed chain exists, an active publication
            could be affected, or the prior manifest cannot be audited.

    A reset never deletes Runs, receipts, fixture bytes, or SEC evidence.  It
    only moves the mutable manifest to a fresh chain after persisting the
    prior manifest and its current blocker as immutable audit evidence.
    """
    try:
        parse_utc_timestamp(value=reset_at_utc)
    except ValueError as error:
        raise QualificationError(
            code="QUALIFICATION_RESET_TIME_INVALID",
            message="Qualification reset timestamp must be UTC",
        ) from error
    if type(reason) is not str or _RESET_REASON.fullmatch(reason) is None:
        raise QualificationError(
            code="QUALIFICATION_RESET_REASON_INVALID",
            message="Qualification reset reason is invalid",
        )
    active_path = repo_root / "outputs/active_publication.json"
    if active_path.exists() or active_path.is_symlink():
        raise QualificationError(
            code="QUALIFICATION_RESET_ACTIVE_FORBIDDEN",
            message="Qualification reset is forbidden after active publication",
        )
    manifest_path = repo_root / QUALIFICATION_MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise QualificationError(
            code="QUALIFICATION_RESET_NOTHING_TO_RESET",
            message="Qualification manifest is absent",
        )
    prior_manifest = strict_json_file(path=manifest_path)
    expected_fields = {
        "holdout_receipt",
        "production_freeze_receipt",
        "schema_version",
        "second_layout_receipt",
    }
    if (
        not isinstance(prior_manifest, dict)
        or set(prior_manifest) != expected_fields
        or prior_manifest["schema_version"] != 1
    ):
        raise QualificationError(
            code="QUALIFICATION_RESET_MANIFEST_INVALID",
            message="Qualification manifest fields are invalid",
        )
    try:
        validate_cutover_qualifications(repo_root=repo_root)
    except QualificationError as error:
        blocker_code = error.code
    else:
        raise QualificationError(
            code="QUALIFICATION_RESET_VALID_CHAIN_FORBIDDEN",
            message="A valid qualification chain cannot be reset",
        )
    body = {
        "schema_version": 1,
        "receipt_type": "QUALIFICATION_CHAIN_RESET",
        "reset_at_utc": reset_at_utc,
        "reason": reason,
        "prior_blocker_code": blocker_code,
        "prior_manifest_sha256": sha256_file(path=manifest_path),
        "prior_manifest": prior_manifest,
    }
    reset_id = content_hash(value=body)
    receipt = {**body, "reset_id": reset_id}
    relative = QUALIFICATION_ROOT / "resets" / (
        reset_id.split(":", maxsplit=1)[1] + ".json"
    )
    atomic_write_json(path=repo_root / relative, value=receipt)
    atomic_write_json(
        path=manifest_path,
        value={
            "schema_version": 1,
            "production_freeze_receipt": None,
            "second_layout_receipt": None,
            "holdout_receipt": None,
        },
    )
    return {**receipt, "receipt_path": relative.as_posix()}


def _write_qualification_reference(
    *, repo_root: Path, role: str, receipt_id: str, receipt_path: str,
) -> None:
    """Update one fixed qualification-manifest role atomically.

    Args:
        repo_root: Repository owning the local audit namespace.
        role: One of the three fixed evidence roles.
        receipt_id: Content-addressed receipt identity.
        receipt_path: Matching repository-relative receipt path.

    Expected output:
        The mutable index changes atomically while every referenced receipt
        remains immutable and content-addressed.
    """
    roles = {
        "holdout_receipt",
        "production_freeze_receipt",
        "second_layout_receipt",
    }
    if role not in roles:
        raise QualificationError(
            code="QUALIFICATION_ROLE_INVALID",
            message="Qualification receipt role is invalid",
        )
    manifest_path = repo_root / QUALIFICATION_MANIFEST
    if manifest_path.is_symlink():
        raise QualificationError(
            code="QUALIFICATION_MANIFEST_INVALID",
            message="Qualification manifest is a symlink",
        )
    if manifest_path.exists():
        manifest = strict_json_file(path=manifest_path)
        if not isinstance(manifest, dict) or set(manifest) != {
            *roles,
            "schema_version",
        } or manifest["schema_version"] != 1:
            raise QualificationError(
                code="QUALIFICATION_MANIFEST_INVALID",
                message="Qualification manifest fields are not exact",
            )
    else:
        manifest = {
            "schema_version": 1,
            "production_freeze_receipt": None,
            "second_layout_receipt": None,
            "holdout_receipt": None,
        }
    manifest[role] = {
        "receipt_id": receipt_id,
        "receipt_path": receipt_path,
    }
    atomic_write_json(path=manifest_path, value=manifest)


def _validate_addressed_receipt(
    *, repo_root: Path, reference: Mapping[str, object], label: str,
) -> Dict[str, object]:
    """Load one receipt whose path, declared ID, and canonical body agree.

    Args:
        repo_root: Repository containing the fixed qualification namespace.
        reference: Exact ``receipt_id`` and ``receipt_path`` mapping.
        label: Stable manifest role for diagnostics.

    Returns:
        Verified receipt object.
    """
    if not isinstance(reference, dict) or set(reference) != {
        "receipt_id",
        "receipt_path",
    }:
        raise QualificationError(
            code="QUALIFICATION_MANIFEST_INVALID",
            message="{} receipt reference is not exact".format(label),
        )
    receipt_id = reference["receipt_id"]
    receipt_path = reference["receipt_path"]
    if (
        type(receipt_id) is not str
        or _SHA256_ID.fullmatch(receipt_id) is None
        or type(receipt_path) is not str
    ):
        raise QualificationError(
            code="QUALIFICATION_MANIFEST_INVALID",
            message="{} receipt identity is invalid".format(label),
        )
    digest = receipt_id.split(":", maxsplit=1)[1]
    expected_path = (QUALIFICATION_ROOT / "receipts" / (
        digest + ".json"
    )).as_posix()
    if receipt_path != expected_path:
        raise QualificationError(
            code="QUALIFICATION_MANIFEST_INVALID",
            message="{} receipt is not content-addressed".format(label),
        )
    path = _portable_file(
        repo_root=repo_root, relative=receipt_path, label=label + " receipt",
    )
    receipt = strict_json_file(path=path)
    if not isinstance(receipt, dict) or "receipt_id" not in receipt:
        raise QualificationError(
            code="QUALIFICATION_RECEIPT_INVALID",
            message="{} receipt root is invalid".format(label),
        )
    body = {
        field: receipt[field]
        for field in receipt
        if field != "receipt_id"
    }
    if (
        receipt["receipt_id"] != receipt_id
        or content_hash(value=body) != receipt_id
    ):
        raise QualificationError(
            code="QUALIFICATION_RECEIPT_TAMPERED",
            message="{} receipt identity differs from bytes".format(label),
        )
    return receipt


def _layout_fixture_manifest(
    *, repo_root: Path, fixture_id: str,
) -> Dict[str, object]:
    """Load one exact fixture manifest and verify its repository byte roots.

    Args:
        repo_root: Repository owning the fixed fixture namespace.
        fixture_id: Safe qualification fixture directory identity.

    Returns:
        Exact schema-v1 manifest with source, excerpt, and response bytes
        constrained below its own fixture directory.
    """
    fixture_relative = LAYOUT_FIXTURE_ROOT / fixture_id
    fixture_path = _portable_file(
        repo_root=repo_root,
        relative=(fixture_relative / "fixture_manifest.json").as_posix(),
        label="layout fixture manifest",
    )
    fixture = strict_json_file(path=fixture_path)
    if (
        not isinstance(fixture, dict)
        or set(fixture) != LAYOUT_FIXTURE_FIELDS
        or fixture["schema_version"] != 1
        or fixture["fixture_id"] != fixture_id
        or type(fixture["selection_reason"]) is not str
        or not fixture["selection_reason"].strip()
    ):
        raise QualificationError(
            code="LAYOUT_FIXTURE_INVALID",
            message="Layout fixture manifest fields are not exact",
        )
    for path_field, hash_field, label in (
        ("source_repo_relative_path", "source_sha256", "layout source"),
        ("excerpt_repo_relative_path", "excerpt_sha256", "layout excerpt"),
        (
            "recorded_response_repo_relative_path",
            "recorded_response_sha256",
            "recorded response",
        ),
    ):
        path = _validate_hashed_file(
            repo_root=repo_root,
            receipt=fixture,
            path_field=path_field,
            hash_field=hash_field,
            label=label,
        )
        if repo_root / fixture_relative not in path.parents:
            raise QualificationError(
                code="LAYOUT_FIXTURE_INVALID",
                message="{} is outside its fixture root".format(label),
            )
    return fixture


def _layout_validation_receipt(*, run_path: Path) -> Dict[str, object]:
    """Load the terminal validation record bound to one layout Run.

    Args:
        run_path: Frozen qualification Run directory.

    Returns:
        Strict ValidationReceipt record for the exact Run bytes.

    Raises:
        QualificationError: If the receipt is absent, malformed, or not a
            ValidationReceipt record.
    """
    try:
        payload = strict_json_file(path=run_path / "validation.json")
        if not isinstance(payload, dict):
            raise RecordError("Layout validation receipt must be an object")
        receipt = validate_record(record=payload)
    except (OSError, ValueError) as error:
        raise QualificationError(
            code="LAYOUT_VALIDATION_NOT_PASSED",
            message="Layout Run validation receipt is invalid",
        ) from error
    if receipt["record_type"] != "VALIDATION_RECEIPT":
        raise QualificationError(
            code="LAYOUT_VALIDATION_NOT_PASSED",
            message="Layout Run lacks a validation receipt",
        )
    return receipt


def _require_qualified_layout_terminal(
    *,
    decision: Mapping[str, object],
    results: Sequence[Mapping[str, object]],
    validation: Mapping[str, object],
    expected_metric_ids: Sequence[str],
) -> None:
    """Require an approved, publishable terminal outcome for one layout.

    Args:
        decision: Effective ReviewDecision already bound to the ReviewUnit.
        results: Validated MetricResult records produced from that decision.
        validation: Strict terminal ValidationReceipt for the same Run.
        expected_metric_ids: Exact result IDs declared by the disclosure Spec.

    Returns:
        None.

    Raises:
        QualificationError: If HUMAN rejected the layout, mechanical Run
            validation did not pass, or any layout result is not publishable.
    """
    # A real layout only proves generalization after an explicit review record.
    # D-06 permits SYSTEM when no HUMAN decision exists; a rejected Run remains
    # audit evidence and cannot become a Cutover qualification witness.
    if (
        decision["reviewer_type"] not in {"HUMAN", "SYSTEM"}
        or decision["decision"] != "APPROVE"
    ):
        raise QualificationError(
            code="LAYOUT_REVIEW_APPROVAL_REQUIRED",
            message="Layout qualification requires an effective review APPROVE",
        )
    if (
        validation["record_type"] != "VALIDATION_RECEIPT"
        or validation["status"] != "PASSED"
    ):
        raise QualificationError(
            code="LAYOUT_VALIDATION_NOT_PASSED",
            message="Layout qualification requires PASSED Run validation",
        )
    result_ids = [record["metric_id"] for record in results]
    if (
        set(result_ids) != set(expected_metric_ids)
        or len(result_ids) != len(set(result_ids))
    ):
        raise QualificationError(
            code="LAYOUT_RESULT_SET_INVALID",
            message="Layout Result metric exact set differs from the Spec",
        )
    if any(record["publication"] != "PUBLISHED" for record in results):
        raise QualificationError(
            code="LAYOUT_RESULTS_NOT_PUBLISHED",
            message="Layout qualification requires published metric results",
        )


def write_layout_qualification_receipt(
    *, repo_root: Path, fixture_id: str,
) -> Dict[str, object]:
    """Derive one layout receipt only from fixed fixture and FROZEN Run bytes.

    Args:
        repo_root: Repository containing fixture, Run, and semantic authority.
        fixture_id: Safe fixture directory identity.

    Returns:
        Content-addressed layout receipt and its portable path.
    """
    if (
        not fixture_id
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
               for character in fixture_id)
    ):
        raise QualificationError(
            code="LAYOUT_FIXTURE_INVALID",
            message="Layout fixture identity is invalid",
        )
    fixture_relative = LAYOUT_FIXTURE_ROOT / fixture_id
    fixture_path = repo_root / fixture_relative / "fixture_manifest.json"
    fixture = _layout_fixture_manifest(
        repo_root=repo_root, fixture_id=fixture_id,
    )
    role = fixture["qualification_role"]
    role_to_index = {
        "SECOND_LAYOUT": "second_layout_receipt",
        "POST_FREEZE_HOLDOUT": "holdout_receipt",
    }
    if role not in role_to_index:
        raise QualificationError(
            code="LAYOUT_FIXTURE_INVALID",
            message="Layout fixture qualification role is invalid",
        )
    index_path = repo_root / QUALIFICATION_MANIFEST
    if role == "SECOND_LAYOUT" and index_path.is_file():
        index = strict_json_file(path=index_path)
        if (
            isinstance(index, dict)
            and "production_freeze_receipt" in index
            and index["production_freeze_receipt"] is not None
        ):
            raise QualificationError(
                code="SECOND_LAYOUT_AFTER_FREEZE_FORBIDDEN",
                message="Second-layout receipt must exist before freeze",
            )
    run_relative = QUALIFICATION_ROOT / "runs" / fixture_id
    run_path = repo_root / run_relative
    manifest, records, decisions = load_run_for_status(
        run_dir=run_path, repo_root=repo_root,
    )
    if manifest["status"] != "FROZEN":
        raise QualificationError(
            code="LAYOUT_RUN_NOT_FROZEN",
            message="Layout Run must pass replay/freeze before receipt",
        )
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    candidates = [
        record
        for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
    ]
    derived_assets = [
        record
        for record in records
        if record["record_type"] == "DERIVED_ASSET"
    ]
    attempts = [
        record
        for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    results = [
        record
        for record in records
        if record["record_type"] == "METRIC_RESULT"
    ]
    if (
        len(units) != 1
        or len(candidates) != 1
        or len(derived_assets) != 1
        or len(attempts) != 1
        or len(results) != 2
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID",
            message="Layout Run record graph is incomplete",
        )
    attempt_observation = attempts[0]["transport_observation"]
    if (
        attempt_observation["egress_attempted"] is not False
        or attempt_observation["endpoint_host"] != "none"
    ):
        raise QualificationError(
            code="LAYOUT_RUN_NOT_RECORDED",
            message="Layout qualification must be socket-zero recorded",
        )
    decision = effective_review_decision(
        review_unit=units[0], decisions=decisions,
    )
    validation = _layout_validation_receipt(run_path=run_path)
    expected_metric_ids = tuple(
        units[0]["compiled_spec"]["legacy_projection"][
            "role_metric_ids"
        ].values()
    )
    _require_qualified_layout_terminal(
        decision=decision,
        results=results,
        validation=validation,
        expected_metric_ids=expected_metric_ids,
    )
    tree = production_semantic_tree(repo_root=repo_root)
    if role == "POST_FREEZE_HOLDOUT":
        index = strict_json_file(path=repo_root / QUALIFICATION_MANIFEST)
        if (
            not isinstance(index, dict)
            or not isinstance(index["production_freeze_receipt"], dict)
        ):
            raise QualificationError(
                code="PRODUCTION_FREEZE_RECEIPT_REQUIRED",
                message="Holdout requires an existing production freeze",
            )
        freeze = _validate_addressed_receipt(
            repo_root=repo_root,
            reference=index["production_freeze_receipt"],
            label="production freeze",
        )
        if tree["semantic_tree_id"] != freeze["semantic_tree_id"]:
            raise QualificationError(
                code="POST_FREEZE_PRODUCTION_DRIFT",
                message="Production semantics changed after holdout freeze",
            )
        _validate_post_freeze_holdout(
            freeze=freeze,
            holdout={
                **fixture,
                "run_repo_relative_path": run_relative.as_posix(),
            },
        )
    comparison = _mechanical_layout_comparison(
        repo_root=repo_root, fixture=fixture,
    )
    body = {
        "schema_version": 1,
        "receipt_type": role,
        "fixture_id": fixture_id,
        "fixture_manifest_sha256": sha256_file(path=fixture_path),
        "company_id": fixture["company_id"],
        "cik": fixture["cik"],
        "accession": fixture["accession"],
        "document_name": fixture["document_name"],
        "source_url": fixture["source_url"],
        "source_repo_relative_path": fixture[
            "source_repo_relative_path"
        ],
        "source_sha256": fixture["source_sha256"],
        "excerpt_repo_relative_path": fixture[
            "excerpt_repo_relative_path"
        ],
        "excerpt_sha256": fixture["excerpt_sha256"],
        "recorded_response_repo_relative_path": fixture[
            "recorded_response_repo_relative_path"
        ],
        "recorded_response_sha256": fixture[
            "recorded_response_sha256"
        ],
        "selection_reason": fixture["selection_reason"],
        "layout_differences": comparison[
            "verified_declared_differences"
        ],
        "layout_comparison": comparison,
        "run_repo_relative_path": run_relative.as_posix(),
        "run_manifest_sha256": sha256_file(
            path=run_path / "manifest.json"
        ),
        "run_validation_sha256": sha256_file(
            path=run_path / "validation.json"
        ),
        "run_status": manifest["status"],
        "review_unit_hash": units[0]["review_unit_hash"],
        "review_context_hash": units[0]["review_context_hash"],
        "effective_human_decision_id": decision["review_decision_id"],
        "metric_result_ids": {
            record["metric_id"]: record["result_id"]
            for record in results
        },
        "production_semantic_tree_id": tree["semantic_tree_id"],
        "socket_count": 0,
    }
    receipt_id = content_hash(value=body)
    receipt = {**body, "receipt_id": receipt_id}
    relative = QUALIFICATION_ROOT / "receipts" / (
        receipt_id.split(":", maxsplit=1)[1] + ".json"
    )
    atomic_write_json(path=repo_root / relative, value=receipt)
    _write_qualification_reference(
        repo_root=repo_root,
        role=role_to_index[str(role)],
        receipt_id=receipt_id,
        receipt_path=relative.as_posix(),
    )
    return {**receipt, "receipt_path": relative.as_posix()}


def _normalized_cik(*, value: object, label: str) -> str:
    """Normalize one SEC CIK so leading-zero aliases cannot escape identity.

    Args:
        value: Candidate CIK string or CSV cell.
        label: Stable diagnostic field name.

    Returns:
        Canonical decimal CIK without leading zeroes.
    """
    if type(value) is not str or not value or not value.isdigit():
        raise QualificationError(
            code="QUALIFICATION_CIK_INVALID",
            message="{} CIK is not decimal".format(label),
        )
    normalized = value.lstrip("0") or "0"
    if len(normalized) > 10 or normalized == "0":
        raise QualificationError(
            code="QUALIFICATION_CIK_INVALID",
            message="{} CIK is outside SEC identity range".format(label),
        )
    return normalized


def _registry_identities(*, repo_root: Path) -> Dict[str, Sequence[str]]:
    """Read every formal production company and CIK alias.

    Args:
        repo_root: Repository containing the canonical company registry.

    Returns:
        Ordered company IDs and canonical primary/related/role CIKs.
    """
    path = _portable_file(
        repo_root=repo_root,
        relative="config/company_registry.csv",
        label="company registry",
    )
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        required_fields = {
            "company_id", "primary_cik", "related_ciks", "roles",
        }
        if (
            reader.fieldnames is None
            or not required_fields.issubset(set(reader.fieldnames))
        ):
            raise QualificationError(
                code="QUALIFICATION_REGISTRY_INVALID",
                message="Company registry lacks identity fields",
            )
        rows = list(reader)
    company_ids = [row["company_id"] for row in rows]
    if (
        not company_ids
        or any(not value for value in company_ids)
        or len(company_ids) != len(set(company_ids))
    ):
        raise QualificationError(
            code="QUALIFICATION_REGISTRY_INVALID",
            message="Company registry identity set is invalid",
        )
    ciks = set()
    for row in rows:
        ciks.add(_normalized_cik(
            value=row["primary_cik"], label="primary",
        ))
        related = row["related_ciks"]
        if related:
            for value in related.split(";"):
                ciks.add(_normalized_cik(value=value, label="related"))
        roles = row["roles"]
        if not roles:
            raise QualificationError(
                code="QUALIFICATION_REGISTRY_INVALID",
                message="Company registry roles are empty",
            )
        for role in roles.split(";"):
            parts = role.split(":", maxsplit=1)
            if len(parts) != 2 or not parts[0]:
                raise QualificationError(
                    code="QUALIFICATION_REGISTRY_INVALID",
                    message="Company registry role is invalid",
                )
            ciks.add(_normalized_cik(value=parts[1], label="role"))
    return {
        "company_ids": tuple(company_ids),
        "ciks": tuple(sorted(ciks, key=lambda value: int(value))),
    }


def _validate_independent_layouts(
    *, second: Mapping[str, object], holdout: Mapping[str, object],
) -> None:
    """Reject company, filing, or exact-source aliases across qualifications.

    Args:
        second: Verified second-layout identity.
        holdout: Verified post-freeze holdout identity.

    Expected output:
        No value. Any shared company, CIK, accession, or source bytes fail.
    """
    required = {"accession", "cik", "company_id", "source_sha256"}
    if not required.issubset(second) or not required.issubset(holdout):
        raise QualificationError(
            code="LAYOUT_RECEIPT_INVALID",
            message="Layout independence identity is incomplete",
        )
    aliases = []
    if second["company_id"] == holdout["company_id"]:
        aliases.append("company_id")
    if _normalized_cik(
        value=second["cik"], label="second layout",
    ) == _normalized_cik(value=holdout["cik"], label="holdout"):
        aliases.append("cik")
    for field in ("accession", "source_sha256"):
        if second[field] == holdout[field]:
            aliases.append(field)
    if aliases:
        raise QualificationError(
            code="HOLDOUT_NOT_INDEPENDENT",
            message="Second layout and holdout alias: {}".format(
                ",".join(aliases)
            ),
        )


def _validate_post_freeze_holdout(
    *, freeze: Mapping[str, object], holdout: Mapping[str, object],
) -> None:
    """Prove holdout fixture bytes and Run path were absent at freeze.

    Args:
        freeze: Verified production freeze receipt.
        holdout: Layout receipt or equivalent exact path/hash mapping.

    Expected output:
        No value. A preexisting holdout byte, fixture directory, or Run path
        fails closed even when its later receipt is otherwise valid.
    """
    if "pre_holdout_inventory" not in freeze:
        raise QualificationError(
            code="PRODUCTION_FREEZE_RECEIPT_INVALID",
            message="Production freeze lacks pre-holdout inventory",
        )
    inventory = _validated_pre_holdout_inventory(
        inventory=freeze["pre_holdout_inventory"],
    )
    required = {
        "excerpt_repo_relative_path",
        "excerpt_sha256",
        "fixture_id",
        "recorded_response_repo_relative_path",
        "recorded_response_sha256",
        "run_repo_relative_path",
        "source_repo_relative_path",
        "source_sha256",
    }
    if not required.issubset(holdout):
        raise QualificationError(
            code="LAYOUT_RECEIPT_INVALID",
            message="Holdout ordering identity is incomplete",
        )
    fixture_namespace = inventory["fixture_namespace"]
    run_namespace = inventory["run_namespace"]
    fixture_root = (
        LAYOUT_FIXTURE_ROOT / str(holdout["fixture_id"])
    ).as_posix()
    run_root = str(holdout["run_repo_relative_path"])
    fixture_paths = {
        fixture_root,
        fixture_root + "/fixture_manifest.json",
        str(holdout["excerpt_repo_relative_path"]),
        str(holdout["recorded_response_repo_relative_path"]),
        str(holdout["source_repo_relative_path"]),
    }
    frozen_fixture_paths = set(fixture_namespace["directories"]) | set(
        fixture_namespace["files"]
    )
    frozen_run_paths = set(run_namespace["directories"]) | set(
        run_namespace["files"]
    )
    fixture_hashes = {
        binding["sha256"]
        for binding in fixture_namespace["files"].values()
    }
    holdout_hashes = {
        str(holdout["excerpt_sha256"]),
        str(holdout["recorded_response_sha256"]),
        str(holdout["source_sha256"]),
    }
    run_alias = any(
        path == run_root or path.startswith(run_root + "/")
        for path in frozen_run_paths
    )
    if (
        fixture_paths & frozen_fixture_paths
        or holdout_hashes & fixture_hashes
        or run_alias
    ):
        raise QualificationError(
            code="HOLDOUT_EXISTED_BEFORE_FREEZE",
            message="Holdout bytes or Run namespace existed at freeze",
        )


def _validate_hashed_file(
    *, repo_root: Path, receipt: Mapping[str, object], path_field: str,
    hash_field: str, label: str,
) -> Path:
    """Verify one receipt-bound repository file.

    Args:
        repo_root: Repository containing the artifact.
        receipt: Layout receipt declaring locator and digest.
        path_field: Receipt locator field.
        hash_field: Receipt digest field.
        label: Stable diagnostic label.

    Returns:
        Verified artifact path.
    """
    if path_field not in receipt or hash_field not in receipt:
        raise QualificationError(
            code="LAYOUT_RECEIPT_INVALID",
            message="{} binding is absent".format(label),
        )
    if (
        type(receipt[path_field]) is not str
        or type(receipt[hash_field]) is not str
    ):
        raise QualificationError(
            code="LAYOUT_RECEIPT_INVALID",
            message="{} binding type is invalid".format(label),
        )
    path = _portable_file(
        repo_root=repo_root,
        relative=str(receipt[path_field]),
        label=label,
    )
    if sha256_file(path=path) != receipt[hash_field]:
        raise QualificationError(
            code="LAYOUT_RECEIPT_TAMPERED",
            message="{} digest differs".format(label),
        )
    return path


def _layout_signature(
    *, excerpt: Mapping[str, object], response: Mapping[str, object],
) -> Dict[str, object]:
    """Derive replayable layout dimensions without company-specific parsing.

    Args:
        excerpt: Minimal real table-grid excerpt.
        response: Strict recorded Reader response bound to that grid.

    Returns:
        Normalized grid and five dimension identities used only to compare
        layout materiality against the frozen repository reference.
    """
    if (
        not isinstance(excerpt, dict)
        or not {"cells", "derived_asset_id", "table_id"}.issubset(excerpt)
        or not isinstance(excerpt["cells"], list)
        or not excerpt["cells"]
        or not isinstance(response, dict)
        or not {"candidates", "table_locator"}.issubset(response)
        or not isinstance(response["candidates"], list)
    ):
        raise QualificationError(
            code="LAYOUT_COMPARISON_INVALID",
            message="Layout excerpt or Reader response is incomplete",
        )
    table_locator = response["table_locator"]
    if (
        not isinstance(table_locator, dict)
        or set(table_locator) != {"derived_asset_id", "table_id"}
        or table_locator["derived_asset_id"] != excerpt["derived_asset_id"]
        or table_locator["table_id"] != excerpt["table_id"]
    ):
        raise QualificationError(
            code="LAYOUT_COMPARISON_INVALID",
            message="Reader table identity differs from excerpt",
        )
    normalized_cells = []
    cell_fields = {
        "column_index",
        "colspan",
        "origin_column_index",
        "origin_row_index",
        "row_index",
        "rowspan",
        "text",
    }
    for cell in excerpt["cells"]:
        if (
            not isinstance(cell, dict)
            or set(cell) != cell_fields
            or any(
                type(cell[field]) is not int
                for field in (
                    "column_index", "colspan", "origin_column_index",
                    "origin_row_index", "row_index", "rowspan",
                )
            )
            or type(cell["text"]) is not str
        ):
            raise QualificationError(
                code="LAYOUT_COMPARISON_INVALID",
                message="Layout excerpt cell is invalid",
            )
        normalized_cells.append({field: cell[field] for field in sorted(cell)})
    normalized_cells.sort(
        key=lambda cell: (
            cell["row_index"], cell["column_index"], cell["text"],
        )
    )
    candidate_roles = set()
    selected = []
    headers = []
    scopes = []
    spans = []
    for candidate in response["candidates"]:
        required_candidate = {
            "claimed_period", "locator", "role",
            "scope_evidence_locators",
        }
        if (
            not isinstance(candidate, dict)
            or not required_candidate.issubset(candidate)
            or type(candidate["role"]) is not str
            or not candidate["role"]
            or candidate["role"] in candidate_roles
            or type(candidate["claimed_period"]) is not str
            or not isinstance(candidate["scope_evidence_locators"], list)
        ):
            raise QualificationError(
                code="LAYOUT_COMPARISON_INVALID",
                message="Reader candidate layout fields are invalid",
            )
        locator = candidate["locator"]
        geometry_fields = {
            "column_index", "colspan", "origin_column_index",
            "origin_row_index", "row_index", "rowspan",
        }
        if (
            not isinstance(locator, dict)
            or not geometry_fields.issubset(locator)
            or any(
                type(locator[field]) is not int
                for field in geometry_fields
            )
        ):
            raise QualificationError(
                code="LAYOUT_COMPARISON_INVALID",
                message="Reader candidate locator geometry is invalid",
            )
        role = str(candidate["role"])
        candidate_roles.add(role)
        selected.append({
            "role": role,
            "row_index": locator["row_index"],
            "column_index": locator["column_index"],
        })
        spans.append({
            "kind": "selected",
            "role": role,
            "rowspan": locator["rowspan"],
            "colspan": locator["colspan"],
        })
        for evidence in candidate["scope_evidence_locators"]:
            if (
                not isinstance(evidence, dict)
                or not {"location_type", "locator", "text"}.issubset(
                    evidence
                )
                or type(evidence["location_type"]) is not str
                or type(evidence["text"]) is not str
                or not isinstance(evidence["locator"], dict)
                or not geometry_fields.issubset(evidence["locator"])
                or any(
                    type(evidence["locator"][field]) is not int
                    for field in geometry_fields
                )
            ):
                raise QualificationError(
                    code="LAYOUT_COMPARISON_INVALID",
                    message="Reader scope locator geometry is invalid",
                )
            evidence_locator = evidence["locator"]
            spans.append({
                "kind": str(evidence["location_type"]),
                "role": role,
                "rowspan": evidence_locator["rowspan"],
                "colspan": evidence_locator["colspan"],
            })
            if evidence["location_type"] == "header":
                headers.append({
                    "role": role,
                    "text": evidence["text"],
                    "claimed_period": candidate["claimed_period"],
                    "row_index": evidence_locator["row_index"],
                    "column_index": evidence_locator["column_index"],
                    "rowspan": evidence_locator["rowspan"],
                    "colspan": evidence_locator["colspan"],
                })
            else:
                scopes.append({
                    "role": role,
                    "location_type": evidence["location_type"],
                    "text": evidence["text"],
                })
    if not candidate_roles:
        raise QualificationError(
            code="LAYOUT_COMPARISON_INVALID",
            message="Reader layout role exact set is empty",
        )
    selected.sort(
        key=lambda entry: (
            entry["column_index"], entry["row_index"], entry["role"],
        )
    )
    headers.sort(
        key=lambda entry: (
            entry["role"], entry["row_index"], entry["column_index"],
            entry["text"],
        )
    )
    scopes.sort(
        key=lambda entry: (
            entry["role"], entry["location_type"], entry["text"],
        )
    )
    spans.sort(
        key=lambda entry: (
            entry["role"], entry["kind"], entry["rowspan"],
            entry["colspan"],
        )
    )
    components = {
        "column_order": [entry["role"] for entry in selected],
        "rowspan_colspan": spans,
        "scope_wording": scopes,
        "table_header": [
            {"role": entry["role"], "text": entry["text"]}
            for entry in headers
        ],
        "year_layout": [
            {
                field: entry[field]
                for field in (
                    "claimed_period", "column_index", "colspan", "role",
                    "row_index", "rowspan",
                )
            }
            for entry in headers
        ],
    }
    component_ids = {
        kind: content_hash(value=components[kind])
        for kind in sorted(components)
    }
    body = {
        "schema_version": 1,
        "roles": sorted(candidate_roles),
        "grid_id": content_hash(value=normalized_cells),
        "component_ids": component_ids,
    }
    return {**body, "signature_id": content_hash(value=body)}


def _mechanical_layout_comparison(
    *, repo_root: Path, fixture: Mapping[str, object],
) -> Dict[str, object]:
    """Replay fixture differences against exact repository reference bytes.

    Args:
        repo_root: Repository containing candidate and reference fixture bytes.
        fixture: Candidate fixture/receipt paths, hashes, reason, and claims.

    Returns:
        Content-addressed comparison with independently derived dimensions.
    """
    required = {
        "excerpt_repo_relative_path",
        "excerpt_sha256",
        "layout_differences",
        "recorded_response_repo_relative_path",
        "recorded_response_sha256",
        "selection_reason",
    }
    if (
        not required.issubset(fixture)
        or type(fixture["selection_reason"]) is not str
        or not fixture["selection_reason"].strip()
        or not isinstance(fixture["layout_differences"], list)
        or len(fixture["layout_differences"]) < 2
        or len(fixture["layout_differences"])
        != len(set(fixture["layout_differences"]))
        or any(
            type(kind) is not str
            for kind in fixture["layout_differences"]
        )
        or not set(fixture["layout_differences"]).issubset(
            LAYOUT_DIFFERENCE_KINDS
        )
    ):
        raise QualificationError(
            code="LAYOUT_DIFFERENCE_INSUFFICIENT",
            message="Layout reason and declared differences are incomplete",
        )
    candidate_excerpt_path = _validate_hashed_file(
        repo_root=repo_root,
        receipt=fixture,
        path_field="excerpt_repo_relative_path",
        hash_field="excerpt_sha256",
        label="layout excerpt",
    )
    candidate_response_path = _validate_hashed_file(
        repo_root=repo_root,
        receipt=fixture,
        path_field="recorded_response_repo_relative_path",
        hash_field="recorded_response_sha256",
        label="recorded response",
    )
    reference_index_path = _portable_file(
        repo_root=repo_root,
        relative=LAYOUT_REFERENCE_INDEX.as_posix(),
        label="layout reference index",
    )
    reference_index = strict_json_file(path=reference_index_path)
    reference_index_fields = {
        "provenance_repo_relative_path",
        "provenance_sha256",
        "reference_id",
        "schema_version",
    }
    if (
        not isinstance(reference_index, dict)
        or set(reference_index) != reference_index_fields
        or reference_index["schema_version"] != 1
        or type(reference_index["reference_id"]) is not str
        or _SHA256_ID.fullmatch(reference_index["reference_id"]) is None
    ):
        raise QualificationError(
            code="LAYOUT_REFERENCE_INVALID",
            message="Layout reference index is invalid",
        )
    reference_index_body = {
        field: reference_index[field]
        for field in reference_index
        if field != "reference_id"
    }
    if content_hash(value=reference_index_body) != reference_index[
        "reference_id"
    ]:
        raise QualificationError(
            code="LAYOUT_REFERENCE_INVALID",
            message="Layout reference index identity differs",
        )
    provenance_path = _validate_hashed_file(
        repo_root=repo_root,
        receipt={
            "path": reference_index["provenance_repo_relative_path"],
            "sha256": reference_index["provenance_sha256"],
        },
        path_field="path",
        hash_field="sha256",
        label="layout reference provenance",
    )
    provenance = strict_json_file(path=provenance_path)
    if (
        not isinstance(provenance, dict)
        or "fixture_provenance_id" not in provenance
        or "excerpt_path" not in provenance
        or "excerpt_sha256" not in provenance
        or "response_path" not in provenance
        or "response_sha256" not in provenance
    ):
        raise QualificationError(
            code="LAYOUT_REFERENCE_INVALID",
            message="Layout reference provenance is incomplete",
        )
    provenance_body = {
        field: provenance[field]
        for field in provenance
        if field != "fixture_provenance_id"
    }
    if (
        content_hash(value=provenance_body)
        != provenance["fixture_provenance_id"]
    ):
        raise QualificationError(
            code="LAYOUT_REFERENCE_INVALID",
            message="Layout reference provenance identity differs",
        )
    reference_excerpt_path = _validate_hashed_file(
        repo_root=repo_root,
        receipt={
            "path": provenance["excerpt_path"],
            "sha256": provenance["excerpt_sha256"],
        },
        path_field="path",
        hash_field="sha256",
        label="reference layout excerpt",
    )
    reference_response_path = _validate_hashed_file(
        repo_root=repo_root,
        receipt={
            "path": provenance["response_path"],
            "sha256": provenance["response_sha256"],
        },
        path_field="path",
        hash_field="sha256",
        label="reference recorded response",
    )
    candidate_signature = _layout_signature(
        excerpt=strict_json_file(path=candidate_excerpt_path),
        response=strict_json_file(path=candidate_response_path),
    )
    reference_signature = _layout_signature(
        excerpt=strict_json_file(path=reference_excerpt_path),
        response=strict_json_file(path=reference_response_path),
    )
    if candidate_signature["roles"] != reference_signature["roles"]:
        raise QualificationError(
            code="LAYOUT_COMPARISON_INVALID",
            message="Candidate and reference role exact sets differ",
        )
    detected = sorted(
        kind
        for kind in LAYOUT_DIFFERENCE_KINDS
        if candidate_signature["component_ids"][kind]
        != reference_signature["component_ids"][kind]
    )
    declared = sorted(fixture["layout_differences"])
    if (
        candidate_signature["grid_id"] == reference_signature["grid_id"]
        or not set(declared).issubset(detected)
    ):
        raise QualificationError(
            code="LAYOUT_DIFFERENCE_NOT_REPLAYABLE",
            message="Declared layout differences do not follow from bytes",
        )
    body = {
        "schema_version": 1,
        "reference": {
            "reference_id": reference_index["reference_id"],
            "reference_index_repo_relative_path": (
                LAYOUT_REFERENCE_INDEX.as_posix()
            ),
            "reference_index_sha256": sha256_file(
                path=reference_index_path,
            ),
            "fixture_provenance_id": provenance["fixture_provenance_id"],
            "fixture_provenance_repo_relative_path": (
                reference_index["provenance_repo_relative_path"]
            ),
            "fixture_provenance_sha256": sha256_file(path=provenance_path),
            "excerpt_repo_relative_path": provenance["excerpt_path"],
            "excerpt_sha256": provenance["excerpt_sha256"],
            "recorded_response_repo_relative_path": provenance[
                "response_path"
            ],
            "recorded_response_sha256": provenance["response_sha256"],
            "grid_id": reference_signature["grid_id"],
            "signature_id": reference_signature["signature_id"],
        },
        "candidate": {
            "grid_id": candidate_signature["grid_id"],
            "signature_id": candidate_signature["signature_id"],
        },
        "detected_differences": detected,
        "verified_declared_differences": declared,
    }
    return {**body, "comparison_id": content_hash(value=body)}


def _validate_layout_receipt(
    *, repo_root: Path, receipt: Mapping[str, object], expected_type: str,
    freeze_tree_id: str,
    registry_identities: Mapping[str, Sequence[str]],
    freeze: Mapping[str, object],
) -> Dict[str, object]:
    """Verify one real layout through its persisted production Run graph.

    Args:
        repo_root: Repository containing fixture bytes and the frozen Run.
        receipt: Content-addressed layout qualification receipt.
        expected_type: ``SECOND_LAYOUT`` or ``POST_FREEZE_HOLDOUT``.
        freeze_tree_id: Tree frozen before the holdout was introduced.
        registry_identities: Formal production company and CIK exact sets.
        freeze: Verified production freeze with pre-holdout inventory.

    Returns:
        Minimal verified identity for the full acceptance receipt.
    """
    required = {
        "accession",
        "cik",
        "company_id",
        "document_name",
        "effective_human_decision_id",
        "excerpt_repo_relative_path",
        "excerpt_sha256",
        "fixture_id",
        "fixture_manifest_sha256",
        "layout_comparison",
        "layout_differences",
        "metric_result_ids",
        "production_semantic_tree_id",
        "receipt_id",
        "receipt_type",
        "recorded_response_repo_relative_path",
        "recorded_response_sha256",
        "review_context_hash",
        "review_unit_hash",
        "run_manifest_sha256",
        "run_repo_relative_path",
        "run_status",
        "run_validation_sha256",
        "schema_version",
        "selection_reason",
        "socket_count",
        "source_repo_relative_path",
        "source_sha256",
        "source_url",
    }
    if set(receipt) != required or receipt["schema_version"] != 1:
        raise QualificationError(
            code="LAYOUT_RECEIPT_INVALID",
            message="Layout receipt fields are not exact",
        )
    if receipt["receipt_type"] != expected_type:
        raise QualificationError(
            code="LAYOUT_RECEIPT_INVALID",
            message="Layout receipt role differs",
        )
    if type(receipt["fixture_id"]) is not str:
        raise QualificationError(
            code="LAYOUT_RECEIPT_INVALID",
            message="Layout fixture identity is invalid",
        )
    fixture = _layout_fixture_manifest(
        repo_root=repo_root, fixture_id=receipt["fixture_id"],
    )
    fixture_manifest_path = (
        repo_root / LAYOUT_FIXTURE_ROOT / str(receipt["fixture_id"])
        / "fixture_manifest.json"
    )
    bound_fixture_fields = (
        "accession",
        "cik",
        "company_id",
        "document_name",
        "excerpt_repo_relative_path",
        "excerpt_sha256",
        "layout_differences",
        "recorded_response_repo_relative_path",
        "recorded_response_sha256",
        "selection_reason",
        "source_repo_relative_path",
        "source_sha256",
        "source_url",
    )
    if (
        sha256_file(path=fixture_manifest_path)
        != receipt["fixture_manifest_sha256"]
        or any(
            fixture[field] != receipt[field]
            for field in bound_fixture_fields
        )
        or fixture["qualification_role"] != expected_type
    ):
        raise QualificationError(
            code="LAYOUT_RECEIPT_TAMPERED",
            message="Layout fixture manifest binding differs",
        )
    company_id = receipt["company_id"]
    if (
        type(company_id) is not str
        or company_id in registry_identities["company_ids"]
        or _normalized_cik(
            value=receipt["cik"], label="qualification company",
        ) in registry_identities["ciks"]
    ):
        raise QualificationError(
            code="LAYOUT_COMPANY_IN_PRODUCTION_REGISTRY",
            message="Qualification company or CIK aliases production",
        )
    differences = receipt["layout_differences"]
    if not isinstance(differences, list):
        raise QualificationError(
            code="LAYOUT_DIFFERENCE_INSUFFICIENT",
            message="At least two approved layout dimensions must differ",
        )
    comparison = _mechanical_layout_comparison(
        repo_root=repo_root, fixture=receipt,
    )
    if comparison != receipt["layout_comparison"]:
        raise QualificationError(
            code="LAYOUT_DIFFERENCE_NOT_REPLAYABLE",
            message="Persisted layout comparison differs from current replay",
        )
    if (
        receipt["production_semantic_tree_id"] != freeze_tree_id
        or receipt["socket_count"] != 0
        or receipt["run_status"] != "FROZEN"
    ):
        raise QualificationError(
            code="LAYOUT_RUN_NOT_RECORDED_FROZEN",
            message="Layout proof is not socket-zero and FROZEN",
        )
    source_path = _validate_hashed_file(
        repo_root=repo_root,
        receipt=receipt,
        path_field="source_repo_relative_path",
        hash_field="source_sha256",
        label="layout source",
    )
    _validate_hashed_file(
        repo_root=repo_root,
        receipt=receipt,
        path_field="excerpt_repo_relative_path",
        hash_field="excerpt_sha256",
        label="layout excerpt",
    )
    _validate_hashed_file(
        repo_root=repo_root,
        receipt=receipt,
        path_field="recorded_response_repo_relative_path",
        hash_field="recorded_response_sha256",
        label="recorded response",
    )
    source_match = (
        _SEC_ARCHIVE_SOURCE.fullmatch(receipt["source_url"])
        if type(receipt["source_url"]) is str
        else None
    )
    if (
        source_match is None
        or type(receipt["accession"]) is not str
        or _ACCESSION.fullmatch(receipt["accession"]) is None
        or type(receipt["document_name"]) is not str
        or type(receipt["source_sha256"]) is not str
        or _SHA256_HEX.fullmatch(receipt["source_sha256"]) is None
        or source_path.name != receipt["document_name"]
        or _normalized_cik(
            value=source_match.group(1), label="SEC source URL",
        ) != _normalized_cik(
            value=receipt["cik"], label="qualification company",
        )
        or source_match.group(2) != receipt["accession"].replace("-", "")
        or source_match.group(3) != receipt["document_name"]
    ):
        raise QualificationError(
            code="LAYOUT_SOURCE_IDENTITY_INVALID",
            message="Layout source is not one exact official SEC document",
        )
    run_relative = receipt["run_repo_relative_path"]
    if type(run_relative) is not str:
        raise QualificationError(
            code="LAYOUT_RUN_INVALID", message="Run locator is invalid",
        )
    run_path = repo_root / Path(run_relative)
    expected_parent = repo_root / QUALIFICATION_ROOT / "runs"
    expected_run_relative = (
        QUALIFICATION_RUN_ROOT / str(receipt["fixture_id"])
    ).as_posix()
    if (
        Path(run_relative).is_absolute()
        or ".." in Path(run_relative).parts
        or run_relative != expected_run_relative
        or expected_parent not in run_path.parents
        or run_path.is_symlink()
        or not run_path.is_dir()
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID", message="Run is outside qualification",
        )
    if expected_type == "POST_FREEZE_HOLDOUT":
        _validate_post_freeze_holdout(
            freeze=freeze, holdout=receipt,
        )
    manifest_path = _validate_hashed_file(
        repo_root=repo_root,
        receipt={
            "path": (Path(run_relative) / "manifest.json").as_posix(),
            "sha256": receipt["run_manifest_sha256"],
        },
        path_field="path",
        hash_field="sha256",
        label="layout Run manifest",
    )
    _validate_hashed_file(
        repo_root=repo_root,
        receipt={
            "path": (Path(run_relative) / "validation.json").as_posix(),
            "sha256": receipt["run_validation_sha256"],
        },
        path_field="path",
        hash_field="sha256",
        label="layout Run validation",
    )
    manifest, records, decisions = load_run_for_status(
        run_dir=run_path, repo_root=repo_root,
    )
    if (
        manifest_path != run_path / "manifest.json"
        or manifest["status"] != "FROZEN"
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID", message="Run is not exactly FROZEN",
        )
    if manifest["company_id"] != company_id:
        raise QualificationError(
            code="LAYOUT_RUN_INVALID",
            message="Run company identity differs",
        )
    source_references = manifest["source_references"]
    if len(source_references) != 1:
        raise QualificationError(
            code="LAYOUT_RUN_INVALID", message="Run source exact set differs",
        )
    source = source_references[0]
    if (
        source["source_url"] != receipt["source_url"]
        or source["accession"] != receipt["accession"]
        or source["document_name"] != receipt["document_name"]
        or source["raw_asset_id"] != "sha256:" + receipt["source_sha256"]
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID", message="Run source binding differs",
        )
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    candidates = [
        record
        for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
    ]
    derived_assets = [
        record
        for record in records
        if record["record_type"] == "DERIVED_ASSET"
    ]
    results = [
        record
        for record in records
        if record["record_type"] == "METRIC_RESULT"
    ]
    attempts = [
        record
        for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    evidence = [
        record
        for record in records
        if record["record_type"] == "EVIDENCE_CHECK"
    ]
    if (
        len(units) != 1
        or len(candidates) != 1
        or len(derived_assets) != 1
        or len(attempts) != 1
        or len(evidence) != 1
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID",
            message="Run did not traverse Reader, Evidence, and Review",
        )
    if (
        attempts[0]["assistant_output_sha256"]
        != receipt["recorded_response_sha256"]
        or candidates[0]["assistant_output_sha256"]
        != receipt["recorded_response_sha256"]
        or candidates[0]["attempt_id"] != attempts[0]["attempt_id"]
        or evidence[0]["candidate_hash"] != candidates[0]["candidate_hash"]
        or units[0]["selected"] != candidates[0]["selected"]
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID",
            message="Run Reader response binding differs",
        )
    excerpt = strict_json_file(
        path=repo_root / str(receipt["excerpt_repo_relative_path"])
    )
    if (
        excerpt["derived_asset_id"]
        != derived_assets[0]["derived_asset_id"]
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID",
            message="Layout excerpt names a different table grid",
        )
    for cell in excerpt["cells"]:
        locator = {
            "derived_asset_id": excerpt["derived_asset_id"],
            "table_id": excerpt["table_id"],
            **{
                field: cell[field]
                for field in (
                    "column_index", "colspan", "origin_column_index",
                    "origin_row_index", "row_index", "rowspan",
                )
            },
        }
        try:
            resolved = resolve_cell(
                derived_asset=derived_assets[0], locator=locator,
            )
        except TableGridError as error:
            raise QualificationError(
                code="LAYOUT_RUN_INVALID",
                message="Layout excerpt locator differs from Run grid",
            ) from error
        if resolved["text"] != cell["text"]:
            raise QualificationError(
                code="LAYOUT_RUN_INVALID",
                message="Layout excerpt text differs from Run grid",
            )
    decision = effective_review_decision(
        review_unit=units[0], decisions=decisions,
    )
    required_traits = set(
        units[0]["compiled_spec"]["applicability"]["all"]
    )
    expected_metric_ids = set(
        units[0]["compiled_spec"]["legacy_projection"][
            "role_metric_ids"
        ].values()
    )
    result_ids = {
        record["metric_id"]: record["result_id"] for record in results
    }
    validation = _layout_validation_receipt(run_path=run_path)
    _require_qualified_layout_terminal(
        decision=decision,
        results=results,
        validation=validation,
        expected_metric_ids=tuple(expected_metric_ids),
    )
    if (
        not required_traits.issubset(set(manifest["company_traits"]))
        or result_ids != receipt["metric_result_ids"]
        or units[0]["review_unit_hash"] != receipt["review_unit_hash"]
        or units[0]["review_context_hash"] != receipt["review_context_hash"]
        or decision["review_decision_id"]
        != receipt["effective_human_decision_id"]
    ):
        raise QualificationError(
            code="LAYOUT_RUN_INVALID",
            message="Run result or HUMAN review binding differs",
        )
    return {
        "receipt_id": receipt["receipt_id"],
        "fixture_id": receipt["fixture_id"],
        "company_id": company_id,
        "cik": _normalized_cik(
            value=receipt["cik"], label="qualification company",
        ),
        "accession": receipt["accession"],
        "source_sha256": receipt["source_sha256"],
        "selection_reason": receipt["selection_reason"],
        "layout_comparison_id": comparison["comparison_id"],
        "run_id": manifest["run_id"],
        "review_unit_hash": units[0]["review_unit_hash"],
    }


def validate_cutover_qualifications(*, repo_root: Path) -> Dict[str, object]:
    """Require pre-holdout freeze plus two independent real layout Runs.

    Args:
        repo_root: Fixed repository containing the formal evidence namespace.

    Returns:
        Exact qualification identities for the Cutover/full receipt.
    """
    manifest_path = repo_root / QUALIFICATION_MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise QualificationError(
            code="CUTOVER_QUALIFICATION_REQUIRED",
            message="Second-layout and post-freeze holdout evidence is absent",
        )
    manifest = strict_json_file(path=manifest_path)
    if not isinstance(manifest, dict) or set(manifest) != {
        "holdout_receipt",
        "production_freeze_receipt",
        "schema_version",
        "second_layout_receipt",
    } or manifest["schema_version"] != 1:
        raise QualificationError(
            code="QUALIFICATION_MANIFEST_INVALID",
            message="Qualification manifest fields are not exact",
        )
    try:
        table_contracts = load_table_task_contracts(repo_root=repo_root)
        for family_id in table_contracts["authorized_family_ids"]:
            require_table_qualification_freeze(
                repo_root=repo_root, family_id=family_id,
            )
    except (TableQualificationFreezeError, ValueError) as error:
        raise QualificationError(
            code="TABLE_QUALIFICATION_FREEZE_REQUIRED",
            message="Table qualification freeze is absent or invalid",
        ) from error
    freeze = _validate_addressed_receipt(
        repo_root=repo_root,
        reference=manifest["production_freeze_receipt"],
        label="production freeze",
    )
    required_freeze = {
        "frozen_at_utc",
        "receipt_id",
        "receipt_type",
        "schema_version",
        "second_layout_receipt_id",
        "semantic_files",
        "semantic_tree_id",
        "pre_holdout_inventory",
    }
    if (
        set(freeze) != required_freeze
        or freeze["schema_version"] != 1
        or freeze["receipt_type"] != "PRODUCTION_SEMANTIC_FREEZE"
    ):
        raise QualificationError(
            code="PRODUCTION_FREEZE_RECEIPT_INVALID",
            message="Production freeze receipt fields are not exact",
        )
    current_tree = production_semantic_tree(repo_root=repo_root)
    _validated_pre_holdout_inventory(
        inventory=freeze["pre_holdout_inventory"],
    )
    if (
        current_tree["semantic_tree_id"] != freeze["semantic_tree_id"]
        or current_tree["files"] != freeze["semantic_files"]
        or not isinstance(manifest["second_layout_receipt"], dict)
        or freeze["second_layout_receipt_id"]
        != manifest["second_layout_receipt"]["receipt_id"]
    ):
        raise QualificationError(
            code="POST_FREEZE_PRODUCTION_DRIFT",
            message="Production semantics changed after holdout freeze",
        )
    registry = _registry_identities(repo_root=repo_root)
    second = _validate_layout_receipt(
        repo_root=repo_root,
        receipt=_validate_addressed_receipt(
            repo_root=repo_root,
            reference=manifest["second_layout_receipt"],
            label="second layout",
        ),
        expected_type="SECOND_LAYOUT",
        freeze_tree_id=str(freeze["semantic_tree_id"]),
        registry_identities=registry,
        freeze=freeze,
    )
    holdout = _validate_layout_receipt(
        repo_root=repo_root,
        receipt=_validate_addressed_receipt(
            repo_root=repo_root,
            reference=manifest["holdout_receipt"],
            label="post-freeze holdout",
        ),
        expected_type="POST_FREEZE_HOLDOUT",
        freeze_tree_id=str(freeze["semantic_tree_id"]),
        registry_identities=registry,
        freeze=freeze,
    )
    _validate_independent_layouts(second=second, holdout=holdout)
    body = {
        "schema_version": 1,
        "production_freeze_receipt_id": freeze["receipt_id"],
        "production_semantic_tree_id": freeze["semantic_tree_id"],
        "second_layout": second,
        "post_freeze_holdout": holdout,
    }
    return {**body, "qualification_id": content_hash(value=body)}


def qualification_closure_paths(*, repo_root: Path) -> Sequence[str]:
    """Derive every file needed to audit the verified qualification offline.

    Args:
        repo_root: Repository containing the fixed qualification namespace.

    Returns:
        Sorted repository-relative exact file set; unreferenced siblings are
        deliberately excluded.
    """
    validate_cutover_qualifications(repo_root=repo_root)
    manifest = strict_json_file(path=repo_root / QUALIFICATION_MANIFEST)
    paths = {QUALIFICATION_MANIFEST.as_posix()}
    for role in (
        "production_freeze_receipt",
        "second_layout_receipt",
        "holdout_receipt",
    ):
        reference = manifest[role]
        paths.add(str(reference["receipt_path"]))
        receipt = strict_json_file(
            path=repo_root / str(reference["receipt_path"])
        )
        if role == "production_freeze_receipt":
            paths.update(str(value) for value in receipt["semantic_files"])
            continue
        fixture_root = (
            LAYOUT_FIXTURE_ROOT / str(receipt["fixture_id"])
        )
        paths.add((fixture_root / "fixture_manifest.json").as_posix())
        for field in (
            "excerpt_repo_relative_path",
            "recorded_response_repo_relative_path",
            "source_repo_relative_path",
        ):
            paths.add(str(receipt[field]))
        reference = receipt["layout_comparison"]["reference"]
        for field in (
            "excerpt_repo_relative_path",
            "fixture_provenance_repo_relative_path",
            "reference_index_repo_relative_path",
            "recorded_response_repo_relative_path",
        ):
            paths.add(str(reference[field]))
        run_root = repo_root / str(receipt["run_repo_relative_path"])
        for path in sorted(run_root.rglob("*")):
            if path.is_symlink():
                raise QualificationError(
                    code="LAYOUT_RUN_INVALID",
                    message="Qualification Run contains a symlink",
                )
            if path.is_file():
                paths.add(path.relative_to(repo_root).as_posix())
    for relative in paths:
        _portable_file(
            repo_root=repo_root,
            relative=relative,
            label="qualification closure file",
        )
    return sorted(paths)
