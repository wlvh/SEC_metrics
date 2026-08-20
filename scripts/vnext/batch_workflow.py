"""Create production structured Runs for the configured release metric set.

The Company Facts path evaluates every structured Spec and materializes any
trait-inapplicable table metrics. The no-source path handles companies for
which the complete release set is structurally inapplicable. Both leave an
OPEN Run for the shared validator/freeze workflow.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from sec_http import legacy_response_snapshot_paths, parse_request_log_rows
from sec_http import request_accession, request_log_attempt_id
from sec_http import request_headers_bytes_match_identity
from sec_http import validate_request_log_manifest

from .calculator import calculate_metric, metric_is_applicable
from .canonical import content_hash, sha256_bytes, sha256_file
from .canonical import strict_json_file
from .canonical import strict_json_loads
from .projector import load_release_plan
from .requirements import load_requirement_snapshot
from .run_store import append_run_record, create_run
from .sources import SourceError, companyfacts_structured_facts
from .sources import raw_blob_record, resolve_repository_file
from .sources import source_reference_record
from .specs import compile_spec_files, parse_spec_document
from .traits import repository_company_ciks, repository_company_traits


class BatchWorkflowError(RuntimeError):
    """Report an incomplete source, ledger, Spec, or release Run."""


REQUEST_BINDING_PROOF_FIELDS = {
    "request_body_sha256",
    "request_body_size",
    "request_headers_repo_relative_path",
    "request_headers_sha256",
    "request_headers_size",
    "request_locator_kind",
    "request_repo_relative_path",
}


def _verified_request_locator(
    *, repo_root: Path, row: Mapping[str, str], source_url: str,
    content_sha256: str, document_name: str,
) -> Dict[str, object]:
    """Verify one ledger-declared body/header pair and bind exact bytes.

    Args:
        repo_root: Repository containing the row-declared request artifacts.
        row: Exact parsed request-ledger row.
        source_url: SEC URL already joined to the planned source.
        content_sha256: Expected response body SHA-256.
        document_name: Expected response document name.

    Returns:
        Locator class, exact portable paths, and body/header hashes and sizes.

    Raises:
        BatchWorkflowError: When either locator is unsafe, its bytes differ,
            or an immutable-looking pair is not the derived immutable pair.
    """
    body_locator = str(row["repo_relative_path"])
    headers_locator = str(row["headers_repo_relative_path"])
    body_claims_attempt = body_locator.startswith(
        "evidence/request_attempts/"
    )
    headers_claims_attempt = headers_locator.startswith(
        "evidence/request_attempts/"
    )
    if body_claims_attempt != headers_claims_attempt:
        raise BatchWorkflowError(
            "Request-ledger immutable locator pair is incomplete"
        )
    try:
        declared_body = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path=body_locator,
        )
        declared_headers = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path=headers_locator,
        )
        if body_claims_attempt:
            expected_body, expected_headers = legacy_response_snapshot_paths(
                workdir=repo_root,
                content_sha256=content_sha256,
                source_url=source_url,
                status_code=str(row["status_code"]),
                content_length=str(row["content_length"]),
                document_name=document_name,
                timestamp_utc=str(row["timestamp_utc"]),
            )
            if (
                declared_body.resolve() != expected_body.resolve()
                or declared_headers.resolve() != expected_headers.resolve()
            ):
                raise BatchWorkflowError(
                    "Request-ledger locator differs from immutable attempt"
                )
        body_bytes = declared_body.read_bytes()
        headers_bytes = declared_headers.read_bytes()
        content_length = int(row["content_length"])
    except BatchWorkflowError:
        raise
    except (OSError, SourceError, ValueError) as error:
        raise BatchWorkflowError(
            "Request-ledger locator evidence is invalid"
        ) from error
    if (
        len(body_bytes) != content_length
        or sha256_bytes(content=body_bytes) != content_sha256
        or not request_headers_bytes_match_identity(
            content=headers_bytes,
            content_sha256=content_sha256,
            source_url=source_url,
            status_code=str(row["status_code"]),
            content_length=str(row["content_length"]),
        )
    ):
        raise BatchWorkflowError(
            "Request-ledger locator bytes differ from observation"
        )
    return {
        "request_body_sha256": sha256_bytes(content=body_bytes),
        "request_body_size": len(body_bytes),
        "request_headers_repo_relative_path": headers_locator,
        "request_headers_sha256": sha256_bytes(content=headers_bytes),
        "request_headers_size": len(headers_bytes),
        "request_locator_kind": (
            "IMMUTABLE_ATTEMPT"
            if body_claims_attempt
            else "LEGACY_WORKING_LOCATOR"
        ),
        "request_repo_relative_path": body_locator,
    }


def request_attempt_binding(
    *,
    repo_root: Path,
    source_url: str,
    content_sha256: str,
    accession: str,
    document_name: str,
) -> Dict[str, object]:
    """Select the latest verified immutable attempt for one SEC response.

    Args:
        repo_root: Repository containing the append-only request ledger.
        source_url: Exact official SEC request URL.
        content_sha256: Exact response-body digest without a prefix.
        accession: SourceReference filing identity. Company Facts requests may
            have an empty ledger accession while the selected fact does not.
        document_name: Exact response document name.

    Returns:
        Attempt identity, declared body/header locators, and locator class.
        Historical working locators remain usable by offline recorded Runs,
        but formal Cutover separately requires ``IMMUTABLE_ATTEMPT``.

    Raises:
        BatchWorkflowError: When the ledger is stale, exact source is absent,
            a claimed immutable locator is invalid, or legacy matches are
            ambiguous.

    Why:
        Re-fetching identical public bytes legitimately creates several
        ordered attempts. Selecting the latest verified immutable row avoids
        ambiguity without letting a direct working-file locator masquerade as
        publication evidence.
    """
    log_path = repo_root / "evidence" / "requests_log.csv"
    try:
        validate_request_log_manifest(log_path=log_path)
        rows = parse_request_log_rows(
            text=log_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise BatchWorkflowError(
            "Request ledger is unavailable or invalid"
        ) from error
    archive_accession = request_accession(source_url=source_url)
    matches = [
        (row_index, row)
        for row_index, row in enumerate(rows)
        if row["method"] == "GET"
        and row["status_code"] == "200"
        and not row["error"]
        and row["source_url"] == source_url
        and row["content_sha256"] == content_sha256
        and row["document_name"] == document_name
        and (
            row["accession"] == archive_accession == accession
            if archive_accession
            else row["accession"] in {"", accession}
        )
    ]
    if not matches:
        raise BatchWorkflowError(
            "Exact SEC response has no request-ledger attempt"
        )
    immutable = []
    legacy = []
    for row_index, row in matches:
        body_locator = str(row["repo_relative_path"])
        headers_locator = str(row["headers_repo_relative_path"])
        body_claims_attempt = body_locator.startswith(
            "evidence/request_attempts/"
        )
        headers_claims_attempt = headers_locator.startswith(
            "evidence/request_attempts/"
        )
        if body_claims_attempt != headers_claims_attempt:
            raise BatchWorkflowError(
                "Request-ledger immutable locator pair is incomplete"
            )
        if not body_claims_attempt:
            legacy.append((row_index, row))
            continue
        proof = _verified_request_locator(
            repo_root=repo_root,
            row=row,
            source_url=source_url,
            content_sha256=content_sha256,
            document_name=document_name,
        )
        immutable.append((row_index, row, proof))
    if immutable:
        row_index, row, proof = immutable[-1]
    else:
        if len(legacy) != 1:
            raise BatchWorkflowError(
                "Exact SEC response has ambiguous legacy ledger attempts"
            )
        row_index, row = legacy[0]
        proof = _verified_request_locator(
            repo_root=repo_root,
            row=row,
            source_url=source_url,
            content_sha256=content_sha256,
            document_name=document_name,
        )
    return {
        **proof,
        "request_attempt_id": request_log_attempt_id(
            row_index=row_index, row=row,
        ),
    }


def validate_request_attempt_binding(
    *,
    repo_root: Path,
    source_url: str,
    content_sha256: str,
    accession: str,
    document_name: str,
    request_attempt_id: str,
    require_immutable: bool,
) -> Dict[str, object]:
    """Rebuild one named SEC attempt from ledger and exact artifact bytes.

    Args:
        repo_root: Repository containing current ledger and attempt artifacts.
        source_url: Exact official SEC request URL.
        content_sha256: Expected response body digest.
        accession: Expected filing accession.
        document_name: Expected response document identity.
        request_attempt_id: Pinned append-only ledger row identity.
        require_immutable: Whether working-file legacy locators are forbidden.

    Returns:
        Exact attempt ID and mechanically rebuilt body/header locator proof.

    Raises:
        BatchWorkflowError: When the named row, source identity, locator bytes,
        or required immutable locator class differs.

    Why:
        A live Reader must verify the caller-named historical attempt rather
        than silently selecting a later ledger row after an append-only tail.
    """
    if type(require_immutable) is not bool:
        raise BatchWorkflowError("Request binding tier must be explicit")
    log_path = repo_root / "evidence" / "requests_log.csv"
    try:
        validate_request_log_manifest(log_path=log_path)
        rows = parse_request_log_rows(
            text=log_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise BatchWorkflowError(
            "Request ledger is unavailable or invalid"
        ) from error
    matches = [
        (row_index, row)
        for row_index, row in enumerate(rows)
        if request_log_attempt_id(row_index=row_index, row=row)
        == request_attempt_id
    ]
    if len(matches) != 1:
        raise BatchWorkflowError("Planned request attempt is absent")
    row_index, row = matches[0]
    archive_accession = request_accession(source_url=source_url)
    if (
        row["method"] != "GET"
        or row["status_code"] != "200"
        or row["error"]
        or row["source_url"] != source_url
        or row["content_sha256"] != content_sha256
        or row["document_name"] != document_name
        or (
            row["accession"] != archive_accession == accession
            if archive_accession
            else row["accession"] not in {"", accession}
        )
    ):
        raise BatchWorkflowError(
            "Planned request attempt differs from its SEC source"
        )
    proof = _verified_request_locator(
        repo_root=repo_root,
        row=row,
        source_url=source_url,
        content_sha256=content_sha256,
        document_name=document_name,
    )
    if require_immutable and proof["request_locator_kind"] != (
        "IMMUTABLE_ATTEMPT"
    ):
        raise BatchWorkflowError(
            "Live request attempt is not an immutable SEC artifact"
        )
    return {
        **proof,
        "request_attempt_id": request_log_attempt_id(
            row_index=row_index, row=row,
        ),
    }


def validate_planned_request_binding(
    *, repo_root: Path, source: Mapping[str, object]
) -> str:
    """Verify one pinned source-plan attempt against append-only authority.

    Args:
        repo_root: Repository containing current ledger and immutable attempts.
        source: Repository-derived plan source including source identity and
            every content-addressed request-binding proof field.

    Returns:
        Exact request attempt ID proven by current repository bytes.

    Raises:
        BatchWorkflowError: When fields are absent, the exact attempt changed,
            or its portable body/header locators are no longer valid. A legal
            append-only ledger tail does not invalidate this pinned attempt.
    """
    required = {
        "accession",
        "content_sha256",
        "document_name",
        "request_attempt_id",
        "request_headers_repo_relative_path",
        "request_locator_kind",
        "request_repo_relative_path",
        "source_url",
    } | REQUEST_BINDING_PROOF_FIELDS
    if not isinstance(source, Mapping) or not required.issubset(source):
        raise BatchWorkflowError("Planned request binding is incomplete")
    proof = validate_request_attempt_binding(
        repo_root=repo_root,
        source_url=str(source["source_url"]),
        content_sha256=str(source["content_sha256"]),
        accession=str(source["accession"]),
        document_name=str(source["document_name"]),
        request_attempt_id=str(source["request_attempt_id"]),
        require_immutable=False,
    )
    if any(source[field] != proof[field] for field in proof):
        raise BatchWorkflowError(
            "Planned request locators differ from the exact attempt"
        )
    return str(proof["request_attempt_id"])


def _metric_spec_paths(*, repo_root: Path) -> Dict[str, str]:
    """Resolve the release exact set to repository catalog paths.

    Args:
        repo_root: Repository containing release plan and metric catalog.

    Returns:
        Metric ID to portable Spec path mapping.
    """
    release_plan, _release_hash = load_release_plan(repo_root=repo_root)
    required_ids = set(release_plan["migrated_metric_ids"])
    paths = {}
    for path in sorted((repo_root / "catalog" / "metrics").glob("*.md")):
        if path.is_symlink() or not path.is_file():
            raise BatchWorkflowError("Metric catalog entry is unsafe")
        try:
            front, _body = parse_spec_document(
                text=path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise BatchWorkflowError(
                "Metric catalog entry is invalid"
            ) from error
        metric_id = front["metric_id"]
        if metric_id in required_ids:
            if metric_id in paths:
                raise BatchWorkflowError("Release MetricSpec is duplicated")
            paths[metric_id] = path.relative_to(repo_root).as_posix()
    if set(paths) != required_ids:
        raise BatchWorkflowError("Release MetricSpec exact set differs")
    return paths


def _compiled_release_specs(
    *, repo_root: Path
) -> Dict[str, Mapping[str, object]]:
    """Compile the exact release MetricSpec closure from repository files.

    Args:
        repo_root: Repository containing release plan and catalog.

    Returns:
        Compiled wrappers keyed by repository-declared metric ID.
    """
    paths = _metric_spec_paths(repo_root=repo_root)
    try:
        compiled = compile_spec_files(
            paths=[repo_root / paths[metric_id] for metric_id in paths],
        )
    except ValueError as error:
        raise BatchWorkflowError(
            "Release MetricSpec closure is invalid"
        ) from error
    if set(compiled) != set(paths):
        raise BatchWorkflowError("Compiled release MetricSpec set differs")
    return compiled


def _frozen_legacy_rows(
    *, repo_root: Path, legacy_snapshot_dir: Path, filename: str
) -> List[Dict[str, str]]:
    """Load one CSV only after matching its frozen baseline declaration.

    Args:
        repo_root: Repository containing the baseline manifest.
        legacy_snapshot_dir: Candidate legacy snapshot directory.
        filename: ``metrics_matrix.csv`` or ``metric_evidence.csv``.

    Returns:
        Ordered exact-schema row mappings.

    Raises:
        BatchWorkflowError: When bytes, schema, or row count drift.
    """
    if filename not in {"metrics_matrix.csv", "metric_evidence.csv"}:
        raise BatchWorkflowError("Release planner input is unsupported")
    manifest_path = (
        repo_root
        / "requirements"
        / "ai_first_v3_3_1"
        / "baseline_manifest.json"
    )
    try:
        manifest = strict_json_file(path=manifest_path)
    except (OSError, ValueError) as error:
        raise BatchWorkflowError(
            "Frozen baseline manifest is invalid"
        ) from error
    artifact_key = "outputs/" + filename
    if (
        not isinstance(manifest, dict)
        or "artifact_digests" not in manifest
        or artifact_key not in manifest["artifact_digests"]
    ):
        raise BatchWorkflowError("Frozen baseline artifact is absent")
    expected = manifest["artifact_digests"][artifact_key]
    required = {"fieldnames", "row_count", "sha256", "size"}
    if not isinstance(expected, dict) or set(expected) != required:
        raise BatchWorkflowError("Frozen baseline artifact schema differs")
    path = legacy_snapshot_dir / filename
    if path.is_symlink() or not path.is_file():
        raise BatchWorkflowError("Frozen legacy input is unsafe or absent")
    if (
        sha256_file(path=path) != expected["sha256"]
        or path.stat().st_size != expected["size"]
    ):
        raise BatchWorkflowError("Frozen legacy input bytes differ")
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        if reader.fieldnames != expected["fieldnames"]:
            raise BatchWorkflowError("Frozen legacy input schema differs")
        rows = [dict(row) for row in reader]
    if len(rows) != expected["row_count"]:
        raise BatchWorkflowError("Frozen legacy input row count differs")
    return rows


def _registry_rows(*, repo_root: Path) -> List[Dict[str, str]]:
    """Read the canonical company registry in stable order.

    Args:
        repo_root: Repository containing ``config/company_registry.csv``.

    Returns:
        Ordered company rows.
    """
    path = repo_root / "config" / "company_registry.csv"
    if path.is_symlink() or not path.is_file():
        raise BatchWorkflowError("Company registry is unsafe or absent")
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        if reader.fieldnames is None or not {
            "company_id",
            "display_name",
            "primary_cik",
        }.issubset(reader.fieldnames):
            raise BatchWorkflowError("Company registry fields are incomplete")
        rows = [dict(row) for row in reader]
    if not rows or len(rows) != len({row["company_id"] for row in rows}):
        raise BatchWorkflowError("Company registry identities are ambiguous")
    return rows


def _one_row(
    *, rows: Sequence[Mapping[str, str]], label: str
) -> Dict[str, str]:
    """Return one exact match rather than picking an arbitrary candidate.

    Args:
        rows: Filtered candidate rows.
        label: Diagnostic identity.

    Returns:
        The unique copied row.
    """
    if len(rows) != 1:
        raise BatchWorkflowError(label + " is absent or ambiguous")
    return dict(rows[0])


def _annual_period(
    *, rows: Sequence[Mapping[str, str]], company_name: str, fiscal_year: int
) -> Dict[str, object]:
    """Derive one annual target period for a structural-only company.

    Args:
        rows: Complete frozen legacy metric rows.
        company_name: Frozen display identity.
        fiscal_year: Batch fiscal year.

    Returns:
        Exact Run target period.
    """
    candidates = {
        (row["period_start"], row["period_end"])
        for row in rows
        if row["company"] == company_name
        and row["fiscal_year"] == str(fiscal_year)
        and row["fiscal_period"] == "FY"
        and row["period_start"] != row["period_end"]
    }
    if len(candidates) != 1:
        raise BatchWorkflowError(
            "Structural company annual target period is ambiguous"
        )
    period_start, period_end = next(iter(candidates))
    return {
        "fiscal_year": fiscal_year,
        "period_start": period_start,
        "period_end": period_end,
    }


def build_release_input_plan(
    *, repo_root: Path, legacy_snapshot_dir: Path
) -> Dict[str, object]:
    """Derive the ten-company source plan from frozen repository authority.

    Args:
        repo_root: Repository containing registry, traits, ledger, and sources.
        legacy_snapshot_dir: Exact frozen metrics/evidence snapshot.

    Returns:
        Content-addressed company plan. The plan carries coordinates and source
        identities but never carries a migrated value as calculator input.
    """
    metrics = _frozen_legacy_rows(
        repo_root=repo_root,
        legacy_snapshot_dir=legacy_snapshot_dir,
        filename="metrics_matrix.csv",
    )
    evidence = _frozen_legacy_rows(
        repo_root=repo_root,
        legacy_snapshot_dir=legacy_snapshot_dir,
        filename="metric_evidence.csv",
    )
    registry = _registry_rows(repo_root=repo_root)
    specs = _compiled_release_specs(repo_root=repo_root)
    structured_ids = [
        metric_id
        for metric_id in specs
        if specs[metric_id]["compiled"]["source_mode"]
        in {"structured", "structured_and_derived"}
    ]
    table_ids = [
        metric_id
        for metric_id in specs
        if specs[metric_id]["compiled"]["source_mode"] == "ai_table"
    ]
    structured_roots = [
        metric_id
        for metric_id in structured_ids
        if not specs[metric_id]["compiled"]["dependencies"]
    ]
    if len(structured_roots) != 1 or not table_ids:
        raise BatchWorkflowError("Release source-mode topology is unsupported")
    primary_metric_id = structured_roots[0]
    declared_years = {
        int(row["fiscal_year"])
        for row in metrics
        if row["metric_id"] == primary_metric_id
        and row["fiscal_year"].isdigit()
    }
    if len(declared_years) != 1:
        raise BatchWorkflowError("Frozen release fiscal year is ambiguous")
    target_fiscal_year = next(iter(declared_years))
    companies = []
    for registry_row in registry:
        company_id = registry_row["company_id"]
        company_name = registry_row["display_name"]
        traits = repository_company_traits(
            repo_root=repo_root, company_id=company_id,
        )
        primary_matches = [
            row
            for row in metrics
            if row["company"] == company_name
            and row["metric_id"] == primary_metric_id
        ]
        if not primary_matches:
            if any(
                metric_is_applicable(
                    applicability=specs[metric_id]["compiled"][
                        "applicability"
                    ],
                    traits=traits,
                )
                for metric_id in specs
            ):
                raise BatchWorkflowError(
                    "Applicable company lacks its structured release row"
                )
            target_period = _annual_period(
                rows=metrics,
                company_name=company_name,
                fiscal_year=target_fiscal_year,
            )
            companies.append(
                {
                    "company_id": company_id,
                    "mode": "STRUCTURAL_ONLY",
                    "target_period": target_period,
                }
            )
            continue
        primary = _one_row(
            rows=primary_matches, label="Frozen primary structured row",
        )
        structured_rows = {
            metric_id: _one_row(
                rows=[
                    row
                    for row in metrics
                    if row["company"] == company_name
                    and row["metric_id"] == metric_id
                ],
                label="Frozen structured metric row " + metric_id,
            )
            for metric_id in structured_ids
        }
        if any(
            row["period_start"] != primary["period_start"]
            or row["period_end"] != primary["period_end"]
            for row in structured_rows.values()
        ):
            raise BatchWorkflowError("Frozen structured metric periods differ")
        cik = registry_row["primary_cik"]
        if not cik.isdigit() or int(cik) <= 0:
            raise BatchWorkflowError("Registry primary CIK is invalid")
        document_name = "CIK{}.json".format(str(int(cik)).zfill(10))
        source_path = "evidence/companyfacts/" + document_name
        source_file = repo_root / source_path
        if source_file.is_symlink() or not source_file.is_file():
            raise BatchWorkflowError("Company Facts source is absent")
        companyfacts_source = {
            "accession": primary["accession"],
            "content_sha256": sha256_file(path=source_file),
            "document_name": document_name,
            "repo_relative_path": source_path,
            "source_url": (
                "https://data.sec.gov/api/xbrl/companyfacts/"
                + document_name
            ),
        }
        companyfacts_source.update(
            request_attempt_binding(
                repo_root=repo_root,
                source_url=companyfacts_source["source_url"],
                content_sha256=companyfacts_source["content_sha256"],
                accession=companyfacts_source["accession"],
                document_name=companyfacts_source["document_name"],
            )
        )
        company_plan = {
            "company_id": company_id,
            "mode": "COMPANYFACTS",
            "target_period": {
                "fiscal_year": target_fiscal_year,
                "period_start": primary["period_start"],
                "period_end": primary["period_end"],
            },
            "companyfacts_source": companyfacts_source,
        }
        applicable_table_ids = [
            metric_id
            for metric_id in table_ids
            if metric_is_applicable(
                applicability=specs[metric_id]["compiled"]["applicability"],
                traits=traits,
            )
        ]
        if applicable_table_ids:
            table_rows = {
                metric_id: _one_row(
                    rows=[
                        row
                        for row in evidence
                        if row["company"] == company_name
                        and row["metric_id"] == metric_id
                    ],
                    label="Frozen table-metric evidence " + metric_id,
                )
                for metric_id in applicable_table_ids
            }
            source = table_rows[applicable_table_ids[0]]
            source_fields = (
                "source_url",
                "repo_relative_path",
                "content_sha256",
                "accession",
                "document_name",
                "period_start",
                "period_end",
            )
            if any(
                row[field] != source[field]
                for row in table_rows.values()
                for field in source_fields
            ):
                raise BatchWorkflowError("Table-metric source bindings differ")
            if (
                source["period_start"] != primary["period_start"]
                or source["period_end"] != primary["period_end"]
            ):
                raise BatchWorkflowError(
                    "Table and structured source periods differ"
                )
            table_path = repo_root / source["repo_relative_path"]
            if (
                table_path.is_symlink()
                or not table_path.is_file()
                or sha256_file(path=table_path) != source["content_sha256"]
            ):
                raise BatchWorkflowError("Table-metric source bytes differ")
            table_source = {
                field: source[field]
                for field in (
                    "accession",
                    "content_sha256",
                    "document_name",
                    "repo_relative_path",
                    "source_url",
                )
            }
            table_source.update(
                request_attempt_binding(
                    repo_root=repo_root,
                    source_url=table_source["source_url"],
                    content_sha256=table_source["content_sha256"],
                    accession=table_source["accession"],
                    document_name=table_source["document_name"],
                )
            )
            company_plan["table_source"] = table_source
        companies.append(company_plan)
    body = {
        "schema_version": 1,
        "release_id": "ai_first_v3_3_1_phase_1",
        "target_fiscal_year": target_fiscal_year,
        "legacy_input_hashes": {
            filename: sha256_file(path=legacy_snapshot_dir / filename)
            for filename in ("metric_evidence.csv", "metrics_matrix.csv")
        },
        "companies": companies,
    }
    plan = dict(body)
    plan["release_input_plan_id"] = content_hash(value=body)
    return plan


def _structured_concepts(
    *, compiled_spec: Mapping[str, object]
) -> List[str]:
    """Collect every approved structured concept from one compiled Spec.

    Args:
        compiled_spec: Repository-compiled MetricSpec wrapper.

    Returns:
        Sorted unique qualified concept names.
    """
    semantic = compiled_spec["compiled"]
    pending = [semantic["inputs"]]
    concepts: List[str] = []
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key in value:
                if key == "approved_concepts":
                    approved = value[key]
                    if not isinstance(approved, list) or any(
                        type(concept) is not str or not concept
                        for concept in approved
                    ):
                        raise BatchWorkflowError(
                            "Compiled structured concepts are invalid"
                        )
                    concepts.extend(approved)
                else:
                    pending.append(value[key])
        elif isinstance(value, list):
            pending.extend(value)
    return sorted(set(concepts))


def _target(
    *,
    company_id: str,
    target_period: Mapping[str, object],
    accession: object,
    entity: object,
) -> Dict[str, object]:
    """Build the one canonical structured result target.

    Args:
        company_id: Registry company identity.
        target_period: Explicit fiscal-year/start/end mapping.
        accession: Filing observation identity or ``None`` for structural N/A.
        entity: SEC entity identity or ``None`` for structural N/A.

    Returns:
        Exact calculator target mapping.
    """
    scope = {"consolidation": "entity"}
    return {
        "company_id": company_id,
        "period_start": target_period["period_start"],
        "period_end": target_period["period_end"],
        "accession": accession,
        "entity": entity,
        "scope": scope,
        "scope_key": content_hash(value=scope),
    }


def _spec_hashes(
    *, repo_root: Path, metric_ids: Sequence[str]
) -> Dict[str, str]:
    """Hash the exact MetricSpec files consumed by one Run.

    Args:
        repo_root: Repository containing the catalog.
        metric_ids: Ordered metric IDs included in the Run.

    Returns:
        Portable path to exact file digest mapping.
    """
    paths = _metric_spec_paths(repo_root=repo_root)
    if any(metric_id not in paths for metric_id in metric_ids):
        raise BatchWorkflowError("Run metric is outside the release exact set")
    return {
        paths[metric_id]: sha256_file(path=repo_root / paths[metric_id])
        for metric_id in metric_ids
    }


def create_companyfacts_release_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    company_id: str,
    target_period: Mapping[str, object],
    source_repo_relative_path: str,
    source_url: str,
    accession: str,
    document_name: str,
    request_attempt_id: str,
) -> Dict[str, object]:
    """Create one OPEN structured Run from exact Company Facts bytes.

    Args:
        repo_root: Repository authority for source, registry, Specs, and
            ledger.
        run_dir: New Run directory.
        run_id: Unique audit identity.
        company_id: Registry company identity.
        target_period: Fiscal year and exact inclusive period.
        source_repo_relative_path: Existing Company Facts response path.
        source_url: Exact official SEC Company Facts URL.
        accession: Filing observation selected from the response.
        document_name: Expected ``CIK##########.json`` name.
        request_attempt_id: Exact repository-ledger attempt selected by the
            content-addressed release plan.

    Returns:
        Run ID plus computed result identities and business fields. Any table
        metric made inapplicable by traits is persisted as structural N/A.
    """
    specs = _compiled_release_specs(repo_root=repo_root)
    traits = repository_company_traits(
        repo_root=repo_root, company_id=company_id,
    )
    raw = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=source_repo_relative_path,
        media_type="application/json",
    )
    content_sha256 = str(raw["raw_asset_id"]).split(":", maxsplit=1)[1]
    current_binding = request_attempt_binding(
        repo_root=repo_root,
        source_url=source_url,
        content_sha256=content_sha256,
        accession=accession,
        document_name=document_name,
    )
    if current_binding["request_attempt_id"] != request_attempt_id:
        raise BatchWorkflowError(
            "Company Facts request binding changed after planning"
        )
    source = source_reference_record(
        raw_blob=raw,
        company_id=company_id,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role="companyfacts",
        request_attempt_id=request_attempt_id,
    )
    raw_bytes = (repo_root / source_repo_relative_path).read_bytes()
    try:
        payload = strict_json_loads(text=raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise BatchWorkflowError(
            "Company Facts root cannot identify the target entity"
        ) from error
    if not isinstance(payload, dict) or "cik" not in payload:
        raise BatchWorkflowError("Company Facts root CIK is absent")
    entity = str(payload["cik"])
    if not entity.isdigit() or int(entity) <= 0:
        raise BatchWorkflowError("Company Facts root CIK is invalid")
    entity = str(int(entity))
    target = _target(
        company_id=company_id,
        target_period=target_period,
        accession=accession,
        entity=entity,
    )
    allowed_ciks = repository_company_ciks(
        repo_root=repo_root, company_id=company_id,
    )
    results = {}
    traces = []
    observations_by_metric = {}
    structured_pending = {
        metric_id
        for metric_id in specs
        if specs[metric_id]["compiled"]["source_mode"]
        in {"structured", "structured_and_derived"}
    }
    while structured_pending:
        ready = sorted(
            metric_id
            for metric_id in structured_pending
            if set(specs[metric_id]["compiled"]["dependencies"])
            .issubset(set(results))
        )
        if not ready:
            raise BatchWorkflowError("Structured dependency graph is cyclic")
        for metric_id in ready:
            dependencies = specs[metric_id]["compiled"]["dependencies"]
            verified_observations = [
                observation
                for dependency_id in dependencies
                for observation in observations_by_metric[dependency_id]
            ]
            facts = companyfacts_structured_facts(
                raw_bytes=raw_bytes,
                source_reference=source,
                approved_concepts=_structured_concepts(
                    compiled_spec=specs[metric_id],
                ),
                allowed_ciks=allowed_ciks,
                include_instant=False,
            )
            result, trace, observations = calculate_metric(
                compiled_spec=specs[metric_id],
                target=target,
                company_traits=traits,
                structured_facts=facts,
                verified_observations=verified_observations,
            )
            results[metric_id] = result
            traces.append(trace)
            observations_by_metric[metric_id] = observations
            structured_pending.remove(metric_id)
    for metric_id in specs:
        if specs[metric_id]["compiled"]["source_mode"] != "ai_table":
            continue
        if metric_is_applicable(
            applicability=specs[metric_id]["compiled"]["applicability"],
            traits=traits,
        ):
            continue
        result, trace, observations = calculate_metric(
            compiled_spec=specs[metric_id],
            target=target,
            company_traits=traits,
            structured_facts=[],
            verified_observations=[],
        )
        if observations or result["applicability"] != "N_A_STRUCTURAL":
            raise BatchWorkflowError(
                "Inapplicable table metric did not produce structural N/A"
            )
        results[metric_id] = result
        traces.append(trace)
        observations_by_metric[metric_id] = []
    release_plan, _release_hash = load_release_plan(repo_root=repo_root)
    metric_ids = [
        metric_id
        for metric_id in release_plan["migrated_metric_ids"]
        if metric_id in results
    ]
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1",
    )
    create_run(
        run_dir=run_dir,
        run_id=run_id,
        company_id=company_id,
        company_traits=traits,
        target_period=target_period,
        source_references=[source],
        missing_required_source_roles=[],
        spec_file_hashes=_spec_hashes(
            repo_root=repo_root, metric_ids=metric_ids,
        ),
        requirement_hashes=requirement["hashes"],
    )
    records = [raw, source]
    observation_ids = set()
    for metric_id in metric_ids:
        for observation in observations_by_metric[metric_id]:
            observation_id = str(observation["observation_id"])
            if observation_id not in observation_ids:
                records.append(observation)
                observation_ids.add(observation_id)
    for trace in traces:
        records.append(trace)
        records.append(results[str(trace["metric_id"])])
    for record in records:
        append_run_record(run_dir=run_dir, record=record)
    return {
        "run_id": run_id,
        "status": "OPEN",
        "results": {
            metric_id: {
                "result_id": results[metric_id]["result_id"],
                "applicability": results[metric_id]["applicability"],
                "publication": results[metric_id]["publication"],
                "quality": results[metric_id]["quality"],
                "value": results[metric_id]["value"],
                "unit": results[metric_id]["unit"],
            }
            for metric_id in metric_ids
        },
    }


def create_structural_release_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    company_id: str,
    target_period: Mapping[str, object],
) -> Dict[str, object]:
    """Create an OPEN no-source Run when all release metrics are N/A.

    Args:
        repo_root: Repository authority for registry, Specs, and Requirement.
        run_dir: New Run directory.
        run_id: Unique audit identity.
        company_id: Registry company identity.
        target_period: Fiscal year and exact inclusive period.

    Returns:
        Run ID and the complete durable structural Result exact set.
    """
    specs = _compiled_release_specs(repo_root=repo_root)
    traits = repository_company_traits(
        repo_root=repo_root, company_id=company_id,
    )
    target = _target(
        company_id=company_id,
        target_period=target_period,
        accession=None,
        entity=None,
    )
    results = {}
    records = []
    release_plan, _release_hash = load_release_plan(repo_root=repo_root)
    metric_ids = list(release_plan["migrated_metric_ids"])
    for metric_id in metric_ids:
        result, trace, observations = calculate_metric(
            compiled_spec=specs[metric_id],
            target=target,
            company_traits=traits,
            structured_facts=[],
            verified_observations=[],
        )
        if observations or result["applicability"] != "N_A_STRUCTURAL":
            raise BatchWorkflowError(
                "No-source release Run contains an applicable metric"
            )
        records.extend((trace, result))
        results[metric_id] = result
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1",
    )
    create_run(
        run_dir=run_dir,
        run_id=run_id,
        company_id=company_id,
        company_traits=traits,
        target_period=target_period,
        source_references=[],
        missing_required_source_roles=[],
        spec_file_hashes=_spec_hashes(
            repo_root=repo_root,
            metric_ids=metric_ids,
        ),
        requirement_hashes=requirement["hashes"],
    )
    for record in records:
        append_run_record(run_dir=run_dir, record=record)
    return {
        "run_id": run_id,
        "status": "OPEN",
        "results": {
            metric_id: {
                "result_id": results[metric_id]["result_id"],
                "applicability": results[metric_id]["applicability"],
                "publication": results[metric_id]["publication"],
                "quality": results[metric_id]["quality"],
                "value": results[metric_id]["value"],
                "unit": results[metric_id]["unit"],
            }
            for metric_id in metric_ids
        },
    }
