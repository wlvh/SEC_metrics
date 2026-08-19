"""Validate strict record schemas used by vNext Runs and publications."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Dict, Mapping, Optional, Set, Tuple

from sec_http import validate_official_sec_url

from .canonical import CanonicalError, canonical_json_bytes, content_hash
from .canonical import decimal_text, parse_decimal, parse_utc_timestamp
from .specs import SEMANTIC_SET_PATHS
from .states import validate_state


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_./-]{2,255}$")


@dataclass(frozen=True)
class RecordSchema:
    """Declare exact required and optional fields for one record type.

    Attributes:
        required: Fields every record must contain.
        optional: Fields a record may additionally contain.
    """

    required: Tuple[str, ...]
    optional: Tuple[str, ...] = ()


SCHEMAS: Dict[str, RecordSchema] = {
    "AI_EXTRACTION_ATTEMPT": RecordSchema(
        required=(
            "record_type",
            "attempt_id",
            "status",
            "provider",
            "model",
            "model_requested",
            "model_returned",
            "api",
            "endpoint_host",
            "transport_observation",
            "sampling_parameters",
            "reader_input_manifest_hash",
            "request_body_sha256",
            "request_body_path",
            "reader_payload_sha256",
            "reader_payload_path",
            "task_contract_sha256",
            "task_contract_path",
            "task_spec_semantic_hash",
            "output_schema_sha256",
            "output_schema_path",
            "assistant_output_sha256",
            "assistant_output_path",
            "raw_response_sha256",
            "raw_response_path",
            "provider_request_id",
            "started_at_utc",
            "finished_at_utc",
            "error_class",
        )
    ),
    "DERIVED_ASSET": RecordSchema(
        required=(
            "record_type",
            "derived_asset_id",
            "parent_raw_asset_ids",
            "transform_id",
            "transform_semantic_version",
            "content_type",
            "storage_uri",
            "tables",
        )
    ),
    "EVIDENCE_CHECK": RecordSchema(
        required=(
            "record_type",
            "evidence_check_id",
            "candidate_hash",
            "status",
            "normalized_values",
            "checks",
            "reason_codes",
            "identity_constraints",
        )
    ),
    "EXECUTION_TRACE": RecordSchema(
        required=(
            "record_type",
            "trace_id",
            "metric_id",
            "calculation_target",
            "input_observation_ids",
            "steps",
            "quality",
            "result",
            "spec_closure_hash",
            "execution_semantics_hash",
            "result_contract_hash",
        )
    ),
    "METRIC_RESULT": RecordSchema(
        required=(
            "record_type",
            "result_id",
            "company_id",
            "metric_id",
            "period_start",
            "period_end",
            "scope_key",
            "spec_closure_hash",
            "applicability",
            "quality",
            "publication",
            "reason_code",
            "value",
            "unit",
            "trace_id",
        )
    ),
    "OBSERVATION_CANDIDATE": RecordSchema(
        required=(
            "record_type",
            "candidate_hash",
            "attempt_id",
            "assistant_output_sha256",
            "disclosure_group",
            "source_reference_ids",
            "derived_asset_ids",
            "selected",
            "competing_candidates",
            "unresolved_competing_claims",
            "status",
        )
    ),
    "PUBLICATION_MANIFEST": RecordSchema(
        required=(
            "record_type",
            "publication_id",
            "candidate_status",
            "requirement_hashes",
            "batch_manifest_id",
            "projection_manifest_id",
            "validation_receipt_id",
            "files",
            "ledger_binding",
            "previous_publication_id",
        )
    ),
    "RAW_BLOB": RecordSchema(
        required=(
            "record_type",
            "raw_asset_id",
            "byte_length",
            "media_type",
            "storage_uri",
        )
    ),
    "READER_INPUT_MANIFEST": RecordSchema(
        required=(
            "record_type",
            "reader_input_manifest_id",
            "derived_asset_id",
            "source_reference_ids",
            "tables",
        )
    ),
    "REVIEW_DECISION": RecordSchema(
        required=(
            "record_type",
            "review_decision_id",
            "review_unit_hash",
            "decision",
            "approved_claims",
            "reviewed_spec_semantic_hash",
            "reviewed_source_bindings",
            "review_context_hash",
            "rendered_review_hash",
            "review_renderer_semantic_version",
            "reviewer_type",
            "reviewer_id",
            "decided_at_utc",
            "reason",
            "supersedes_decision_id",
            "approval_effect_hash",
        )
    ),
    "REVIEW_UNIT": RecordSchema(
        required=(
            "record_type",
            "review_unit_hash",
            "status",
            "selected",
            "competing_candidates",
            "unresolved_competing_claims",
            "candidate_hashes",
            "source_bindings",
            "spec_semantic_hash",
            "compiled_spec",
            "required_claims",
            "evidence_check_id",
            "review_context_hash",
            "rendered_review_hash",
            "review_renderer_semantic_version",
        )
    ),
    "RUN": RecordSchema(
        required=(
            "record_type",
            "run_id",
            "status",
            "company_id",
            "company_traits",
            "target_period",
            "source_references",
            "missing_required_source_roles",
            "spec_file_hashes",
            "requirement_hashes",
            "records_file_hash",
            "review_decisions_file_hash",
            "validation_file_hash",
            "content_manifest_hash",
            "audit_manifest_hash",
            "execution_semantics_hash",
        )
    ),
    "SOURCE_REFERENCE": RecordSchema(
        required=(
            "record_type",
            "source_reference_id",
            "raw_asset_id",
            "company_id",
            "source_url",
            "accession",
            "document_name",
            "source_role",
            "request_attempt_id",
        )
    ),
    "DETERMINISTIC_VERIFIED_CLAIM": RecordSchema(
        required=(
            "record_type",
            "verified_claim_id",
            "claim_kind",
            "company_id",
            "source_reference_id",
            "source_role",
            "source_set_manifest_id",
            "locator",
            "value",
            "unit",
            "attributes",
        )
    ),
    "VALIDATION_RECEIPT": RecordSchema(
        required=(
            "record_type",
            "validation_receipt_id",
            "status",
            "view_id",
            "checks",
            "artifact_hashes",
        )
    ),
    "VERIFIED_OBSERVATION": RecordSchema(
        required=(
            "record_type",
            "observation_id",
            "metric_id",
            "semantic_role",
            "company_id",
            "period_start",
            "period_end",
            "scope",
            "scope_key",
            "value",
            "unit",
            "quality",
            "source_binding",
            "approval_effect_hash",
        )
    ),
}


TEXT_FIELDS = {
    "accession",
    "applicability",
    "approval_effect_hash",
    "attempt_id",
    "audit_manifest_hash",
    "batch_manifest_id",
    "candidate_hash",
    "candidate_status",
    "claim_kind",
    "company_id",
    "content_manifest_hash",
    "content_type",
    "decided_at_utc",
    "decision",
    "derived_asset_id",
    "disclosure_group",
    "document_name",
    "endpoint_host",
    "error_class",
    "evidence_check_id",
    "execution_semantics_hash",
    "finished_at_utc",
    "media_type",
    "metric_id",
    "model",
    "model_requested",
    "model_returned",
    "api",
    "observation_id",
    "period_end",
    "period_start",
    "provider",
    "provider_request_id",
    "publication",
    "publication_id",
    "projection_manifest_id",
    "quality",
    "raw_asset_id",
    "raw_response_sha256",
    "raw_response_path",
    "reader_payload_sha256",
    "reader_payload_path",
    "reader_input_manifest_hash",
    "reader_input_manifest_id",
    "reason",
    "reason_code",
    "record_type",
    "records_file_hash",
    "rendered_review_hash",
    "request_attempt_id",
    "request_body_sha256",
    "request_body_path",
    "output_schema_sha256",
    "output_schema_path",
    "assistant_output_sha256",
    "assistant_output_path",
    "result_id",
    "result_contract_hash",
    "review_context_hash",
    "review_decision_id",
    "review_decisions_file_hash",
    "review_renderer_semantic_version",
    "review_unit_hash",
    "reviewed_spec_semantic_hash",
    "reviewer_id",
    "reviewer_type",
    "run_id",
    "scope_key",
    "semantic_role",
    "source_reference_id",
    "source_role",
    "source_set_manifest_id",
    "source_url",
    "spec_closure_hash",
    "spec_semantic_hash",
    "started_at_utc",
    "status",
    "storage_uri",
    "task_contract_path",
    "task_contract_sha256",
    "task_spec_semantic_hash",
    "trace_id",
    "transform_id",
    "transform_semantic_version",
    "validation_file_hash",
    "validation_receipt_id",
    "verified_claim_id",
    "view_id",
}
OPTIONAL_TEXT_FIELDS = {
    "previous_publication_id",
    "result",
    "supersedes_decision_id",
    "unit",
    "value",
}
LIST_FIELDS = {
    "candidate_hashes",
    "checks",
    "company_traits",
    "competing_candidates",
    "derived_asset_ids",
    "files",
    "input_observation_ids",
    "identity_constraints",
    "missing_required_source_roles",
    "parent_raw_asset_ids",
    "reason_codes",
    "reviewed_source_bindings",
    "source_bindings",
    "source_reference_ids",
    "source_references",
    "steps",
    "tables",
    "unresolved_competing_claims",
}
MAPPING_FIELDS = {
    "approved_claims",
    "artifact_hashes",
    "calculation_target",
    "compiled_spec",
    "ledger_binding",
    "normalized_values",
    "requirement_hashes",
    "required_claims",
    "sampling_parameters",
    "scope",
    "selected",
    "attributes",
    "locator",
    "source_binding",
    "spec_file_hashes",
    "target_period",
    "transport_observation",
}
INTEGER_FIELDS = {"byte_length"}

METRIC_RESULT_CONTRACT_FIELDS = (
    "company_id",
    "metric_id",
    "period_start",
    "period_end",
    "scope_key",
    "spec_closure_hash",
    "applicability",
    "quality",
    "publication",
    "reason_code",
    "value",
    "unit",
)


class RecordError(ValueError):
    """Report a malformed, unknown, or semantically invalid record."""


def metric_result_contract_hash(*, result: Mapping[str, object]) -> str:
    """Hash every MetricResult field whose meaning precedes its Trace ID.

    Args:
        result: MetricResult body or complete record.

    Returns:
        Acyclic hash that lets an ExecutionTrace bind the complete outcome.

    Raises:
        RecordError: When a required result-contract field is missing.
    """
    missing = sorted(set(METRIC_RESULT_CONTRACT_FIELDS) - set(result))
    if missing:
        raise RecordError(
            "MetricResult contract fields are missing: {}".format(
                ",".join(missing)
            )
        )
    body = {
        field: result[field] for field in METRIC_RESULT_CONTRACT_FIELDS
    }
    return content_hash(value=body)


def _utc_timestamp(*, value: str, field: str) -> datetime:
    """Parse one timezone-aware UTC record timestamp.

    Args:
        value: ISO-8601 text using ``Z`` or an explicit zero offset.
        field: Diagnostic field name.

    Returns:
        Parsed UTC datetime.

    Raises:
        RecordError: When the text is invalid, naive, or non-UTC.
    """
    try:
        return parse_utc_timestamp(value=value)
    except CanonicalError as error:
        raise RecordError("Record {} must be UTC".format(field)) from error


def _validate_field_types(*, record: Mapping[str, object]) -> None:
    """Require every top-level field to use its exact JSON shape.

    Args:
        record: Exact-field record mapping.

    Raises:
        RecordError: On an unclassified field or wrong top-level JSON type.
    """
    for field in record:
        value = record[field]
        valid = (
            (field in TEXT_FIELDS and type(value) is str)
            or (
                field in OPTIONAL_TEXT_FIELDS
                and (value is None or type(value) is str)
            )
            or (field in LIST_FIELDS and type(value) is list)
            or (field in MAPPING_FIELDS and type(value) is dict)
            or (field in INTEGER_FIELDS and type(value) is int)
        )
        if not valid:
            raise RecordError(
                "Record field type is invalid: {}".format(field)
            )


def validate_identifier(*, value: object, field: str) -> str:
    """Return one bounded opaque identifier.

    Args:
        value: Candidate identifier.
        field: Diagnostic field name.

    Returns:
        Valid identifier string.

    Raises:
        RecordError: When the value is absent, too short, too long, or contains
            unapproved characters.
    """
    if (
        not isinstance(value, str)
        or IDENTIFIER_PATTERN.fullmatch(value) is None
    ):
        raise RecordError("Invalid {} identifier".format(field))
    return value


def validate_run_coordinates(
    *, target_period: object, company_traits: object
) -> None:
    """Validate the exact business coordinates owned by a Run manifest.

    Args:
        target_period: Exact fiscal year and period start/end mapping.
        company_traits: Ordered unique applicability traits.

    Raises:
        RecordError: On wrong shape, invalid ISO dates, or duplicate traits.
    """
    if not isinstance(target_period, dict) or set(target_period) != {
        "fiscal_year",
        "period_start",
        "period_end",
    }:
        raise RecordError("Run target period fields are not exact")
    if type(target_period["fiscal_year"]) is not int:
        raise RecordError("Run fiscal_year must be an integer")
    fiscal_year = target_period["fiscal_year"]
    if type(target_period["period_start"]) is not str or type(
        target_period["period_end"]
    ) is not str:
        raise RecordError("Run period dates must be text")
    if any(
        re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", target_period[field])
        is None
        for field in ("period_start", "period_end")
    ):
        raise RecordError("Run period dates must use YYYY-MM-DD")
    try:
        period_start = date.fromisoformat(target_period["period_start"])
        period_end = date.fromisoformat(target_period["period_end"])
    except ValueError as error:
        raise RecordError("Run period dates must be ISO dates") from error
    if period_end < period_start:
        raise RecordError("Run period ends before it starts")
    # A named fiscal year may end in the following calendar year, but it must
    # occur inside the exact period and cannot describe more than 53 weeks.
    if not period_start.year <= fiscal_year <= period_end.year:
        raise RecordError("Run fiscal_year falls outside its exact period")
    if (period_end - period_start).days + 1 > 371:
        raise RecordError("Run target period exceeds 53 weeks")
    if type(company_traits) is not list or (
        any(
            not isinstance(trait, str) or not trait
            for trait in company_traits
        )
        or len(company_traits) != len(set(company_traits))
    ):
        raise RecordError("Run company traits must be unique strings")


def require_exact_fields(
    *, record: Mapping[str, object], schema: RecordSchema
) -> None:
    """Require exact required/optional record fields.

    Args:
        record: Candidate record mapping.
        schema: Exact field contract.

    Raises:
        RecordError: On missing or unknown fields.
    """
    required = set(schema.required)
    allowed = required | set(schema.optional)
    missing = sorted(required - set(record))
    unknown = sorted(set(record) - allowed)
    if missing:
        raise RecordError(
            "Missing record fields: {}".format(",".join(missing))
        )
    if unknown:
        raise RecordError(
            "Unknown record fields: {}".format(",".join(unknown))
        )


def _validate_record_status(
    *, record_type: str, record: Mapping[str, object]
) -> None:
    """Validate state fields whose record owns an independent state machine.

    Args:
        record_type: Exact record type.
        record: Candidate record.

    Expected output:
        Known state-bearing records return normally; records without a state
        machine are intentionally ignored here.
    """
    state_types = {
        "AI_EXTRACTION_ATTEMPT": "AI_EXTRACTION_ATTEMPT",
        "REVIEW_UNIT": "REVIEW_UNIT",
        "RUN": "RUN",
        "VALIDATION_RECEIPT": "VALIDATION_RECEIPT",
    }
    if record_type not in state_types:
        return
    validate_state(
        object_type=state_types[record_type], status=str(record["status"]),
    )


def _expected_identifier(
    *, record_type: str, record: Mapping[str, object]
) -> Optional[Tuple[str, str]]:
    """Return a recomputable primary ID field and expected value.

    Args:
        record_type: Exact record type.
        record: Schema-valid record.

    Returns:
        ``(field, expected_id)`` for content-addressed records, otherwise
        ``None`` for externally/randomly identified audit objects.
    """
    if record_type == "SOURCE_REFERENCE":
        body = {
            key: record[key]
            for key in (
                "raw_asset_id",
                "company_id",
                "source_url",
                "accession",
                "document_name",
                "source_role",
            )
        }
        return "source_reference_id", content_hash(value=body)
    if record_type == "DETERMINISTIC_VERIFIED_CLAIM":
        body = {
            key: record[key]
            for key in (
                "record_type",
                "claim_kind",
                "company_id",
                "source_reference_id",
                "source_role",
                "source_set_manifest_id",
                "locator",
                "value",
                "unit",
                "attributes",
            )
        }
        return "verified_claim_id", content_hash(value=body)
    if record_type == "DERIVED_ASSET":
        body = {
            key: record[key]
            for key in (
                "parent_raw_asset_ids",
                "transform_id",
                "transform_semantic_version",
                "content_type",
                "tables",
            )
        }
        return "derived_asset_id", content_hash(value=body)
    if record_type == "READER_INPUT_MANIFEST":
        body = {
            key: record[key]
            for key in ("derived_asset_id", "source_reference_ids", "tables",)
        }
        return "reader_input_manifest_id", content_hash(value=body)
    if record_type == "OBSERVATION_CANDIDATE":
        body = {
            key: record[key]
            for key in (
                "disclosure_group",
                "source_reference_ids",
                "derived_asset_ids",
                "selected",
                "competing_candidates",
                "unresolved_competing_claims",
            )
        }
        return "candidate_hash", content_hash(value=body)
    if record_type == "EVIDENCE_CHECK":
        body = {
            key: record[key]
            for key in (
                "candidate_hash",
                "status",
                "normalized_values",
                "checks",
                "reason_codes",
                "identity_constraints",
            )
        }
        return "evidence_check_id", content_hash(value=body)
    if record_type == "REVIEW_UNIT":
        body = {
            key: record[key]
            for key in (
                "selected",
                "competing_candidates",
                "unresolved_competing_claims",
                "candidate_hashes",
                "source_bindings",
                "spec_semantic_hash",
                "compiled_spec",
                "required_claims",
                "evidence_check_id",
                "review_context_hash",
                "rendered_review_hash",
                "review_renderer_semantic_version",
            )
        }
        return "review_unit_hash", content_hash(value=body)
    if record_type == "VERIFIED_OBSERVATION":
        body = {
            key: record[key]
            for key in (
                "semantic_role",
                "metric_id",
                "company_id",
                "period_start",
                "period_end",
                "scope",
                "scope_key",
                "value",
                "unit",
                "source_binding",
            )
        }
        return "observation_id", content_hash(value=body)
    if record_type == "EXECUTION_TRACE":
        body = {
            key: record[key]
            for key in (
                "metric_id",
                "calculation_target",
                "input_observation_ids",
                "steps",
                "quality",
                "result",
                "spec_closure_hash",
                "execution_semantics_hash",
                "result_contract_hash",
            )
        }
        return "trace_id", content_hash(value=body)
    if record_type == "METRIC_RESULT":
        body = {
            key: record[key]
            for key in (
                "company_id",
                "metric_id",
                "period_start",
                "period_end",
                "scope_key",
                "spec_closure_hash",
                "applicability",
                "quality",
                "publication",
                "reason_code",
                "value",
                "unit",
                "trace_id",
            )
        }
        return "result_id", content_hash(value=body)
    if record_type == "VALIDATION_RECEIPT":
        body = {
            key: record[key]
            for key in ("status", "view_id", "checks", "artifact_hashes")
        }
        return "validation_receipt_id", content_hash(value=body)
    if record_type == "PUBLICATION_MANIFEST":
        body = {
            key: record[key]
            for key in (
                "candidate_status",
                "requirement_hashes",
                "batch_manifest_id",
                "projection_manifest_id",
                "validation_receipt_id",
                "files",
                "ledger_binding",
                "previous_publication_id",
            )
        }
        expected = "publication_" + content_hash(value=body).split(":", 1)[1]
        return "publication_id", expected
    return None


def _validate_decision_hashes(*, record: Mapping[str, object]) -> None:
    """Recompute ReviewDecision audit and approval-effect identities.

    Args:
        record: Strict REVIEW_DECISION mapping.

    Raises:
        RecordError: When either identity differs from substantive bytes.
    """
    approval_fields = (
        "review_unit_hash",
        "decision",
        "approved_claims",
        "reviewed_spec_semantic_hash",
        "reviewed_source_bindings",
        "review_context_hash",
        "rendered_review_hash",
        "review_renderer_semantic_version",
    )
    approval = {key: record[key] for key in approval_fields}
    if record["approval_effect_hash"] != content_hash(value=approval):
        raise RecordError("ReviewDecision approval effect hash differs")
    audit = dict(approval)
    for key in (
        "reviewer_type",
        "reviewer_id",
        "decided_at_utc",
        "reason",
        "supersedes_decision_id",
    ):
        audit[key] = record[key]
    if record["review_decision_id"] != content_hash(value=audit):
        raise RecordError("ReviewDecision audit identity differs")


def _validate_enums(*, record_type: str, record: Mapping[str, object]) -> None:
    """Reject unknown contract enumerations not owned by a state machine.

    Args:
        record_type: Exact record type.
        record: Schema-valid record.
    """
    if record_type == "OBSERVATION_CANDIDATE" and record["status"] not in {
        "CANDIDATE",
        "REVIEW_REQUIRED",
    }:
        raise RecordError("Candidate status is invalid")
    if record_type == "EVIDENCE_CHECK" and record["status"] not in {
        "PASS",
        "REJECTED",
    }:
        raise RecordError("Evidence status is invalid")
    if record_type == "REVIEW_DECISION":
        if record["decision"] not in {"APPROVE", "REJECT"}:
            raise RecordError("Review decision is invalid")
        if record["reviewer_type"] not in {"HUMAN", "SYSTEM"}:
            raise RecordError("Review decision reviewer type is invalid")
    if record_type == "OBSERVATION_CANDIDATE" and re.fullmatch(
        r"[0-9a-f]{64}", str(record["assistant_output_sha256"])
    ) is None:
        raise RecordError("Candidate assistant output digest is invalid")
    if record_type == "VERIFIED_OBSERVATION" and record["quality"] not in {
        "EXACT",
        "APPROX",
    }:
        raise RecordError("Observation quality is invalid")
    if record_type == "METRIC_RESULT":
        if record["applicability"] not in {"APPLICABLE", "N_A_STRUCTURAL"}:
            raise RecordError("Result applicability is invalid")
        if record["quality"] not in {
            "EXACT",
            "APPROX",
            "NOT_MEANINGFUL",
            "NONE",
        }:
            raise RecordError("Result quality is invalid")
        if record["publication"] not in {"PUBLISHED", "WITHHELD"}:
            raise RecordError("Result publication state is invalid")
    if (
        record_type == "PUBLICATION_MANIFEST"
        and record["candidate_status"] != "PUBLISHABLE"
    ):
        raise RecordError("Committed publication must be PUBLISHABLE")
    if record_type == "SOURCE_REFERENCE":
        # Constructor checks are not an authority boundary: frozen Runs reload
        # caller-supplied records, so the schema validator must reapply the
        # production SEC client's exact-origin rule.
        try:
            validate_official_sec_url(url=str(record["source_url"]))
        except ValueError as error:
            raise RecordError(
                "SourceReference URL must use an official SEC origin"
            ) from error


def _validate_record_semantics(
    *, record_type: str, record: Mapping[str, object]
) -> None:
    """Reapply constructor invariants when records are loaded from disk.

    Args:
        record_type: Exact record type.
        record: Exact-field, canonical record.

    Raises:
        RecordError: When a caller-crafted record bypasses a constructor's
            temporal, sampling, or raw-byte invariants.
    """
    if record_type == "RUN":
        validate_run_coordinates(
            target_period=record["target_period"],
            company_traits=record["company_traits"],
        )
    if record_type == "AI_EXTRACTION_ATTEMPT":
        observation = record["transport_observation"]
        observation_fields = {
            "egress_attempted",
            "provider",
            "model",
            "model_requested",
            "model_returned",
            "api",
            "store",
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
        if not isinstance(observation, dict) or set(observation) != (
            observation_fields
        ):
            raise RecordError("Attempt transport observation fields differ")
        for field in (
            "provider",
            "model",
            "model_requested",
            "model_returned",
            "api",
            "endpoint_host",
            "region",
            "retention",
            "data_use",
            "filing_egress_policy",
        ):
            if type(observation[field]) is not str or not observation[field]:
                raise RecordError(
                    "Attempt transport observation text is invalid"
                )
        if type(observation["egress_attempted"]) is not bool:
            raise RecordError("Attempt egress observation must be boolean")
        if type(observation["store"]) is not bool or observation["store"]:
            raise RecordError("Attempt must explicitly use store=false")
        for field in (
            "timeout_seconds",
            "retry_count",
            "retries_performed",
            "maximum_payload_bytes",
            "request_body_bytes",
        ):
            if type(observation[field]) is not int or observation[field] < 0:
                raise RecordError(
                    "Attempt transport observation count is invalid"
                )
        if observation["request_body_bytes"] < 1:
            raise RecordError("Attempt request byte count is invalid")
        if observation["retries_performed"] > observation["retry_count"]:
            raise RecordError("Attempt retries exceed applied policy")
        if observation["egress_attempted"] and (
            observation["endpoint_host"] == "none"
        ):
            raise RecordError("Attempted egress lacks an observed host")
        if not observation["egress_attempted"] and (
            observation["endpoint_host"] != "none"
        ):
            raise RecordError("Non-egress attempt claims an observed host")
        if not observation["egress_attempted"] and (
            observation["model_returned"] != "none"
        ):
            raise RecordError("Non-egress attempt claims a returned model")
        for field in (
            "provider",
            "model",
            "model_requested",
            "model_returned",
            "api",
            "endpoint_host",
        ):
            if record[field] != observation[field]:
                raise RecordError(
                    "Attempt top-level transport fact differs: {}".format(
                        field
                    )
                )
        sampling = record["sampling_parameters"]
        if set(sampling) not in (
            {"temperature", "reasoning_effort"},
            {"temperature", "reasoning_effort", "seed"},
        ):
            raise RecordError("Attempt sampling fields are not exact")
        if type(sampling["temperature"]) is not int or sampling[
            "temperature"
        ] != 0:
            raise RecordError("Attempt temperature must be integer zero")
        if "seed" in sampling and type(sampling["seed"]) is not int:
            raise RecordError("Attempt seed must be an integer")
        if sampling["reasoning_effort"] != "none":
            raise RecordError("Attempt reasoning effort must be none")
        started = _utc_timestamp(
            value=str(record["started_at_utc"]), field="started_at_utc",
        )
        finished = _utc_timestamp(
            value=str(record["finished_at_utc"]), field="finished_at_utc",
        )
        if finished < started:
            raise RecordError("Attempt finished before it started")
        for field in (
            "request_body_sha256",
            "reader_payload_sha256",
            "task_contract_sha256",
            "output_schema_sha256",
        ):
            if re.fullmatch(r"[0-9a-f]{64}", str(record[field])) is None:
                raise RecordError(
                    "Attempt digest is invalid: {}".format(field)
                )
        if re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(record["task_spec_semantic_hash"])
        ) is None:
            raise RecordError("Attempt task Spec identity is invalid")
        response_digest = str(record["raw_response_sha256"])
        response_path = str(record["raw_response_path"])
        if bool(response_digest) != bool(response_path):
            raise RecordError("Attempt response digest/path presence differs")
        if response_digest and re.fullmatch(
            r"[0-9a-f]{64}", response_digest
        ) is None:
            raise RecordError("Attempt response digest is invalid")
        assistant_digest = str(record["assistant_output_sha256"])
        assistant_path = str(record["assistant_output_path"])
        if bool(assistant_digest) != bool(assistant_path):
            raise RecordError("Attempt assistant output presence differs")
        if assistant_digest and re.fullmatch(
            r"[0-9a-f]{64}", assistant_digest
        ) is None:
            raise RecordError("Attempt assistant output digest is invalid")
        path_contract = {
            "request_body_path": "attempt_payloads/request_{}.bin".format(
                record["request_body_sha256"]
            ),
            "reader_payload_path": (
                "attempt_payloads/reader_payload_{}.json".format(
                    record["reader_payload_sha256"]
                )
            ),
            "task_contract_path": (
                "attempt_payloads/task_contract_{}.json".format(
                    record["task_contract_sha256"]
                )
            ),
            "output_schema_path": (
                "attempt_payloads/output_schema_{}.json".format(
                    record["output_schema_sha256"]
                )
            ),
            "assistant_output_path": (
                "attempt_payloads/assistant_output_{}.json".format(
                    assistant_digest
                )
                if assistant_digest
                else ""
            ),
            "raw_response_path": (
                "attempt_payloads/response_{}.bin".format(response_digest)
                if response_digest
                else ""
            ),
        }
        for field in path_contract:
            if record[field] != path_contract[field]:
                raise RecordError(
                    "Attempt content-addressed path differs: {}".format(field)
                )
        if record["status"] == "SUCCEEDED" and (
            not response_digest
            or not assistant_digest
            or record["error_class"]
        ):
            raise RecordError("Successful attempt response state is invalid")
        if record["status"] == "FAILED" and not record["error_class"]:
            raise RecordError("Failed attempt error class is required")
    if record_type == "REVIEW_DECISION":
        _utc_timestamp(
            value=str(record["decided_at_utc"]), field="decided_at_utc",
        )
        if not record["reason"]:
            raise RecordError("Review decision reason is required")
        if record["decision"] == "REJECT" and record["approved_claims"]:
            raise RecordError(
                "Rejected ReviewDecision cannot contain approved claims"
            )
    if record_type == "VALIDATION_RECEIPT":
        checks = record["checks"]
        if any(
            not isinstance(check, dict)
            or set(check) not in (
                {"check", "status"},
                {"check", "evidence_hash", "status"},
            )
            or not isinstance(check["check"], str)
            or not check["check"]
            or check["status"] not in {"PASS", "FAIL"}
            or (
                "evidence_hash" in check
                and (
                    not isinstance(check["evidence_hash"], str)
                    or re.fullmatch(
                        r"sha256:[0-9a-f]{64}", check["evidence_hash"]
                    )
                    is None
                )
            )
            for check in checks
        ):
            raise RecordError("Validation receipt check is invalid")
        check_names = [str(check["check"]) for check in checks]
        if len(check_names) != len(set(check_names)):
            raise RecordError("Validation receipt checks are duplicated")
        bindings = record["artifact_hashes"]
        for relative in bindings:
            path = PurePosixPath(str(relative))
            binding = bindings[relative]
            if (
                not isinstance(relative, str)
                or not relative
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or not isinstance(binding, dict)
                or set(binding) != {"sha256", "size"}
                or not isinstance(binding["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", binding["sha256"])
                is None
                or type(binding["size"]) is not int
                or binding["size"] < 0
            ):
                raise RecordError("Validation artifact binding is invalid")
        if record["status"] == "PASSED" and (
            not checks
            or not bindings
            or any(check["status"] != "PASS" for check in checks)
        ):
            raise RecordError("PASSED validation receipt is incomplete")
        if record["status"] == "FAILED" and (
            not checks
            or not any(check["status"] == "FAIL" for check in checks)
        ):
            raise RecordError("FAILED validation receipt lacks a failed gate")
        if record["status"] == "NOT_RUN" and (checks or bindings):
            raise RecordError(
                "NOT_RUN validation receipt cannot claim evidence"
            )
    if record_type == "REVIEW_UNIT":
        compiled_spec = record["compiled_spec"]
        if (
            not isinstance(compiled_spec, dict)
            or not {
                "required_claims",
                "identity_constraints",
                "disclosure_group",
            }.issubset(compiled_spec)
            or record["spec_semantic_hash"]
            != content_hash(
                value=compiled_spec, set_paths=SEMANTIC_SET_PATHS,
            )
            or record["required_claims"]
            != compiled_spec["required_claims"]
        ):
            raise RecordError("ReviewUnit compiled Spec binding differs")
    if record_type == "RAW_BLOB" and (
        record["byte_length"] < 0
        or not record["media_type"]
        or not record["storage_uri"]
    ):
        raise RecordError("RawBlob metadata is invalid")
    if record_type == "SOURCE_REFERENCE":
        required = (
            "accession",
            "document_name",
            "source_role",
            "source_url",
        )
        if any(not record[field] for field in required):
            raise RecordError("SourceReference identity is incomplete")
    if record_type == "VERIFIED_OBSERVATION":
        scope = record["scope"]
        if not scope or record["scope_key"] != content_hash(value=scope):
            raise RecordError("Observation scope identity differs")
        binding = record["source_binding"]
        required_binding = (
            "accession",
            "document_name",
            "raw_asset_id",
            "source_reference_id",
            "source_role",
        )
        if any(
            field not in binding
            or type(binding[field]) is not str
            or not binding[field]
            for field in required_binding
        ):
            raise RecordError("Observation source binding is incomplete")
        try:
            normalized = decimal_text(
                value=parse_decimal(value=str(record["value"]))
            )
        except CanonicalError as error:
            raise RecordError("Observation value is invalid") from error
        if normalized != record["value"] or not record["unit"]:
            raise RecordError("Observation value/unit is not canonical")
    if record_type == "DETERMINISTIC_VERIFIED_CLAIM":
        if (
            not record["claim_kind"]
            or not record["company_id"]
            or not record["source_reference_id"]
            or not record["source_set_manifest_id"]
            or not record["source_role"]
            or not record["unit"]
            or not record["value"]
            or not record["locator"]
        ):
            raise RecordError("Deterministic claim identity is incomplete")
    if record_type == "EXECUTION_TRACE":
        target = record["calculation_target"]
        required_target = {
            "accession",
            "company_id",
            "entity",
            "period_end",
            "period_start",
            "scope",
            "scope_key",
        }
        if set(target) != required_target:
            raise RecordError("Trace calculation target fields are not exact")
        for field in (
            "company_id",
            "period_end",
            "period_start",
            "scope_key",
        ):
            if type(target[field]) is not str or not target[field]:
                raise RecordError("Trace calculation target text is invalid")
        if (
            type(target["scope"]) is not dict
            or not target["scope"]
            or target["scope_key"] != content_hash(value=target["scope"])
        ):
            raise RecordError("Trace calculation scope identity differs")
        source_values = (target["accession"], target["entity"])
        if not (
            all(value is None for value in source_values)
            or all(type(value) is str and value for value in source_values)
        ):
            raise RecordError("Trace source target is incomplete")
    if record_type in {"EXECUTION_TRACE", "METRIC_RESULT"}:
        value = record["result"] if record_type == "EXECUTION_TRACE" else (
            record["value"]
        )
        if value is not None:
            try:
                normalized = decimal_text(
                    value=parse_decimal(value=str(value))
                )
            except CanonicalError as error:
                raise RecordError(
                    "{} value is invalid".format(record_type)
                ) from error
            if normalized != value:
                raise RecordError(
                    "{} value is not canonical".format(record_type)
                )
    if record_type == "METRIC_RESULT":
        if (record["value"] is None) != (record["unit"] is None):
            raise RecordError("MetricResult value/unit nullability differs")
        if record["value"] is not None and record["publication"] != (
            "PUBLISHED"
        ):
            raise RecordError("WITHHELD MetricResult cannot carry a value")
        if record["value"] is not None and (
            record["applicability"] != "APPLICABLE"
            or record["quality"] not in {"EXACT", "APPROX"}
            or record["reason_code"] != "PASS"
        ):
            raise RecordError("Published MetricResult state is inconsistent")
        if record["applicability"] == "N_A_STRUCTURAL" and (
            record["value"] is not None
            or record["quality"] != "NONE"
            or record["publication"] != "PUBLISHED"
            or record["reason_code"] != "TRAIT_NOT_APPLICABLE"
        ):
            raise RecordError("Structural MetricResult state is inconsistent")
        if record["publication"] == "WITHHELD" and (
            record["applicability"] != "APPLICABLE"
            or record["value"] is not None
            or record["quality"] != "NONE"
            or record["reason_code"] == "PASS"
        ):
            raise RecordError("WITHHELD MetricResult state is inconsistent")
        if (
            record["applicability"] == "APPLICABLE"
            and record["publication"] == "PUBLISHED"
            and record["value"] is None
            and (
                record["quality"] != "NOT_MEANINGFUL"
                or record["reason_code"] == "PASS"
            )
        ):
            raise RecordError("Null published MetricResult state is invalid")


def validate_record(*, record: Mapping[str, object]) -> Dict[str, object]:
    """Validate an exact vNext record and return an isolated copy.

    Args:
        record: Candidate record.

    Returns:
        Plain dictionary safe for canonical hashing.

    Raises:
        RecordError: On unknown type, schema drift, invalid state, or invalid
            primary identifier.
    """
    if "record_type" not in record or not isinstance(
        record["record_type"], str
    ):
        raise RecordError("record_type is required")
    record_type = str(record["record_type"])
    if record_type not in SCHEMAS:
        raise RecordError("Unknown record_type: {}".format(record_type))
    require_exact_fields(record=record, schema=SCHEMAS[record_type])
    _validate_field_types(record=record)
    try:
        canonical_json_bytes(value=dict(record))
    except CanonicalError as error:
        raise RecordError("Record is not canonical JSON data") from error
    _validate_record_status(record_type=record_type, record=record)
    _validate_enums(record_type=record_type, record=record)
    _validate_record_semantics(record_type=record_type, record=record)
    identifiers = [
        key
        for key in record
        if key.endswith("_id") and record[key] not in {None, ""}
    ]
    for key in identifiers:
        validate_identifier(value=record[key], field=key)
    if record_type == "REVIEW_DECISION":
        _validate_decision_hashes(record=record)
    expected = _expected_identifier(record_type=record_type, record=record)
    if expected is not None:
        field, expected_value = expected
        if record[field] != expected_value:
            raise RecordError(
                "{} content identity differs".format(record_type)
            )
    return dict(record)


def record_content_hash(
    *, record: Mapping[str, object], excluded_fields: Set[str]
) -> str:
    """Hash substantive record content after explicit audit-field removal.

    Args:
        record: Valid record mapping.
        excluded_fields: Audit-only fields that the caller's contract excludes
            from business content identity.

    Returns:
        Canonical content hash.

    Raises:
        RecordError: When an excluded field is absent, which prevents a typo
            from silently changing the identity contract.
    """
    validated = validate_record(record=record)
    missing = sorted(excluded_fields - set(validated))
    if missing:
        raise RecordError(
            "Excluded record fields are absent: {}".format(",".join(missing))
        )
    substantive = {
        key: validated[key] for key in validated if key not in excluded_fields
    }
    try:
        return content_hash(value=substantive)
    except CanonicalError as error:
        raise RecordError("Record cannot be canonicalized") from error
