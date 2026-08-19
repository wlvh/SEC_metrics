"""Immutable bundle, atomic pointer, pinned view, CAS, and rollback tests."""

from __future__ import annotations

import csv
import inspect
import json
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Dict, Mapping, Optional
from unittest import mock

from sec_http import REQUEST_LOG_FIELDNAMES, parse_request_log_rows
from sec_http import request_log_attempt_id
from sec_http import request_log_csv_bytes, request_log_manifest_payload
from tests.vnext.common import REPO_ROOT
from tests.vnext.projection_fixture_support import scoped_repository
from tests.vnext.test_replay import approve_and_finalize
from tests.vnext.test_replay import create_full_release_run, create_review_run
from tests.vnext.test_replay import create_structured_b01_run
from tests.vnext.test_replay import freeze_fixture
from vnext.canonical import atomic_write_bytes, atomic_write_json
from vnext.canonical import canonical_json_bytes
from vnext.canonical import content_hash, sha256_bytes
from vnext.canonical import sha256_file, strict_json_file
from vnext.projector import ProjectionError, build_projection_manifest
from vnext.projector import write_projection_batch_manifest
from vnext.projector import write_projection_candidate
from vnext import publication as publication_module
from vnext.publication import REQUIRED_BUNDLE_FILES, PublicationError
from vnext.publication import RECORDED_VALIDATION_MODE
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS
from vnext.publication import EVIDENCE_FIELDS, GOLDEN_FIELDS
from vnext.publication import METRIC_FIELDS, REPAIR_FIELDS
from vnext.publication import PublicationView, commit_publication
from vnext.publication import complete_recorded_publication_sandbox
from vnext.publication import prepare_publication_bundle
from vnext.publication import publication_state_snapshot
from vnext.publication import publication_ledger_binding
from vnext.publication import publication_layout
from vnext.publication import publication_validation_view_id
from vnext.publication import recover_publication_mirrors, rollback_publication
from vnext.publication import verify_publication_bundle
from vnext.publication import write_latest_run_status
from vnext.publication import write_publication_fault_receipt
from vnext.publication import write_publication_validation_receipt
from vnext.records import validate_record
from vnext.run_store import create_run, fail_run, write_validation_receipt


PUBLICATION_CHECKS = (
    "COVERAGE",
    "GOLDEN",
    "LEGACY_INVARIANT_MIGRATION",
    "PROJECTION_EXACT_SET",
    "REQUEST_LOCATOR_TIER",
    "REPAIR_VALIDATION",
    "SCALABILITY_AUDIT",
    "SEMANTIC_AUDIT",
    "STRATIFIED_AUDIT",
)


class SimulatedPublicationCrash(BaseException):
    """Escape normal transaction recovery to model process termination."""


def write_csv(
    *, path: Path, fieldnames: tuple, rows: list
) -> None:
    """Persist deterministic UTF-8 CSV fixture bytes.

    Args:
        path: Destination path.
        fieldnames: Exact ordered schema.
        rows: Ordered exact-schema rows.
    """
    with path.open(mode="w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(fieldnames), lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_csv(*, path: Path) -> list:
    """Read one UTF-8 CSV fixture as ordered string mappings.

    Args:
        path: Existing fixture path.

    Returns:
        Ordered CSV rows.
    """
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def legacy_snapshot(*, workspace: Path) -> Path:
    """Write independent legacy rows matching the frozen structured fixture.

    Args:
        workspace: Fixture workspace.

    Returns:
        Complete one-company legacy snapshot directory.
    """
    legacy_dir = workspace / "legacy"
    legacy_dir.mkdir()
    common = {
        "company": "Pfizer",
        "cik": "78003",
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "fiscal_year": "2025",
        "fiscal_period": "FY",
        "form": "10-K",
        "filed_date": "2026-02-26",
    }
    accession = "0000078003-26-100099"
    metrics = [
        {
            **common,
            "metric_id": "B01",
            "metric_name": "Revenue",
            "value": "1000",
            "unit": "USD",
            "status": "OK",
            "source_class": "STD_XBRL",
            "formula": "direct",
            "accession": accession,
            "concept_or_section": "Revenues",
            "context_or_dimension": "companyfacts:USD:CY2025",
            "confidence": "0.95",
            "notes": "Revenue candidate chain from metric definition.",
        },
        {
            **common,
            "metric_id": "B03",
            "metric_name": "EBITDA margin",
            "value": "0.12",
            "unit": "ratio",
            "status": "OK_APPROX",
            "source_class": "DERIVED",
            "formula": "(Operating income + D&A) / revenue",
            "accession": ";".join([accession] * 4),
            "form": "10-K",
            "filed_date": ";".join(["2026-02-26"] * 4),
            "concept_or_section": (
                "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
                "ExtraordinaryItemsNoncontrollingInterest"
                "+OtherNonoperatingIncomeExpense"
                "+DepreciationDepletionAndAmortization+Revenues"
            ),
            "context_or_dimension": ";".join(
                ["companyfacts:USD:CY2025"] * 4
            ),
            "confidence": "0.90",
            "notes": "Fixture branch explanation.",
        },
    ]
    write_csv(
        path=legacy_dir / "metrics_matrix.csv",
        fieldnames=METRIC_FIELDS,
        rows=metrics,
    )
    source_url = (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000078003.json"
    )
    repo_path = (
        "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
        "CIK0000078003.json"
    )
    digest = "f40032f775aa595e9acecb1d90391e117e03e4b4c60317510aaef2c28394e3b2"
    document = "CIK0000078003.json"
    evidence = [
        {
            "company": "Pfizer",
            "cik": "78003",
            "metric_id": "B01",
            "source_url": source_url,
            "repo_relative_path": repo_path,
            "content_sha256": digest,
            "accession": accession,
            "document_name": document,
            "concept_or_section": "Revenues",
            "context_or_dimension": (
                "companyfacts:USD:CY2025:2025-01-01:2025-12-31"
            ),
            "unit": "USD",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "value_raw": "1000",
            "value_normalized": "1000",
            "evidence_quote": "Independent structured fixture.",
            "extraction_method": "companyfacts_direct",
            "parser_version": "sec_pipeline_v1",
        },
        {
            "company": "Pfizer",
            "cik": "78003",
            "metric_id": "B03",
            "source_url": ";".join([source_url] * 4),
            "repo_relative_path": ";".join([repo_path] * 4),
            "content_sha256": ";".join([digest] * 4),
            "accession": ";".join([accession] * 4),
            "document_name": ";".join([document] * 4),
            "concept_or_section": metrics[1]["concept_or_section"],
            "context_or_dimension": ";".join(
                ["companyfacts:USD:CY2025"] * 4
            ),
            "unit": "ratio",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "value_raw": "200;100;20;1000",
            "value_normalized": "0.12",
            "evidence_quote": "Independent derived fixture.",
            "extraction_method": "companyfacts_derived",
            "parser_version": "sec_pipeline_v1",
        },
    ]
    write_csv(
        path=legacy_dir / "metric_evidence.csv",
        fieldnames=EVIDENCE_FIELDS,
        rows=evidence,
    )
    write_csv(
        path=legacy_dir / "golden_results.csv",
        fieldnames=GOLDEN_FIELDS,
        rows=[
            {
                "assertion_id": "fixture_value",
                "description": "Structured fixture value",
                "expected": "1000",
                "actual": "1000",
                "status": "PASS",
                "evidence_path": "metrics_matrix.csv",
                "notes": "diff=0 tolerance=0",
            }
        ],
    )
    return legacy_dir


def write_request_ledger_rows(
    *, repo_root: Path, rows: list[dict[str, str]]
) -> None:
    """Persist one exact current-schema request ledger and manifest.

    Args:
        repo_root: Scoped repository containing the audit chain.
        rows: Complete ordered request observations.

    Expected output:
        CSV and manifest bytes describe the same exact ordered row set.
    """
    log_path = repo_root / "evidence" / "requests_log.csv"
    log_path.parent.mkdir(exist_ok=True)
    log_path.write_bytes(request_log_csv_bytes(rows=rows))
    manifest = request_log_manifest_payload(log_path=log_path)
    (log_path.parent / "requests_log_manifest.json").write_bytes(
        canonical_json_bytes(value=manifest) + b"\n"
    )


def request_ledger_fixture(
    *,
    repo_root: Path,
    row_changes: Optional[Mapping[str, str]] = None,
    working_locator: bool = False,
) -> str:
    """Write one real request row with exact body/header evidence.

    Args:
        repo_root: Scoped repository containing the Company Facts fixture.
        row_changes: Optional deliberate current-row mutations for negatives.
        working_locator: Whether the row truthfully names legacy working
            files instead of claiming the immutable attempt namespace.

    Returns:
        Deterministic attempt identity derived from the ordered ledger row.
    """
    relative = (
        "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
        "CIK0000078003.json"
    )
    source_url = (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000078003.json"
    )
    document_name = "CIK0000078003.json"
    content = (repo_root / relative).read_bytes()
    digest = sha256_bytes(content=content)
    body_relative = Path(
        "evidence", "request_attempts", digest[:2], digest, document_name,
    )
    body_path = repo_root / body_relative
    body_path.parent.mkdir(parents=True)
    body_path.write_bytes(content)
    headers_bytes = canonical_json_bytes(
        value={
            "url": source_url,
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "content_length": len(content),
            "sha256": digest,
            "saved_at_utc": "2026-08-03T00:00:00+00:00",
        }
    ) + b"\n"
    headers_relative = body_relative.with_name(
        "{}.{}.headers.json".format(
            document_name, sha256_bytes(content=headers_bytes),
        )
    )
    (repo_root / headers_relative).write_bytes(headers_bytes)
    if working_locator:
        working_root = Path("evidence", "legacy_working")
        body_relative = working_root / document_name
        headers_relative = working_root / (
            document_name + ".headers.json"
        )
        (repo_root / working_root).mkdir(parents=True)
        (repo_root / body_relative).write_bytes(content)
        (repo_root / headers_relative).write_bytes(headers_bytes)
    row = {
        "timestamp_utc": "2026-08-03T00:00:01+00:00",
        "method": "GET",
        "source_url": source_url,
        "status_code": "200",
        "purpose": "vnext_publication_fixture",
        "repo_relative_path": body_relative.as_posix(),
        "headers_repo_relative_path": headers_relative.as_posix(),
        "content_length": str(len(content)),
        "content_sha256": digest,
        "accession": "",
        "document_name": document_name,
        "user_agent": "SEC metrics fixture fixture@example.com",
        "retry_attempt": "0",
        "error": "",
    }
    if set(row) != set(REQUEST_LOG_FIELDNAMES):
        raise AssertionError("Request ledger fixture fields differ")
    if row_changes is not None:
        if not set(row_changes).issubset(set(row)):
            raise AssertionError("Request ledger mutation field is unknown")
        row.update(row_changes)
    write_request_ledger_rows(
        repo_root=repo_root, rows=[row],
    )
    return request_log_attempt_id(row_index=0, row=row)


def append_unrelated_request_ledger_row(*, repo_root: Path) -> None:
    """Append a valid row that the frozen publication Batch never consumed.

    Args:
        repo_root: Scoped repository containing the current ledger.

    Expected output:
        The full ledger grows while every Batch-consumed row remains unchanged.
    """
    log_path = repo_root / "evidence" / "requests_log.csv"
    rows = parse_request_log_rows(
        text=log_path.read_text(encoding="utf-8")
    )
    unrelated = dict(rows[-1])
    unrelated["timestamp_utc"] = "2026-08-03T00:00:02+00:00"
    unrelated["purpose"] = "unrelated_later_request"
    rows.append(unrelated)
    write_request_ledger_rows(repo_root=repo_root, rows=rows)


def complete_projection_fixture(
    *,
    workspace: Path,
    tag: str,
    request_ledger: bool = True,
    source_request_attempt_id: Optional[str] = None,
    request_ledger_row_changes: Optional[Mapping[str, str]] = None,
    request_ledger_working_locator: bool = False,
    accession: str = "0000078003-26-100099",
) -> Dict[str, object]:
    """Build a genuine one-company batch and complete semantic staging view.

    Args:
        workspace: Empty fixture workspace.
        tag: Stable Run identity suffix.
        request_ledger: Whether to persist the real request audit chain.
        source_request_attempt_id: Optional SourceReference attempt override.
        request_ledger_row_changes: Optional deliberate ledger row mutation.
        request_ledger_working_locator: Whether recorded evidence uses one
            exact historical working-file locator pair.
        accession: Exact structured-fact fixture observation to calculate.

    Returns:
        Repository, batch, legacy, and staging locators.
    """
    legacy_dir = legacy_snapshot(workspace=workspace)
    repo_root = scoped_repository(
        workspace=workspace, baseline_snapshot_dir=legacy_dir,
    )
    attempt_id = (
        request_ledger_fixture(
            repo_root=repo_root,
            row_changes=request_ledger_row_changes,
            working_locator=request_ledger_working_locator,
        )
        if request_ledger
        else "request:attempt:unavailable"
    )
    if source_request_attempt_id is not None:
        attempt_id = source_request_attempt_id
    batch_root = workspace / "batch"
    batch_root.mkdir()
    run_dir = batch_root / "run"
    create_full_release_run(
        run_dir=run_dir, run_id="run:publication:" + tag,
        repo_root=repo_root,
        request_attempt_id=attempt_id,
        accession=accession,
    )
    freeze_fixture(run_dir=run_dir, repo_root=repo_root)
    batch_path = batch_root / "batch_manifest.json"
    write_projection_batch_manifest(
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        run_dirs=[run_dir],
    )
    staging_dir = workspace / "staging"
    write_projection_candidate(
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        legacy_snapshot_dir=legacy_dir,
        staging_dir=staging_dir,
    )
    projection = build_projection_manifest(
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        legacy_snapshot_dir=legacy_dir,
        staging_dir=staging_dir,
    )
    write_json(
        path=staging_dir / "projection_manifest.json", value=projection,
    )
    return {
        "repo_root": repo_root,
        "batch_manifest_path": batch_path,
        "legacy_snapshot_dir": legacy_dir,
        "staging_dir": staging_dir,
    }


def self_signed_validation_receipt(
    *,
    files: Mapping[str, bytes],
    requirement_hashes: Mapping[str, str],
    batch_manifest_id: str,
    projection_manifest_id: str,
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> Dict[str, object]:
    """Build an adversarial caller-signed PASS receipt for negative tests.

    Args:
        files: Candidate bundle bytes excluding the receipt itself.
        requirement_hashes: Exact Requirement Snapshot identities.
        batch_manifest_id: Caller-asserted batch identity.
        projection_manifest_id: Caller-asserted projection identity.
        ledger_binding: Exact request-ledger prefix used by the candidate.
        previous_publication_id: Prepared predecessor identity.

    Returns:
        Strict non-self-referential ValidationReceipt.
    """
    body = {
        "status": "PASSED",
        "view_id": publication_validation_view_id(
            files=files,
            requirement_hashes=requirement_hashes,
            batch_manifest_id=batch_manifest_id,
            projection_manifest_id=projection_manifest_id,
            ledger_binding=ledger_binding,
            previous_publication_id=previous_publication_id,
        ),
        "checks": [
            {"check": check, "status": "PASS"}
            for check in PUBLICATION_CHECKS
        ],
        "artifact_hashes": {
            relative: {
                "sha256": sha256_bytes(content=files[relative]),
                "size": len(files[relative]),
            }
            for relative in sorted(files)
        },
    }
    record = dict(body)
    record.update(
        {
            "record_type": "VALIDATION_RECEIPT",
            "validation_receipt_id": content_hash(value=body),
        }
    )
    return validate_record(record=record)


def write_json(*, path: Path, value: Mapping[str, object]) -> None:
    """Persist deterministic JSON fixture bytes.

    Args:
        path: Destination file.
        value: JSON mapping.
    """
    path.write_bytes(canonical_json_bytes(value=value) + b"\n")


def staging_files(*, inputs: Mapping[str, object]) -> Dict[str, bytes]:
    """Read every non-self-referential staging artifact.

    Args:
        inputs: Public preparation kwargs.

    Returns:
        Exact bytes excluding the validation receipt.
    """
    staging_dir = inputs["staging_dir"]
    return {
        relative: (staging_dir / relative).read_bytes()
        for relative in REQUIRED_BUNDLE_FILES
        if relative != "publication_validation_receipt.json"
    }


def replace_receipt(
    *, inputs: Mapping[str, object], body: Mapping[str, object]
) -> None:
    """Replace a fixture receipt while keeping its identity consistent.

    Args:
        inputs: Preparation kwargs naming the staging directory.
        body: Receipt body without record type or identity.
    """
    receipt = dict(body)
    receipt.update(
        {
            "record_type": "VALIDATION_RECEIPT",
            "validation_receipt_id": content_hash(value=body),
        }
    )
    write_json(
        path=(
            inputs["staging_dir"]
            / "publication_validation_receipt.json"
        ),
        value=receipt,
    )


def resign_staging(*, inputs: Mapping[str, object]) -> None:
    """Self-sign staging bytes after an intentional adversarial mutation.

    Args:
        inputs: Preparation kwargs naming staging, ledger, and CAS state.
    """
    projection = json.loads(
        (
            inputs["staging_dir"] / "projection_manifest.json"
        ).read_text(encoding="utf-8")
    )
    receipt = self_signed_validation_receipt(
        files=staging_files(inputs=inputs),
        requirement_hashes=projection["requirement_hashes"],
        batch_manifest_id=projection["batch_manifest_id"],
        projection_manifest_id=projection["projection_manifest_id"],
        ledger_binding=publication_ledger_binding(
            repo_root=inputs["repo_root"],
            batch_manifest_path=inputs["batch_manifest_path"],
            validation_tier=RECORDED_VALIDATION_MODE,
        ),
        previous_publication_id=inputs["previous_publication_id"],
    )
    write_json(
        path=(
            inputs["staging_dir"]
            / "publication_validation_receipt.json"
        ),
        value=receipt,
    )


def replace_projection(
    *, inputs: Mapping[str, object], changes: Mapping[str, object]
) -> None:
    """Re-sign a ProjectionManifest after one deliberate semantic mutation.

    Args:
        inputs: Preparation kwargs naming the staging directory.
        changes: Top-level ProjectionManifest fields to replace.
    """
    path = inputs["staging_dir"] / "projection_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(changes)
    body = {
        key: manifest[key]
        for key in manifest
        if key not in {"projection_manifest_id", "schema_version"}
    }
    manifest["projection_manifest_id"] = content_hash(value=body)
    write_json(path=path, value=manifest)


def publication_inputs(
    *, root: Path, tag: str, previous_publication_id: Optional[str]
) -> Dict[str, object]:
    """Create real FROZEN Run and persisted staging preparation inputs.

    Args:
        root: Publication test root used to isolate fixture locators.
        tag: Distinguishing artifact tag.
        previous_publication_id: Prepared CAS predecessor.

    Returns:
        Keyword-compatible preparation input mapping.
    """
    workspace = root / ".fixture-{}".format(tag)
    workspace.mkdir()
    inputs = complete_projection_fixture(workspace=workspace, tag=tag)
    inputs.update(
        {
            "previous_publication_id": previous_publication_id,
        }
    )
    write_publication_validation_receipt(
        repo_root=inputs["repo_root"],
        batch_manifest_path=inputs["batch_manifest_path"],
        legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
        staging_dir=inputs["staging_dir"],
        previous_publication_id=inputs["previous_publication_id"],
        validated_at_utc="2026-07-31T00:00:00Z",
    )
    return inputs


def legacy_baseline_import_fixture(
    *, workspace: Path,
) -> Dict[str, object]:
    """Create one exact 14-artifact root with baseline-owned hashes.

    Args:
        workspace: Empty temporary parent for authority and root bytes.

    Returns:
        Repository authority, legacy root, and exact root artifact bytes.
    """
    authority_workspace = workspace / "legacy-authority"
    authority_workspace.mkdir()
    repo_root = scoped_repository(workspace=authority_workspace)
    legacy_root = workspace / "legacy-root"
    legacy_root.mkdir()
    artifact_bytes = {}
    artifact_digests = {}
    for relative in sorted(REQUIRED_BUNDLE_FILES):
        if relative in {
            "legacy_invariant_migration_receipt.json",
            "projection_manifest.json",
            "publication_validation_receipt.json",
        }:
            continue
        root_relative = ROOT_MIRROR_RELATIVE_PATHS[relative]
        content = "legacy-baseline:{}\n".format(relative).encode("utf-8")
        destination = legacy_root / root_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        artifact_bytes[relative] = content
        artifact_digests[root_relative] = {
            "sha256": sha256_bytes(content=content),
            "size": len(content),
        }
    provenance_relative = "outputs/validation_snapshot_provenance.json"
    provenance = b"legacy-baseline:validation-snapshot-provenance\n"
    provenance_path = legacy_root / provenance_relative
    provenance_path.write_bytes(provenance)
    artifact_digests[provenance_relative] = {
        "sha256": sha256_bytes(content=provenance),
        "size": len(provenance),
    }
    baseline_path = (
        repo_root
        / "requirements"
        / "ai_first_v3_3_1"
        / "baseline_manifest.json"
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["artifact_digests"] = artifact_digests
    write_json(path=baseline_path, value=baseline)
    return {
        "artifact_bytes": artifact_bytes,
        "legacy_root": legacy_root,
        "repo_root": repo_root,
    }


def mirror_paths(*, root: Path) -> Dict[str, Path]:
    """Map every required bundle file to one fixed-root compatibility mirror.

    Args:
        root: Mirror root.

    Returns:
        Exact mirror mapping.
    """
    return publication_layout(publication_root=root)["mirror_paths"]


def commit_formal_fixture(
    *, publication_root: Path, publication_id: str,
    expected_active_publication_id: Optional[str], committed_at_utc: str,
) -> Dict[str, object]:
    """Exercise commit mechanics with a recorded test bundle as formal.

    Args:
        publication_root: Isolated transaction-test root.
        publication_id: Prepared fixture bundle identity.
        expected_active_publication_id: Expected fixture CAS predecessor.
        committed_at_utc: Explicit fixture UTC timestamp.

    Returns:
        Pointer returned by the real public commit operation.

    Dedicated authority tests call ``commit_publication`` without this helper;
    transaction tests use it so their historical recorded fixture continues
    to isolate mirror, CAS, rollback, lock, and tamper behavior.
    """
    if threading.current_thread() is not threading.main_thread():
        raise AssertionError(
            "Formal fixture authority patch requires the main test thread"
        )
    with mock.patch(
        "vnext.publication._publication_commit_authority",
        return_value="FORMAL",
    ), mock.patch(
        "vnext.publication._require_existing_active_for_forward_commit",
    ):
        return publication_module._commit_publication(
            publication_root=publication_root,
            publication_id=publication_id,
            expected_active_publication_id=(
                expected_active_publication_id
            ),
            committed_at_utc=committed_at_utc,
        )


def record_fault(
    *, root: Path, scenario_id: str,
    prepared_publication_id: Optional[str],
    fault_point: str, before: Mapping[str, object],
    after: Mapping[str, object], outcome: str,
    temporary_workspace_cleaned: bool,
) -> Dict[str, object]:
    """Persist and return one exact fault-observation receipt.

    Args:
        root: Formal repository-layout root used by the scenario.
        scenario_id: Stable fault-matrix identity.
        prepared_publication_id: Candidate exercised by the fault.
        fault_point: Exact transaction checkpoint.
        before: Verified pointer and mirror state before the attempt.
        after: Verified pointer and mirror state after recovery.
        outcome: Stable scenario outcome.
        temporary_workspace_cleaned: Whether temporary bundle paths remain.

    Returns:
        Content-addressed persisted receipt.
    """
    return write_publication_fault_receipt(
        publication_root=root,
        scenario_id=scenario_id,
        prepared_publication_id=prepared_publication_id,
        fault_point=fault_point,
        before=before,
        after=after,
        outcome=outcome,
        temporary_workspace_cleaned=temporary_workspace_cleaned,
    )


def create_failed_run(*, run_dir: Path, run_id: str) -> None:
    """Persist one minimal hash-bound FAILED Run for latest-status tests.

    Args:
        run_dir: New Run directory.
        run_id: Stable Run identity, including adversarial identity reuse.
    """
    create_run(
        run_dir=run_dir,
        run_id=run_id,
        company_id="company_fixture",
        company_traits=["non_financial"],
        target_period={
            "fiscal_year": 2025,
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
        },
        source_references=[],
        missing_required_source_roles=[],
        spec_file_hashes={},
        requirement_hashes={},
    )
    write_validation_receipt(
        run_dir=run_dir,
        status="FAILED",
        checks=[{"check": "LATEST_FIXTURE", "status": "FAIL"}],
    )
    fail_run(run_dir=run_dir)


class PublicationTest(unittest.TestCase):
    """Prove only complete verified bundles become active."""

    def test_recorded_bundle_cannot_commit_through_private_orchestrator_primitive(
        self,
    ) -> None:
        """Keep PASSED_RECORDED_ONLY outside even the private mutation path."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="recorded-commit-authority",
                    previous_publication_id=None,
                ),
            )
            with self.assertRaisesRegex(
                PublicationError, "recorded-only",
            ):
                publication_module._commit_publication(
                    publication_root=root,
                    publication_id=str(manifest["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-08-06T11:00:00Z",
                )
            self.assertIsNone(
                publication_state_snapshot(
                    publication_root=root
                )["active_publication_id"]
            )

    def test_formal_bundle_cannot_bootstrap_without_legacy_chain(
        self,
    ) -> None:
        """Require the immutable legacy predecessor for first activation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="formal-bootstrap-authority",
                    previous_publication_id=None,
                ),
            )
            with mock.patch(
                "vnext.publication._publication_commit_authority",
                return_value="FORMAL",
            ), self.assertRaisesRegex(
                PublicationError, "initial publication chain",
            ):
                publication_module._commit_publication(
                    publication_root=root,
                    publication_id=str(manifest["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-08-06T11:00:30Z",
                )
            self.assertIsNone(
                publication_state_snapshot(
                    publication_root=root
                )["active_publication_id"]
            )

    def test_initial_chain_failure_restores_legacy_root_and_supports_rollback(
        self,
    ) -> None:
        """Import opaque legacy bytes and atomically activate first vNext."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            fixture = legacy_baseline_import_fixture(workspace=workspace)
            root = Path(fixture["legacy_root"])
            legacy = publication_module.prepare_legacy_baseline_predecessor(
                publication_root=root,
                repo_root=Path(fixture["repo_root"]),
                legacy_root=root,
            )
            successor = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="initial-vnext-successor",
                    previous_publication_id=str(legacy["publication_id"]),
                ),
            )
            legacy_id = str(legacy["publication_id"])
            successor_id = str(successor["publication_id"])

            def legacy_root_bytes() -> Dict[str, Optional[bytes]]:
                """Read present root bytes while preserving absent metadata."""
                result = {}
                for relative in REQUIRED_BUNDLE_FILES:
                    path = root / ROOT_MIRROR_RELATIVE_PATHS[relative]
                    result[relative] = (
                        path.read_bytes() if path.exists() else None
                    )
                return result

            original = legacy_root_bytes()
            with self.assertRaisesRegex(
                PublicationError, "legacy baseline",
            ):
                publication_module._commit_publication(
                    publication_root=root,
                    publication_id=legacy_id,
                    expected_active_publication_id=None,
                    committed_at_utc="2026-08-06T11:01:00Z",
                )

            mirror_checkpoints = []

            def fail_second_commit(*, fault_point: str) -> None:
                """Raise only after the predecessor mirror pass completes.

                Args:
                    fault_point: Real publication transaction checkpoint.
                """
                if fault_point != "MID_MIRROR_WRITE":
                    return
                mirror_checkpoints.append(fault_point)
                if len(mirror_checkpoints) == 2:
                    raise OSError("injected initial second-commit failure")

            def formal_fixture_authority(*, bundle_dir: Path) -> str:
                """Classify the recorded fixture as formal for mechanics.

                Args:
                    bundle_dir: Verified immutable bundle path.

                Returns:
                    Legacy authority for the import and formal for successor.
                """
                marker = bundle_dir / (
                    "internal/legacy_baseline_import.json"
                )
                return "LEGACY_BASELINE" if marker.is_file() else "FORMAL"

            with mock.patch(
                "vnext.publication._publication_commit_authority",
                side_effect=formal_fixture_authority,
            ), mock.patch(
                "vnext.publication._fault_injection_checkpoint",
                side_effect=fail_second_commit,
            ):
                with self.assertRaisesRegex(
                    PublicationError, "initial publication chain",
                ):
                    publication_module._commit_initial_publication_chain(
                        publication_root=root,
                        legacy_predecessor_publication_id=legacy_id,
                        successor_publication_id=successor_id,
                        committed_at_utc="2026-08-06T11:02:00Z",
                    )
            failed = publication_state_snapshot(publication_root=root)
            self.assertIsNone(failed["active_publication_id"])
            self.assertEqual(original, legacy_root_bytes())
            receipt_dir = (
                root / "outputs" / "publication_switch_receipts"
            )
            self.assertEqual([], list(receipt_dir.glob("*.json")))
            self.assertEqual(
                [],
                list(
                    (
                        root / "outputs/publication_switch_intents"
                    ).glob("*.json")
                ),
            )

            with mock.patch(
                "vnext.publication._publication_commit_authority",
                side_effect=formal_fixture_authority,
            ):
                chain = publication_module._commit_initial_publication_chain(
                    publication_root=root,
                    legacy_predecessor_publication_id=legacy_id,
                    successor_publication_id=successor_id,
                    committed_at_utc="2026-08-06T11:03:00Z",
                )
                self.assertEqual(
                    successor_id,
                    chain["active_pointer"]["publication_id"],
                )
                rollback_publication(
                    publication_root=root,
                    target_publication_id=legacy_id,
                    expected_active_publication_id=successor_id,
                    committed_at_utc="2026-08-06T11:04:00Z",
                )
                legacy_view = PublicationView.open(publication_root=root)
                self.assertEqual(legacy_id, legacy_view.publication_id)
                for relative in REQUIRED_BUNDLE_FILES:
                    content = legacy_view.read_bytes(
                        relative_path=relative
                    )
                    if original[relative] is None:
                        metadata = json.loads(content.decode("utf-8"))
                        self.assertEqual(
                            "LEGACY_BASELINE_IMPORT_ARTIFACT",
                            metadata["record_type"],
                        )
                        self.assertEqual(
                            "NOT_RUN_DATA_IMPORT_ONLY",
                            metadata["producer_execution"],
                        )
                    else:
                        self.assertEqual(original[relative], content)
                publication_module._commit_publication(
                    publication_root=root,
                    publication_id=successor_id,
                    expected_active_publication_id=legacy_id,
                    committed_at_utc="2026-08-06T11:05:00Z",
                )
            self.assertEqual(
                successor_id,
                PublicationView.open(
                    publication_root=root
                ).publication_id,
            )
            with mock.patch(
                "vnext.publication._publication_commit_authority",
                side_effect=formal_fixture_authority,
            ), self.assertRaisesRegex(
                PublicationError, "requires no active pointer",
            ):
                publication_module._commit_initial_publication_chain(
                    publication_root=root,
                    legacy_predecessor_publication_id=legacy_id,
                    successor_publication_id=successor_id,
                    committed_at_utc="2026-08-06T11:06:00Z",
                )

    def test_legacy_import_rejects_root_bytes_outside_frozen_baseline(
        self,
    ) -> None:
        """Reject a strict root artifact changed after baseline freezing."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            fixture = legacy_baseline_import_fixture(workspace=workspace)
            root = Path(fixture["legacy_root"])
            metrics = root / "outputs" / "metrics_matrix.csv"
            metrics.write_bytes(metrics.read_bytes() + b"post-freeze-change")
            with self.assertRaisesRegex(
                PublicationError, "baseline artifact bytes differ",
            ):
                publication_module.prepare_legacy_baseline_predecessor(
                    publication_root=root,
                    repo_root=Path(fixture["repo_root"]),
                    legacy_root=root,
                )

    def test_bundle_carries_portable_frozen_run_transitive_closure(
        self,
    ) -> None:
        """Verify the Run closure without its original source workspace."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="portable-transitive-closure",
                previous_publication_id=None,
            )
            manifest = prepare_publication_bundle(
                publication_root=root,
                **inputs,
            )
            bundle = (
                root
                / "outputs"
                / "publications"
                / str(manifest["publication_id"])
            )
            closure_path = bundle / "internal/closure_manifest.json"
            self.assertTrue(closure_path.is_file())
            closure = json.loads(
                closure_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["batch_manifest_id"],
                closure["batch_manifest_id"],
            )
            self.assertTrue(
                (bundle / str(closure["batch_manifest_path"])).is_file()
            )
            closure_files = {
                str(record["path"]) for record in closure["files"]
            }
            self.assertTrue(
                any(path.endswith("/manifest.json") for path in closure_files)
            )
            self.assertTrue(
                any(path.endswith("/records.jsonl") for path in closure_files)
            )
            self.assertTrue(
                any(
                    path.endswith("/review_decisions.jsonl")
                    for path in closure_files
                )
            )
            self.assertTrue(
                any(
                    path.endswith("/validation.json")
                    for path in closure_files
                )
            )
            self.assertTrue(
                any("/catalog/metrics/" in path for path in closure_files)
            )
            self.assertTrue(
                any(
                    path.endswith("/ISSUE_CONTRACT_R3_ADDENDUM.md")
                    for path in closure_files
                )
            )
            self.assertIn(
                "internal/authority/evidence/requests_log.csv",
                closure_files,
            )
            self.assertIn(
                "internal/authority/evidence/requests_log_manifest.json",
                closure_files,
            )

            # A committed bundle must remain independently reviewable after
            # the mutable build workspace and its original Run locators go.
            shutil.rmtree(root / ".fixture-portable-transitive-closure")
            self.assertEqual(
                manifest,
                verify_publication_bundle(bundle_dir=bundle),
            )

            tamper_targets = {
                "batch": str(closure["batch_manifest_path"]),
                "run_manifest": next(
                    path
                    for path in sorted(closure_files)
                    if path.endswith("/manifest.json")
                    and "/batch/" in path
                ),
                "decision_chain": next(
                    path
                    for path in sorted(closure_files)
                    if path.endswith("/review_decisions.jsonl")
                ),
                "trace_records": next(
                    path
                    for path in sorted(closure_files)
                    if path.endswith("/records.jsonl")
                ),
                "run_receipt": next(
                    path
                    for path in sorted(closure_files)
                    if path.endswith("/validation.json")
                ),
                "spec": next(
                    path
                    for path in sorted(closure_files)
                    if "/catalog/metrics/" in path
                ),
                "ledger_prefix": (
                    "internal/authority/evidence/requests_log.csv"
                ),
            }
            for label, relative in tamper_targets.items():
                with self.subTest(artifact=label):
                    path = bundle / relative
                    original = path.read_bytes()
                    path.write_bytes(original + b" ")
                    with self.assertRaisesRegex(
                        PublicationError, "artifact digest differs"
                    ):
                        verify_publication_bundle(bundle_dir=bundle)
                    path.write_bytes(original)

    def test_migration_ledger_must_match_inventory_at_prepare(self) -> None:
        """Reject a re-signed ledger that changes inventory entry order."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="migration-ledger-drift",
                previous_publication_id=None,
            )
            receipt_path = (
                inputs["staging_dir"]
                / "legacy_invariant_migration_receipt.json"
            )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["migration_entries"] = list(
                reversed(receipt["migration_entries"])
            )
            body = {
                key: receipt[key]
                for key in receipt
                if key not in {"receipt_id", "schema_version"}
            }
            receipt["receipt_id"] = content_hash(value=body)
            write_json(path=receipt_path, value=receipt)
            projection = json.loads(
                (
                    inputs["staging_dir"] / "projection_manifest.json"
                ).read_text(encoding="utf-8")
            )
            gate_hashes = dict(projection["gate_receipt_hashes"])
            gate_hashes[
                "legacy_invariant_migration_receipt.json"
            ] = sha256_file(path=receipt_path)
            replace_projection(
                inputs=inputs,
                changes={"gate_receipt_hashes": gate_hashes},
            )
            resign_staging(inputs=inputs)

            with self.assertRaisesRegex(
                PublicationError,
                "verified projection context|migration ledger differs",
            ):
                prepare_publication_bundle(
                    publication_root=root / "publication",
                    **inputs,
                )

    def test_migration_ledger_tamper_fails_bundle_readback(self) -> None:
        """Reject changed ledger bytes through immutable bundle read-back."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="migration-ledger-readback",
                previous_publication_id=None,
            )
            manifest = prepare_publication_bundle(
                publication_root=root / "publication",
                **inputs,
            )
            bundle = (
                root
                / "publication"
                / "outputs"
                / "publications"
                / str(manifest["publication_id"])
            )
            receipt_path = bundle / "legacy_invariant_migration_receipt.json"
            receipt_path.write_bytes(receipt_path.read_bytes() + b" ")

            with self.assertRaisesRegex(
                PublicationError, "artifact digest differs"
            ):
                verify_publication_bundle(bundle_dir=bundle)

    def test_missing_request_ledger_blocks_before_validation_receipt(
        self,
    ) -> None:
        """Do not issue publication PASS without the actual audit chain."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "candidate"
            workspace.mkdir()
            inputs = complete_projection_fixture(
                workspace=workspace,
                tag="missing-request-ledger",
                request_ledger=False,
            )

            with self.assertRaisesRegex(
                PublicationError, "request ledger"
            ):
                write_publication_validation_receipt(
                    repo_root=inputs["repo_root"],
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                    previous_publication_id=None,
                    validated_at_utc="2026-08-03T00:00:00Z",
                )
            self.assertFalse(
                (
                    inputs["staging_dir"]
                    / "publication_validation_receipt.json"
                ).exists()
            )

    def test_publication_entrypoints_do_not_accept_ledger_authority(
        self,
    ) -> None:
        """Keep request-ledger facts derived inside publication entrypoints."""
        self.assertEqual(
            {
                "batch_manifest_path",
                "legacy_snapshot_dir",
                "previous_publication_id",
                "repo_root",
                "staging_dir",
                "validated_at_utc",
            },
            set(
                inspect.signature(
                    write_publication_validation_receipt
                ).parameters
            ),
        )
        self.assertEqual(
            {
                "batch_manifest_path",
                "legacy_snapshot_dir",
                "previous_publication_id",
                "publication_root",
                "repo_root",
                "staging_dir",
            },
            set(inspect.signature(prepare_publication_bundle).parameters),
        )

    def test_batch_source_absent_from_request_ledger_cannot_validate(
        self,
    ) -> None:
        """Reject a batch whose consumed source names no real ledger row."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            inputs = complete_projection_fixture(
                workspace=workspace,
                tag="unknown-request-attempt",
                source_request_attempt_id=(
                    "request:attempt:" + "f" * 64
                ),
            )

            with self.assertRaisesRegex(
                PublicationError, "request ledger attempt is absent"
            ):
                write_publication_validation_receipt(
                    repo_root=inputs["repo_root"],
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                    previous_publication_id=None,
                    validated_at_utc="2026-08-03T00:00:00Z",
                )

    def test_unrelated_ledger_tail_preserves_used_publication_prefix(
        self,
    ) -> None:
        """Do not bind later requests that this Batch never consumed."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="unrelated-ledger-tail",
                previous_publication_id=None,
            )
            before = publication_ledger_binding(
                repo_root=inputs["repo_root"],
                batch_manifest_path=inputs["batch_manifest_path"],
            )
            append_unrelated_request_ledger_row(
                repo_root=inputs["repo_root"],
            )
            after = publication_ledger_binding(
                repo_root=inputs["repo_root"],
                batch_manifest_path=inputs["batch_manifest_path"],
            )

            self.assertEqual(before, after)
            prepare_publication_bundle(
                publication_root=root / "publication", **inputs,
            )

    def test_declared_request_ledger_locators_must_identify_attempt(
        self,
    ) -> None:
        """Reject a row that points away from its immutable body/header."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            inputs = complete_projection_fixture(
                workspace=workspace,
                tag="wrong-request-locators",
                request_ledger_row_changes={
                    "repo_relative_path": (
                        "evidence/never-existed-body.json"
                    ),
                    "headers_repo_relative_path": (
                        "evidence/never-existed-headers.json"
                    ),
                },
            )

            with self.assertRaisesRegex(PublicationError, "locator"):
                write_publication_validation_receipt(
                    repo_root=inputs["repo_root"],
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                    previous_publication_id=None,
                    validated_at_utc="2026-08-03T00:00:00Z",
                )

    def test_recorded_legacy_locator_is_portable_but_formal_rejects(
        self,
    ) -> None:
        """Close exact working bytes offline without weakening live policy."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = complete_projection_fixture(
                workspace=root,
                tag="recorded-legacy-locator",
                request_ledger_working_locator=True,
            )
            recorded = publication_ledger_binding(
                repo_root=inputs["repo_root"],
                batch_manifest_path=inputs["batch_manifest_path"],
                validation_tier=RECORDED_VALIDATION_MODE,
            )
            self.assertEqual(
                ["LEGACY_WORKING_LOCATOR"],
                recorded["request_locator_classes"],
            )
            self.assertEqual(
                RECORDED_VALIDATION_MODE,
                recorded["request_locator_tier"],
            )
            with self.assertRaisesRegex(
                PublicationError, "LIVE_SOURCE_ATTEMPT_INCOMPLETE"
            ):
                publication_ledger_binding(
                    repo_root=inputs["repo_root"],
                    batch_manifest_path=inputs["batch_manifest_path"],
                )

            write_publication_validation_receipt(
                repo_root=inputs["repo_root"],
                batch_manifest_path=inputs["batch_manifest_path"],
                legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                staging_dir=inputs["staging_dir"],
                previous_publication_id=None,
                validated_at_utc="2026-08-06T17:05:09Z",
            )
            publication_root = root / "publication"
            manifest = prepare_publication_bundle(
                publication_root=publication_root,
                previous_publication_id=None,
                **inputs,
            )
            bundle_dir = (
                publication_root
                / "outputs/publications"
                / str(manifest["publication_id"])
            )
            locator_proof = strict_json_file(
                path=(
                    bundle_dir
                    / "internal/request_locator_provenance.json"
                )
            )
            self.assertEqual(
                recorded["request_locator_proof_id"],
                locator_proof["request_locator_proof_id"],
            )
            self.assertEqual(
                "LEGACY_WORKING_LOCATOR",
                locator_proof["source_proofs"][0]["locator_class"],
            )
            for field in (
                "body_sha256",
                "body_size",
                "headers_sha256",
                "headers_size",
                "original_body_locator",
                "original_headers_locator",
            ):
                self.assertTrue(locator_proof["source_proofs"][0][field])

            # Portable verification may not fall back to the mutable checkout.
            source_proof = locator_proof["source_proofs"][0]
            for locator in (
                source_proof["original_body_locator"],
                source_proof["original_headers_locator"],
            ):
                (inputs["repo_root"] / str(locator)).unlink()
            verified = verify_publication_bundle(bundle_dir=bundle_dir)
            self.assertEqual(
                manifest["publication_id"], verified["publication_id"],
            )

    def test_complete_batch_projects_publishes_and_reads_active_view(
        self,
    ) -> None:
        """Publish one complete batch and read exact projected N/A rows."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="complete-e2e",
                previous_publication_id=None,
            )
            expected_metrics = (
                inputs["staging_dir"] / "metrics_matrix.csv"
            ).read_bytes()

            manifest = prepare_publication_bundle(
                publication_root=root / "publication", **inputs,
            )
            expected_ledger = publication_ledger_binding(
                repo_root=inputs["repo_root"],
                batch_manifest_path=inputs["batch_manifest_path"],
                validation_tier=RECORDED_VALIDATION_MODE,
            )
            self.assertEqual(expected_ledger, manifest["ledger_binding"])
            self.assertEqual(
                1, len(expected_ledger["source_reference_ids"]),
            )
            self.assertEqual(
                1, len(expected_ledger["used_request_attempt_ids"]),
            )
            commit_formal_fixture(
                publication_root=root / "publication",
                publication_id=str(manifest["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-31T00:00:00Z",
            )
            view = PublicationView.open(
                publication_root=root / "publication",
            )
            active_metrics = view.read_bytes(
                relative_path="metrics_matrix.csv",
            )
            rows = list(
                csv.DictReader(
                    active_metrics.decode("utf-8").splitlines()
                )
            )
            compatibility = json.loads(
                view.read_bytes(
                    relative_path=(
                        "legacy_invariant_migration_receipt.json"
                    ),
                ).decode("utf-8")
            )
            active_evidence = list(
                csv.DictReader(
                    view.read_bytes(
                        relative_path="metric_evidence.csv",
                    ).decode("utf-8").splitlines()
                )
            )
            stratified = list(
                csv.DictReader(
                    view.read_bytes(
                        relative_path="stratified_audit.csv",
                    ).decode("utf-8").splitlines()
                )
            )
            method_cells = [
                cell
                for receipt in compatibility["evidence_reconciliations"]
                for cell in receipt["method_cells"]
            ]

            self.assertEqual(expected_metrics, active_metrics)
            self.assertEqual(
                {"B01", "B03", "B10", "B11"},
                {row["metric_id"] for row in rows},
            )
            self.assertEqual(
                {"B10": "N_A_STRUCTURAL", "B11": "N_A_STRUCTURAL"},
                {
                    row["metric_id"]: row["status"]
                    for row in rows
                    if row["metric_id"] in {"B10", "B11"}
                },
            )
            self.assertEqual(
                {"evidence_quote", "extraction_method", "parser_version"},
                {cell["field"] for cell in method_cells},
            )
            self.assertTrue(
                all(cell["status"] == "RECORDED" for cell in method_cells)
            )
            b03_evidence = [
                row for row in active_evidence if row["metric_id"] == "B03"
            ]
            b03_audit = next(
                row for row in stratified if row["metric_id"] == "B03"
            )
            self.assertEqual(
                ";".join(row["value_normalized"] for row in b03_evidence),
                b03_audit["evidence_value"],
            )
            layout = publication_layout(
                publication_root=root / "publication"
            )
            for relative, mirror in layout["mirror_paths"].items():
                with self.subTest(root_mirror=relative):
                    self.assertEqual(
                        view.read_bytes(relative_path=relative),
                        mirror.read_bytes(),
                    )

    def test_candidate_row_mutations_cannot_prepare(self) -> None:
        """Reject deleted, added, or Run-inconsistent migrated rows."""
        for mutation in ("delete", "add", "value"):
            with self.subTest(
                mutation=mutation
            ), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                inputs = publication_inputs(
                    root=root,
                    tag="row-mutation-" + mutation,
                    previous_publication_id=None,
                )
                path = inputs["staging_dir"] / "metrics_matrix.csv"
                rows = read_csv(path=path)
                if mutation == "delete":
                    rows.pop()
                elif mutation == "add":
                    rows.append({**rows[0], "company": "Unregistered"})
                else:
                    rows[0]["value"] = "999"
                write_csv(path=path, fieldnames=METRIC_FIELDS, rows=rows)
                resign_staging(inputs=inputs)

                with self.assertRaises(PublicationError):
                    prepare_publication_bundle(
                        publication_root=root / "publication", **inputs,
                    )

    def test_malformed_nested_projection_fails_at_publication_boundary(
        self,
    ) -> None:
        """Convert adversarial nested JSON into a PublicationError."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="nested-projection",
                previous_publication_id=None,
            )
            replace_projection(
                inputs=inputs,
                changes={
                    "expected_result_keys": [
                        {
                            "applicability": "APPLICABLE",
                            "company_id": [],
                            "metric_id": "B01",
                        }
                    ],
                },
            )
            resign_staging(inputs=inputs)

            with self.assertRaises(PublicationError):
                prepare_publication_bundle(
                    publication_root=root / "publication", **inputs,
                )

    def test_malformed_gate_execution_record_fails_closed(self) -> None:
        """Reject nested validation types before hashing gate evidence."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="nested-gate",
                previous_publication_id=None,
            )
            path = (
                inputs["staging_dir"] / "validation_run_manifest.json"
            )
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["refreshed_artifacts"] = [[]]
            write_json(path=path, value=manifest)
            (
                inputs["staging_dir"]
                / "publication_validation_receipt.json"
            ).unlink()

            with self.assertRaises(PublicationError):
                write_publication_validation_receipt(
                    repo_root=inputs["repo_root"],
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                    previous_publication_id=(
                        inputs["previous_publication_id"]
                    ),
                    validated_at_utc="2026-07-31T00:00:00Z",
                )

    def test_legacy_snapshot_outside_frozen_baseline_cannot_project(
        self,
    ) -> None:
        """Reject even schema-valid non-migrated rows absent from baseline."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "fixture"
            workspace.mkdir()
            inputs = complete_projection_fixture(
                workspace=workspace, tag="missing-evidence",
            )
            legacy_path = (
                inputs["legacy_snapshot_dir"] / "metrics_matrix.csv"
            )
            legacy_rows = read_csv(path=legacy_path)
            legacy_rows.append(
                {
                    **legacy_rows[0],
                    "metric_id": "B99",
                    "metric_name": "Unmigrated numeric fixture",
                }
            )
            write_csv(
                path=legacy_path,
                fieldnames=METRIC_FIELDS,
                rows=legacy_rows,
            )
            with self.assertRaisesRegex(ProjectionError, "baseline"):
                write_projection_candidate(
                    repo_root=inputs["repo_root"],
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                )

    def test_baseline_boolean_row_count_cannot_project(self) -> None:
        """Reject bool-as-int metadata in the frozen baseline authority."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            legacy_dir = legacy_snapshot(workspace=workspace)
            repo_root = scoped_repository(
                workspace=workspace,
                baseline_snapshot_dir=legacy_dir,
            )
            baseline_path = (
                repo_root
                / "requirements"
                / "ai_first_v3_3_1"
                / "baseline_manifest.json"
            )
            baseline = json.loads(
                baseline_path.read_text(encoding="utf-8")
            )
            baseline["artifact_digests"][
                "outputs/golden_results.csv"
            ]["row_count"] = True
            write_json(path=baseline_path, value=baseline)
            batch_root = workspace / "batch"
            batch_root.mkdir()
            run_dir = batch_root / "run"
            create_full_release_run(
                run_dir=run_dir,
                run_id="run:publication:bool-baseline",
                repo_root=repo_root,
            )
            freeze_fixture(run_dir=run_dir, repo_root=repo_root)
            batch_path = batch_root / "batch_manifest.json"
            write_projection_batch_manifest(
                repo_root=repo_root,
                batch_manifest_path=batch_path,
                run_dirs=[run_dir],
            )

            with self.assertRaisesRegex(ProjectionError, "schema"):
                write_projection_candidate(
                    repo_root=repo_root,
                    batch_manifest_path=batch_path,
                    legacy_snapshot_dir=legacy_dir,
                    staging_dir=workspace / "staging",
                )

    def test_self_signed_pass_without_gate_execution_cannot_prepare(
        self,
    ) -> None:
        """Reject a valid candidate whose PASS labels lack execution proof."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="self-signed-pass",
                previous_publication_id=None,
            )
            resign_staging(inputs=inputs)

            with self.assertRaisesRegex(
                PublicationError, "gate execution"
            ):
                prepare_publication_bundle(
                    publication_root=root / "publication",
                    **inputs,
                )

    def test_caller_authored_pass_gate_cannot_prepare(self) -> None:
        """Reject a self-consistent PASS row not emitted by Projector."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="caller-gate",
                previous_publication_id=None,
            )
            repair_path = (
                inputs["staging_dir"] / "repair_validation_results.csv"
            )
            write_csv(
                path=repair_path,
                fieldnames=REPAIR_FIELDS,
                rows=[
                    {
                        "check_id": "caller_says_ok",
                        "severity": "P0",
                        "status": "PASS",
                        "details": "not an executed repository check",
                    }
                ],
            )
            projection = json.loads(
                (
                    inputs["staging_dir"] / "projection_manifest.json"
                ).read_text(encoding="utf-8")
            )
            gate_hashes = dict(projection["gate_receipt_hashes"])
            gate_hashes["repair_validation_results.csv"] = sha256_file(
                path=repair_path,
            )
            replace_projection(
                inputs=inputs, changes={"gate_receipt_hashes": gate_hashes},
            )
            resign_staging(inputs=inputs)

            with self.assertRaisesRegex(
                PublicationError, "verified projection context"
            ):
                prepare_publication_bundle(
                    publication_root=root / "publication",
                    **inputs,
                )

    def test_caller_authored_report_cannot_prepare(self) -> None:
        """Reject a self-signed report not rendered from candidate rows."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="caller-report",
                previous_publication_id=None,
            )
            (
                inputs["staging_dir"] / "REPORT_十公司财务指标.md"
            ).write_text("caller-authored PASS\n", encoding="utf-8")
            resign_staging(inputs=inputs)

            with self.assertRaisesRegex(PublicationError, "document"):
                prepare_publication_bundle(
                    publication_root=root / "publication",
                    **inputs,
                )

    def test_scalability_gate_executes_real_scanner(self) -> None:
        """Reject a company branch added after the candidate gate ran."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="real-scalability-gate",
                previous_publication_id=None,
            )
            bad_path = (
                inputs["repo_root"]
                / "scripts"
                / "forged_company_branch.py"
            )
            bad_path.write_text(
                '"""Adversarial production branch."""\n'
                'TARGET_COMPANY = "Pfizer"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PublicationError, "Scalability audit execution"
            ):
                prepare_publication_bundle(
                    publication_root=root / "publication", **inputs,
                )

    def test_scalability_gate_scans_vnext_sources(self) -> None:
        """Reject a registry ticker branch inside vNext production code."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="recursive-scalability-gate",
                previous_publication_id=None,
            )
            (
                inputs["staging_dir"]
                / "publication_validation_receipt.json"
            ).unlink()
            (
                inputs["staging_dir"] / "semantic_audit_receipt.json"
            ).unlink()
            bad_path = (
                inputs["repo_root"]
                / "scripts"
                / "vnext"
                / "forged_company_branch.py"
            )
            bad_path.write_text(
                '"""Adversarial vNext production branch."""\n'
                'TARGET_TICKER = "PFE"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PublicationError, "Scalability audit execution"
            ):
                write_publication_validation_receipt(
                    repo_root=inputs["repo_root"],
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                    previous_publication_id=(
                        inputs["previous_publication_id"]
                    ),
                    validated_at_utc="2026-07-31T00:00:00Z",
                )

    def test_semantic_gate_binds_checker_bytes(self) -> None:
        """Reject a checker replaced by a replay of its prior PASS bytes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="semantic-checker-binding",
                previous_publication_id=None,
            )
            staged_receipt = (
                inputs["staging_dir"] / "semantic_audit_receipt.json"
            ).read_bytes()
            checker = (
                inputs["repo_root"]
                / "tools"
                / "check_vnext_semantics.py"
            )
            checker.write_text(
                '"""Replay a previously valid receipt."""\n'
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                'parser.add_argument("--repo-root")\n'
                'parser.add_argument("--output")\n'
                "arguments = parser.parse_args()\n"
                "Path(arguments.output).write_bytes({!r})\n".format(
                    staged_receipt
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PublicationError, "Semantic audit source binding"
            ):
                prepare_publication_bundle(
                    publication_root=root / "publication", **inputs,
                )

    def test_arbitrary_staging_and_self_signed_pass_cannot_prepare(
        self,
    ) -> None:
        """Reject syntactically bound bytes without projection semantics."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="self-signed-garbage",
                previous_publication_id=None,
            )
            for relative in REQUIRED_BUNDLE_FILES - {
                "projection_manifest.json",
                "publication_validation_receipt.json",
            }:
                (inputs["staging_dir"] / relative).write_bytes(
                    "review-garbage:{}\n".format(relative).encode("utf-8")
                )
            resign_staging(inputs=inputs)

            with self.assertRaisesRegex(
                PublicationError,
                "projection|gate|CSV|semantic|Validation manifest",
            ):
                prepare_publication_bundle(
                    publication_root=root / "publication",
                    **inputs,
                )

    def test_withheld_or_incomplete_bundle_cannot_prepare(self) -> None:
        """Block publication on applicable WITHHELD or missing files."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="blocked",
                previous_publication_id=None,
            )
            replace_projection(
                inputs=inputs,
                changes={"publication_candidate_status": "BLOCKED"},
            )
            resign_staging(inputs=inputs)
            with self.assertRaisesRegex(
                PublicationError, "BLOCKED|ProjectionManifest"
            ):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )
            inputs = publication_inputs(
                root=root, tag="missing", previous_publication_id=None,
            )
            (
                inputs["staging_dir"] / "REPORT_十公司财务指标.md"
            ).unlink()
            with self.assertRaisesRegex(PublicationError, "exact set"):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )

    def test_real_withheld_candidate_preserves_previous_active(self) -> None:
        """Block a replayable 1.01% B03 failure before bundle preparation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="withheld-active",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            workspace = root / ".fixture-withheld-real"
            workspace.mkdir()
            before = publication_state_snapshot(publication_root=root)

            with self.assertRaisesRegex(
                ProjectionError, "quality has no legacy status mapping"
            ):
                complete_projection_fixture(
                    workspace=workspace,
                    tag="withheld-real",
                    accession="0000078003-26-100101",
                )

            after = publication_state_snapshot(publication_root=root)
            receipt = record_fault(
                root=root,
                scenario_id="WITHHELD_CANDIDATE",
                prepared_publication_id=None,
                fault_point="PREPARE_VALIDATION_GATE",
                before=before,
                after=after,
                outcome="WITHHELD_BLOCKED",
                temporary_workspace_cleaned=True,
            )
            self.assertEqual(before, after)
            self.assertEqual("WITHHELD_BLOCKED", receipt["outcome"])
            self.assertFalse(
                any(workspace.rglob("publication_validation_receipt.json"))
            )

    def test_projection_cannot_forge_run_or_release_identity(self) -> None:
        """Bind staged Result IDs and release bytes to the verified Run."""
        mutations = (
            {"result_ids": ["sha256:" + "f" * 64]},
            {"release_plan_sha256": "e" * 64},
        )
        for index, changes in enumerate(mutations):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory(
            ) as directory:
                root = Path(directory)
                inputs = publication_inputs(
                    root=root,
                    tag="forged-projection-{}".format(index),
                    previous_publication_id=None,
                )
                replace_projection(inputs=inputs, changes=changes)
                resign_staging(inputs=inputs)

                with self.assertRaisesRegex(
                    PublicationError, "Projection|projection|Result|release"
                ):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )

    def test_symlinked_publication_storage_cannot_escape_root(self) -> None:
        """Reject a publications directory redirected outside its root."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "publication"
            external = workspace / "external-publications"
            root.mkdir()
            external.mkdir()
            inputs = publication_inputs(
                root=root,
                tag="storage-symlink",
                previous_publication_id=None,
            )
            outputs = root / "outputs"
            outputs.mkdir()
            (outputs / "publications").symlink_to(
                external, target_is_directory=True,
            )

            with self.assertRaisesRegex(
                PublicationError, "storage must be a real directory"
            ):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )

    def test_symlinked_artifacts_parent_cannot_escape_root(self) -> None:
        """Reject latest-status storage redirected through its parent."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "publication"
            external = workspace / "external-artifacts"
            root.mkdir()
            external.mkdir()
            (root / "artifacts").symlink_to(
                external, target_is_directory=True,
            )

            with self.assertRaisesRegex(
                PublicationError, "artifacts must be a real directory"
            ):
                publication_layout(publication_root=root)

    def test_invalid_request_ledger_manifest_cannot_prepare(self) -> None:
        """Reject malformed persisted row counts and content digests."""
        invalid_values = (
            ("row_count", True),
            ("content_sha256", "not-a-digest"),
        )
        for field, value in invalid_values:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                inputs = publication_inputs(
                    root=root,
                    tag="invalid-ledger-" + field,
                    previous_publication_id=None,
                )
                manifest_path = (
                    inputs["repo_root"]
                    / "evidence"
                    / "requests_log_manifest.json"
                )
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
                manifest[field] = value
                write_json(path=manifest_path, value=manifest)
                with self.assertRaisesRegex(
                    PublicationError, "request ledger"
                ):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )

    def test_missing_immutable_request_headers_cannot_prepare(self) -> None:
        """Require the consumed ledger row's immutable header sidecar."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="missing-request-headers",
                previous_publication_id=None,
            )
            row = read_csv(
                path=(
                    inputs["repo_root"] / "evidence" / "requests_log.csv"
                )
            )[0]
            (
                inputs["repo_root"]
                / row["headers_repo_relative_path"]
            ).unlink()

            with self.assertRaisesRegex(
                PublicationError, "immutable attempt is invalid"
            ):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )

    def test_latest_failed_attempt_is_visible_without_moving_active(
        self,
    ) -> None:
        """Keep a failed latest Run distinct from the usable active bundle."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-visible-active",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            path = (
                root / "artifacts" / "vnext" / "latest_run_status.json"
            )
            failed_run = root / "failed-run"
            create_failed_run(
                run_dir=failed_run, run_id="run:failed:fixture",
            )
            status = write_latest_run_status(
                repo_root=REPO_ROOT,
                latest_run_dir=failed_run,
                latest_publication_id=None,
                message="Latest attempt failed; active is unchanged.",
                updated_at_utc="2026-07-29T13:00:00Z",
                publication_root=root,
            )
            self.assertEqual("FAILED", status["latest_run_status"])
            self.assertEqual(
                "NOT_EVALUATED", status["publication_candidate_status"],
            )
            self.assertEqual(
                status, json.loads(path.read_text(encoding="utf-8")),
            )

    def test_bundled_validation_receipt_must_match_candidate_view(
        self,
    ) -> None:
        """Reject a PASS record paired with different bundled bytes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root, tag="receipt", previous_publication_id=None
            )
            (
                inputs["staging_dir"]
                / "publication_validation_receipt.json"
            ).write_bytes(b"{}\n")
            with self.assertRaisesRegex(
                PublicationError, "validation receipt"
            ):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )

    def test_nonpassed_validation_receipt_cannot_prepare(self) -> None:
        """Keep FAILED and NOT_RUN audit Runs outside publication staging."""
        for status in ("FAILED", "NOT_RUN"):
            with self.subTest(status=status), tempfile.TemporaryDirectory(
            ) as directory:
                root = Path(directory)
                inputs = publication_inputs(
                    root=root,
                    tag="validation-{}".format(status.lower()),
                    previous_publication_id=None,
                )
                receipt = json.loads(
                    (
                        inputs["staging_dir"]
                        / "publication_validation_receipt.json"
                    ).read_text(encoding="utf-8")
                )
                body = {
                    key: receipt[key]
                    for key in (
                        "status",
                        "view_id",
                        "checks",
                        "artifact_hashes",
                    )
                }
                body["status"] = status
                if status == "FAILED":
                    body["checks"][0] = {
                        "check": body["checks"][0]["check"],
                        "status": "FAIL",
                    }
                else:
                    body["checks"] = []
                    body["artifact_hashes"] = {}
                replace_receipt(inputs=inputs, body=body)
                with self.assertRaisesRegex(
                    PublicationError, "validation is not PASSED"
                ):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )

    def test_receipt_binds_exact_artifacts_checks_and_view(self) -> None:
        """Reject every receipt that did not validate this exact view."""
        mutations = (
            "hash",
            "size",
            "missing",
            "extra",
            "failed_check",
            "missing_check",
            "old_view",
            "requirement_hash",
            "run_binding",
            "ledger_binding",
            "predecessor",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
            ) as directory:
                root = Path(directory)
                pointer = root / "outputs" / "active_publication.json"
                mirrors = mirror_paths(root=root)
                active = prepare_publication_bundle(
                    publication_root=root,
                    **publication_inputs(
                        root=root,
                        tag="active-" + mutation,
                        previous_publication_id=None,
                    ),
                )
                commit_formal_fixture(
                    publication_root=root,
                    publication_id=str(active["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-07-29T13:00:00Z",
                )
                pointer_before = pointer.read_bytes()
                mirrors_before = {
                    relative: mirrors[relative].read_bytes()
                    for relative in mirrors
                }
                inputs = publication_inputs(
                    root=root,
                    tag="receipt-" + mutation,
                    previous_publication_id=str(active["publication_id"]),
                )
                receipt = json.loads(
                    (
                        inputs["staging_dir"]
                        / "publication_validation_receipt.json"
                    ).read_text(encoding="utf-8")
                )
                body = {
                    key: receipt[key]
                    for key in (
                        "status",
                        "view_id",
                        "checks",
                        "artifact_hashes",
                    )
                }
                if mutation == "hash":
                    body["artifact_hashes"]["metrics_matrix.csv"][
                        "sha256"
                    ] = "0" * 64
                elif mutation == "size":
                    body["artifact_hashes"]["metrics_matrix.csv"]["size"] += 1
                elif mutation == "missing":
                    del body["artifact_hashes"]["metrics_matrix.csv"]
                elif mutation == "extra":
                    body["artifact_hashes"]["extra.csv"] = {
                        "sha256": "0" * 64,
                        "size": 0,
                    }
                elif mutation == "failed_check":
                    body["checks"][0]["status"] = "FAIL"
                elif mutation == "missing_check":
                    body["checks"] = body["checks"][1:]
                elif mutation == "old_view":
                    body["view_id"] = "staging:sha256:" + "0" * 64
                elif mutation == "requirement_hash":
                    projection = json.loads(
                        (
                            inputs["staging_dir"]
                            / "projection_manifest.json"
                        ).read_text(encoding="utf-8")
                    )
                    requirement_hashes = dict(
                        projection["requirement_hashes"]
                    )
                    requirement_hashes["baseline_sha256"] = "f" * 64
                    replace_projection(
                        inputs=inputs,
                        changes={
                            "requirement_hashes": requirement_hashes,
                        },
                    )
                    resign_staging(inputs=inputs)
                elif mutation == "run_binding":
                    projection = json.loads(
                        (
                            inputs["staging_dir"]
                            / "projection_manifest.json"
                        ).read_text(encoding="utf-8")
                    )
                    run_bindings = list(projection["run_bindings"])
                    run_bindings[0] = dict(run_bindings[0])
                    run_bindings[0]["audit_manifest_hash"] = (
                        "sha256:" + "e" * 64
                    )
                    replace_projection(
                        inputs=inputs,
                        changes={"run_bindings": run_bindings},
                    )
                    resign_staging(inputs=inputs)
                elif mutation == "ledger_binding":
                    log_path = (
                        inputs["repo_root"]
                        / "evidence"
                        / "requests_log.csv"
                    )
                    ledger_rows = parse_request_log_rows(
                        text=log_path.read_text(encoding="utf-8")
                    )
                    ledger_rows[0]["purpose"] = "tampered_used_request"
                    write_request_ledger_rows(
                        repo_root=inputs["repo_root"],
                        rows=ledger_rows,
                    )
                elif mutation == "predecessor":
                    inputs["previous_publication_id"] = (
                        "publication_" + "d" * 64
                    )
                if mutation not in {
                    "requirement_hash",
                    "run_binding",
                    "ledger_binding",
                    "predecessor",
                }:
                    replace_receipt(inputs=inputs, body=body)
                with self.assertRaises(PublicationError):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )
                self.assertEqual(pointer_before, pointer.read_bytes())
                self.assertEqual(
                    mirrors_before,
                    {
                        relative: mirrors[relative].read_bytes()
                        for relative in mirrors
                    },
                )

    def test_active_run_cannot_be_rebranded_failed_in_latest_status(
        self,
    ) -> None:
        """Reject one Run identity claiming active success and FAILED state."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="latest-conflict",
                previous_publication_id=None,
            )
            active = prepare_publication_bundle(
                publication_root=root,
                **inputs,
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            failed_run = root / "failed-run"
            batch = json.loads(
                inputs["batch_manifest_path"].read_text(encoding="utf-8")
            )
            create_failed_run(
                run_dir=failed_run,
                run_id=str(batch["runs"][0]["run_id"]),
            )
            with self.assertRaisesRegex(PublicationError, "conflicts"):
                write_latest_run_status(
                    repo_root=REPO_ROOT,
                    latest_run_dir=failed_run,
                    latest_publication_id=None,
                    message="Latest attempt failed.",
                    updated_at_utc="2026-07-29T13:01:00Z",
                    publication_root=root,
                )

    def test_latest_success_binds_corresponding_publication(self) -> None:
        """Derive latest-success from the latest and active bundle IDs."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-identity-active",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            latest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-identity-candidate",
                    previous_publication_id=str(active["publication_id"]),
                ),
            )
            status = write_latest_run_status(
                repo_root=REPO_ROOT,
                latest_run_dir=None,
                latest_publication_id=str(latest["publication_id"]),
                message="Latest candidate has not become active.",
                updated_at_utc="2026-07-29T13:00:00Z",
                publication_root=root,
            )
            self.assertFalse(status["active_is_latest_success"])
            self.assertEqual(
                active["publication_id"], status["active_publication_id"],
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(latest["publication_id"]),
                expected_active_publication_id=str(active["publication_id"]),
                committed_at_utc="2026-07-29T13:01:00Z",
            )
            status = write_latest_run_status(
                repo_root=REPO_ROOT,
                latest_run_dir=None,
                latest_publication_id=str(latest["publication_id"]),
                message="Latest publication is active.",
                updated_at_utc="2026-07-29T13:02:00Z",
                publication_root=root,
            )
            self.assertTrue(status["active_is_latest_success"])

    def test_mixed_fiscal_year_batch_fails_through_public_entrypoint(
        self,
    ) -> None:
        """Reject two persisted Runs for one company with different years."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            structured = root / "run-2024"
            reviewed = root / "run-2025"
            create_structured_b01_run(
                run_dir=structured,
                forged_value=None,
                run_id="run:mixed-year:structured",
            )
            freeze_fixture(run_dir=structured)
            create_review_run(run_dir=reviewed)
            approve_and_finalize(run_dir=reviewed)
            freeze_fixture(run_dir=reviewed)

            with self.assertRaisesRegex(
                ProjectionError, "Batch company periods differ"
            ):
                write_projection_batch_manifest(
                    repo_root=REPO_ROOT,
                    batch_manifest_path=root / "batch_manifest.json",
                    run_dirs=[structured, reviewed],
                )
            self.assertFalse((root / "batch_manifest.json").exists())

    def test_publication_layout_is_derived_from_one_root(self) -> None:
        """Make pointer, status, storage, and mirror aliases inexpressible."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout = publication_layout(publication_root=root)
            self.assertEqual(
                root / "outputs" / "publications",
                layout["publications_dir"],
            )
            self.assertEqual(
                root / "outputs" / "active_publication.json",
                layout["pointer_path"],
            )
            self.assertEqual(
                root / "artifacts" / "vnext" / "latest_run_status.json",
                layout["latest_status_path"],
            )
            self.assertEqual(
                {
                    relative: (
                        root / relative
                        if relative in {
                            "README_RUN.md",
                            "REPORT_十公司财务指标.md",
                        }
                        else root / "outputs" / relative
                    )
                    for relative in REQUIRED_BUNDLE_FILES
                },
                layout["mirror_paths"],
            )
            self.assertEqual(
                {
                    "committed_at_utc",
                    "expected_active_publication_id",
                    "publication_id",
                    "publication_root",
                },
                set(inspect.signature(commit_publication).parameters),
            )
            self.assertEqual(
                {
                    "committed_at_utc",
                    "expected_active_publication_id",
                    "publication_root",
                    "target_publication_id",
                },
                set(inspect.signature(rollback_publication).parameters),
            )
            self.assertEqual(
                {"publication_root"},
                set(
                    inspect.signature(
                        recover_publication_mirrors
                    ).parameters
                ),
            )
            self.assertEqual(
                {"publication_root"},
                set(inspect.signature(PublicationView.open).parameters),
            )
            self.assertEqual(
                {
                    "latest_publication_id",
                    "latest_run_dir",
                    "message",
                    "publication_root",
                    "repo_root",
                    "updated_at_utc",
                },
                set(inspect.signature(write_latest_run_status).parameters),
            )

    def test_fault_receipt_requires_complete_observed_mirror_state(
        self,
    ) -> None:
        """Reject caller summaries that omit any formal root mirror."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = publication_state_snapshot(publication_root=root)
            incomplete = {
                "active_publication_id": None,
                "mirror_hashes": dict(state["mirror_hashes"]),
            }
            incomplete["mirror_hashes"].pop("metrics_matrix.csv")
            with self.assertRaisesRegex(PublicationError, "exact set"):
                write_publication_fault_receipt(
                    publication_root=root,
                    scenario_id="INCOMPLETE_STATE",
                    prepared_publication_id=None,
                    fault_point="PREPARE_VALIDATION_GATE",
                    before=incomplete,
                    after=state,
                    outcome="WITHHELD_BLOCKED",
                    temporary_workspace_cleaned=True,
                )
            self.assertFalse(
                (
                    root / "outputs" / "publication_fault_receipts"
                ).exists()
            )

    def test_latest_status_revalidates_candidate_inside_pointer_lock(
        self,
    ) -> None:
        """Reject latest bundle drift at the serialized status boundary."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publications = root / "outputs" / "publications"
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-lock-active",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            latest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-lock-candidate",
                    previous_publication_id=str(active["publication_id"]),
                ),
            )
            latest_metric = (
                publications
                / str(latest["publication_id"])
                / "metrics_matrix.csv"
            )

            def corrupt_latest(_descriptor: int, _operation: int) -> None:
                """Simulate concurrent byte drift exactly as the lock lands."""
                latest_metric.write_bytes(b"corrupt-after-precheck")

            with mock.patch(
                "vnext.publication.fcntl.flock", side_effect=corrupt_latest,
            ), self.assertRaises(PublicationError):
                write_latest_run_status(
                    repo_root=REPO_ROOT,
                    latest_run_dir=None,
                    latest_publication_id=str(latest["publication_id"]),
                    message="Latest candidate is still staging.",
                    updated_at_utc="2026-07-29T13:01:00Z",
                    publication_root=root,
                )

    def test_pinned_view_survives_forward_commit_and_rollback(self) -> None:
        """Read a pinned version while pointer and mirrors move."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mirrors = mirror_paths(root=root)
            first_inputs = publication_inputs(
                root=root, tag="first", previous_publication_id=None,
            )
            first = prepare_publication_bundle(
                publication_root=root, **first_inputs,
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            pinned_first = PublicationView.open(
                publication_root=root,
            )
            before_switch = publication_state_snapshot(
                publication_root=root
            )
            second_inputs = publication_inputs(
                root=root,
                tag="second",
                previous_publication_id=str(first["publication_id"]),
            )
            second = prepare_publication_bundle(
                publication_root=root, **second_inputs,
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-07-29T13:01:00Z",
            )
            pinned_second = PublicationView.open(
                publication_root=root,
            )
            self.assertIn(
                str(first["projection_manifest_id"]).encode("utf-8"),
                pinned_first.read_bytes(
                    relative_path="REPORT_十公司财务指标.md"
                ),
            )
            self.assertIn(
                str(second["projection_manifest_id"]).encode("utf-8"),
                pinned_second.read_bytes(
                    relative_path="REPORT_十公司财务指标.md"
                ),
            )
            self.assertEqual(
                pinned_second.read_bytes(relative_path="metrics_matrix.csv"),
                mirrors["metrics_matrix.csv"].read_bytes(),
            )
            rollback_publication(
                publication_root=root,
                target_publication_id=str(first["publication_id"]),
                expected_active_publication_id=str(second["publication_id"]),
                committed_at_utc="2026-07-29T13:02:00Z",
            )
            rolled_back = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(
                first["publication_id"], rolled_back.publication_id
            )
            self.assertIn(
                str(first["projection_manifest_id"]).encode("utf-8"),
                mirrors["REPORT_十公司财务指标.md"].read_bytes(),
            )
            after_rollback = publication_state_snapshot(
                publication_root=root
            )
            receipt = record_fault(
                root=root,
                scenario_id="PINNED_VIEW_POINTER_SWITCH",
                prepared_publication_id=str(second["publication_id"]),
                fault_point="POINTER_SWITCH_DURING_PINNED_READ",
                before=before_switch,
                after=after_rollback,
                outcome="PINNED_VIEW_STABLE",
                temporary_workspace_cleaned=True,
            )
            self.assertEqual(before_switch, after_rollback)
            self.assertEqual("PINNED_VIEW_STABLE", receipt["outcome"])

    def test_rollback_rejects_prepared_never_committed_sibling(self) -> None:
        """Allow rollback only to the committed predecessor."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mirrors = mirror_paths(root=root)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root, tag="first", previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            sibling = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="never-committed",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-07-29T13:01:00Z",
            )
            before = mirrors["metrics_matrix.csv"].read_bytes()
            with self.assertRaises(PublicationError):
                rollback_publication(
                    publication_root=root,
                    target_publication_id=str(sibling["publication_id"]),
                    expected_active_publication_id=str(
                        second["publication_id"]
                    ),
                    committed_at_utc="2026-07-29T13:02:00Z",
                )
            active = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(second["publication_id"], active.publication_id)
            self.assertEqual(
                before, mirrors["metrics_matrix.csv"].read_bytes(),
            )

    def test_pointer_predecessor_must_match_committed_switch_history(
        self,
    ) -> None:
        """Reject a pointer whose predecessor lacks its committed edge."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="edge-first",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="edge-second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            sibling = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="edge-never-committed",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-08-06T00:01:00Z",
            )
            pointer_path = root / "outputs" / "active_publication.json"
            pointer = strict_json_file(path=pointer_path)
            pointer["previous_publication_id"] = sibling["publication_id"]
            atomic_write_json(path=pointer_path, value=pointer)
            with self.assertRaises(PublicationError):
                PublicationView.open(publication_root=root)
            with self.assertRaises(PublicationError):
                rollback_publication(
                    publication_root=root,
                    target_publication_id=str(sibling["publication_id"]),
                    expected_active_publication_id=str(
                        second["publication_id"]
                    ),
                    committed_at_utc="2026-08-06T00:02:00Z",
                )

    def test_historical_pointer_bytes_are_not_current_chain_tip(
        self,
    ) -> None:
        """Reject exact old pointer bytes after a newer committed switch."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="stale-pointer-first",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            pointer_path = root / "outputs" / "active_publication.json"
            historical_pointer = pointer_path.read_bytes()
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="stale-pointer-second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-08-06T00:01:00Z",
            )
            atomic_write_bytes(
                path=pointer_path, content=historical_pointer,
            )

            with self.assertRaisesRegex(
                PublicationError, "committed switch.*tip"
            ):
                PublicationView.open(publication_root=root)

    def test_switch_receipt_graph_has_one_connected_root_and_tip(
        self,
    ) -> None:
        """Reject a validly hashed disconnected switch-history root."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="disconnected-switch-root",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            pointer = strict_json_file(
                path=root / "outputs" / "active_publication.json"
            )
            body = {
                "schema_version": 1,
                "record_type": "PUBLICATION_SWITCH",
                "switch_mode": "ROLLBACK",
                "previous_switch_receipt_id": None,
                "pointer": pointer,
            }
            receipt = {
                **body,
                "switch_receipt_id": content_hash(value=body),
            }
            receipt_path = (
                root
                / "outputs/publication_switch_receipts"
                / "{}.json".format(
                    receipt["switch_receipt_id"].split(":", 1)[1]
                )
            )
            atomic_write_json(path=receipt_path, value=receipt)

            with self.assertRaisesRegex(
                PublicationError, "one committed switch tip"
            ):
                PublicationView.open(publication_root=root)

    def test_hard_crash_after_pointer_requires_writer_recovery(
        self,
    ) -> None:
        """Fail readers closed, then complete a pointer-committed intent."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="intent-crash-first",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="intent-crash-second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )

            def crash_after_pointer(*, fault_point: str) -> None:
                """Model process death at the pointer/receipt boundary."""
                if fault_point == "POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT":
                    raise SimulatedPublicationCrash("hard crash after pointer")

            with mock.patch(
                "vnext.publication._fault_injection_checkpoint",
                side_effect=crash_after_pointer,
            ), self.assertRaises(SimulatedPublicationCrash):
                commit_formal_fixture(
                    publication_root=root,
                    publication_id=str(second["publication_id"]),
                    expected_active_publication_id=str(
                        first["publication_id"]
                    ),
                    committed_at_utc="2026-08-06T00:01:00Z",
                )
            intent_dir = (
                root / "outputs" / "publication_switch_intents"
            )
            self.assertEqual(1, len(list(intent_dir.glob("*.json"))))
            with self.assertRaisesRegex(
                PublicationError, "recovery intent is pending"
            ):
                PublicationView.open(publication_root=root)

            recovered = recover_publication_mirrors(publication_root=root)
            self.assertEqual(second["publication_id"], recovered)
            self.assertEqual(
                second["publication_id"],
                PublicationView.open(publication_root=root).publication_id,
            )
            self.assertEqual([], list(intent_dir.glob("*.json")))

    def test_reader_waits_for_pointer_edge_transaction(
        self,
    ) -> None:
        """Expose no pointer-before-edge half state to a concurrent reader."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="reader-lock-first",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            pinned_old = PublicationView.open(publication_root=root)
            pinned_old_metrics = pinned_old.read_bytes(
                relative_path="metrics_matrix.csv"
            )
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="reader-lock-second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            pointer_written = threading.Event()
            allow_receipt = threading.Event()
            original_authority = (
                publication_module._publication_commit_authority
            )
            original_forward_guard = (
                publication_module._require_existing_active_for_forward_commit
            )

            def pause_after_pointer(*, fault_point: str) -> None:
                """Hold the exclusive transaction at its narrowest interval."""
                if fault_point != "POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT":
                    return
                pointer_written.set()
                if not allow_receipt.wait(timeout=5):
                    raise OSError("reader-lock test timed out")

            def commit_second() -> Dict[str, object]:
                """Commit the successor through the real transaction helper."""
                return publication_module._commit_publication(
                    publication_root=root,
                    publication_id=str(second["publication_id"]),
                    expected_active_publication_id=str(
                        first["publication_id"]
                    ),
                    committed_at_utc="2026-08-06T00:01:00Z",
                )

            # Keep every process-global test authority patch in the main
            # thread so a worker cannot leak a mock into later test cases.
            with mock.patch(
                "vnext.publication._publication_commit_authority",
                return_value="FORMAL",
            ), mock.patch(
                "vnext.publication._require_existing_active_for_forward_commit",
            ), mock.patch(
                "vnext.publication._fault_injection_checkpoint",
                side_effect=pause_after_pointer,
            ), ThreadPoolExecutor(max_workers=2) as executor:
                writer = executor.submit(commit_second)
                self.assertTrue(pointer_written.wait(timeout=5))
                reader = executor.submit(
                    PublicationView.open, publication_root=root,
                )
                with self.assertRaises(FutureTimeoutError):
                    reader.result(timeout=0.2)
                allow_receipt.set()
                writer.result(timeout=5)
                pinned_new = reader.result(timeout=5)
            self.assertIs(
                original_authority,
                publication_module._publication_commit_authority,
            )
            self.assertIs(
                original_forward_guard,
                publication_module._require_existing_active_for_forward_commit,
            )
            self.assertEqual(
                second["publication_id"], pinned_new.publication_id,
            )
            self.assertEqual(first["publication_id"], pinned_old.publication_id)
            self.assertEqual(
                pinned_old_metrics,
                pinned_old.read_bytes(relative_path="metrics_matrix.csv"),
            )

    def test_recorded_sandbox_owns_root_authority_and_supports_cas(
        self,
    ) -> None:
        """Commit only RECORDED bundles below the fixed workspace root."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="recorded-sandbox",
                previous_publication_id=None,
            )
            repo_root = Path(inputs["repo_root"])
            workspace = (
                repo_root / "artifacts" / "vnext" / "recorded-u01"
            )
            receipt_path = (
                Path(inputs["staging_dir"])
                / "publication_validation_receipt.json"
            )
            receipt_path.unlink()
            formal_before = publication_state_snapshot(
                publication_root=repo_root,
            )
            first = complete_recorded_publication_sandbox(
                repo_root=repo_root,
                workspace_dir=workspace,
                batch_manifest_path=Path(inputs["batch_manifest_path"]),
                legacy_snapshot_dir=Path(inputs["legacy_snapshot_dir"]),
                staging_dir=Path(inputs["staging_dir"]),
                validated_at_utc="2026-07-31T00:00:00Z",
                committed_at_utc="2026-08-06T00:00:01Z",
            )
            receipt_path.unlink()
            second = complete_recorded_publication_sandbox(
                repo_root=repo_root,
                workspace_dir=workspace,
                batch_manifest_path=Path(inputs["batch_manifest_path"]),
                legacy_snapshot_dir=Path(inputs["legacy_snapshot_dir"]),
                staging_dir=Path(inputs["staging_dir"]),
                validated_at_utc="2026-07-31T00:00:00Z",
                committed_at_utc="2026-08-06T00:00:02Z",
            )
            self.assertEqual(
                formal_before,
                publication_state_snapshot(publication_root=repo_root),
            )
        self.assertNotEqual(
            first["publication_id"], second["publication_id"],
        )
        self.assertEqual(
            first["publication_id"], second["previous_publication_id"],
        )
        self.assertEqual(
            "artifacts/vnext/recorded-u01/recorded-publication",
            second["publication_root"],
        )
        self.assertEqual(
            second["readback_hashes"], second["root_mirror_hashes"],
        )
        parameters = set(
            inspect.signature(
                complete_recorded_publication_sandbox
            ).parameters
        )
        self.assertNotIn("publication_root", parameters)
        self.assertNotIn("authority", parameters)

    def test_recorded_sandbox_rejects_workspace_outside_repository(
        self,
    ) -> None:
        """Do not let a caller redirect RECORDED mirrors to another root."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="recorded-sandbox-escape",
                previous_publication_id=None,
            )
            outside = root / "outside" / "not-created"
            with self.assertRaisesRegex(PublicationError, "artifacts/vnext"):
                complete_recorded_publication_sandbox(
                    repo_root=Path(inputs["repo_root"]),
                    workspace_dir=outside,
                    batch_manifest_path=Path(
                        inputs["batch_manifest_path"]
                    ),
                    legacy_snapshot_dir=Path(
                        inputs["legacy_snapshot_dir"]
                    ),
                    staging_dir=Path(inputs["staging_dir"]),
                    validated_at_utc="2026-07-31T00:00:00Z",
                    committed_at_utc="2026-08-06T00:00:01Z",
                )
            self.assertFalse(outside.exists())

    def test_recorded_sandbox_rejects_formal_publication_namespace(
        self,
    ) -> None:
        """Do not hide recorded bytes below formal immutable storage."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="recorded-sandbox-formal-namespace",
                previous_publication_id=None,
            )
            repo_root = Path(inputs["repo_root"])
            with self.assertRaisesRegex(
                PublicationError, "artifacts/vnext",
            ):
                complete_recorded_publication_sandbox(
                    repo_root=repo_root,
                    workspace_dir=repo_root / "outputs" / "publications",
                    batch_manifest_path=Path(
                        inputs["batch_manifest_path"]
                    ),
                    legacy_snapshot_dir=Path(
                        inputs["legacy_snapshot_dir"]
                    ),
                    staging_dir=Path(inputs["staging_dir"]),
                    validated_at_utc="2026-07-31T00:00:00Z",
                    committed_at_utc="2026-08-06T00:00:01Z",
                )

    def test_pre_pointer_crash_orphan_edge_cannot_authorize_pointer(
        self,
    ) -> None:
        """Require writer recovery; no orphan edge alone authorizes a switch."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="orphan-edge-first",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="orphan-edge-second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )

            def crash_before_pointer(*, fault_point: str) -> None:
                """Leave every pre-pointer mutation exactly as a crash would."""
                if fault_point == "MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT":
                    raise SimulatedPublicationCrash("crash before pointer")

            with mock.patch(
                "vnext.publication._fault_injection_checkpoint",
                side_effect=crash_before_pointer,
            ), self.assertRaises(SimulatedPublicationCrash):
                commit_formal_fixture(
                    publication_root=root,
                    publication_id=str(second["publication_id"]),
                    expected_active_publication_id=str(
                        first["publication_id"]
                    ),
                    committed_at_utc="2026-08-06T00:01:00Z",
                )

            receipt_paths = sorted(
                (
                    root / "outputs" / "publication_switch_receipts"
                ).glob("*.json")
            )
            orphans = [
                strict_json_file(path=path)
                for path in receipt_paths
                if strict_json_file(path=path)["pointer"]["publication_id"]
                == second["publication_id"]
            ]
            self.assertEqual([], orphans)
            pointer_path = root / "outputs" / "active_publication.json"
            atomic_write_json(
                path=pointer_path,
                value={
                    "publication_id": second["publication_id"],
                    "bundle_manifest_sha256": sha256_file(
                        path=(
                            root
                            / "outputs"
                            / "publications"
                            / str(second["publication_id"])
                            / "publication_manifest.json"
                        )
                    ),
                    "previous_publication_id": first["publication_id"],
                    "committed_at_utc": "2026-08-06T00:01:00Z",
                },
            )
            with self.assertRaises(PublicationError):
                PublicationView.open(publication_root=root)
            rolled_back = rollback_publication(
                publication_root=root,
                target_publication_id=str(first["publication_id"]),
                expected_active_publication_id=str(
                    second["publication_id"]
                ),
                committed_at_utc="2026-08-06T00:02:00Z",
            )
            self.assertEqual(first["publication_id"], rolled_back[
                "publication_id"
            ])
            self.assertEqual(
                first["publication_id"],
                PublicationView.open(publication_root=root).publication_id,
            )

    def test_rollback_then_restore_reuses_only_verified_bundles(self) -> None:
        """Return to the committed successor without rerunning a producer."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="restore-first",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="restore-second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-08-06T00:01:00Z",
            )
            rollback_publication(
                publication_root=root,
                target_publication_id=str(first["publication_id"]),
                expected_active_publication_id=str(second["publication_id"]),
                committed_at_utc="2026-08-06T00:02:00Z",
            )
            restored = commit_formal_fixture(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-08-06T00:03:00Z",
            )

            view = PublicationView.open(publication_root=root)
            self.assertEqual(second["publication_id"], view.publication_id)
            self.assertEqual(
                second["publication_id"], restored["publication_id"]
            )
            for relative, mirror in mirror_paths(root=root).items():
                with self.subTest(restored_mirror=relative):
                    self.assertEqual(
                        view.read_bytes(relative_path=relative),
                        mirror.read_bytes(),
                    )

    def test_mirror_recovery_and_cas_loss_preserve_active(self) -> None:
        """Repair mirrors from active and reject a stale publisher."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mirrors = mirror_paths(root=root)
            inputs = publication_inputs(
                root=root, tag="active", previous_publication_id=None
            )
            active = prepare_publication_bundle(
                publication_root=root, **inputs,
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            mirrors["metrics_matrix.csv"].write_bytes(b"corrupt")
            recovered_id = recover_publication_mirrors(
                publication_root=root,
            )
            self.assertEqual(active["publication_id"], recovered_id)
            self.assertEqual(
                (inputs["staging_dir"] / "metrics_matrix.csv").read_bytes(),
                mirrors["metrics_matrix.csv"].read_bytes(),
            )
            before_cas_loss = publication_state_snapshot(
                publication_root=root
            )
            with self.assertRaisesRegex(PublicationError, "CAS predecessor"):
                commit_formal_fixture(
                    publication_root=root,
                    publication_id=str(active["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-07-29T13:01:00Z",
                )
            current = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(active["publication_id"], current.publication_id)
            after_cas_loss = publication_state_snapshot(
                publication_root=root
            )
            receipt = record_fault(
                root=root,
                scenario_id="CAS_LOSER",
                prepared_publication_id=str(active["publication_id"]),
                fault_point="CAS_POINTER_LOCK",
                before=before_cas_loss,
                after=after_cas_loss,
                outcome="CAS_LOST_ACTIVE_PRESERVED",
                temporary_workspace_cleaned=True,
            )
            self.assertEqual(before_cas_loss, after_cas_loss)
            self.assertEqual(
                "CAS_LOST_ACTIVE_PRESERVED", receipt["outcome"]
            )

    def test_mid_bundle_write_failure_cleans_temporary_namespace(
        self,
    ) -> None:
        """Abort a partial immutable-bundle write without moving active."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="mid-bundle-active",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            successor_inputs = publication_inputs(
                root=root,
                tag="mid-bundle-successor",
                previous_publication_id=str(active["publication_id"]),
            )
            preview = prepare_publication_bundle(
                publication_root=root / "preview",
                **successor_inputs,
            )
            before = publication_state_snapshot(publication_root=root)

            def fail_mid_bundle(*, fault_point: str) -> None:
                """Fail only after a deterministic partial bundle write."""
                if fault_point == "MID_BUNDLE_WRITE":
                    raise OSError("injected mid-bundle write failure")

            with mock.patch(
                "vnext.publication._fault_injection_checkpoint",
                side_effect=fail_mid_bundle,
            ), self.assertRaisesRegex(PublicationError, "bundle write"):
                prepare_publication_bundle(
                    publication_root=root,
                    **successor_inputs,
                )

            publications = root / "outputs" / "publications"
            temporary_cleaned = not any(
                path.name.startswith(".") and path.name.endswith(".tmp")
                for path in publications.iterdir()
            )
            after = publication_state_snapshot(publication_root=root)
            receipt = record_fault(
                root=root,
                scenario_id="MID_BUNDLE_WRITE",
                prepared_publication_id=str(preview["publication_id"]),
                fault_point="MID_BUNDLE_WRITE",
                before=before,
                after=after,
                outcome="ABORTED_ACTIVE_PRESERVED",
                temporary_workspace_cleaned=temporary_cleaned,
            )
            self.assertEqual(before, after)
            self.assertTrue(temporary_cleaned)
            self.assertFalse(
                (
                    publications / str(preview["publication_id"])
                ).exists()
            )
            self.assertEqual("MID_BUNDLE_WRITE", receipt["scenario_id"])

    def test_mid_mirror_write_failure_restores_pointer_and_every_mirror(
        self,
    ) -> None:
        """Restore the complete prior root view after a mirror write fails."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="mid-mirror-active",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            successor = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="mid-mirror-successor",
                    previous_publication_id=str(active["publication_id"]),
                ),
            )
            before = publication_state_snapshot(publication_root=root)

            def fail_mid_mirror(*, fault_point: str) -> None:
                """Fail after the transaction has replaced some mirrors."""
                if fault_point == "MID_MIRROR_WRITE":
                    raise OSError("injected mid-mirror write failure")

            with mock.patch(
                "vnext.publication._fault_injection_checkpoint",
                side_effect=fail_mid_mirror,
            ), self.assertRaisesRegex(PublicationError, "rolled back"):
                commit_formal_fixture(
                    publication_root=root,
                    publication_id=str(successor["publication_id"]),
                    expected_active_publication_id=str(
                        active["publication_id"]
                    ),
                    committed_at_utc="2026-08-06T00:01:00Z",
                )

            after = publication_state_snapshot(publication_root=root)
            receipt = record_fault(
                root=root,
                scenario_id="MID_MIRROR_WRITE",
                prepared_publication_id=str(successor["publication_id"]),
                fault_point="MID_MIRROR_WRITE",
                before=before,
                after=after,
                outcome="ABORTED_ACTIVE_PRESERVED",
                temporary_workspace_cleaned=True,
            )
            self.assertEqual(before, after)
            self.assertEqual(
                before["mirror_hashes"], receipt["mirror_hashes_after"]
            )
            self.assertEqual(
                [],
                list(
                    (
                        root / "outputs/publication_switch_intents"
                    ).glob("*.json")
                ),
            )

    def test_mirrors_written_before_pointer_commit_recover_from_pointer(
        self,
    ) -> None:
        """Repair a crash-divergent root view from the official old pointer."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="pre-pointer-active",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            successor = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="pre-pointer-successor",
                    previous_publication_id=str(active["publication_id"]),
                ),
            )
            before = publication_state_snapshot(publication_root=root)

            def crash_before_pointer(*, fault_point: str) -> None:
                """Model termination after all mirrors but before pointer."""
                if fault_point == "MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT":
                    raise SimulatedPublicationCrash(
                        "injected crash before pointer commit"
                    )

            with mock.patch(
                "vnext.publication._fault_injection_checkpoint",
                side_effect=crash_before_pointer,
            ), self.assertRaises(SimulatedPublicationCrash):
                commit_formal_fixture(
                    publication_root=root,
                    publication_id=str(successor["publication_id"]),
                    expected_active_publication_id=str(
                        active["publication_id"]
                    ),
                    committed_at_utc="2026-08-06T00:01:00Z",
                )

            crashed = publication_state_snapshot(publication_root=root)
            self.assertEqual(
                before["active_publication_id"],
                crashed["active_publication_id"],
            )
            self.assertNotEqual(
                before["mirror_hashes"], crashed["mirror_hashes"]
            )
            recovered_id = recover_publication_mirrors(
                publication_root=root,
            )
            after = publication_state_snapshot(publication_root=root)
            receipt = record_fault(
                root=root,
                scenario_id="MIRRORS_BEFORE_POINTER",
                prepared_publication_id=str(successor["publication_id"]),
                fault_point="MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT",
                before=before,
                after=after,
                outcome="RECOVERED_FROM_ACTIVE",
                temporary_workspace_cleaned=True,
            )
            self.assertEqual(active["publication_id"], recovered_id)
            self.assertEqual(before, after)
            self.assertRegex(
                str(receipt["fault_receipt_id"]), r"^sha256:[0-9a-f]{64}$"
            )
            self.assertEqual(
                content_hash(
                    value={
                        field: value
                        for field, value in receipt.items()
                        if field != "fault_receipt_id"
                    }
                ),
                receipt["fault_receipt_id"],
            )
            self.assertEqual(
                {
                    "active_after",
                    "active_before",
                    "fault_point",
                    "fault_receipt_id",
                    "mirror_hashes_after",
                    "mirror_hashes_before",
                    "outcome",
                    "prepared_publication_id",
                    "scenario_id",
                    "schema_version",
                    "temporary_workspace_cleaned",
                },
                set(receipt),
            )
            receipt_path = (
                root
                / "outputs"
                / "publication_fault_receipts"
                / "{}.json".format(
                    str(receipt["fault_receipt_id"]).split(":", 1)[1]
                )
            )
            self.assertEqual(
                receipt,
                json.loads(receipt_path.read_text(encoding="utf-8")),
            )

    def test_symlinked_pointer_or_manifest_is_not_authoritative(self) -> None:
        """Reject authority files that resolve outside their named path."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publications = root / "outputs" / "publications"
            real_pointer = root / "real_pointer.json"
            pointer_alias = root / "outputs" / "active_publication.json"
            inputs = publication_inputs(
                root=root, tag="symlink", previous_publication_id=None,
            )
            manifest = prepare_publication_bundle(
                publication_root=root, **inputs,
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(manifest["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            real_pointer.write_bytes(pointer_alias.read_bytes())
            pointer_alias.unlink()
            pointer_alias.symlink_to(real_pointer)
            with self.assertRaisesRegex(PublicationError, "pointer.*symlink"):
                PublicationView.open(publication_root=root)
            bundle_dir = publications / str(manifest["publication_id"])
            manifest_path = bundle_dir / "publication_manifest.json"
            redirected = root / "redirected_manifest.json"
            redirected.write_bytes(manifest_path.read_bytes())
            manifest_path.unlink()
            manifest_path.symlink_to(redirected)
            with self.assertRaisesRegex(PublicationError, "manifest.*real"):
                verify_publication_bundle(bundle_dir=bundle_dir)

    def test_publication_view_never_creates_missing_authority_lock(
        self,
    ) -> None:
        """Fail closed without creating a lock from a read-only consumer."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="read-only-lock",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(manifest["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T01:00:00Z",
            )
            lock_path = (
                root / "outputs" / "active_publication.json.lock"
            )
            lock_path.unlink()

            with self.assertRaisesRegex(
                PublicationError, "authority lock.*missing"
            ):
                PublicationView.open(publication_root=root)
            self.assertFalse(lock_path.exists())

    def test_committed_bundle_tamper_fails_read_back_and_records_fault(
        self,
    ) -> None:
        """Reject changed active bytes before any pinned consumer can read."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="bundle-tamper",
                    previous_publication_id=None,
                ),
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(manifest["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            before = publication_state_snapshot(publication_root=root)
            metric_path = (
                root
                / "outputs"
                / "publications"
                / str(manifest["publication_id"])
                / "metrics_matrix.csv"
            )
            original = metric_path.read_bytes()
            metric_path.write_bytes(original + b"tamper")
            with self.assertRaisesRegex(
                PublicationError, "artifact digest differs"
            ):
                PublicationView.open(publication_root=root)
            metric_path.write_bytes(original)
            after = publication_state_snapshot(publication_root=root)
            receipt = record_fault(
                root=root,
                scenario_id="ACTIVE_BUNDLE_TAMPER",
                prepared_publication_id=str(manifest["publication_id"]),
                fault_point="PUBLICATION_VIEW_READ_BACK",
                before=before,
                after=after,
                outcome="TAMPER_REJECTED",
                temporary_workspace_cleaned=True,
            )
            self.assertEqual(before, after)
            self.assertEqual("TAMPER_REJECTED", receipt["outcome"])

    def test_two_concurrent_publishers_have_one_winner(self) -> None:
        """Serialize commits so a stale CAS publisher cannot win."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_authority = (
                publication_module._publication_commit_authority
            )
            original_forward_guard = (
                publication_module._require_existing_active_for_forward_commit
            )
            manifests = [
                prepare_publication_bundle(
                    publication_root=root,
                    **publication_inputs(
                        root=root, tag=tag, previous_publication_id=None,
                    ),
                )
                for tag in ("publisher-a", "publisher-b")
            ]
            before = publication_state_snapshot(publication_root=root)

            def publish(manifest: Mapping[str, object]) -> str:
                """Attempt one first-publication CAS commit."""
                publication_module._commit_publication(
                    publication_root=root,
                    publication_id=str(manifest["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-07-29T13:00:00Z",
                )
                return str(manifest["publication_id"])

            # Test-only formal authority belongs to the main thread and spans
            # both workers; overlapping per-thread patches can restore mocks
            # out of order and corrupt later recorded tests.
            with mock.patch(
                "vnext.publication._publication_commit_authority",
                return_value="FORMAL",
            ), mock.patch(
                "vnext.publication._require_existing_active_for_forward_commit",
            ), ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(publish, manifest)
                    for manifest in manifests
                ]
                successes = []
                failures = []
                for future in futures:
                    try:
                        successes.append(future.result())
                    except PublicationError as error:
                        failures.append(str(error))
            self.assertIs(
                original_authority,
                publication_module._publication_commit_authority,
            )
            self.assertIs(
                original_forward_guard,
                publication_module._require_existing_active_for_forward_commit,
            )
            self.assertEqual(1, len(successes))
            self.assertEqual(1, len(failures))
            active = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(successes[0], active.publication_id)
            after = publication_state_snapshot(publication_root=root)
            receipt = record_fault(
                root=root,
                scenario_id="CONCURRENT_PUBLISHERS",
                prepared_publication_id=successes[0],
                fault_point="CAS_POINTER_LOCK",
                before=before,
                after=after,
                outcome="EXACTLY_ONE_WINNER",
                temporary_workspace_cleaned=True,
            )
            self.assertEqual("EXACTLY_ONE_WINNER", receipt["outcome"])

    def test_threaded_formal_fixture_restores_commit_authority(self) -> None:
        """Reject worker-owned authority patches before they can leak."""
        original_authority = (
            publication_module._publication_commit_authority
        )
        original_forward_guard = (
            publication_module._require_existing_active_for_forward_commit
        )
        def invoke(*, publication_id: str) -> str:
            """Return the stable worker-thread fixture rejection."""
            try:
                commit_formal_fixture(
                    publication_root=Path("unused-threaded-root"),
                    publication_id=publication_id,
                    expected_active_publication_id=None,
                    committed_at_utc="2026-08-07T00:00:00Z",
                )
            except AssertionError as error:
                return str(error)
            raise AssertionError("worker fixture helper unexpectedly passed")

        with ThreadPoolExecutor(max_workers=2) as executor:
            errors = list(executor.map(
                lambda publication_id: invoke(
                    publication_id=publication_id,
                ),
                ("publication_a", "publication_b"),
            ))
        self.assertEqual(
            [
                "Formal fixture authority patch requires the main test thread",
                "Formal fixture authority patch requires the main test thread",
            ],
            errors,
        )
        self.assertIs(
            original_authority,
            publication_module._publication_commit_authority,
        )
        self.assertIs(
            original_forward_guard,
            publication_module._require_existing_active_for_forward_commit,
        )


if __name__ == "__main__":
    unittest.main()
