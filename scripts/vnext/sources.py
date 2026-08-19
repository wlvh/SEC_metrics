"""Adapt existing repository bytes into RawBlob and SourceReference records."""

from __future__ import annotations

import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from sec_http import validate_official_sec_url

from .canonical import CanonicalError, content_hash, decimal_text
from .canonical import sha256_bytes, strict_json_loads
from .records import validate_record


class SourceError(ValueError):
    """Report an unsafe path or incomplete source identity."""


_SEC_ARCHIVE_FILING = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/"
    r"([0-9]{1,10})/([0-9]{18})/([^/?#]+)$"
)


def validate_public_sec_filing_identity(
    *,
    raw_blob: Mapping[str, object],
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    allowed_ciks: Sequence[str],
) -> Dict[str, str]:
    """Verify one live Reader source is an exact registry-owned SEC filing.

    Args:
        raw_blob: Valid exact-byte RawBlob selected for Reader input.
        source_url: Exact SEC Archives primary-document URL.
        accession: Hyphenated filing accession bound to the Run.
        document_name: Primary filing document name bound to the Run.
        source_role: Required Run role; live Reader accepts target_primary only.
        allowed_ciks: Registry-authorized unpadded CIKs for the logical company.

    Returns:
        Normalized CIK, accession, and document identity proven by the URL.

    Raises:
        SourceError: Before egress when media, role, URL, company, accession, or
        document identity is not the exact public SEC filing authority.
    """
    validate_record(record=dict(raw_blob))
    if (
        raw_blob["record_type"] != "RAW_BLOB"
        or raw_blob["media_type"] != "text/html"
        or source_role != "target_primary"
    ):
        raise SourceError(
            "Live Reader requires one target_primary SEC HTML filing"
        )
    if (
        not isinstance(allowed_ciks, Sequence)
        or isinstance(allowed_ciks, (str, bytes))
        or not allowed_ciks
        or any(
            type(cik) is not str or not cik.isdigit() or int(cik) <= 0
            for cik in allowed_ciks
        )
    ):
        raise SourceError("Live Reader company CIK authority is invalid")
    try:
        validate_official_sec_url(url=source_url)
    except ValueError as error:
        raise SourceError(
            "Live Reader source is not an official SEC filing"
        ) from error
    match = _SEC_ARCHIVE_FILING.fullmatch(source_url)
    if match is None:
        raise SourceError(
            "Live Reader source is not an exact SEC Archives document"
        )
    cik = str(int(match.group(1)))
    compact = match.group(2)
    url_accession = "{}-{}-{}".format(
        compact[:10], compact[10:12], compact[12:]
    )
    if (
        cik not in {str(int(value)) for value in allowed_ciks}
        or accession != url_accession
        or document_name != match.group(3)
    ):
        raise SourceError(
            "Live Reader filing identity differs from registry authority"
        )
    return {
        "cik": cik,
        "accession": url_accession,
        "document_name": match.group(3),
    }


def resolve_repository_file(
    *, repo_root: Path, repo_relative_path: str
) -> Path:
    """Resolve one repository-relative regular file without following aliases.

    Args:
        repo_root: Repository root.
        repo_relative_path: Normalized portable path.

    Returns:
        Existing regular path inside ``repo_root``.

    Raises:
        SourceError: On traversal, symlink, directory, missing file, or escape
            from the repository root.
    """
    relative = Path(repo_relative_path)
    if (
        repo_relative_path in {"", "."}
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != repo_relative_path
    ):
        raise SourceError("Source path escapes repository")
    current = repo_root
    for part in relative.parts:
        current /= part
        if os.path.lexists(current) and current.is_symlink():
            raise SourceError(
                "Source path contains a symlink: {}".format(current)
            )
    try:
        current.resolve(strict=False).relative_to(repo_root.resolve())
    except ValueError as error:
        raise SourceError("Source path resolves outside repository") from error
    if not current.is_file():
        raise SourceError(
            "Source path is not a regular file: {}".format(current)
        )
    return current


def raw_blob_record(
    *, repo_root: Path, repo_relative_path: str, media_type: str
) -> Dict[str, object]:
    """Create a content-addressed RawBlob view over existing exact bytes.

    Args:
        repo_root: Repository root.
        repo_relative_path: Existing source path; bytes are referenced rather
            than copied into ``artifacts/vnext``.
        media_type: Explicit media type.

    Returns:
        Strict ``RAW_BLOB`` record.
    """
    if not media_type:
        raise SourceError("RawBlob media_type is required")
    path = resolve_repository_file(
        repo_root=repo_root, repo_relative_path=repo_relative_path,
    )
    content = path.read_bytes()
    record = {
        "record_type": "RAW_BLOB",
        "raw_asset_id": "sha256:" + sha256_bytes(content=content),
        "byte_length": len(content),
        "media_type": media_type,
        "storage_uri": repo_relative_path,
    }
    return validate_record(record=record)


def source_reference_record(
    *,
    raw_blob: Dict[str, object],
    company_id: str,
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    request_attempt_id: str,
) -> Dict[str, object]:
    """Bind exact bytes to one company/accession/document observation.

    Args:
        raw_blob: Valid ``RAW_BLOB`` record.
        company_id: Logical company identity.
        source_url: Official source URL.
        accession: SEC accession identity.
        document_name: Filing document identity.
        source_role: Role in the Run, such as target primary filing.
        request_attempt_id: Existing request ledger attempt identity.

    Returns:
        Strict SourceReference. Two observations of the same bytes remain
        distinct when their filing identity differs.
    """
    validate_record(record=raw_blob)
    if raw_blob["record_type"] != "RAW_BLOB":
        raise SourceError("SourceReference requires a RawBlob")
    required_text = {
        "company_id": company_id,
        "source_url": source_url,
        "accession": accession,
        "document_name": document_name,
        "source_role": source_role,
        "request_attempt_id": request_attempt_id,
    }
    missing = sorted(key for key in required_text if not required_text[key])
    if missing:
        raise SourceError(
            "SourceReference fields are empty: {}".format(",".join(missing))
        )
    # Reuse the production transport's exact-origin rule so source provenance
    # cannot accept an authority that the SEC client would refuse to request.
    try:
        validate_official_sec_url(url=source_url)
    except ValueError as error:
        raise SourceError(
            "SourceReference URL must use an official SEC origin"
        ) from error
    identity = {
        "raw_asset_id": raw_blob["raw_asset_id"],
        "company_id": company_id,
        "source_url": source_url,
        "accession": accession,
        "document_name": document_name,
        "source_role": source_role,
    }
    record = {
        "record_type": "SOURCE_REFERENCE",
        "source_reference_id": content_hash(value=identity),
        "raw_asset_id": raw_blob["raw_asset_id"],
        "company_id": company_id,
        "source_url": source_url,
        "accession": accession,
        "document_name": document_name,
        "source_role": source_role,
        "request_attempt_id": request_attempt_id,
    }
    return validate_record(record=record)


def load_raw_blob_bytes(
    *, repo_root: Path, raw_blob: Dict[str, object]
) -> bytes:
    """Load and revalidate bytes referenced by a RawBlob record.

    Args:
        repo_root: Repository root.
        raw_blob: Valid RawBlob record.

    Returns:
        Exact bytes whose hash and length match the record.

    Raises:
        SourceError: When the referenced bytes have moved or changed.
    """
    validate_record(record=raw_blob)
    path = resolve_repository_file(
        repo_root=repo_root, repo_relative_path=str(raw_blob["storage_uri"]),
    )
    content = path.read_bytes()
    expected_id = "sha256:" + sha256_bytes(content=content)
    if expected_id != raw_blob["raw_asset_id"]:
        raise SourceError("RawBlob content hash mismatch")
    if len(content) != raw_blob["byte_length"]:
        raise SourceError("RawBlob byte length mismatch")
    return content


def _iso_date(*, value: object, field: str) -> date:
    """Parse one required Company Facts ISO date.

    Args:
        value: Parsed JSON field value.
        field: Diagnostic field name.

    Returns:
        Exact calendar date.

    Raises:
        SourceError: When the field is not non-empty ISO date text.
    """
    if type(value) is not str or not value:
        raise SourceError(
            "Company Facts {} must be date text".format(field)
        )
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise SourceError(
            "Company Facts {} is not an ISO date".format(field)
        ) from error


def _companyfacts_text(
    *, fact: Mapping[str, object], field: str
) -> str:
    """Return one required non-empty Company Facts text field.

    Args:
        fact: Raw SEC fact object.
        field: Required field name.

    Returns:
        Exact text value.

    Raises:
        SourceError: When the field is missing, non-text, or empty.
    """
    if (
        field not in fact
        or type(fact[field]) is not str
        or not fact[field]
    ):
        raise SourceError(
            "Company Facts {} is missing or empty".format(field)
        )
    return str(fact[field])


def companyfacts_structured_facts(
    *,
    raw_bytes: bytes,
    source_reference: Mapping[str, object],
    approved_concepts: Sequence[str],
    allowed_ciks: Sequence[str],
    include_instant: bool,
) -> List[Dict[str, object]]:
    """Adapt exact SEC Company Facts bytes into calculator candidates.

    Args:
        raw_bytes: Hash-verified SEC Company Facts response bytes.
        source_reference: Run-bound SourceReference for those bytes.
        approved_concepts: Repository-Spec concept names worth materializing.
        allowed_ciks: Registry-authorized CIKs for the logical company.
        include_instant: Whether facts with one instant date may be emitted;
            false preserves the annual-duration calculator contract.

    Returns:
        Deterministic structured facts carrying portable source bindings.

    Raises:
        SourceError: On malformed JSON, identity disagreement, unsupported
            values, or an unsafe concept/fact shape.
    """
    validated = validate_record(record=source_reference)
    if validated["record_type"] != "SOURCE_REFERENCE":
        raise SourceError("Company Facts source is not a SourceReference")
    if (
        "sha256:" + sha256_bytes(content=raw_bytes)
        != validated["raw_asset_id"]
    ):
        raise SourceError("Company Facts bytes differ from SourceReference")
    if (
        not approved_concepts
        or any(
            type(concept) is not str or not concept
            for concept in approved_concepts
        )
    ):
        raise SourceError("Approved Company Facts concepts are invalid")
    normalized_ciks = []
    for cik in allowed_ciks:
        if type(cik) is not str or not cik.isdigit() or int(cik) <= 0:
            raise SourceError("Allowed Company Facts CIK is invalid")
        normalized_ciks.append(str(int(cik)))
    if not normalized_ciks or len(normalized_ciks) != len(
        set(normalized_ciks)
    ):
        raise SourceError("Allowed Company Facts CIK set is invalid")
    try:
        payload = strict_json_loads(text=raw_bytes.decode("utf-8"))
    except (CanonicalError, UnicodeDecodeError) as error:
        raise SourceError(
            "Company Facts bytes are not strict UTF-8 JSON"
        ) from error
    if (
        not isinstance(payload, dict)
        or "cik" not in payload
        or "facts" not in payload
        or not isinstance(payload["facts"], dict)
    ):
        raise SourceError("Company Facts root is incomplete")
    raw_cik = payload["cik"]
    if type(raw_cik) is int:
        cik = str(raw_cik)
    elif type(raw_cik) is str and raw_cik.isdigit():
        cik = str(int(raw_cik))
    else:
        raise SourceError("Company Facts root CIK is invalid")
    if cik not in normalized_ciks:
        raise SourceError("Company Facts CIK differs from company registry")
    padded_cik = cik.zfill(10)
    expected_name = "CIK{}.json".format(padded_cik)
    expected_url = (
        "https://data.sec.gov/api/xbrl/companyfacts/" + expected_name
    )
    if (
        validated["document_name"] != expected_name
        or validated["source_url"] != expected_url
    ):
        raise SourceError("Company Facts locator differs from root CIK")
    facts_root = payload["facts"]
    output = []
    for approved in sorted(set(approved_concepts)):
        if ":" in approved:
            taxonomy, local_name = approved.split(":", 1)
            locations = [(taxonomy, local_name, approved)]
        else:
            locations = [
                (str(taxonomy), approved, approved)
                for taxonomy in facts_root
                if isinstance(facts_root[taxonomy], dict)
                and approved in facts_root[taxonomy]
            ]
        for taxonomy, local_name, output_concept in locations:
            if taxonomy not in facts_root:
                continue
            concepts = facts_root[taxonomy]
            if not isinstance(concepts, dict):
                raise SourceError("Company Facts taxonomy is not an object")
            if local_name not in concepts:
                continue
            concept = concepts[local_name]
            if (
                not isinstance(concept, dict)
                or "units" not in concept
                or not isinstance(concept["units"], dict)
            ):
                raise SourceError("Company Facts concept units are invalid")
            for unit in concept["units"]:
                fact_list = concept["units"][unit]
                if type(unit) is not str or not unit or not isinstance(
                    fact_list, list
                ):
                    raise SourceError("Company Facts unit bucket is invalid")
                for fact in fact_list:
                    if not isinstance(fact, dict):
                        raise SourceError(
                            "Company Facts fact is not an object"
                        )
                    instant = (
                        "start" not in fact
                        or fact["start"] is None
                        or fact["start"] == ""
                    )
                    if instant and not include_instant:
                        continue
                    if "end" not in fact:
                        raise SourceError("Company Facts end is missing")
                    period_end = _iso_date(value=fact["end"], field="end")
                    if instant:
                        period_start = period_end
                        duration_days = 0
                    else:
                        period_start = _iso_date(
                            value=fact["start"], field="start",
                        )
                        duration_days = (period_end - period_start).days + 1
                        if duration_days <= 0:
                            raise SourceError(
                                "Company Facts duration must be positive"
                            )
                    accession = _companyfacts_text(
                        fact=fact, field="accn",
                    )
                    # One SourceReference represents one filing observation
                    # over shared Company Facts bytes. Other accessions need
                    # their own SourceReference rather than borrowed identity.
                    if accession != validated["accession"]:
                        continue
                    filed = _companyfacts_text(fact=fact, field="filed")
                    _iso_date(value=filed, field="filed")
                    fiscal_period = _companyfacts_text(
                        fact=fact, field="fp",
                    )
                    form = _companyfacts_text(fact=fact, field="form")
                    if "val" not in fact or type(fact["val"]) not in {
                        int,
                        Decimal,
                    }:
                        raise SourceError("Company Facts value is invalid")
                    value = Decimal(fact["val"])
                    fact_identity = {
                        "taxonomy": taxonomy,
                        "concept": local_name,
                        "unit": unit,
                        "fact": fact,
                    }
                    source_binding = {
                        "raw_asset_id": validated["raw_asset_id"],
                        "source_reference_id": validated[
                            "source_reference_id"
                        ],
                        "accession": validated["accession"],
                        "document_name": validated["document_name"],
                        "source_role": validated["source_role"],
                        "entity": cik,
                    }
                    output.append(
                        {
                            "accession": accession,
                            "concept": output_concept,
                            "duration_days": duration_days,
                            "entity": cik,
                            "fact_id": "fact:" + content_hash(
                                value=fact_identity
                            ),
                            "filed": filed,
                            "fiscal_period": fiscal_period,
                            "form": form,
                            "period_start": period_start.isoformat(),
                            "period_end": period_end.isoformat(),
                            "source_binding": source_binding,
                            "unit": unit,
                            "value": decimal_text(value=value),
                        }
                    )
    return output
