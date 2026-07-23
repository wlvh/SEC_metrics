#!/usr/bin/env python3
"""Mechanically validate capability-contract anchors and code locators.

Purpose:
    Check only deterministic structure: unique anchors, Markdown references,
    document paths, Python file::symbol locators, explicit untested reasons,
    and the persistent deprecated-anchor registry.

Call relationships:
    main() calls check_alignment(), prints every structural error, and exits
    nonzero on failure. Symbol existence does not prove the associated claim;
    reviewers still grade evidence as direct, partial, structural, or none.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from git_workspace import (  # noqa: E402
    git_checkout_metadata_error,
    sanitized_git_environment,
)


ANCHOR_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
ANCHOR_PATTERN = re.compile(
    r"<!--\s*capability-anchor:\s*([A-Za-z0-9_.-]+)\s*-->"
)
ENTRY_TYPES = {
    "agent_behavior",
    "capability",
    "capability_boundary",
    "document",
    "responsibility_boundary",
}
ENTRY_STATUSES = {"active", "deprecated"}
CURRENT_REQUEST_HISTORY_FIELDS = [
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
LEGACY_REQUEST_HISTORY_FIELDS = [
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
LEGACY_REQUEST_PATH_ANCHOR = "evidence"


def require_key(*, mapping: dict, key: str) -> object:
    """Return one required mapping value or fail fast."""
    if key not in mapping:
        raise KeyError(f"Required key missing: {key}")
    return mapping[key]


def read_contract(*, path: Path) -> dict:
    """Read the UTF-8 capability contract as one JSON object."""
    with path.open(mode="r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        raise TypeError("Capability contract root must be an object")
    return payload


def git_output(*, repo_root: Path, arguments: list[str]) -> str:
    """Return UTF-8 Git stdout or fail with the command diagnostic."""
    result = subprocess.run(
        args=[
            "git",
            "--no-replace-objects",
            "-C",
            str(repo_root),
            *arguments,
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=sanitized_git_environment(),
    )
    if result.returncode != 0:
        diagnostic = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Git command failed: {diagnostic}")
    return result.stdout


def git_bytes(*, repo_root: Path, arguments: list[str]) -> bytes:
    """Return exact Git stdout bytes or fail with its diagnostic."""
    result = subprocess.run(
        args=[
            "git",
            "--no-replace-objects",
            "-C",
            str(repo_root),
            *arguments,
        ],
        check=False,
        capture_output=True,
        env=sanitized_git_environment(),
    )
    if result.returncode != 0:
        diagnostic = result.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()
        raise RuntimeError(f"Git command failed: {diagnostic}")
    return result.stdout


def git_repository_toplevel(*, repo_root: Path) -> Path:
    """Return the resolved Git toplevel containing the requested path."""
    path_text = git_output(
        repo_root=repo_root,
        arguments=["rev-parse", "--show-toplevel"],
    ).strip()
    if not path_text:
        raise RuntimeError("Git repository toplevel is empty")
    return Path(path_text).resolve()


def git_committed_entries(
    *,
    repo_root: Path,
) -> dict[Path, tuple[str, str, str]]:
    """Return HEAD paths mapped to mode, object type, and object id."""
    output = git_output(
        repo_root=repo_root,
        arguments=["ls-tree", "-r", "-z", "HEAD"],
    )
    entries = {}
    for record in output.split("\0"):
        if not record:
            continue
        metadata, path_text = record.split("\t", maxsplit=1)
        mode, object_type, object_id = metadata.split(maxsplit=2)
        entries[Path(path_text)] = (mode, object_type, object_id)
    return entries


def contract_at_ref(
    *,
    repo_root: Path,
    contract_path: Path,
    ref: str,
) -> dict:
    """Read the capability contract committed at one verified base ref."""
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError("base ref must be a non-empty string")
    try:
        relative_path = contract_path.resolve(strict=False).relative_to(
            repo_root.resolve()
        )
    except ValueError as error:
        raise ValueError(
            "contract path must be inside the repository"
        ) from error

    # Resolving first prevents an option-like ref from changing git-show flags.
    commit = git_output(
        repo_root=repo_root,
        arguments=[
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        ],
    ).strip()
    raw_payload = git_output(
        repo_root=repo_root,
        arguments=["show", f"{commit}:{relative_path.as_posix()}"],
    )
    payload = json.loads(raw_payload)
    if not isinstance(payload, dict):
        raise TypeError("Base capability contract root must be an object")
    return payload


def request_log_at_ref(*, repo_root: Path, ref: str) -> str:
    """Return the request ledger committed at one verified ref."""
    commit = git_output(
        repo_root=repo_root,
        arguments=[
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        ],
    ).strip()
    return git_output(
        repo_root=repo_root,
        arguments=["show", f"{commit}:evidence/requests_log.csv"],
    )


def checker_legacy_request_path_candidates(*, path: Path) -> list[Path]:
    """Enumerate every evidence suffix without importing production logic.

    Args:
        path: Legacy absolute request-artifact locator.

    Returns:
        Deduplicated repository-shaped suffixes in lexical order.
    """
    if ".." in path.parts:
        raise ValueError(
            f"Legacy request artifact escapes repository: {path}"
        )
    candidates = []
    seen = set()
    for index, part in enumerate(path.parts):
        if part != LEGACY_REQUEST_PATH_ANCHOR:
            continue
        candidate = Path(*path.parts[index:])
        candidate_text = candidate.as_posix()
        if candidate_text in seen:
            continue
        seen.add(candidate_text)
        candidates.append(candidate)
    return candidates


def checker_selected_legacy_repository_prefix(
    *,
    path_text: str,
    relative_path: str,
) -> tuple[str, ...]:
    """Return the discarded clone prefix without production migration code.

    Args:
        path_text: Original legacy request-artifact locator.
        relative_path: Independently selected repository-relative suffix.

    Returns:
        Lexical path components before the suffix, or an empty tuple when the
        locator has no comparable absolute repository boundary.
    """
    path = Path(path_text)
    if not path.is_absolute() or not relative_path:
        return ()
    for candidate in checker_legacy_request_path_candidates(path=path):
        if candidate.as_posix() == relative_path:
            return path.parts[:-len(candidate.parts)]
    return ()


def normalized_legacy_request_path(
    *,
    repo_root: Path,
    row: dict[str, str],
    path_text: str,
    document_name: str,
    is_headers: bool,
) -> str:
    """Select one legacy request suffix by independent current-clone identity.

    Args:
        repo_root: Current checkout root used only to inspect candidates.
        row: Complete legacy request observation.
        path_text: Body or headers legacy locator.
        document_name: Expected response document name.
        is_headers: Whether path_text identifies the headers sidecar.

    Returns:
        Unique repository-relative path; ambiguous inputs fail closed.
    """
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_absolute():
        if ".." in path.parts or not (repo_root / path).resolve(
            strict=False,
        ).is_relative_to(repo_root.resolve()):
            raise ValueError(
                f"Legacy request artifact escapes repository: {path}"
            )
        return path.as_posix()
    candidates = checker_legacy_request_path_candidates(path=path)
    if not candidates:
        raise ValueError(
            f"Legacy request artifact is outside repository: {path}"
        )
    if len(candidates) == 1:
        # Preserve the legacy one-anchor mapping so missing or stale bytes stay
        # visible to the business validation layer rather than this gate.
        return candidates[0].as_posix()
    matched = []
    for candidate in candidates:
        current_path = repo_root / candidate
        if not current_path.resolve(strict=False).is_relative_to(
            repo_root.resolve()
        ):
            raise ValueError(
                f"Legacy request artifact escapes repository: {candidate}"
            )
        if not current_path.is_file():
            continue
        if not is_headers and (
            current_path.name == document_name
            and hashlib.sha256(current_path.read_bytes()).hexdigest()
            == row["sha256"]
        ):
            matched.append(candidate)
            continue
        if not is_headers:
            continue
        try:
            payload = json.loads(current_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        required_fields = {"url", "status_code", "content_length", "sha256"}
        if (
            isinstance(payload, dict)
            and required_fields.issubset(payload)
            and str(payload["url"]) == row["url"]
            and str(payload["status_code"]) == row["status_code"]
            and str(payload["content_length"]) == row["content_length"]
            and str(payload["sha256"]) == row["sha256"]
        ):
            matched.append(candidate)
    if len(matched) == 1:
        return matched[0].as_posix()
    if not matched:
        raise FileNotFoundError(
            f"Legacy request artifact has no identity match: {path}"
        )
    raise ValueError(f"Legacy request artifact is ambiguous: {path}")


def normalized_legacy_request_history_row(
    *,
    repo_root: Path,
    row: dict[str, str],
) -> tuple[str, ...]:
    """Normalize one legacy ledger row without production migration code."""
    source_url = row["url"]
    document_name = (
        Path(row["local_path"]).name
        if row["local_path"]
        else Path(urlparse(source_url).path).name
    )
    accession_match = re.search(
        pattern=r"/Archives/edgar/data/\d+/(\d{18})(?:/|$)",
        string=urlparse(source_url).path,
    )
    accession = ""
    if accession_match is not None:
        compact = accession_match.group(1)
        accession = f"{compact[:10]}-{compact[10:12]}-{compact[12:]}"
    if not row["sha256"]:
        # A body-less attempt cannot retain a locator later bytes may fill.
        relative_path = ""
        headers_relative_path = ""
    else:
        relative_path = normalized_legacy_request_path(
            repo_root=repo_root,
            row=row,
            path_text=row["local_path"],
            document_name=document_name,
            is_headers=False,
        )
        headers_relative_path = normalized_legacy_request_path(
            repo_root=repo_root,
            row=row,
            path_text=row["headers_path"],
            document_name=document_name,
            is_headers=True,
        )
        body_root = checker_selected_legacy_repository_prefix(
            path_text=row["local_path"],
            relative_path=relative_path,
        )
        headers_root = checker_selected_legacy_repository_prefix(
            path_text=row["headers_path"],
            relative_path=headers_relative_path,
        )
        # This independent gate must reject the same cross-clone splice
        # without importing the production helper it is meant to audit.
        if body_root and headers_root and body_root != headers_root:
            raise ValueError(
                "Request body and headers use different legacy repository "
                "roots"
            )
    return (
        row["timestamp_utc"],
        row["method"],
        source_url,
        row["status_code"],
        row["purpose"],
        relative_path,
        headers_relative_path,
        row["content_length"],
        row["sha256"],
        accession,
        document_name,
        row["user_agent"],
        row["retry_attempt"],
        row["error"],
    )


def request_history_sequence(
    *,
    repo_root: Path,
    text: str,
) -> list[tuple[str, ...]]:
    """Return an exact current or independently normalized legacy sequence."""
    with io.StringIO(text, newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        rows = list(reader)
        fieldnames = reader.fieldnames if reader.fieldnames is not None else []
    if fieldnames not in [
        CURRENT_REQUEST_HISTORY_FIELDS,
        LEGACY_REQUEST_HISTORY_FIELDS,
    ]:
        raise ValueError(f"Unrecognized request ledger schema: {fieldnames}")
    expected_fields = set(fieldnames)
    # Validate every base and HEAD row before projection so malformed prefix
    # or appended cells cannot disappear from the ordered-history comparison.
    for row_number, row in enumerate(rows, start=2):
        if set(row) != expected_fields or any(
            row[field] is None for field in fieldnames
        ):
            raise ValueError(
                f"Unexpected request ledger row shape at line {row_number}"
            )
    if fieldnames == CURRENT_REQUEST_HISTORY_FIELDS:
        return [
            tuple(row[field] for field in CURRENT_REQUEST_HISTORY_FIELDS)
            for row in rows
        ]
    return [
        normalized_legacy_request_history_row(
            repo_root=repo_root,
            row=row,
        )
        for row in rows
    ]


def request_log_history_errors(
    *,
    repo_root: Path,
    base_ref: str,
) -> list[str]:
    """Return base rows removed, changed, or reordered in the HEAD ledger."""
    sequences = []
    # Convert expected evidence-shape failures into reviewer-facing gate output
    # while leaving Git and programming errors at their original boundaries.
    for label, ref in [("base", base_ref), ("HEAD", "HEAD")]:
        try:
            sequence = request_history_sequence(
                repo_root=repo_root,
                text=request_log_at_ref(repo_root=repo_root, ref=ref),
            )
        except (FileNotFoundError, ValueError) as error:
            return [f"{label} request ledger invalid: {error}"]
        sequences.append(sequence)
    base_sequence, head_sequence = sequences
    if len(head_sequence) < len(base_sequence):
        return [
            "request ledger observations removed since base: "
            f"count={len(base_sequence) - len(head_sequence)}"
        ]
    for row_number, base_row in enumerate(base_sequence, start=1):
        if head_sequence[row_number - 1] == base_row:
            continue
        return [
            "request ledger prefix changed since base: "
            f"row={row_number}; base={base_row}; "
            f"head={head_sequence[row_number - 1]}"
        ]
    return []


def contract_entries(*, payload: dict) -> list[dict]:
    """Flatten every declared contract group into ordered entry rows."""
    contracts = require_key(mapping=payload, key="contracts")
    if not isinstance(contracts, dict):
        raise TypeError("contracts must be an object")
    entries = []
    for group_name, group_entries in contracts.items():
        if not isinstance(group_entries, list):
            raise TypeError(f"Contract group must be an array: {group_name}")
        for entry in group_entries:
            if not isinstance(entry, dict):
                raise TypeError(
                    f"Contract entry must be an object: {group_name}")
            entries.append(entry)
    return entries


def contract_evidence_paths(
    *,
    payload: dict,
    contract_relative_path: Path,
    committed_paths: set[Path],
) -> set[Path]:
    """Return committed paths whose working bytes can affect the checker."""
    paths = {
        path
        for path in committed_paths
        if path.suffix == ".md" and path != Path("PR_BODY.md")
    }
    paths.add(contract_relative_path)
    for entry in contract_entries(payload=payload):
        test_anchor = entry["test_anchor"] if "test_anchor" in entry else None
        if isinstance(test_anchor, str) and test_anchor.count("::") == 1:
            file_text, _symbol = test_anchor.split("::", maxsplit=1)
            paths.add(Path(file_text))
        document_path = (
            entry["document_path"] if "document_path" in entry else None
        )
        if isinstance(document_path, str):
            paths.add(Path(document_path))
    return paths


def markdown_files(
    *,
    repo_root: Path,
    tracked_paths: set[Path] | None = None,
) -> list[Path]:
    """Return in-scope Markdown while excluding the root local PR draft."""
    local_pr_draft = repo_root / "PR_BODY.md"
    if tracked_paths is not None:
        candidates = [repo_root / path for path in tracked_paths]
    else:
        # Direct helper callers may supply a synthetic non-Git filesystem.
        candidates = list(repo_root.rglob("*.md"))
    return [
        path
        for path in sorted(candidates)
        if path.suffix == ".md"
        and path.is_file()
        and ".git" not in path.parts
        and path != local_pr_draft
    ]


def markdown_anchor_references(
    *,
    repo_root: Path,
    tracked_paths: set[Path] | None = None,
) -> list[tuple[Path, str]]:
    """Return every Markdown capability-anchor reference with its file."""
    references = []
    for path in markdown_files(
        repo_root=repo_root,
        tracked_paths=tracked_paths,
    ):
        text = path.read_text(encoding="utf-8")
        for anchor_id in ANCHOR_PATTERN.findall(text):
            references.append((path, anchor_id))
    return references


def markdown_anchor_syntax_errors(
    *,
    repo_root: Path,
    tracked_paths: set[Path] | None = None,
) -> list[str]:
    """Return malformed capability-anchor directive errors in Markdown."""
    errors = []
    for path in markdown_files(
        repo_root=repo_root,
        tracked_paths=tracked_paths,
    ):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            marker_count = line.count("capability-anchor:")
            if not marker_count:
                continue
            # The permissive marker count exposes malformed comments that the
            # strict extractor would otherwise silently omit from alignment.
            if len(ANCHOR_PATTERN.findall(line)) != marker_count:
                relative_path = path.relative_to(repo_root)
                errors.append(
                    f"{relative_path}:{line_number}: malformed "
                    "capability-anchor directive"
                )
    return errors


def python_symbols(*, path: Path) -> set[str]:
    """Return top-level and Class.member Python symbols from one source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    symbols = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        if not isinstance(node, ast.ClassDef):
            continue
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.add(f"{node.name}.{member.name}")
    return symbols


def valid_required_text(*, mapping: dict, key: str) -> bool:
    """Return whether one required field is a non-empty string."""
    return (
        key in mapping
        and isinstance(mapping[key], str)
        and bool(mapping[key].strip())
    )


def test_anchor_errors(
    *,
    repo_root: Path,
    entry: dict,
    tracked_paths: set[Path] | None = None,
) -> list[str]:
    """Return structural errors for one entry's test anchor."""
    anchor_id = require_key(mapping=entry, key="anchor_id")
    test_anchor = require_key(mapping=entry, key="test_anchor")
    if test_anchor is None:
        errors = []
        if not valid_required_text(mapping=entry, key="untested_reason"):
            errors.append(
                f"{anchor_id}: null test_anchor requires untested_reason"
            )
        if not valid_required_text(mapping=entry, key="pending_since"):
            errors.append(
                f"{anchor_id}: null test_anchor requires pending_since"
            )
        return errors
    if (
        not isinstance(test_anchor, str)
        or test_anchor.count("::") != 1
    ):
        return [f"{anchor_id}: test_anchor must be file::symbol or null"]
    file_text, symbol = test_anchor.split("::", maxsplit=1)
    if not file_text.strip() or not symbol.strip():
        return [f"{anchor_id}: test_anchor must be file::symbol or null"]
    file_path = Path(file_text)
    if file_path.is_absolute() or ".." in file_path.parts:
        return [
            f"{anchor_id}: test anchor path must be repository-relative"
        ]
    source_path = repo_root / file_path
    if not source_path.resolve(strict=False).is_relative_to(repo_root.resolve()):
        return [
            f"{anchor_id}: test anchor path must be repository-relative"
        ]
    errors = []
    if tracked_paths is not None and file_path not in tracked_paths:
        return [
            f"{anchor_id}: test file is not committed in HEAD: {file_text}"
        ]
    if source_path.is_symlink():
        return [f"{anchor_id}: test file must not be a symlink: {file_text}"]
    if not source_path.is_file():
        return [f"{anchor_id}: test file missing: {file_text}"]
    if source_path.suffix != ".py":
        return [f"{anchor_id}: test anchor file is not Python: {file_text}"]
    if symbol not in python_symbols(path=source_path):
        errors.append(f"{anchor_id}: symbol missing: {test_anchor}")
    return errors


def document_path_errors(
    *,
    repo_root: Path,
    entry: dict,
    tracked_paths: set[Path] | None = None,
) -> list[str]:
    """Return missing or escaping document-path errors for one entry."""
    entry_type = entry["type"] if "type" in entry else None
    if "document_path" not in entry and entry_type == "document":
        anchor_id = require_key(mapping=entry, key="anchor_id")
        return [f"{anchor_id}: document type requires document_path"]
    if "document_path" not in entry:
        return []
    anchor_id = require_key(mapping=entry, key="anchor_id")
    if not valid_required_text(mapping=entry, key="document_path"):
        return [f"{anchor_id}: document_path must be a non-empty string"]
    document_path = Path(entry["document_path"])
    if document_path.is_absolute() or ".." in document_path.parts:
        return [f"{anchor_id}: document_path must be repository-relative"]
    resolved_path = (repo_root / document_path).resolve(strict=False)
    if not resolved_path.is_relative_to(repo_root.resolve()):
        return [f"{anchor_id}: document_path must be repository-relative"]
    if tracked_paths is not None and document_path not in tracked_paths:
        return [
            f"{anchor_id}: document path is not committed in HEAD: "
            f"{document_path}"
        ]
    if (repo_root / document_path).is_symlink():
        return [
            f"{anchor_id}: document path must not be a symlink: "
            f"{document_path}"
        ]
    if not resolved_path.is_file():
        return [f"{anchor_id}: document path missing: {document_path}"]
    return []


def deprecated_registry(*, payload: dict, required: bool) -> set[str]:
    """Return a validated deprecated-anchor registry."""
    if "deprecated_anchor_ids" not in payload and not required:
        return set()
    values = require_key(mapping=payload, key="deprecated_anchor_ids")
    if not isinstance(values, list):
        raise TypeError("deprecated_anchor_ids must be an array")
    for value in values:
        if (
            not isinstance(value, str)
            or ANCHOR_ID_PATTERN.fullmatch(value) is None
        ):
            raise TypeError(
                "deprecated_anchor_ids values must be valid anchor ids"
            )
    return set(values)


def deprecated_history_errors(
    *,
    base_payload: dict,
    payload: dict,
) -> list[str]:
    """Return base-to-head tombstone deletion and reuse errors."""
    base_entries = contract_entries(payload=base_payload)
    entries = contract_entries(payload=payload)
    base_ids = {
        require_key(mapping=entry, key="anchor_id") for entry in base_entries
    }
    current_ids = {
        require_key(mapping=entry, key="anchor_id") for entry in entries
    }
    base_registry = deprecated_registry(
        payload=base_payload,
        required=False,
    )
    registry = deprecated_registry(payload=payload, required=True)
    base_deprecated_entries = {
        require_key(mapping=entry, key="anchor_id")
        for entry in base_entries
        if require_key(mapping=entry, key="status") == "deprecated"
    }
    active_ids = {
        require_key(mapping=entry, key="anchor_id")
        for entry in entries
        if require_key(mapping=entry, key="status") != "deprecated"
    }
    errors = []
    for anchor_id in sorted(base_registry - registry):
        errors.append(
            f"deprecated registry id removed since base: {anchor_id}"
        )
    for anchor_id in sorted(base_ids - current_ids - registry):
        errors.append(f"removed anchor missing from registry: {anchor_id}")
    historical_deprecated = base_registry | base_deprecated_entries
    for anchor_id in sorted(historical_deprecated & active_ids):
        errors.append(f"historically deprecated anchor reused: {anchor_id}")
    return errors


def alignment_errors(
    *,
    repo_root: Path,
    payload: dict,
    tracked_paths: set[Path] | None = None,
    base_payload: dict | None = None,
) -> list[str]:
    """Return all deterministic capability-contract alignment errors."""
    entries = contract_entries(payload=payload)
    errors = []
    anchor_counts: dict[str, int] = {}
    active_anchors = set()
    deprecated_entries = set()
    for entry in entries:
        if (
            not valid_required_text(mapping=entry, key="anchor_id")
            or ANCHOR_ID_PATTERN.fullmatch(str(entry["anchor_id"])) is None
        ):
            errors.append(
                "contract entry anchor_id must be a valid anchor id"
            )
            continue
        anchor_id = entry["anchor_id"]
        anchor_counts[anchor_id] = (
            anchor_counts[anchor_id] + 1
            if anchor_id in anchor_counts
            else 1
        )
        if not valid_required_text(mapping=entry, key="status"):
            errors.append(f"{anchor_id}: status must be a non-empty string")
            continue
        status = entry["status"]
        if status not in ENTRY_STATUSES:
            errors.append(
                f"{anchor_id}: status must be one of "
                f"{sorted(ENTRY_STATUSES)}"
            )
        if not valid_required_text(mapping=entry, key="type"):
            errors.append(f"{anchor_id}: type must be a non-empty string")
        elif entry["type"] not in ENTRY_TYPES:
            errors.append(
                f"{anchor_id}: type must be one of {sorted(ENTRY_TYPES)}"
            )
        if status == "deprecated":
            deprecated_entries.add(anchor_id)
        else:
            active_anchors.add(anchor_id)
        errors.extend(
            test_anchor_errors(
                repo_root=repo_root,
                entry=entry,
                tracked_paths=tracked_paths,
            )
        )
        errors.extend(
            document_path_errors(
                repo_root=repo_root,
                entry=entry,
                tracked_paths=tracked_paths,
            )
        )
    for anchor_id, count in anchor_counts.items():
        if count != 1:
            errors.append(f"duplicate anchor_id: {anchor_id} count={count}")

    deprecated_ids = require_key(mapping=payload, key="deprecated_anchor_ids")
    registry = deprecated_registry(
        payload=payload,
        required=True,
    )
    if len(deprecated_ids) != len(set(deprecated_ids)):
        errors.append("deprecated_anchor_ids contains duplicates")
    for anchor_id in sorted(deprecated_entries - registry):
        errors.append(f"deprecated entry missing from registry: {anchor_id}")
    for anchor_id in sorted(registry & active_anchors):
        errors.append(f"deprecated anchor reused by active entry: {anchor_id}")

    known_anchors = set(anchor_counts)
    errors.extend(
        markdown_anchor_syntax_errors(
            repo_root=repo_root,
            tracked_paths=tracked_paths,
        )
    )
    for path, anchor_id in markdown_anchor_references(
        repo_root=repo_root,
        tracked_paths=tracked_paths,
    ):
        relative_path = path.relative_to(repo_root)
        if anchor_id not in known_anchors:
            errors.append(
                f"{relative_path}: unknown Markdown anchor: {anchor_id}")
        if anchor_id in registry:
            errors.append(
                f"{relative_path}: deprecated Markdown anchor: {anchor_id}")
    if base_payload is not None:
        errors.extend(
            deprecated_history_errors(
                base_payload=base_payload,
                payload=payload,
            )
        )
    return errors


def check_alignment(
    *,
    repo_root: Path,
    contract_path: Path,
    base_ref: str | None = None,
) -> list[str]:
    """Read the contract and return its deterministic alignment errors.

    Args:
        repo_root: Checked-out repository root.
        contract_path: Current capability-contract JSON path.
        base_ref: Optional historical boundary for tombstone validation.

    Returns:
        Structural and clean-clone reproducibility errors.
    """
    metadata_error = git_checkout_metadata_error(repo_root=repo_root)
    if metadata_error:
        return [metadata_error]
    if git_repository_toplevel(repo_root=repo_root) != repo_root.resolve():
        return ["repo_root must be the Git repository toplevel"]
    if contract_path.is_symlink():
        return ["capability_contract.json must not be a symlink"]
    candidate_path = contract_path
    if not contract_path.is_absolute():
        candidate_path = repo_root / contract_path
    try:
        contract_relative_path = candidate_path.relative_to(repo_root)
    except ValueError:
        return ["capability_contract.json must be repository-relative"]
    if ".." in contract_relative_path.parts:
        return ["capability_contract.json must be repository-relative"]
    if not candidate_path.resolve(strict=False).is_relative_to(
        repo_root.resolve()
    ):
        return ["capability_contract.json must be repository-relative"]
    payload = read_contract(path=candidate_path)
    committed_entries = git_committed_entries(repo_root=repo_root)
    tracked_paths = set(committed_entries)
    if contract_relative_path not in tracked_paths:
        return ["capability_contract.json is not committed in HEAD"]
    base_payload = (
        contract_at_ref(
            repo_root=repo_root,
            contract_path=candidate_path,
            ref=base_ref,
        )
        if base_ref is not None
        else None
    )
    errors = alignment_errors(
        repo_root=repo_root,
        payload=payload,
        tracked_paths=tracked_paths,
        base_payload=base_payload,
    )
    evidence_paths = contract_evidence_paths(
        payload=payload,
        contract_relative_path=contract_relative_path,
        committed_paths=tracked_paths,
    )
    for path in sorted(evidence_paths & tracked_paths):
        mode, object_type, object_id = committed_entries[path]
        working_path = repo_root / path
        if (
            mode not in {"100644", "100755"}
            or object_type != "blob"
            or working_path.is_symlink()
            or not working_path.is_file()
        ):
            errors.append(
                f"clean-clone evidence is not a regular file: {path}"
            )
            continue
        committed_bytes = git_bytes(
            repo_root=repo_root,
            arguments=["cat-file", "blob", object_id],
        )
        if working_path.read_bytes() != committed_bytes:
            errors.append(f"clean-clone evidence differs from HEAD: {path}")
    if base_ref is not None:
        errors.extend(
            request_log_history_errors(
                repo_root=repo_root,
                base_ref=base_ref,
            )
        )
    return errors


def parse_arguments(*, argv: list[str]) -> argparse.Namespace:
    """Parse an optional repository root and base-ref history boundary."""
    parser = argparse.ArgumentParser(
        description="Validate capability-contract structural evidence.",
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=Path.cwd(),
        type=Path,
    )
    parser.add_argument(
        "--base-ref",
        help=(
            "Compare deprecated anchors from this Git ref to current "
            "payload."
        ),
    )
    return parser.parse_args(args=argv[1:])


def main(*, argv: list[str]) -> None:
    """Run the repository checker and exit nonzero on structural drift."""
    arguments = parse_arguments(argv=argv)
    repo_root = arguments.repo_root.resolve()
    errors = check_alignment(
        repo_root=repo_root,
        contract_path=repo_root / "capability_contract.json",
        base_ref=arguments.base_ref,
    )
    if errors:
        print("Capability contract alignment failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(
        "PASS: capability contract structure aligns; symbol existence is "
        "structural evidence, not proof of the claim"
    )


if __name__ == "__main__":
    main(argv=sys.argv)
