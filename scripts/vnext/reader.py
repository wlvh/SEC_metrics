"""Validate strict Reader output without solving or correcting its claims."""

from __future__ import annotations

from typing import Dict, Sequence

from .canonical import CanonicalError, content_hash, sha256_bytes
from .canonical import strict_json_loads
from .records import validate_record


ROOT_FIELDS = {
    "candidates",
    "disclosure_group",
    "table_locator",
    "unresolved_competing_claims",
}
CANDIDATE_FIELDS = {
    "claimed_period",
    "claimed_raw_value",
    "claimed_reported_unit",
    "claimed_scope",
    "competing_candidates",
    "locator",
    "role",
    "scope_evidence_locators",
}
COMPETING_FIELDS = {
    "claimed_period",
    "claimed_raw_value",
    "claimed_reported_unit",
    "claimed_scope",
    "locator",
    "rejection_reason_claim",
}
TABLE_LOCATOR_FIELDS = {"derived_asset_id", "table_id"}
CELL_LOCATOR_FIELDS = {
    "column_index",
    "colspan",
    "derived_asset_id",
    "origin_column_index",
    "origin_row_index",
    "row_index",
    "rowspan",
    "table_id",
}
LABEL_LOCATOR_FIELDS = {"location_type", "locator", "text"}
UNRESOLVED_FIELDS = {"description"}


class ReaderError(ValueError):
    """Report malformed, duplicated, incomplete, or unknown Reader claims."""


def _require_exact_mapping(
    *, value: object, fields: set, label: str
) -> Dict[str, object]:
    """Return a mapping whose keys exactly match a Reader schema fragment.

    Args:
        value: Candidate mapping.
        fields: Exact required keys.
        label: Diagnostic name.

    Returns:
        Isolated dictionary.

    Raises:
        ReaderError: When type or field set differs.
    """
    if not isinstance(value, dict) or set(value) != fields:
        raise ReaderError("{} fields are not exact".format(label))
    return dict(value)


def _validate_cell_locator(*, value: object) -> Dict[str, object]:
    """Validate an exact coordinate locator without resolving another cell.

    Args:
        value: Candidate locator.

    Returns:
        Isolated locator.
    """
    locator = _require_exact_mapping(
        value=value, fields=CELL_LOCATOR_FIELDS, label="cell locator",
    )
    for key in (
        "row_index",
        "column_index",
        "origin_row_index",
        "origin_column_index",
        "rowspan",
        "colspan",
    ):
        if type(locator[key]) is not int:
            raise ReaderError(
                "Cell locator coordinates/spans must be integers"
            )
    if any(
        locator[key] < 0
        for key in (
            "row_index",
            "column_index",
            "origin_row_index",
            "origin_column_index",
        )
    ):
        raise ReaderError("Cell locator coordinates cannot be negative")
    if locator["rowspan"] < 1 or locator["colspan"] < 1:
        raise ReaderError("Cell locator spans must be positive")
    for key in ("derived_asset_id", "table_id"):
        if not isinstance(locator[key], str) or not locator[key]:
            raise ReaderError("Cell locator identity is empty")
    return locator


def _validate_competing(*, value: object) -> Dict[str, object]:
    """Validate one competing claim with a replayable locator.

    Args:
        value: Candidate competing claim.

    Returns:
        Isolated claim.
    """
    claim = _require_exact_mapping(
        value=value, fields=COMPETING_FIELDS, label="competing candidate",
    )
    claim["locator"] = _validate_cell_locator(value=claim["locator"])
    for key in (
        "claimed_period",
        "claimed_raw_value",
        "claimed_reported_unit",
        "rejection_reason_claim",
    ):
        if not isinstance(claim[key], str) or not claim[key]:
            raise ReaderError(
                "Competing candidate field is empty: {}".format(key)
            )
    if not isinstance(claim["claimed_scope"], dict):
        raise ReaderError("Competing candidate scope must be an object")
    return claim


def _validate_label_locator(*, value: object) -> Dict[str, object]:
    """Validate one local caption/header/row/cell evidence locator.

    Args:
        value: Candidate label evidence mapping.

    Returns:
        Isolated label with a strict table or cell locator.
    """
    label = _require_exact_mapping(
        value=value,
        fields=LABEL_LOCATOR_FIELDS,
        label="scope evidence locator",
    )
    if label["location_type"] == "caption":
        locator = _require_exact_mapping(
            value=label["locator"],
            fields=TABLE_LOCATOR_FIELDS,
            label="caption locator",
        )
        if any(
            not isinstance(locator[key], str) or not locator[key]
            for key in locator
        ):
            raise ReaderError("Caption locator identity is empty")
        label["locator"] = locator
    elif label["location_type"] in {"cell", "header", "row", "label"}:
        label["locator"] = _validate_cell_locator(value=label["locator"])
    else:
        raise ReaderError("Scope evidence location_type is unknown")
    if not isinstance(label["text"], str) or not label["text"]:
        raise ReaderError("Scope evidence text is empty")
    return label


def _validate_candidate(*, value: object) -> Dict[str, object]:
    """Validate one selected role and all its replayable alternatives.

    Args:
        value: Candidate role mapping.

    Returns:
        Isolated validated candidate.
    """
    candidate = _require_exact_mapping(
        value=value, fields=CANDIDATE_FIELDS, label="selected candidate",
    )
    for key in (
        "role",
        "claimed_period",
        "claimed_raw_value",
        "claimed_reported_unit",
    ):
        if not isinstance(candidate[key], str) or not candidate[key]:
            raise ReaderError(
                "Selected candidate field is empty: {}".format(key)
            )
    if not isinstance(candidate["claimed_scope"], dict):
        raise ReaderError("Selected candidate scope must be an object")
    candidate["locator"] = _validate_cell_locator(value=candidate["locator"])
    if not isinstance(candidate["scope_evidence_locators"], list):
        raise ReaderError("Scope evidence locators must be an ordered array")
    labels = []
    for item in candidate["scope_evidence_locators"]:
        labels.append(_validate_label_locator(value=item))
    candidate["scope_evidence_locators"] = labels
    if not isinstance(candidate["competing_candidates"], list):
        raise ReaderError("Competing candidates must be an ordered array")
    candidate["competing_candidates"] = [
        _validate_competing(value=item)
        for item in candidate["competing_candidates"]
    ]
    return candidate


def validate_reader_output(
    *,
    response_text: str,
    attempt_id: str,
    required_roles: Sequence[str],
    source_reference_ids: Sequence[str],
    derived_asset_ids: Sequence[str],
) -> Dict[str, object]:
    """Validate exact Reader JSON and create a substantive Candidate record.

    Args:
        response_text: Raw model JSON response.
        attempt_id: Audit attempt that produced these exact response bytes.
        required_roles: Spec-derived exact role list.
        source_reference_ids: Source bindings sent to the Reader.
        derived_asset_ids: Derived assets sent to the Reader.

    Returns:
        Strict ``OBSERVATION_CANDIDATE`` record whose hash includes unresolved
        claims and excludes model/timestamp/log metadata.

    Raises:
        ReaderError: On duplicate JSON keys, unknown fields, missing/duplicate
            roles, invalid locators, or malformed claims.
    """
    if (
        not required_roles
        or any(
            not isinstance(role, str) or not role for role in required_roles
        )
        or len(required_roles) != len(set(required_roles))
    ):
        raise ReaderError("Required Reader roles must be unique and non-empty")
    for label, identifiers in (
        ("SourceReference", source_reference_ids),
        ("DerivedAsset", derived_asset_ids),
    ):
        if (
            not identifiers
            or any(
                not isinstance(item, str) or not item for item in identifiers
            )
            or len(identifiers) != len(set(identifiers))
        ):
            raise ReaderError(
                "{} identities must be unique and non-empty".format(label)
            )
    try:
        parsed = strict_json_loads(
            text=response_text, allowed_fields=ROOT_FIELDS
        )
    except CanonicalError as error:
        raise ReaderError("Reader response is not strict JSON") from error
    if not isinstance(parsed, dict):
        raise ReaderError("Reader response root must be an object")
    if set(parsed) != ROOT_FIELDS:
        raise ReaderError("Reader response fields are not exact")
    table_locator = _require_exact_mapping(
        value=parsed["table_locator"],
        fields=TABLE_LOCATOR_FIELDS,
        label="table locator",
    )
    for key in TABLE_LOCATOR_FIELDS:
        if not isinstance(table_locator[key], str) or not table_locator[key]:
            raise ReaderError("Reader table locator identity is empty")
    if table_locator["derived_asset_id"] not in derived_asset_ids:
        raise ReaderError("Reader table locator names an unsupplied asset")
    if (
        not isinstance(parsed["disclosure_group"], str)
        or not parsed["disclosure_group"]
    ):
        raise ReaderError("Reader disclosure_group is empty")
    if not isinstance(parsed["candidates"], list):
        raise ReaderError("Reader candidates must be an ordered array")
    candidates = [
        _validate_candidate(value=item) for item in parsed["candidates"]
    ]
    roles = [str(candidate["role"]) for candidate in candidates]
    if roles != list(required_roles):
        raise ReaderError("Reader roles are missing, duplicated, or reordered")
    for candidate in candidates:
        locators = [candidate["locator"]]
        locators.extend(
            competing["locator"]
            for competing in candidate["competing_candidates"]
        )
        locators.extend(
            label["locator"] for label in candidate["scope_evidence_locators"]
        )
        if any(
            locator["derived_asset_id"] != table_locator["derived_asset_id"]
            or locator["table_id"] != table_locator["table_id"]
            for locator in locators
        ):
            raise ReaderError("Reader claim locator leaves the target table")
    if not isinstance(parsed["unresolved_competing_claims"], list):
        raise ReaderError("Unresolved claims must be an ordered array")
    unresolved = []
    for item in parsed["unresolved_competing_claims"]:
        claim = _require_exact_mapping(
            value=item,
            fields=UNRESOLVED_FIELDS,
            label="unresolved competing claim",
        )
        if (
            not isinstance(claim["description"], str)
            or not claim["description"]
        ):
            raise ReaderError("Unresolved claim description is empty")
        unresolved.append(claim)
    selected = {str(candidate["role"]): candidate for candidate in candidates}
    substantive = {
        "disclosure_group": parsed["disclosure_group"],
        "source_reference_ids": list(source_reference_ids),
        "derived_asset_ids": list(derived_asset_ids),
        "selected": selected,
        "competing_candidates": [
            {
                "role": candidate["role"],
                "claims": candidate["competing_candidates"],
            }
            for candidate in candidates
        ],
        "unresolved_competing_claims": unresolved,
    }
    record = {
        "record_type": "OBSERVATION_CANDIDATE",
        "candidate_hash": content_hash(value=substantive),
        "attempt_id": attempt_id,
        "assistant_output_sha256": sha256_bytes(
            content=response_text.encode("utf-8")
        ),
        "disclosure_group": parsed["disclosure_group"],
        "source_reference_ids": list(source_reference_ids),
        "derived_asset_ids": list(derived_asset_ids),
        "selected": selected,
        "competing_candidates": substantive["competing_candidates"],
        "unresolved_competing_claims": substantive[
            "unresolved_competing_claims"
        ],
        "status": (
            "REVIEW_REQUIRED"
            if substantive["unresolved_competing_claims"]
            else "CANDIDATE"
        ),
    }
    return validate_record(record=record)
