"""Saved annual source reads and ordinary source-state errors only.

No metric calculation, publication or qualification workflow is imported.
A later failed request remains a failure rather than falling back to success.
"""
from datetime import datetime
from sec_http import request_log_attempt_id
from . import annual_input
from .canonical import strict_json_file
from .sources import resolve_repository_file


class AnnualUpdateError(ValueError):
    """An unsuccessful check is never a no-change observation."""


def _require(condition, reason):
    if not condition:
        raise AnnualUpdateError(reason)


def _utc(value):
    _require(type(value) is str, "SOURCE_SAVED_TIME_UNKNOWN")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.utcoffset() is not None, "SOURCE_SAVED_TIME_UNKNOWN")
    return value


def _rows(repo_root):
    path = repo_root / "evidence/requests_log.csv"
    annual_input.validate_request_log_manifest(log_path=path)
    return annual_input.parse_request_log_rows(text=path.read_text(encoding="utf-8"))


def saved_source(*, repo_root, url, accession=""):
    """Retain the normal proof, but never hide a later failed observation."""
    rows = _rows(repo_root)
    matching = [(i, r) for i, r in enumerate(rows) if r["source_url"] == url and r["method"] == "GET"]
    if not matching:
        return None
    index, latest = matching[-1]
    _require(latest["status_code"] == "200" and not latest["error"], "LATEST_SOURCE_REQUEST_FAILED: " + url)
    proof, raw = annual_input._saved_source(repo_root=repo_root, rows=rows, url=url, accession=accession)
    _require(proof["request_attempt_id"] == request_log_attempt_id(row_index=index, row=latest),
             "SOURCE_ATTEMPT_SELECTION_CONFLICT")
    headers = strict_json_file(path=resolve_repository_file(repo_root=repo_root,
        repo_relative_path=proof["request_headers_repo_relative_path"]))
    return {"proof": proof, "saved_at_utc": _utc(headers.get("saved_at_utc")), "raw": raw}

