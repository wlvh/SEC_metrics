"""Compose the metric-neutral table-review shadow workflow.

This module wires SourceReference, complete table-grid input, an approved or
recorded AI attempt, strict Candidate, mechanical Evidence, safe review
context, and ReviewUnit into one OPEN Run. It never publishes, calls SEC, or
creates a HUMAN decision; those remain explicit later transitions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Sequence

from .ai_adapter import AIAdapter, run_ai_attempt
from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import sha256_file, strict_json_loads
from .evidence import check_evidence
from .reader import validate_reader_output
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .reader_input import required_reader_roles
from .render import build_review_context, render_review_markdown
from .review import build_review_unit, effective_review_decision
from .observations import reviewed_observation, scope_key
from .requirements import load_requirement_snapshot
from .run_store import append_run_record, create_run, load_open_run
from .run_store import load_run_bound_specs
from .run_store import RunStoreError
from .run_store import write_review_assets
from .run_store import write_attempt_payloads
from .sources import load_raw_blob_bytes, raw_blob_record
from .sources import source_reference_record
from .specs import SpecError, compile_spec_file, parse_spec_document
from .table_grid import build_table_grid
from .traits import TraitError, repository_company_traits


class WorkflowError(RuntimeError):
    """Report incomplete compiled semantics or inconsistent Reader output."""


def _required_roles(*, compiled_spec: Mapping[str, object]) -> Sequence[str]:
    """Read ordered disclosure roles from compiled projection semantics.

    Args:
        compiled_spec: Compiled disclosure-group Spec.

    Returns:
        Ordered selected plus supporting roles.

    Raises:
        WorkflowError: On absent, empty, or duplicated role declaration.
    """
    try:
        return required_reader_roles(compiled_spec=compiled_spec)
    except ValueError as error:
        raise WorkflowError("Disclosure role contract is invalid") from error


def _load_disclosure_plan(
    *, repo_root: Path, disclosure_spec_path: str,
) -> tuple[Dict[str, object], Sequence[str]]:
    """Load one disclosure Spec and derive its exact metric Spec paths.

    Args:
        repo_root: Repository containing the authoritative catalog.
        disclosure_spec_path: Repository-relative disclosure Spec locator.

    Returns:
        Compiled disclosure wrapper and ordered closure paths.

    Raises:
        WorkflowError: When the locator escapes the disclosure catalog or its
            role metrics cannot be resolved exactly from repository files.
    """
    relative = Path(disclosure_spec_path)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[:2] != ("catalog", "disclosures")
    ):
        raise WorkflowError("Disclosure Spec locator is invalid")
    try:
        compiled_spec = compile_spec_file(
            path=repo_root / relative,
            dependency_specs={},
        )
    except SpecError as error:
        raise WorkflowError("Disclosure Spec cannot be compiled") from error
    semantic = compiled_spec["compiled"]
    if semantic["kind"] != "disclosure_group":
        raise WorkflowError("Workflow requires a disclosure-group Spec")
    required_metric_ids = set(
        semantic["legacy_projection"]["role_metric_ids"].values()
    )
    metric_paths = {}
    for candidate in sorted((repo_root / "catalog" / "metrics").glob("*.md")):
        if candidate.is_symlink() or not candidate.is_file():
            raise WorkflowError("Metric Spec catalog entry is unsafe")
        try:
            front, _body = parse_spec_document(
                text=candidate.read_text(encoding="utf-8")
            )
        except (UnicodeDecodeError, SpecError) as error:
            raise WorkflowError("Metric Spec catalog is invalid") from error
        metric_id = front["metric_id"]
        if type(metric_id) is not str or not metric_id:
            raise WorkflowError("Metric Spec identity is invalid")
        if metric_id in required_metric_ids:
            if metric_id in metric_paths:
                raise WorkflowError("Disclosure metric Spec is duplicated")
            metric_paths[metric_id] = candidate
    if set(metric_paths) != required_metric_ids:
        raise WorkflowError("Disclosure metric Spec exact set differs")
    paths = [repo_root / relative]
    paths.extend(metric_paths[metric_id] for metric_id in sorted(metric_paths))
    return compiled_spec, [
        path.relative_to(repo_root).as_posix() for path in paths
    ]


def create_review_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    company_id: str,
    target_period: Mapping[str, object],
    source_repo_relative_path: str,
    source_media_type: str,
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    request_attempt_id: str,
    disclosure_spec_path: str,
    adapter: AIAdapter,
    clock: Optional[Callable[[], datetime]],
) -> Dict[str, object]:
    """Create one OPEN shadow Run through a pending ReviewUnit.

    Args:
        repo_root: Repository containing exact raw bytes and Specs.
        run_dir: New run-scoped directory.
        run_id: Opaque Run identity.
        company_id: Logical company identity.
        target_period: Explicit target-period mapping.
        source_repo_relative_path: Existing raw filing path.
        source_media_type: Raw filing media type.
        source_url: Official SEC source URL.
        accession: Filing accession.
        document_name: Filing document name.
        source_role: Run source role.
        request_attempt_id: Existing SEC ledger attempt identity.
        disclosure_spec_path: Repository-relative disclosure Spec locator.
        adapter: Recorded or repository-approved AI transport.
        clock: Explicit UTC clock or ``None`` for real UTC audit time.

    Returns:
        Run, attempt, Candidate, Evidence, and ReviewUnit identities. Rejection
        returns without creating a ReviewUnit and never invokes a fallback.
    """
    compiled_spec, spec_paths = _load_disclosure_plan(
        repo_root=repo_root,
        disclosure_spec_path=disclosure_spec_path,
    )
    try:
        company_traits = repository_company_traits(
            repo_root=repo_root, company_id=company_id,
        )
    except TraitError as error:
        raise WorkflowError(
            "Repository company traits are invalid"
        ) from error
    semantic = compiled_spec["compiled"]
    required_traits = set(semantic["applicability"]["all"])
    forbidden_traits = set(semantic["applicability"]["none"])
    supplied_traits = set(company_traits)
    if not required_traits.issubset(supplied_traits) or (
        forbidden_traits & supplied_traits
    ):
        return {
            "run_id": run_id,
            "status": "N_A_STRUCTURAL",
            "attempt_count": 0,
        }
    roles = _required_roles(compiled_spec=compiled_spec)
    raw_blob = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=source_repo_relative_path,
        media_type=source_media_type,
    )
    source_reference = source_reference_record(
        raw_blob=raw_blob,
        company_id=company_id,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id=request_attempt_id,
    )
    spec_file_hashes = {
        relative: sha256_file(path=repo_root / relative)
        for relative in spec_paths
    }
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1",
    )
    create_run(
        run_dir=run_dir,
        run_id=run_id,
        company_id=company_id,
        company_traits=company_traits,
        target_period=target_period,
        source_references=[source_reference],
        missing_required_source_roles=[],
        spec_file_hashes=spec_file_hashes,
        requirement_hashes=requirement["hashes"],
    )
    append_run_record(run_dir=run_dir, record=raw_blob)
    append_run_record(run_dir=run_dir, record=source_reference)
    # Re-read through the RawBlob verifier so review input cannot race away
    # from the exact source identity created above.
    raw_bytes = load_raw_blob_bytes(repo_root=repo_root, raw_blob=raw_blob)
    derived_asset = build_table_grid(
        html_bytes=raw_bytes,
        parent_raw_asset_ids=[str(raw_blob["raw_asset_id"])],
        storage_uri=(
            "artifacts/vnext/derived/{}.json".format(
                str(raw_blob["raw_asset_id"]).split(":", maxsplit=1)[1]
            )
        ),
    )
    append_run_record(run_dir=run_dir, record=derived_asset)
    reader_manifest = build_reader_input_manifest(
        derived_asset=derived_asset,
        source_reference_ids=[str(source_reference["source_reference_id"])],
    )
    append_run_record(run_dir=run_dir, record=reader_manifest)
    prepared_request = prepare_reader_request(
        manifest=reader_manifest,
        derived_asset=derived_asset,
        compiled_spec=compiled_spec,
    )

    response, raw_response, attempt = run_ai_attempt(
        adapter=adapter,
        prepared_request=prepared_request,
        clock=clock,
    )
    write_attempt_payloads(
        run_dir=run_dir,
        attempt=attempt,
        request_bytes=prepared_request.request_bytes,
        task_contract_bytes=prepared_request.task_contract_bytes,
        raw_response_bytes=raw_response,
    )
    append_run_record(run_dir=run_dir, record=attempt)
    if response is None:
        return {
            "run_id": run_id,
            "status": "FAILED_ATTEMPT",
            "attempt_id": attempt["attempt_id"],
        }
    candidate = validate_reader_output(
        response_text=response.decode("utf-8"),
        attempt_id=str(attempt["attempt_id"]),
        required_roles=roles,
        source_reference_ids=[str(source_reference["source_reference_id"])],
        derived_asset_ids=[str(derived_asset["derived_asset_id"])],
    )
    if candidate["disclosure_group"] != semantic["disclosure_group"]:
        raise WorkflowError("Reader disclosure group differs from Spec")
    append_run_record(run_dir=run_dir, record=candidate)
    evidence = check_evidence(
        candidate=candidate,
        derived_asset=derived_asset,
        reader_manifest=reader_manifest,
        reader_payload_body=strict_json_loads(
            text=prepared_request.request_bytes.decode("utf-8")
        ),
        source_references=[source_reference],
        identity_constraints=semantic["identity_constraints"],
    )
    append_run_record(run_dir=run_dir, record=evidence)
    if evidence["status"] != "PASS":
        return {
            "run_id": run_id,
            "status": "EVIDENCE_REJECTED",
            "attempt_id": attempt["attempt_id"],
            "candidate_hash": candidate["candidate_hash"],
            "evidence_check_id": evidence["evidence_check_id"],
        }
    context = build_review_context(
        candidate=candidate,
        evidence_check=evidence,
        derived_asset=derived_asset,
        source_bindings=[source_reference],
        spec_semantic_hash=str(compiled_spec["spec_semantic_hash"]),
        required_claims=semantic["required_claims"],
    )
    rendered = render_review_markdown(
        review_context=context["review_context"],
    )
    review_unit = build_review_unit(
        candidate=candidate,
        evidence_check=evidence,
        source_bindings=[source_reference],
        compiled_spec=compiled_spec,
        review_context_hash=str(context["review_context_hash"]),
        rendered_review_hash=str(rendered["rendered_review_hash"]),
        renderer_semantic_version=str(
            rendered["review_renderer_semantic_version"]
        ),
    )
    append_run_record(run_dir=run_dir, record=review_unit)
    write_review_assets(
        run_dir=run_dir,
        review_unit=review_unit,
        review_context_bytes=context["review_context_bytes"],
        rendered_review_bytes=rendered["bytes"],
    )
    return {
        "run_id": run_id,
        "status": "PENDING_HUMAN_REVIEW",
        "attempt_id": attempt["attempt_id"],
        "candidate_hash": candidate["candidate_hash"],
        "evidence_check_id": evidence["evidence_check_id"],
        "review_unit_hash": review_unit["review_unit_hash"],
    }


def finalize_reviewed_direct_results(
    *,
    run_dir: Path,
    repo_root: Path,
) -> Dict[str, object]:
    """Turn one effective whole-unit decision into observations/results.

    Args:
        run_dir: OPEN Run after HUMAN decision append.
        repo_root: Repository whose Run-bound Specs are authoritative.

    Returns:
        Ordered created observation/result/trace identities and decision.

    Raises:
        WorkflowError: On ambiguous/stale review content, repository drift,
        period mismatch, or incomplete role classification.
    """
    manifest, records, decisions = load_open_run(run_dir=run_dir)
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    if len(units) != 1:
        raise WorkflowError("Finalization requires one ReviewUnit")
    unit = units[0]
    bound_decisions = [
        decision
        for decision in decisions
        if decision["review_unit_hash"] == unit["review_unit_hash"]
    ]
    try:
        decision = effective_review_decision(
            review_unit=unit, decisions=bound_decisions,
        )
    except ValueError as error:
        raise WorkflowError(
            "Review decision semantic binding is invalid"
        ) from error
    evidence_matches = [
        record
        for record in records
        if record["record_type"] == "EVIDENCE_CHECK"
        and record["evidence_check_id"] == unit["evidence_check_id"]
    ]
    candidate_matches = [
        record
        for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
        and evidence_matches
        and record["candidate_hash"] == evidence_matches[0]["candidate_hash"]
    ]
    if len(evidence_matches) != 1 or len(candidate_matches) != 1:
        raise WorkflowError("Review Candidate/Evidence binding is ambiguous")
    candidate = candidate_matches[0]
    try:
        compiled_by_id = load_run_bound_specs(
            repo_root=repo_root, manifest=manifest,
        )
    except RunStoreError as error:
        raise WorkflowError(
            "Run-bound repository Specs are invalid"
        ) from error
    disclosure_matches = [
        wrapper
        for wrapper in compiled_by_id.values()
        if wrapper["spec_semantic_hash"] == unit["spec_semantic_hash"]
    ]
    if len(disclosure_matches) != 1:
        raise WorkflowError("Reviewed disclosure Spec is not authoritative")
    disclosure_spec = disclosure_matches[0]
    if disclosure_spec["compiled"] != unit["compiled_spec"]:
        raise WorkflowError("Reviewed disclosure Spec differs from repository")
    roles = _required_roles(compiled_spec=disclosure_spec)
    projection = disclosure_spec["compiled"]["legacy_projection"]
    published_roles = list(projection["roles"])
    supporting_roles = list(projection["supporting_roles"])
    if set(roles) != set(candidate["selected"]):
        raise WorkflowError("Reviewed role classification exact set differs")
    role_metric_specs = {}
    for role in published_roles:
        metric_id = str(projection["role_metric_ids"][role])
        if metric_id not in compiled_by_id:
            raise WorkflowError("Published role MetricSpec is absent from Run")
        role_metric_specs[role] = compiled_by_id[metric_id]
    target_scope = dict(unit["required_claims"])
    for role in role_metric_specs:
        metric_claims = role_metric_specs[role]["compiled"][
            "required_claims"
        ]
        if dict(metric_claims) != target_scope:
            raise WorkflowError(
                "Reviewed metric required claims differ from ReviewUnit"
            )
    target = {
        "company_id": manifest["company_id"],
        "period_start": manifest["target_period"]["period_start"],
        "period_end": manifest["target_period"]["period_end"],
        "scope": target_scope,
        "scope_key": scope_key(scope=target_scope),
    }
    expected_claimed_period = "FY{}".format(
        manifest["target_period"]["fiscal_year"]
    )
    if any(
        candidate["selected"][role]["claimed_period"]
        != expected_claimed_period
        for role in candidate["selected"]
    ):
        raise WorkflowError("Reviewed Candidate period differs from Run")
    created_observations = []
    created_results = []
    created_traces = []
    if decision["decision"] == "REJECT":
        for role in published_roles:
            result, trace = withheld_metric_result(
                compiled_spec=role_metric_specs[role],
                target=target,
                reason_code="HUMAN_REVIEW_REJECTED",
            )
            append_run_record(run_dir=run_dir, record=trace)
            append_run_record(run_dir=run_dir, record=result)
            created_results.append(result["result_id"])
            created_traces.append(trace["trace_id"])
        return {
            "decision_id": decision["review_decision_id"],
            "observation_ids": [],
            "result_ids": created_results,
            "trace_ids": created_traces,
        }
    unit_mismatches = []
    for role in published_roles:
        expected_unit = role_metric_specs[role]["compiled"]["reported_unit"]
        if (
            candidate["selected"][role]["claimed_reported_unit"]
            != expected_unit
        ):
            unit_mismatches.append(role)
    for role in supporting_roles:
        expected_unit = projection["supporting_role_units"][role]
        if (
            candidate["selected"][role]["claimed_reported_unit"]
            != expected_unit
        ):
            unit_mismatches.append(role)
    if unit_mismatches:
        for role in published_roles:
            result, trace = withheld_metric_result(
                compiled_spec=role_metric_specs[role],
                target=target,
                reason_code="REPORTED_UNIT_MISMATCH",
            )
            append_run_record(run_dir=run_dir, record=trace)
            append_run_record(run_dir=run_dir, record=result)
            created_results.append(result["result_id"])
            created_traces.append(trace["trace_id"])
        return {
            "decision_id": decision["review_decision_id"],
            "observation_ids": [],
            "result_ids": created_results,
            "trace_ids": created_traces,
        }
    source_bindings = unit["source_bindings"]
    if len(source_bindings) != 1:
        raise WorkflowError("Phase 1 reviewed observation requires one source")
    source_reference = source_bindings[0]
    derived_ids = candidate["derived_asset_ids"]
    if len(derived_ids) != 1:
        raise WorkflowError("Phase 1 reviewed observation requires one grid")
    for role in candidate["selected"]:
        if role in published_roles:
            metric_spec = role_metric_specs[role]
            metric_id = str(metric_spec["compiled"]["metric_id"])
            canonical_unit = str(metric_spec["compiled"]["canonical_unit"])
        else:
            metric_spec = None
            metric_id = str(disclosure_spec["compiled"]["metric_id"])
            canonical_unit = str(projection["supporting_role_units"][role])
        observation = reviewed_observation(
            metric_id=metric_id,
            role=role,
            company_id=str(manifest["company_id"]),
            period_start=str(manifest["target_period"]["period_start"]),
            period_end=str(manifest["target_period"]["period_end"]),
            canonical_unit=canonical_unit,
            candidate=candidate,
            evidence_check=evidence_matches[0],
            review_unit=unit,
            decision=decision,
            source_reference=source_reference,
            derived_asset_id=str(derived_ids[0]),
            quality="EXACT",
        )
        append_run_record(run_dir=run_dir, record=observation)
        created_observations.append(observation["observation_id"])
        if metric_spec is None:
            continue
        result, trace = calculate_observation_metric(
            compiled_spec=metric_spec,
            target=target,
            company_traits=list(manifest["company_traits"]),
            observation=observation,
        )
        append_run_record(run_dir=run_dir, record=trace)
        append_run_record(run_dir=run_dir, record=result)
        created_results.append(result["result_id"])
        created_traces.append(trace["trace_id"])
    return {
        "decision_id": decision["review_decision_id"],
        "observation_ids": created_observations,
        "result_ids": created_results,
        "trace_ids": created_traces,
    }
