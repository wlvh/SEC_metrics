"""Load report inputs only from one already pinned PublicationView.

The module does not repair data, call AI, open SEC connections, or write
authoritative artifacts. A future Cutover report generator can consume the
returned exact bytes without falling back to mutable repository-root files.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Dict, Mapping

from .canonical import CanonicalError, sha256_bytes, strict_json_loads
from .publication import GOLDEN_FIELDS, REQUIRED_BUNDLE_FILES
from .publication import ROOT_MIRROR_RELATIVE_PATHS, PublicationView
from .publication import verified_legacy_baseline_identity


REPORT_INPUT_FILES = (
    "coverage_matrix.csv",
    "golden_results.csv",
    "metric_evidence.csv",
    "metrics_matrix.csv",
    "repair_validation_results.csv",
    "stratified_audit.csv",
    "validation_run_manifest.json",
)


def load_report_inputs(
    *, publication_view: PublicationView
) -> Dict[str, bytes]:
    """Read every report input from exactly one immutable publication.

    Args:
        publication_view: Pinned and verified publication boundary.

    Returns:
        Required relative paths mapped to verified bytes.
    """
    return {
        relative: publication_view.read_bytes(relative_path=relative)
        for relative in REPORT_INPUT_FILES
    }


def _json_mapping(*, content: bytes, label: str) -> Mapping[str, object]:
    """Decode one strict UTF-8 JSON object from a pinned artifact.

    Args:
        content: Exact artifact bytes read through ``PublicationView``.
        label: Stable diagnostic name for the artifact.

    Returns:
        Parsed JSON mapping.

    Raises:
        ValueError: When bytes are not strict UTF-8 JSON object data.
    """
    try:
        parsed = strict_json_loads(text=content.decode("utf-8"))
    except (CanonicalError, UnicodeDecodeError) as error:
        raise ValueError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} root must be an object")
    return parsed


def validate_golden_results(*, publication_view: PublicationView) -> int:
    """Validate the Golden snapshot already bound to one pinned publication.

    Args:
        publication_view: Verified immutable publication boundary.

    Returns:
        Number of exact Golden assertions that passed.

    Raises:
        ValueError: On invalid UTF-8/CSV shape, empty rows, or any non-PASS.
    """
    content = publication_view.read_bytes(relative_path="golden_results.csv")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Active Golden snapshot is not UTF-8") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != GOLDEN_FIELDS:
        raise ValueError("Active Golden snapshot schema differs")
    rows = list(reader)
    if not rows:
        raise ValueError("Active Golden snapshot is empty")
    failed = [
        row["assertion_id"]
        for row in rows
        if row["status"] != "PASS"
    ]
    if failed:
        raise ValueError(
            "Active Golden assertions failed: " + ";".join(failed)
        )
    return len(rows)


def read_validated_report(*, publication_view: PublicationView) -> str:
    """Read and bind the report to the same publication validation manifest.

    Args:
        publication_view: Verified immutable publication boundary.

    Returns:
        Exact UTF-8 report text from the pinned bundle.

    Raises:
        ValueError: When manifest identity/result and report bytes disagree.
    """
    manifest = _json_mapping(
        content=publication_view.read_bytes(
            relative_path="validation_run_manifest.json"
        ),
        label="Active validation manifest",
    )
    for field in ("run_id", "mode", "result"):
        if field not in manifest or not isinstance(manifest[field], str):
            raise ValueError(
                f"Active validation manifest field is invalid: {field}"
            )
    if (
        manifest["mode"] != "FULL_VALIDATION"
        or manifest["result"] != "PASSED"
    ):
        raise ValueError("Active publication is not a formal passed view")
    try:
        report = publication_view.read_bytes(
            relative_path="REPORT_十公司财务指标.md",
        ).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Active report is not UTF-8") from error
    expected_lines = {
        f"- run_id: `{manifest['run_id']}`",
        f"- result: `{manifest['result']}`",
    }
    missing = sorted(expected_lines - set(report.splitlines()))
    if missing:
        raise ValueError(
            "Active report validation identity differs: " + ";".join(missing)
        )
    return report


def validate_active_publication(
    *, publication_view: PublicationView, publication_root: Path
) -> Dict[str, object]:
    """Read back one formal publication and its fixed-root mirrors.

    Args:
        publication_view: Already opened and therefore pinned bundle view.
        publication_root: Root containing compatibility mirrors.

    Returns:
        Publication ID, validation result, Golden count, and mirror hashes.

    Raises:
        ValueError: On receipt identity/status or any root mirror mismatch.

    Notes:
        The function never reopens the active pointer. A concurrent pointer
        switch therefore cannot mix artifacts inside this consumer view.
    """
    golden_count = validate_golden_results(
        publication_view=publication_view,
    )
    read_validated_report(publication_view=publication_view)
    validation_manifest = _json_mapping(
        content=publication_view.read_bytes(
            relative_path="validation_run_manifest.json"
        ),
        label="Active validation manifest",
    )
    receipt = _json_mapping(
        content=publication_view.read_bytes(
            relative_path="publication_validation_receipt.json"
        ),
        label="Active publication validation receipt",
    )
    legacy_identity = verified_legacy_baseline_identity(
        publication_view=publication_view,
    )
    if legacy_identity is None:
        for field in ("status", "validation_receipt_id"):
            if field not in receipt or not isinstance(receipt[field], str):
                raise ValueError(
                    f"Active publication receipt field is invalid: {field}"
                )
        if receipt["status"] != "PASSED":
            raise ValueError(
                "Active publication validation receipt did not pass"
            )
        if (
            "validation_receipt_id" not in publication_view.manifest
            or receipt["validation_receipt_id"]
            != publication_view.manifest["validation_receipt_id"]
        ):
            raise ValueError("Active publication receipt identity differs")
        publication_authority = "FORMAL"
        publication_validation_status = str(receipt["status"])
    else:
        expected_legacy_receipt = {
            "schema_version": 1,
            "record_type": "LEGACY_BASELINE_IMPORT_ARTIFACT",
            "artifact_role": "publication_validation_receipt.json",
            "status": "IMPORTED_FROZEN_LEGACY_BASELINE",
            "baseline_manifest_sha256": legacy_identity[
                "baseline_manifest_sha256"
            ],
            "requirement_hashes": legacy_identity["requirement_hashes"],
            "producer_execution": "NOT_RUN_DATA_IMPORT_ONLY",
        }
        if receipt != expected_legacy_receipt:
            raise ValueError(
                "Active legacy import receipt identity differs"
            )
        publication_authority = "LEGACY_BASELINE_IMPORT"
        publication_validation_status = str(receipt["status"])
    mirror_hashes = {}
    if set(ROOT_MIRROR_RELATIVE_PATHS) != REQUIRED_BUNDLE_FILES:
        raise ValueError("Active root mirror exact set differs")
    for relative in sorted(ROOT_MIRROR_RELATIVE_PATHS):
        expected = publication_view.read_bytes(relative_path=relative)
        mirror = publication_root / ROOT_MIRROR_RELATIVE_PATHS[relative]
        if mirror.is_symlink() or not mirror.is_file():
            raise ValueError(
                f"ACTIVE_ROOT_MIRROR_MISMATCH: missing={relative}"
            )
        actual = mirror.read_bytes()
        if actual != expected:
            raise ValueError(
                f"ACTIVE_ROOT_MIRROR_MISMATCH: divergent={relative}"
            )
        mirror_hashes[relative] = sha256_bytes(content=actual)
    return {
        "publication_id": publication_view.publication_id,
        "validation_result": validation_manifest["result"],
        "publication_authority": publication_authority,
        "publication_validation_status": publication_validation_status,
        "golden_assertion_count": golden_count,
        "mirror_hashes": mirror_hashes,
    }
