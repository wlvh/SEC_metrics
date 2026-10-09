"""SEC request/body/header identity checks without release or Run dependencies."""
from pathlib import Path
from typing import Dict, Mapping
from urllib.parse import urlsplit
from sec_http import legacy_response_snapshot_paths, parse_request_log_rows, request_accession
from sec_http import request_log_attempt_id, request_headers_bytes_match_identity, validate_request_log_manifest
from .canonical import sha256_bytes
from .sources import SourceError, resolve_repository_file

class BatchWorkflowError(RuntimeError):
    """Report an incomplete source, ledger, Spec, or release Run."""


REQUEST_BINDING_PROOF_FIELDS = {
    "request_body_sha256",
    "request_body_size",
    "request_headers_repo_relative_path",
    "request_headers_sha256",
    "request_headers_size",
    "request_locator_kind",
    "request_repo_relative_path",
}


def _verified_request_locator(
    *, repo_root: Path, row: Mapping[str, str], source_url: str,
    content_sha256: str, document_name: str,
) -> Dict[str, object]:
    """Verify one ledger-declared body/header pair and bind exact bytes.

    Args:
        repo_root: Repository containing the row-declared request artifacts.
        row: Exact parsed request-ledger row.
        source_url: SEC URL already joined to the planned source.
        content_sha256: Expected response body SHA-256.
        document_name: Expected response document name.

    Returns:
        Locator class, exact portable paths, and body/header hashes and sizes.

    Raises:
        BatchWorkflowError: When either locator is unsafe, its bytes differ,
            or an immutable-looking pair is not the derived immutable pair.
    """
    body_locator = str(row["repo_relative_path"])
    headers_locator = str(row["headers_repo_relative_path"])
    body_claims_attempt = body_locator.startswith(
        "evidence/request_attempts/"
    )
    headers_claims_attempt = headers_locator.startswith(
        "evidence/request_attempts/"
    )
    if body_claims_attempt != headers_claims_attempt:
        raise BatchWorkflowError(
            "Request-ledger immutable locator pair is incomplete"
        )
    try:
        declared_body = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path=body_locator,
        )
        declared_headers = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path=headers_locator,
        )
        if body_claims_attempt:
            expected_body, expected_headers = legacy_response_snapshot_paths(
                workdir=repo_root,
                content_sha256=content_sha256,
                source_url=source_url,
                status_code=str(row["status_code"]),
                content_length=str(row["content_length"]),
                document_name=document_name,
                timestamp_utc=str(row["timestamp_utc"]),
            )
            if (
                declared_body.resolve() != expected_body.resolve()
                or declared_headers.resolve() != expected_headers.resolve()
            ):
                raise BatchWorkflowError(
                    "Request-ledger locator differs from immutable attempt"
                )
        body_bytes = declared_body.read_bytes()
        headers_bytes = declared_headers.read_bytes()
        content_length = int(row["content_length"])
    except BatchWorkflowError:
        raise
    except (OSError, SourceError, ValueError) as error:
        raise BatchWorkflowError(
            "Request-ledger locator evidence is invalid"
        ) from error
    if (
        len(body_bytes) != content_length
        or sha256_bytes(content=body_bytes) != content_sha256
        or not request_headers_bytes_match_identity(
            content=headers_bytes,
            content_sha256=content_sha256,
            source_url=source_url,
            status_code=str(row["status_code"]),
            content_length=str(row["content_length"]),
        )
    ):
        raise BatchWorkflowError(
            "Request-ledger locator bytes differ from observation"
        )
    return {
        "request_body_sha256": sha256_bytes(content=body_bytes),
        "request_body_size": len(body_bytes),
        "request_headers_repo_relative_path": headers_locator,
        "request_headers_sha256": sha256_bytes(content=headers_bytes),
        "request_headers_size": len(headers_bytes),
        "request_locator_kind": (
            "IMMUTABLE_ATTEMPT"
            if body_claims_attempt
            else "LEGACY_WORKING_LOCATOR"
        ),
        "request_repo_relative_path": body_locator,
    }


def request_attempt_binding(
    *,
    repo_root: Path,
    source_url: str,
    content_sha256: str,
    accession: str,
    document_name: str,
) -> Dict[str, object]:
    """Select the latest verified immutable attempt for one SEC response.

    Args:
        repo_root: Repository containing the append-only request ledger.
        source_url: Exact official SEC request URL.
        content_sha256: Exact response-body digest without a prefix.
        accession: SourceReference filing identity. Company Facts requests may
            have an empty ledger accession while the selected fact does not.
        document_name: Exact response document name.

    Returns:
        Attempt identity, declared body/header locators, and locator class.
        Historical working locators remain usable by offline recorded Runs,
        but formal Cutover separately requires ``IMMUTABLE_ATTEMPT``.

    Raises:
        BatchWorkflowError: When the ledger is stale, exact source is absent,
            a claimed immutable locator is invalid, or legacy matches are
            ambiguous.

    Why:
        Re-fetching identical public bytes legitimately creates several
        ordered attempts. Selecting the latest verified immutable row avoids
        ambiguity without letting a direct working-file locator masquerade as
        publication evidence.
    """
    log_path = repo_root / "evidence" / "requests_log.csv"
    try:
        validate_request_log_manifest(log_path=log_path)
        rows = parse_request_log_rows(
            text=log_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise BatchWorkflowError(
            "Request ledger is unavailable or invalid"
        ) from error
    archive_accession = request_accession(source_url=source_url)
    matches = [
        (row_index, row)
        for row_index, row in enumerate(rows)
        if row["method"] == "GET"
        and row["status_code"] == "200"
        and not row["error"]
        and row["source_url"] == source_url
        and row["content_sha256"] == content_sha256
        and row["document_name"] == document_name
        and (
            row["accession"] == archive_accession == accession
            if archive_accession
            else row["accession"] in {"", accession}
        )
    ]
    if not matches:
        raise BatchWorkflowError(
            "Exact SEC response has no request-ledger attempt"
        )
    immutable = []
    legacy = []
    for row_index, row in matches:
        body_locator = str(row["repo_relative_path"])
        headers_locator = str(row["headers_repo_relative_path"])
        body_claims_attempt = body_locator.startswith(
            "evidence/request_attempts/"
        )
        headers_claims_attempt = headers_locator.startswith(
            "evidence/request_attempts/"
        )
        if body_claims_attempt != headers_claims_attempt:
            raise BatchWorkflowError(
                "Request-ledger immutable locator pair is incomplete"
            )
        if not body_claims_attempt:
            legacy.append((row_index, row))
            continue
        proof = _verified_request_locator(
            repo_root=repo_root,
            row=row,
            source_url=source_url,
            content_sha256=content_sha256,
            document_name=document_name,
        )
        immutable.append((row_index, row, proof))
    if immutable:
        row_index, row, proof = immutable[-1]
    else:
        if len(legacy) != 1:
            raise BatchWorkflowError(
                "Exact SEC response has ambiguous legacy ledger attempts"
            )
        row_index, row = legacy[0]
        proof = _verified_request_locator(
            repo_root=repo_root,
            row=row,
            source_url=source_url,
            content_sha256=content_sha256,
            document_name=document_name,
        )
    return {
        **proof,
        "request_attempt_id": request_log_attempt_id(
            row_index=row_index, row=row,
        ),
    }


def validate_request_attempt_binding(
    *,
    repo_root: Path,
    source_url: str,
    content_sha256: str,
    accession: str,
    document_name: str,
    request_attempt_id: str,
    require_immutable: bool,
) -> Dict[str, object]:
    """Rebuild one named SEC attempt from ledger and exact artifact bytes.

    Args:
        repo_root: Repository containing current ledger and attempt artifacts.
        source_url: Exact official SEC request URL.
        content_sha256: Expected response body digest.
        accession: Expected filing accession.
        document_name: Expected response document identity.
        request_attempt_id: Pinned append-only ledger row identity.
        require_immutable: Whether working-file legacy locators are forbidden.

    Returns:
        Exact attempt ID and mechanically rebuilt body/header locator proof.

    Raises:
        BatchWorkflowError: When the named row, source identity, locator bytes,
        or required immutable locator class differs.

    Why:
        A live Reader must verify the caller-named historical attempt rather
        than silently selecting a later ledger row after an append-only tail.
    """
    if type(require_immutable) is not bool:
        raise BatchWorkflowError("Request binding tier must be explicit")
    log_path = repo_root / "evidence" / "requests_log.csv"
    try:
        validate_request_log_manifest(log_path=log_path)
        rows = parse_request_log_rows(
            text=log_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise BatchWorkflowError(
            "Request ledger is unavailable or invalid"
        ) from error
    matches = [
        (row_index, row)
        for row_index, row in enumerate(rows)
        if request_log_attempt_id(row_index=row_index, row=row)
        == request_attempt_id
    ]
    if len(matches) != 1:
        raise BatchWorkflowError("Planned request attempt is absent")
    row_index, row = matches[0]
    archive_accession = request_accession(source_url=source_url)
    # The requested document identity is the URL's final path component.
    # A pinned immutable attempt may retain a different local storage name;
    # its original path/header pair is still validated using the logged name.
    logical_name = Path(urlsplit(source_url).path).name
    immutable_storage_name = str(row["repo_relative_path"]).startswith("evidence/request_attempts/")
    document_matches = (row["document_name"] == document_name
                        or (immutable_storage_name and document_name == logical_name and bool(logical_name)))
    if (
        row["method"] != "GET"
        or row["status_code"] != "200"
        or row["error"]
        or row["source_url"] != source_url
        or row["content_sha256"] != content_sha256
        or not document_matches
        or (
            (row["accession"] != archive_accession or accession != archive_accession)
            if archive_accession
            else row["accession"] not in {"", accession}
        )
    ):
        raise BatchWorkflowError(
            "Planned request attempt differs from its SEC source"
        )
    proof = _verified_request_locator(
        repo_root=repo_root,
        row=row,
        source_url=source_url,
        content_sha256=content_sha256,
        document_name=row["document_name"],
    )
    if require_immutable and proof["request_locator_kind"] != (
        "IMMUTABLE_ATTEMPT"
    ):
        raise BatchWorkflowError(
            "Live request attempt is not an immutable SEC artifact"
        )
    return {
        **proof,
        "request_attempt_id": request_log_attempt_id(
            row_index=row_index, row=row,
        ),
    }


def validate_planned_request_binding(
    *, repo_root: Path, source: Mapping[str, object]
) -> str:
    """Verify one pinned source-plan attempt against append-only authority.

    Args:
        repo_root: Repository containing current ledger and immutable attempts.
        source: Repository-derived plan source including source identity and
            every content-addressed request-binding proof field.

    Returns:
        Exact request attempt ID proven by current repository bytes.

    Raises:
        BatchWorkflowError: When fields are absent, the exact attempt changed,
            or its portable body/header locators are no longer valid. A legal
            append-only ledger tail does not invalidate this pinned attempt.
    """
    required = {
        "accession",
        "content_sha256",
        "document_name",
        "request_attempt_id",
        "request_headers_repo_relative_path",
        "request_locator_kind",
        "request_repo_relative_path",
        "source_url",
    } | REQUEST_BINDING_PROOF_FIELDS
    if not isinstance(source, Mapping) or not required.issubset(source):
        raise BatchWorkflowError("Planned request binding is incomplete")
    proof = validate_request_attempt_binding(
        repo_root=repo_root,
        source_url=str(source["source_url"]),
        content_sha256=str(source["content_sha256"]),
        accession=str(source["accession"]),
        document_name=str(source["document_name"]),
        request_attempt_id=str(source["request_attempt_id"]),
        require_immutable=False,
    )
    if any(source[field] != proof[field] for field in proof):
        raise BatchWorkflowError(
            "Planned request locators differ from the exact attempt"
        )
    return str(proof["request_attempt_id"])

