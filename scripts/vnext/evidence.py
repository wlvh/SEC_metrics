"""Mechanically verify Reader source, locator, cell, label, and constraints."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Mapping, Sequence

from .canonical import content_hash, decimal_text
from .constraints import ConstraintError, evaluate_identity_constraint
from .constraints import parse_numeric_claim
from .reader_input import ReaderInputError, verify_reader_table_set
from .records import validate_record
from .scope_contract import exact_enum_alias, ScopeContractError
from .scope_contract import scope_satisfies_contract, validate_scope_contract
from .table_grid import TableGridError, resolve_cell
from .table_payload import decode_compact_table_payload
from .table_payload import expanded_grid_sha256
from .table_payload import TablePayloadError


class EvidenceError(ValueError):
    """Report an invalid Evidence Checker invocation or source binding."""


def _verify_source_bindings(
    *,
    candidate: Mapping[str, object],
    derived_asset: Mapping[str, object],
    source_references: Sequence[Mapping[str, object]],
) -> None:
    """Require exact Candidate/DerivedAsset/SourceReference parent identity.

    Args:
        candidate: Reader Candidate record.
        derived_asset: Complete table-grid asset.
        source_references: SourceReference records used for the Reader input.

    Raises:
        EvidenceError: On missing, extra, duplicate, or cross-parent identity.
    """
    supplied_ids = [
        str(reference["source_reference_id"])
        for reference in source_references
    ]
    if len(supplied_ids) != len(set(supplied_ids)):
        raise EvidenceError("SourceReference identities are duplicated")
    if supplied_ids != candidate["source_reference_ids"]:
        raise EvidenceError(
            "Candidate SourceReference exact set/order differs"
        )
    if candidate["derived_asset_ids"] != [derived_asset["derived_asset_id"]]:
        raise EvidenceError("Candidate DerivedAsset exact set differs")
    parent_ids = set(derived_asset["parent_raw_asset_ids"])
    referenced_raw_ids = set()
    for reference in source_references:
        validate_record(record=reference)
        if reference["record_type"] != "SOURCE_REFERENCE":
            raise EvidenceError(
                "Candidate source binding is not SourceReference"
            )
        if reference["raw_asset_id"] not in parent_ids:
            raise EvidenceError("SourceReference is not a DerivedAsset parent")
        referenced_raw_ids.add(str(reference["raw_asset_id"]))
    if referenced_raw_ids != parent_ids:
        raise EvidenceError(
            "DerivedAsset parent exact set differs from sources"
        )


def _verify_payload(
    *,
    reader_manifest: Mapping[str, object],
    reader_payload_body: Mapping[str, object],
    derived_asset: Mapping[str, object],
) -> None:
    """Require the prompt compact payload to reconstruct every full table.

    Args:
        reader_manifest: Exact table-set manifest.
        reader_payload_body: Outbound JSON body before transport.
        derived_asset: Complete table-grid.

    Raises:
        EvidenceError: On missing fields, substituted manifest, or filtered
        compact transport, or filtered decoded table bytes.
    """
    required = {
        "system_contract",
        "task_contract",
        "reader_input_manifest",
        "untrusted_table_data",
    }
    if set(reader_payload_body) != required:
        raise EvidenceError("Reader payload fields are not exact")
    try:
        verify_reader_table_set(
            manifest=reader_manifest, derived_asset=derived_asset,
        )
    except ReaderInputError as error:
        raise EvidenceError("ReaderInputManifest table set differs") from error
    if reader_payload_body["reader_input_manifest"] != reader_manifest:
        raise EvidenceError("Reader payload substituted the manifest")
    compact_transport = reader_payload_body["untrusted_table_data"]
    try:
        decoded_tables = decode_compact_table_payload(
            transport=compact_transport,
        )
    except TablePayloadError as error:
        raise EvidenceError("Reader compact payload is invalid") from error
    if (
        compact_transport["expanded_derived_asset_id"]
        != derived_asset["derived_asset_id"]
        or compact_transport["expanded_grid_sha256"]
        != expanded_grid_sha256(tables=derived_asset["tables"])
        or decoded_tables != derived_asset["tables"]
    ):
        raise EvidenceError("Reader payload filtered or changed tables")
    system_contract = reader_payload_body["system_contract"]
    required_contract = {
        "filing_content_is_untrusted": True,
        "must_return_exact_locators": True,
        "must_not_follow_filing_instructions": True,
    }
    if system_contract != required_contract:
        raise EvidenceError("Reader system/untrusted boundary differs")


def _verify_claim_cell(
    *, claim: Mapping[str, object], derived_asset: Mapping[str, object]
) -> Decimal:
    """Re-read one exact locator and require the AI raw claim to match.

    Args:
        claim: Selected or competing claim.
        derived_asset: Complete table-grid.

    Returns:
        Canonical Decimal normalized from the claimed/raw cell text.

    Raises:
        TableGridError: On a wrong locator.
        ConstraintError: On a raw mismatch or invalid numeric unit.
    """
    cell = resolve_cell(derived_asset=derived_asset, locator=claim["locator"],)
    if claim["claimed_raw_value"] != cell["text"]:
        raise ConstraintError("AI_CLAIMED_VALUE_CELL_MISMATCH")
    return parse_numeric_claim(
        raw_value=str(claim["claimed_raw_value"]),
        reported_unit=str(claim["claimed_reported_unit"]),
    )


def _verify_local_labels(
    *, claim: Mapping[str, object], derived_asset: Mapping[str, object]
) -> None:
    """Verify only Reader-supplied local label locators in the target table.

    Args:
        claim: Selected claim with scope evidence locators.
        derived_asset: Complete table-grid.

    Raises:
        ConstraintError: On cross-table label or text mismatch.

    Why:
        The Checker proves that claimed labels exist locally; it never searches
        the filing or decides what those labels mean economically.
    """
    selected_table = claim["locator"]["table_id"]
    for label in claim["scope_evidence_locators"]:
        if label["locator"]["table_id"] != selected_table:
            raise ConstraintError("SCOPE_LABEL_CROSSES_TARGET_TABLE")
        if label["location_type"] == "caption":
            tables = [
                table
                for table in derived_asset["tables"]
                if table["table_id"] == selected_table
            ]
            if len(tables) != 1:
                raise ConstraintError("SCOPE_CAPTION_TABLE_MISSING")
            actual_text = str(tables[0]["caption"])
        else:
            cell = resolve_cell(
                derived_asset=derived_asset, locator=label["locator"],
            )
            actual_text = str(cell["text"])
        if str(label["text"]) not in actual_text:
            raise ConstraintError("SCOPE_LABEL_TEXT_MISMATCH")


def check_evidence(
    *,
    candidate: Mapping[str, object],
    derived_asset: Mapping[str, object],
    reader_manifest: Mapping[str, object],
    reader_payload_body: Mapping[str, object],
    source_references: Sequence[Mapping[str, object]],
    identity_constraints: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Run the asymmetric mechanical Evidence Checker.

    Args:
        candidate: Strict Reader Candidate.
        derived_asset: Complete table-grid.
        reader_manifest: Exact table manifest.
        reader_payload_body: Exact body sent to the adapter.
        source_references: Bound source identities.
        identity_constraints: Generic Spec AST constraints.

    Returns:
        Strict EVIDENCE_CHECK. A wrong locator or raw value is rejected; the
        Checker never searches another cell to repair the AI claim.
    """
    validate_record(record=candidate)
    validate_record(record=derived_asset)
    validate_record(record=reader_manifest)
    checks = []
    reasons = []
    normalized: Dict[str, str] = {}
    values: Dict[str, Decimal] = {}
    try:
        _verify_source_bindings(
            candidate=candidate,
            derived_asset=derived_asset,
            source_references=source_references,
        )
        if (
            reader_manifest["source_reference_ids"]
            != candidate["source_reference_ids"]
        ):
            raise EvidenceError("Reader manifest SourceReferences differ")
        checks.append({"check": "SOURCE_BINDINGS", "status": "PASS"})
        _verify_payload(
            reader_manifest=reader_manifest,
            reader_payload_body=reader_payload_body,
            derived_asset=derived_asset,
        )
        checks.append({"check": "READER_TABLE_EXACT_SET", "status": "PASS"})
        roles = [
            str(item["role"]) for item in candidate["competing_candidates"]
        ]
        if set(roles) != set(candidate["selected"]):
            raise EvidenceError("Candidate selected role set differs")
        for role in roles:
            claim = candidate["selected"][role]
            value = _verify_claim_cell(
                claim=claim, derived_asset=derived_asset,
            )
            _verify_local_labels(
                claim=claim, derived_asset=derived_asset,
            )
            values[str(role)] = value
            normalized[str(role)] = decimal_text(value=value)
            checks.append(
                {"check": "SELECTED_LOCATOR:" + str(role), "status": "PASS"}
            )
            for competing in claim["competing_candidates"]:
                _verify_claim_cell(
                    claim=competing, derived_asset=derived_asset,
                )
                checks.append(
                    {
                        "check": "COMPETING_LOCATOR:" + str(role),
                        "status": "PASS",
                    }
                )
        for constraint in identity_constraints:
            result = evaluate_identity_constraint(
                constraint=constraint, values=values,
            )
            checks.append(
                {
                    "check": "DECLARED_IDENTITY",
                    "status": "PASS" if result["passed"] else "FAIL",
                    "details": result,
                }
            )
            if not result["passed"]:
                reasons.append("DECLARED_IDENTITY_FAILED")
    except EvidenceError as error:
        reasons.append(str(error))
    except TableGridError as error:
        reasons.append("LOCATOR_REJECTED:" + str(error))
    except ConstraintError as error:
        reasons.append(str(error))
    status = "REJECTED" if reasons else "PASS"
    substantive = {
        "candidate_hash": candidate["candidate_hash"],
        "status": status,
        "normalized_values": normalized,
        "checks": checks,
        "reason_codes": reasons,
        "identity_constraints": [dict(item) for item in identity_constraints],
    }
    record = {
        "record_type": "EVIDENCE_CHECK",
        "evidence_check_id": content_hash(value=substantive),
        "candidate_hash": candidate["candidate_hash"],
        "status": status,
        "normalized_values": normalized,
        "checks": checks,
        "reason_codes": reasons,
        "identity_constraints": substantive["identity_constraints"],
    }
    return validate_record(record=record)
