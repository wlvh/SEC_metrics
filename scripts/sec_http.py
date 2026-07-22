"""HTTP client for audited SEC requests.

Purpose:
    Provide one configured path for SEC network access: User-Agent,
    per-client process-local request pacing, no implicit redirects, retry
    policy, raw response persistence, and request logs. Pacing remains per
    client; request-ledger publication is serialized across cooperating
    threads and POSIX processes.

Call relationships:
    Stage scripts call sec_pipeline.py.
    sec_pipeline.py creates SecHttpClient and calls fetch for every SEC URL.
"""

from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import os
import re
import stat
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


REQUEST_LOG_FIELDNAMES = [
    "timestamp_utc",
    "method",
    "source_url",
    "status_code",
    "purpose",
    "repo_relative_path",
    "headers_repo_relative_path",
    "content_length",
    "content_sha256",
    "accession",
    "document_name",
    "user_agent",
    "retry_attempt",
    "error",
]
LEGACY_REQUEST_LOG_FIELDNAMES = [
    "timestamp_utc",
    "method",
    "url",
    "status_code",
    "purpose",
    "local_path",
    "headers_path",
    "content_length",
    "sha256",
    "user_agent",
    "retry_attempt",
    "error",
]
REQUEST_LOG_MANIFEST_NAME = "requests_log_manifest.json"
REQUEST_LOG_MANIFEST_SCHEMA_VERSION = 1
_REQUEST_LOG_THREAD_LOCK = threading.RLock()
_IMMUTABLE_ARTIFACT_THREAD_LOCK = threading.RLock()
OFFICIAL_SEC_HOSTS = frozenset({"www.sec.gov", "data.sec.gov"})
REDIRECT_DISABLED_ERROR_PREFIX = "RedirectDisabled: "
REPOSITORY_PATH_ANCHORS = ("evidence", "outputs", "tests", "config")


class NoRedirectHandler(HTTPRedirectHandler):
    """Prevent urllib from issuing an implicit second network request."""

    def redirect_request(
        self,
        request,
        response,
        code,
        message,
        headers,
        new_url,
    ) -> None:
        """Return no follow-up request for every HTTP redirect response."""
        return None


_NO_REDIRECT_OPENER = build_opener(NoRedirectHandler())


def urlopen(*, request: Request, timeout: float) -> object:
    """Open exactly one HTTP request without following redirect responses."""
    return _NO_REDIRECT_OPENER.open(fullurl=request, timeout=timeout)


@dataclass(frozen=True)
class FetchResult:
    """Represent a single SEC HTTP attempt result.

    Args:
        url: Requested SEC URL.
        status_code: HTTP status code returned by SEC or 0 for transport
            failures.
        local_path: Immutable audit path for raw bytes when available. The
            caller-provided working path is also refreshed for downstream use.
        sha256: SHA-256 digest of the response body, or empty string when no
            body was available.
        content_length: Response body size in bytes.
        headers_path: Path to the saved response headers JSON, or empty string.
        error: Transport or HTTP error text. Empty string means no error.

    Expected output:
        A small immutable data record that downstream code can cite in evidence.
    """

    url: str
    status_code: int
    local_path: str
    sha256: str
    content_length: int
    headers_path: str
    error: str


def load_config(*, config_path: Path) -> dict:
    """Load centralized SEC HTTP configuration.

    Args:
        config_path: UTF-8 JSON path with organization, contact_email,
            rate_limit_per_sec, max_retries, and backoff_initial_seconds.

    Returns:
        Parsed configuration dictionary.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"SEC config not found: {config_path}")
    with config_path.open(mode="r", encoding="utf-8") as file_obj:
        config = json.load(file_obj)
    required_keys = [
        "organization",
        "contact_email",
        "rate_limit_per_sec",
        "max_retries",
        "backoff_initial_seconds",
    ]
    for key in required_keys:
        if key not in config:
            raise KeyError(f"SEC config missing required key: {key}")
    return config


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(tz=timezone.utc).isoformat()


def validate_official_sec_url(*, url: str) -> None:
    """Fail unless a URL uses one exact official SEC HTTPS origin.

    Args:
        url: Absolute URL with no userinfo or explicit port.

    Expected output:
        Only ``https://www.sec.gov`` and ``https://data.sec.gov`` pass.
    """
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"Invalid SEC URL authority: {url}") from error
    hostname = parsed.hostname
    authority_is_host_only = (
        hostname is not None
        and parsed.netloc.casefold() == hostname.casefold()
    )
    if (
        parsed.scheme.casefold() != "https"
        or hostname not in OFFICIAL_SEC_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not authority_is_host_only
    ):
        raise ValueError(f"Only official SEC HTTPS URLs are allowed: {url}")


def ensure_parent(*, path: Path) -> None:
    """Create a file parent directory when it is missing.

    Args:
        path: File path whose parent should exist.

    Returns:
        None. The side effect is limited to directory creation.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def legacy_repository_path_candidates(*, path: Path) -> list[Path]:
    """Return every repository-shaped suffix in one legacy absolute path.

    Args:
        path: Legacy locator whose former clone root is not authoritative.

    Returns:
        Deduplicated candidate suffixes in lexical order.
    """
    if ".." in path.parts:
        raise ValueError(f"Legacy artifact path contains traversal: {path}")
    candidates = []
    seen = set()
    # Every anchor occurrence is a candidate; choosing first or last silently
    # assumes facts that only the current clone's evidence can establish.
    for index, part in enumerate(path.parts):
        if part not in REPOSITORY_PATH_ANCHORS:
            continue
        candidate = Path(*path.parts[index:])
        candidate_text = candidate.as_posix()
        if candidate_text in seen:
            continue
        seen.add(candidate_text)
        candidates.append(candidate)
    return candidates


def selected_legacy_repository_prefix(
    *,
    path_text: str,
    relative_path: str,
) -> tuple[str, ...]:
    """Return the lexical clone prefix discarded from one legacy locator.

    Args:
        path_text: Original absolute or repository-relative locator.
        relative_path: Selected repository-relative suffix.

    Returns:
        Original path components before the selected suffix, or an empty tuple
        when the locator does not encode a comparable absolute clone root.
    """
    path = Path(path_text)
    if not path.is_absolute() or not relative_path:
        return ()
    for candidate in legacy_repository_path_candidates(path=path):
        if candidate.as_posix() == relative_path:
            return path.parts[:-len(candidate.parts)]
    return ()


def request_log_source_url(*, row: dict) -> str:
    """Return the required current or legacy request URL field."""
    if "source_url" in row and row["source_url"]:
        return str(row["source_url"])
    if "url" in row and row["url"]:
        return str(row["url"])
    raise KeyError("Request log row requires source_url or legacy url")


def request_candidate_matches_identity(
    *,
    path: Path,
    content_sha256: str,
    source_url: str,
    status_code: str,
    content_length: str,
    document_name: str,
    is_headers: bool,
) -> bool:
    """Return whether one ambiguous request candidate matches its observation.

    Args:
        path: Existing current-clone body or headers candidate.
        content_sha256: Immutable response-body identity.
        source_url: Requested official SEC URL.
        status_code: Recorded HTTP status text.
        content_length: Recorded response byte length text.
        document_name: Expected response document name.
        is_headers: Whether the candidate is a headers JSON sidecar.

    Returns:
        True only when bytes or sidecar metadata disambiguate the candidate.
    """
    if not path.is_file():
        return False
    if not is_headers:
        if document_name and path.name != document_name:
            return False
        return bool(content_sha256) and (
            hashlib.sha256(path.read_bytes()).hexdigest() == content_sha256
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    required_fields = {
        "url",
        "status_code",
        "content_length",
        "sha256",
    }
    if not isinstance(payload, dict) or not required_fields.issubset(payload):
        return False
    return (
        str(payload["url"]) == source_url
        and str(payload["status_code"]) == status_code
        and str(payload["content_length"]) == content_length
        and str(payload["sha256"]) == content_sha256
    )


def repo_relative_request_path(
    *,
    workdir: Path,
    path_text: str,
    content_sha256: str,
    source_url: str,
    status_code: str,
    content_length: str,
    document_name: str,
    is_headers: bool,
) -> str:
    """Return a portable request-artifact path under the current repository.

    Args:
        workdir: Current repository root.
        path_text: Current, relative, or legacy-clone artifact path.
        content_sha256: Recorded response-body identity used for ambiguity.
        source_url: Recorded SEC URL used for headers-sidecar identity.
        status_code: Recorded HTTP status used for headers-sidecar identity.
        content_length: Recorded byte length used for headers-sidecar identity.
        document_name: Recorded response document name.
        is_headers: Whether path_text identifies a headers JSON sidecar.

    Returns:
        Repository-relative POSIX path, or an empty string when no artifact was
        written. An unrelated external path fails because it cannot be trusted.
    """
    if not path_text:
        return ""
    path = Path(path_text)
    relative_path = path
    if not path.is_absolute():
        request_artifact_candidate(
            workdir=workdir,
            relative_path=path.as_posix(),
        )
        return path.as_posix()
    try:
        relative_path = path.relative_to(workdir)
    except ValueError:
        candidates = legacy_repository_path_candidates(path=path)
        if not candidates:
            raise ValueError(
                f"Request artifact is outside repository: {path_text}"
            )
        candidate_pairs = [
            (
                candidate,
                request_artifact_candidate(
                    workdir=workdir,
                    relative_path=candidate.as_posix(),
                ),
            )
            for candidate in candidates
        ]
        if len(candidate_pairs) == 1:
            # A single anchor preserves the historical migration behavior;
            # downstream evidence validation still judges missing/stale bytes.
            relative_path = candidate_pairs[0][0]
        else:
            existing = [pair for pair in candidate_pairs if pair[1].is_file()]
            matched = [
                pair
                for pair in existing
                if request_candidate_matches_identity(
                    path=pair[1],
                    content_sha256=content_sha256,
                    source_url=source_url,
                    status_code=status_code,
                    content_length=content_length,
                    document_name=document_name,
                    is_headers=is_headers,
                )
            ]
            if len(matched) == 1:
                relative_path = matched[0][0]
            elif not existing:
                raise FileNotFoundError(
                    "Request artifact has no current-clone candidate: "
                    f"{path_text}"
                )
            else:
                raise ValueError(
                    "Request artifact relocation is ambiguous: "
                    f"{path_text}"
                )
    request_artifact_candidate(
        workdir=workdir,
        relative_path=relative_path.as_posix(),
    )
    return relative_path.as_posix()


def request_artifact_candidate(*, workdir: Path, relative_path: str) -> Path:
    """Return one request artifact path contained by the repository.

    Args:
        workdir: Current repository root.
        relative_path: Repository-relative request artifact locator.

    Returns:
        Candidate path using the declared repository spelling.
    """
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(
            f"Request artifact escapes repository: {relative_path}"
        )
    candidate = workdir / path
    if not candidate.resolve(strict=False).is_relative_to(workdir.resolve()):
        raise ValueError(
            f"Request artifact escapes repository: {relative_path}"
        )
    return candidate


def repository_write_path(*, workdir: Path, path: Path) -> Path:
    """Return a contained write path with no repository-internal symlink.

    Args:
        workdir: Current repository root.
        path: Final file or directory path that a caller intends to write.

    Returns:
        The original path after containment and symlink checks have passed.
    """
    workdir_path = workdir.absolute()
    candidate = path.absolute()
    if not candidate.resolve(strict=False).is_relative_to(workdir.resolve()):
        raise ValueError(f"Request artifact escapes repository: {path}")
    try:
        relative_path = candidate.relative_to(workdir_path)
    except ValueError as error:
        raise ValueError(
            f"Request artifact is not lexically under repository: {path}"
        ) from error
    current_path = workdir_path
    for part in relative_path.parts:
        current_path /= part
        if current_path.is_symlink():
            raise ValueError(
                f"Request artifact path contains symlink: {current_path}"
            )
    return candidate


def repository_file_write_path(*, workdir: Path, path: Path) -> Path:
    """Return one contained path whose existing target can be a file.

    Args:
        workdir: Current repository root.
        path: Final file path that a caller intends to write.

    Returns:
        The original path after containment and filesystem shape checks.
    """
    candidate = repository_write_path(workdir=workdir, path=path)
    if candidate.exists() and not candidate.is_file():
        raise IsADirectoryError(f"Request artifact is not a file: {candidate}")
    if candidate.parent.exists() and not candidate.parent.is_dir():
        raise NotADirectoryError(
            f"Request artifact parent is not a directory: {candidate.parent}"
        )
    return candidate


def response_working_paths(
    *,
    workdir: Path,
    local_path: Path,
) -> tuple[Path, Path]:
    """Return repository-contained working response and header paths.

    Args:
        workdir: Current repository root.
        local_path: Caller-visible working response path.

    Returns:
        The body path and its JSON headers sidecar path.
    """
    headers_path = local_path.with_suffix(local_path.suffix + ".headers.json")
    # Writes must follow the real filesystem target so a repository-owned
    # spelling cannot escape through an existing symlink.
    paths = (
        repository_file_write_path(workdir=workdir, path=local_path),
        repository_file_write_path(workdir=workdir, path=headers_path),
    )
    resolved_workdir = workdir.resolve()
    reserved_root = (
        workdir / "evidence" / "request_attempts"
    ).resolve(strict=False)
    reserved_parts = ("evidence", "request_attempts")
    for path in paths:
        resolved_path = path.resolve(strict=False)
        relative_parts = resolved_path.relative_to(resolved_workdir).parts
        uses_reserved_spelling = tuple(
            part.casefold() for part in relative_parts[:2]
        ) == reserved_parts
        if (
            resolved_path.is_relative_to(reserved_root)
            or uses_reserved_spelling
        ):
            raise ValueError(
                "Working response path uses immutable snapshot storage: "
                f"{path}"
            )
    return paths


def artifact_paths_alias(*, first: Path, second: Path) -> bool:
    """Return whether two artifact spellings resolve to one path or inode."""
    return first.resolve(strict=False) == second.resolve(strict=False) or (
        first.exists() and second.exists() and first.samefile(second)
    )


def validate_request_artifact_targets(
    *,
    paths: tuple[Path, ...],
    log_path: Path,
) -> None:
    """Reject response targets that alias request-audit state.

    Args:
        paths: Body or header paths that one request may overwrite.
        log_path: Request CSV whose bytes and integrity manifest are protected.

    Expected output:
        Every target is pairwise distinct and does not alias the log or
        manifest.
        Transaction files use unguessable exclusive names.
    """
    manifest_path = request_log_manifest_path(log_path=log_path)
    protected_paths = (
        log_path,
        manifest_path,
    )
    for index, path in enumerate(paths):
        for other_path in paths[index + 1:]:
            if artifact_paths_alias(first=path, second=other_path):
                raise ValueError(
                    "Request artifact targets alias each other: "
                    f"first={path}; second={other_path}"
                )
        for protected_path in protected_paths:
            if artifact_paths_alias(first=path, second=protected_path):
                raise ValueError(
                    "Request artifact aliases request-log state: "
                    f"target={path}; protected={protected_path}"
                )


def response_snapshot_path(
    *,
    workdir: Path,
    local_path: Path,
    content_sha256: str,
) -> Path:
    """Return a content-addressed immutable response path.

    Args:
        workdir: Current repository root.
        local_path: Caller-visible working response path.
        content_sha256: Response body SHA-256 digest.

    Returns:
        Audit path under evidence/request_attempts keyed by body content.
    """
    repo_relative_request_path(
        workdir=workdir,
        path_text=str(local_path),
        content_sha256=content_sha256,
        source_url="",
        status_code="",
        content_length="",
        document_name=local_path.name,
        is_headers=False,
    )
    relative_path = Path(
        "evidence",
        "request_attempts",
        content_sha256[:2],
        content_sha256,
        local_path.name,
    )
    return request_artifact_candidate(
        workdir=workdir,
        relative_path=relative_path.as_posix(),
    )


def request_log_manifest_path(*, log_path: Path) -> Path:
    """Return the fixed integrity-manifest sibling for a request log.

    Args:
        log_path: Request CSV path whose complete bytes are attested.

    Returns:
        The sibling ``requests_log_manifest.json`` path.
    """
    return log_path.with_name(REQUEST_LOG_MANIFEST_NAME)


def parse_request_log_rows(*, text: str) -> list[dict[str, str]]:
    """Parse current request-log rows with an exact CSV shape.

    Args:
        text: UTF-8-decoded CSV text using the current request-log schema.

    Returns:
        Ordered rows containing every declared field and no overflow cells.
    """
    with io.StringIO(text, newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        if reader.fieldnames != REQUEST_LOG_FIELDNAMES:
            raise ValueError(
                f"Unexpected request log schema: {reader.fieldnames}"
            )
        rows = list(reader)
    expected_fields = set(REQUEST_LOG_FIELDNAMES)
    # Validate shape before projection so overflow and absent cells cannot
    # disappear behind DictReader's None key or value representation.
    for row_number, row in enumerate(rows, start=2):
        if set(row) != expected_fields or any(
            row[field] is None for field in REQUEST_LOG_FIELDNAMES
        ):
            raise ValueError(
                f"Unexpected request log row shape at line {row_number}"
            )
    return rows


def request_log_manifest_payload(*, log_path: Path) -> dict:
    """Build the exact-set integrity payload for one request log.

    Args:
        log_path: Current-schema UTF-8 request CSV path.

    Returns:
        Schema version, parsed data-row count, and SHA-256 of the exact bytes.
    """
    log_bytes = log_path.read_bytes()
    rows = parse_request_log_rows(text=log_bytes.decode("utf-8"))
    return {
        "schema_version": REQUEST_LOG_MANIFEST_SCHEMA_VERSION,
        "row_count": len(rows),
        "content_sha256": hashlib.sha256(log_bytes).hexdigest(),
    }


def unique_request_manifest_object(pairs: list[tuple[str, object]]) -> dict:
    """Build one JSON object while rejecting duplicate manifest keys."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate request manifest key: {key}")
        result[key] = value
    return result


def validate_request_log_manifest(*, log_path: Path) -> None:
    """Fail unless the committed manifest attests the complete request log.

    Args:
        log_path: Current-schema request CSV path to validate.

    Expected output:
        The manifest has the exact schema, row count, and content hash produced
        from the current CSV bytes; missing or stale evidence raises.
    """
    manifest_path = request_log_manifest_path(log_path=log_path)
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Request log manifest not found: {manifest_path}"
        )
    with manifest_path.open(mode="r", encoding="utf-8") as file_obj:
        actual = json.load(
            file_obj,
            object_pairs_hook=unique_request_manifest_object,
        )
    expected = request_log_manifest_payload(log_path=log_path)
    if type(actual) is not dict or set(actual) != set(expected):
        raise ValueError(
            f"Unexpected request log manifest schema: {actual}"
        )
    if (
        type(actual["schema_version"]) is not int
        or type(actual["row_count"]) is not int
        or type(actual["content_sha256"]) is not str
        or actual["row_count"] < 0
        or re.fullmatch(
            pattern=r"[0-9a-f]{64}",
            string=actual["content_sha256"],
        )
        is None
    ):
        raise ValueError(
            f"Unexpected request log manifest values: {actual}"
        )
    if actual != expected:
        raise ValueError(
            "Request log manifest mismatch; "
            f"expected={expected}; actual={actual}"
        )


def request_log_state_paths(
    *,
    workdir: Path,
    log_path: Path,
) -> tuple[Path, Path]:
    """Return validated final request-log and manifest paths.

    Args:
        workdir: Current repository root.
        log_path: Request CSV path attested by the manifest.

    Returns:
        Repository-contained regular-file targets for the CSV and manifest.
    """
    manifest_path = request_log_manifest_path(log_path=log_path)
    return (
        repository_file_write_path(workdir=workdir, path=log_path),
        repository_file_write_path(workdir=workdir, path=manifest_path),
    )


@contextmanager
def request_log_write_lock(
    *,
    workdir: Path,
    log_path: Path,
) -> Iterator[None]:
    """Serialize one request ledger across threads and local processes.

    Args:
        workdir: Current repository root used for containment validation.
        log_path: Mutable request CSV whose parent directory is never replaced.

    Yields:
        Control while both the module lock and stable-directory flock are held.
    """
    with _REQUEST_LOG_THREAD_LOCK:
        candidate = repository_file_write_path(
            workdir=workdir,
            path=log_path,
        )
        ensure_parent(path=candidate)
        lock_path = repository_write_path(
            workdir=workdir,
            path=candidate.parent,
        )
        if not lock_path.is_dir():
            raise NotADirectoryError(
                f"Request-log parent is not a directory: {lock_path}"
            )
        descriptor = os.open(path=lock_path, flags=os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def write_repository_bytes_atomically(
    *,
    workdir: Path,
    path: Path,
    content: bytes,
) -> None:
    """Replace one mutable repository artifact through a new exclusive inode.

    Args:
        workdir: Current repository root used for containment validation.
        path: Final mutable artifact path.
        content: Complete bytes for the next state.

    Expected output:
        A UUID sibling is exclusively created and atomically replaces the
        lexical target, so pre-existing hardlinks are never mutated.
    """
    target_path = repository_file_write_path(workdir=workdir, path=path)
    ensure_parent(path=target_path)
    temporary_path = repository_file_write_path(
        workdir=workdir,
        path=target_path.with_name(
            f".{target_path.name}.{uuid.uuid4().hex}.tmp"
        ),
    )
    created = False
    try:
        with temporary_path.open(mode="xb") as file_obj:
            created = True
            file_obj.write(content)
        temporary_path.replace(target_path)
    finally:
        # Only remove the inode created by this call; a preoccupied UUID path
        # must survive the exclusive-open failure unchanged for diagnosis.
        if created and temporary_path.exists():
            temporary_path.unlink()
    if target_path.is_symlink() or not target_path.is_file():
        raise RuntimeError(
            f"Repository artifact is not a regular file: {target_path}"
        )
    if target_path.read_bytes() != content:
        raise RuntimeError(
            f"Repository artifact postcondition failed: {target_path}"
        )


def request_log_csv_bytes(*, rows: list[dict]) -> bytes:
    """Serialize the complete current request log as UTF-8 bytes.

    Args:
        rows: Complete ordered observation rows in current-schema form.

    Returns:
        Header plus all observations with stable LF line endings.
    """
    with io.StringIO(newline="") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=REQUEST_LOG_FIELDNAMES,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
        return file_obj.getvalue().encode("utf-8")


def refresh_request_log_manifest(*, workdir: Path, log_path: Path) -> None:
    """Atomically attest the complete current request log.

    Args:
        workdir: Current repository root used for containment validation.
        log_path: Request CSV path to hash and count.

    Expected output:
        The fixed sibling manifest matches one complete read of the CSV. A
        crash before replacement leaves the prior manifest to fail closed.
    """
    _, manifest_path = request_log_state_paths(
        workdir=workdir,
        log_path=log_path,
    )
    payload = request_log_manifest_payload(log_path=log_path)
    manifest_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    write_repository_bytes_atomically(
        workdir=workdir,
        path=manifest_path,
        content=manifest_bytes,
    )


def read_verified_immutable_bytes(
    *,
    path: Path,
) -> tuple[bytes, os.stat_result]:
    """Read one non-linked regular immutable artifact without following aliases.

    Args:
        path: Final content-addressed artifact path.

    Returns:
        Exact bytes and descriptor metadata for a single-link regular file.
    """
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeError(
            f"Immutable request artifact is not safely readable: {path}"
        ) from error
    with os.fdopen(descriptor, mode="rb") as file_obj:
        metadata = os.fstat(file_obj.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RuntimeError(
                f"Immutable request artifact must be a single-link regular "
                f"file: {path}"
            )
        return file_obj.read(), metadata


@contextmanager
def immutable_artifact_write_lock(*, path: Path) -> Iterator[None]:
    """Serialize cooperating publishers within one snapshot directory.

    Args:
        path: Final immutable artifact path whose parent is lockable.

    Yields:
        Control while local threads and POSIX processes exclude another
        publication in the same directory.
    """
    with _IMMUTABLE_ARTIFACT_THREAD_LOCK:
        descriptor = os.open(path.parent, flags=os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def write_immutable_bytes(*, path: Path, content: bytes) -> None:
    """Create immutable audit bytes or verify an existing identical copy.

    Args:
        path: Content-addressed response or headers path.
        content: Exact bytes that the path must retain.

    Expected output:
        The path contains the requested bytes and is never overwritten with
        different content.
    """
    ensure_parent(path=path)
    with immutable_artifact_write_lock(path=path):
        if os.path.lexists(path):
            existing, _metadata = read_verified_immutable_bytes(path=path)
            if existing != content:
                raise RuntimeError(
                    f"Immutable request artifact changed: {path}"
                )
            return

        # A full sibling inode plus a no-overwrite hardlink prevents partial
        # visibility and closes the final-name exists/write race.
        temporary_path = path.with_name(
            f".{path.name}.{uuid.uuid4().hex}.tmp"
        )
        temporary_identity = None
        created = False
        try:
            with temporary_path.open(mode="xb") as file_obj:
                created = True
                file_obj.write(content)
                metadata = os.fstat(file_obj.fileno())
                temporary_identity = (metadata.st_dev, metadata.st_ino)
            try:
                os.link(
                    src=temporary_path,
                    dst=path,
                    follow_symlinks=False,
                )
            except FileExistsError:
                # A non-cooperating alias may still occupy the final name;
                # verification below distinguishes it from valid content.
                temporary_identity = None
        finally:
            if created and temporary_path.exists():
                temporary_path.unlink()

        existing, metadata = read_verified_immutable_bytes(path=path)
        final_identity = (metadata.st_dev, metadata.st_ino)
        if (
            temporary_identity is not None
            and final_identity != temporary_identity
        ):
            raise RuntimeError(
                f"Immutable request artifact was replaced: {path}"
            )
        if existing != content:
            raise RuntimeError(
                f"Immutable request artifact changed: {path}"
            )


def request_accession(*, source_url: str) -> str:
    """Derive a filing accession from an SEC Archives document URL."""
    match = re.search(
        pattern=r"/Archives/edgar/data/\d+/(\d{18})(?:/|$)",
        string=urlparse(source_url).path,
    )
    if match is None:
        return ""
    compact = match.group(1)
    return f"{compact[:10]}-{compact[10:12]}-{compact[12:]}"


def portable_request_log_row(*, row: dict, workdir: Path) -> dict:
    """Normalize one current or legacy request observation.

    Args:
        row: Request row using the current schema or legacy url/local_path,
            headers_path, and sha256 fields.
        workdir: Current repository root used to remove clone-specific paths.

    Returns:
        One row in REQUEST_LOG_FIELDNAMES order with portable artifact paths.
    """
    source_url = request_log_source_url(row=row)
    path_text = (
        str(row["repo_relative_path"])
        if "repo_relative_path" in row and row["repo_relative_path"]
        else str(row["local_path"])
        if "local_path" in row and row["local_path"]
        else ""
    )
    headers_path_text = (
        str(row["headers_repo_relative_path"])
        if (
            "headers_repo_relative_path" in row
            and row["headers_repo_relative_path"]
        )
        else str(row["headers_path"])
        if "headers_path" in row and row["headers_path"]
        else ""
    )
    document_name = (
        str(row["document_name"])
        if "document_name" in row and row["document_name"]
        else Path(path_text).name
        if path_text
        else Path(urlparse(source_url).path).name
    )
    accession = (
        str(row["accession"])
        if "accession" in row and row["accession"]
        else request_accession(source_url=source_url)
    )
    content_sha256 = (
        str(row["content_sha256"])
        if "content_sha256" in row and row["content_sha256"]
        else str(row["sha256"])
        if "sha256" in row and row["sha256"]
        else ""
    )
    if not content_sha256:
        # A transport failure has no response bytes to locate. Retaining a
        # A working-path hint could let later bytes masquerade as this attempt.
        relative_path = ""
        headers_path_text = ""
        headers_relative_path = ""
    else:
        relative_path = repo_relative_request_path(
            workdir=workdir,
            path_text=path_text,
            content_sha256=content_sha256,
            source_url=source_url,
            status_code=str(row["status_code"]),
            content_length=str(row["content_length"]),
            document_name=document_name,
            is_headers=False,
        )
        headers_relative_path = repo_relative_request_path(
            workdir=workdir,
            path_text=headers_path_text,
            content_sha256=content_sha256,
            source_url=source_url,
            status_code=str(row["status_code"]),
            content_length=str(row["content_length"]),
            document_name=document_name,
            is_headers=True,
        )
        body_root = selected_legacy_repository_prefix(
            path_text=path_text,
            relative_path=relative_path,
        )
        headers_root = selected_legacy_repository_prefix(
            path_text=headers_path_text,
            relative_path=headers_relative_path,
        )
        # Sidecar metadata is not independently content-addressed in legacy
        # rows, so both files must relocate from one former clone boundary.
        if body_root and headers_root and body_root != headers_root:
            raise ValueError(
                "Request body and headers use different legacy repository "
                "roots"
            )
    normalized = {
        "timestamp_utc": row["timestamp_utc"],
        "method": row["method"],
        "source_url": source_url,
        "status_code": row["status_code"],
        "purpose": row["purpose"],
        "repo_relative_path": relative_path,
        "headers_repo_relative_path": headers_relative_path,
        "content_length": row["content_length"],
        "content_sha256": content_sha256,
        "accession": accession,
        "document_name": document_name,
        "user_agent": row["user_agent"],
        "retry_attempt": row["retry_attempt"],
        "error": row["error"],
    }
    return {field: normalized[field] for field in REQUEST_LOG_FIELDNAMES}


def migrate_request_log(
    *,
    log_path: Path,
    workdir: Path,
    allow_legacy_bootstrap: bool,
) -> None:
    """Serialize and rewrite a legacy request log with portable fields.

    Args:
        log_path: Existing request log, or a future log path not yet created.
        workdir: Current repository root.
        allow_legacy_bootstrap: Explicit authorization to attest one exact
            pre-manifest legacy schema. Normal client and stage paths pass
            false.

    Expected output:
        Existing request observations retain their non-locator values while
        absolute body/header paths and legacy field names are removed.
    """
    with request_log_write_lock(workdir=workdir, log_path=log_path):
        _migrate_request_log_unlocked(
            log_path=log_path,
            workdir=workdir,
            allow_legacy_bootstrap=allow_legacy_bootstrap,
        )


def _migrate_request_log_unlocked(
    *,
    log_path: Path,
    workdir: Path,
    allow_legacy_bootstrap: bool,
) -> None:
    """Rewrite one request log while its stable parent lock is held.

    Args:
        log_path: Existing request CSV or a future path not yet created.
        workdir: Current repository root.
        allow_legacy_bootstrap: Explicit legacy attestation authorization.
    """
    log_path, manifest_path = request_log_state_paths(
        workdir=workdir,
        log_path=log_path,
    )
    if not log_path.exists() and manifest_path.exists():
        raise FileNotFoundError(
            "Request log is missing while its integrity manifest exists: "
            f"{log_path}"
        )
    if not log_path.exists():
        return
    with log_path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        rows = list(reader)
        fieldnames = reader.fieldnames if reader.fieldnames is not None else []
    if manifest_path.exists():
        # Existing current evidence must authenticate before normalization;
        # otherwise migration could bless deleted rows with a fresh manifest.
        validate_request_log_manifest(log_path=log_path)
    elif fieldnames == REQUEST_LOG_FIELDNAMES:
        raise FileNotFoundError(
            "Current request log requires its integrity manifest: "
            f"{manifest_path}"
        )
    elif fieldnames != LEGACY_REQUEST_LOG_FIELDNAMES:
        raise ValueError(
            f"Unrecognized legacy request log schema: {fieldnames}"
        )
    elif not allow_legacy_bootstrap:
        raise PermissionError(
            "Legacy request log bootstrap requires explicit authorization"
        )
    normalized = [
        portable_request_log_row(row=row, workdir=workdir)
        for row in rows
    ]
    if fieldnames == REQUEST_LOG_FIELDNAMES and rows == normalized:
        return
    write_repository_bytes_atomically(
        workdir=workdir,
        path=log_path,
        content=request_log_csv_bytes(rows=normalized),
    )
    refresh_request_log_manifest(workdir=workdir, log_path=log_path)


class SecHttpClient:
    """Fetch SEC URLs with audit logging, rate limiting, and retry behavior.

    Args:
        workdir: Project root used to resolve config and evidence paths.
        config_path: Central SEC HTTP config path.
        log_path: CSV request log path.

    Expected output:
        fetch returns FetchResult and writes raw evidence files plus one log row
        per network attempt.
    """

    def __init__(self, *, workdir: Path, config_path: Path, log_path: Path) -> None:
        """Initialize the client from centralized config."""
        self.workdir = workdir
        self.config = load_config(config_path=config_path)
        self.log_path = log_path
        self.last_request_at = 0.0
        self.user_agent = (
            f"{self.config['organization']} {self.config['contact_email']}"
        )
        self.log_path, _ = request_log_state_paths(
            workdir=self.workdir,
            log_path=self.log_path,
        )
        ensure_parent(path=self.log_path)
        manifest_path = request_log_manifest_path(log_path=self.log_path)
        if manifest_path.exists() and not self.log_path.exists():
            raise FileNotFoundError(
                "Request log is missing while its integrity manifest exists: "
                f"{self.log_path}"
            )
        if self.log_path.exists():
            migrate_request_log(
                log_path=self.log_path,
                workdir=self.workdir,
                allow_legacy_bootstrap=False,
            )
        else:
            self._write_log_header()

    def fetch(self, *, url: str, purpose: str, local_path: Path) -> FetchResult:
        """Fetch a SEC URL, persist raw bytes, and return evidence metadata.

        Args:
            url: Official SEC endpoint URL.
            purpose: Short machine-readable reason for the request.
            local_path: Path where the response body should be saved.

        Returns:
            FetchResult containing status, paths, content length, and digest.
        """
        validate_official_sec_url(url=url)
        if not purpose:
            raise ValueError("purpose is required for request logging")

        max_retries = int(self.config["max_retries"])
        delay = float(self.config["backoff_initial_seconds"])
        retry_statuses = {403, 429, 500, 502, 503, 504}
        attempt = 0
        latest_result = FetchResult(
            url=url,
            status_code=0,
            local_path=str(local_path),
            sha256="",
            content_length=0,
            headers_path="",
            error="not_attempted",
        )

        while attempt <= max_retries:
            result = self._fetch_once(
                url=url,
                purpose=purpose,
                local_path=local_path,
                attempt=attempt,
            )
            latest_result = result
            if result.status_code not in retry_statuses:
                return result
            if attempt == max_retries:
                print(
                    f"SEC retry exhausted for {url}; "
                    f"status={result.status_code}; error={result.error}"
                )
                return result
            print(
                f"SEC retryable status {result.status_code} for {url}; "
                f"sleep_seconds={delay}"
            )
            time.sleep(delay)
            delay *= 2
            attempt += 1
        return latest_result

    def _fetch_once(
        self,
        *,
        url: str,
        purpose: str,
        local_path: Path,
        attempt: int,
    ) -> FetchResult:
        """Execute one HTTP attempt and log it.

        Args:
            url: Official SEC endpoint URL.
            purpose: Request purpose propagated to requests_log.csv.
            local_path: Body persistence path.
            attempt: Zero-based retry attempt number.

        Returns:
            FetchResult for this attempt.
        """
        # Reject unsafe targets or a broken audit chain before a request can
        # create an observation that cannot be persisted safely.
        working_paths = response_working_paths(
            workdir=self.workdir,
            local_path=local_path,
        )
        validate_request_artifact_targets(
            paths=working_paths,
            log_path=self.log_path,
        )
        for working_path in working_paths:
            ensure_parent(path=working_path)
        snapshot_root = repository_write_path(
            workdir=self.workdir,
            path=request_artifact_candidate(
                workdir=self.workdir,
                relative_path="evidence/request_attempts",
            ),
        )
        if snapshot_root.exists() and not snapshot_root.is_dir():
            raise NotADirectoryError(
                f"Request snapshot root is not a directory: {snapshot_root}"
            )
        snapshot_root.mkdir(parents=True, exist_ok=True)
        # Hold the ledger lock only for the short predecessor read; network I/O
        # must not block another client's completed-attempt publication.
        with request_log_write_lock(
            workdir=self.workdir,
            log_path=self.log_path,
        ):
            validate_request_log_manifest(log_path=self.log_path)
        self._pace_request()
        request = Request(
            url=url,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "identity",
                "Accept": "application/json,text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            method="GET",
        )
        try:
            try:
                with urlopen(request=request, timeout=60) as response:
                    body = response.read()
                    status_code = int(response.status)
                    headers = dict(response.headers.items())
                    response_error = ""
            except HTTPError as error:
                with error:
                    body = error.read()
                    status_code = int(error.code)
                    headers = dict(error.headers.items())
                response_error = (
                    f"{REDIRECT_DISABLED_ERROR_PREFIX}{error}"
                    if 300 <= status_code < 400
                    else str(error)
                )
        except (HTTPException, OSError) as error:
            # A request already reached the transport boundary, so read and
            # socket failures must remain visible even when no body exists.
            # HTTPException covers IncompleteRead, BadStatusLine, and
            # RemoteDisconnected; OSError covers socket and URL I/O failures.
            result = FetchResult(
                url=url,
                status_code=0,
                local_path="",
                sha256="",
                content_length=0,
                headers_path="",
                error=f"{type(error).__name__}: {error}",
            )
        else:
            # Persistence stays outside the transport exception boundary so a
            # local filesystem failure remains a fail-fast error.
            try:
                result = self._persist_result(
                    url=url,
                    status_code=status_code,
                    body=body,
                    headers=headers,
                    local_path=local_path,
                    error=response_error,
                )
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                # The transport already returned, so retain the response
                # identity even when no complete artifact pair can be cited.
                result = FetchResult(
                    url=url,
                    status_code=0,
                    local_path="",
                    sha256="",
                    content_length=0,
                    headers_path="",
                    error=(
                        f"PersistenceError: {type(error).__name__}: {error}; "
                        f"response_status={status_code}; "
                        f"response_content_length={len(body)}; "
                        "response_sha256="
                        f"{hashlib.sha256(body).hexdigest()}"
                    ),
                )
                self._append_log_row(
                    result=result,
                    purpose=purpose,
                    attempt=attempt,
                )
                raise
        self._append_log_row(
            result=result,
            purpose=purpose,
            attempt=attempt,
        )
        return result

    def _pace_request(self) -> None:
        """Sleep when needed so this client stays within its configured rate."""
        rate_limit = float(self.config["rate_limit_per_sec"])
        if rate_limit <= 0:
            raise ValueError("rate_limit_per_sec must be positive")
        min_interval = 1.0 / rate_limit
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_at = time.monotonic()

    def _persist_result(
        self,
        *,
        url: str,
        status_code: int,
        body: bytes,
        headers: dict,
        local_path: Path,
        error: str,
    ) -> FetchResult:
        """Write response body and headers to evidence files.

        Args:
            url: Official SEC endpoint URL.
            status_code: HTTP status returned by SEC.
            body: Raw response bytes.
            headers: Response headers.
            local_path: Body persistence path.
            error: Empty string for success, otherwise error text.

        Returns:
            FetchResult with digest and persisted paths.
        """
        sha256 = hashlib.sha256(body).hexdigest()
        local_path, headers_path = response_working_paths(
            workdir=self.workdir,
            local_path=local_path,
        )
        snapshot_path = response_snapshot_path(
            workdir=self.workdir,
            local_path=local_path,
            content_sha256=sha256,
        )
        headers_payload = {
            "url": url,
            "status_code": status_code,
            "headers": headers,
            "content_length": len(body),
            "sha256": sha256,
            "saved_at_utc": utc_now_iso(),
        }
        headers_bytes = json.dumps(
            headers_payload,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        headers_sha256 = hashlib.sha256(headers_bytes).hexdigest()
        snapshot_headers_path = snapshot_path.with_name(
            f"{snapshot_path.name}.{headers_sha256}.headers.json"
        )
        snapshot_path = repository_file_write_path(
            workdir=self.workdir,
            path=snapshot_path,
        )
        snapshot_headers_path = repository_file_write_path(
            workdir=self.workdir,
            path=snapshot_headers_path,
        )
        validate_request_artifact_targets(
            paths=(
                local_path,
                headers_path,
                snapshot_path,
                snapshot_headers_path,
            ),
            log_path=self.log_path,
        )

        # Validate every final target before the first write so a later path
        # failure cannot leave a partial response observation on disk.
        write_immutable_bytes(path=snapshot_path, content=body)
        write_immutable_bytes(
            path=snapshot_headers_path,
            content=headers_bytes,
        )
        # Downstream parsers still consume the stable working path, while the
        # request observation points to immutable attempt evidence.
        ensure_parent(path=local_path)
        write_repository_bytes_atomically(
            workdir=self.workdir,
            path=local_path,
            content=body,
        )
        write_repository_bytes_atomically(
            workdir=self.workdir,
            path=headers_path,
            content=headers_bytes,
        )
        return FetchResult(
            url=url,
            status_code=status_code,
            local_path=str(snapshot_path),
            sha256=sha256,
            content_length=len(body),
            headers_path=str(snapshot_headers_path),
            error=error,
        )

    def _write_log_header(self) -> None:
        """Initialize requests_log.csv with the required audit columns."""
        with request_log_write_lock(
            workdir=self.workdir,
            log_path=self.log_path,
        ):
            self.log_path, manifest_path = request_log_state_paths(
                workdir=self.workdir,
                log_path=self.log_path,
            )
            if self.log_path.exists() and manifest_path.exists():
                validate_request_log_manifest(log_path=self.log_path)
                return
            if self.log_path.exists() or manifest_path.exists():
                raise FileNotFoundError(
                    "Request log and manifest must be created together"
                )
            write_repository_bytes_atomically(
                workdir=self.workdir,
                path=self.log_path,
                content=request_log_csv_bytes(rows=[]),
            )
            refresh_request_log_manifest(
                workdir=self.workdir,
                log_path=self.log_path,
            )

    def _append_log_row(
        self,
        *,
        result: FetchResult,
        purpose: str,
        attempt: int,
    ) -> None:
        """Append one request attempt to requests_log.csv."""
        with request_log_write_lock(
            workdir=self.workdir,
            log_path=self.log_path,
        ):
            # The lock keeps predecessor validation and both COW publications
            # in one transaction so two clients cannot bless a lost update.
            validate_request_log_manifest(log_path=self.log_path)
            self.log_path, _ = request_log_state_paths(
                workdir=self.workdir,
                log_path=self.log_path,
            )
            with self.log_path.open(
                mode="r",
                encoding="utf-8",
                newline="",
            ) as file_obj:
                reader = csv.DictReader(file_obj)
                rows = list(reader)
            row = portable_request_log_row(
                row={
                    "timestamp_utc": utc_now_iso(),
                    "method": "GET",
                    "source_url": result.url,
                    "status_code": result.status_code,
                    "purpose": purpose,
                    "local_path": result.local_path,
                    "headers_path": result.headers_path,
                    "content_length": result.content_length,
                    "content_sha256": result.sha256,
                    "accession": "",
                    "document_name": "",
                    "user_agent": self.user_agent,
                    "retry_attempt": attempt,
                    "error": result.error,
                },
                workdir=self.workdir,
            )
            rows.append(row)
            write_repository_bytes_atomically(
                workdir=self.workdir,
                path=self.log_path,
                content=request_log_csv_bytes(rows=rows),
            )
            refresh_request_log_manifest(
                workdir=self.workdir,
                log_path=self.log_path,
            )
