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
from .ai_adapter import validate_adapter_repository_authority
from .batch_workflow import BatchWorkflowError
from .batch_workflow import validate_request_attempt_binding
from .calculator import calculate_metric, calculate_observation_metric
from .calculator import withheld_metric_result
from .canonical import sha256_file, strict_json_file, strict_json_loads
from .evidence import check_evidence
from .reader import validate_reader_output
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .reader_input import prepare_live_reader_request
from .reader_input import required_reader_roles
from .render import build_review_context, render_review_markdown
from .review import build_review_unit, effective_review_decision
from .observations import reviewed_observation, scope_key
from .requirements import load_requirement_snapshot
from .run_store import append_run_record, append_run_records_atomically
from .run_store import create_run, load_open_run
from .run_store import load_run_bound_specs
from .run_store import RunStoreError
from .run_store import write_review_assets
from .run_store import write_attempt_payloads
from .sources import load_raw_blob_bytes, raw_blob_record
from .sources import SourceError, source_reference_record
from .sources import validate_public_sec_filing_identity
from .specs import SpecError, compile_spec_file, compile_spec_files
from .specs import parse_spec_document
from .table_grid import build_table_grid
from .traits import TraitError, repository_company_ciks
from .traits import repository_company_traits


class WorkflowError(RuntimeError):
    """Report incomplete compiled semantics or inconsistent Reader output."""


class LiveSourceAuthorityError(WorkflowError):
    """Report a live source not proven by immutable public SEC authority."""


def _validate_live_source_authority(
    *,
    repo_root: Path,
    company_id: str,
    raw_blob: Mapping[str, object],
    source_url: str,
    accession: str,
    document_name: str,
    source_role: str,
    request_attempt_id: str,
) -> Dict[str, object]:
    """Rebuild the registry, filing, ledger, body, and header proof pre-egress.

    Args:
        repo_root: Fixed repository containing registry and SEC audit authority.
        company_id: Registry logical company identity.
        raw_blob: Exact candidate filing bytes and media type.
        source_url: Claimed official SEC primary-document URL.
        accession: Claimed filing accession.
        document_name: Claimed filing document identity.
        source_role: Claimed Run source role.
        request_attempt_id: Pinned immutable request-ledger row identity.

    Returns:
        Exact immutable body/header locator proof for transport replay.

    Raises:
        LiveSourceAuthorityError: Before any AI attempt when the complete public
        SEC source proof cannot be rebuilt from current repository bytes.
    """
    try:
        validate_public_sec_filing_identity(
            raw_blob=raw_blob,
            source_url=source_url,
            accession=accession,
            document_name=document_name,
            source_role=source_role,
            allowed_ciks=repository_company_ciks(
                repo_root=repo_root, company_id=company_id,
            ),
        )
        binding = validate_request_attempt_binding(
            repo_root=repo_root,
            source_url=source_url,
            content_sha256=str(raw_blob["raw_asset_id"]).split(
                ":", maxsplit=1
            )[1],
            accession=accession,
            document_name=document_name,
            request_attempt_id=request_attempt_id,
            require_immutable=True,
        )
    except (BatchWorkflowError, SourceError, TraitError) as error:
        raise LiveSourceAuthorityError(
            "Live Reader source lacks immutable public SEC authority"
        ) from error
    if binding["request_attempt_id"] != request_attempt_id:
        raise LiveSourceAuthorityError(
            "Live Reader request attempt identity differs"
        )
    return binding


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
    """Create one registry-authorized OPEN Run through HUMAN review.

    Args:
        repo_root: Repository containing exact raw bytes and Specs.
        run_dir: New run-scoped directory.
        run_id: Opaque Run identity.
        company_id: Logical company identity from the production registry.
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
        Run, attempt, Candidate, Evidence, and ReviewUnit identities.
    """
    try:
        company_traits = repository_company_traits(
            repo_root=repo_root, company_id=company_id,
        )
    except TraitError as error:
        raise WorkflowError(
            "Repository company traits are invalid"
        ) from error
    return _create_review_run_with_traits(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=run_id,
        company_id=company_id,
        company_traits=company_traits,
        target_period=target_period,
        source_repo_relative_path=source_repo_relative_path,
        source_media_type=source_media_type,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id=request_attempt_id,
        disclosure_spec_path=disclosure_spec_path,
        adapter=adapter,
        clock=clock,
    )


def create_layout_qualification_run(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    fixture_id: str,
    adapter: AIAdapter,
    clock: Optional[Callable[[], datetime]],
) -> Dict[str, object]:
    """Run a repository fixture company through the production review path.

    Args:
        repo_root: Repository containing the fixed fixture authority.
        run_dir: New qualification Run directory.
        run_id: Opaque Run identity.
        fixture_id: Safe directory identity below ``fixtures/vnext/layouts``.
        adapter: Repository-created recorded adapter; live transport is barred.
        clock: Explicit UTC clock or ``None`` for real UTC audit time.

    Returns:
        The same Run/Candidate/Evidence/ReviewUnit result as production.
    """
    if (
        not fixture_id
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
               for character in fixture_id)
        or adapter.provider != "recorded"
    ):
        raise WorkflowError(
            "Layout qualification requires a safe fixture and "
            "socket-zero adapter"
        )
    relative_root = Path("fixtures/vnext/layouts") / fixture_id
    manifest_path = repo_root / relative_root / "fixture_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise WorkflowError("Layout fixture manifest is absent or unsafe")
    manifest = strict_json_file(path=manifest_path)
    required = {
        "accession",
        "cik",
        "company_id",
        "company_traits",
        "disclosure_spec_path",
        "document_name",
        "excerpt_repo_relative_path",
        "excerpt_sha256",
        "fixture_id",
        "layout_differences",
        "qualification_role",
        "recorded_response_repo_relative_path",
        "recorded_response_sha256",
        "request_attempt_id",
        "schema_version",
        "selection_reason",
        "source_media_type",
        "source_repo_relative_path",
        "source_role",
        "source_sha256",
        "source_url",
        "target_period",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or manifest["schema_version"] != 1
        or manifest["fixture_id"] != fixture_id
        or type(manifest["selection_reason"]) is not str
        or not manifest["selection_reason"].strip()
        or not isinstance(manifest["company_traits"], list)
        or not manifest["company_traits"]
        or len(manifest["company_traits"])
        != len(set(manifest["company_traits"]))
        or any(
            type(trait) is not str or not trait
            for trait in manifest["company_traits"]
        )
    ):
        raise WorkflowError("Layout fixture manifest fields are not exact")
    source_path = repo_root / Path(str(manifest["source_repo_relative_path"]))
    response_path = repo_root / Path(
        str(manifest["recorded_response_repo_relative_path"])
    )
    excerpt_path = repo_root / Path(
        str(manifest["excerpt_repo_relative_path"])
    )
    fixture_root = repo_root / relative_root
    if (
        Path(str(manifest["source_repo_relative_path"])).is_absolute()
        or ".." in Path(str(manifest["source_repo_relative_path"])).parts
        or fixture_root not in source_path.parents
        or source_path.is_symlink()
        or not source_path.is_file()
        or sha256_file(path=source_path) != manifest["source_sha256"]
        or Path(
            str(manifest["recorded_response_repo_relative_path"])
        ).is_absolute()
        or ".." in Path(
            str(manifest["recorded_response_repo_relative_path"])
        ).parts
        or fixture_root not in response_path.parents
        or response_path.is_symlink()
        or not response_path.is_file()
        or sha256_file(path=response_path)
        != manifest["recorded_response_sha256"]
        or Path(str(manifest["excerpt_repo_relative_path"])).is_absolute()
        or ".." in Path(str(manifest["excerpt_repo_relative_path"])).parts
        or fixture_root not in excerpt_path.parents
        or excerpt_path.is_symlink()
        or not excerpt_path.is_file()
        or sha256_file(path=excerpt_path) != manifest["excerpt_sha256"]
    ):
        raise WorkflowError("Layout fixture byte binding differs")
    return _create_review_run_with_traits(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=run_id,
        company_id=str(manifest["company_id"]),
        company_traits=list(manifest["company_traits"]),
        target_period=manifest["target_period"],
        source_repo_relative_path=str(manifest["source_repo_relative_path"]),
        source_media_type=str(manifest["source_media_type"]),
        source_url=str(manifest["source_url"]),
        accession=str(manifest["accession"]),
        document_name=str(manifest["document_name"]),
        source_role=str(manifest["source_role"]),
        request_attempt_id=str(manifest["request_attempt_id"]),
        disclosure_spec_path=str(manifest["disclosure_spec_path"]),
        adapter=adapter,
        clock=clock,
    )


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
) -> tuple[
    Dict[str, object], Sequence[str], Dict[str, Dict[str, object]]
]:
    """Load one disclosure Spec and derive its exact metric Spec paths.

    Args:
        repo_root: Repository containing the authoritative catalog.
        disclosure_spec_path: Repository-relative disclosure Spec locator.

    Returns:
        Compiled disclosure wrapper, ordered closure paths, and authoritative
        metric wrappers keyed by metric ID.

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
    try:
        metric_specs = compile_spec_files(
            paths=[metric_paths[metric_id] for metric_id in metric_paths],
        )
    except SpecError as error:
        raise WorkflowError(
            "Disclosure metric Spec closure cannot be compiled"
        ) from error
    if set(metric_specs) != required_metric_ids:
        raise WorkflowError("Disclosure metric Spec exact set differs")
    return (
        compiled_spec,
        [path.relative_to(repo_root).as_posix() for path in paths],
        metric_specs,
    )


def _create_review_run_with_traits(
    *,
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    company_id: str,
    company_traits: Sequence[str],
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
    """Create one OPEN Run from already repository-resolved company traits.

    Args:
        repo_root: Repository containing exact raw bytes and Specs.
        run_dir: New run-scoped directory.
        run_id: Opaque Run identity.
        company_id: Logical company identity.
        company_traits: Registry- or fixture-manifest-derived traits.
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
    # Close the only joint remote boundary before loading Spec or filing
    # bytes, so D-01 cannot authorize a payload assembled from another tree.
    adapter_mode = validate_adapter_repository_authority(
        adapter=adapter, repo_root=repo_root,
    )
    compiled_spec, spec_paths, metric_specs = _load_disclosure_plan(
        repo_root=repo_root,
        disclosure_spec_path=disclosure_spec_path,
    )
    if (
        not isinstance(company_traits, list)
        or not company_traits
        or any(type(trait) is not str or not trait for trait in company_traits)
        or len(company_traits) != len(set(company_traits))
    ):
        raise WorkflowError("Resolved company traits are invalid")
    semantic = compiled_spec["compiled"]
    required_traits = set(semantic["applicability"]["all"])
    forbidden_traits = set(semantic["applicability"]["none"])
    supplied_traits = set(company_traits)
    spec_file_hashes = {
        relative: sha256_file(path=repo_root / relative)
        for relative in spec_paths
    }
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1",
    )
    if not required_traits.issubset(supplied_traits) or (
        forbidden_traits & supplied_traits
    ):
        # Structural inapplicability is a durable business fact. Persist the
        # Run and Calculator output while deliberately omitting source and AI
        # records so freeze/replay can prove both the result and zero egress.
        records = []
        result_ids = []
        trace_ids = []
        for metric_id in sorted(metric_specs):
            metric_spec = metric_specs[metric_id]
            target_scope = dict(metric_spec["compiled"]["required_claims"])
            target = {
                "company_id": company_id,
                "period_start": target_period["period_start"],
                "period_end": target_period["period_end"],
                "accession": None,
                "entity": None,
                "scope": target_scope,
                "scope_key": scope_key(scope=target_scope),
            }
            result, trace, observations = calculate_metric(
                compiled_spec=metric_spec,
                target=target,
                company_traits=company_traits,
                structured_facts=[],
                verified_observations=[],
            )
            if observations or result["applicability"] != "N_A_STRUCTURAL":
                raise WorkflowError(
                    "Inapplicable disclosure metric did not produce N/A"
                )
            records.extend((trace, result))
            result_ids.append(result["result_id"])
            trace_ids.append(trace["trace_id"])
        create_run(
            run_dir=run_dir,
            run_id=run_id,
            company_id=company_id,
            company_traits=company_traits,
            target_period=target_period,
            source_references=[],
            missing_required_source_roles=[],
            spec_file_hashes=spec_file_hashes,
            requirement_hashes=requirement["hashes"],
        )
        for record in records:
            append_run_record(run_dir=run_dir, record=record)
        return {
            "run_id": run_id,
            "status": "N_A_STRUCTURAL",
            "attempt_count": 0,
            "result_ids": result_ids,
            "trace_ids": trace_ids,
        }
    roles = _required_roles(compiled_spec=compiled_spec)
    raw_blob = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=source_repo_relative_path,
        media_type=source_media_type,
    )
    live_source_binding = None
    if adapter_mode == "LIVE":
        live_source_binding = _validate_live_source_authority(
            repo_root=repo_root,
            company_id=company_id,
            raw_blob=raw_blob,
            source_url=source_url,
            accession=accession,
            document_name=document_name,
            source_role=source_role,
            request_attempt_id=request_attempt_id,
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
    attempt_request = (
        prepare_live_reader_request(
            prepared_request=prepared_request,
            raw_blob=raw_blob,
            source_reference=source_reference,
            derived_asset=derived_asset,
            reader_manifest=reader_manifest,
            disclosure_spec_path=disclosure_spec_path,
            immutable_source_repo_relative_path=str(
                live_source_binding["request_repo_relative_path"]
            ),
        )
        if adapter_mode == "LIVE"
        else prepared_request
    )

    response, _raw_response, attempt, attempt_payloads = run_ai_attempt(
        adapter=adapter,
        prepared_request=attempt_request,
        clock=clock,
    )
    write_attempt_payloads(
        run_dir=run_dir,
        attempt=attempt,
        payloads=attempt_payloads,
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
    records_file_hash = sha256_file(path=run_dir / "records.jsonl")
    decisions_file_hash = sha256_file(
        path=run_dir / "review_decisions.jsonl"
    )
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
    finalization_records = []
    if decision["decision"] == "REJECT":
        for role in published_roles:
            result, trace = withheld_metric_result(
                compiled_spec=role_metric_specs[role],
                target=target,
                reason_code="HUMAN_REVIEW_REJECTED",
            )
            finalization_records.extend([trace, result])
            created_results.append(result["result_id"])
            created_traces.append(trace["trace_id"])
        append_run_records_atomically(
            run_dir=run_dir,
            records=finalization_records,
            expected_records_file_hash=records_file_hash,
            expected_review_decisions_file_hash=decisions_file_hash,
        )
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
            finalization_records.extend([trace, result])
            created_results.append(result["result_id"])
            created_traces.append(trace["trace_id"])
        append_run_records_atomically(
            run_dir=run_dir,
            records=finalization_records,
            expected_records_file_hash=records_file_hash,
            expected_review_decisions_file_hash=decisions_file_hash,
        )
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
        finalization_records.append(observation)
        created_observations.append(observation["observation_id"])
        if metric_spec is None:
            continue
        result, trace = calculate_observation_metric(
            compiled_spec=metric_spec,
            target=target,
            company_traits=list(manifest["company_traits"]),
            observation=observation,
        )
        finalization_records.extend([trace, result])
        created_results.append(result["result_id"])
        created_traces.append(trace["trace_id"])
    append_run_records_atomically(
        run_dir=run_dir,
        records=finalization_records,
        expected_records_file_hash=records_file_hash,
        expected_review_decisions_file_hash=decisions_file_hash,
    )
    return {
        "decision_id": decision["review_decision_id"],
        "observation_ids": created_observations,
        "result_ids": created_results,
        "trace_ids": created_traces,
    }
