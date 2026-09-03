"""Validate strict Reader output without solving or correcting its claims."""

from __future__ import annotations

from typing import Dict, Mapping, Sequence, Tuple

from .canonical import CanonicalError, content_hash, sha256_bytes
from .canonical import strict_json_loads
from .records import validate_record
from .scope_contract import exact_enum_alias, ScopeContractError
from .scope_contract import validate_scope_contract


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
SCOPE_CLAIM_FIELDS = {"dimension", "evidence_locator_ids", "raw_value"}
LABEL_LOCATOR_FIELDS = {
    "id",
    "location_type",
    "locator",
    "raw_text",
    "supports_dimensions",
}
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


def _validate_claimed_scope(
    *, value: object, scope_contract: Mapping[str, object], label: str,
) -> Tuple[list, bool]:
    """Validate raw scope claims without normalizing any model-supplied text.

    Args:
        value: Reader supplied ordered scope claim array.
        scope_contract: Spec-owned generic scope contract v2.
        label: Stable caller diagnostic label.

    Returns:
        Validated raw claims and whether missing/unknown aliases require review.
    """
    if type(value) is not list:
        raise ReaderError("{} scope must be an ordered array".format(label))
    allowed_dimensions = set(scope_contract["allowed_dimensions"])
    required_dimensions = set(scope_contract["required_dimensions"])
    claims = []
    dimensions = []
    needs_review = False
    for item in value:
        claim = _require_exact_mapping(
            value=item, fields=SCOPE_CLAIM_FIELDS, label=label + " scope claim",
        )
        if (
            type(claim["dimension"]) is not str
            or claim["dimension"] not in allowed_dimensions
            or type(claim["raw_value"]) is not str
            or not claim["raw_value"]
            or type(claim["evidence_locator_ids"]) is not list
            or not claim["evidence_locator_ids"]
            or any(
                type(locator_id) is not str or not locator_id
                for locator_id in claim["evidence_locator_ids"]
            )
            or len(claim["evidence_locator_ids"])
            != len(set(claim["evidence_locator_ids"]))
        ):
            raise ReaderError("{} scope claim is invalid".format(label))
        dimensions.append(claim["dimension"])
        try:
            canonical = exact_enum_alias(
                contract=scope_contract,
                dimension=claim["dimension"],
                raw_value=claim["raw_value"],
            )
        except ScopeContractError as error:
            raise ReaderError("{} scope contract is invalid".format(label)) from error
        if canonical is None:
            needs_review = True
        claims.append(claim)
    if len(dimensions) != len(set(dimensions)):
        raise ReaderError("{} scope dimensions are duplicated".format(label))
    if not required_dimensions.issubset(set(dimensions)):
        needs_review = True
    return claims, needs_review


def _validate_competing(
    *, value: object, scope_contract: Mapping[str, object],
) -> Dict[str, object]:
    """Validate one competing raw claim with a replayable same-table locator.

    Args:
        value: Candidate competing claim.
        scope_contract: Spec-owned generic scope contract v2.

    Returns:
        Isolated claim containing raw scope facts only.
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
    claim["claimed_scope"], _needs_review = _validate_claimed_scope(
        value=claim["claimed_scope"],
        scope_contract=scope_contract,
        label="Competing candidate",
    )
    return claim


def _validate_label_locator(
    *, value: object, scope_contract: Mapping[str, object],
) -> Dict[str, object]:
    """Validate one local raw scope-evidence locator and supported dimensions.

    Args:
        value: Candidate scope-evidence mapping.
        scope_contract: Spec-owned generic scope contract v2.

    Returns:
        Isolated evidence locator with one exact table or cell locator.
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
    if (
        type(label["id"]) is not str
        or not label["id"]
        or type(label["raw_text"]) is not str
        or not label["raw_text"]
        or type(label["supports_dimensions"]) is not list
        or not label["supports_dimensions"]
        or any(
            type(dimension) is not str
            or dimension not in scope_contract["allowed_dimensions"]
            for dimension in label["supports_dimensions"]
        )
        or len(label["supports_dimensions"])
        != len(set(label["supports_dimensions"]))
    ):
        raise ReaderError("Scope evidence locator fields are invalid")
    return label


def _validate_candidate(
    *, value: object, scope_contract: Mapping[str, object],
) -> Tuple[Dict[str, object], bool]:
    """Validate one selected role and expose whether it requires review.

    Args:
        value: Candidate role mapping.
        scope_contract: Spec-owned generic scope contract v2.

    Returns:
        Validated candidate plus a status signal for unresolved scope facts.
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
    candidate["claimed_scope"], needs_review = _validate_claimed_scope(
        value=candidate["claimed_scope"],
        scope_contract=scope_contract,
        label="Selected candidate",
    )
    candidate["locator"] = _validate_cell_locator(value=candidate["locator"])
    if not isinstance(candidate["scope_evidence_locators"], list):
        raise ReaderError("Scope evidence locators must be an ordered array")
    labels = []
    for item in candidate["scope_evidence_locators"]:
        labels.append(_validate_label_locator(
            value=item, scope_contract=scope_contract,
        ))
    label_ids = [label["id"] for label in labels]
    if len(label_ids) != len(set(label_ids)):
        raise ReaderError("Scope evidence locator IDs are duplicated")
    by_id = {label["id"]: label for label in labels}
    for scope_claim in candidate["claimed_scope"]:
        for locator_id in scope_claim["evidence_locator_ids"]:
            if (
                locator_id not in by_id
                or scope_claim["dimension"]
                not in by_id[locator_id]["supports_dimensions"]
            ):
                raise ReaderError("Scope claim evidence binding differs")
    candidate["scope_evidence_locators"] = labels
    if not isinstance(candidate["competing_candidates"], list):
        raise ReaderError("Competing candidates must be an ordered array")
    candidate["competing_candidates"] = [
        _validate_competing(value=item, scope_contract=scope_contract)
        for item in candidate["competing_candidates"]
    ]
    return candidate, needs_review


def validate_reader_output(
    *,
    response_text: str,
    attempt_id: str,
    required_roles: Sequence[str],
    scope_contract: Mapping[str, object],
    source_reference_ids: Sequence[str],
    derived_asset_ids: Sequence[str],
) -> Dict[str, object]:
    """Validate exact Reader JSON and create a substantive Candidate record.

    Args:
        response_text: Raw model JSON response.
        attempt_id: Audit attempt that produced these exact response bytes.
        required_roles: Spec-derived exact role list.
        scope_contract: Spec-owned generic scope normalization authority.
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
    try:
        validated_scope_contract = validate_scope_contract(
            value=scope_contract,
        )
    except ScopeContractError as error:
        raise ReaderError("Reader scope contract is invalid") from error
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
    candidates = []
    scope_review_required = False
    for item in parsed["candidates"]:
        candidate, needs_review = _validate_candidate(
            value=item, scope_contract=validated_scope_contract,
        )
        candidates.append(candidate)
        scope_review_required = scope_review_required or needs_review
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
            if (
                substantive["unresolved_competing_claims"]
                or scope_review_required
            )
            else "CANDIDATE"
        ),
    }
    return validate_record(record=record)


def validate_source_bound_reader_output(
    *, response_text: str, attempt_id: str, source_bound_proof: Mapping,
    expected_proof_id: str, requirement: Mapping, repo_root,
    source_bytes: bytes, raw_blob: Mapping, source_reference: Mapping,
    full_derived_asset: Mapping, task_contract: Mapping,
) -> Dict[str, object]:
    """Keep model output intact and bind deterministic successor enrichment.

    The ordinary Reader schema remains table-only. Narrative bytes and unit
    factors are independently reconstructed local evidence, never invented
    model claims or text inserted into a source caption/cell.
    """
    from .composite_scope import source_bound_scope, validate_source_bound_proof
    from .records import SOURCE_BOUND_CANDIDATE_FIELDS, SOURCE_BOUND_CANDIDATE_TYPE
    native = validate_reader_output(response_text=response_text, attempt_id=attempt_id,
        required_roles=task_contract["required_roles"], scope_contract=task_contract["scope_contract"],
        source_reference_ids=[source_reference["source_reference_id"]],
        derived_asset_ids=[full_derived_asset["derived_asset_id"]])
    proof = validate_source_bound_proof(proof=source_bound_proof, expected_proof_id=expected_proof_id,
        requirement=requirement, repo_root=repo_root, source_bytes=source_bytes, raw_blob=raw_blob,
        source_reference=source_reference, full_derived_asset=full_derived_asset, task_contract=task_contract)
    if native["disclosure_group"] != task_contract["disclosure_group"]:
        raise ReaderError("Source-bound Reader task differs")
    requires_review = bool(native["unresolved_competing_claims"])
    for claim in native["selected"].values():
        if claim["locator"] != proof["target_locator"]:
            raise ReaderError("Source-bound response does not name the certified target")
        numeric = proof["numeric_normalization"]
        if numeric is not None and claim["claimed_reported_unit"] != numeric["reported_unit"]:
            raise ReaderError("Source-bound response invented a different reported unit")
        scope = {}
        for item in claim["claimed_scope"]:
            value = exact_enum_alias(contract=task_contract["scope_contract"],
                                     dimension=item["dimension"], raw_value=item["raw_value"])
            if value is None:
                requires_review = True
            else:
                scope[item["dimension"]] = value
        source_bound_scope(proof=proof, native_scope=scope, task_contract=task_contract)
    candidate = {**native, "record_type": SOURCE_BOUND_CANDIDATE_TYPE,
        "artifact_requirement_generation": requirement["artifact_requirement_generation"],
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "requirement_hashes": dict(requirement["hashes"]),
        "native_candidate_hash": native["candidate_hash"],
        "source_bound_proof_id": proof["source_bound_proof_id"],
        "status": "REVIEW_REQUIRED" if requires_review else "CANDIDATE"}
    body = {key: candidate[key] for key in (
        "disclosure_group", "source_reference_ids", "derived_asset_ids", "selected",
        "competing_candidates", "unresolved_competing_claims", *SOURCE_BOUND_CANDIDATE_FIELDS)}
    candidate["candidate_hash"] = content_hash(value=body)
    return validate_record(record=candidate)
