"""Project migrated results into complete legacy-compatible row collections."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Set, Tuple

from .canonical import CanonicalError, content_hash, sha256_file
from .canonical import strict_json_file
from .records import metric_result_contract_hash
from .run_store import RunStoreError, load_frozen_run
from .states import publication_candidate_status


RowKey = Tuple[str, str]


class ProjectionError(ValueError):
    """Report incomplete, duplicate, incompatible, or withheld projection."""


RELEASE_PLAN_FIELDS = {
    "migrated_metric_ids",
    "release_id",
    "schema_version",
}
LEGACY_INPUT_FILES = (
    "metric_evidence.csv",
    "metrics_matrix.csv",
)
PROJECTION_CANDIDATE_FILES = (
    "metric_evidence.csv",
    "metrics_matrix.csv",
)
PROJECTION_GATE_FILES = (
    "golden_results.csv",
    "legacy_invariant_migration_receipt.json",
    "repair_validation_results.csv",
)


def projection_file_hashes(
    *, root: Path, relative_paths: Sequence[str], label: str
) -> Dict[str, str]:
    """Hash one fixed set of real projection input files.

    Args:
        root: Stable legacy snapshot or staging locator.
        relative_paths: Repository-defined required file names.
        label: Diagnostic identity.

    Returns:
        Isolated mapping.

    Raises:
        ProjectionError: When the root/file is missing, aliased, or unsafe.
    """
    if root.is_symlink() or not root.is_dir():
        raise ProjectionError("{} root is unsafe or missing".format(label))
    hashes = {}
    for relative in relative_paths:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ProjectionError(
                "{} file is unsafe or missing: {}".format(label, relative)
            )
        hashes[relative] = sha256_file(path=path)
    return hashes


def load_release_plan(*, repo_root: Path) -> Tuple[Dict[str, object], str]:
    """Load the repository-owned vNext migration set.

    Args:
        repo_root: Repository containing ``config/vnext_release_plan.json``.

    Returns:
        Strict release plan and its exact file SHA-256.

    Raises:
        ProjectionError: On unsafe, malformed, or ambiguous release input.
    """
    path = repo_root / "config" / "vnext_release_plan.json"
    if path.is_symlink() or not path.is_file():
        raise ProjectionError("vNext release plan is unsafe or missing")
    try:
        parsed = strict_json_file(
            path=path, allowed_fields=RELEASE_PLAN_FIELDS,
        )
    except CanonicalError as error:
        raise ProjectionError("vNext release plan is invalid") from error
    if not isinstance(parsed, dict) or set(parsed) != RELEASE_PLAN_FIELDS:
        raise ProjectionError("vNext release plan fields are not exact")
    metric_ids = parsed["migrated_metric_ids"]
    if (
        type(parsed["schema_version"]) is not int
        or parsed["schema_version"] != 1
        or type(parsed["release_id"]) is not str
        or not parsed["release_id"]
        or type(metric_ids) is not list
        or not metric_ids
        or any(
            type(metric_id) is not str or not metric_id
            for metric_id in metric_ids
        )
        or len(metric_ids) != len(set(metric_ids))
    ):
        raise ProjectionError("vNext release plan values are invalid")
    return dict(parsed), sha256_file(path=path)


def _row_key(*, row: Mapping[str, object]) -> RowKey:
    """Return the legacy compatibility key.

    Args:
        row: Legacy metric/evidence row.

    Returns:
        Company and metric identity.

    Raises:
        ProjectionError: When either field is missing or empty.
    """
    for field in ("company", "metric_id"):
        if (
            field not in row
            or not isinstance(row[field], str)
            or not row[field]
        ):
            raise ProjectionError("Projection row lacks {}".format(field))
    return str(row["company"]), str(row["metric_id"])


def project_metric_rows(
    *,
    legacy_rows: Sequence[Mapping[str, object]],
    migrated_keys: Set[RowKey],
    replacement_rows: Mapping[RowKey, Mapping[str, object]],
    fieldnames: Sequence[str],
) -> List[Dict[str, object]]:
    """Replace migrated rows in place while preserving all other row bytes.

    Args:
        legacy_rows: Complete ordered legacy matrix.
        migrated_keys: Exact company/metric keys controlled by vNext.
        replacement_rows: One replacement for each migrated key.
        fieldnames: Exact legacy schema order.

    Returns:
        Complete projected matrix with stable legacy position.

    Raises:
        ProjectionError: On duplicate legacy key, incomplete replacement,
            unknown fields, or extra replacement.
    """
    missing = sorted(migrated_keys - set(replacement_rows))
    extra = sorted(set(replacement_rows) - migrated_keys)
    if missing or extra:
        raise ProjectionError("Migrated metric replacement exact set differs")
    for key in replacement_rows:
        if _row_key(row=replacement_rows[key]) != key:
            raise ProjectionError(
                "Projected metric replacement identity differs"
            )
    seen: Set[RowKey] = set()
    output: List[Dict[str, object]] = []
    for legacy in legacy_rows:
        key = _row_key(row=legacy)
        if key in seen:
            raise ProjectionError(
                "Legacy metric matrix contains duplicate key"
            )
        seen.add(key)
        source = replacement_rows[key] if key in migrated_keys else legacy
        if set(source) != set(fieldnames):
            raise ProjectionError("Projected metric row fields are not exact")
        output.append({field: source[field] for field in fieldnames})
    absent_legacy = sorted(migrated_keys - seen)
    for key in absent_legacy:
        source = replacement_rows[key]
        output.append({field: source[field] for field in fieldnames})
    return output


def project_evidence_rows(
    *,
    legacy_rows: Sequence[Mapping[str, object]],
    migrated_keys: Set[RowKey],
    replacement_rows: Mapping[RowKey, Sequence[Mapping[str, object]]],
    fieldnames: Sequence[str],
) -> List[Dict[str, object]]:
    """Replace migrated evidence with stable one-source rows.

    Args:
        legacy_rows: Complete ordered evidence rows.
        migrated_keys: vNext-owned keys.
        replacement_rows: Ordered component/direct evidence per key.
        fieldnames: Exact legacy evidence schema.

    Returns:
        Complete evidence sequence; non-migrated rows retain exact order and
        field values.

    Raises:
        ProjectionError: On missing/extra replacement or schema drift.
    """
    if set(replacement_rows) != migrated_keys:
        raise ProjectionError(
            "Migrated evidence replacement exact set differs"
        )
    if any(not replacement_rows[key] for key in migrated_keys):
        raise ProjectionError("Migrated evidence replacement cannot be empty")
    for key in replacement_rows:
        if any(_row_key(row=row) != key for row in replacement_rows[key]):
            raise ProjectionError(
                "Projected evidence replacement identity differs"
            )
    output: List[Dict[str, object]] = []
    emitted: Set[RowKey] = set()
    for legacy in legacy_rows:
        key = _row_key(row=legacy)
        if key not in migrated_keys:
            if set(legacy) != set(fieldnames):
                raise ProjectionError("Legacy evidence fields are not exact")
            output.append({field: legacy[field] for field in fieldnames})
            continue
        if key in emitted:
            continue
        for replacement in replacement_rows[key]:
            if set(replacement) != set(fieldnames):
                raise ProjectionError(
                    "Projected evidence fields are not exact"
                )
            output.append({field: replacement[field] for field in fieldnames})
        emitted.add(key)
    for key in sorted(migrated_keys - emitted):
        for replacement in replacement_rows[key]:
            output.append({field: replacement[field] for field in fieldnames})
    return output


def compatibility_receipt(
    *,
    baseline_rows: Mapping[RowKey, Mapping[str, object]],
    projected_rows: Mapping[RowKey, Mapping[str, object]],
    exact_fields: Sequence[str],
    allowed_delta_fields: Sequence[str],
) -> Dict[str, object]:
    """Record every exact comparison and declared old-to-new method delta.

    Args:
        baseline_rows: Frozen legacy migrated rows.
        projected_rows: vNext projected rows.
        exact_fields: Fields that cannot change.
        allowed_delta_fields: Method description fields allowed to change.

    Returns:
        Receipt with one cell record per key/field and overall status.

    Raises:
        ProjectionError: On key mismatch or undeclared field class.
    """
    if set(baseline_rows) != set(projected_rows):
        raise ProjectionError("Compatibility row keys differ")
    classified = set(exact_fields) | set(allowed_delta_fields)
    if set(exact_fields) & set(allowed_delta_fields):
        raise ProjectionError("Compatibility field classes overlap")
    if len(exact_fields) != len(set(exact_fields)) or len(
        allowed_delta_fields
    ) != len(set(allowed_delta_fields)):
        raise ProjectionError("Compatibility fields are duplicated")
    cells = []
    failed = False
    for key in sorted(baseline_rows):
        if set(baseline_rows[key]) != set(projected_rows[key]):
            raise ProjectionError("Compatibility row schema differs")
        if set(baseline_rows[key]) != classified:
            raise ProjectionError(
                "Compatibility fields are not fully classified"
            )
        for field in exact_fields:
            passed = baseline_rows[key][field] == projected_rows[key][field]
            failed = failed or not passed
            cells.append(
                {
                    "key": list(key),
                    "field": field,
                    "class": "EXACT",
                    "old": baseline_rows[key][field],
                    "new": projected_rows[key][field],
                    "status": "PASS" if passed else "FAIL",
                }
            )
        for field in allowed_delta_fields:
            cells.append(
                {
                    "key": list(key),
                    "field": field,
                    "class": "DECLARATIVE_METHOD_DELTA",
                    "old": baseline_rows[key][field],
                    "new": projected_rows[key][field],
                    "status": "RECORDED",
                }
            )
    return {
        "status": "FAIL" if failed else "PASS",
        "cells": cells,
        "receipt_hash": content_hash(value=cells),
    }


def reconcile_component_evidence(
    *,
    component_rows: Sequence[Mapping[str, object]],
    baseline_row: Mapping[str, object],
    joined_fields: Sequence[str],
    concept_field: str,
    value_separator: str,
    concept_separator: str,
) -> Dict[str, object]:
    """Rebuild frozen aggregate evidence from ordered source components.

    Args:
        component_rows: Rows sorted by explicit ``evidence_order``.
        baseline_row: Frozen aggregate evidence.
        joined_fields: Fields reconstructed with ``value_separator``.
        concept_field: Field reconstructed with ``concept_separator``.
        value_separator: Legacy component separator.
        concept_separator: Legacy concept separator.

    Returns:
        Exact reconstruction receipt.

    Raises:
        ProjectionError: On duplicate/non-contiguous order or missing fields.
    """
    if not component_rows:
        raise ProjectionError("Component evidence cannot be empty")
    orders = [row["evidence_order"] for row in component_rows]
    if orders != list(range(len(component_rows))):
        raise ProjectionError("Evidence order must be unique and contiguous")
    rebuilt = {}
    for field in joined_fields:
        if (
            any(field not in row for row in component_rows)
            or field not in baseline_row
        ):
            raise ProjectionError("Reconciliation field is missing")
        rebuilt[field] = value_separator.join(
            str(row[field]) for row in component_rows
        )
    if (
        any(concept_field not in row for row in component_rows)
        or concept_field not in baseline_row
    ):
        raise ProjectionError("Reconciliation concept field is missing")
    rebuilt[concept_field] = concept_separator.join(
        str(row[concept_field]) for row in component_rows
    )
    comparisons = {
        field: {
            "expected": baseline_row[field],
            "actual": rebuilt[field],
            "status": "PASS"
            if baseline_row[field] == rebuilt[field]
            else "FAIL",
        }
        for field in rebuilt
    }
    passed = all(
        comparisons[field]["status"] == "PASS" for field in comparisons
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "comparisons": comparisons,
        "receipt_hash": content_hash(value=comparisons),
    }


def reject_legacy_migrated_writes(
    *,
    before_rows: Sequence[Mapping[str, object]],
    after_rows: Sequence[Mapping[str, object]],
    migrated_keys: Set[RowKey],
) -> None:
    """Fail when a legacy producer mutates any migrated result row.

    Args:
        before_rows: Migrated rows before a legacy stage.
        after_rows: Rows after that stage.
        migrated_keys: vNext-owned key set.

    Raises:
        ProjectionError: With ``LEGACY_PATH_STILL_ACTIVE`` on any addition,
            deletion, or field change.
    """
    before_selected = [
        row for row in before_rows if _row_key(row=row) in migrated_keys
    ]
    after_selected = [
        row for row in after_rows if _row_key(row=row) in migrated_keys
    ]
    before_keys = [_row_key(row=row) for row in before_selected]
    after_keys = [_row_key(row=row) for row in after_selected]
    if len(before_keys) != len(set(before_keys)) or len(after_keys) != len(
        set(after_keys)
    ):
        raise ProjectionError("LEGACY_PATH_STILL_ACTIVE")
    before = {
        _row_key(row=row): dict(row) for row in before_selected
    }
    after = {_row_key(row=row): dict(row) for row in after_selected}
    if before != after:
        raise ProjectionError("LEGACY_PATH_STILL_ACTIVE")


def build_projection_manifest(
    *,
    repo_root: Path,
    run_dir: Path,
    legacy_snapshot_dir: Path,
    staging_dir: Path,
) -> Dict[str, object]:
    """Build a projection only from a repository-verified FROZEN Run.

    Args:
        repo_root: Repository containing exact Requirement, Spec, and release
            configuration bytes.
        run_dir: Persisted Run directory reloaded through ``load_frozen_run``.
        legacy_snapshot_dir: Complete legacy matrix/evidence snapshot root.
        staging_dir: Candidate metrics/evidence and gate receipt root.

    Returns:
        Content-addressed projection manifest mapping.

    Raises:
        ProjectionError: On any Run/repository drift, duplicate legacy key,
            incomplete release metric set, detached Trace, or WITHHELD batch.
    """
    try:
        validated_run, run_records, _decisions = load_frozen_run(
            run_dir=run_dir, repo_root=repo_root,
        )
    except RunStoreError as error:
        raise ProjectionError(
            "Projection requires a verified FROZEN Run"
        ) from error
    release_plan, release_plan_sha256 = load_release_plan(
        repo_root=repo_root,
    )
    # The repository release plan defines the complete batch. Inferring a
    # subset from bound Specs cannot distinguish a dependency from a metric
    # that is both a dependency and a required top-level release output.
    migrated_metric_ids = list(release_plan["migrated_metric_ids"])
    legacy_hashes = projection_file_hashes(
        root=legacy_snapshot_dir,
        relative_paths=LEGACY_INPUT_FILES,
        label="Legacy input",
    )
    artifact_hashes = projection_file_hashes(
        root=staging_dir,
        relative_paths=PROJECTION_CANDIDATE_FILES,
        label="Candidate artifact",
    )
    receipt_hashes = projection_file_hashes(
        root=staging_dir,
        relative_paths=PROJECTION_GATE_FILES,
        label="Gate receipt",
    )
    validated_results = [
        record
        for record in run_records
        if record["record_type"] == "METRIC_RESULT"
    ]
    validated_observations = [
        record
        for record in run_records
        if record["record_type"] == "VERIFIED_OBSERVATION"
    ]
    validated_traces = [
        record
        for record in run_records
        if record["record_type"] == "EXECUTION_TRACE"
    ]
    if set(migrated_metric_ids) != {
        str(result["metric_id"]) for result in validated_results
    }:
        raise ProjectionError("Migrated metric exact set differs")
    result_ids = [str(result["result_id"]) for result in validated_results]
    result_grains = [
        (
            result["company_id"],
            result["metric_id"],
            result["period_start"],
            result["period_end"],
            result["scope_key"],
            result["spec_closure_hash"],
        )
        for result in validated_results
    ]
    if len(result_ids) != len(set(result_ids)) or len(result_grains) != len(
        set(result_grains)
    ):
        raise ProjectionError("Projected result identity is duplicated")
    legacy_result_keys = [
        (str(result["company_id"]), str(result["metric_id"]))
        for result in validated_results
    ]
    if len(legacy_result_keys) != len(set(legacy_result_keys)):
        raise ProjectionError(
            "Projected legacy compatibility key is duplicated"
        )
    trace_by_id = {
        str(trace["trace_id"]): trace for trace in validated_traces
    }
    required_trace_ids = {
        str(result["trace_id"]) for result in validated_results
    }
    if len(trace_by_id) != len(validated_traces) or set(
        trace_by_id
    ) != required_trace_ids:
        raise ProjectionError("Projection Trace exact set differs")
    for result in validated_results:
        trace = trace_by_id[str(result["trace_id"])]
        if (
            trace["metric_id"] != result["metric_id"]
            or trace["result"] != result["value"]
            or trace["result_contract_hash"]
            != metric_result_contract_hash(result=result)
        ):
            raise ProjectionError("Projection Result/Trace binding differs")
    observation_ids = {
        str(observation["observation_id"])
        for observation in validated_observations
    }
    if len(observation_ids) != len(validated_observations):
        raise ProjectionError("Projection observation identity is duplicated")
    if any(
        set(trace["input_observation_ids"]) - observation_ids
        for trace in validated_traces
    ):
        raise ProjectionError("Projection Trace observation is absent")
    status = publication_candidate_status(results=validated_results)
    body = {
        "legacy_input_hashes": legacy_hashes,
        "requirement_hashes": dict(validated_run["requirement_hashes"]),
        "release_id": release_plan["release_id"],
        "release_plan_sha256": release_plan_sha256,
        "run_id": validated_run["run_id"],
        "run_content_manifest_hash": validated_run["content_manifest_hash"],
        "run_audit_manifest_hash": validated_run["audit_manifest_hash"],
        "migrated_metric_ids": list(migrated_metric_ids),
        "result_ids": result_ids,
        "observation_ids": [
            observation["observation_id"]
            for observation in validated_observations
        ],
        "trace_ids": [trace["trace_id"] for trace in validated_traces],
        "derived_asset_ids": [
            record["derived_asset_id"]
            for record in run_records
            if record["record_type"] == "DERIVED_ASSET"
        ],
        "review_unit_hashes": [
            record["review_unit_hash"]
            for record in run_records
            if record["record_type"] == "REVIEW_UNIT"
        ],
        "candidate_artifact_hashes": artifact_hashes,
        "gate_receipt_hashes": receipt_hashes,
        "publication_candidate_status": status,
    }
    manifest = dict(body)
    manifest.update(
        {
            "schema_version": 1,
            "projection_manifest_id": content_hash(value=body),
        }
    )
    return manifest
