"""Verify saved input imports against an installed, pinned acquisition baseline.

This is a read-only adapter for the existing request ledger and source checks.
The caller controls its data directory, not the installed source manifest. It
does not create an acquisition receipt, reopen a budget or fetch anything.
"""

import hashlib
from pathlib import Path

from .batch_workflow import validate_request_attempt_binding
from .canonical import sha256_file, strict_json_file
from .sources import resolve_repository_file


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = "config/normal_candidate_sources_v1.json"


class NormalSourceAuthorityError(ValueError):
    """Reject caller-created sources or a changed imported acquisition record."""


def _need(condition, reason):
    if not condition:
        raise NormalSourceAuthorityError(reason)


def _git_blob_id(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _baseline_file(data_root, relative, baseline):
    entry = baseline["files"].get(relative)
    _need(entry is not None, "SOURCE_NOT_IN_TRUSTED_SAVED_BASELINE:" + relative)
    path = resolve_repository_file(repo_root=data_root, repo_relative_path=relative)
    raw = path.read_bytes()
    _need(len(raw) == entry["size"] and _git_blob_id(raw) == entry["git_blob_id"],
          "TRUSTED_SAVED_BASELINE_BYTES_CHANGED:" + relative)


def verify_saved_source_proofs(*, data_root: Path, proofs: list) -> dict:
    """Bind actual SHA-256 request proofs to the code-owned historical ledger.

    Git blob IDs identify bytes imported from the reviewed source tree. The
    ledger inside that same tree binds the SHA-256 of each requested body and
    its independent headers; a self-consistent replacement ledger cannot join.
    """
    manifest_path = resolve_repository_file(repo_root=ROOT,
                                            repo_relative_path=MANIFEST_PATH)
    baseline = strict_json_file(path=manifest_path)
    _need(baseline["record_type"] == "TRUSTED_SAVED_SOURCE_BASELINE"
          and baseline["schema_version"] == 1
          and baseline["source_credit"] == "PREEXISTING_SAVED_ACQUISITIONS_ONLY",
          "SAVED_SOURCE_BASELINE_INVALID")
    _need(type(proofs) is list and bool(proofs), "SOURCE_PROOF_SET_REQUIRED")
    for relative in ["config/company_registry.csv", "evidence/requests_log.csv",
                     "evidence/requests_log_manifest.json"]:
        _baseline_file(data_root, relative, baseline)
    verified = []
    for proof in proofs:
        for relative in [proof["request_repo_relative_path"],
                         proof["request_headers_repo_relative_path"]]:
            _baseline_file(data_root, relative, baseline)
        binding = validate_request_attempt_binding(
            repo_root=data_root, source_url=proof["source_url"],
            content_sha256=proof["content_sha256"], accession=proof["accession"],
            document_name=proof["document_name"],
            request_attempt_id=proof["request_attempt_id"],
            require_immutable=proof["request_locator_kind"] == "IMMUTABLE_ATTEMPT")
        expected = {k: v for k, v in proof.items()
                    if k not in {"source_url", "accession", "document_name", "content_sha256"}}
        _need(binding == expected, "IMPORTED_REQUEST_PROOF_CHANGED")
        verified.append(proof["request_attempt_id"])
    return {"record_type": "VERIFIED_NORMAL_SAVED_INPUTS",
            "trusted_baseline_commit": baseline["baseline_commit"],
            "source_manifest_sha256": sha256_file(path=manifest_path),
            "request_attempt_ids": verified,
            "source_credit": baseline["source_credit"],
            "new_business_calls": {"provider": 0, "paid": 0, "sec": 0}}
