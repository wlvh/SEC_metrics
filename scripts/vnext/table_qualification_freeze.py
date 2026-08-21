"""Freeze the table-family qualification authority without live egress.

The module binds WB-3 invocation protections, WB-4 compact transport
measurements, WB-5 scope semantics, WB-6 single-table task contracts, and the
unchanged R2 active/root state.  It writes only a content-addressed freeze
receipt and an empty qualification-cycle provider ledger; it never fetches SEC
bytes or invokes a model provider.
"""

from __future__ import annotations

import csv
import inspect
import json
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from .ai_adapter import _open_provider_request, approved_transport_policy
from .ai_adapter import build_provider_request_body
from .canonical import atomic_write_json, canonical_json_bytes, content_hash
from .canonical import parse_utc_timestamp, sha256_bytes, sha256_file
from .canonical import strict_json_file
from .invocation_control import effective_invocation_policy
from .provider_runtime import estimate_context_tokens
from .provider_runtime import load_provider_runtime_authority
from .reader_input import READER_SYSTEM_CONTRACT
from .reader_input import build_reader_input_manifest, build_reader_payload
from .requirements import load_requirement_snapshot
from .scope_contract import scope_contract_hash, validate_scope_contract
from .specs import parse_spec_document, SpecError
from .table_grid import build_table_grid
from .table_payload import compact_payload_receipt
from .table_payload import DECODER_SEMANTIC_VERSION
from .table_payload import TABLE_PAYLOAD_SERIALIZATION_VERSION
from .table_task_contracts import load_table_task_contracts
from .table_task_contracts import resolve_table_task_contract


MATRIX_PATH = Path("config/table_qualification_matrix.json")
FREEZE_POINTER_PATH = Path("config/table_qualification_freeze.json")
FREEZE_ROOT = Path("artifacts/vnext/table_qualification_freeze")
FREEZE_RECEIPT_ROOT = FREEZE_ROOT / "receipts"
FREEZE_CYCLE_ROOT = FREEZE_ROOT / "cycles"
MARRIOTT_PROVENANCE_PATH = Path(
    "fixtures/vnext/recorded/marriott_2025_fixture_provenance.json"
)
LAYOUT_FIXTURE_ROOT = Path("fixtures/vnext/layouts")
MATRIX_FIELDS = {"families", "requirement_id", "schema_version"}
MATRIX_ENTRY_FIELDS = {
    "development_source",
    "expected_claims",
    "expected_locator_range",
    "expected_output_status",
    "family_id",
    "fresh_samples_required",
    "materially_different_criteria",
    "negative_cases",
    "post_freeze_holdout_source",
    "reader_contract_id",
    "review_policy",
    "second_layout_policy",
    "second_layout_source",
    "token_context_limits",
}
LOCATOR_RANGE_FIELDS = {
    "column_index_min",
    "row_index_min",
    "selected_competing_scope_evidence",
    "table_selection",
}
TOKEN_LIMIT_FIELDS = {"max_estimated_input_tokens", "maximum_context_tokens"}
IMMUTABLE_SOURCE_FIELDS = {
    "accession",
    "cik",
    "company_id",
    "document_name",
    "source_kind",
    "source_repo_relative_path",
    "source_sha256",
}
FUTURE_SOURCE_FIELDS = {
    "cik", "company_id", "fiscal_year", "form", "source_kind",
}
FIXTURE_SOURCE_FIELDS = {"fixture_id", "source_kind"}
POINTER_FIELDS = {
    "qualification_cycle_id",
    "receipt_id",
    "receipt_path",
    "schema_version",
}
RECEIPT_FIELDS = {
    "d07_decision_required",
    "freeze_commit",
    "frozen_at_utc",
    "identity",
    "monetary_policy",
    "protected_closure",
    "provider_state",
    "qualification_cycle_id",
    "record_type",
    "schema_version",
    "table_qualification_freeze_receipt_id",
    "wb3_protection",
    "wb4_compact_transport",
    "wb5_scope_contract",
    "wb6_task_contracts",
}
WB3_TESTS = {
    "single_flight": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_concurrent_exact_request_has_one_mock_invocation"
    ),
    "http_402_batch_stop": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_http_402_calls_once_and_stops_batch"
    ),
    "unknown_remote_outcome": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_egress_crash_is_unknown_and_never_retried"
    ),
    "successful_exact_response_reuse": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_successful_exact_response_resume_has_zero_mock_invocation"
    ),
}


class TableQualificationFreezeError(RuntimeError):
    """Report an unsafe or incomplete table qualification freeze."""


def _regular_file(*, repo_root: Path, relative: Path, label: str) -> Path:
    """Resolve one safe repository-relative regular file.

    Args:
        repo_root: Repository authority root.
        relative: Portable relative path.
        label: Stable diagnostic label.

    Returns:
        Existing non-symlink regular path.
    """
    if relative.is_absolute() or ".." in relative.parts:
        raise TableQualificationFreezeError(
            "{} is not repository-relative".format(label)
        )
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        raise TableQualificationFreezeError("{} is absent or unsafe".format(label))
    return path


def _file_binding(*, repo_root: Path, relative: Path) -> Dict[str, object]:
    """Return a portable byte binding for one protected regular file.

    Args:
        repo_root: Repository authority root.
        relative: Repository-relative file locator.

    Returns:
        SHA-256 and size fields suitable for freeze/revalidation receipts.
    """
    path = _regular_file(repo_root=repo_root, relative=relative, label="file")
    return {
        "sha256": sha256_file(path=path),
        "size": path.stat().st_size,
    }


def _json_object(*, repo_root: Path, relative: Path, label: str) -> Dict[str, object]:
    """Load one strict JSON object from a safe repository file.

    Args:
        repo_root: Repository authority root.
        relative: Repository-relative JSON locator.
        label: Stable diagnostic label.

    Returns:
        Strict JSON object.
    """
    path = _regular_file(repo_root=repo_root, relative=relative, label=label)
    value = strict_json_file(path=path)
    if type(value) is not dict:
        raise TableQualificationFreezeError("{} root is not an object".format(label))
    return value


def _source_binding(
    *, repo_root: Path, value: object, label: str,
) -> Dict[str, object]:
    """Validate one frozen development, second-layout, or holdout source.

    Args:
        repo_root: Repository authority root.
        value: Matrix source declaration.
        label: Stable matrix field label.

    Returns:
        Validated source declaration with exact bytes where they already exist.
    """
    if type(value) is not dict or "source_kind" not in value:
        raise TableQualificationFreezeError("{} source is invalid".format(label))
    source = dict(value)
    kind = source["source_kind"]
    if kind == "IMMUTABLE_ATTEMPT":
        if set(source) != IMMUTABLE_SOURCE_FIELDS:
            raise TableQualificationFreezeError("{} fields are not exact".format(label))
        path = _regular_file(
            repo_root=repo_root,
            relative=Path(str(source["source_repo_relative_path"])),
            label=label + " source",
        )
        if sha256_file(path=path) != source["source_sha256"]:
            raise TableQualificationFreezeError("{} bytes differ".format(label))
    elif kind == "FUTURE_LIVE_IMMUTABLE_ATTEMPT":
        if set(source) != FUTURE_SOURCE_FIELDS:
            raise TableQualificationFreezeError("{} fields are not exact".format(label))
        if (
            type(source["fiscal_year"]) is not int
            or source["fiscal_year"] < 2000
        ):
            raise TableQualificationFreezeError("{} fiscal year is invalid".format(label))
    elif kind == "RECORDED_LAYOUT_FIXTURE":
        if set(source) != FIXTURE_SOURCE_FIELDS:
            raise TableQualificationFreezeError("{} fields are not exact".format(label))
        fixture_id = source["fixture_id"]
        if type(fixture_id) is not str or not fixture_id:
            raise TableQualificationFreezeError("{} fixture ID is invalid".format(label))
        manifest_relative = (
            LAYOUT_FIXTURE_ROOT / fixture_id / "fixture_manifest.json"
        )
        manifest = _json_object(
            repo_root=repo_root,
            relative=manifest_relative,
            label=label + " fixture manifest",
        )
        if manifest["fixture_id"] != fixture_id:
            raise TableQualificationFreezeError("{} fixture differs".format(label))
        source["fixture_manifest_sha256"] = sha256_file(
            path=repo_root / manifest_relative,
        )
        source["fixture_source_sha256"] = manifest["source_sha256"]
    else:
        raise TableQualificationFreezeError("{} source kind is unsupported".format(label))
    return source


def load_table_qualification_matrix(*, repo_root: Path) -> Dict[str, object]:
    """Load the complete table-family qualification matrix without egress.

    Args:
        repo_root: Repository authority root.

    Returns:
        Exact matrix entries keyed by family ID and the matrix file hash.
    """
    payload = _json_object(
        repo_root=repo_root,
        relative=MATRIX_PATH,
        label="table qualification matrix",
    )
    if (
        set(payload) != MATRIX_FIELDS
        or payload["schema_version"] != 1
        or payload["requirement_id"] != "issue_15_v1"
        or type(payload["families"]) is not list
        or not payload["families"]
    ):
        raise TableQualificationFreezeError("Table qualification matrix invalid")
    entries = {}
    for value in payload["families"]:
        if type(value) is not dict or set(value) != MATRIX_ENTRY_FIELDS:
            raise TableQualificationFreezeError("Matrix entry fields are not exact")
        entry = dict(value)
        family_id = entry["family_id"]
        if type(family_id) is not str or not family_id or family_id in entries:
            raise TableQualificationFreezeError("Matrix family identity is invalid")
        if (
            type(entry["reader_contract_id"]) is not str
            or not entry["reader_contract_id"]
            or entry["second_layout_policy"] != "REQUIRED"
            or entry["expected_output_status"]
            != "REVIEW_REQUIRED_OR_CANDIDATE"
            or type(entry["fresh_samples_required"]) is not int
            or entry["fresh_samples_required"] < 1
            or type(entry["expected_claims"]) is not list
            or not entry["expected_claims"]
            or len(entry["expected_claims"])
            != len(set(entry["expected_claims"]))
            or any(
                type(item) is not str or not item
                for item in entry["expected_claims"]
            )
            or type(entry["materially_different_criteria"]) is not list
            or len(entry["materially_different_criteria"]) < 2
            or type(entry["negative_cases"]) is not list
            or not entry["negative_cases"]
            or type(entry["review_policy"]) is not str
            or not entry["review_policy"]
        ):
            raise TableQualificationFreezeError("Matrix entry values are invalid")
        locator_range = entry["expected_locator_range"]
        limits = entry["token_context_limits"]
        if (
            type(locator_range) is not dict
            or set(locator_range) != LOCATOR_RANGE_FIELDS
            or locator_range["row_index_min"] != 0
            or locator_range["column_index_min"] != 0
            or locator_range["table_selection"]
            != "ONE_MODEL_SELECTED_TABLE_FROM_COMPLETE_DOCUMENT_SET"
            or locator_range["selected_competing_scope_evidence"]
            != "SAME_TARGET_TABLE_ONLY"
            or type(limits) is not dict
            or set(limits) != TOKEN_LIMIT_FIELDS
            or any(type(limits[field]) is not int or limits[field] < 1
                   for field in limits)
        ):
            raise TableQualificationFreezeError("Matrix limits are invalid")
        entry["development_source"] = _source_binding(
            repo_root=repo_root,
            value=entry["development_source"],
            label=family_id + " development",
        )
        entry["second_layout_source"] = _source_binding(
            repo_root=repo_root,
            value=entry["second_layout_source"],
            label=family_id + " second layout",
        )
        entry["post_freeze_holdout_source"] = _source_binding(
            repo_root=repo_root,
            value=entry["post_freeze_holdout_source"],
            label=family_id + " holdout",
        )
        entries[family_id] = entry
    return {
        "entries": entries,
        "matrix_sha256": sha256_file(path=repo_root / MATRIX_PATH),
    }


def _round_trip_sources(
    *, repo_root: Path,
) -> List[Tuple[str, Path, str]]:
    """Return the exact Marriott, Hilton, and Hyatt WB-4 source set.

    Args:
        repo_root: Repository authority root.

    Returns:
        Eleven fixture IDs with paths and declared raw SHA-256 values.
    """
    marriott = _json_object(
        repo_root=repo_root,
        relative=MARRIOTT_PROVENANCE_PATH,
        label="Marriott provenance",
    )
    sources = [
        (
            str(marriott["fixture_id"]),
            repo_root / str(marriott["source_repo_relative_path"]),
            str(marriott["source_sha256"]),
        )
    ]
    fixture_root = repo_root / LAYOUT_FIXTURE_ROOT
    if fixture_root.is_symlink() or not fixture_root.is_dir():
        raise TableQualificationFreezeError("Layout fixture root is unsafe")
    for root in sorted(path for path in fixture_root.iterdir() if path.is_dir()):
        manifest_relative = (
            LAYOUT_FIXTURE_ROOT / root.name / "fixture_manifest.json"
        )
        manifest = _json_object(
            repo_root=repo_root,
            relative=manifest_relative,
            label="layout fixture manifest",
        )
        fixture_id = str(manifest["fixture_id"])
        if not (
            fixture_id.startswith("hilton-")
            or fixture_id.startswith("hyatt-")
        ):
            continue
        sources.append(
            (
                fixture_id,
                repo_root / str(manifest["source_repo_relative_path"]),
                str(manifest["source_sha256"]),
            )
        )
    if len(sources) != 11:
        raise TableQualificationFreezeError("WB-4 source set is not eleven")
    return sources


def _measurement_task_contract(
    *, repo_root: Path, contracts: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Build one deterministic catalog task for transport measurement.

    Args:
        repo_root: Repository root owning catalog task authority.
        contracts: Validated table task contracts.

    Returns:
        Complete catalog task whose words cannot filter supplied tables.
    """
    if not contracts:
        raise TableQualificationFreezeError("Table measurement task is absent")
    contract_id = sorted(
        str(contract["task_contract_id"]) for contract in contracts
    )[0]
    return resolve_table_task_contract(
        repo_root=repo_root,
        task_contract_id=contract_id,
    )


def _measurement_receipts(
    *, repo_root: Path, contracts: Sequence[Mapping[str, object]],
) -> Tuple[List[Dict[str, object]], bool]:
    """Measure compact transport on all frozen sources without provider egress.

    Args:
        repo_root: Repository authority root.
        contracts: Validated static table task contracts.

    Returns:
        Eleven measurements and whether D-07 decision is required.
    """
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    policy = approved_transport_policy(requirement=requirement)
    runtime = load_provider_runtime_authority(
        repo_root=repo_root,
        provider=policy.provider,
        model=policy.model,
        api=policy.api,
    )
    task_contract = _measurement_task_contract(
        repo_root=repo_root,
        contracts=contracts,
    )
    measurements = []
    decision_required = False
    for fixture_id, source_path, expected_sha256 in _round_trip_sources(
        repo_root=repo_root,
    ):
        if source_path.is_symlink() or not source_path.is_file():
            raise TableQualificationFreezeError("WB-4 source is absent or unsafe")
        source_bytes = source_path.read_bytes()
        if sha256_bytes(content=source_bytes) != expected_sha256:
            raise TableQualificationFreezeError("WB-4 source hash differs")
        asset = build_table_grid(
            html_bytes=source_bytes,
            parent_raw_asset_ids=["sha256:" + expected_sha256],
            storage_uri="artifacts/vnext/table_qualification_freeze/{}.json".format(
                fixture_id
            ),
        )
        manifest = build_reader_input_manifest(
            derived_asset=asset,
            source_reference_ids=["source:" + expected_sha256],
        )
        compact_payload = build_reader_payload(
            manifest=manifest,
            derived_asset=asset,
            task_contract=task_contract,
        )
        expanded_body = {
            "system_contract": dict(READER_SYSTEM_CONTRACT),
            "task_contract": dict(task_contract),
            "reader_input_manifest": dict(manifest),
            "untrusted_table_data": list(asset["tables"]),
        }
        expanded_bytes = canonical_json_bytes(value=expanded_body)
        provider_envelope, _output_schema = build_provider_request_body(
            policy=policy,
            reader_request_bytes=compact_payload["request_bytes"],
        )
        estimated_tokens = estimate_context_tokens(
            request_body=provider_envelope,
            authority=runtime,
        )
        compact_transport = compact_payload["table_transport"]
        round_trip = compact_payload_receipt(transport=compact_transport)
        compression = (
            Decimal(len(compact_payload["request_bytes"]))
            / Decimal(len(expanded_bytes))
        ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)
        over_limit = (
            estimated_tokens > 100000
            or estimated_tokens > runtime["maximum_context_tokens"]
            or len(provider_envelope) > policy.maximum_payload_bytes
        )
        decision_required = decision_required or over_limit
        measurement_body = {
            "fixture_id": fixture_id,
            "source_sha256": expected_sha256,
            "expanded_reader_payload_bytes": len(expanded_bytes),
            "compact_reader_payload_bytes": len(compact_payload["request_bytes"]),
            "compression_ratio": format(compression, "f"),
            "provider_envelope_estimated_bytes": len(provider_envelope),
            "estimated_input_tokens": estimated_tokens,
            "actual_prompt_tokens": "NOT_RUN",
            "estimator_id": runtime["estimator_id"],
            "estimator_version": runtime["estimator_version"],
            "provider_context_authority_hash": runtime["context_authority_hash"],
            "round_trip_receipt_id": round_trip["round_trip_receipt_id"],
            "round_trip_hash": content_hash(value=round_trip),
            "context_or_resource_limit_exceeded": over_limit,
        }
        measurements.append({
            **measurement_body,
            "measurement_id": content_hash(value=measurement_body),
        })
    return measurements, decision_required


def _run_wb3_test_receipts(*, repo_root: Path) -> Dict[str, object]:
    """Execute four deterministic WB-3 regression tests with no real egress.

    Args:
        repo_root: Repository authority root.

    Returns:
        Content-addressed test outcome receipt keyed by the required invariant.
    """
    rows = {}
    for label, test_id in WB3_TESTS.items():
        completed = subprocess.run(
            args=[sys.executable, "-m", "unittest", "-q", test_id],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            encoding="utf-8",
            env={"PYTHONDONTWRITEBYTECODE": "1", **dict()},
        )
        if completed.returncode != 0:
            raise TableQualificationFreezeError(
                "WB-3 regression failed: {}".format(label)
            )
        rows[label] = {
            "test_id": test_id,
            "return_code": completed.returncode,
            "test_source_sha256": sha256_file(
                path=repo_root / "tests/vnext/test_invocation_control.py",
            ),
            "stdout_sha256": sha256_bytes(content=completed.stdout.encode("utf-8")),
            "stderr_sha256": sha256_bytes(content=completed.stderr.encode("utf-8")),
        }
    body = {"schema_version": 1, "tests": rows}
    return {**body, "wb3_regression_receipt_id": content_hash(value=body)}


def _root_state(*, repo_root: Path) -> Dict[str, object]:
    """Capture the exact unchanged R2 pointer and root compatibility mirrors.

    Args:
        repo_root: Repository authority root.

    Returns:
        Active publication identity and all protected root file byte hashes.
    """
    pointer = _json_object(
        repo_root=repo_root,
        relative=Path("outputs/active_publication.json"),
        label="active publication pointer",
    )
    if set(pointer) != {
        "bundle_manifest_sha256",
        "committed_at_utc",
        "previous_publication_id",
        "publication_id",
    }:
        raise TableQualificationFreezeError("Active publication pointer differs")
    root_paths = [
        Path("outputs/active_publication.json"),
        Path("outputs/metrics_matrix.csv"),
        Path("outputs/metric_evidence.csv"),
        Path("REPORT_十公司财务指标.md"),
    ]
    return {
        "active_publication_id": pointer["publication_id"],
        "active_pointer": _file_binding(
            repo_root=repo_root,
            relative=Path("outputs/active_publication.json"),
        ),
        "root_hashes": {
            path.as_posix(): _file_binding(repo_root=repo_root, relative=path)
            for path in root_paths
        },
    }


def _request_ledger_binding(*, repo_root: Path) -> Dict[str, object]:
    """Return the pre-freeze SEC ledger bytes without adding a request row.

    Args:
        repo_root: Repository authority root.

    Returns:
        Current ledger SHA-256 and data-row count.
    """
    path = _regular_file(
        repo_root=repo_root,
        relative=Path("evidence/requests_log.csv"),
        label="SEC request ledger",
    )
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        row_count = sum(1 for _row in csv.DictReader(file_obj))
    return {"sha256": sha256_file(path=path), "row_count": row_count}


def _protected_closure(
    *, repo_root: Path, matrix: Mapping[str, object],
    task_contracts: Mapping[str, object],
) -> Dict[str, object]:
    """Bind common and family-specific bytes that invalidate qualification.

    Args:
        repo_root: Repository authority root.
        matrix: Validated matrix entry mapping.
        task_contracts: Exact catalog contracts derived from SourceStrategy.

    Returns:
        Common protected files plus per-family dependent file/hash sets.
    """
    common_paths = [
        Path("config/provider_model_runtime.json"),
        Path("config/source_strategy_registry.json"),
        Path("config/source_strategy_fallback_representation.json"),
        Path("config/table_qualification_matrix.json"),
        Path("catalog/table_task_contracts.json"),
        Path("scripts/vnext/ai_adapter.py"),
        Path("scripts/vnext/evidence.py"),
        Path("scripts/vnext/invocation_control.py"),
        Path("scripts/vnext/reader.py"),
        Path("scripts/vnext/reader_input.py"),
        Path("scripts/vnext/records.py"),
        Path("scripts/vnext/review.py"),
        Path("scripts/vnext/scope_contract.py"),
        Path("scripts/vnext/stage_a_snapshot.py"),
        Path("scripts/vnext/table_grid.py"),
        Path("scripts/vnext/table_payload.py"),
        Path("scripts/vnext/table_qualification_freeze.py"),
        Path("scripts/vnext/table_task_contracts.py"),
        Path("requirements/issue_15_v1/CONTRACT.md"),
        Path("requirements/issue_15_v1/decision_register.json"),
        Path("tools/check_validation_snapshot.py"),
        Path("tools/create_stage_a_validation_snapshot.py"),
    ]
    common = {
        path.as_posix(): _file_binding(repo_root=repo_root, relative=path)
        for path in common_paths
    }
    disclosure_paths = {}
    disclosure_root = repo_root / "catalog" / "disclosures"
    if disclosure_root.is_symlink() or not disclosure_root.is_dir():
        raise TableQualificationFreezeError("Disclosure catalog is unsafe")
    for path in sorted(disclosure_root.glob("*.md")):
        if path.is_symlink() or not path.is_file():
            raise TableQualificationFreezeError("Disclosure catalog entry is unsafe")
        try:
            front, _body = parse_spec_document(
                text=path.read_text(encoding="utf-8"),
            )
        except (UnicodeDecodeError, SpecError) as error:
            raise TableQualificationFreezeError("Disclosure catalog is invalid") from error
        if front["kind"] != "disclosure_group":
            continue
        family_id = front["disclosure_group"]
        if type(family_id) is not str or not family_id:
            raise TableQualificationFreezeError("Disclosure family identity is invalid")
        if family_id in disclosure_paths:
            raise TableQualificationFreezeError("Disclosure family is duplicated")
        disclosure_paths[family_id] = path.relative_to(repo_root)
    families = {}
    for family_id in sorted(matrix["entries"]):
        family_contracts = [
            contract
            for contract in task_contracts["contracts"]
            if contract["reader_family_id"] == family_id
        ]
        paths = {
            Path(metric["path"])
            for contract in family_contracts
            for metric in contract["metric_specs"]
        }
        if family_id in disclosure_paths:
            paths.add(disclosure_paths[family_id])
        if not paths:
            raise TableQualificationFreezeError("Family semantic closure is empty")
        families[family_id] = {
            "matrix_entry_hash": content_hash(
                value=matrix["entries"][family_id],
            ),
            "files": {
                path.as_posix(): _file_binding(
                    repo_root=repo_root, relative=path,
                )
                for path in sorted(paths)
            },
        }
    return {"common_files": common, "families": families}


def _family_scope_closure(
    *, task_contracts: Mapping[str, object],
) -> Dict[str, object]:
    """Bind each family to its actual MetricSpec scope alias closure.

    Args:
        task_contracts: Exact contracts already derived from SourceStrategy.

    Returns:
        Per-family task/MetricSpec/scope identity mappings.

    Why:
        A single lodging disclosure scope cannot authorize financial table
        tasks.  Each selected task owns its own MetricSpec scope authority.
    """
    families = {}
    for family_id in task_contracts["authorized_family_ids"]:
        rows = []
        for contract in task_contracts["contracts"]:
            if contract["reader_family_id"] != family_id:
                continue
            metric_specs = contract["metric_specs"]
            if len(metric_specs) != 1:
                raise TableQualificationFreezeError("Task MetricSpec set is invalid")
            metric = metric_specs[0]
            scope_contract = metric["compiled"]["scope_contract"]
            rows.append({
                "task_contract_id": contract["task_contract_id"],
                "metric_id": metric["metric_id"],
                "metric_spec_path": metric["path"],
                "metric_spec_semantic_hash": metric["spec_semantic_hash"],
                "scope_contract_hash": scope_contract_hash(
                    contract=scope_contract,
                ),
                "exact_enum_alias_closure_hash": content_hash(
                    value=validate_scope_contract(value=scope_contract)[
                        "exact_enum_aliases"
                    ],
                ),
            })
        if not rows:
            raise TableQualificationFreezeError("Family scope closure is empty")
        families[family_id] = {"tasks": rows}
    return families


def _freeze_commit(*, repo_root: Path, freeze_commit: str) -> str:
    """Verify a caller-supplied Git commit before binding it in a receipt.

    Args:
        repo_root: Repository authority root.
        freeze_commit: Exact commit SHA that freezes protected source bytes.

    Returns:
        Full commit SHA resolved by local Git only.
    """
    completed = subprocess.run(
        args=["git", "rev-parse", "{}^{{commit}}".format(freeze_commit)],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise TableQualificationFreezeError("Freeze commit is not resolvable")
    resolved = completed.stdout.strip()
    clean = subprocess.run(
        args=["git", "diff", "--quiet", resolved, "--"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if clean.returncode != 0:
        raise TableQualificationFreezeError(
            "Tracked source differs from requested freeze commit"
        )
    return resolved


def build_table_qualification_freeze_receipt(
    *, repo_root: Path, freeze_commit: str, frozen_at_utc: str,
) -> Dict[str, object]:
    """Build one complete table qualification freeze receipt without writes.

    Args:
        repo_root: Repository authority root.
        freeze_commit: Exact committed source freeze identity.
        frozen_at_utc: Explicit UTC freeze timestamp.

    Returns:
        Complete content-addressed receipt body and identity.
    """
    try:
        parse_utc_timestamp(value=frozen_at_utc)
    except ValueError as error:
        raise TableQualificationFreezeError("Freeze timestamp is invalid") from error
    commit = _freeze_commit(repo_root=repo_root, freeze_commit=freeze_commit)
    task_contracts = load_table_task_contracts(repo_root=repo_root)
    matrix = load_table_qualification_matrix(repo_root=repo_root)
    if sorted(matrix["entries"]) != task_contracts["authorized_family_ids"]:
        raise TableQualificationFreezeError("Matrix family set differs from tasks")
    for family_id in task_contracts["authorized_family_ids"]:
        entry = matrix["entries"][family_id]
        matching_contracts = [
            contract for contract in task_contracts["contracts"]
            if contract["reader_family_id"] == family_id
        ]
        if (
            entry["reader_contract_id"]
            != matching_contracts[0]["reader_contract_id"]
            or sorted(entry["expected_claims"])
            != sorted(
                role
                for contract in matching_contracts
                for role in contract["required_roles"]
            )
        ):
            raise TableQualificationFreezeError("Matrix task binding differs")
    measurements, decision_required = _measurement_receipts(
        repo_root=repo_root,
        contracts=task_contracts["contracts"],
    )
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    policy = approved_transport_policy(requirement=requirement)
    root_state = _root_state(repo_root=repo_root)
    invocation_policy = effective_invocation_policy()
    wb3_tests = _run_wb3_test_receipts(repo_root=repo_root)
    opener_source = inspect.getsource(_open_provider_request).encode("utf-8")
    cycle_body = {
        "freeze_commit": commit,
        "requirement_closure_hash": task_contracts["requirement_closure_hash"],
        "active_publication_id": root_state["active_publication_id"],
        "matrix_sha256": matrix["matrix_sha256"],
    }
    cycle_id = content_hash(value=cycle_body)
    provider_ledger = {
        "sha256": sha256_bytes(content=b""),
        "row_count": 0,
        "path": (
            FREEZE_CYCLE_ROOT / cycle_id.split(":", maxsplit=1)[1]
            / "provider_ledger.jsonl"
        ).as_posix(),
    }
    family_scope_closure = _family_scope_closure(
        task_contracts=task_contracts,
    )
    body = {
        "record_type": "TABLE_QUALIFICATION_FREEZE_RECEIPT",
        "schema_version": 1,
        "freeze_commit": commit,
        "frozen_at_utc": frozen_at_utc,
        "qualification_cycle_id": cycle_id,
        "d07_decision_required": decision_required,
        "identity": {
            "requirement_closure_hash": task_contracts[
                "requirement_closure_hash"
            ],
            "parent_r2_active_publication_id": root_state[
                "active_publication_id"
            ],
            "active_pointer": root_state["active_pointer"],
            "root_hashes": root_state["root_hashes"],
        },
        "wb3_protection": {
            "invocation_control_semantic_hashes": invocation_policy,
            "provider_opener_identity": {
                "path": "scripts/vnext/ai_adapter.py",
                "symbol": "_open_provider_request",
                "source_sha256": sha256_bytes(content=opener_source),
            },
            "regression_receipt": wb3_tests,
        },
        "wb4_compact_transport": {
            "table_payload_serialization_version": (
                TABLE_PAYLOAD_SERIALIZATION_VERSION
            ),
            "encoder_source_sha256": sha256_file(
                path=repo_root / "scripts/vnext/table_payload.py",
            ),
            "decoder_source_sha256": sha256_file(
                path=repo_root / "scripts/vnext/table_payload.py",
            ),
            "decoder_semantic_version": DECODER_SEMANTIC_VERSION,
            "expanded_compact_identity_schema_hash": content_hash(
                value=[
                    "table_payload_serialization_version",
                    "expanded_derived_asset_id",
                    "expanded_grid_sha256",
                    "compact_payload_sha256",
                    "decoder_semantic_version",
                    "round_trip_receipt_id",
                ]
            ),
            "round_trip_receipts": measurements,
            "d07_full_table_no_prefilter_proof": {
                "table_grid_source_sha256": sha256_file(
                    path=repo_root / "scripts/vnext/table_grid.py",
                ),
                "reader_input_source_sha256": sha256_file(
                    path=repo_root / "scripts/vnext/reader_input.py",
                ),
                "all_fixture_count": len(measurements),
                "selection_parameters": [],
            },
            "maximum_estimated_input_tokens": max(
                item["estimated_input_tokens"] for item in measurements
            ),
        },
        "wb5_scope_contract": {
            "scope_contract_version": "2",
            "families": family_scope_closure,
            "evidence_binding_hash": sha256_file(
                path=repo_root / "scripts/vnext/evidence.py",
            ),
            "review_binding_hash": sha256_file(
                path=repo_root / "scripts/vnext/review.py",
            ),
        },
        "wb6_task_contracts": {
            "catalog_sha256": task_contracts["catalog_sha256"],
            "fallback_representation_sha256": task_contracts[
                "fallback_representation_sha256"
            ],
            "expected_table_metric_ids": task_contracts["table_metric_ids"],
            "expected_table_family_ids": task_contracts["table_family_ids"],
            "authorized_family_ids": task_contracts["authorized_family_ids"],
            "families": {
                family_id: {
                    "matrix_entry_hash": content_hash(
                        value=matrix["entries"][family_id],
                    ),
                    "contracts": [
                        {
                            key: contract[key]
                            for key in (
                                "task_contract_id",
                                "task_contract_hash",
                                "output_schema_hash",
                                "system_prompt_hash",
                            )
                        }
                        | {
                            "metric_specs": [
                                {
                                    key: metric[key]
                                    for key in (
                                        "metric_id",
                                        "path",
                                        "spec_semantic_hash",
                                        "spec_closure_hash",
                                    )
                                }
                                for metric in contract["metric_specs"]
                            ]
                        }
                        for contract in task_contracts["contracts"]
                        if contract["reader_family_id"] == family_id
                    ],
                }
                for family_id in task_contracts["authorized_family_ids"]
            },
        },
        "provider_state": {
            "provider": policy.provider,
            "model": policy.model,
            "api": policy.api,
            "provider_ledger_before": provider_ledger,
            "qualification_cycle_real_model_egress_count": 0,
            "qualification_cycle_paid_model_call_count": 0,
            "qualification_cycle_sec_egress_count": 0,
            "sec_ledger_before": _request_ledger_binding(repo_root=repo_root),
        },
        "monetary_policy": {
            "repository_monetary_budget_enforcement": False,
            "monetary_cost_observability_only": True,
            "forbidden_monetary_fields_present": [],
        },
        "protected_closure": _protected_closure(
            repo_root=repo_root,
            matrix=matrix,
            task_contracts=task_contracts,
        ),
    }
    receipt_id = content_hash(value=body)
    return {
        "table_qualification_freeze_receipt_id": receipt_id,
        **body,
    }


def write_table_qualification_freeze_receipt(
    *, repo_root: Path, freeze_commit: str, frozen_at_utc: str,
) -> Dict[str, object]:
    """Write one content-addressed freeze receipt and empty local cycle ledger.

    Args:
        repo_root: Repository authority root.
        freeze_commit: Exact committed source freeze identity.
        frozen_at_utc: Explicit UTC freeze timestamp.

    Returns:
        Receipt plus its portable repository-relative path.
    """
    receipt = build_table_qualification_freeze_receipt(
        repo_root=repo_root,
        freeze_commit=freeze_commit,
        frozen_at_utc=frozen_at_utc,
    )
    digest = receipt["table_qualification_freeze_receipt_id"].split(
        ":", maxsplit=1,
    )[1]
    receipt_relative = FREEZE_RECEIPT_ROOT / (digest + ".json")
    receipt_path = repo_root / receipt_relative
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path=receipt_path, value=receipt)
    ledger_relative = Path(receipt["provider_state"]["provider_ledger_before"]["path"])
    ledger_path = repo_root / ledger_relative
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists() and ledger_path.read_bytes() != b"":
        raise TableQualificationFreezeError("Qualification provider ledger differs")
    if not ledger_path.exists():
        ledger_path.write_bytes(b"")
    return {**receipt, "receipt_path": receipt_relative.as_posix()}


def validate_table_qualification_freeze(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Revalidate the configured freeze and return only affected family IDs.

    Args:
        repo_root: Repository authority root.

    Returns:
        Receipt identity and the exact family IDs invalidated by current drift.
    """
    pointer = _json_object(
        repo_root=repo_root,
        relative=FREEZE_POINTER_PATH,
        label="table qualification freeze pointer",
    )
    if set(pointer) != POINTER_FIELDS or pointer["schema_version"] != 1:
        raise TableQualificationFreezeError("Freeze pointer fields are invalid")
    receipt_relative = Path(str(pointer["receipt_path"]))
    receipt = _json_object(
        repo_root=repo_root,
        relative=receipt_relative,
        label="table qualification freeze receipt",
    )
    if set(receipt) != RECEIPT_FIELDS:
        raise TableQualificationFreezeError("Freeze receipt fields are invalid")
    receipt_id = receipt["table_qualification_freeze_receipt_id"]
    body = {
        key: receipt[key]
        for key in receipt
        if key != "table_qualification_freeze_receipt_id"
    }
    if (
        receipt_id != content_hash(value=body)
        or pointer["receipt_id"] != receipt_id
        or pointer["qualification_cycle_id"]
        != receipt["qualification_cycle_id"]
    ):
        raise TableQualificationFreezeError("Freeze receipt identity differs")
    protected = receipt["protected_closure"]
    common_drift = []
    for relative, binding in protected["common_files"].items():
        current = _file_binding(repo_root=repo_root, relative=Path(relative))
        if current != binding:
            common_drift.append(relative)
    invalidated = []
    drift_by_family = {}
    for family_id, family in protected["families"].items():
        drift = list(common_drift)
        for relative, binding in family["files"].items():
            current = _file_binding(repo_root=repo_root, relative=Path(relative))
            if current != binding:
                drift.append(relative)
        if drift:
            invalidated.append(family_id)
            drift_by_family[family_id] = sorted(drift)
    return {
        "receipt_id": receipt_id,
        "qualification_cycle_id": receipt["qualification_cycle_id"],
        "d07_decision_required": receipt["d07_decision_required"],
        "invalidated_family_ids": sorted(invalidated),
        "drift_by_family": drift_by_family,
    }


def require_table_qualification_freeze(
    *, repo_root: Path, family_id: str,
) -> Dict[str, object]:
    """Fail closed before future qualification when its family drifted.

    Args:
        repo_root: Repository authority root.
        family_id: Reader family planned for qualification.

    Returns:
        Validated freeze status for an unaffected authorized family.
    """
    status = validate_table_qualification_freeze(repo_root=repo_root)
    if status["d07_decision_required"] is True:
        raise TableQualificationFreezeError("D07_DECISION_REQUIRED")
    if family_id in status["invalidated_family_ids"]:
        raise TableQualificationFreezeError(
            "TABLE_QUALIFICATION_FREEZE_INVALIDATED:{}".format(family_id)
        )
    return status
