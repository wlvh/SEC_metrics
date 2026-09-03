"""Route Issue #15 deterministic SEC sources without model-provider calls.

Five bounded adapters convert Company Facts, accession XBRL, ECD XBRL,
auditor facts, and fiscal-year 8-K item documents into content-addressed
deterministic claims. Source-set manifests prove the exact discovery set, and
generic projection converts claims into VerifiedObservation, MetricResult,
and ExecutionTrace records.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from types import MappingProxyType
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .calculator import calculate_observation_metric
from .canonical import content_hash, decimal_text, sha256_bytes
from .canonical import CanonicalError, strict_json_file, strict_json_loads
from .observations import scope_key, structured_observation
from .records import validate_record
from .sources import companyfacts_structured_facts
from .specs import compile_spec


SOURCE_ROLE_MODES = {
    "STRUCTURED_JSON",
    "ACCESSION_XBRL",
    "ECD_XBRL",
    "AUDITOR_FACT",
    "ITEM_CODE_INDEX",
}
SOURCE_SET_FIELDS = {
    "company_id",
    "cutoff_timestamp_or_pinned_submissions_attempt",
    "discovery_policy",
    "discovered_accession_set_hash",
    "fiscal_or_date_window",
    "form_types",
    "inventory_source_reference_id",
    "ordered_source_reference_ids",
    "record_type",
    "schema_version",
    "sec_submissions_inventory_hash",
    "source_role",
    "source_set_manifest_id",
}
SOURCE_ROLE_FIELDS = {
    "source_mode",
    "source_reference_ids",
    "source_role",
    "source_set_manifest_id",
}
CLAIM_FIELDS = {
    "attributes",
    "claim_kind",
    "company_id",
    "locator",
    "record_type",
    "source_reference_id",
    "source_role",
    "source_set_manifest_id",
    "unit",
    "value",
    "verified_claim_id",
}
EVENT_CATALOG_FIELDS = {
    "brief_source_priority",
    "match_mode",
    "record_type",
    "routes",
    "schema_version",
    "text_normalization",
}
EVENT_ROUTE_FIELDS = {
    "direct_item_codes",
    "keyword_item_rules",
    "legacy_projection",
    "metric_name",
    "shared_claim_group_id",
}
KEYWORD_RULE_FIELDS = {"aliases", "item_code"}
EVENT_ROUTE_IDS = {"C01", "E01", "E02", "E03", "E04", "E05"}
MAX_XBRL_FACTS = 250000
MAX_XBRL_TEXT = 16 * 1024 * 1024
DETERMINISTIC_ROUTER_SEMANTIC_VERSION = "2"


class DeterministicRouterError(ValueError):
    """Report incomplete source sets, malformed SEC bytes, or route drift."""


def _object(*, value: object, label: str) -> Dict[str, object]:
    """Return one isolated mapping or fail fast.

    Args:
        value: Candidate JSON value.
        label: Stable diagnostic location.

    Returns:
        Shallow isolated mapping.
    """
    if not isinstance(value, dict):
        raise DeterministicRouterError("{} must be an object".format(label))
    return dict(value)


def _exact_fields(
    *, value: Mapping[str, object], expected: set[str], label: str
) -> None:
    """Require one exact mapping schema.

    Args:
        value: Mapping under validation.
        expected: Exact required and allowed keys.
        label: Stable diagnostic location.

    Raises:
        DeterministicRouterError: When one key is missing or extra.
    """
    if set(value) != expected:
        raise DeterministicRouterError("{} fields are not exact".format(label))


def _text(*, value: object, label: str) -> str:
    """Return one required non-empty text scalar.

    Args:
        value: Candidate scalar.
        label: Stable diagnostic location.

    Returns:
        Validated text.
    """
    if not isinstance(value, str) or not value:
        raise DeterministicRouterError("{} must be non-empty text".format(label))
    return value


def _text_list(
    *, value: object, label: str, allow_empty: bool
) -> List[str]:
    """Return one ordered duplicate-free string list.

    Args:
        value: Candidate array.
        label: Stable diagnostic location.
        allow_empty: Whether zero members are valid.

    Returns:
        Isolated validated list.
    """
    if not isinstance(value, list):
        raise DeterministicRouterError("{} must be an array".format(label))
    values = list(value)
    if (
        (not allow_empty and not values)
        or any(not isinstance(item, str) or not item for item in values)
        or len(values) != len(set(values))
    ):
        raise DeterministicRouterError("{} string set is invalid".format(label))
    return values


def _sha256_identity(*, value: object, label: str) -> str:
    """Return one required ``sha256:`` content identity.

    Args:
        value: Candidate scalar.
        label: Stable diagnostic location.

    Returns:
        Validated identity.
    """
    text = _text(value=value, label=label)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", text) is None:
        raise DeterministicRouterError("{} is not a SHA-256 identity".format(label))
    return text


def _reference(*, value: Mapping[str, object]) -> Dict[str, object]:
    """Return one strict SourceReference.

    Args:
        value: Candidate source record.

    Returns:
        Validated SourceReference.
    """
    try:
        record = validate_record(record=value)
    except ValueError as error:
        raise DeterministicRouterError("SourceReference is invalid") from error
    if record["record_type"] != "SOURCE_REFERENCE":
        raise DeterministicRouterError("Source record is not a SourceReference")
    return record


def _require_raw_bytes(
    *, source_reference: Mapping[str, object], raw_bytes: bytes
) -> None:
    """Require exact bytes to match their SourceReference RawBlob identity.

    Args:
        source_reference: Validated SEC observation.
        raw_bytes: Candidate source bytes supplied to an adapter.

    Raises:
        DeterministicRouterError: When the bytes belong to another RawBlob.
    """
    if (
        source_reference["raw_asset_id"]
        != "sha256:" + sha256_bytes(content=raw_bytes)
    ):
        raise DeterministicRouterError("Adapter bytes differ from SourceReference")


def source_set_manifest(
    *,
    company_id: str,
    source_role: str,
    form_types: Sequence[str],
    fiscal_or_date_window: Mapping[str, object],
    discovery_policy: str,
    inventory_source_reference: Mapping[str, object],
    inventory_bytes: bytes,
    ordered_source_references: Sequence[Mapping[str, object]],
    cutoff_timestamp_or_pinned_submissions_attempt: str,
) -> Dict[str, object]:
    """Build one complete source-set proof from exact SEC observations.

    Args:
        company_id: Logical company identity.
        source_role: Release-plan role whose discovery set is proven.
        form_types: Exact SEC form types included by discovery.
        fiscal_or_date_window: Explicit fiscal year or inclusive date window.
        discovery_policy: Stable repository-owned discovery algorithm ID.
        inventory_source_reference: SEC submissions observation proving the
            population from which filing references were selected.
        inventory_bytes: Exact SEC submissions bytes bound to that reference.
        ordered_source_references: Exact filing/source observations in order.
        cutoff_timestamp_or_pinned_submissions_attempt: Immutable discovery
            cutoff or pinned submissions attempt identity.

    Returns:
        Content-addressed source-set manifest.
    """
    _text(value=company_id, label="source-set company id")
    _text(value=source_role, label="source-set role")
    forms = _text_list(
        value=list(form_types), label="source-set form types", allow_empty=False
    )
    if not isinstance(fiscal_or_date_window, dict) or not fiscal_or_date_window:
        raise DeterministicRouterError("Source-set window must be an object")
    policy = _text(value=discovery_policy, label="source-set discovery policy")
    cutoff = _text(
        value=cutoff_timestamp_or_pinned_submissions_attempt,
        label="source-set cutoff",
    )
    inventory = _reference(value=inventory_source_reference)
    _require_raw_bytes(source_reference=inventory, raw_bytes=inventory_bytes)
    references = [
        _reference(value=reference)
        for reference in ordered_source_references
    ]
    if inventory["company_id"] != company_id or any(
        reference["company_id"] != company_id for reference in references
    ):
        raise DeterministicRouterError("Source-set company binding differs")
    reference_ids = [
        str(reference["source_reference_id"]) for reference in references
    ]
    if len(reference_ids) != len(set(reference_ids)):
        raise DeterministicRouterError("Source-set reference identity is duplicated")
    discovered_accessions = _submissions_accessions(
        inventory_bytes=inventory_bytes,
        form_types=forms,
        fiscal_or_date_window=fiscal_or_date_window,
    )
    planned_accessions = sorted(
        {str(reference["accession"]) for reference in references}
    )
    if planned_accessions != discovered_accessions:
        raise DeterministicRouterError(
            "Source-set references differ from submissions discovery"
        )
    body = {
        "schema_version": 1,
        "record_type": "SOURCE_SET_MANIFEST",
        "company_id": company_id,
        "source_role": source_role,
        "form_types": forms,
        "fiscal_or_date_window": dict(fiscal_or_date_window),
        "discovery_policy": policy,
        "discovered_accession_set_hash": content_hash(
            value=discovered_accessions
        ),
        "sec_submissions_inventory_hash": inventory["raw_asset_id"],
        "inventory_source_reference_id": inventory["source_reference_id"],
        "ordered_source_reference_ids": reference_ids,
        "cutoff_timestamp_or_pinned_submissions_attempt": cutoff,
    }
    manifest = dict(body)
    manifest["source_set_manifest_id"] = content_hash(value=body)
    return validate_source_set_manifest(manifest=manifest)


def validate_source_set_manifest(
    *, manifest: Mapping[str, object]
) -> Dict[str, object]:
    """Validate one exact content-addressed source-set manifest.

    Args:
        manifest: Candidate proof object.

    Returns:
        Isolated validated manifest.
    """
    value = _object(value=manifest, label="source-set manifest")
    _exact_fields(
        value=value, expected=SOURCE_SET_FIELDS, label="source-set manifest"
    )
    if value["schema_version"] != 1 or value["record_type"] != "SOURCE_SET_MANIFEST":
        raise DeterministicRouterError("Source-set manifest identity differs")
    _text(value=value["company_id"], label="source-set company id")
    _text(value=value["source_role"], label="source-set role")
    _text_list(
        value=value["form_types"], label="source-set form types", allow_empty=False
    )
    if not isinstance(value["fiscal_or_date_window"], dict) or not value[
        "fiscal_or_date_window"
    ]:
        raise DeterministicRouterError("Source-set window is invalid")
    _text(value=value["discovery_policy"], label="source-set discovery policy")
    _sha256_identity(
        value=value["discovered_accession_set_hash"],
        label="source-set discovered accession hash",
    )
    _sha256_identity(
        value=value["sec_submissions_inventory_hash"],
        label="source-set submissions inventory hash",
    )
    _sha256_identity(
        value=value["inventory_source_reference_id"],
        label="source-set inventory reference",
    )
    _text_list(
        value=value["ordered_source_reference_ids"],
        label="source-set references",
        allow_empty=True,
    )
    _text(
        value=value["cutoff_timestamp_or_pinned_submissions_attempt"],
        label="source-set cutoff",
    )
    body = {
        field: value[field]
        for field in value
        if field != "source_set_manifest_id"
    }
    if value["source_set_manifest_id"] != content_hash(value=body):
        raise DeterministicRouterError("Source-set manifest identity differs")
    return value


def _submissions_accessions(
    *, inventory_bytes: bytes, form_types: Sequence[str],
    fiscal_or_date_window: Mapping[str, object],
) -> List[str]:
    """Derive exact in-window filing accessions from SEC submissions bytes.

    Args:
        inventory_bytes: Exact current/pinned SEC submissions JSON.
        form_types: Included form types.
        fiscal_or_date_window: Mapping containing ISO period boundaries.

    Returns:
        Sorted unique in-window accession set.
    """
    try:
        payload = strict_json_loads(text=inventory_bytes.decode("utf-8"))
    except (CanonicalError, UnicodeDecodeError) as error:
        raise DeterministicRouterError(
            "SEC submissions inventory is not strict UTF-8 JSON"
        ) from error
    if not isinstance(payload, dict):
        raise DeterministicRouterError("SEC submissions inventory is incomplete")
    if (
        "filings" in payload
        and isinstance(payload["filings"], dict)
        and "recent" in payload["filings"]
        and isinstance(payload["filings"]["recent"], dict)
    ):
        recent = payload["filings"]["recent"]
    elif all(field in payload for field in ("accessionNumber", "filingDate", "form")):
        # SEC submissions history shards expose the same parallel arrays at
        # the root instead of below filings.recent.
        recent = payload
    else:
        raise DeterministicRouterError("SEC submissions inventory is incomplete")
    if not isinstance(fiscal_or_date_window, dict) or not {
        "period_start",
        "period_end",
    }.issubset(fiscal_or_date_window):
        raise DeterministicRouterError("Source-set date window is incomplete")
    period_start = _text(
        value=fiscal_or_date_window["period_start"], label="source-set period start"
    )
    period_end = _text(
        value=fiscal_or_date_window["period_end"], label="source-set period end"
    )
    try:
        start_date = date.fromisoformat(period_start)
        end_date = date.fromisoformat(period_end)
    except ValueError as error:
        raise DeterministicRouterError(
            "Source-set period must use ISO dates"
        ) from error
    if end_date < start_date:
        raise DeterministicRouterError("Source-set period ends before it starts")
    required = {"accessionNumber", "filingDate", "form"}
    if not required.issubset(recent) or any(
        not isinstance(recent[field], list) for field in required
    ):
        raise DeterministicRouterError("SEC submissions recent arrays are incomplete")
    lengths = {len(recent[field]) for field in required}
    if len(lengths) != 1:
        raise DeterministicRouterError("SEC submissions recent arrays differ in length")
    forms = set(form_types)
    accessions = []
    row_count = lengths.pop()
    for index in range(row_count):
        accession = recent["accessionNumber"][index]
        filing_date = recent["filingDate"][index]
        form = recent["form"][index]
        if any(
            not isinstance(value, str) or not value
            for value in (accession, filing_date, form)
        ):
            raise DeterministicRouterError("SEC submissions row is invalid")
        try:
            filing_day = date.fromisoformat(filing_date)
        except ValueError as error:
            raise DeterministicRouterError(
                "SEC submissions filing date is invalid"
            ) from error
        if form in forms and start_date <= filing_day <= end_date:
            accessions.append(accession)
    if len(accessions) != len(set(accessions)):
        raise DeterministicRouterError("SEC submissions accession is duplicated")
    return sorted(accessions)


def verify_source_set_completeness(
    *, manifest: Mapping[str, object], inventory_source_reference: Mapping[str, object],
    inventory_bytes: bytes, ordered_source_references: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Recompute a source-set manifest from its pinned submissions bytes.

    Args:
        manifest: Persisted source-set proof.
        inventory_source_reference: Pinned SEC submissions observation.
        inventory_bytes: Exact submissions bytes.
        ordered_source_references: Exact planned filing/source observations.

    Returns:
        Validated manifest after independent set derivation.
    """
    value = validate_source_set_manifest(manifest=manifest)
    rebuilt = source_set_manifest(
        company_id=str(value["company_id"]),
        source_role=str(value["source_role"]),
        form_types=value["form_types"],
        fiscal_or_date_window=value["fiscal_or_date_window"],
        discovery_policy=str(value["discovery_policy"]),
        inventory_source_reference=inventory_source_reference,
        inventory_bytes=inventory_bytes,
        ordered_source_references=ordered_source_references,
        cutoff_timestamp_or_pinned_submissions_attempt=str(
            value["cutoff_timestamp_or_pinned_submissions_attempt"]
        ),
    )
    if rebuilt != value:
        raise DeterministicRouterError("Source-set completeness proof differs")
    return value


def source_role_plan(
    *, manifest: Mapping[str, object], source_mode: str
) -> Dict[str, object]:
    """Build one uniform ``sources[]`` role entry.

    Args:
        manifest: Exact source-set proof.
        source_mode: One of the five deterministic adapter modes.

    Returns:
        Role entry using an array even for one source reference.
    """
    validated = validate_source_set_manifest(manifest=manifest)
    if source_mode not in SOURCE_ROLE_MODES:
        raise DeterministicRouterError("Source role mode is invalid")
    return {
        "source_role": validated["source_role"],
        "source_mode": source_mode,
        "source_reference_ids": list(validated["ordered_source_reference_ids"]),
        "source_set_manifest_id": validated["source_set_manifest_id"],
    }


def validate_source_role_plan(*, role: Mapping[str, object]) -> Dict[str, object]:
    """Validate one uniform multi-source role entry.

    Args:
        role: Candidate entry from a company ``sources`` array.

    Returns:
        Isolated validated role.
    """
    value = _object(value=role, label="source role plan")
    _exact_fields(value=value, expected=SOURCE_ROLE_FIELDS, label="source role plan")
    _text(value=value["source_role"], label="source role")
    if value["source_mode"] not in SOURCE_ROLE_MODES:
        raise DeterministicRouterError("Source role mode is invalid")
    _text_list(
        value=value["source_reference_ids"],
        label="source role reference ids",
        allow_empty=True,
    )
    _sha256_identity(
        value=value["source_set_manifest_id"], label="source-set manifest id"
    )
    return value


def build_multi_source_release_input_plan(
    *,
    release_plan_id: str,
    release_plan_content_id: str,
    requirement_id: str,
    authority_hashes: Mapping[str, object],
    companies: Sequence[Mapping[str, object]],
    source_references: Sequence[Mapping[str, object]],
    source_set_manifests: Sequence[Mapping[str, object]],
    event_route_catalog_sha256: str,
) -> Dict[str, object]:
    """Build one content-addressed Issue #15 multi-source input plan.

    Args:
        release_plan_id: Configured ratchet ReleasePlan identity.
        release_plan_content_id: Immutable full ReleasePlan content identity.
        requirement_id: Exact Requirement snapshot identity.
        authority_hashes: ReleasePlan authority hash mapping.
        companies: Company rows with exact ``sources`` arrays.
        source_references: All SourceReference records used by the plan.
        source_set_manifests: All complete source-set proofs used by roles.
        event_route_catalog_sha256: Exact event-route catalog byte hash.

    Returns:
        Content-addressed release input plan with no scalar source slots.
    """
    _text(value=release_plan_id, label="release plan id")
    _sha256_identity(
        value=release_plan_content_id, label="release plan content id",
    )
    _text(value=requirement_id, label="Requirement id")
    _sha256_identity(
        value="sha256:" + event_route_catalog_sha256,
        label="event route catalog hash",
    )
    if not isinstance(authority_hashes, dict) or not authority_hashes:
        raise DeterministicRouterError("Release authority hashes are invalid")
    references = [_reference(value=reference) for reference in source_references]
    reference_index = {
        str(reference["source_reference_id"]): reference for reference in references
    }
    if len(reference_index) != len(references):
        raise DeterministicRouterError("Release SourceReference is duplicated")
    manifests = [
        validate_source_set_manifest(manifest=manifest)
        for manifest in source_set_manifests
    ]
    manifest_index = {
        str(manifest["source_set_manifest_id"]): manifest for manifest in manifests
    }
    if len(manifest_index) != len(manifests):
        raise DeterministicRouterError("Release source-set manifest is duplicated")
    if any(
        manifest["inventory_source_reference_id"] not in reference_index
        for manifest in manifests
    ):
        raise DeterministicRouterError(
            "Release inventory SourceReference is absent"
        )
    company_rows = []
    for company in companies:
        row = _object(value=company, label="release company")
        if set(row) != {"company_id", "result_metric_ids", "sources", "target_period"}:
            raise DeterministicRouterError("Release company fields are not exact")
        company_id = _text(value=row["company_id"], label="release company id")
        metric_ids = _text_list(
            value=row["result_metric_ids"],
            label="release result metric ids",
            allow_empty=False,
        )
        if metric_ids != sorted(metric_ids):
            raise DeterministicRouterError("Release result metric ids are not sorted")
        if not isinstance(row["target_period"], dict) or not row["target_period"]:
            raise DeterministicRouterError("Release target period is invalid")
        if not isinstance(row["sources"], list):
            raise DeterministicRouterError("Release sources must be an array")
        roles = [validate_source_role_plan(role=role) for role in row["sources"]]
        role_names = [str(role["source_role"]) for role in roles]
        if len(role_names) != len(set(role_names)):
            raise DeterministicRouterError("Release source role is duplicated")
        for role in roles:
            manifest_id = str(role["source_set_manifest_id"])
            if manifest_id not in manifest_index:
                raise DeterministicRouterError("Release source-set manifest is absent")
            manifest = manifest_index[manifest_id]
            if (
                manifest["company_id"] != company_id
                or manifest["source_role"] != role["source_role"]
                or manifest["ordered_source_reference_ids"]
                != role["source_reference_ids"]
            ):
                raise DeterministicRouterError(
                    "Release source role differs from manifest"
                )
            if any(
                source_id not in reference_index
                for source_id in role["source_reference_ids"]
            ):
                raise DeterministicRouterError("Release SourceReference is absent")
        company_rows.append(
            {
                "company_id": company_id,
                "result_metric_ids": metric_ids,
                "sources": roles,
                "target_period": dict(row["target_period"]),
            }
        )
    company_ids = [str(row["company_id"]) for row in company_rows]
    if not company_rows or len(company_ids) != len(set(company_ids)):
        raise DeterministicRouterError("Release company exact set is invalid")
    body = {
        "schema_version": 2,
        "record_type": "MULTI_SOURCE_RELEASE_INPUT_PLAN",
        "release_plan_id": release_plan_id,
        "release_plan_content_id": release_plan_content_id,
        "requirement_id": requirement_id,
        "authority_hashes": dict(authority_hashes),
        "event_route_catalog_sha256": event_route_catalog_sha256,
        "companies": company_rows,
        "source_references": sorted(
            references, key=lambda reference: str(reference["source_reference_id"])
        ),
        "source_set_manifests": sorted(
            manifests, key=lambda manifest: str(manifest["source_set_manifest_id"])
        ),
    }
    plan = dict(body)
    plan["release_input_plan_id"] = content_hash(value=body)
    return plan


def verified_claim(
    *,
    claim_kind: str,
    source_reference: Mapping[str, object],
    source_set_manifest: Mapping[str, object],
    locator: Mapping[str, object],
    value: str,
    unit: str,
    attributes: Mapping[str, object],
) -> Dict[str, object]:
    """Create one deterministic, non-model VerifiedClaim.

    Args:
        claim_kind: Bounded adapter output kind.
        source_reference: Exact SEC observation supporting the claim.
        source_set_manifest: Complete discovery set containing the source.
        locator: Deterministic byte/fact/item locator.
        value: Canonical numeric or normalized text value.
        unit: Explicit unit or ``text``.
        attributes: Adapter-specific audit fields.

    Returns:
        Content-addressed deterministic claim.
    """
    kind = _text(value=claim_kind, label="claim kind")
    reference = _reference(value=source_reference)
    if source_set_manifest.get("record_type") == "PINNED_SINGLE_FILING_FIXTURE_SOURCE_SET":
        # This additive subtype is never accepted by normal source-role or
        # release-input planners. It only carries owner-pinned offline fixture
        # facts through the existing accession parser; it claims no complete
        # submissions inventory, latest source or qualification credit.
        from .r4_structured_sources import validate_fixture_source_set
        if kind not in {"ACCESSION_XBRL_NUMERIC_FACT", "ACCESSION_XBRL_TEXT_FACT"}:
            raise DeterministicRouterError("Fixture source set is accession-audit only")
        manifest = validate_fixture_source_set(manifest=source_set_manifest)
        if reference != manifest["source_reference"]:
            raise DeterministicRouterError("Fixture claim source/attempt differs")
    else:
        manifest = validate_source_set_manifest(manifest=source_set_manifest)
    reference_id = str(reference["source_reference_id"])
    if (
        reference["company_id"] != manifest["company_id"]
        or reference_id not in manifest["ordered_source_reference_ids"]
    ):
        raise DeterministicRouterError("Claim source is outside its source set")
    if not isinstance(locator, dict) or not locator:
        raise DeterministicRouterError("Claim locator must be an object")
    if not isinstance(attributes, dict):
        raise DeterministicRouterError("Claim attributes must be an object")
    if "deterministic_router_semantic_version" in attributes:
        raise DeterministicRouterError(
            "Claim cannot override router semantic version"
        )
    claim_attributes = dict(attributes)
    claim_attributes["deterministic_router_semantic_version"] = (
        DETERMINISTIC_ROUTER_SEMANTIC_VERSION
    )
    body = {
        "record_type": "DETERMINISTIC_VERIFIED_CLAIM",
        "claim_kind": kind,
        "company_id": reference["company_id"],
        "source_reference_id": reference_id,
        "source_role": manifest["source_role"],
        "source_set_manifest_id": manifest["source_set_manifest_id"],
        "locator": dict(locator),
        "value": _text(value=value, label="claim value"),
        "unit": _text(value=unit, label="claim unit"),
        "attributes": claim_attributes,
    }
    claim = dict(body)
    claim["verified_claim_id"] = content_hash(value=body)
    return validate_verified_claim(claim=claim)


def validate_verified_claim(*, claim: Mapping[str, object]) -> Dict[str, object]:
    """Validate one deterministic VerifiedClaim and its content identity.

    Args:
        claim: Candidate claim object.

    Returns:
        Isolated validated claim.
    """
    value = _object(value=claim, label="deterministic VerifiedClaim")
    _exact_fields(
        value=value,
        expected=CLAIM_FIELDS,
        label="deterministic VerifiedClaim",
    )
    if value["record_type"] != "DETERMINISTIC_VERIFIED_CLAIM":
        raise DeterministicRouterError("Deterministic claim record type differs")
    for field in (
        "claim_kind",
        "company_id",
        "source_reference_id",
        "source_role",
        "source_set_manifest_id",
        "unit",
        "value",
    ):
        _text(value=value[field], label="claim " + field)
    if not isinstance(value["locator"], dict) or not value["locator"]:
        raise DeterministicRouterError("Claim locator is invalid")
    if not isinstance(value["attributes"], dict):
        raise DeterministicRouterError("Claim attributes are invalid")
    body = {field: value[field] for field in value if field != "verified_claim_id"}
    if value["verified_claim_id"] != content_hash(value=body):
        raise DeterministicRouterError("Deterministic claim identity differs")
    try:
        return validate_record(record=value)
    except ValueError as error:
        raise DeterministicRouterError(
            "Deterministic claim record is invalid"
        ) from error


def adapt_companyfacts(
    *,
    raw_bytes: bytes,
    source_reference: Mapping[str, object],
    source_set_manifest: Mapping[str, object],
    approved_concepts: Sequence[str],
    allowed_ciks: Sequence[str],
    include_instant: bool,
) -> List[Dict[str, object]]:
    """Adapt Company Facts bytes into deterministic numeric claims.

    Args:
        raw_bytes: Exact hash-verified SEC Company Facts response.
        source_reference: Company Facts SourceReference.
        source_set_manifest: Complete singleton source-set proof.
        approved_concepts: Declarative concept candidates.
        allowed_ciks: Registry-authorized CIK set.
        include_instant: Whether balance-sheet instant facts are allowed.

    Returns:
        Ordered deterministic numeric claims.
    """
    reference = _reference(value=source_reference)
    _require_raw_bytes(source_reference=reference, raw_bytes=raw_bytes)
    facts = companyfacts_structured_facts(
        raw_bytes=raw_bytes,
        source_reference=reference,
        approved_concepts=approved_concepts,
        allowed_ciks=allowed_ciks,
        include_instant=include_instant,
    )
    claims = []
    for fact in facts:
        claims.append(
            verified_claim(
                claim_kind="COMPANYFACTS_NUMERIC_FACT",
                source_reference=reference,
                source_set_manifest=source_set_manifest,
                locator={
                    "concept": fact["concept"],
                    "fact_id": fact["fact_id"],
                    "period_start": fact["period_start"],
                    "period_end": fact["period_end"],
                },
                value=str(fact["value"]),
                unit=str(fact["unit"]),
                attributes={
                    "accession": fact["accession"],
                    "entity": fact["entity"],
                    "filed": fact["filed"],
                    "fiscal_period": fact["fiscal_period"],
                    "form": fact["form"],
                    "frame": fact["source_binding"]["frame"],
                },
            )
        )
    return sorted(claims, key=lambda claim: str(claim["verified_claim_id"]))


class _XbrlContextParser(HTMLParser):
    """Capture period, entity, and explicit dimensions for XBRL contexts."""

    def __init__(self) -> None:
        """Initialize one empty bounded context index."""
        super().__init__(convert_charrefs=True)
        self.active_context: Optional[Dict[str, object]] = None
        self.active_fields: List[Dict[str, object]] = []
        self.output: Dict[str, Dict[str, object]] = {}

    @staticmethod
    def _local_tag(*, tag: str) -> str:
        """Return one case-folded local XML/HTML tag name."""
        return tag.rsplit(":", maxsplit=1)[-1].casefold()

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        """Open one context field while preserving declared dimension names."""
        local = self._local_tag(tag=tag)
        attributes = {name.casefold(): value for name, value in attrs}
        if local == "context":
            if self.active_context is not None:
                raise DeterministicRouterError("XBRL contexts cannot nest")
            context_id = attributes["id"] if "id" in attributes else None
            if not context_id or context_id in self.output:
                raise DeterministicRouterError("XBRL context id is invalid")
            self.active_context = {
                "context_ref": context_id,
                "dimensions": {},
                "entity_identifier": "",
                "period_end": "",
                "period_start": "",
                "typed_dimension_count": 0,
            }
            return
        if self.active_context is None:
            return
        field_by_tag = {
            "identifier": "entity_identifier",
            "instant": "instant",
            "startdate": "period_start",
            "enddate": "period_end",
            "explicitmember": "explicit_member",
        }
        if local in field_by_tag:
            field = {
                "field": field_by_tag[local],
                "parts": [],
                "tag": tag,
            }
            if local == "explicitmember":
                dimension = (
                    attributes["dimension"]
                    if "dimension" in attributes
                    else None
                )
                if not dimension:
                    raise DeterministicRouterError(
                        "XBRL explicit dimension is absent"
                    )
                field["dimension"] = dimension
            self.active_fields.append(field)
        elif local == "typedmember":
            self.active_context["typed_dimension_count"] = int(
                self.active_context["typed_dimension_count"]
            ) + 1

    def handle_data(self, data: str) -> None:
        """Accumulate exact visible content for the innermost context field."""
        if self.active_fields:
            self.active_fields[-1]["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        """Close one context field or publish one complete context."""
        local = self._local_tag(tag=tag)
        if self.active_fields and self.active_fields[-1]["tag"] == tag:
            field = self.active_fields.pop()
            text = " ".join("".join(field["parts"]).split())
            if not text or self.active_context is None:
                raise DeterministicRouterError("XBRL context field is empty")
            if field["field"] == "explicit_member":
                dimensions = self.active_context["dimensions"]
                dimension = str(field["dimension"])
                if dimension in dimensions:
                    raise DeterministicRouterError(
                        "XBRL context dimension is duplicated"
                    )
                dimensions[dimension] = text
            elif field["field"] == "instant":
                self.active_context["period_start"] = text
                self.active_context["period_end"] = text
            else:
                self.active_context[str(field["field"])] = text
        if local != "context":
            return
        if self.active_context is None or self.active_fields:
            raise DeterministicRouterError("XBRL context markup is incomplete")
        context = dict(self.active_context)
        if not all(
            isinstance(context[field], str) and context[field]
            for field in ("entity_identifier", "period_start", "period_end")
        ):
            raise DeterministicRouterError("XBRL context identity is incomplete")
        context_id = str(context["context_ref"])
        self.output[context_id] = context
        self.active_context = None

    def contexts(self) -> Dict[str, Dict[str, object]]:
        """Return the complete context index after parsing."""
        if self.active_context is not None or self.active_fields:
            raise DeterministicRouterError("XBRL context stream is incomplete")
        if not self.output:
            raise DeterministicRouterError("XBRL source contains no contexts")
        return {key: dict(value) for key, value in self.output.items()}


class _XbrlFactParser(HTMLParser):
    """Capture bounded XBRL or inline-XBRL facts without script execution."""

    def __init__(self) -> None:
        """Initialize an empty bounded fact stream."""
        super().__init__(convert_charrefs=True)
        self.active: List[Dict[str, object]] = []
        self.output: List[Dict[str, object]] = []
        self.total_text = 0
        self.ordinal = 0

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        """Open one fact when the element declares a context reference."""
        attributes = {name.casefold(): value for name, value in attrs}
        context_ref = attributes["contextref"] if "contextref" in attributes else None
        if context_ref is None:
            return
        self.ordinal += 1
        if self.ordinal > MAX_XBRL_FACTS:
            raise DeterministicRouterError("XBRL fact count exceeds limit")
        qualified_name = (
            attributes["name"]
            if "name" in attributes and attributes["name"]
            else tag
        )
        self.active.append(
            {
                "tag": tag,
                "qualified_name": qualified_name,
                "context_ref": context_ref,
                "unit_ref": attributes["unitref"] if "unitref" in attributes else "",
                "scale": attributes["scale"] if "scale" in attributes else "0",
                "sign": attributes["sign"] if "sign" in attributes else "",
                "ordinal": self.ordinal,
                "parts": [],
            }
        )

    def handle_data(self, data: str) -> None:
        """Append visible fact text while enforcing one aggregate ceiling."""
        if not self.active:
            return
        self.total_text += len(data)
        if self.total_text > MAX_XBRL_TEXT:
            raise DeterministicRouterError("XBRL fact text exceeds limit")
        for fact in self.active:
            fact["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        """Close the most recent matching fact and preserve document order."""
        matching = [
            index for index, fact in enumerate(self.active) if fact["tag"] == tag
        ]
        if not matching:
            return
        index = matching[-1]
        fact = self.active.pop(index)
        fact["text"] = " ".join("".join(fact.pop("parts")).split())
        self.output.append(fact)

    def facts(self) -> List[Dict[str, object]]:
        """Return the complete ordered fact list after parsing."""
        if self.active:
            raise DeterministicRouterError("XBRL fact markup is incomplete")
        return list(self.output)


def _local_name(*, qualified_name: str) -> str:
    """Return one XBRL local-name token.

    Args:
        qualified_name: Prefixed or expanded fact name.

    Returns:
        Local token used for declarative fact-name matching.
    """
    if "}" in qualified_name:
        return qualified_name.rsplit("}", maxsplit=1)[1]
    return qualified_name.split(":", maxsplit=1)[-1]


def _numeric_xbrl_value(*, text: str, scale: str, sign: str) -> str:
    """Normalize one numeric XBRL lexical value to fixed-point text.

    Args:
        text: Visible numeric fact text.
        scale: Base-ten inline-XBRL scale.
        sign: Optional inline-XBRL negative marker.

    Returns:
        Canonical fixed-point value.
    """
    lexical = text.replace(",", "").replace(" ", "")
    if lexical.startswith("(") and lexical.endswith(")"):
        lexical = "-" + lexical[1:-1]
    try:
        scale_value = int(scale)
        if scale_value < -18 or scale_value > 18:
            raise DeterministicRouterError("XBRL scale exceeds limit")
        value = Decimal(lexical) * (Decimal(10) ** scale_value)
    except (InvalidOperation, ValueError) as error:
        raise DeterministicRouterError("XBRL numeric fact is invalid") from error
    if sign == "-" and value > 0:
        value = -value
    return decimal_text(value=value)


def _parse_xbrl_parts(*, raw_bytes: bytes) -> Tuple[Dict[str, Dict[str, object]], List[Dict[str, object]]]:
    """Run the unchanged native context/fact parsers once over exact bytes."""
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DeterministicRouterError("XBRL bytes are not UTF-8") from error
    context_parser = _XbrlContextParser()
    context_parser.feed(text)
    context_parser.close()
    contexts = context_parser.contexts()
    parser = _XbrlFactParser()
    parser.feed(text)
    parser.close()
    return contexts, parser.facts()


_PARSED_XBRL_FACTORY = object()


def _freeze_xbrl_owned(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze_xbrl_owned(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze_xbrl_owned(item) for item in value)
    return value


@dataclass(frozen=True, init=False)
class ParsedAccessionXbrlSource:
    """Exact-source-owned immutable parsed facts; no global/persistent cache."""

    source_sha256: str
    source_size: int
    parsed_source_id: str
    contexts: Mapping
    facts: Tuple
    _factory: object

    def __init__(self, *, source_sha256, source_size, contexts, facts, factory):
        if factory is not _PARSED_XBRL_FACTORY:
            raise DeterministicRouterError("Parsed XBRL source requires its native factory")
        identity = {"source_sha256": source_sha256, "source_size": source_size,
                    "contexts": contexts, "facts": facts, "parser_generation": "NATIVE_XBRL_PARTS_V1"}
        object.__setattr__(self, "source_sha256", source_sha256)
        object.__setattr__(self, "source_size", source_size)
        object.__setattr__(self, "parsed_source_id", content_hash(value=identity))
        object.__setattr__(self, "contexts", _freeze_xbrl_owned(contexts))
        object.__setattr__(self, "facts", _freeze_xbrl_owned(facts))
        object.__setattr__(self, "_factory", factory)


def parse_accession_xbrl_source(*, raw_bytes: bytes) -> ParsedAccessionXbrlSource:
    """Create one exact SHA/size/content-ID-bound process-local native parse."""
    if type(raw_bytes) is not bytes:
        raise DeterministicRouterError("Parsed XBRL source must be immutable bytes")
    contexts, facts = _parse_xbrl_parts(raw_bytes=raw_bytes)
    return ParsedAccessionXbrlSource(source_sha256=sha256_bytes(content=raw_bytes),
        source_size=len(raw_bytes), contexts=contexts, facts=facts, factory=_PARSED_XBRL_FACTORY)


def _claims_from_xbrl_parts(*, reference: Mapping, source_set_manifest: Mapping,
                           names: Sequence[str], contexts: Mapping, facts: Sequence[Mapping],
                           adapter_id: str) -> List[Dict[str, object]]:
    """The shared native fact matcher/normalizer, independent of parse reuse."""
    claims = []
    folded_names = {name.casefold() for name in names}
    for fact in facts:
        qualified_name = str(fact["qualified_name"])
        if (
            qualified_name.casefold() not in folded_names
            and _local_name(qualified_name=qualified_name).casefold()
            not in folded_names
        ):
            continue
        canonical_names = [
            name for name in names
            if name.casefold() == qualified_name.casefold()
            or name.casefold()
            == _local_name(qualified_name=qualified_name).casefold()
        ]
        if len(canonical_names) != 1:
            raise DeterministicRouterError(
                "XBRL fact canonical name is absent or ambiguous"
            )
        unit_ref = str(fact["unit_ref"])
        fact_text = str(fact["text"])
        if not fact_text:
            continue
        numeric = bool(unit_ref)
        value = (
            _numeric_xbrl_value(
                text=fact_text,
                scale=str(fact["scale"]),
                sign=str(fact["sign"]),
            )
            if numeric
            else " ".join(fact_text.split())
        )
        context_ref = str(fact["context_ref"])
        if context_ref not in contexts:
            raise DeterministicRouterError("XBRL fact context is absent")
        context = contexts[context_ref]
        if type(context) is not dict:
            context = {**context, "dimensions": dict(context["dimensions"])}
        claims.append(
            verified_claim(
                claim_kind=(
                    adapter_id + "_NUMERIC_FACT"
                    if numeric
                    else adapter_id + "_TEXT_FACT"
                ),
                source_reference=reference,
                source_set_manifest=source_set_manifest,
                locator={
                    "qualified_name": qualified_name,
                    "context_ref": fact["context_ref"],
                    "ordinal": fact["ordinal"],
                },
                value=value,
                unit=unit_ref if unit_ref else "text",
                attributes={
                    "adapter_id": adapter_id,
                    "canonical_name": canonical_names[0],
                    "context": context,
                    "lexical_value": fact_text,
                },
            )
        )
    return sorted(claims, key=lambda claim: str(claim["verified_claim_id"]))


def _adapt_xbrl(
    *, raw_bytes: bytes, source_reference: Mapping[str, object],
    source_set_manifest: Mapping[str, object], fact_names: Sequence[str], adapter_id: str,
) -> List[Dict[str, object]]:
    """Adapt exact XBRL bytes through the unchanged native parse/claim path."""
    reference = _reference(value=source_reference)
    _require_raw_bytes(source_reference=reference, raw_bytes=raw_bytes)
    names = _text_list(value=list(fact_names), label="XBRL fact names", allow_empty=False)
    contexts, facts = _parse_xbrl_parts(raw_bytes=raw_bytes)
    return _claims_from_xbrl_parts(reference=reference, source_set_manifest=source_set_manifest,
                                  names=names, contexts=contexts, facts=facts, adapter_id=adapter_id)


def adapt_accession_xbrl_from_parsed(
    *, parsed_source: ParsedAccessionXbrlSource, raw_bytes: bytes,
    source_reference: Mapping[str, object], source_set_manifest: Mapping[str, object],
    fact_names: Sequence[str],
) -> List[Dict[str, object]]:
    """Re-evaluate native claims without reparsing an exact immutable source.

    Raw bytes and SourceReference are still re-bound on every call. Callers
    retain responsibility for the exact disk path/hash/size and Requirement
    pins that own this context; no stored response or claim result is reused.
    """
    if type(parsed_source) is not ParsedAccessionXbrlSource or getattr(parsed_source, "_factory", None) is not _PARSED_XBRL_FACTORY:
        raise DeterministicRouterError("Parsed XBRL context is not factory-owned")
    reference = _reference(value=source_reference)
    _require_raw_bytes(source_reference=reference, raw_bytes=raw_bytes)
    if len(raw_bytes) != parsed_source.source_size or sha256_bytes(content=raw_bytes) != parsed_source.source_sha256:
        raise DeterministicRouterError("Parsed XBRL source SHA/size differs")
    names = _text_list(value=list(fact_names), label="XBRL fact names", allow_empty=False)
    return _claims_from_xbrl_parts(reference=reference, source_set_manifest=source_set_manifest,
        names=names, contexts=parsed_source.contexts, facts=parsed_source.facts, adapter_id="ACCESSION_XBRL")


def adapt_accession_xbrl(
    *, raw_bytes: bytes, source_reference: Mapping[str, object],
    source_set_manifest: Mapping[str, object], fact_names: Sequence[str],
) -> List[Dict[str, object]]:
    """Adapt one accession-level XBRL instance into deterministic claims."""
    return _adapt_xbrl(
        raw_bytes=raw_bytes,
        source_reference=source_reference,
        source_set_manifest=source_set_manifest,
        fact_names=fact_names,
        adapter_id="ACCESSION_XBRL",
    )


def adapt_ecd_xbrl(
    *, raw_bytes: bytes, source_reference: Mapping[str, object],
    source_set_manifest: Mapping[str, object], fact_names: Sequence[str],
) -> List[Dict[str, object]]:
    """Adapt one DEF 14A ECD XBRL source into deterministic claims."""
    return _adapt_xbrl(
        raw_bytes=raw_bytes,
        source_reference=source_reference,
        source_set_manifest=source_set_manifest,
        fact_names=fact_names,
        adapter_id="ECD_XBRL",
    )


def adapt_auditor_fact(
    *, raw_bytes: bytes, source_reference: Mapping[str, object],
    source_set_manifest: Mapping[str, object], fact_names: Sequence[str],
) -> List[Dict[str, object]]:
    """Adapt declaratively named auditor facts without text-model fallback."""
    return _adapt_xbrl(
        raw_bytes=raw_bytes,
        source_reference=source_reference,
        source_set_manifest=source_set_manifest,
        fact_names=fact_names,
        adapter_id="AUDITOR_FACT",
    )


class _VisibleTextParser(HTMLParser):
    """Extract visible filing text for deterministic item-heading briefs."""

    def __init__(self) -> None:
        """Initialize an empty visible-text buffer."""
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        """Preserve non-empty visible text in document order."""
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        """Return whitespace-normalized visible text."""
        return " ".join(" ".join(self.parts).split())


def _visible_text(*, raw_bytes: bytes) -> str:
    """Decode filing bytes and return normalized visible text."""
    text = raw_bytes.decode("utf-8", errors="replace")
    parser = _VisibleTextParser()
    parser.feed(text)
    parser.close()
    return parser.text()


def _normalize_item_code(*, value: str) -> str:
    """Return one canonical SEC 8-K item code."""
    match = re.search(pattern=r"(\d{1,2}\.\d{2})", string=value)
    return match.group(1) if match is not None else value.strip()


def _hdr_item_codes(*, raw_bytes: bytes) -> List[str]:
    """Parse ordered unique item codes from one hdr.sgml source."""
    text = raw_bytes.decode("utf-8", errors="replace")
    repeated = re.findall(
        pattern=r"<ITEMS?>\s*([0-9]{1,2}\.[0-9]{2})",
        string=text,
        flags=re.IGNORECASE,
    )
    if repeated:
        candidates = repeated
    else:
        block = re.search(
            pattern=r"<ITEMS>(.*?)</ITEMS>",
            string=text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        candidates = (
            re.findall(
                pattern=r"<ITEM>(.*?)</ITEM>",
                string=block.group(1),
                flags=re.IGNORECASE | re.DOTALL,
            )
            if block is not None
            else []
        )
    output = []
    for candidate in candidates:
        code = _normalize_item_code(value=candidate)
        if code not in output:
            output.append(code)
    return output


def _primary_item_briefs(*, raw_bytes: bytes) -> List[Tuple[str, str]]:
    """Parse item headings and bounded briefs from a primary document."""
    text = _visible_text(raw_bytes=raw_bytes)
    matches = list(
        re.finditer(
            pattern=r"Item\s+(\d{1,2}\.\d{2})",
            string=text,
            flags=re.IGNORECASE,
        )
    )
    rows = []
    seen = set()
    for match in matches:
        code = match.group(1)
        if code in seen:
            continue
        seen.add(code)
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 220)
        rows.append((code, " ".join(text[start:end].split())))
    return rows


def acquisition_event_source_set_receipt(
    *, filing_documents: Sequence[Mapping[str, object]], company_id: str,
    period_start: str, period_end: str,
) -> Dict[str, object]:
    """Prove one complete repository acquisition-receipt event subset."""
    accessions = []
    filing_dates = []
    reference_ids = []
    request_attempt_ids = []
    for document_value in filing_documents:
        document = _object(
            value=document_value, label="acquired 8-K document"
        )
        hdr = _reference(value=document["hdr_source_reference"])
        primary = _reference(value=document["primary_source_reference"])
        hdr_bytes = document["hdr_bytes"]
        primary_bytes = document["primary_document_bytes"]
        if not isinstance(hdr_bytes, bytes) or not isinstance(
            primary_bytes, bytes
        ):
            raise DeterministicRouterError("Acquired 8-K bytes are invalid")
        _require_raw_bytes(source_reference=hdr, raw_bytes=hdr_bytes)
        _require_raw_bytes(source_reference=primary, raw_bytes=primary_bytes)
        try:
            header = hdr_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DeterministicRouterError(
                "Acquired 8-K header is not UTF-8"
            ) from error
        accession_match = re.search(
            pattern=r"<ACCESSION-NUMBER>\s*([^\r\n]+)", string=header,
        )
        form_match = re.search(
            pattern=r"<TYPE>\s*([^\r\n]+)", string=header,
        )
        date_match = re.search(
            pattern=r"<FILING-DATE>\s*([0-9]{8})", string=header,
        )
        if accession_match is None or form_match is None or date_match is None:
            raise DeterministicRouterError("Acquired 8-K identity is absent")
        filed = "{}-{}-{}".format(
            date_match.group(1)[:4], date_match.group(1)[4:6],
            date_match.group(1)[6:],
        )
        accession = accession_match.group(1).strip()
        if (
            accession != hdr["accession"]
            or accession != primary["accession"]
            or hdr["company_id"] != company_id
            or primary["company_id"] != company_id
            or form_match.group(1).strip() not in {"8-K", "8-K/A"}
            or not period_start <= filed <= period_end
        ):
            raise DeterministicRouterError(
                "Acquired 8-K falls outside its source-set contract"
            )
        accessions.append(accession)
        filing_dates.append({"accession": accession, "filing_date": filed})
        for reference in (hdr, primary):
            reference_ids.append(str(reference["source_reference_id"]))
            request_attempt_ids.append(str(reference["request_attempt_id"]))
    if (
        not accessions
        or accessions != sorted(accessions)
        or len(accessions) != len(set(accessions))
        or len(reference_ids) != len(set(reference_ids))
    ):
        raise DeterministicRouterError(
            "Acquired 8-K source-set order or identity differs"
        )
    body = {
        "schema_version": 1,
        "record_type": "ACQUISITION_EVENT_SOURCE_SET_RECEIPT",
        "company_id": company_id,
        "form_types": ["8-K", "8-K/A"],
        "fiscal_or_date_window": {
            "period_start": period_start,
            "period_end": period_end,
        },
        "ordered_accessions": accessions,
        "filing_dates": filing_dates,
        "ordered_source_reference_ids": reference_ids,
        "request_attempt_ids": request_attempt_ids,
    }
    return {
        **body,
        "acquisition_source_set_receipt_id": content_hash(value=body),
    }


def adapt_8k_item_index(
    *,
    filing_documents: Sequence[Mapping[str, object]],
    source_set_manifest: Mapping[str, object],
    inventory_source_reference: Mapping[str, object],
    inventory_bytes: bytes,
    acquisition_discovery_receipt: Optional[Mapping[str, object]] = None,
) -> List[Dict[str, object]]:
    """Adapt a complete fiscal-year 8-K set into neutral item-brief claims.

    Args:
        filing_documents: Exact rows containing separate hdr/primary
            SourceReferences and bytes for each filing.
        source_set_manifest: Fiscal-year source-set proof.
        inventory_source_reference: Pinned SEC submissions observation.
        inventory_bytes: Exact submissions bytes proving the fiscal-year set.
        acquisition_discovery_receipt: Optional repository acquisition proof
            for filings absent from the pinned submissions response.

    Returns:
        One deterministic claim per unique filing/item code.
    """
    rows = []
    filing_references = []
    for document in filing_documents:
        row = _object(value=document, label="8-K filing document")
        if set(row) != {
            "hdr_bytes",
            "hdr_source_reference",
            "primary_document_bytes",
            "primary_source_reference",
        }:
            raise DeterministicRouterError(
                "8-K filing document fields are not exact"
            )
        if not isinstance(row["hdr_bytes"], bytes) or not isinstance(
            row["primary_document_bytes"], bytes
        ):
            raise DeterministicRouterError("8-K filing bytes are invalid")
        rows.append(row)
        filing_references.extend(
            [row["hdr_source_reference"], row["primary_source_reference"]]
        )
    if acquisition_discovery_receipt is None:
        manifest = verify_source_set_completeness(
            manifest=source_set_manifest,
            inventory_source_reference=inventory_source_reference,
            inventory_bytes=inventory_bytes,
            ordered_source_references=filing_references,
        )
    else:
        manifest = validate_source_set_manifest(manifest=source_set_manifest)
        inventory = _reference(value=inventory_source_reference)
        receipt = acquisition_event_source_set_receipt(
            filing_documents=rows,
            company_id=str(manifest["company_id"]),
            period_start=str(manifest["fiscal_or_date_window"]["period_start"]),
            period_end=str(manifest["fiscal_or_date_window"]["period_end"]),
        )
        if (
            dict(acquisition_discovery_receipt) != receipt
            or manifest["discovery_policy"]
            != "IMMUTABLE_ACQUISITION_LEDGER_FISCAL_WINDOW_V1"
            or manifest["ordered_source_reference_ids"]
            != receipt["ordered_source_reference_ids"]
            or manifest["discovered_accession_set_hash"]
            != content_hash(value=receipt["ordered_accessions"])
            or manifest["inventory_source_reference_id"]
            != inventory["source_reference_id"]
            or manifest["sec_submissions_inventory_hash"]
            != inventory["raw_asset_id"]
        ):
            raise DeterministicRouterError(
                "Acquisition event source-set proof differs"
            )
    claims = []
    for row in rows:
        hdr_reference = _reference(value=row["hdr_source_reference"])
        reference = _reference(value=row["primary_source_reference"])
        _require_raw_bytes(
            source_reference=hdr_reference, raw_bytes=row["hdr_bytes"]
        )
        _require_raw_bytes(
            source_reference=reference,
            raw_bytes=row["primary_document_bytes"],
        )
        document_reference_ids = {
            str(hdr_reference["source_reference_id"]),
            str(reference["source_reference_id"]),
        }
        if (
            hdr_reference["company_id"] != reference["company_id"]
            or hdr_reference["accession"] != reference["accession"]
            or not document_reference_ids.issubset(
                set(manifest["ordered_source_reference_ids"])
            )
        ):
            raise DeterministicRouterError("8-K filing is outside its source set")
        primary_rows = _primary_item_briefs(raw_bytes=row["primary_document_bytes"])
        primary_by_code = {code: brief for code, brief in primary_rows}
        hdr_codes = _hdr_item_codes(raw_bytes=row["hdr_bytes"])
        if hdr_codes:
            item_rows = [
                (
                    code,
                    "8-K item {} parsed from hdr.sgml".format(code),
                    "HDR_SGML_ITEM_CODE",
                )
                for code in hdr_codes
            ]
        else:
            item_rows = [
                (code, brief, "PRIMARY_DOCUMENT_HEADING_FALLBACK")
                for code, brief in primary_rows
            ]
        for code, brief, brief_source in item_rows:
            # Legacy event identity is hdr.sgml when its item code is the
            # authority; primary-document URL is used only for heading
            # fallback.  The brief may still be enriched from primary bytes.
            event_reference = (
                hdr_reference if hdr_codes else reference
            )
            event_key = {
                "source_url": event_reference["source_url"],
                "accession": event_reference["accession"],
                "item_code": code,
            }
            claims.append(
                verified_claim(
                    claim_kind="DETERMINISTIC_8K_ITEM_BRIEF",
                    source_reference=event_reference,
                    source_set_manifest=manifest,
                    locator={"item_code": code, "brief_source": brief_source},
                    value=brief,
                    unit="text",
                    attributes={
                        "accession": reference["accession"],
                        "brief": brief,
                        "brief_source": brief_source,
                        "event_key": event_key,
                        "event_key_hash": content_hash(value=event_key),
                        "hdr_source_reference_id": hdr_reference[
                            "source_reference_id"
                        ],
                        "primary_source_reference_id": reference[
                            "source_reference_id"
                        ],
                        "primary_heading_brief": (
                            primary_by_code[code]
                            if code in primary_by_code
                            else ""
                        ),
                        "item_code": code,
                        "source_url": event_reference["source_url"],
                    },
                )
            )
    identities = [str(claim["verified_claim_id"]) for claim in claims]
    if len(identities) != len(set(identities)):
        raise DeterministicRouterError("8-K item claim identity is duplicated")
    return sorted(
        claims,
        key=lambda claim: (
            str(claim["attributes"]["source_url"]),
            str(claim["attributes"]["accession"]),
            str(claim["attributes"]["item_code"]),
        ),
    )


def load_event_route_catalog(*, repo_root: Path) -> Dict[str, object]:
    """Load and validate the declarative event route catalog.

    Args:
        repo_root: Repository root containing ``catalog/event_routes.json``.

    Returns:
        Exact catalog mapping.
    """
    parsed = strict_json_file(path=repo_root / "catalog" / "event_routes.json")
    catalog = _object(value=parsed, label="event route catalog")
    _exact_fields(
        value=catalog,
        expected=EVENT_CATALOG_FIELDS,
        label="event route catalog",
    )
    if (
        catalog["schema_version"] != 1
        or catalog["record_type"] != "DETERMINISTIC_EVENT_ROUTE_CATALOG"
        or catalog["text_normalization"]
        != "UNICODE_NFKC_CASEFOLD_COLLAPSE_WHITESPACE"
        or catalog["match_mode"] != "SUBSTRING_ANY"
    ):
        raise DeterministicRouterError("Event route catalog policy differs")
    _text_list(
        value=catalog["brief_source_priority"],
        label="event brief source priority",
        allow_empty=False,
    )
    routes = _object(value=catalog["routes"], label="event routes")
    if set(routes) != EVENT_ROUTE_IDS:
        raise DeterministicRouterError("Event route metric exact set differs")
    for metric_id in sorted(routes):
        route = _object(value=routes[metric_id], label="event route " + metric_id)
        _exact_fields(value=route, expected=EVENT_ROUTE_FIELDS, label="event route")
        _text(value=route["metric_name"], label="event metric name")
        direct = _text_list(
            value=route["direct_item_codes"],
            label="event direct item codes",
            allow_empty=True,
        )
        if any(
            re.fullmatch(r"[0-9]{1,2}\.[0-9]{2}", code) is None
            for code in direct
        ):
            raise DeterministicRouterError("Event direct item code is invalid")
        if not isinstance(route["keyword_item_rules"], list):
            raise DeterministicRouterError("Event keyword rules must be an array")
        for rule_value in route["keyword_item_rules"]:
            rule = _object(value=rule_value, label="event keyword rule")
            _exact_fields(
                value=rule,
                expected=KEYWORD_RULE_FIELDS,
                label="event keyword rule",
            )
            _text(value=rule["item_code"], label="keyword item code")
            _text_list(
                value=rule["aliases"], label="event aliases", allow_empty=False
            )
        _text(value=route["shared_claim_group_id"], label="shared claim group id")
        if not isinstance(route["legacy_projection"], dict):
            raise DeterministicRouterError("Event legacy projection is invalid")
    return catalog


def normalize_event_text(*, value: str) -> str:
    """Apply the catalog-frozen event text normalization."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def match_event_claims(
    *, metric_id: str, claims: Sequence[Mapping[str, object]],
    catalog: Mapping[str, object],
) -> List[Dict[str, object]]:
    """Apply one declarative route without metric-specific Python branches.

    Args:
        metric_id: Route identity looked up in catalog data.
        claims: Neutral 8-K item claims.
        catalog: Valid event route catalog.

    Returns:
        Stable matched claim set.
    """
    validated_catalog = _object(value=catalog, label="event route catalog")
    routes = _object(value=validated_catalog["routes"], label="event routes")
    if metric_id not in routes:
        raise DeterministicRouterError("Event route metric is unknown")
    route = _object(value=routes[metric_id], label="event route " + metric_id)
    direct_codes = set(route["direct_item_codes"])
    keyword_rules = {
        str(rule["item_code"]): [
            normalize_event_text(value=str(alias)) for alias in rule["aliases"]
        ]
        for rule in route["keyword_item_rules"]
    }
    matched = []
    for claim_value in claims:
        claim = validate_verified_claim(claim=claim_value)
        if claim["claim_kind"] != "DETERMINISTIC_8K_ITEM_BRIEF":
            raise DeterministicRouterError("Event route received a non-item claim")
        attributes = claim["attributes"]
        item_code = str(attributes["item_code"])
        brief = normalize_event_text(value=str(attributes["brief"]))
        aliases = keyword_rules[item_code] if item_code in keyword_rules else []
        if item_code in direct_codes or any(alias in brief for alias in aliases):
            matched.append(claim)
    return sorted(
        matched,
        key=lambda claim: (
            str(claim["attributes"]["source_url"]),
            str(claim["attributes"]["accession"]),
            str(claim["attributes"]["item_code"]),
        ),
    )


def matched_event_key_set(
    *, metric_id: str, claims: Sequence[Mapping[str, object]],
    catalog: Mapping[str, object],
) -> List[Dict[str, str]]:
    """Return the exact legacy-compatible matched event key set."""
    return [
        {
            "source_url": str(claim["attributes"]["source_url"]),
            "accession": str(claim["attributes"]["accession"]),
            "item_code": str(claim["attributes"]["item_code"]),
        }
        for claim in match_event_claims(
            metric_id=metric_id, claims=claims, catalog=catalog,
        )
    ]


def _compiled_event_spec(
    *, metric_id: str, route: Mapping[str, object]
) -> Dict[str, object]:
    """Compile one direct-numeric Spec whose closure binds its event route."""
    front = {
        "metric_id": metric_id,
        "name": route["metric_name"],
        "kind": "direct_numeric",
        "canonical_unit": "count",
        "unit_policy": "fixed_canonical",
        "source_mode": "structured",
        "applicability": {"all": [], "none": []},
        "identity_constraints": [],
        "legacy_projection": {
            **dict(route["legacy_projection"]),
            "event_route_hash": content_hash(value=dict(route)),
        },
        "dependencies": [],
    }
    text = "---\n{}\n---\n\n# {}\n".format(
        json.dumps(front, ensure_ascii=False, indent=2), route["metric_name"]
    )
    return compile_spec(text=text)


def project_event_result(
    *,
    metric_id: str,
    claims: Sequence[Mapping[str, object]],
    source_set_manifest: Mapping[str, object],
    inventory_source_reference: Mapping[str, object],
    target_period: Mapping[str, object],
    catalog: Mapping[str, object],
) -> Dict[str, object]:
    """Project neutral item claims through Observation, Result, and Trace.

    Args:
        metric_id: Declarative event route identity.
        claims: Complete neutral item-brief claim set.
        source_set_manifest: Complete fiscal-year 8-K source-set proof.
        inventory_source_reference: SEC submissions SourceReference anchoring
            closed-world zero and positive counts.
        target_period: Exact fiscal year and inclusive date window.
        catalog: Valid declarative event route catalog.

    Returns:
        Matched claim IDs, VerifiedObservation, MetricResult, and Trace.
    """
    manifest = validate_source_set_manifest(manifest=source_set_manifest)
    inventory = _reference(value=inventory_source_reference)
    if (
        inventory["source_reference_id"] != manifest["inventory_source_reference_id"]
        or inventory["raw_asset_id"] != manifest["sec_submissions_inventory_hash"]
    ):
        raise DeterministicRouterError("Event inventory SourceReference differs")
    if not isinstance(target_period, dict) or set(target_period) != {
        "fiscal_year",
        "period_end",
        "period_start",
    }:
        raise DeterministicRouterError("Event target period fields are not exact")
    routes = _object(value=catalog["routes"], label="event routes")
    route = _object(value=routes[metric_id], label="event route " + metric_id)
    matched = match_event_claims(metric_id=metric_id, claims=claims, catalog=catalog)
    scope = {
        "coverage": "fiscal_year_source_set",
        "fiscal_year": target_period["fiscal_year"],
        "shared_claim_group_id": route["shared_claim_group_id"],
    }
    source_binding = {
        "raw_asset_id": inventory["raw_asset_id"],
        "source_reference_id": inventory["source_reference_id"],
        "accession": inventory["accession"],
        "document_name": inventory["document_name"],
        "source_role": manifest["source_role"],
        "source_set_manifest_id": manifest["source_set_manifest_id"],
        "matched_verified_claim_ids": [
            claim["verified_claim_id"] for claim in matched
        ],
        "ordered_source_reference_ids": list(
            manifest["ordered_source_reference_ids"]
        ),
    }
    observation = structured_observation(
        metric_id=metric_id,
        semantic_role="event_count",
        company_id=str(manifest["company_id"]),
        period_start=str(target_period["period_start"]),
        period_end=str(target_period["period_end"]),
        scope=scope,
        value=str(len(matched)),
        unit="count",
        quality="EXACT",
        source_binding=source_binding,
    )
    result, trace = calculate_observation_metric(
        compiled_spec=_compiled_event_spec(metric_id=metric_id, route=route),
        target={
            "company_id": manifest["company_id"],
            "period_start": target_period["period_start"],
            "period_end": target_period["period_end"],
            "scope": scope,
            "scope_key": scope_key(scope=scope),
        },
        company_traits=[],
        observation=observation,
    )
    return {
        "matched_verified_claim_ids": [
            claim["verified_claim_id"] for claim in matched
        ],
        "observation": observation,
        "result": result,
        "trace": trace,
    }
