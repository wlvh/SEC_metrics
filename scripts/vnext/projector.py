"""Project migrated results into complete legacy-compatible row collections."""

from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .calculator import metric_is_applicable
from .canonical import CanonicalError, arithmetic_context
from .canonical import atomic_write_bytes, atomic_write_json
from .canonical import canonical_json_bytes, content_hash, decimal_text
from .canonical import parse_decimal, sha256_file
from .canonical import strict_json_file
from .records import metric_result_contract_hash
from .records import validate_record
from .requirements import load_requirement_snapshot
from .run_store import RunStoreError, load_frozen_run
from .specs import SpecError, compile_spec_files, parse_spec_document
from .states import publication_candidate_status
from .traits import TraitError, repository_company_traits


RowKey = Tuple[str, ...]


class ProjectionError(ValueError):
    """Report incomplete, duplicate, incompatible, or withheld projection."""


RELEASE_PLAN_FIELDS = {
    "migrated_metric_ids",
    "release_id",
    "schema_version",
}
LEGACY_INPUT_FILES = (
    "golden_results.csv",
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
REGISTRY_FIELDS = (
    "company_id",
    "display_name",
    "primary_cik",
    "ticker",
    "sic",
    "sic_description",
    "industry_profile",
    "fiscal_year_end",
    "target_period_policy",
    "entity_continuity_status",
    "related_ciks",
    "roles",
)
BATCH_MANIFEST_FIELDS = {
    "applicability_sha256",
    "batch_manifest_id",
    "expected_result_keys",
    "metric_spec_hashes",
    "registry_sha256",
    "release_id",
    "release_plan_sha256",
    "requirement_hashes",
    "runs",
    "schema_version",
    "target_fiscal_year",
    "trait_catalog_sha256",
}
BATCH_RUN_FIELDS = {
    "audit_manifest_hash",
    "company_id",
    "content_manifest_hash",
    "result_ids",
    "run_id",
    "run_path",
    "validation_receipt_id",
}
PROJECTION_MANIFEST_FIELDS = {
    "batch_manifest_id",
    "candidate_artifact_hashes",
    "derived_asset_ids",
    "expected_result_keys",
    "gate_receipt_hashes",
    "legacy_input_hashes",
    "migrated_metric_ids",
    "observation_ids",
    "projection_manifest_id",
    "publication_candidate_status",
    "release_id",
    "release_plan_sha256",
    "requirement_hashes",
    "result_bindings",
    "result_ids",
    "review_unit_hashes",
    "run_bindings",
    "schema_version",
    "trace_ids",
}
GOLDEN_FIELDS = (
    "assertion_id",
    "description",
    "expected",
    "actual",
    "status",
    "evidence_path",
    "notes",
)
REPAIR_FIELDS = ("check_id", "severity", "status", "details")


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


def _read_csv_rows(
    *, content: bytes, fieldnames: Sequence[str], label: str
) -> List[Dict[str, object]]:
    """Parse one strict UTF-8 CSV with an exact ordered schema.

    Args:
        content: Complete CSV bytes.
        fieldnames: Required header order.
        label: Diagnostic artifact identity.

    Returns:
        Ordered rows with string values.

    Raises:
        ProjectionError: On encoding, header, width, or null-value drift.
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProjectionError("{} is not UTF-8".format(label)) from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None or tuple(reader.fieldnames) != tuple(
        fieldnames
    ):
        raise ProjectionError("{} CSV schema differs".format(label))
    rows: List[Dict[str, object]] = []
    for row in reader:
        if None in row or any(row[field] is None for field in fieldnames):
            raise ProjectionError("{} CSV row width differs".format(label))
        rows.append({field: str(row[field]) for field in fieldnames})
    return rows


def _csv_bytes(
    *, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]
) -> bytes:
    """Serialize deterministic UTF-8 CSV bytes.

    Args:
        rows: Ordered exact-schema row mappings.
        fieldnames: Required column order.

    Returns:
        UTF-8 bytes using a stable newline convention.
    """
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(fieldnames),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        if set(row) != set(fieldnames):
            raise ProjectionError("Projected CSV row fields are not exact")
        writer.writerow({field: row[field] for field in fieldnames})
    return output.getvalue().encode("utf-8")


def _load_registry(*, repo_root: Path) -> List[Dict[str, str]]:
    """Load the unique company and legacy-display mapping authority.

    Args:
        repo_root: Repository containing the company registry.

    Returns:
        Ordered registry rows.

    Raises:
        ProjectionError: On unsafe bytes, schema drift, or duplicate identity.
    """
    path = repo_root / "config" / "company_registry.csv"
    if path.is_symlink() or not path.is_file():
        raise ProjectionError("Company registry is unsafe or missing")
    rows = _read_csv_rows(
        content=path.read_bytes(),
        fieldnames=REGISTRY_FIELDS,
        label="Company registry",
    )
    company_ids = [str(row["company_id"]) for row in rows]
    display_names = [str(row["display_name"]) for row in rows]
    if (
        not rows
        or any(not value for value in company_ids + display_names)
        or len(company_ids) != len(set(company_ids))
        or len(display_names) != len(set(display_names))
        or any(
            not str(row["primary_cik"]).isdigit()
            or int(str(row["primary_cik"])) <= 0
            for row in rows
        )
    ):
        raise ProjectionError("Company registry identity is invalid")
    return [
        {field: str(row[field]) for field in REGISTRY_FIELDS}
        for row in rows
    ]


def _load_release_specs(
    *, repo_root: Path, metric_ids: Sequence[str]
) -> Tuple[Dict[str, Dict[str, object]], Dict[str, str]]:
    """Compile the repository-owned migrated MetricSpec exact set.

    Args:
        repo_root: Repository containing the metric catalog.
        metric_ids: Release-plan metric identities.

    Returns:
        Compiled wrappers and source hashes keyed by metric identity.

    Raises:
        ProjectionError: On an unsafe, duplicate, or incomplete catalog.
    """
    metric_root = repo_root / "catalog" / "metrics"
    paths = sorted(metric_root.glob("*.md"))
    if not paths:
        raise ProjectionError("MetricSpec catalog is empty")
    selected = []
    seen = set()
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ProjectionError("MetricSpec catalog entry is unsafe")
        try:
            front, _body = parse_spec_document(
                text=path.read_text(encoding="utf-8")
            )
        except (UnicodeDecodeError, SpecError) as error:
            raise ProjectionError("MetricSpec catalog is invalid") from error
        metric_id = front["metric_id"]
        if type(metric_id) is not str or not metric_id or metric_id in seen:
            raise ProjectionError("MetricSpec identity is invalid")
        seen.add(metric_id)
        if metric_id in metric_ids:
            selected.append(path)
    try:
        compiled = compile_spec_files(paths=selected)
    except SpecError as error:
        raise ProjectionError(
            "Release MetricSpec closure is invalid"
        ) from error
    if set(compiled) != set(metric_ids):
        raise ProjectionError("Release MetricSpec exact set differs")
    hashes = {}
    for path in selected:
        front, _body = parse_spec_document(
            text=path.read_text(encoding="utf-8")
        )
        hashes[str(front["metric_id"])] = sha256_file(path=path)
    return compiled, hashes


def _release_context(*, repo_root: Path) -> Dict[str, object]:
    """Derive the complete company and metric release authority.

    Args:
        repo_root: Repository containing release, registry, trait, and Spec
            inputs.

    Returns:
        Release plan, registry, Specs, expected keys, and source hashes.
    """
    release_plan, release_plan_sha256 = load_release_plan(
        repo_root=repo_root,
    )
    metric_ids = [str(value) for value in release_plan["migrated_metric_ids"]]
    registry = _load_registry(repo_root=repo_root)
    specs, metric_spec_hashes = _load_release_specs(
        repo_root=repo_root, metric_ids=metric_ids,
    )
    expected = []
    try:
        for company in registry:
            traits = repository_company_traits(
                repo_root=repo_root,
                company_id=str(company["company_id"]),
            )
            for metric_id in metric_ids:
                applicable = metric_is_applicable(
                    applicability=specs[metric_id]["compiled"][
                        "applicability"
                    ],
                    traits=traits,
                )
                expected.append(
                    {
                        "company_id": company["company_id"],
                        "metric_id": metric_id,
                        "applicability": (
                            "APPLICABLE" if applicable else "N_A_STRUCTURAL"
                        ),
                    }
                )
    except TraitError as error:
        raise ProjectionError(
            "Company applicability authority is invalid"
        ) from error
    return {
        "release_plan": release_plan,
        "release_plan_sha256": release_plan_sha256,
        "registry": registry,
        "specs": specs,
        "expected_result_keys": expected,
        "registry_sha256": sha256_file(
            path=repo_root / "config" / "company_registry.csv"
        ),
        "applicability_sha256": sha256_file(
            path=repo_root / "config" / "metric_applicability.yaml"
        ),
        "trait_catalog_sha256": sha256_file(
            path=repo_root / "catalog" / "company_traits.yaml"
        ),
        "metric_spec_hashes": metric_spec_hashes,
    }


def _relative_run_path(*, root: Path, run_dir: Path) -> str:
    """Return one normalized Run locator below the batch directory.

    Args:
        root: Batch-manifest parent directory.
        run_dir: Persisted Run directory.

    Returns:
        Portable relative locator.

    Raises:
        ProjectionError: When the Run is aliased or outside the batch root.
    """
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ProjectionError("Batch Run locator is unsafe or missing")
    try:
        relative = run_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ProjectionError(
            "Batch Run must be below its manifest root"
        ) from error
    if not relative or relative == "." or ".." in Path(relative).parts:
        raise ProjectionError("Batch Run locator is invalid")
    if run_dir.resolve() != root.resolve() / relative:
        raise ProjectionError("Batch Run locator contains a symlink")
    return relative


def _batch_manifest_from_paths(
    *, repo_root: Path, batch_root: Path, run_paths: Sequence[str]
) -> Dict[str, object]:
    """Rebuild one batch manifest from verified FROZEN Run locators.

    Args:
        repo_root: Repository authority.
        batch_root: Directory against which Run locators are resolved.
        run_paths: Exact relative Run-directory set.

    Returns:
        Content-addressed complete batch manifest.

    Raises:
        ProjectionError: On missing companies, metrics, PASS receipts, or
            duplicate coordinates.
    """
    if batch_root.is_symlink() or not batch_root.is_dir():
        raise ProjectionError("Batch manifest root is unsafe or missing")
    if (
        not run_paths
        or len(run_paths) != len(set(run_paths))
        or any(
            type(relative) is not str
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or Path(relative).as_posix() != relative
            for relative in run_paths
        )
    ):
        raise ProjectionError("Batch Run locator exact set is invalid")
    authority = _release_context(repo_root=repo_root)
    expected_entries = authority["expected_result_keys"]
    expected = {
        (str(entry["company_id"]), str(entry["metric_id"])): str(
            entry["applicability"]
        )
        for entry in expected_entries
    }
    run_bindings = []
    results_by_key: Dict[Tuple[str, str], Mapping[str, object]] = {}
    requirement_hashes: Optional[Dict[str, object]] = None
    company_periods: Dict[str, Mapping[str, object]] = {}
    fiscal_years = set()
    run_ids = set()
    for relative in run_paths:
        run_dir = batch_root / relative
        if (
            run_dir.is_symlink()
            or not run_dir.is_dir()
            or run_dir.resolve() != batch_root.resolve() / relative
        ):
            raise ProjectionError("Batch Run locator is unsafe or missing")
        try:
            manifest, records, _decisions = load_frozen_run(
                run_dir=run_dir, repo_root=repo_root,
            )
            receipt_payload = strict_json_file(
                path=run_dir / "validation.json"
            )
            if not isinstance(receipt_payload, dict):
                raise ProjectionError("Batch Run validation is malformed")
            receipt = validate_record(record=receipt_payload)
        except (CanonicalError, RunStoreError, ValueError) as error:
            raise ProjectionError(
                "Batch requires verified FROZEN Runs"
            ) from error
        if receipt["status"] != "PASSED":
            raise ProjectionError("Batch Run validation did not PASS")
        run_id = str(manifest["run_id"])
        if run_id in run_ids:
            raise ProjectionError("Batch Run identity is duplicated")
        run_ids.add(run_id)
        company_id = str(manifest["company_id"])
        target_period = dict(manifest["target_period"])
        if (
            company_id in company_periods
            and company_periods[company_id] != target_period
        ):
            raise ProjectionError("Batch company periods differ")
        company_periods[company_id] = target_period
        fiscal_years.add(target_period["fiscal_year"])
        current_requirements = dict(manifest["requirement_hashes"])
        if requirement_hashes is None:
            requirement_hashes = current_requirements
        elif requirement_hashes != current_requirements:
            raise ProjectionError("Batch Run Requirement hashes differ")
        run_results = [
            record
            for record in records
            if record["record_type"] == "METRIC_RESULT"
        ]
        if not run_results:
            raise ProjectionError("Batch Run contains no MetricResult")
        for result in run_results:
            key = (str(result["company_id"]), str(result["metric_id"]))
            if result["company_id"] != manifest["company_id"]:
                raise ProjectionError("Batch Result company differs from Run")
            if key in results_by_key:
                raise ProjectionError(
                    "Batch company metric coordinate is duplicated"
                )
            results_by_key[key] = result
        run_bindings.append(
            {
                "audit_manifest_hash": manifest["audit_manifest_hash"],
                "company_id": manifest["company_id"],
                "content_manifest_hash": manifest["content_manifest_hash"],
                "result_ids": sorted(
                    str(result["result_id"]) for result in run_results
                ),
                "run_id": run_id,
                "run_path": relative,
                "validation_receipt_id": receipt["validation_receipt_id"],
            }
        )
    if set(results_by_key) != set(expected):
        raise ProjectionError(
            "Complete batch company metric exact set differs"
        )
    if any(
        results_by_key[key]["applicability"] != expected[key]
        for key in expected
    ):
        raise ProjectionError("Batch applicability exact set differs")
    if requirement_hashes is None:
        raise ProjectionError("Batch Requirement hashes are absent")
    if len(fiscal_years) != 1:
        raise ProjectionError("Batch target fiscal year differs")
    repository_requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1",
    )
    if requirement_hashes != repository_requirement["hashes"]:
        raise ProjectionError("Batch Requirement authority differs")
    run_bindings.sort(key=lambda item: (item["company_id"], item["run_id"]))
    body = {
        "applicability_sha256": authority["applicability_sha256"],
        "expected_result_keys": list(expected_entries),
        "metric_spec_hashes": dict(authority["metric_spec_hashes"]),
        "registry_sha256": authority["registry_sha256"],
        "release_id": authority["release_plan"]["release_id"],
        "release_plan_sha256": authority["release_plan_sha256"],
        "requirement_hashes": requirement_hashes,
        "runs": run_bindings,
        "target_fiscal_year": next(iter(fiscal_years)),
        "trait_catalog_sha256": authority["trait_catalog_sha256"],
    }
    manifest = dict(body)
    manifest.update(
        {
            "schema_version": 1,
            "batch_manifest_id": content_hash(value=body),
        }
    )
    return manifest


def write_projection_batch_manifest(
    *, repo_root: Path, batch_manifest_path: Path, run_dirs: Sequence[Path]
) -> Dict[str, object]:
    """Persist a content-addressed complete release batch authority.

    Args:
        repo_root: Repository authority.
        batch_manifest_path: New or identical manifest destination.
        run_dirs: Exact FROZEN Run directories below the manifest parent.

    Returns:
        Verified batch manifest.

    Raises:
        ProjectionError: On an incomplete batch or divergent existing file.
    """
    if batch_manifest_path.is_symlink():
        raise ProjectionError("Batch manifest path is unsafe")
    batch_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    run_paths = sorted(
        _relative_run_path(
            root=batch_manifest_path.parent, run_dir=run_dir,
        )
        for run_dir in run_dirs
    )
    manifest = _batch_manifest_from_paths(
        repo_root=repo_root,
        batch_root=batch_manifest_path.parent,
        run_paths=run_paths,
    )
    expected = canonical_json_bytes(value=manifest) + b"\n"
    if batch_manifest_path.exists():
        if not batch_manifest_path.is_file():
            raise ProjectionError("Batch manifest path is not a file")
        if batch_manifest_path.read_bytes() != expected:
            raise ProjectionError("Existing batch manifest bytes differ")
    else:
        atomic_write_json(path=batch_manifest_path, value=manifest)
    return manifest


def load_projection_batch_manifest(
    *, repo_root: Path, batch_manifest_path: Path
) -> Dict[str, object]:
    """Reload and independently rebuild a persisted batch authority.

    Args:
        repo_root: Repository authority.
        batch_manifest_path: Persisted batch manifest.

    Returns:
        Strict manifest matching current Run and repository bytes.
    """
    if batch_manifest_path.is_symlink() or not batch_manifest_path.is_file():
        raise ProjectionError("Batch manifest is unsafe or missing")
    try:
        payload = strict_json_file(
            path=batch_manifest_path,
            allowed_fields=BATCH_MANIFEST_FIELDS,
        )
    except CanonicalError as error:
        raise ProjectionError("Batch manifest is invalid") from error
    if not isinstance(payload, dict) or set(payload) != BATCH_MANIFEST_FIELDS:
        raise ProjectionError("Batch manifest fields are not exact")
    runs = payload["runs"]
    if (
        type(payload["schema_version"]) is not int
        or payload["schema_version"] != 1
        or type(runs) is not list
        or not runs
        or any(
            not isinstance(run, dict) or set(run) != BATCH_RUN_FIELDS
            for run in runs
        )
    ):
        raise ProjectionError("Batch manifest values are invalid")
    rebuilt = _batch_manifest_from_paths(
        repo_root=repo_root,
        batch_root=batch_manifest_path.parent,
        run_paths=[str(run["run_path"]) for run in runs],
    )
    if dict(payload) != rebuilt:
        raise ProjectionError("Batch manifest differs from repository Runs")
    return rebuilt


def _batch_runs(
    *, repo_root: Path, batch_manifest_path: Path,
    batch_manifest: Mapping[str, object]
) -> List[Tuple[Dict[str, object], List[Dict[str, object]]]]:
    """Load the exact FROZEN Run set named by a verified batch.

    Args:
        repo_root: Repository authority.
        batch_manifest_path: Manifest locator establishing the Run root.
        batch_manifest: Already verified batch mapping.

    Returns:
        Ordered Run manifests and record sequences.
    """
    output = []
    for binding in batch_manifest["runs"]:
        run_dir = batch_manifest_path.parent / str(binding["run_path"])
        if (
            run_dir.is_symlink()
            or not run_dir.is_dir()
            or run_dir.resolve()
            != batch_manifest_path.parent.resolve() / str(
                binding["run_path"]
            )
        ):
            raise ProjectionError("Batch Run reload locator is unsafe")
        try:
            manifest, records, _decisions = load_frozen_run(
                run_dir=run_dir, repo_root=repo_root,
            )
        except RunStoreError as error:
            raise ProjectionError("Batch Run reload failed") from error
        output.append((manifest, records))
    return output


def _legacy_inputs(
    *, repo_root: Path, legacy_snapshot_dir: Path
) -> Dict[str, object]:
    """Load complete legacy inputs using baseline-declared schemas.

    Args:
        repo_root: Repository containing the frozen baseline manifest.
        legacy_snapshot_dir: Current post-repair legacy snapshot.

    Returns:
        Schemas, rows, and exact input hashes.
    """
    baseline_path = (
        repo_root
        / "requirements"
        / "ai_first_v3_3_1"
        / "baseline_manifest.json"
    )
    try:
        baseline = strict_json_file(path=baseline_path)
    except CanonicalError as error:
        raise ProjectionError("Legacy baseline manifest is invalid") from error
    if not isinstance(baseline, dict) or "artifact_digests" not in baseline:
        raise ProjectionError("Legacy baseline artifact contract is absent")
    artifacts = baseline["artifact_digests"]
    if not isinstance(artifacts, dict):
        raise ProjectionError("Legacy baseline artifacts are invalid")
    names = {
        "golden_results.csv": "outputs/golden_results.csv",
        "metrics_matrix.csv": "outputs/metrics_matrix.csv",
        "metric_evidence.csv": "outputs/metric_evidence.csv",
    }
    rows = {}
    fieldnames = {}
    for relative in LEGACY_INPUT_FILES:
        artifact_key = names[relative]
        if artifact_key not in artifacts:
            raise ProjectionError("Legacy baseline schema is absent")
        record = artifacts[artifact_key]
        expected_record_fields = {"row_count", "sha256", "size"}
        if relative != "golden_results.csv":
            expected_record_fields.add("fieldnames")
        if (
            not isinstance(record, dict)
            or set(record) != expected_record_fields
            or type(record["row_count"]) is not int
            or record["row_count"] < 0
            or type(record["size"]) is not int
            or record["size"] < 0
            or type(record["sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
        ):
            raise ProjectionError("Legacy baseline schema is invalid")
        fields = (
            list(GOLDEN_FIELDS)
            if relative == "golden_results.csv"
            else record["fieldnames"]
        )
        if (
            type(fields) is not list
            or not fields
            or any(type(field) is not str or not field for field in fields)
            or len(fields) != len(set(fields))
        ):
            raise ProjectionError("Legacy baseline fieldnames are invalid")
        path = legacy_snapshot_dir / relative
        if path.is_symlink() or not path.is_file():
            raise ProjectionError("Legacy input file is unsafe or missing")
        if (
            sha256_file(path=path) != record["sha256"]
            or path.stat().st_size != record["size"]
        ):
            raise ProjectionError("Legacy input differs from frozen baseline")
        fieldnames[relative] = list(fields)
        rows[relative] = _read_csv_rows(
            content=path.read_bytes(), fieldnames=fields, label=relative,
        )
        if len(rows[relative]) != record["row_count"]:
            raise ProjectionError("Legacy baseline row count differs")
    return {
        "fieldnames": fieldnames,
        "rows": rows,
        "bytes": {
            relative: (legacy_snapshot_dir / relative).read_bytes()
            for relative in LEGACY_INPUT_FILES
        },
        "hashes": projection_file_hashes(
            root=legacy_snapshot_dir,
            relative_paths=LEGACY_INPUT_FILES,
            label="Legacy input",
        ),
    }


def _record_indexes(
    *, runs: Sequence[
        Tuple[Mapping[str, object], Sequence[Mapping[str, object]]]
    ]
) -> Dict[str, object]:
    """Index batch records while rejecting divergent duplicate identities.

    Args:
        runs: Verified Run manifests and records.

    Returns:
        Result, Trace, Observation, source, raw, and audit identity indexes.
    """
    indexes: Dict[str, Dict[object, Mapping[str, object]]] = {
        "results": {},
        "traces": {},
        "observations": {},
        "sources": {},
        "raw": {},
    }
    audit_ids = {
        "derived_asset_ids": set(),
        "review_unit_hashes": set(),
    }
    result_runs: Dict[Tuple[str, str], Mapping[str, object]] = {}
    id_fields = {
        "EXECUTION_TRACE": ("traces", "trace_id"),
        "VERIFIED_OBSERVATION": ("observations", "observation_id"),
        "SOURCE_REFERENCE": ("sources", "source_reference_id"),
        "RAW_BLOB": ("raw", "raw_asset_id"),
    }
    for manifest, records in runs:
        for record in records:
            record_type = str(record["record_type"])
            if record_type == "METRIC_RESULT":
                key = (str(record["company_id"]), str(record["metric_id"]))
                if key in indexes["results"]:
                    raise ProjectionError(
                        "Projection Result key is duplicated"
                    )
                indexes["results"][key] = record
                result_runs[key] = manifest
            elif record_type in id_fields:
                index_name, identity_field = id_fields[record_type]
                identity = str(record[identity_field])
                existing = indexes[index_name]
                if identity in existing and existing[identity] != record:
                    raise ProjectionError(
                        "Projection record identity diverges"
                    )
                existing[identity] = record
            elif record_type == "DERIVED_ASSET":
                audit_ids["derived_asset_ids"].add(
                    str(record["derived_asset_id"])
                )
            elif record_type == "REVIEW_UNIT":
                audit_ids["review_unit_hashes"].add(
                    str(record["review_unit_hash"])
                )
    indexes["result_runs"] = result_runs
    indexes.update(audit_ids)
    return indexes


def _projection_value(
    *, result: Mapping[str, object], projection: Mapping[str, object]
) -> str:
    """Convert one canonical Result value through declarative projection.

    Args:
        result: Verified MetricResult.
        projection: Compiled legacy projection mapping.

    Returns:
        Legacy decimal text or an empty structural value.
    """
    if result["value"] is None:
        return ""
    multiplier = (
        str(projection["value_multiplier"])
        if "value_multiplier" in projection
        else "1"
    )
    with arithmetic_context():
        value = parse_decimal(value=str(result["value"])) * parse_decimal(
            value=multiplier
        )
    return decimal_text(value=value)


def _projection_status(
    *, result: Mapping[str, object], projection: Mapping[str, object]
) -> str:
    """Map verified business state to one legacy status.

    Args:
        result: Verified MetricResult.
        projection: Declarative legacy mapping.

    Returns:
        Legacy status string.
    """
    if result["applicability"] == "N_A_STRUCTURAL":
        return "N_A_STRUCTURAL"
    quality = str(result["quality"])
    field_by_quality = {
        "EXACT": "status_exact",
        "APPROX": "status_approx",
        "NOT_MEANINGFUL": "status_not_meaningful",
    }
    if quality not in field_by_quality:
        raise ProjectionError("Result quality has no legacy status mapping")
    field = field_by_quality[quality]
    if field in projection:
        return str(projection[field])
    if quality == "EXACT" and "status" in projection:
        return str(projection["status"])
    if quality == "NOT_MEANINGFUL":
        return "NOT_MEANINGFUL"
    raise ProjectionError("MetricSpec lacks a legacy status mapping")


def _ordered_observations(
    *,
    trace: Mapping[str, object],
    observations: Mapping[object, Mapping[str, object]],
    projection: Mapping[str, object],
) -> Tuple[List[Mapping[str, object]], int]:
    """Order contributing evidence before supporting validation evidence.

    Args:
        trace: Verified ExecutionTrace.
        observations: Batch Observation index.
        projection: Declarative evidence ordering.

    Returns:
        Ordered observations and the contributing prefix length.
    """
    input_ids = [str(value) for value in trace["input_observation_ids"]]
    if any(identity not in observations for identity in input_ids):
        raise ProjectionError("Projection Trace observation is absent")
    role_order = (
        list(projection["evidence_role_order"])
        if "evidence_role_order" in projection
        else []
    )
    if any(type(role) is not str or not role for role in role_order):
        raise ProjectionError("Evidence role order is invalid")
    contributors: List[str] = []
    for role in role_order:
        derived_ids = []
        for step in trace["steps"]:
            if (
                step["event"] == "DERIVED_BRANCH_SELECTED"
                and step["role"] == role
            ):
                derived_ids.extend(
                    str(value) for value in step["component_observation_ids"]
                )
        role_ids = (
            derived_ids
            if derived_ids
            else [
                identity
                for identity in input_ids
                if observations[identity]["semantic_role"] == role
            ]
        )
        for identity in role_ids:
            if identity in input_ids and identity not in contributors:
                contributors.append(identity)
    if not role_order:
        contributors = list(input_ids)
    supporting = [
        identity for identity in input_ids if identity not in contributors
    ]
    ordered = contributors + supporting
    return [observations[identity] for identity in ordered], len(contributors)


def _context_text(
    *,
    style: str,
    observation: Mapping[str, object],
    fiscal_year: str,
    constant: str,
) -> str:
    """Render one Spec-selected legacy context representation.

    Args:
        style: Declarative context style.
        observation: Source observation.
        fiscal_year: Run fiscal-year label.
        constant: Spec-provided constant context.

    Returns:
        Legacy context text.
    """
    if style == "constant":
        return constant
    if style == "companyfacts_fiscal":
        return "companyfacts:{}:CY{}".format(
            observation["unit"], fiscal_year,
        )
    if style == "companyfacts_period":
        return "companyfacts:{}:CY{}:{}:{}".format(
            observation["unit"],
            fiscal_year,
            observation["period_start"],
            observation["period_end"],
        )
    raise ProjectionError("Legacy context style is unknown")


def _evidence_row(
    *,
    observation: Mapping[str, object],
    result: Mapping[str, object],
    company: Mapping[str, str],
    projection: Mapping[str, object],
    source_index: Mapping[object, Mapping[str, object]],
    raw_index: Mapping[object, Mapping[str, object]],
    fiscal_year: str,
) -> Dict[str, object]:
    """Project one verified source binding into one legacy evidence row.

    Args:
        observation: Verified source-grain fact.
        result: Owning MetricResult.
        company: Registry row.
        projection: Declarative legacy mapping.
        source_index: SourceReference index.
        raw_index: RawBlob index.
        fiscal_year: Run fiscal-year label.

    Returns:
        Exact legacy evidence schema row.
    """
    binding = observation["source_binding"]
    source_id = str(binding["source_reference_id"])
    raw_id = str(binding["raw_asset_id"])
    if source_id not in source_index or raw_id not in raw_index:
        raise ProjectionError("Observation source binding is incomplete")
    source = source_index[source_id]
    raw = raw_index[raw_id]
    if source["company_id"] != result["company_id"]:
        raise ProjectionError("Observation source company differs")
    concept = (
        str(binding["concept"]).split(":", maxsplit=1)[-1]
        if "concept" in binding
        else str(projection["concept_or_section"])
    )
    evidence_style = str(projection["evidence_context_style"])
    constant_context = (
        str(projection["context_or_dimension"])
        if "context_or_dimension" in projection
        else ""
    )
    context = _context_text(
        style=evidence_style,
        observation=observation,
        fiscal_year=fiscal_year,
        constant=constant_context,
    )
    projected_value = _projection_value(
        result=result, projection=projection,
    )
    unit_policy = str(projection["evidence_unit_policy"])
    if unit_policy == "observation":
        evidence_unit = str(observation["unit"])
        raw_value = str(observation["value"])
        normalized_value = str(observation["value"])
    elif unit_policy == "projected_result":
        evidence_unit = str(projection["unit"])
        raw_value = projected_value
        normalized_value = projected_value
    else:
        raise ProjectionError("Evidence unit policy is unknown")
    filed = str(binding["filed"]) if "filed" in binding else ""
    quote = "{}={} unit={} accn={} filed={}".format(
        concept,
        raw_value,
        evidence_unit,
        source["accession"],
        filed,
    )
    return {
        "company": company["display_name"],
        "cik": company["primary_cik"],
        "metric_id": result["metric_id"],
        "source_url": source["source_url"],
        "repo_relative_path": raw["storage_uri"],
        "content_sha256": raw_id.split(":", maxsplit=1)[1],
        "accession": source["accession"],
        "document_name": source["document_name"],
        "concept_or_section": concept,
        "context_or_dimension": context,
        "unit": evidence_unit,
        "period_start": result["period_start"],
        "period_end": result["period_end"],
        "value_raw": raw_value,
        "value_normalized": normalized_value,
        "evidence_quote": quote,
        "extraction_method": projection["evidence_extraction_method"],
        "parser_version": projection["parser_version"],
    }


def _joined_binding_field(
    *, bindings: Sequence[Mapping[str, object]], field: str, fallback: object
) -> str:
    """Join one optional source field or retain its frozen baseline value.

    Args:
        bindings: Ordered contributing Observation source bindings.
        field: Optional source-binding field name.
        fallback: Frozen legacy value when the source model does not own it.

    Returns:
        Joined source values or the exact baseline value.

    Raises:
        ProjectionError: When only part of a component set has the field.
    """
    presence = [field in binding for binding in bindings]
    if any(presence) and not all(presence):
        raise ProjectionError(
            "Projection source binding field is only partially present"
        )
    if all(presence):
        return ";".join(str(binding[field]) for binding in bindings)
    return str(fallback)


def _project_result(
    *,
    result: Mapping[str, object],
    trace: Mapping[str, object],
    company: Mapping[str, str],
    spec: Mapping[str, object],
    baseline_row: Optional[Mapping[str, object]],
    indexes: Mapping[str, object],
    fiscal_year: str,
    metric_fields: Sequence[str],
) -> Tuple[Dict[str, object], List[Dict[str, object]], int]:
    """Build one metric row and its ordered evidence rows.

    Args:
        result: Verified MetricResult.
        trace: Bound ExecutionTrace.
        company: Registry row.
        spec: Compiled MetricSpec wrapper.
        baseline_row: Existing migrated row, if any.
        indexes: Batch record indexes.
        fiscal_year: Run target fiscal-year label.
        metric_fields: Exact legacy matrix schema.

    Returns:
        Metric row, evidence rows, and contributing evidence count.
    """
    projection = spec["compiled"]["legacy_projection"]
    if result["applicability"] == "N_A_STRUCTURAL":
        row = {field: "" for field in metric_fields}
        row.update(
            {
                "company": company["display_name"],
                "cik": company["primary_cik"],
                "metric_id": result["metric_id"],
                "metric_name": spec["compiled"]["name"],
                "value": "",
                "unit": (
                    projection["unit"]
                    if "unit" in projection
                    else spec["compiled"]["reported_unit"]
                ),
                "status": "N_A_STRUCTURAL",
                "source_class": "NOT_AVAILABLE",
                "formula": (
                    projection["formula"]
                    if "formula" in projection
                    else "not applicable"
                ),
                "period_start": result["period_start"],
                "period_end": result["period_end"],
                "fiscal_year": fiscal_year,
                "fiscal_period": "FY",
                "confidence": "0.00",
                "notes": "Trait applicability is structurally false.",
            }
        )
        return row, [], 0
    if baseline_row is None:
        raise ProjectionError("Applicable migrated legacy row is absent")
    ordered, contributor_count = _ordered_observations(
        trace=trace,
        observations=indexes["observations"],
        projection=projection,
    )
    evidence_rows = [
        _evidence_row(
            observation=observation,
            result=result,
            company=company,
            projection=projection,
            source_index=indexes["sources"],
            raw_index=indexes["raw"],
            fiscal_year=fiscal_year,
        )
        for observation in ordered
    ]
    if not evidence_rows:
        raise ProjectionError("Applicable result has no projected evidence")
    contributor_bindings = [
        ordered[index]["source_binding"]
        for index in range(contributor_count)
    ]
    form = (
        str(projection["form"])
        if "form" in projection
        else _joined_binding_field(
            bindings=contributor_bindings,
            field="form",
            fallback=baseline_row["form"],
        )
    )
    filed_date = _joined_binding_field(
        bindings=contributor_bindings,
        field="filed",
        fallback=baseline_row["filed_date"],
    )
    row = dict(baseline_row)
    row.update(
        {
            "company": company["display_name"],
            "cik": company["primary_cik"],
            "metric_id": result["metric_id"],
            "metric_name": spec["compiled"]["name"],
            "value": _projection_value(result=result, projection=projection),
            "unit": (
                projection["unit"]
                if "unit" in projection
                else result["unit"]
            ),
            "status": _projection_status(
                result=result, projection=projection,
            ),
            "source_class": projection["source_class"],
            "formula": projection["formula"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "fiscal_year": (
                projection["fiscal_year"]
                if "fiscal_year" in projection
                else fiscal_year
            ),
            "fiscal_period": "FY",
            "accession": ";".join(
                str(row_value["accession"])
                for row_value in evidence_rows[:contributor_count]
            ),
            "form": form,
            "filed_date": filed_date,
            "concept_or_section": "+".join(
                str(row_value["concept_or_section"])
                for row_value in evidence_rows[:contributor_count]
            ),
            "context_or_dimension": ";".join(
                _context_text(
                    style=str(projection["metric_context_style"]),
                    observation=ordered[index],
                    fiscal_year=fiscal_year,
                    constant=(
                        str(projection["context_or_dimension"])
                        if "context_or_dimension" in projection
                        else ""
                    ),
                )
                for index in range(contributor_count)
            ),
            "confidence": projection["confidence"],
            "notes": (
                projection["notes_template"]
                if "notes_template" in projection
                else projection["notes"]
                if "notes" in projection
                else baseline_row["notes"]
            ),
        }
    )
    if set(row) != set(metric_fields):
        raise ProjectionError("Projected metric row schema differs")
    return row, evidence_rows, contributor_count


def _projection_candidate(
    *, repo_root: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path
) -> Dict[str, object]:
    """Derive exact candidate bytes and compatibility proof from authority.

    Args:
        repo_root: Repository authority.
        batch_manifest_path: Complete verified batch locator.
        legacy_snapshot_dir: Post-repair complete legacy snapshot.

    Returns:
        Candidate rows/bytes, compatibility receipt, and record indexes.
    """
    batch = load_projection_batch_manifest(
        repo_root=repo_root, batch_manifest_path=batch_manifest_path,
    )
    authority = _release_context(repo_root=repo_root)
    legacy = _legacy_inputs(
        repo_root=repo_root, legacy_snapshot_dir=legacy_snapshot_dir,
    )
    runs = _batch_runs(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        batch_manifest=batch,
    )
    indexes = _record_indexes(runs=runs)
    registry_by_id = {
        str(row["company_id"]): row for row in authority["registry"]
    }
    display_to_id = {
        str(row["display_name"]): str(row["company_id"])
        for row in authority["registry"]
    }
    expected = {
        (str(entry["company_id"]), str(entry["metric_id"]))
        for entry in batch["expected_result_keys"]
    }
    migrated_ids = set(authority["release_plan"]["migrated_metric_ids"])
    metric_fields = legacy["fieldnames"]["metrics_matrix.csv"]
    evidence_fields = legacy["fieldnames"]["metric_evidence.csv"]
    legacy_metrics = legacy["rows"]["metrics_matrix.csv"]
    legacy_evidence = legacy["rows"]["metric_evidence.csv"]
    baseline_metrics = {}
    for row in legacy_metrics:
        if row["metric_id"] not in migrated_ids:
            continue
        if row["company"] not in display_to_id:
            raise ProjectionError("Legacy migrated company is unregistered")
        key = (display_to_id[str(row["company"])], str(row["metric_id"]))
        if key not in expected or key in baseline_metrics:
            raise ProjectionError("Legacy migrated metric key is invalid")
        baseline_metrics[key] = row
    baseline_evidence: Dict[Tuple[str, str], List[Mapping[str, object]]] = {}
    for row in legacy_evidence:
        if row["metric_id"] not in migrated_ids:
            continue
        if row["company"] not in display_to_id:
            raise ProjectionError("Legacy migrated evidence is unregistered")
        key = (display_to_id[str(row["company"])], str(row["metric_id"]))
        if key not in expected:
            raise ProjectionError("Legacy migrated evidence key is invalid")
        if key not in baseline_evidence:
            baseline_evidence[key] = []
        baseline_evidence[key].append(row)
    replacements = {}
    evidence_replacements = {}
    contributor_counts = {}
    result_bindings = []
    for entry in batch["expected_result_keys"]:
        internal_key = (str(entry["company_id"]), str(entry["metric_id"]))
        result = indexes["results"][internal_key]
        trace_id = str(result["trace_id"])
        if trace_id not in indexes["traces"]:
            raise ProjectionError("Projection Result Trace is absent")
        trace = indexes["traces"][trace_id]
        if (
            trace["metric_id"] != result["metric_id"]
            or trace["result"] != result["value"]
            or trace["result_contract_hash"]
            != metric_result_contract_hash(result=result)
        ):
            raise ProjectionError("Projection Result Trace binding differs")
        result_run = indexes["result_runs"][internal_key]
        if (
            result_run["target_period"]["period_start"]
            != result["period_start"]
            or result_run["target_period"]["period_end"]
            != result["period_end"]
        ):
            raise ProjectionError("Projection Result Run period differs")
        fiscal_year = str(result_run["target_period"]["fiscal_year"])
        metric_row, evidence_rows, contributor_count = _project_result(
            result=result,
            trace=trace,
            company=registry_by_id[internal_key[0]],
            spec=authority["specs"][internal_key[1]],
            baseline_row=(
                baseline_metrics[internal_key]
                if internal_key in baseline_metrics
                else None
            ),
            indexes=indexes,
            fiscal_year=fiscal_year,
            metric_fields=metric_fields,
        )
        legacy_key = (
            str(metric_row["company"]), str(metric_row["metric_id"])
        )
        replacements[legacy_key] = metric_row
        evidence_replacements[legacy_key] = evidence_rows
        contributor_counts[legacy_key] = contributor_count
        result_bindings.append(
            {
                "applicability": result["applicability"],
                "company_id": result["company_id"],
                "evidence_row_hashes": [
                    content_hash(value=row) for row in evidence_rows
                ],
                "metric_id": result["metric_id"],
                "metric_row_hash": content_hash(value=metric_row),
                "result_id": result["result_id"],
                "trace_id": result["trace_id"],
                "unit": result["unit"],
                "value": result["value"],
            }
        )
    migrated_keys = set(replacements)
    projected_metrics = project_metric_rows(
        legacy_rows=legacy_metrics,
        migrated_keys=migrated_keys,
        replacement_rows=replacements,
        fieldnames=metric_fields,
    )
    projected_evidence = project_evidence_rows(
        legacy_rows=legacy_evidence,
        migrated_keys=migrated_keys,
        replacement_rows=evidence_replacements,
        fieldnames=evidence_fields,
    )
    metric_cells = []
    evidence_receipts = []
    failed = False
    for legacy_key in sorted(migrated_keys):
        internal_key = (
            display_to_id[legacy_key[0]], legacy_key[1],
        )
        projection = authority["specs"][internal_key[1]]["compiled"][
            "legacy_projection"
        ]
        if internal_key in baseline_metrics:
            allowed = (
                list(projection["allowed_metric_delta_fields"])
                if "allowed_metric_delta_fields" in projection
                else []
            )
            exact = [field for field in metric_fields if field not in allowed]
            comparison = compatibility_receipt(
                baseline_rows={legacy_key: baseline_metrics[internal_key]},
                projected_rows={legacy_key: replacements[legacy_key]},
                exact_fields=exact,
                allowed_delta_fields=allowed,
            )
            metric_cells.extend(comparison["cells"])
            failed = failed or comparison["status"] != "PASS"
        elif replacements[legacy_key]["status"] != "N_A_STRUCTURAL":
            raise ProjectionError("Applicable migrated legacy row is absent")
        baseline_rows = (
            baseline_evidence[internal_key]
            if internal_key in baseline_evidence
            else []
        )
        projected_rows = evidence_replacements[legacy_key]
        if not baseline_rows and not projected_rows:
            evidence_receipts.append(
                {
                    "key": list(legacy_key),
                    "status": "PASS",
                    "comparisons": {},
                    "exact_cells": [],
                    "method_cells": [],
                }
            )
            continue
        if len(baseline_rows) != 1 or not projected_rows:
            failed = True
            evidence_receipts.append(
                {
                    "key": list(legacy_key),
                    "status": "FAIL",
                    "comparisons": {},
                    "exact_cells": [],
                    "method_cells": [],
                }
            )
            continue
        contributors = []
        for order, row in enumerate(
            projected_rows[: contributor_counts[legacy_key]]
        ):
            value = dict(row)
            value["evidence_order"] = order
            contributors.append(value)
        joined_fields = [
            field
            for field in (
                "source_url",
                "repo_relative_path",
                "content_sha256",
                "accession",
                "document_name",
                "context_or_dimension",
                "value_raw",
            )
            if field in evidence_fields
        ]
        reconciliation = reconcile_component_evidence(
            component_rows=contributors,
            baseline_row=baseline_rows[0],
            joined_fields=joined_fields,
            concept_field="concept_or_section",
            value_separator=";",
            concept_separator="+",
        )
        exact_evidence_fields = [
            "company", "cik", "metric_id", "period_start", "period_end",
        ]
        if "component_evidence_grain" not in projection:
            exact_evidence_fields.extend(["unit", "value_normalized"])
        configured_evidence_fields = projection[
            "allowed_evidence_delta_fields"
        ]
        if (
            type(configured_evidence_fields) is not list
            or any(
                type(field) is not str or not field
                for field in configured_evidence_fields
            )
        ):
            raise ProjectionError("Evidence delta field contract is invalid")
        allowed_evidence_fields = list(configured_evidence_fields)
        baseline_cells = {}
        projected_cells = {}
        for order, row in enumerate(projected_rows):
            cell_key = (*legacy_key, str(order))
            compared_fields = exact_evidence_fields + allowed_evidence_fields
            baseline_cells[cell_key] = {
                field: baseline_rows[0][field] for field in compared_fields
            }
            projected_cells[cell_key] = {
                field: row[field] for field in compared_fields
            }
        cell_receipt = compatibility_receipt(
            baseline_rows=baseline_cells,
            projected_rows=projected_cells,
            exact_fields=exact_evidence_fields,
            allowed_delta_fields=allowed_evidence_fields,
        )
        evidence_receipts.append(
            {
                "key": list(legacy_key),
                "status": (
                    "PASS"
                    if reconciliation["status"] == "PASS"
                    and cell_receipt["status"] == "PASS"
                    else "FAIL"
                ),
                "comparisons": reconciliation["comparisons"],
                "exact_cells": [
                    cell
                    for cell in cell_receipt["cells"]
                    if cell["class"] == "EXACT"
                ],
                "method_cells": [
                    cell
                    for cell in cell_receipt["cells"]
                    if cell["class"] == "DECLARATIVE_METHOD_DELTA"
                ],
            }
        )
        failed = (
            failed
            or reconciliation["status"] != "PASS"
            or cell_receipt["status"] != "PASS"
        )
    receipt_body = {
        "batch_manifest_id": batch["batch_manifest_id"],
        "evidence_reconciliations": evidence_receipts,
        "legacy_input_hashes": legacy["hashes"],
        "metric_cells": metric_cells,
        "status": "FAIL" if failed else "PASS",
    }
    receipt = dict(receipt_body)
    receipt.update(
        {
            "schema_version": 1,
            "receipt_id": content_hash(value=receipt_body),
        }
    )
    metric_bytes = _csv_bytes(
        rows=projected_metrics, fieldnames=metric_fields,
    )
    evidence_bytes = _csv_bytes(
        rows=projected_evidence, fieldnames=evidence_fields,
    )
    repair_rows = [
        {
            "check_id": "frozen_legacy_baseline_exact",
            "severity": "P0",
            "status": "PASS",
            "details": "artifacts={}".format(len(LEGACY_INPUT_FILES)),
        },
        {
            "check_id": "batch_result_exact_set",
            "severity": "P0",
            "status": "PASS",
            "details": "results={}".format(len(result_bindings)),
        },
        {
            "check_id": "legacy_invariant_migration",
            "severity": "P0",
            "status": receipt["status"],
            "details": "receipt_id={}".format(receipt["receipt_id"]),
        },
        {
            "check_id": "projection_result_row_binding",
            "severity": "P0",
            "status": "PASS",
            "details": "metric_rows={};evidence_rows={}".format(
                len(projected_metrics), len(projected_evidence),
            ),
        },
    ]
    return {
        "batch": batch,
        "indexes": indexes,
        "metric_rows": projected_metrics,
        "evidence_rows": projected_evidence,
        "metric_bytes": metric_bytes,
        "evidence_bytes": evidence_bytes,
        "compatibility_receipt": receipt,
        "compatibility_bytes": canonical_json_bytes(value=receipt) + b"\n",
        "golden_bytes": legacy["bytes"]["golden_results.csv"],
        "repair_bytes": _csv_bytes(
            rows=repair_rows, fieldnames=REPAIR_FIELDS,
        ),
        "migrated_metric_ids": list(
            authority["release_plan"]["migrated_metric_ids"]
        ),
        "result_bindings": result_bindings,
        "legacy_hashes": legacy["hashes"],
    }


def write_projection_candidate(
    *, repo_root: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path, staging_dir: Path
) -> Dict[str, object]:
    """Write only Projector-owned candidate and compatibility artifacts.

    Args:
        repo_root: Repository authority.
        batch_manifest_path: Complete batch locator.
        legacy_snapshot_dir: Post-repair legacy snapshot.
        staging_dir: Dedicated staging root.

    Returns:
        Candidate summary including compatibility status and row counts.
    """
    if staging_dir.is_symlink() or (
        staging_dir.exists() and not staging_dir.is_dir()
    ):
        raise ProjectionError("Projection staging root is unsafe")
    staging_dir.mkdir(parents=True, exist_ok=True)
    candidate = _projection_candidate(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
    )
    atomic_write_bytes(
        path=staging_dir / "metrics_matrix.csv",
        content=candidate["metric_bytes"],
    )
    atomic_write_bytes(
        path=staging_dir / "metric_evidence.csv",
        content=candidate["evidence_bytes"],
    )
    atomic_write_bytes(
        path=staging_dir / "legacy_invariant_migration_receipt.json",
        content=candidate["compatibility_bytes"],
    )
    atomic_write_bytes(
        path=staging_dir / "golden_results.csv",
        content=candidate["golden_bytes"],
    )
    atomic_write_bytes(
        path=staging_dir / "repair_validation_results.csv",
        content=candidate["repair_bytes"],
    )
    return {
        "batch_manifest_id": candidate["batch"]["batch_manifest_id"],
        "compatibility_status": candidate["compatibility_receipt"]["status"],
        "evidence_row_count": len(candidate["evidence_rows"]),
        "metric_row_count": len(candidate["metric_rows"]),
    }


def golden_row_passes(*, row: Mapping[str, object]) -> bool:
    """Recompute one stored Golden row from its explicit grammar.

    Args:
        row: Strict Golden CSV row.

    Returns:
        Whether expected and actual support PASS independently of the label.
    """
    expected = str(row["expected"])
    actual = str(row["actual"])
    if expected.startswith("source_class != "):
        return bool(actual) and actual != expected.replace(
            "source_class != ", "", 1
        )
    if expected.startswith("B08="):
        return "B08_status={}".format(expected.split("=", 1)[1]) in actual
    if " or " in expected:
        return actual in {value.strip() for value in expected.split(" or ")}
    if expected.startswith("at least one"):
        try:
            return parse_decimal(value=actual) >= parse_decimal(value="1")
        except CanonicalError:
            return False
    match = re.search(r"tolerance=([^ ]+)", str(row["notes"]))
    if match is not None:
        try:
            with arithmetic_context():
                difference = abs(
                    Decimal(actual) - Decimal(expected)
                )
                return difference <= Decimal(match.group(1))
        except InvalidOperation:
            return False
    return actual == expected


def _projection_gate_status(*, staging_dir: Path) -> bool:
    """Evaluate the Projector-owned Golden and repair gate artifacts.

    Args:
        staging_dir: Candidate root containing gate outputs.

    Returns:
        True only when both parsed gate result sets genuinely pass.
    """
    golden_path = staging_dir / "golden_results.csv"
    repair_path = staging_dir / "repair_validation_results.csv"
    for path in (golden_path, repair_path):
        if path.is_symlink() or not path.is_file():
            raise ProjectionError("Projection gate artifact is missing")
    golden = _read_csv_rows(
        content=golden_path.read_bytes(),
        fieldnames=GOLDEN_FIELDS,
        label="Golden gate",
    )
    repair = _read_csv_rows(
        content=repair_path.read_bytes(),
        fieldnames=REPAIR_FIELDS,
        label="Repair gate",
    )
    if not golden or not repair:
        raise ProjectionError("Projection gate result set is empty")
    golden_ids = [str(row["assertion_id"]) for row in golden]
    repair_ids = [str(row["check_id"]) for row in repair]
    if (
        len(golden_ids) != len(set(golden_ids))
        or len(repair_ids) != len(set(repair_ids))
    ):
        raise ProjectionError("Projection gate identity is duplicated")
    golden_passed = all(
        row["status"] == "PASS" and golden_row_passes(row=row)
        for row in golden
    )
    repair_passed = all(row["status"] == "PASS" for row in repair)
    return golden_passed and repair_passed


def build_projection_manifest(
    *,
    repo_root: Path,
    batch_manifest_path: Path,
    legacy_snapshot_dir: Path,
    staging_dir: Path,
) -> Dict[str, object]:
    """Verify generated projection bytes and build their durable proof.

    Args:
        repo_root: Repository containing Requirement, Spec, registry, trait,
            and release authority.
        batch_manifest_path: Persisted complete FROZEN Run collection.
        legacy_snapshot_dir: Complete post-repair legacy snapshot root.
        staging_dir: Candidate metrics/evidence and gate output root.

    Returns:
        Content-addressed ProjectionManifest.

    Raises:
        ProjectionError: On incomplete batch, arbitrary candidate bytes,
            malformed gates, detached trace, or repository drift.
    """
    candidate = _projection_candidate(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
    )
    expected = {
        "metrics_matrix.csv": candidate["metric_bytes"],
        "metric_evidence.csv": candidate["evidence_bytes"],
        "legacy_invariant_migration_receipt.json": candidate[
            "compatibility_bytes"
        ],
        "golden_results.csv": candidate["golden_bytes"],
        "repair_validation_results.csv": candidate["repair_bytes"],
    }
    for relative in expected:
        path = staging_dir / relative
        if path.is_symlink() or not path.is_file():
            raise ProjectionError("Projection artifact is unsafe or missing")
        if path.read_bytes() != expected[relative]:
            raise ProjectionError(
                "Projection artifact differs from Run-derived bytes"
            )
    gate_passed = _projection_gate_status(staging_dir=staging_dir)
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
    batch = candidate["batch"]
    indexes = candidate["indexes"]
    results = list(indexes["results"].values())
    status = publication_candidate_status(results=results)
    if (
        candidate["compatibility_receipt"]["status"] != "PASS"
        or not gate_passed
    ):
        status = "BLOCKED"
    body = {
        "batch_manifest_id": batch["batch_manifest_id"],
        "candidate_artifact_hashes": artifact_hashes,
        "derived_asset_ids": sorted(indexes["derived_asset_ids"]),
        "expected_result_keys": list(batch["expected_result_keys"]),
        "gate_receipt_hashes": receipt_hashes,
        "legacy_input_hashes": dict(candidate["legacy_hashes"]),
        "migrated_metric_ids": candidate["migrated_metric_ids"],
        "observation_ids": sorted(
            str(value) for value in indexes["observations"]
        ),
        "publication_candidate_status": status,
        "release_id": batch["release_id"],
        "release_plan_sha256": batch["release_plan_sha256"],
        "requirement_hashes": dict(batch["requirement_hashes"]),
        "result_bindings": list(candidate["result_bindings"]),
        "result_ids": sorted(str(result["result_id"]) for result in results),
        "review_unit_hashes": sorted(indexes["review_unit_hashes"]),
        "run_bindings": list(batch["runs"]),
        "trace_ids": sorted(str(value) for value in indexes["traces"]),
    }
    manifest = dict(body)
    manifest.update(
        {
            "schema_version": 2,
            "projection_manifest_id": content_hash(value=body),
        }
    )
    if set(manifest) != PROJECTION_MANIFEST_FIELDS:
        raise ProjectionError("ProjectionManifest fields are not exact")
    return manifest
