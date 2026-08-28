"""Publish one Issue #15 delta through existing Run, Projector, and CAS gates.

The module owns no metric, company, source, or task literal.  It derives the
active child plan and its table qualification exact set from repository
authority, replays committed qualification evidence, materializes only the
structural coordinates that need no source, and delegates row construction to
the shared Projector.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from git_workspace import sanitized_git_environment
from validation_provenance import capture_source_snapshot
from validation_provenance import publish_validation_snapshot

from .ai_adapter import build_recorded_adapter
from .calculator import calculate_observation_metric
from .canonical import atomic_write_bytes, atomic_write_json
from .canonical import canonical_json_bytes, content_hash, sha256_bytes
from .canonical import sha256_file, strict_json_file, strict_json_loads
from .evidence import check_evidence
from .projector import FrozenRunLoader, build_projection_manifest
from .projector import write_projection_batch_manifest
from .projector import write_projection_candidate
from .publication import FORMAL_VALIDATION_MODE, REQUIRED_BUNDLE_FILES
from .publication import REQUIRED_PUBLICATION_CHECKS, ROOT_MIRROR_RELATIVE_PATHS
from .publication import PublicationView, _commit_publication
from .publication import _finalize_staging_view, _publication_gate_evidence
from .publication import _portable_closure_files
from .publication import _read_staging_files, _write_prepared_publication_bundle
from .publication import publication_layout, publication_ledger_binding
from .publication import publication_state_snapshot
from .publication import publication_validation_view_id
from .publication import verify_publication_bundle
from .records import validate_record
from .requirements import load_requirement_snapshot
from .review import effective_review_decision
from .run_store import RunStoreError, _read_jsonl, _read_manifest
from .run_store import _run_content_and_audit_hashes, _run_paths
from .run_store import _validate_review_bindings, _verify_review_assets
from .run_store import _verify_run_validation_receipt
from .run_store import load_frozen_run, validate_and_freeze_run
from .source_strategy import load_issue15_release_plans
from .sources import load_raw_blob_bytes
from .specs import compile_spec_files
from .table_grid import build_table_grid
from .table_qualification_freeze import load_table_qualification_matrix
from .table_task_contracts import load_table_task_contracts
from .traits import repository_company_traits
from .workflow import create_table_task_review_run


RATCHET_WORKSPACE = Path("artifacts/vnext/ratchet_release/r3")
QUALIFICATION_POINTER = Path("config/table_qualification_freeze.json")
QUALIFICATION_CYCLE_ROOT = Path("artifacts/vnext/qualification/cycles")
QUALIFICATION_FREEZE_ROOT = Path("artifacts/vnext/table_qualification_freeze")


class RatchetReleaseError(RuntimeError):
    """Report an invalid plan, qualification, projection, or publication."""


def _json_bytes(*, value: Mapping[str, object]) -> bytes:
    """Return canonical JSON with one terminal LF."""
    return canonical_json_bytes(value=value) + b"\n"


def _git(
    *, repo_root: Path, arguments: Sequence[str], check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run one non-interactive Git query in the fixed repository."""
    completed = subprocess.run(
        ["git", *arguments],
        cwd=str(repo_root),
        env=sanitized_git_environment(),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if check and completed.returncode != 0:
        raise RatchetReleaseError("Ratchet Git authority is unavailable")
    return completed


def _relative(*, repo_root: Path, candidate: Path) -> str:
    """Return one direct repository-relative path without aliases."""
    if candidate.is_symlink():
        raise RatchetReleaseError("Ratchet path is a symlink")
    try:
        relative = candidate.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise RatchetReleaseError("Ratchet path is outside repository") from error
    if ".." in relative.parts or relative.as_posix() in {"", "."}:
        raise RatchetReleaseError("Ratchet path is invalid")
    return relative.as_posix()


def _tree_files(*, root: Path) -> Dict[str, Dict[str, object]]:
    """Hash one exact regular-file tree and reject aliases/special entries."""
    if root.is_symlink() or not root.is_dir():
        raise RatchetReleaseError("Ratchet tree is absent or unsafe")
    files: Dict[str, Dict[str, object]] = {}
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink():
            raise RatchetReleaseError("Ratchet tree contains a symlink")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise RatchetReleaseError("Ratchet tree contains a special entry")
        relative = candidate.relative_to(root).as_posix()
        files[relative] = {
            "sha256": sha256_file(path=candidate),
            "size": candidate.stat().st_size,
        }
    if not files:
        raise RatchetReleaseError("Ratchet tree is empty")
    return files


def _copy_exact_tree(*, source: Path, destination: Path) -> None:
    """Copy a tree once or require an existing byte-identical destination."""
    source_files = _tree_files(root=source)
    if destination.exists():
        if _tree_files(root=destination) != source_files:
            raise RatchetReleaseError("Existing ratchet tree bytes differ")
        return
    if destination.is_symlink():
        raise RatchetReleaseError("Ratchet destination is unsafe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    if _tree_files(root=destination) != source_files:
        raise RatchetReleaseError("Ratchet tree copy differs")


def _committed_run_origin(
    *, repo_root: Path, run_dir: Path,
) -> Dict[str, str]:
    """Bind a qualification Run to the commit that introduced its manifest."""
    relative = _relative(repo_root=repo_root, candidate=run_dir)
    manifest_relative = str(Path(relative) / "manifest.json")
    commit = _git(
        repo_root=repo_root,
        arguments=[
            "log", "-1", "--format=%H", "--diff-filter=A", "--",
            manifest_relative,
        ],
    ).stdout.strip()
    if len(commit) != 40:
        raise RatchetReleaseError("Qualification Run commit is unavailable")
    if _git(
        repo_root=repo_root,
        arguments=["merge-base", "--is-ancestor", commit, "HEAD"],
        check=False,
    ).returncode != 0:
        raise RatchetReleaseError("Qualification Run commit is not an ancestor")
    if _git(
        repo_root=repo_root,
        arguments=["diff", "--quiet", commit, "--", relative],
        check=False,
    ).returncode != 0:
        raise RatchetReleaseError("Qualification Run differs from its commit")
    committed_paths = {
        value.removeprefix(relative + "/")
        for value in _git(
            repo_root=repo_root,
            arguments=["ls-tree", "-r", "--name-only", commit, "--", relative],
        ).stdout.splitlines()
        if value
    }
    if committed_paths != set(_tree_files(root=run_dir)):
        raise RatchetReleaseError("Qualification Run committed file set differs")
    tree_oid = _git(
        repo_root=repo_root, arguments=["rev-parse", commit + "^{tree}"],
    ).stdout.strip()
    if len(tree_oid) != 40:
        raise RatchetReleaseError("Qualification Run tree is unavailable")
    return {"commit": commit, "tree_oid": tree_oid, "run_path": relative}


def _group(
    *, records: Sequence[Mapping[str, object]], record_type: str,
    expected: int,
) -> List[Dict[str, object]]:
    """Return one exact record-type group."""
    values = [dict(row) for row in records if row["record_type"] == record_type]
    if len(values) != expected:
        raise RatchetReleaseError(
            "Qualification {} exact set differs".format(record_type)
        )
    return values


def _validate_committed_qualification_run(
    *, repo_root: Path, run_dir: Path,
    origin: Optional[Mapping[str, str]],
) -> Tuple[Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]]:
    """Replay one committed table terminal without consulting mutable tips."""
    manifest = _read_manifest(run_dir=run_dir)
    authorization = manifest.get("qualification_authorization")
    if manifest["status"] != "FROZEN" or not isinstance(authorization, dict):
        raise RatchetReleaseError("Committed qualification Run is not FROZEN")
    if origin is not None:
        original = repo_root / str(authorization["run_directory_relative_path"])
        current_origin = _committed_run_origin(
            repo_root=repo_root, run_dir=original,
        )
        if current_origin != dict(origin):
            raise RatchetReleaseError("Qualification Run origin binding differs")
        if _tree_files(root=run_dir) != _tree_files(root=original):
            raise RatchetReleaseError("Qualification Run copy differs from commit")

    paths = _run_paths(run_dir=run_dir)
    expected_hashes = {
        "records_file_hash": sha256_file(path=paths["records"]),
        "review_decisions_file_hash": sha256_file(path=paths["decisions"]),
        "validation_file_hash": sha256_file(path=paths["validation"]),
    }
    if any(manifest[field] != value for field, value in expected_hashes.items()):
        raise RatchetReleaseError("Qualification Run file hash differs")
    records = _read_jsonl(path=paths["records"])
    decisions = _read_jsonl(path=paths["decisions"])
    validation_value = strict_json_file(path=paths["validation"])
    if not isinstance(validation_value, dict):
        raise RatchetReleaseError("Qualification validation is malformed")
    validation = validate_record(record=validation_value)
    if validation["status"] != "PASSED":
        raise RatchetReleaseError("Qualification validation did not PASS")
    _verify_run_validation_receipt(
        run_dir=run_dir, manifest=manifest, receipt=validation,
    )
    expected_content, expected_audit = _run_content_and_audit_hashes(
        manifest=manifest,
        records=records,
        decisions=decisions,
        validation=validation,
    )
    if (
        manifest["content_manifest_hash"] != expected_content
        or manifest["audit_manifest_hash"] != expected_audit
    ):
        raise RatchetReleaseError("Qualification terminal hash differs")
    effective = _validate_review_bindings(records=records, decisions=decisions)
    review_units = _group(
        records=records, record_type="REVIEW_UNIT", expected=1,
    )
    _verify_review_assets(run_dir=run_dir, review_units=review_units)

    raw = _group(records=records, record_type="RAW_BLOB", expected=1)[0]
    source = _group(
        records=records, record_type="SOURCE_REFERENCE", expected=1,
    )[0]
    derived = _group(
        records=records, record_type="DERIVED_ASSET", expected=1,
    )[0]
    raw_bytes = load_raw_blob_bytes(repo_root=repo_root, raw_blob=raw)
    replayed = build_table_grid(
        html_bytes=raw_bytes,
        parent_raw_asset_ids=list(derived["parent_raw_asset_ids"]),
        storage_uri=str(derived["storage_uri"]),
    )
    if replayed != derived or source["raw_asset_id"] != raw["raw_asset_id"]:
        raise RatchetReleaseError("Qualification DerivedAsset replay differs")

    reader_manifest = _group(
        records=records, record_type="READER_INPUT_MANIFEST", expected=1,
    )[0]
    candidate = _group(
        records=records, record_type="OBSERVATION_CANDIDATE", expected=1,
    )[0]
    evidence = _group(
        records=records, record_type="EVIDENCE_CHECK", expected=1,
    )[0]
    attempt = _group(
        records=records, record_type="AI_EXTRACTION_ATTEMPT", expected=1,
    )[0]
    qualification_evidence = _group(
        records=records,
        record_type="TABLE_QUALIFICATION_EVIDENCE",
        expected=1,
    )[0]
    unit = review_units[0]
    payload = strict_json_file(
        path=run_dir / str(attempt["reader_payload_path"]),
    )
    if not isinstance(payload, dict):
        raise RatchetReleaseError("Qualification Reader payload is malformed")
    replayed_evidence = check_evidence(
        candidate=candidate,
        derived_asset=derived,
        reader_manifest=reader_manifest,
        reader_payload_body=payload,
        source_references=manifest["source_references"],
        identity_constraints=unit["compiled_spec"]["identity_constraints"],
        scope_contract=unit["compiled_spec"]["scope_contract"],
    )
    if replayed_evidence != evidence or evidence["status"] != "PASS":
        raise RatchetReleaseError("Qualification Evidence replay differs")
    decision = next(iter(effective.values()))
    if (
        decision["decision"] != "APPROVE"
        or unit["evidence_check_id"] != evidence["evidence_check_id"]
        or unit["selected"] != candidate["selected"]
    ):
        raise RatchetReleaseError("Qualification Review binding differs")

    observations = _group(
        records=records, record_type="VERIFIED_OBSERVATION", expected=1,
    )
    results = _group(records=records, record_type="METRIC_RESULT", expected=1)
    traces = _group(records=records, record_type="EXECUTION_TRACE", expected=1)
    result = results[0]
    trace = traces[0]
    spec_paths = [repo_root / relative for relative in manifest["spec_file_hashes"]]
    if any(
        sha256_file(path=repo_root / relative) != digest
        for relative, digest in manifest["spec_file_hashes"].items()
    ):
        raise RatchetReleaseError("Qualification MetricSpec bytes differ")
    compiled = compile_spec_files(paths=spec_paths)
    if set(compiled) != {result["metric_id"]}:
        raise RatchetReleaseError("Qualification MetricSpec exact set differs")
    expected_result, expected_trace = calculate_observation_metric(
        compiled_spec=compiled[str(result["metric_id"])],
        target={
            field: trace["calculation_target"][field]
            for field in (
                "company_id", "period_start", "period_end", "scope",
                "scope_key",
            )
        },
        company_traits=manifest["company_traits"],
        observation=observations[0],
    )
    if (
        result != expected_result
        or trace != expected_trace
        or result["publication"] != "PUBLISHED"
        or result["quality"] != "EXACT"
    ):
        raise RatchetReleaseError("Qualification Result replay differs")

    raw_response = strict_json_file(
        path=run_dir / str(attempt["raw_response_path"]),
    )
    if not isinstance(raw_response, dict) or not isinstance(
        raw_response.get("usage"), dict
    ):
        raise RatchetReleaseError("Qualification provider usage is absent")
    usage = raw_response["usage"]
    if (
        type(usage.get("prompt_tokens")) is not int
        or usage["prompt_tokens"] > 200000
        or type(usage.get("completion_tokens")) is not int
        or type(usage.get("total_tokens")) is not int
        or usage["total_tokens"]
        != usage["prompt_tokens"] + usage["completion_tokens"]
        or attempt["status"] != "SUCCEEDED"
        or attempt["transport_observation"]["egress_attempted"] is not True
        or attempt["transport_observation"]["retry_count"] != 0
        or qualification_evidence["attempt_id"] != attempt["attempt_id"]
    ):
        raise RatchetReleaseError("Qualification terminal usage differs")
    return manifest, records, decisions


def load_portable_qualification_run(
    run_dir: Path, repo_root: Path,
) -> Tuple[Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]]:
    """Replay a closure-hashed qualification Run without mutable Git state."""
    return _validate_committed_qualification_run(
        repo_root=repo_root, run_dir=run_dir, origin=None,
    )


def validate_portable_qualification_binding(
    *, repo_root: Path, binding: Mapping[str, object],
) -> Dict[str, object]:
    """Rebuild the complete ratchet qualification binding inside a bundle."""
    required = {
        "cycle_id", "family_id", "fresh_samples_required",
        "ledger_row_count", "ledger_sha256", "release_plan_content_id",
        "selected_run_ids", "terminal_validations",
    }
    if set(binding) != required:
        raise RatchetReleaseError("Portable qualification fields differ")
    cycle_id = str(binding["cycle_id"])
    cycle_hex = cycle_id.split(":", maxsplit=1)[-1]
    ledger_path = (
        repo_root / QUALIFICATION_FREEZE_ROOT / "cycles" / cycle_hex
        / "provider_ledger.jsonl"
    )
    rows = [
        strict_json_loads(text=line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if (
        len(rows) != binding["ledger_row_count"]
        or sha256_file(path=ledger_path) != binding["ledger_sha256"]
        or any(not isinstance(row, dict) for row in rows)
        or any(
            row["qualification_cycle_id"] != cycle_id
            or row["family_id"] != binding["family_id"]
            for row in rows
        )
    ):
        raise RatchetReleaseError("Portable qualification ledger differs")
    task_ids = sorted({str(row["task_contract_id"]) for row in rows})
    fresh_count = int(binding["fresh_samples_required"])
    expected_coordinates = {
        (task_id, "SECOND_LAYOUT", 1) for task_id in task_ids
    } | {
        (task_id, "POST_FREEZE_HOLDOUT", 1) for task_id in task_ids
    } | {
        (task_id, "FRESH_STABILITY", ordinal)
        for task_id in task_ids for ordinal in range(1, fresh_count + 1)
    }
    actual_coordinates = {
        (
            str(row["task_contract_id"]),
            str(row["qualification_phase"]),
            int(row["qualification_ordinal"]),
        )
        for row in rows
    }
    if (
        actual_coordinates != expected_coordinates
        or len(rows) != len(expected_coordinates)
        or len({str(row["attempt_id"]) for row in rows}) != len(rows)
        or len({str(row["provider_request_id"]) for row in rows}) != len(rows)
    ):
        raise RatchetReleaseError("Portable qualification exact set differs")
    validations = []
    selected = {}
    for row in sorted(
        rows,
        key=lambda value: (
            str(value["qualification_phase"]),
            int(value["qualification_ordinal"]),
            str(value["task_contract_id"]),
        ),
    ):
        authorization = row["qualification_authorization"]
        run_dir = repo_root / str(authorization["run_directory_relative_path"])
        manifest, records, _decisions = load_portable_qualification_run(
            run_dir, repo_root,
        )
        result = _group(
            records=records, record_type="METRIC_RESULT", expected=1,
        )[0]
        validations.append({
            "attempt_id": row["attempt_id"],
            "metric_id": result["metric_id"],
            "phase": row["qualification_phase"],
            "ordinal": row["qualification_ordinal"],
            "provider_request_id": row["provider_request_id"],
            "run_id": manifest["run_id"],
            "terminal_id": authorization["qualification_terminal_id"],
        })
        if (
            row["qualification_phase"] == "FRESH_STABILITY"
            and int(row["qualification_ordinal"]) == fresh_count
        ):
            selected[str(result["metric_id"])] = manifest["run_id"]
    plans = load_issue15_release_plans(repo_root=repo_root)
    current_plan = plans["plans"][-1]
    rebuilt = {
        "cycle_id": cycle_id,
        "family_id": binding["family_id"],
        "fresh_samples_required": fresh_count,
        "ledger_row_count": len(rows),
        "ledger_sha256": sha256_file(path=ledger_path),
        "release_plan_content_id": current_plan["release_plan_content_id"],
        "selected_run_ids": dict(sorted(selected.items())),
        "terminal_validations": validations,
    }
    if rebuilt != dict(binding):
        raise RatchetReleaseError("Portable qualification binding differs")
    return rebuilt


def _qualification_cycle(
    *, repo_root: Path, workspace: Path,
) -> Dict[str, object]:
    """Copy and validate the complete current table qualification cycle."""
    plans = load_issue15_release_plans(repo_root=repo_root)
    plan = plans["plans"][-1]
    subset = plan["qualification_matrix_subset"]
    family_ids = sorted({str(row["reader_family_id"]) for row in subset})
    if plan["release_stage"] != "R3" or len(family_ids) != 1:
        raise RatchetReleaseError("R3 qualification family exact set differs")
    family_id = family_ids[0]
    matrix = load_table_qualification_matrix(repo_root=repo_root)
    if family_id not in matrix["entries"]:
        raise RatchetReleaseError("R3 qualification matrix entry is absent")
    entry = matrix["entries"][family_id]
    task_ids = list(entry["task_contract_ids"])
    contracts = load_table_task_contracts(repo_root=repo_root)
    metric_by_task = {
        str(contract["task_contract_id"]): list(contract["metric_ids"])
        for contract in contracts["contracts"]
        if contract["task_contract_id"] in set(task_ids)
    }
    if (
        set(metric_by_task) != set(task_ids)
        or sorted(metric for values in metric_by_task.values() for metric in values)
        != list(plan["added_metric_ids"])
        or any(len(values) != 1 for values in metric_by_task.values())
    ):
        raise RatchetReleaseError("R3 task-to-metric exact set differs")

    pointer = strict_json_file(path=repo_root / QUALIFICATION_POINTER)
    if not isinstance(pointer, dict):
        raise RatchetReleaseError("Qualification freeze pointer is malformed")
    cycle_id = str(pointer["qualification_cycle_id"])
    cycle_hex = cycle_id.split(":", maxsplit=1)[-1]
    cycle_root = repo_root / QUALIFICATION_CYCLE_ROOT / cycle_hex
    ledger_path = (
        repo_root / QUALIFICATION_FREEZE_ROOT / "cycles" / cycle_hex
        / "provider_ledger.jsonl"
    )
    rows = [
        strict_json_loads(text=line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise RatchetReleaseError("Qualification ledger is malformed")
    expected_coordinates = {
        (task_id, "SECOND_LAYOUT", 1) for task_id in task_ids
    } | {
        (task_id, "POST_FREEZE_HOLDOUT", 1) for task_id in task_ids
    } | {
        (task_id, "FRESH_STABILITY", ordinal)
        for task_id in task_ids
        for ordinal in range(1, int(entry["fresh_samples_required"]) + 1)
    }
    actual_coordinates = {
        (
            str(row["task_contract_id"]),
            str(row["qualification_phase"]),
            int(row["qualification_ordinal"]),
        )
        for row in rows
    }
    if (
        actual_coordinates != expected_coordinates
        or len(rows) != len(expected_coordinates)
        or len({str(row["attempt_id"]) for row in rows}) != len(rows)
        or len({str(row["provider_request_id"]) for row in rows}) != len(rows)
    ):
        raise RatchetReleaseError("Qualification cycle exact set differs")

    copied_root = workspace / "qualification_runs"
    copied_root.mkdir(parents=True, exist_ok=True)
    origin_by_run_id: Dict[str, Dict[str, str]] = {}
    rows_by_run_id: Dict[str, Dict[str, object]] = {}
    run_dirs: List[Path] = []
    selected_by_metric: Dict[str, Path] = {}
    validations = []
    for row in sorted(
        rows,
        key=lambda value: (
            str(value["qualification_phase"]),
            int(value["qualification_ordinal"]),
            str(value["task_contract_id"]),
        ),
    ):
        authorization = row["qualification_authorization"]
        terminal_id = str(authorization["qualification_terminal_id"])
        source_run = cycle_root / "runs" / terminal_id.split(":", maxsplit=1)[-1]
        copied = copied_root / terminal_id.split(":", maxsplit=1)[-1]
        origin = _committed_run_origin(repo_root=repo_root, run_dir=source_run)
        _copy_exact_tree(source=source_run, destination=copied)
        manifest = _read_manifest(run_dir=copied)
        origin_by_run_id[str(manifest["run_id"])] = origin
        rows_by_run_id[str(manifest["run_id"])] = dict(row)
        run_dirs.append(copied)

    cache: Dict[str, Tuple[
        Dict[str, object], List[Dict[str, object]], List[Dict[str, object]],
    ]] = {}
    signatures: Dict[str, Dict[str, Dict[str, object]]] = {}

    def committed_loader(
        run_dir: Path, loader_repo_root: Path,
    ) -> Tuple[
        Dict[str, object], List[Dict[str, object]], List[Dict[str, object]],
    ]:
        manifest = _read_manifest(run_dir=run_dir)
        run_id = str(manifest["run_id"])
        if "qualification_authorization" not in manifest:
            return load_frozen_run(
                run_dir=run_dir, repo_root=loader_repo_root,
            )
        if run_id not in origin_by_run_id:
            raise RatchetReleaseError("Qualification Run is outside cycle")
        signature = _tree_files(root=run_dir)
        if run_id in cache:
            if signatures[run_id] != signature:
                raise RatchetReleaseError("Cached qualification Run changed")
            return cache[run_id]
        loaded = _validate_committed_qualification_run(
            repo_root=loader_repo_root,
            run_dir=run_dir,
            origin=origin_by_run_id[run_id],
        )
        cache[run_id] = loaded
        signatures[run_id] = signature
        return loaded

    for copied in run_dirs:
        manifest, records, _decisions = committed_loader(copied, repo_root)
        row = rows_by_run_id[str(manifest["run_id"])]
        result = _group(
            records=records, record_type="METRIC_RESULT", expected=1,
        )[0]
        metric_ids = metric_by_task[str(row["task_contract_id"])]
        if result["metric_id"] != metric_ids[0]:
            raise RatchetReleaseError("Qualification terminal metric differs")
        validations.append({
            "attempt_id": row["attempt_id"],
            "metric_id": result["metric_id"],
            "phase": row["qualification_phase"],
            "ordinal": row["qualification_ordinal"],
            "provider_request_id": row["provider_request_id"],
            "run_id": manifest["run_id"],
            "terminal_id": manifest["qualification_authorization"][
                "qualification_terminal_id"
            ],
        })
        if (
            row["qualification_phase"] == "FRESH_STABILITY"
            and int(row["qualification_ordinal"])
            == int(entry["fresh_samples_required"])
        ):
            selected_by_metric[str(result["metric_id"])] = copied
    if set(selected_by_metric) != set(plan["added_metric_ids"]):
        raise RatchetReleaseError("R3 production terminal exact set differs")

    production_freeze = cycle_root / "production_semantic_freeze.json"
    freeze_receipt = repo_root / str(pointer["receipt_path"])
    closure_files = {
        "provider_ledger.jsonl": ledger_path.read_bytes(),
        "production_semantic_freeze.json": production_freeze.read_bytes(),
        "table_qualification_freeze.json": freeze_receipt.read_bytes(),
        "table_qualification_freeze_pointer.json": (
            repo_root / QUALIFICATION_POINTER
        ).read_bytes(),
    }
    summary = {
        "cycle_id": cycle_id,
        "family_id": family_id,
        "fresh_samples_required": entry["fresh_samples_required"],
        "ledger_row_count": len(rows),
        "ledger_sha256": sha256_file(path=ledger_path),
        "release_plan_content_id": plan["release_plan_content_id"],
        "selected_run_ids": {
            metric_id: _read_manifest(run_dir=selected)["run_id"]
            for metric_id, selected in sorted(selected_by_metric.items())
        },
        "terminal_validations": validations,
    }
    return {
        "closure_authority_paths": sorted({
            _relative(repo_root=repo_root, candidate=ledger_path),
            _relative(repo_root=repo_root, candidate=production_freeze),
            _relative(repo_root=repo_root, candidate=freeze_receipt),
            QUALIFICATION_POINTER.as_posix(),
            *(
                _relative(repo_root=repo_root, candidate=source_run / relative)
                for source_run in (
                    repo_root / str(row["qualification_authorization"][
                        "run_directory_relative_path"
                    ])
                    for row in rows
                )
                for relative in _tree_files(root=source_run)
            ),
        }),
        "closure_files": closure_files,
        "committed_loader": committed_loader,
        "family_id": family_id,
        "matrix_entry": entry,
        "plan": plan,
        "selected_run_dirs": selected_by_metric,
        "summary": summary,
        "task_ids": task_ids,
    }


def _structural_runs(
    *, repo_root: Path, workspace: Path, qualification: Mapping[str, object],
) -> List[Path]:
    """Materialize FROZEN zero-egress rows for structurally false companies."""
    selected = qualification["selected_run_dirs"]
    selected_manifests = {
        metric_id: _read_manifest(run_dir=run_dir)
        for metric_id, run_dir in selected.items()
    }
    applicable_companies = {
        str(manifest["company_id"]) for manifest in selected_manifests.values()
    }
    if len(applicable_companies) != 1:
        raise RatchetReleaseError("R3 applicable company exact set differs")
    applicable_company = next(iter(applicable_companies))
    sample_authorization = next(iter(selected_manifests.values()))[
        "qualification_authorization"
    ]
    source = sample_authorization["source_binding"]
    declaration = source["source_declaration"]
    target_period = sample_authorization["target_period"]
    plan = qualification["plan"]
    task_ids = qualification["task_ids"]
    contracts = load_table_task_contracts(repo_root=repo_root)
    task_by_metric = {
        str(contract["metric_ids"][0]): str(contract["task_contract_id"])
        for contract in contracts["contracts"]
        if contract["task_contract_id"] in set(task_ids)
    }
    if set(task_by_metric) != set(plan["added_metric_ids"]):
        raise RatchetReleaseError("R3 structural task exact set differs")
    registry_path = repo_root / "config/company_registry.csv"
    with registry_path.open(mode="r", encoding="utf-8", newline="") as stream:
        companies = [dict(row) for row in csv.DictReader(stream)]
    structural_root = workspace / "structural_runs"
    structural_root.mkdir(parents=True, exist_ok=True)
    run_dirs = []
    for company in companies:
        company_id = str(company["company_id"])
        if company_id == applicable_company:
            continue
        for metric_id in plan["added_metric_ids"]:
            task_id = task_by_metric[str(metric_id)]
            identity = content_hash(value={
                "company_id": company_id,
                "metric_id": metric_id,
                "release_plan_content_id": plan["release_plan_content_id"],
                "target_period": target_period,
                "task_contract_id": task_id,
            }).split(":", maxsplit=1)[1]
            run_dir = structural_root / identity
            if not run_dir.exists():
                result = create_table_task_review_run(
                    repo_root=repo_root,
                    run_dir=run_dir,
                    run_id="run:ratchet:structural:" + identity,
                    company_id=company_id,
                    target_period=target_period,
                    source_repo_relative_path=declaration[
                        "source_repo_relative_path"
                    ],
                    source_media_type=sample_authorization["source_media_type"],
                    source_url=source["source_url"],
                    accession=declaration["accession"],
                    document_name=declaration["document_name"],
                    source_role=source["source_role"],
                    request_attempt_id=source["request_attempt_id"],
                    task_contract_id=task_id,
                    adapter=build_recorded_adapter(
                        response_bytes=b"{}",
                        fixture_id="ratchet-structural-zero-egress",
                    ),
                    clock=None,
                )
                if result["status"] != "N_A_STRUCTURAL":
                    raise RatchetReleaseError("Structural Run is not N/A")
                validate_and_freeze_run(run_dir=run_dir, repo_root=repo_root)
            manifest, records, _decisions = load_frozen_run(
                run_dir=run_dir, repo_root=repo_root,
            )
            results = _group(
                records=records, record_type="METRIC_RESULT", expected=1,
            )
            attempts = [
                row for row in records
                if row["record_type"] == "AI_EXTRACTION_ATTEMPT"
            ]
            if (
                manifest["company_id"] != company_id
                or results[0]["metric_id"] != metric_id
                or results[0]["applicability"] != "N_A_STRUCTURAL"
                or results[0]["publication"] != "PUBLISHED"
                or attempts
            ):
                raise RatchetReleaseError("Structural Run replay differs")
            run_dirs.append(run_dir)
    expected = (
        len(companies) - len(applicable_companies)
    ) * len(plan["added_metric_ids"])
    if len(run_dirs) != expected:
        raise RatchetReleaseError("Structural Run exact set differs")
    return run_dirs


def _write_validation_receipt(
    *, repo_root: Path, staging_dir: Path,
    projection: Mapping[str, object], ledger_binding: Mapping[str, object],
    previous_publication_id: str, parent_requirement_hashes: Mapping[str, str],
) -> Dict[str, object]:
    """Write the existing generic publication ValidationReceipt shape."""
    files = _read_staging_files(
        staging_dir=staging_dir, include_receipt=False,
    )
    evidence = _publication_gate_evidence(
        files=files,
        projection=projection,
        repo_root=repo_root,
        ledger_binding=ledger_binding,
    )
    body = {
        "status": "PASSED",
        "view_id": publication_validation_view_id(
            files=files,
            requirement_hashes=parent_requirement_hashes,
            batch_manifest_id=projection["batch_manifest_id"],
            projection_manifest_id=projection["projection_manifest_id"],
            ledger_binding=ledger_binding,
            previous_publication_id=previous_publication_id,
        ),
        "checks": [
            {
                "check": check,
                "evidence_hash": content_hash(value=evidence[check]),
                "status": "PASS",
            }
            for check in sorted(REQUIRED_PUBLICATION_CHECKS)
        ],
        "artifact_hashes": {
            relative: {
                "sha256": sha256_bytes(content=files[relative]),
                "size": len(files[relative]),
            }
            for relative in sorted(files)
        },
    }
    receipt = validate_record(record={
        **body,
        "record_type": "VALIDATION_RECEIPT",
        "validation_receipt_id": content_hash(value=body),
    })
    atomic_write_json(
        path=staging_dir / "publication_validation_receipt.json",
        value=receipt,
    )
    return receipt


def _ratchet_authority_paths(
    *, repo_root: Path, qualification: Mapping[str, object],
) -> List[str]:
    """Return repository authority needed for portable child-plan replay."""
    paths = set(qualification["closure_authority_paths"])
    run_record_paths = [
        relative for relative in paths if relative.endswith("/records.jsonl")
    ]
    for relative in run_record_paths:
        for record in _read_jsonl(path=repo_root / relative):
            if record["record_type"] == "RAW_BLOB":
                paths.add(str(record["storage_uri"]))
    paths.update({
        "catalog/deterministic_metrics.json",
        "catalog/event_routes.json",
        "catalog/table_task_contracts.json",
        "catalog/zero_ai_public_projection.json",
        "config/issue_15_release_plan.json",
        "config/provider_model_runtime.json",
        "config/source_strategy_fallback_representation.json",
        "config/source_strategy_registry.json",
        "config/table_qualification_matrix.json",
    })
    index = strict_json_file(
        path=repo_root / "config/issue_15_release_plan.json",
    )
    if not isinstance(index, dict) or not isinstance(
        index.get("release_plan_paths"), list,
    ):
        raise RatchetReleaseError("ReleasePlan index is malformed")
    paths.update(str(row["path"]) for row in index["release_plan_paths"])
    requirement_root = repo_root / "requirements/issue_15_v1"
    for candidate in requirement_root.rglob("*"):
        if candidate.is_symlink():
            raise RatchetReleaseError("Issue #15 authority contains a symlink")
        if candidate.is_file():
            paths.add(candidate.relative_to(repo_root).as_posix())
    foundation = strict_json_file(
        path=requirement_root / "foundation_verification_receipt.json",
    )
    pending: List[object] = [foundation]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, str):
            relative = Path(value)
            candidate = repo_root / relative
            if (
                not relative.is_absolute()
                and ".." not in relative.parts
                and candidate.is_file()
                and not candidate.is_symlink()
            ):
                paths.add(relative.as_posix())
    for relative in paths:
        candidate = repo_root / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise RatchetReleaseError("Ratchet authority file is unavailable")
    return sorted(paths)


def _legacy_baseline_bundle(
    *, repo_root: Path, predecessor: PublicationView,
) -> Path:
    """Return the immutable imported legacy A used only for compatibility."""
    current = predecessor.bundle_dir
    while True:
        manifest = verify_publication_bundle(bundle_dir=current)
        if (current / "internal/legacy_baseline_import.json").is_file():
            return current
        previous = manifest["previous_publication_id"]
        if previous is None:
            raise RatchetReleaseError("Publication chain lacks legacy baseline")
        current = repo_root / "outputs/publications" / str(previous)


def prepare_r3_successor(
    *, repo_root: Path, publication_root: Path, source_commit: str,
    validated_at_utc: str, workspace: Optional[Path] = None,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Prepare one R3 successor without mutating the active pointer."""
    current_workspace = (
        repo_root / RATCHET_WORKSPACE / source_commit
        if workspace is None else workspace
    )
    if current_workspace.is_symlink() or (
        current_workspace.exists() and not current_workspace.is_dir()
    ):
        raise RatchetReleaseError("R3 workspace is unsafe")
    current_workspace.mkdir(parents=True, exist_ok=True)
    predecessor = PublicationView.open(publication_root=repo_root)
    predecessor_plan = strict_json_file(
        path=predecessor.bundle_dir / "internal/issue15_release_plan.json",
    )
    if not isinstance(predecessor_plan, dict):
        raise RatchetReleaseError("R3 predecessor plan is malformed")
    qualification = _qualification_cycle(
        repo_root=repo_root, workspace=current_workspace,
    )
    plan = qualification["plan"]
    if (
        predecessor_plan["release_plan_content_id"]
        != plan["parent_release_plan_content_id"]
        or predecessor_plan["release_plan_id"]
        != plan["parent_release_plan_id"]
    ):
        raise RatchetReleaseError("R3 predecessor plan differs")
    structural = _structural_runs(
        repo_root=repo_root,
        workspace=current_workspace,
        qualification=qualification,
    )
    batch_run_dirs = [
        *qualification["selected_run_dirs"].values(), *structural,
    ]
    release_input_plan_id = content_hash(value={
        "predecessor_publication_id": predecessor.publication_id,
        "qualification": qualification["summary"],
        "release_plan_content_id": plan["release_plan_content_id"],
        "structural_run_ids": sorted(
            _read_manifest(run_dir=run_dir)["run_id"] for run_dir in structural
        ),
    })
    batch_manifest_path = current_workspace / "batch_manifest.json"
    loader = qualification["committed_loader"]
    batch = write_projection_batch_manifest(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        run_dirs=batch_run_dirs,
        release_input_plan_id=release_input_plan_id,
        release_id=plan["release_plan_id"],
        release_plan_root=repo_root,
        run_loader=loader,
    )
    staging = current_workspace / "staging"
    legacy_baseline = _legacy_baseline_bundle(
        repo_root=repo_root, predecessor=predecessor,
    )
    candidate = write_projection_candidate(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_baseline,
        staging_dir=staging,
        public_predecessor_dir=predecessor.bundle_dir,
        release_plan_root=repo_root,
        run_loader=loader,
    )
    if candidate["compatibility_status"] != "PASS":
        raise RatchetReleaseError("R3 strict compatibility did not PASS")
    parent = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/ai_first_v3_3_1",
    )
    projection = build_projection_manifest(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_baseline,
        staging_dir=staging,
        public_predecessor_dir=predecessor.bundle_dir,
        release_plan_root=repo_root,
        run_loader=loader,
        projection_requirement_hashes=parent["hashes"],
    )
    atomic_write_json(path=staging / "projection_manifest.json", value=projection)
    context = {
        "batch_manifest_id": projection["batch_manifest_id"],
        "projection_manifest": projection,
        "projection_manifest_id": projection["projection_manifest_id"],
        "requirement_hashes": projection["requirement_hashes"],
    }
    _finalize_staging_view(
        repo_root=repo_root,
        staging_dir=staging,
        context=context,
        validated_at_utc=validated_at_utc,
        validation_mode=FORMAL_VALIDATION_MODE,
        source_commit=source_commit,
    )
    ledger_binding = publication_ledger_binding(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        validation_tier=FORMAL_VALIDATION_MODE,
        release_plan_root=repo_root,
        run_loader=loader,
    )
    receipt = _write_validation_receipt(
        repo_root=repo_root,
        staging_dir=staging,
        projection=projection,
        ledger_binding=ledger_binding,
        previous_publication_id=predecessor.publication_id,
        parent_requirement_hashes=parent["hashes"],
    )
    public_files = _read_staging_files(
        staging_dir=staging, include_receipt=True,
    )
    metrics = list(csv.DictReader(io.StringIO(
        public_files["metrics_matrix.csv"].decode("utf-8")
    )))
    predecessor_metrics = list(csv.DictReader(io.StringIO(
        predecessor.read_bytes(relative_path="metrics_matrix.csv").decode("utf-8")
    )))
    public_keys = {(row["company"], row["metric_id"]) for row in metrics}
    predecessor_keys = {
        (row["company"], row["metric_id"]) for row in predecessor_metrics
    }
    with (repo_root / "config/company_registry.csv").open(
        mode="r", encoding="utf-8", newline="",
    ) as stream:
        display_names = [
            str(row["display_name"]) for row in csv.DictReader(stream)
        ]
    delta_public_keys = {
        (display_name, str(metric_id))
        for display_name in display_names
        for metric_id in plan["added_metric_ids"]
    }
    expected_public_keys = predecessor_keys | delta_public_keys
    added_rows = [
        row for row in metrics
        if (row["company"], row["metric_id"]) not in predecessor_keys
    ]
    if (
        len(batch["expected_result_keys"])
        != len(plan["added_metric_ids"]) * 10
        or len(plan["cumulative_vnext_result_keys"])
        != len(plan["cumulative_metric_ids"]) * 10
        or public_keys != expected_public_keys
        or any(row["status"] != "N_A_STRUCTURAL" for row in added_rows)
    ):
        raise RatchetReleaseError("R3 public key set differs")
    closure = _portable_closure_files(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        ledger_binding=ledger_binding,
        include_cutover_qualification=False,
        validation_tier=FORMAL_VALIDATION_MODE,
        release_plan_root=repo_root,
        run_loader=loader,
        additional_authority_paths=_ratchet_authority_paths(
            repo_root=repo_root, qualification=qualification,
        ),
        qualification_binding_override=qualification["summary"],
    )
    files = {**public_files, **closure}
    layout = publication_layout(publication_root=publication_root)
    successor = _write_prepared_publication_bundle(
        publications_dir=Path(layout["publications_dir"]),
        files=files,
        requirement_hashes=parent["hashes"],
        batch_manifest_id=str(batch["batch_manifest_id"]),
        projection_manifest_id=str(projection["projection_manifest_id"]),
        validation_receipt_id=str(receipt["validation_receipt_id"]),
        ledger_binding=ledger_binding,
        previous_publication_id=predecessor.publication_id,
    )
    summary = {
        "batch_manifest_id": batch["batch_manifest_id"],
        "previous_publication_id": predecessor.publication_id,
        "projection_manifest_id": projection["projection_manifest_id"],
        "public_matrix_row_count": len(metrics),
        "public_key_set_hash": content_hash(value=sorted(public_keys)),
        "qualification": qualification["summary"],
        "release_input_plan_id": release_input_plan_id,
        "release_plan_content_id": plan["release_plan_content_id"],
        "release_plan_id": plan["release_plan_id"],
        "source_commit": source_commit,
        "validation_receipt_id": receipt["validation_receipt_id"],
    }
    return successor, summary


def _read_back(
    *, repo_root: Path, publication_id: str,
) -> Dict[str, object]:
    """Validate active files, root mirrors, predecessor, and complete bundle."""
    view = PublicationView.open(publication_root=repo_root)
    if view.publication_id != publication_id:
        raise RatchetReleaseError("R3 active publication differs")
    manifest = verify_publication_bundle(bundle_dir=view.bundle_dir)
    predecessor_id = str(manifest["previous_publication_id"])
    predecessor_dir = repo_root / "outputs/publications" / predecessor_id
    predecessor = verify_publication_bundle(bundle_dir=predecessor_dir)
    hashes = {}
    for relative in sorted(REQUIRED_BUNDLE_FILES):
        content = view.read_bytes(relative_path=relative)
        mirror = repo_root / ROOT_MIRROR_RELATIVE_PATHS[relative]
        if mirror.read_bytes() != content:
            raise RatchetReleaseError("R3 root mirror differs")
        hashes[relative] = sha256_bytes(content=content)
    state = publication_state_snapshot(publication_root=repo_root)
    if state["active_publication_id"] != publication_id:
        raise RatchetReleaseError("R3 publication state differs")
    body = {
        "active_publication_id": publication_id,
        "artifact_hashes": hashes,
        "mirror_hashes": state["mirror_hashes"],
        "predecessor_manifest_id": predecessor["publication_id"],
        "predecessor_publication_id": predecessor_id,
        "status": "PASSED",
    }
    return {**body, "read_back_proof_id": content_hash(value=body)}


def _persist_receipts(
    *, repo_root: Path, receipts: Mapping[str, Mapping[str, object]],
) -> Dict[str, object]:
    """Persist content-addressed R3 receipts and one stable role index."""
    receipt_dir = repo_root / "outputs/ratchet_release_receipts/r3"
    if receipt_dir.is_symlink() or (
        receipt_dir.exists() and not receipt_dir.is_dir()
    ):
        raise RatchetReleaseError("R3 receipt directory is unsafe")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    bindings = {}
    for role in sorted(receipts):
        content = _json_bytes(value=receipts[role])
        digest = sha256_bytes(content=content)
        destination = receipt_dir / (digest + ".json")
        if destination.exists() and destination.read_bytes() != content:
            raise RatchetReleaseError("R3 content-addressed receipt differs")
        if not destination.exists():
            atomic_write_bytes(path=destination, content=content)
        bindings[role] = {
            "path": destination.relative_to(repo_root).as_posix(),
            "sha256": digest,
            "size": len(content),
        }
    body = {"status": "PASSED", "receipts": bindings}
    index = {**body, "receipt_index_id": content_hash(value=body)}
    atomic_write_json(path=receipt_dir / "index.json", value=index)
    return index


def publish_r3(
    *, repo_root: Path, source_commit: str, committed_at_utc: str,
) -> Dict[str, object]:
    """Prepare, commit, and actively read back the R3 ratchet successor."""
    if len(source_commit) != 40:
        raise RatchetReleaseError("R3 source commit must be a full SHA")
    source_snapshot = capture_source_snapshot(workdir=repo_root)
    if source_snapshot.source_commit != source_commit:
        raise RatchetReleaseError("R3 source snapshot differs from HEAD")
    predecessor = PublicationView.open(publication_root=repo_root)
    successor, summary = prepare_r3_successor(
        repo_root=repo_root,
        publication_root=repo_root,
        source_commit=source_commit,
        validated_at_utc=committed_at_utc,
    )
    pointer = _commit_publication(
        publication_root=repo_root,
        publication_id=str(successor["publication_id"]),
        expected_active_publication_id=predecessor.publication_id,
        committed_at_utc=committed_at_utc,
    )
    read_back = _read_back(
        repo_root=repo_root,
        publication_id=str(successor["publication_id"]),
    )
    index = _persist_receipts(
        repo_root=repo_root,
        receipts={
            "active_terminal": pointer,
            "immutable_read_back": read_back,
            "predecessor_r2": predecessor.manifest,
            "successor_publication": successor,
        },
    )
    publish_validation_snapshot(
        workdir=repo_root, source_snapshot=source_snapshot,
    )
    return {
        **summary,
        "active_publication_id": successor["publication_id"],
        "committed_at_utc": committed_at_utc,
        "receipt_index_id": index["receipt_index_id"],
        "receipt_index_path": "outputs/ratchet_release_receipts/r3/index.json",
    }
