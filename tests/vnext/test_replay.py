"""Run freeze TOCTOU, immutability, and offline replay tests."""

from __future__ import annotations

import copy
import csv
import json
import socket
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence
from unittest import mock

from tests.vnext.common import REPO_ROOT, compiled_specs, fixed_clock
from tests.vnext.common import reader_response
from tests.vnext.projection_fixture_support import scoped_repository
from tools.vnext_review import append_human_decision
from vnext.ai_adapter import RecordedAdapter
from vnext.calculator import calculate_metric, calculate_observation_metric
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.canonical import sha256_file
from vnext.observations import reviewed_observation, structured_observation
from vnext.projector import ProjectionError
from vnext.projector import _project_result, _record_indexes
from vnext.projector import load_projection_batch_manifest
from vnext.projector import write_projection_batch_manifest
from vnext.records import metric_result_contract_hash
from vnext.render import render_review_markdown
from vnext.requirements import load_requirement_snapshot
from vnext.replay import ReplayError, replay_frozen_results
from vnext.review import create_review_decision
from vnext.run_store import RunStoreError, append_review_decision
from vnext.run_store import append_run_record, create_run, freeze_run
from vnext.run_store import _structured_concepts
from vnext.run_store import load_frozen_run
from vnext.run_store import load_open_run
from vnext.run_store import write_attempt_payloads
from vnext.run_store import write_validation_receipt
from vnext.sources import companyfacts_structured_facts, raw_blob_record
from vnext.sources import source_reference_record
from vnext.specs import compile_spec_file
from vnext.table_grid import build_table_grid
from vnext.traits import repository_company_ciks, repository_company_traits
from vnext.workflow import create_review_run as create_workflow_review_run
from vnext.workflow import finalize_reviewed_direct_results
from vnext.workflow import WorkflowError


def create_review_run(
    *,
    run_dir: Path,
    reported_units: Optional[Mapping[str, str]] = None,
    recorded_response_bytes: Optional[bytes] = None,
    target_period: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    """Create one OPEN recorded shadow Run at the pending-review boundary.

    Args:
        run_dir: New run-scoped directory.
        reported_units: Optional exact Reader role-unit override.
        recorded_response_bytes: Optional exact Reader response override.
        target_period: Optional exact Run period override.

    Returns:
        Workflow result with ReviewUnit identity.
    """
    relative = "tests/fixtures/vnext/sample_lodging.html"
    raw = raw_blob_record(
        repo_root=REPO_ROOT,
        repo_relative_path=relative,
        media_type="text/html",
    )
    asset = build_table_grid(
        html_bytes=(REPO_ROOT / relative).read_bytes(),
        parent_raw_asset_ids=[str(raw["raw_asset_id"])],
        storage_uri="artifacts/vnext/derived/fixture.json",
    )
    return create_workflow_review_run(
        repo_root=REPO_ROOT,
        run_dir=run_dir,
        run_id="run:recorded:replay:001",
        company_id="marriott_international",
        target_period=(
            {
                "fiscal_year": 2025,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            }
            if target_period is None
            else dict(target_period)
        ),
        source_repo_relative_path=relative,
        source_media_type="text/html",
        source_url="https://www.sec.gov/Archives/sample.htm",
        accession="0001048286-25-000001",
        document_name="sample_lodging.html",
        source_role="target_primary",
        request_attempt_id="request:attempt:fixture",
        disclosure_spec_path=(
            "catalog/disclosures/lodging_kpi_table.md"
        ),
        adapter=RecordedAdapter(
            response_bytes=(
                reader_response(asset=asset, reported_units=reported_units)
                if recorded_response_bytes is None
                else recorded_response_bytes
            ),
            fixture_id="fixture:lodging:replay",
        ),
        clock=fixed_clock,
    )


def approve_review_run(*, run_dir: Path) -> None:
    """Append one exact HUMAN approval to a pending fixture Run.

    Args:
        run_dir: OPEN recorded Run.

    Expected output:
        The decision log contains one effective whole-unit approval.
    """
    _manifest, records, _decisions = load_open_run(run_dir=run_dir)
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    if len(units) != 1:
        raise AssertionError("Fixture must contain one ReviewUnit")
    required = compiled_specs()["DISCLOSURE"]["compiled"]["required_claims"]
    decision = create_review_decision(
        review_unit=units[0],
        decision="APPROVE",
        approved_claims=required,
        required_claims=required,
        reviewer_id="human:reviewer:fixture",
        decided_at_utc="2026-07-29T13:00:00Z",
        reason="Fixture scope and period reviewed.",
        supersedes_decision_id=None,
    )
    append_review_decision(run_dir=run_dir, decision=decision)


def approve_and_finalize(*, run_dir: Path) -> Mapping[str, object]:
    """Append an exact HUMAN approval and create B10/B11 results.

    Args:
        run_dir: OPEN recorded Run.

    Returns:
        Created result/trace identities.
    """
    approve_review_run(run_dir=run_dir)
    return finalize_reviewed_direct_results(
        run_dir=run_dir,
        repo_root=REPO_ROOT,
    )


def freeze_fixture(
    *, run_dir: Path, repo_root: Path = REPO_ROOT
) -> Dict[str, object]:
    """Validate and freeze a fully reviewed deterministic Run.

    Args:
        run_dir: OPEN finalized Run.
        repo_root: Repository authority used to create the Run.

    Returns:
        FROZEN Run manifest.
    """
    write_validation_receipt(
        run_dir=run_dir,
        status="PASSED",
        checks=[{"check": "RECORDED_REPLAY_FIXTURE", "status": "PASS"}],
    )
    return freeze_run(run_dir=run_dir, repo_root=repo_root)


def _compiled_specs_at(*, repo_root: Path) -> Dict[str, Mapping[str, object]]:
    """Compile the release MetricSpecs from one fixture repository.

    Args:
        repo_root: Repository containing the copied or primary catalog.

    Returns:
        B01/B03/B10/B11 compiled wrappers keyed by metric ID.
    """
    b01 = compile_spec_file(
        path=repo_root / "catalog" / "metrics" / "B01_revenue.md",
        dependency_specs={},
    )
    return {
        "B01": b01,
        "B03": compile_spec_file(
            path=(
                repo_root / "catalog" / "metrics" / "B03_ebitda_margin.md"
            ),
            dependency_specs={"B01": b01},
        ),
        "B10": compile_spec_file(
            path=repo_root / "catalog" / "metrics" / "B10_occupancy.md",
            dependency_specs={},
        ),
        "B11": compile_spec_file(
            path=repo_root / "catalog" / "metrics" / "B11_revpar.md",
            dependency_specs={},
        ),
    }


def create_structured_b01_run(
    *,
    run_dir: Path,
    forged_value: Optional[str],
    run_id: str = "run:structured:forgery",
) -> Dict[str, object]:
    """Create a B01 Run from raw facts or one coherent forged value.

    Args:
        run_dir: New Run directory.
        forged_value: Caller-invented value, or ``None`` to use raw bytes.
        run_id: Stable fixture Run identity.

    Returns:
        Created MetricResult. The Run remains OPEN for freeze assertions.
    """
    relative = "evidence/companyfacts/CIK0001048286.json"
    raw = raw_blob_record(
        repo_root=REPO_ROOT,
        repo_relative_path=relative,
        media_type="application/json",
    )
    source = source_reference_record(
        raw_blob=raw,
        company_id="marriott_international",
        source_url=(
            "https://data.sec.gov/api/xbrl/companyfacts/"
            "CIK0001048286.json"
        ),
        accession="0001628280-25-004818",
        document_name="CIK0001048286.json",
        source_role="companyfacts",
        request_attempt_id="request:attempt:existing-ledger",
    )
    scope = {"consolidation": "entity"}
    target = {
        "company_id": "marriott_international",
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "accession": source["accession"],
        "entity": "1048286",
        "scope": scope,
        "scope_key": content_hash(value=scope),
    }
    spec = compiled_specs()["B01"]
    approved = spec["compiled"]["inputs"]["revenue"][
        "structured_role"
    ]["approved_concepts"]
    facts = companyfacts_structured_facts(
        raw_bytes=(REPO_ROOT / relative).read_bytes(),
        source_reference=source,
        approved_concepts=approved,
        allowed_ciks=repository_company_ciks(
            repo_root=REPO_ROOT,
            company_id="marriott_international",
        ),
    )
    if forged_value is not None:
        facts = [
            {
                "accession": source["accession"],
                "concept": "us-gaap:Revenues",
                "duration_days": 366,
                "entity": "1048286",
                "fact_id": "fact:forged-but-self-consistent",
                "filed": "2025-02-11",
                "fiscal_period": "FY",
                "form": "10-K",
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
                "source_binding": {
                    "raw_asset_id": raw["raw_asset_id"],
                    "source_reference_id": source["source_reference_id"],
                    "accession": source["accession"],
                    "document_name": source["document_name"],
                    "source_role": source["source_role"],
                    "entity": "1048286",
                },
                "unit": "USD",
                "value": forged_value,
            }
        ]
    result, trace, observations = calculate_metric(
        compiled_spec=spec,
        target=target,
        company_traits=repository_company_traits(
            repo_root=REPO_ROOT,
            company_id="marriott_international",
        ),
        structured_facts=facts,
        verified_observations=[],
    )
    requirement = load_requirement_snapshot(
        snapshot_dir=REPO_ROOT / "requirements" / "ai_first_v3_3_1"
    )
    spec_path = REPO_ROOT / "catalog" / "metrics" / "B01_revenue.md"
    create_run(
        run_dir=run_dir,
        run_id=run_id,
        company_id="marriott_international",
        company_traits=repository_company_traits(
            repo_root=REPO_ROOT,
            company_id="marriott_international",
        ),
        target_period={
            "fiscal_year": 2024,
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
        },
        source_references=[source],
        missing_required_source_roles=[],
        spec_file_hashes={
            "catalog/metrics/B01_revenue.md": sha256_file(path=spec_path)
        },
        requirement_hashes=requirement["hashes"],
    )
    for record in [raw, source, *observations, trace, result]:
        append_run_record(run_dir=run_dir, record=record)
    return dict(result)


def create_structured_b03_dependency_run(*, run_dir: Path) -> None:
    """Create B03 from real facts but a forged reusable B01 observation.

    Args:
        run_dir: New Run directory left OPEN for a freeze assertion.

    Expected output:
        B03's own components come from Marriott Company Facts, while its B01
        dependency claims ``999`` and no standalone B01 Result/Trace exists.
    """
    relative = "evidence/companyfacts/CIK0001048286.json"
    company_id = "marriott_international"
    raw = raw_blob_record(
        repo_root=REPO_ROOT,
        repo_relative_path=relative,
        media_type="application/json",
    )
    source = source_reference_record(
        raw_blob=raw,
        company_id=company_id,
        source_url=(
            "https://data.sec.gov/api/xbrl/companyfacts/"
            "CIK0001048286.json"
        ),
        accession="0001628280-25-004818",
        document_name="CIK0001048286.json",
        source_role="companyfacts",
        request_attempt_id="request:attempt:existing-ledger",
    )
    specs = compiled_specs()
    traits = repository_company_traits(
        repo_root=REPO_ROOT, company_id=company_id,
    )
    allowed_ciks = repository_company_ciks(
        repo_root=REPO_ROOT, company_id=company_id,
    )
    raw_bytes = (REPO_ROOT / relative).read_bytes()
    scope = {"consolidation": "entity"}
    target = {
        "company_id": company_id,
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "accession": source["accession"],
        "entity": "1048286",
        "scope": scope,
        "scope_key": content_hash(value=scope),
    }
    b01_facts = companyfacts_structured_facts(
        raw_bytes=raw_bytes,
        source_reference=source,
        approved_concepts=_structured_concepts(
            compiled_spec=specs["B01"],
        ),
        allowed_ciks=allowed_ciks,
    )
    _result, _trace, b01_observations = calculate_metric(
        compiled_spec=specs["B01"],
        target=target,
        company_traits=traits,
        structured_facts=b01_facts,
        verified_observations=[],
    )
    actual_revenue = b01_observations[0]
    forged_revenue = structured_observation(
        metric_id="B01",
        semantic_role="revenue",
        company_id=company_id,
        period_start="2024-01-01",
        period_end="2024-12-31",
        scope=scope,
        value="999",
        unit=str(actual_revenue["unit"]),
        quality="EXACT",
        source_binding=actual_revenue["source_binding"],
    )
    b03_facts = companyfacts_structured_facts(
        raw_bytes=raw_bytes,
        source_reference=source,
        approved_concepts=_structured_concepts(
            compiled_spec=specs["B03"],
        ),
        allowed_ciks=allowed_ciks,
    )
    result, trace, observations = calculate_metric(
        compiled_spec=specs["B03"],
        target=target,
        company_traits=traits,
        structured_facts=b03_facts,
        verified_observations=[forged_revenue],
    )
    requirement = load_requirement_snapshot(
        snapshot_dir=REPO_ROOT / "requirements" / "ai_first_v3_3_1"
    )
    spec_paths = {
        "catalog/metrics/B01_revenue.md": (
            REPO_ROOT / "catalog" / "metrics" / "B01_revenue.md"
        ),
        "catalog/metrics/B03_ebitda_margin.md": (
            REPO_ROOT / "catalog" / "metrics" / "B03_ebitda_margin.md"
        ),
    }
    create_run(
        run_dir=run_dir,
        run_id="run:structured:forged-dependency",
        company_id=company_id,
        company_traits=traits,
        target_period={
            "fiscal_year": 2024,
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
        },
        source_references=[source],
        missing_required_source_roles=[],
        spec_file_hashes={
            relative_path: sha256_file(path=path)
            for relative_path, path in spec_paths.items()
        },
        requirement_hashes=requirement["hashes"],
    )
    for record in [raw, source, *observations, trace, result]:
        append_run_record(run_dir=run_dir, record=record)


def create_structured_b03_run(
    *,
    run_dir: Path,
    repo_relative_path: str,
    accession: str,
    run_id: str,
    repo_root: Path = REPO_ROOT,
) -> Dict[str, object]:
    """Create one replayable Pfizer B03 Run from exact Company Facts bytes.

    Args:
        run_dir: New Run directory.
        repo_relative_path: Existing real or boundary-fixture raw JSON path.
        accession: Exact filing observation selected from those bytes.
        run_id: Unique Run identity for the scenario.
        repo_root: Repository authority containing the source and Specs.

    Returns:
        Result, Trace, and selected observations left in an OPEN Run.
    """
    company_id = "pfizer"
    entity = "78003"
    document_name = "CIK0000078003.json"
    raw = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=repo_relative_path,
        media_type="application/json",
    )
    source = source_reference_record(
        raw_blob=raw,
        company_id=company_id,
        source_url=(
            "https://data.sec.gov/api/xbrl/companyfacts/" + document_name
        ),
        accession=accession,
        document_name=document_name,
        source_role="companyfacts",
        request_attempt_id="request:attempt:" + accession,
    )
    specs = _compiled_specs_at(repo_root=repo_root)
    traits = repository_company_traits(
        repo_root=repo_root, company_id=company_id,
    )
    allowed_ciks = repository_company_ciks(
        repo_root=repo_root, company_id=company_id,
    )
    raw_bytes = (repo_root / repo_relative_path).read_bytes()
    scope = {"consolidation": "entity"}
    target = {
        "company_id": company_id,
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "accession": accession,
        "entity": entity,
        "scope": scope,
        "scope_key": content_hash(value=scope),
    }

    # B03 owns a cross-Spec B01 dependency, so materialize the exact B01
    # observation from the same raw bytes before executing the consumer.
    b01_facts = companyfacts_structured_facts(
        raw_bytes=raw_bytes,
        source_reference=source,
        approved_concepts=_structured_concepts(
            compiled_spec=specs["B01"],
        ),
        allowed_ciks=allowed_ciks,
    )
    _b01_result, _b01_trace, b01_observations = calculate_metric(
        compiled_spec=specs["B01"],
        target=target,
        company_traits=traits,
        structured_facts=b01_facts,
        verified_observations=[],
    )
    b03_facts = companyfacts_structured_facts(
        raw_bytes=raw_bytes,
        source_reference=source,
        approved_concepts=_structured_concepts(
            compiled_spec=specs["B03"],
        ),
        allowed_ciks=allowed_ciks,
    )
    result, trace, observations = calculate_metric(
        compiled_spec=specs["B03"],
        target=target,
        company_traits=traits,
        structured_facts=b03_facts,
        verified_observations=b01_observations,
    )
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1"
    )
    spec_paths = {
        "catalog/metrics/B01_revenue.md": (
            repo_root / "catalog" / "metrics" / "B01_revenue.md"
        ),
        "catalog/metrics/B03_ebitda_margin.md": (
            repo_root / "catalog" / "metrics" / "B03_ebitda_margin.md"
        ),
    }
    create_run(
        run_dir=run_dir,
        run_id=run_id,
        company_id=company_id,
        company_traits=traits,
        target_period={
            "fiscal_year": 2025,
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
        },
        source_references=[source],
        missing_required_source_roles=[],
        spec_file_hashes={
            relative_path: sha256_file(path=path)
            for relative_path, path in spec_paths.items()
        },
        requirement_hashes=requirement["hashes"],
    )
    for record in [raw, source, *observations, trace, result]:
        append_run_record(run_dir=run_dir, record=record)
    return {
        "result": result,
        "trace": trace,
        "observations": observations,
    }


def create_full_release_run(
    *, run_dir: Path, run_id: str, repo_root: Path = REPO_ROOT,
) -> Dict[str, object]:
    """Create one replayable Run containing the exact Phase 1 metric set.

    Args:
        run_dir: New Run directory.
        run_id: Unique Run identity for the scenario.
        repo_root: Repository authority containing source and release Specs.

    Returns:
        B01/B03/B10/B11 results left in one OPEN Run.
    """
    relative = (
        "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
        "CIK0000078003.json"
    )
    accession = "0000078003-26-100099"
    b03 = create_structured_b03_run(
        run_dir=run_dir,
        repo_relative_path=relative,
        accession=accession,
        run_id=run_id,
        repo_root=repo_root,
    )
    manifest, records, _decisions = load_open_run(run_dir=run_dir)
    source = next(
        record
        for record in records
        if record["record_type"] == "SOURCE_REFERENCE"
    )
    specs = _compiled_specs_at(repo_root=repo_root)
    traits = repository_company_traits(
        repo_root=repo_root, company_id="pfizer",
    )
    target = b03["trace"]["calculation_target"]
    b01_facts = companyfacts_structured_facts(
        raw_bytes=(repo_root / relative).read_bytes(),
        source_reference=source,
        approved_concepts=_structured_concepts(
            compiled_spec=specs["B01"],
        ),
        allowed_ciks=repository_company_ciks(
            repo_root=repo_root, company_id="pfizer",
        ),
    )
    b01_result, b01_trace, b01_observations = calculate_metric(
        compiled_spec=specs["B01"],
        target=target,
        company_traits=traits,
        structured_facts=b01_facts,
        verified_observations=[],
    )
    existing_observation_ids = {
        observation["observation_id"] for observation in b03["observations"]
    }
    if {
        observation["observation_id"] for observation in b01_observations
    } - existing_observation_ids:
        raise AssertionError("B03 fixture did not retain its B01 dependency")
    append_run_record(run_dir=run_dir, record=b01_trace)
    append_run_record(run_dir=run_dir, record=b01_result)
    results = {"B01": b01_result, "B03": b03["result"]}
    for metric_id in ("B10", "B11"):
        result, trace, observations = calculate_metric(
            compiled_spec=specs[metric_id],
            target=target,
            company_traits=traits,
            structured_facts=[],
            verified_observations=[],
        )
        if observations:
            raise AssertionError("Structural fixture created observations")
        append_run_record(run_dir=run_dir, record=trace)
        append_run_record(run_dir=run_dir, record=result)
        results[metric_id] = result

    # The full Run binds every release Spec even when non-lodging traits make
    # B10/B11 structurally inapplicable rather than AI-backed.
    manifest_path = run_dir / "manifest.json"
    for metric_id, filename in (
        ("B10", "B10_occupancy.md"),
        ("B11", "B11_revpar.md"),
    ):
        relative_path = "catalog/metrics/" + filename
        manifest["spec_file_hashes"][relative_path] = sha256_file(
            path=repo_root / relative_path,
        )
    manifest_path.write_bytes(canonical_json_bytes(value=manifest) + b"\n")
    return results


def rewrite_result_trace(
    *,
    run_dir: Path,
    records: Sequence[Mapping[str, object]],
    original_trace: Mapping[str, object],
    changed_trace: Dict[str, object],
    original_result: Mapping[str, object],
    changed_result: Dict[str, object],
) -> None:
    """Persist a newly content-addressed Result/Trace tamper pair.

    Args:
        run_dir: OPEN fixture Run.
        records: Complete original record sequence.
        original_trace: Trace being replaced.
        changed_trace: Mutated Trace without its updated identity.
        original_result: Result being replaced.
        changed_result: Mutated Result without its updated identity.

    Expected output:
        The fixture remains structurally content-addressed, so the freeze gate
        must detect the semantic inconsistency rather than a stale ID.
    """
    trace_fields = (
        "metric_id",
        "calculation_target",
        "input_observation_ids",
        "steps",
        "quality",
        "result",
        "spec_closure_hash",
        "execution_semantics_hash",
        "result_contract_hash",
    )
    changed_trace["result_contract_hash"] = metric_result_contract_hash(
        result=changed_result,
    )
    changed_trace["trace_id"] = content_hash(
        value={key: changed_trace[key] for key in trace_fields}
    )
    changed_result["trace_id"] = changed_trace["trace_id"]
    result_fields = (
        "company_id",
        "metric_id",
        "period_start",
        "period_end",
        "scope_key",
        "spec_closure_hash",
        "applicability",
        "quality",
        "publication",
        "reason_code",
        "value",
        "unit",
        "trace_id",
    )
    changed_result["result_id"] = content_hash(
        value={key: changed_result[key] for key in result_fields}
    )
    rewritten = [
        changed_trace
        if record is original_trace
        else changed_result
        if record is original_result
        else record
        for record in records
    ]
    records_text = "\n".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True)
        for record in rewritten
    ) + "\n"
    (run_dir / "records.jsonl").write_text(
        records_text, encoding="utf-8",
    )


def rewrite_records(
    *, run_dir: Path, records: Sequence[Mapping[str, object]]
) -> None:
    """Persist a complete caller-mutated OPEN Run record sequence.

    Args:
        run_dir: OPEN fixture Run.
        records: Ordered records whose own content identities remain valid.

    Expected output:
        Freeze must independently detect the cross-object mutation.
    """
    records_text = "\n".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True)
        for record in records
    ) + "\n"
    (run_dir / "records.jsonl").write_text(
        records_text, encoding="utf-8",
    )


def rehash_review_decision(
    *, decision: Mapping[str, object], approved_claims: Mapping[str, object]
) -> Dict[str, object]:
    """Return a self-hash-consistent decision with replacement claims.

    Args:
        decision: Existing strict ReviewDecision.
        approved_claims: Replacement business claims used to model disk or
            low-level API tampering.

    Returns:
        ReviewDecision whose own two hashes are correct, leaving semantic
        validation as the only expected rejection boundary.
    """
    changed = copy.deepcopy(decision)
    changed["approved_claims"] = dict(approved_claims)
    approval_fields = (
        "review_unit_hash",
        "decision",
        "approved_claims",
        "reviewed_spec_semantic_hash",
        "reviewed_source_bindings",
        "review_context_hash",
        "rendered_review_hash",
        "review_renderer_semantic_version",
    )
    approval = {key: changed[key] for key in approval_fields}
    changed["approval_effect_hash"] = content_hash(value=approval)
    audit = dict(approval)
    for key in (
        "reviewer_type",
        "reviewer_id",
        "decided_at_utc",
        "reason",
        "supersedes_decision_id",
    ):
        audit[key] = changed[key]
    changed["review_decision_id"] = content_hash(value=audit)
    return changed


class ReplayTest(unittest.TestCase):
    """Prove disk revalidation, immutable freeze, and AI-free replay."""

    def test_freeze_rejects_nonterminal_ai_attempt(self) -> None:
        """Keep STARTED attempt snapshots out of an immutable FROZEN Run."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            completed = next(
                record
                for record in records
                if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            )
            started = copy.deepcopy(completed)
            started["attempt_id"] = "attempt:started:freeze-fixture"
            started["status"] = "STARTED"
            append_run_record(run_dir=run_dir, record=started)
            write_validation_receipt(
                run_dir=run_dir,
                status="PASSED",
                checks=[{"check": "TERMINAL_ATTEMPT", "status": "PASS"}],
            )

            with self.assertRaisesRegex(RunStoreError, "terminal"):
                freeze_run(run_dir=run_dir, repo_root=REPO_ROOT)

    def test_review_cli_derives_claims_from_review_unit(self) -> None:
        """Keep review choices free of caller-repeated claim mappings."""
        for decision, expected_claims in (
            (
                "APPROVE",
                compiled_specs()["DISCLOSURE"]["compiled"][
                    "required_claims"
                ],
            ),
            ("REJECT", {}),
        ):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory(
            ) as directory:
                run_dir = Path(directory) / "run"
                created = create_review_run(run_dir=run_dir)
                appended = append_human_decision(
                    run_dir=run_dir,
                    review_unit_hash=str(created["review_unit_hash"]),
                    decision=decision,
                    reviewer_id="human:reviewer:fixture",
                    decided_at_utc="2026-07-29T13:00:00Z",
                    reason="Fixture whole-unit decision.",
                    supersedes_decision_id=None,
                )
                self.assertEqual(
                    expected_claims, appended["approved_claims"],
                )

    def test_freeze_replays_every_successful_ai_response(self) -> None:
        """Reject invalid response bytes even without a Candidate reference."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            completed = next(
                record
                for record in records
                if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            )
            request_bytes = (
                run_dir / str(completed["request_body_path"])
            ).read_bytes()
            task_contract_bytes = (
                run_dir / str(completed["task_contract_path"])
            ).read_bytes()
            invalid_response = b"not-json"
            forged = copy.deepcopy(completed)
            forged["attempt_id"] = "attempt:invalid-success:fixture"
            forged["raw_response_sha256"] = sha256_bytes(
                content=invalid_response,
            )
            forged["raw_response_path"] = (
                "attempt_payloads/response_{}.bin".format(
                    forged["raw_response_sha256"]
                )
            )
            write_attempt_payloads(
                run_dir=run_dir,
                attempt=forged,
                request_bytes=request_bytes,
                task_contract_bytes=task_contract_bytes,
                raw_response_bytes=invalid_response,
            )
            append_run_record(run_dir=run_dir, record=forged)
            write_validation_receipt(
                run_dir=run_dir,
                status="PASSED",
                checks=[{"check": "ALL_RESPONSES", "status": "PASS"}],
            )

            with self.assertRaisesRegex(RunStoreError, "response bytes"):
                freeze_run(run_dir=run_dir, repo_root=REPO_ROOT)

    def test_missing_source_role_cannot_freeze_published_result(self) -> None:
        """Allow missing-source audit only when no result claims PUBLISHED."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["missing_required_source_roles"] = ["target_primary"]
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
            write_validation_receipt(
                run_dir=run_dir,
                status="PASSED",
                checks=[{"check": "SOURCE_CLOSURE", "status": "PASS"}],
            )

            with self.assertRaisesRegex(RunStoreError, "missing source"):
                freeze_run(run_dir=run_dir, repo_root=REPO_ROOT)

    def test_projector_preserves_baseline_fields_absent_from_review_source(
        self,
    ) -> None:
        """Project real reviewed facts whose source has no form/filed keys."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            freeze_fixture(run_dir=run_dir)
            manifest, records, _decisions = load_frozen_run(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            indexes = _record_indexes(runs=[(manifest, records)])
            with (
                REPO_ROOT / "config" / "company_registry.csv"
            ).open(encoding="utf-8", newline="") as stream:
                company = next(
                    row
                    for row in csv.DictReader(stream)
                    if row["company_id"] == "marriott_international"
                )
            with (
                REPO_ROOT / "outputs" / "metrics_matrix.csv"
            ).open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                metric_fields = tuple(reader.fieldnames or ())
                baselines = {
                    row["metric_id"]: row
                    for row in reader
                    if row["company"] == "Marriott International"
                    and row["metric_id"] in {"B10", "B11"}
                }
            for metric_id, expected_value in (
                ("B10", "69.3"),
                ("B11", "128.8"),
            ):
                result = indexes["results"][
                    ("marriott_international", metric_id)
                ]
                trace = indexes["traces"][str(result["trace_id"])]
                source_binding = indexes["observations"][
                    str(trace["input_observation_ids"][0])
                ]["source_binding"]
                self.assertNotIn("form", source_binding)
                self.assertNotIn("filed", source_binding)

                row, evidence, contributor_count = _project_result(
                    result=result,
                    trace=trace,
                    company=company,
                    spec=compiled_specs()[metric_id],
                    baseline_row=baselines[metric_id],
                    indexes=indexes,
                    fiscal_year=str(
                        manifest["target_period"]["fiscal_year"]
                    ),
                    metric_fields=metric_fields,
                )

                self.assertEqual(expected_value, row["value"])
                self.assertEqual("", row["form"])
                self.assertEqual(
                    baselines[metric_id]["filed_date"],
                    row["filed_date"],
                )
                self.assertEqual(1, contributor_count)
                self.assertEqual(1, len(evidence))

    def test_projector_reloads_the_persisted_frozen_run(self) -> None:
        """Reject a self-consistent caller story when Run bytes disagree."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = scoped_repository(workspace=root)
            batch_root = root / "batch"
            batch_root.mkdir()
            run_dir = batch_root / "run"
            create_full_release_run(
                run_dir=run_dir, run_id="run:projection:verified",
            )
            freeze_fixture(run_dir=run_dir)
            batch_path = batch_root / "batch_manifest.json"
            batch = write_projection_batch_manifest(
                repo_root=repo_root,
                batch_manifest_path=batch_path,
                run_dirs=[run_dir],
            )
            self.assertEqual(
                "ai_first_v3_3_1_phase_1", batch["release_id"],
            )
            self.assertEqual(4, len(batch["expected_result_keys"]))
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["content_manifest_hash"] = "sha256:" + "f" * 64
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ProjectionError, "verified FROZEN|repository Runs"
            ):
                load_projection_batch_manifest(
                    repo_root=repo_root,
                    batch_manifest_path=batch_path,
                )

    def test_projector_rejects_duplicate_legacy_compatibility_key(
        self,
    ) -> None:
        """Do not project two scope grains into one legacy metric cell."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = scoped_repository(workspace=root)
            batch_root = root / "batch"
            batch_root.mkdir()
            run_dir = batch_root / "run"
            create_full_release_run(
                run_dir=run_dir, run_id="run:projection:duplicate",
            )
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            original_trace = next(
                record
                for record in records
                if record["record_type"] == "EXECUTION_TRACE"
                and record["metric_id"] == "B01"
            )
            source = next(
                record
                for record in records
                if record["record_type"] == "SOURCE_REFERENCE"
            )
            raw = next(
                record
                for record in records
                if record["record_type"] == "RAW_BLOB"
            )
            scope = {"consolidation": "alternate-scope"}
            target = dict(original_trace["calculation_target"])
            target["scope"] = scope
            target["scope_key"] = content_hash(value=scope)
            spec = compiled_specs()["B01"]
            facts = companyfacts_structured_facts(
                raw_bytes=(REPO_ROOT / str(raw["storage_uri"])).read_bytes(),
                source_reference=source,
                approved_concepts=_structured_concepts(
                    compiled_spec=spec,
                ),
                allowed_ciks=repository_company_ciks(
                    repo_root=REPO_ROOT,
                    company_id=str(source["company_id"]),
                ),
            )
            duplicate_result, duplicate_trace, duplicate_observations = (
                calculate_metric(
                    compiled_spec=spec,
                    target=target,
                    company_traits=repository_company_traits(
                        repo_root=REPO_ROOT,
                        company_id=str(source["company_id"]),
                    ),
                    structured_facts=facts,
                    verified_observations=[],
                )
            )
            for observation in duplicate_observations:
                append_run_record(run_dir=run_dir, record=observation)
            append_run_record(run_dir=run_dir, record=duplicate_trace)
            append_run_record(run_dir=run_dir, record=duplicate_result)
            freeze_fixture(run_dir=run_dir)

            with self.assertRaisesRegex(
                ProjectionError, "company metric coordinate is duplicated"
            ):
                write_projection_batch_manifest(
                    repo_root=repo_root,
                    batch_manifest_path=batch_root / "batch_manifest.json",
                    run_dirs=[run_dir],
                )

    def test_projector_requires_persisted_projection_inputs(self) -> None:
        """Reject missing Run bytes instead of trusting a batch manifest."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = scoped_repository(workspace=root)
            batch_root = root / "batch"
            batch_root.mkdir()
            run_dir = batch_root / "run"
            create_full_release_run(
                run_dir=run_dir, run_id="run:projection:missing-input",
            )
            freeze_fixture(run_dir=run_dir)
            batch_path = batch_root / "batch_manifest.json"
            write_projection_batch_manifest(
                repo_root=repo_root,
                batch_manifest_path=batch_path,
                run_dirs=[run_dir],
            )
            (run_dir / "records.jsonl").unlink()

            with self.assertRaisesRegex(ProjectionError, "verified FROZEN"):
                load_projection_batch_manifest(
                    repo_root=repo_root,
                    batch_manifest_path=batch_path,
                )

    def test_projector_rejects_intermediate_run_locator_symlink(self) -> None:
        """Keep a persisted batch Run below its original real namespace."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = scoped_repository(workspace=root)
            batch_root = root / "batch"
            run_parent = batch_root / "runs"
            run_parent.mkdir(parents=True)
            run_dir = run_parent / "run"
            create_full_release_run(
                run_dir=run_dir, run_id="run:projection:parent-symlink",
            )
            freeze_fixture(run_dir=run_dir)
            batch_path = batch_root / "batch_manifest.json"
            write_projection_batch_manifest(
                repo_root=repo_root,
                batch_manifest_path=batch_path,
                run_dirs=[run_dir],
            )
            external_parent = root / "external-runs"
            run_parent.rename(external_parent)
            run_parent.symlink_to(external_parent, target_is_directory=True)

            with self.assertRaisesRegex(ProjectionError, "unsafe"):
                load_projection_batch_manifest(
                    repo_root=repo_root,
                    batch_manifest_path=batch_path,
                )

    def test_projector_requires_complete_release_result_set(self) -> None:
        """Do not let a B03-only Run shrink the repository release plan."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = scoped_repository(workspace=root)
            batch_root = root / "batch"
            batch_root.mkdir()
            run_dir = batch_root / "run"
            create_structured_b03_run(
                run_dir=run_dir,
                repo_relative_path=(
                    "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
                    "CIK0000078003.json"
                ),
                accession="0000078003-26-100099",
                run_id="run:projection:b03-dependency",
            )
            freeze_fixture(run_dir=run_dir)

            with self.assertRaisesRegex(
                ProjectionError, "Complete batch company metric exact set"
            ):
                write_projection_batch_manifest(
                    repo_root=repo_root,
                    batch_manifest_path=batch_root / "batch_manifest.json",
                    run_dirs=[run_dir],
                )

    def test_projector_rejects_single_company_as_complete_batch(self) -> None:
        """Require every registry company and migrated metric coordinate."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            create_full_release_run(
                run_dir=run_dir,
                run_id="run:projection:single-company",
            )
            freeze_fixture(run_dir=run_dir)
            with self.assertRaisesRegex(
                ProjectionError, "complete batch|company.*metric"
            ):
                write_projection_batch_manifest(
                    repo_root=REPO_ROOT,
                    batch_manifest_path=root / "batch_manifest.json",
                    run_dirs=[run_dir],
                )

    def test_freeze_requires_effective_decision_for_each_review_unit(
        self,
    ) -> None:
        """Do not freeze a complete Candidate while HUMAN review is pending."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            with self.assertRaisesRegex(
                RunStoreError, "Review unit has no effective decision"
            ):
                freeze_fixture(run_dir=run_dir)

    def _assert_append_rejects_self_consistent_reject_with_claims(
        self,
    ) -> None:
        """Enforce context-free REJECT semantics at the persistence API."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            unit = next(
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            )
            required = unit["required_claims"]
            decision = create_review_decision(
                review_unit=unit,
                decision="REJECT",
                approved_claims={},
                required_claims=required,
                reviewer_id="human:reviewer:fixture",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Fixture claims rejected.",
                supersedes_decision_id=None,
            )
            forged = rehash_review_decision(
                decision=decision, approved_claims=required,
            )
            with self.assertRaises(RunStoreError):
                append_review_decision(run_dir=run_dir, decision=forged)
            _manifest, _records, decisions = load_open_run(run_dir=run_dir)
            self.assertEqual([], decisions)

    def _assert_append_rejects_partial_approve_against_review_unit(
        self,
    ) -> None:
        """Enforce whole-unit approval at the low-level append boundary."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            unit = next(
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            )
            required = unit["required_claims"]
            decision = create_review_decision(
                review_unit=unit,
                decision="APPROVE",
                approved_claims=required,
                required_claims=required,
                reviewer_id="human:reviewer:fixture",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Fixture claims approved.",
                supersedes_decision_id=None,
            )
            partial = dict(required)
            del partial[sorted(partial)[0]]
            forged = rehash_review_decision(
                decision=decision, approved_claims=partial,
            )
            with self.assertRaisesRegex(
                RunStoreError, "Review decision semantic binding"
            ):
                append_review_decision(run_dir=run_dir, decision=forged)

    def _assert_finalizer_revalidates_mutated_approve_before_writes(
        self,
    ) -> None:
        """Catch post-append claim mutation before materializing any result."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_review_run(run_dir=run_dir)
            _manifest, _records, decisions = load_open_run(run_dir=run_dir)
            partial = dict(decisions[0]["approved_claims"])
            del partial[sorted(partial)[0]]
            forged = rehash_review_decision(
                decision=decisions[0], approved_claims=partial,
            )
            decisions_path = run_dir / "review_decisions.jsonl"
            decisions_path.write_text(
                json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            records_path = run_dir / "records.jsonl"
            before = records_path.read_bytes()
            with self.assertRaisesRegex(
                WorkflowError, "Review decision semantic binding"
            ):
                finalize_reviewed_direct_results(
                    run_dir=run_dir, repo_root=REPO_ROOT,
                )
            self.assertEqual(before, records_path.read_bytes())

    def _assert_freeze_rejects_mutated_reject_with_dead_claims(self) -> None:
        """Reload decision semantics even when REJECT results stay withheld."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            unit = next(
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            )
            decision = create_review_decision(
                review_unit=unit,
                decision="REJECT",
                approved_claims={},
                required_claims=unit["required_claims"],
                reviewer_id="human:reviewer:fixture",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Fixture claims rejected.",
                supersedes_decision_id=None,
            )
            append_review_decision(run_dir=run_dir, decision=decision)
            finalize_reviewed_direct_results(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            forged = rehash_review_decision(
                decision=decision, approved_claims=unit["required_claims"],
            )
            (run_dir / "review_decisions.jsonl").write_text(
                json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(RunStoreError):
                freeze_fixture(run_dir=run_dir)

    def test_review_decision_semantics_cross_every_trust_boundary(
        self,
    ) -> None:
        """Reapply whole-unit semantics at append, finalize, and reload."""
        self._assert_append_rejects_self_consistent_reject_with_claims()
        self._assert_append_rejects_partial_approve_against_review_unit()
        self._assert_finalizer_revalidates_mutated_approve_before_writes()
        self._assert_freeze_rejects_mutated_reject_with_dead_claims()

    def test_freeze_accepts_each_audit_validation_state(self) -> None:
        """Freeze PASSED, FAILED, and NOT_RUN while preserving their status."""
        cases = (
            ("PASSED", [{"check": "fixture", "status": "PASS"}]),
            ("FAILED", [{"check": "fixture", "status": "FAIL"}]),
            ("NOT_RUN", []),
        )
        for status, checks in cases:
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as directory:
                    run_dir = Path(directory) / "run"
                    create_review_run(run_dir=run_dir)
                    approve_and_finalize(run_dir=run_dir)
                    if status != "NOT_RUN":
                        write_validation_receipt(
                            run_dir=run_dir,
                            status=status,
                            checks=checks,
                        )
                    frozen = freeze_run(
                        run_dir=run_dir, repo_root=REPO_ROOT,
                    )
                    loaded, _records, _decisions = load_frozen_run(
                        run_dir=run_dir, repo_root=REPO_ROOT,
                    )
                    validation = json.loads(
                        (run_dir / "validation.json").read_text(
                            encoding="utf-8",
                        )
                    )
                    self.assertEqual("FROZEN", frozen["status"])
                    self.assertEqual("FROZEN", loaded["status"])
                    self.assertEqual(status, validation["status"])

    def test_freeze_rejects_ai_metric_disguised_as_structured_input(
        self,
    ) -> None:
        """Do not bypass HUMAN review through an empty approval effect."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            manifest, _records, _decisions = load_open_run(run_dir=run_dir)
            source = manifest["source_references"][0]
            forged_scope = {
                "geography": "forged",
                "operating_scope": "forged",
                "period_role": "current_fiscal_year",
                "property_population": "forged",
            }
            forged = structured_observation(
                metric_id="B10",
                semantic_role="occupancy",
                company_id=str(manifest["company_id"]),
                period_start=str(manifest["target_period"]["period_start"]),
                period_end=str(manifest["target_period"]["period_end"]),
                scope=forged_scope,
                value="0.999",
                unit="ratio",
                quality="EXACT",
                source_binding={
                    "raw_asset_id": source["raw_asset_id"],
                    "source_reference_id": source["source_reference_id"],
                    "accession": source["accession"],
                    "document_name": source["document_name"],
                    "source_role": source["source_role"],
                },
            )
            target = {
                "company_id": manifest["company_id"],
                "period_start": manifest["target_period"]["period_start"],
                "period_end": manifest["target_period"]["period_end"],
                "scope": forged_scope,
                "scope_key": content_hash(value=forged_scope),
            }
            result, trace = calculate_observation_metric(
                compiled_spec=compiled_specs()["B10"],
                target=target,
                company_traits=list(manifest["company_traits"]),
                observation=forged,
            )
            for record in (forged, trace, result):
                append_run_record(run_dir=run_dir, record=record)
            with self.assertRaisesRegex(
                RunStoreError, "AI-table observation lacks HUMAN approval"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_recalculates_reviewed_result_from_observation(
        self,
    ) -> None:
        """Reject a self-consistent formula that changes an approved value."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            result = next(
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
                and record["metric_id"] == "B10"
            )
            trace = next(
                record
                for record in records
                if record["record_type"] == "EXECUTION_TRACE"
                and record["trace_id"] == result["trace_id"]
            )
            changed_result = copy.deepcopy(result)
            changed_trace = copy.deepcopy(trace)
            final = next(
                step
                for step in changed_trace["steps"]
                if step["event"] == "FORMULA_RESULT"
            )
            final["formula"] = "0.999"
            final["value"] = "0.999"
            changed_trace["result"] = "0.999"
            changed_result["value"] = "0.999"
            rewrite_result_trace(
                run_dir=run_dir,
                records=records,
                original_trace=trace,
                changed_trace=changed_trace,
                original_result=result,
                changed_result=changed_result,
            )
            with self.assertRaisesRegex(
                RunStoreError, "reviewed calculator replay"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_structured_value_absent_from_raw_bytes(
        self,
    ) -> None:
        """Rebuild structured selection instead of trusting its caller."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_structured_b01_run(run_dir=run_dir, forged_value="999")
            with self.assertRaisesRegex(
                RunStoreError, "structured calculator replay"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_accepts_b01_rebuilt_from_raw_companyfacts(self) -> None:
        """Freeze a real Marriott B01 selected from exact raw bytes."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            result = create_structured_b01_run(
                run_dir=run_dir, forged_value=None,
            )
            frozen = freeze_fixture(run_dir=run_dir)
            self.assertEqual("25100000000", result["value"])
            self.assertEqual("FROZEN", frozen["status"])

    def test_freeze_rejects_false_structured_withheld_result(self) -> None:
        """Recalculate a no-input WITHHELD result from its raw target."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_structured_b01_run(run_dir=run_dir, forged_value=None)
            manifest, records, _decisions = load_open_run(run_dir=run_dir)
            scope = {"consolidation": "entity"}
            source = manifest["source_references"][0]
            result, trace, _observations = calculate_metric(
                compiled_spec=compiled_specs()["B01"],
                target={
                    "accession": source["accession"],
                    "company_id": manifest["company_id"],
                    "entity": "1048286",
                    "period_start": manifest["target_period"][
                        "period_start"
                    ],
                    "period_end": manifest["target_period"]["period_end"],
                    "scope": scope,
                    "scope_key": content_hash(value=scope),
                },
                company_traits=list(manifest["company_traits"]),
                structured_facts=[],
                verified_observations=[],
            )
            self.assertEqual("WITHHELD", result["publication"])
            retained = [
                record
                for record in records
                if record["record_type"] not in {
                    "EXECUTION_TRACE",
                    "METRIC_RESULT",
                    "VERIFIED_OBSERVATION",
                }
            ]
            rewrite_records(
                run_dir=run_dir, records=[*retained, trace, result],
            )
            with self.assertRaisesRegex(
                RunStoreError, "structured calculator replay"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_forged_structured_dependency(self) -> None:
        """Rebuild a reused B01 observation even without a B01 Result."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_structured_b03_dependency_run(run_dir=run_dir)
            with self.assertRaisesRegex(
                RunStoreError, "structured dependency replay"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_pfizer_approx_real_bytes_freezes_and_replays(self) -> None:
        """Preserve the required legacy APPROX branch through FROZEN replay."""
        relative = "evidence/companyfacts/CIK0000078003.json"
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            built = create_structured_b03_run(
                run_dir=run_dir,
                repo_relative_path=relative,
                accession="0000078003-26-000026",
                run_id="run:structured:b03:pfizer-real",
            )
            result = built["result"]
            trace = built["trace"]
            observations = built["observations"]

            # The checked-in legacy row is an acceptance anchor, while the
            # vNext Run remains a distinct recorded/shadow publication path.
            with (REPO_ROOT / "outputs/metrics_matrix.csv").open(
                encoding="utf-8", newline="",
            ) as handle:
                legacy_rows = [
                    row
                    for row in csv.DictReader(handle)
                    if row["company"] == "Pfizer"
                    and row["metric_id"] == "B03"
                ]
            self.assertEqual(1, len(legacy_rows))
            self.assertEqual("OK_APPROX", legacy_rows[0]["status"])
            self.assertEqual(legacy_rows[0]["value"], result["value"])
            self.assertEqual("APPROX", result["quality"])
            self.assertEqual(
                {"EXACT"},
                {
                    observation["quality"]
                    for observation in observations
                    if observation["observation_id"]
                    in trace["input_observation_ids"]
                },
            )
            self.assertIn(
                "APPROX",
                {
                    step["quality"]
                    for step in trace["steps"]
                    if step["event"] == "DERIVED_BRANCH_SELECTED"
                },
            )

            frozen = freeze_fixture(run_dir=run_dir)
            replay = replay_frozen_results(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            self.assertEqual("FROZEN", frozen["status"])
            self.assertEqual(result, replay["results"][0])

    def test_b03_cross_check_boundaries_freeze_and_replay(self) -> None:
        """Carry accepted and rejected 1% boundaries through one full Run."""
        relative = (
            "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
            "CIK0000078003.json"
        )
        cases = (
            ("0000078003-26-100099", "0.0099", "PUBLISHED"),
            ("0000078003-26-100100", "0.01", "PUBLISHED"),
            ("0000078003-26-100101", "0.0101", "WITHHELD"),
        )
        for accession, relative_error, publication in cases:
            with self.subTest(
                accession=accession,
            ), tempfile.TemporaryDirectory() as directory:
                run_dir = Path(directory) / "run"
                built = create_structured_b03_run(
                    run_dir=run_dir,
                    repo_relative_path=relative,
                    accession=accession,
                    run_id="run:structured:b03:" + accession,
                )
                result = built["result"]
                trace = built["trace"]
                self.assertEqual(publication, result["publication"])
                cross_checks = [
                    step
                    for step in trace["steps"]
                    if step["event"] == "CROSS_CHECK_EVALUATED"
                ]
                self.assertEqual(1, len(cross_checks))
                self.assertEqual(
                    relative_error, cross_checks[0]["relative_error"],
                )
                selected_component_ids = {
                    observation_id
                    for step in trace["steps"]
                    if step["event"] == "DERIVED_BRANCH_SELECTED"
                    for observation_id in step["component_observation_ids"]
                }
                self.assertLessEqual(
                    selected_component_ids,
                    set(trace["input_observation_ids"]),
                )

                frozen = freeze_fixture(run_dir=run_dir)
                replay = replay_frozen_results(
                    run_dir=run_dir, repo_root=REPO_ROOT,
                )
                self.assertEqual("FROZEN", frozen["status"])
                self.assertEqual(result, replay["results"][0])

    def test_freeze_rejects_unconsumed_structured_observation(self) -> None:
        """Do not let detached facts enter a frozen projection manifest."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_structured_b01_run(run_dir=run_dir, forged_value=None)
            manifest, _records, _decisions = load_open_run(run_dir=run_dir)
            source = manifest["source_references"][0]
            forged_scope = {"consolidation": "forged-extra"}
            forged = structured_observation(
                metric_id="B01",
                semantic_role="revenue",
                company_id="marriott_international",
                period_start="2024-01-01",
                period_end="2024-12-31",
                scope=forged_scope,
                value="888",
                unit="USD",
                quality="EXACT",
                source_binding={
                    "raw_asset_id": source["raw_asset_id"],
                    "source_reference_id": source["source_reference_id"],
                    "accession": source["accession"],
                    "document_name": source["document_name"],
                    "source_role": source["source_role"],
                    "entity": "1048286",
                    "concept": "us-gaap:Revenues",
                    "duration_days": 366,
                    "fact_id": "fact:forged-extra",
                    "filed": "2025-02-11",
                    "fiscal_period": "FY",
                    "form": "10-K",
                },
            )
            append_run_record(run_dir=run_dir, record=forged)
            with self.assertRaisesRegex(
                RunStoreError, "Observation exact consumption set differs"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_frozen_run_replays_without_any_socket(self) -> None:
        """Recalculate direct results from a hash-bound frozen Run."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            frozen = freeze_fixture(run_dir=run_dir)
            with mock.patch.object(
                socket,
                "socket",
                side_effect=AssertionError("replay opened a socket"),
            ):
                replay = replay_frozen_results(
                    run_dir=run_dir, repo_root=REPO_ROOT,
                )
            self.assertEqual("FROZEN", frozen["status"])
            values = {
                result["metric_id"]: result["value"]
                for result in replay["results"]
            }
            self.assertEqual({"B10": "0.693", "B11": "128.8"}, values)

    def test_freeze_rejects_remote_success_bypassing_adapter(self) -> None:
        """Reapply D-01 when a successful attempt is written directly."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            changed = copy.deepcopy(records)
            attempt = next(
                record
                for record in changed
                if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            )
            observation = attempt["transport_observation"]
            observation.update(
                {
                    "egress_attempted": True,
                    "provider": "forged-provider",
                    "model": "forged-model",
                    "endpoint_host": "attacker.example",
                    "region": "unknown",
                    "retention": "unknown",
                    "data_use": "unknown",
                    "timeout_seconds": 30,
                    "retry_count": 0,
                    "retries_performed": 0,
                    "maximum_payload_bytes": observation[
                        "request_body_bytes"
                    ],
                    "filing_egress_policy": "forged",
                }
            )
            for field in ("provider", "model", "endpoint_host"):
                attempt[field] = observation[field]
            rewrite_records(run_dir=run_dir, records=changed)
            with self.assertRaisesRegex(
                RunStoreError, "lacks approved D-01"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_recomputes_attempt_digests_from_exact_bytes(self) -> None:
        """Reject request-only and coordinated response digest mutations."""
        for mutation in ("request", "response"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
            ) as directory:
                run_dir = Path(directory) / "run"
                create_review_run(run_dir=run_dir)
                approve_and_finalize(run_dir=run_dir)
                _manifest, records, _decisions = load_open_run(
                    run_dir=run_dir
                )
                changed = copy.deepcopy(records)
                attempt = next(
                    record
                    for record in changed
                    if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                )
                if mutation == "request":
                    attempt["request_body_sha256"] = "0" * 64
                else:
                    attempt["raw_response_sha256"] = "0" * 64
                    candidate = next(
                        record
                        for record in changed
                        if record["record_type"] == "OBSERVATION_CANDIDATE"
                    )
                    candidate["raw_response_sha256"] = "0" * 64
                rewrite_records(run_dir=run_dir, records=changed)
                with self.assertRaises(RunStoreError):
                    freeze_fixture(run_dir=run_dir)

    def test_freeze_rebuilds_failed_attempt_request_from_task_spec(
        self,
    ) -> None:
        """Bind a failed attempt request to its repository disclosure Spec."""
        for mutation in (False, True):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
            ) as directory:
                run_dir = Path(directory) / "run"
                result = create_review_run(
                    run_dir=run_dir,
                    recorded_response_bytes=b'{"invalid":true}',
                )
                self.assertEqual("FAILED_ATTEMPT", result["status"])
                _manifest, records, _decisions = load_open_run(
                    run_dir=run_dir
                )
                attempt = next(
                    record
                    for record in records
                    if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                )
                self.assertEqual("FAILED", attempt["status"])
                if mutation:
                    attempt["task_spec_semantic_hash"] = str(
                        compiled_specs()["B10"]["spec_semantic_hash"]
                    )
                    rewrite_records(run_dir=run_dir, records=records)
                    with self.assertRaisesRegex(
                        RunStoreError, "not a disclosure"
                    ):
                        freeze_fixture(run_dir=run_dir)
                else:
                    self.assertEqual(
                        "FROZEN", freeze_fixture(run_dir=run_dir)["status"]
                    )

    def test_run_validation_receipt_binds_immutable_manifest_view(
        self,
    ) -> None:
        """Reject a target mutation after a failed Run was validated."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            result = create_review_run(
                run_dir=run_dir,
                recorded_response_bytes=b'{"invalid":true}',
            )
            self.assertEqual("FAILED_ATTEMPT", result["status"])
            write_validation_receipt(
                run_dir=run_dir,
                status="FAILED",
                checks=[{"check": "FAILED_ATTEMPT", "status": "FAIL"}],
            )
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["target_period"]["period_end"] = "2025-12-30"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RunStoreError, "validation receipt view differs"
            ):
                freeze_run(run_dir=run_dir, repo_root=REPO_ROOT)

    def test_freeze_rejects_company_traits_detached_from_registry(
        self,
    ) -> None:
        """Reject a Run whose applicability traits do not match config."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["company_traits"] = ["financial"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RunStoreError, "company traits differ from repository"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_result_metric_spec_identity_substitution(
        self,
    ) -> None:
        """Reject a caller Spec wrapper that rebrands B10 as B99/USD."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            trace = next(
                record
                for record in records
                if record["record_type"] == "EXECUTION_TRACE"
                and record["metric_id"] == "B10"
            )
            result = next(
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
                and record["metric_id"] == "B10"
            )
            changed_trace = copy.deepcopy(trace)
            changed_result = copy.deepcopy(result)
            changed_trace["metric_id"] = "B99"
            changed_result["metric_id"] = "B99"
            changed_result["unit"] = "USD"
            rewrite_result_trace(
                run_dir=run_dir,
                records=records,
                original_trace=trace,
                changed_trace=changed_trace,
                original_result=result,
                changed_result=changed_result,
            )
            with self.assertRaises(RunStoreError):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_supporting_role_identity_and_unit_substitution(
        self,
    ) -> None:
        """Bind every ADR Observation field to Spec and reviewed content."""
        for mutation in (
            "identity_unit",
            "missing",
            "quality",
            "scope",
            "value",
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
            ) as directory:
                run_dir = Path(directory) / "run"
                create_review_run(run_dir=run_dir)
                approve_and_finalize(run_dir=run_dir)
                _manifest, records, _decisions = load_open_run(
                    run_dir=run_dir
                )
                changed = copy.deepcopy(records)
                adr = next(
                    record
                    for record in changed
                    if record["record_type"] == "VERIFIED_OBSERVATION"
                    and record["semantic_role"] == "adr"
                )
                if mutation == "missing":
                    changed.remove(adr)
                    rewrite_records(run_dir=run_dir, records=changed)
                    with self.assertRaises(RunStoreError):
                        freeze_fixture(run_dir=run_dir)
                    continue
                if mutation == "identity_unit":
                    adr["metric_id"] = "TOTALLY_MADE_UP_METRIC"
                    adr["unit"] = "JPY"
                elif mutation == "value":
                    adr["value"] = "999"
                elif mutation == "scope":
                    adr["scope"] = dict(adr["scope"])
                    adr["scope"]["geography"] = "regional"
                    adr["scope_key"] = content_hash(value=adr["scope"])
                elif mutation == "quality":
                    adr["quality"] = "APPROX"
                body = {
                    key: adr[key]
                    for key in (
                        "semantic_role",
                        "metric_id",
                        "company_id",
                        "period_start",
                        "period_end",
                        "scope",
                        "scope_key",
                        "value",
                        "unit",
                        "source_binding",
                    )
                }
                adr["observation_id"] = content_hash(value=body)
                rewrite_records(run_dir=run_dir, records=changed)
                with self.assertRaises(RunStoreError):
                    freeze_fixture(run_dir=run_dir)

    def test_run_period_is_the_only_finalization_period(self) -> None:
        """Reject an inconsistent Run label and changed result period."""
        with tempfile.TemporaryDirectory() as directory:
            invalid_dir = Path(directory) / "invalid-run"
            with self.assertRaisesRegex(
                RunStoreError, "business coordinates"
            ):
                create_review_run(
                    run_dir=invalid_dir,
                    target_period={
                        "fiscal_year": 2025,
                        "period_start": "2030-01-01",
                        "period_end": "2030-12-31",
                    },
                )
            self.assertFalse(invalid_dir.exists())
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            trace = next(
                record
                for record in records
                if record["record_type"] == "EXECUTION_TRACE"
            )
            result = next(
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
                and record["trace_id"] == trace["trace_id"]
            )
            changed_trace = copy.deepcopy(trace)
            changed_result = copy.deepcopy(result)
            changed_result["period_start"] = "2030-01-01"
            changed_result["period_end"] = "2030-12-31"
            rewrite_result_trace(
                run_dir=run_dir,
                records=records,
                original_trace=trace,
                changed_trace=changed_trace,
                original_result=result,
                changed_result=changed_result,
            )
            with self.assertRaises(RunStoreError):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_result_business_state_detached_from_inputs(
        self,
    ) -> None:
        """Bind the complete Result set and business state to inputs."""
        for mutation in (
            "applicability",
            "missing",
            "quality",
            "reason",
            "scope",
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
            ) as directory:
                run_dir = Path(directory) / "run"
                create_review_run(run_dir=run_dir)
                approve_and_finalize(run_dir=run_dir)
                _manifest, records, _decisions = load_open_run(
                    run_dir=run_dir
                )
                trace = next(
                    record
                    for record in records
                    if record["record_type"] == "EXECUTION_TRACE"
                )
                result = next(
                    record
                    for record in records
                    if record["record_type"] == "METRIC_RESULT"
                    and record["trace_id"] == trace["trace_id"]
                )
                if mutation == "missing":
                    changed = [
                        record
                        for record in records
                        if record not in (trace, result)
                    ]
                    rewrite_records(run_dir=run_dir, records=changed)
                    with self.assertRaises(RunStoreError):
                        freeze_fixture(run_dir=run_dir)
                    continue
                changed_trace = copy.deepcopy(trace)
                changed_result = copy.deepcopy(result)
                if mutation == "scope":
                    changed_result["scope_key"] = "sha256:" + "d" * 64
                elif mutation == "quality":
                    changed_result["quality"] = "APPROX"
                    changed_trace["quality"] = "APPROX"
                    formula = next(
                        step
                        for step in changed_trace["steps"]
                        if step["event"] == "FORMULA_RESULT"
                    )
                    formula["quality"] = "APPROX"
                elif mutation == "applicability":
                    changed_result["applicability"] = "N_A_STRUCTURAL"
                elif mutation == "reason":
                    changed_result["reason_code"] = "FORGED_SUCCESS_REASON"
                rewrite_result_trace(
                    run_dir=run_dir,
                    records=records,
                    original_trace=trace,
                    changed_trace=changed_trace,
                    original_result=result,
                    changed_result=changed_result,
                )
                with self.assertRaises(RunStoreError):
                    freeze_fixture(run_dir=run_dir)

    def test_reviewed_currency_mismatch_materializes_withheld_results(
        self,
    ) -> None:
        """Do not relabel EUR RevPAR/ADR values as canonical USD."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(
                run_dir=run_dir,
                reported_units={
                    "occupancy": "percent",
                    "revpar": "EUR",
                    "adr": "EUR",
                },
            )
            approve_and_finalize(run_dir=run_dir)
            manifest, records, decisions = load_open_run(run_dir=run_dir)
            results = [
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
            ]
            self.assertEqual(2, len(results))
            self.assertEqual(
                {"WITHHELD"},
                {str(result["publication"]) for result in results},
            )
            self.assertEqual(
                {"REPORTED_UNIT_MISMATCH"},
                {str(result["reason_code"]) for result in results},
            )
            unit = next(
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            )
            evidence = next(
                record
                for record in records
                if record["record_type"] == "EVIDENCE_CHECK"
            )
            candidate = next(
                record
                for record in records
                if record["record_type"] == "OBSERVATION_CANDIDATE"
            )
            forged = reviewed_observation(
                metric_id="B11",
                role="revpar",
                company_id=str(manifest["company_id"]),
                period_start=str(manifest["target_period"]["period_start"]),
                period_end=str(manifest["target_period"]["period_end"]),
                canonical_unit="USD",
                candidate=candidate,
                evidence_check=evidence,
                review_unit=unit,
                decision=decisions[-1],
                source_reference=unit["source_bindings"][0],
                derived_asset_id=str(candidate["derived_asset_ids"][0]),
                quality="EXACT",
            )
            append_run_record(run_dir=run_dir, record=forged)
            with self.assertRaisesRegex(
                RunStoreError, "Candidate unit is incompatible"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_applicable_result_rebranded_structural(
        self,
    ) -> None:
        """Bind applicable WITHHELD state and reason to Spec/Trace."""
        for mutation in ("applicability", "not_meaningful", "reason"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
            ) as directory:
                run_dir = Path(directory) / "run"
                create_review_run(
                    run_dir=run_dir,
                    reported_units={
                        "occupancy": "percent",
                        "revpar": "EUR",
                        "adr": "EUR",
                    },
                )
                approve_and_finalize(run_dir=run_dir)
                _manifest, records, _decisions = load_open_run(
                    run_dir=run_dir
                )
                result = next(
                    record
                    for record in records
                    if record["record_type"] == "METRIC_RESULT"
                )
                trace = next(
                    record
                    for record in records
                    if record["record_type"] == "EXECUTION_TRACE"
                    and record["trace_id"] == result["trace_id"]
                )
                changed_result = copy.deepcopy(result)
                changed_trace = copy.deepcopy(trace)
                if mutation == "applicability":
                    changed_result["applicability"] = "N_A_STRUCTURAL"
                    changed_result["publication"] = "PUBLISHED"
                    changed_result["reason_code"] = "TRAIT_NOT_APPLICABLE"
                    changed_trace["steps"] = [{"event": "N_A_STRUCTURAL"}]
                elif mutation == "not_meaningful":
                    changed_result["publication"] = "PUBLISHED"
                    changed_result["quality"] = "NOT_MEANINGFUL"
                    changed_result["reason_code"] = "DENOMINATOR_ZERO"
                    changed_trace["quality"] = "NOT_MEANINGFUL"
                elif mutation == "reason":
                    changed_result["reason_code"] = "FORGED_WITHHELD_REASON"
                    withheld = next(
                        step
                        for step in changed_trace["steps"]
                        if step["event"] == "WITHHELD"
                    )
                    withheld["reason_code"] = "FORGED_WITHHELD_REASON"
                rewrite_result_trace(
                    run_dir=run_dir,
                    records=records,
                    original_trace=trace,
                    changed_trace=changed_trace,
                    original_result=result,
                    changed_result=changed_result,
                )
                with self.assertRaises(RunStoreError):
                    freeze_fixture(run_dir=run_dir)

    def test_invalid_create_run_input_leaves_no_partial_directory(
        self,
    ) -> None:
        """Validate duplicate source identity before authoritative writes."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            source = {
                "record_type": "SOURCE_REFERENCE",
                "source_reference_id": "sha256:" + "a" * 64,
                "raw_asset_id": "sha256:" + "b" * 64,
                "company_id": "company_fixture",
                "source_url": "https://www.sec.gov/Archives/sample.htm",
                "accession": "0000000000-25-000001",
                "document_name": "sample.htm",
                "source_role": "target_primary",
                "request_attempt_id": "request:attempt:fixture",
            }
            source_identity = {
                key: source[key]
                for key in (
                    "raw_asset_id",
                    "company_id",
                    "source_url",
                    "accession",
                    "document_name",
                    "source_role",
                )
            }
            source["source_reference_id"] = content_hash(
                value=source_identity
            )
            with self.assertRaisesRegex(RunStoreError, "duplicated"):
                create_run(
                    run_dir=run_dir,
                    run_id="run:create:fixture",
                    company_id="company_fixture",
                    company_traits=["non_financial"],
                    target_period={
                        "fiscal_year": 2025,
                        "period_start": "2025-01-01",
                        "period_end": "2025-12-31",
                    },
                    source_references=[source, copy.deepcopy(source)],
                    missing_required_source_roles=[],
                    spec_file_hashes={},
                    requirement_hashes={},
                )
            self.assertFalse(run_dir.exists())
            cross_company_dir = Path(directory) / "cross_company"
            with self.assertRaisesRegex(RunStoreError, "company differs"):
                create_run(
                    run_dir=cross_company_dir,
                    run_id="run:create:cross-company",
                    company_id="another_company",
                    company_traits=["non_financial"],
                    target_period={
                        "fiscal_year": 2025,
                        "period_start": "2025-01-01",
                        "period_end": "2025-12-31",
                    },
                    source_references=[source],
                    missing_required_source_roles=[],
                    spec_file_hashes={},
                    requirement_hashes={},
                )
            self.assertFalse(cross_company_dir.exists())

    def test_freeze_replays_derived_asset_from_parent_bytes(self) -> None:
        """Reject a grid built from bytes outside its declared parent."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            relative = "tests/fixtures/vnext/sample_lodging.html"
            raw = raw_blob_record(
                repo_root=REPO_ROOT,
                repo_relative_path=relative,
                media_type="text/html",
            )
            source = source_reference_record(
                raw_blob=raw,
                company_id="company_fixture",
                source_url="https://www.sec.gov/Archives/sample.htm",
                accession="0000000000-25-000001",
                document_name="sample.htm",
                source_role="target_primary",
                request_attempt_id="request:attempt:fixture",
            )
            forged_asset = build_table_grid(
                html_bytes=b"<table><tr><td>forged</td></tr></table>",
                parent_raw_asset_ids=[str(raw["raw_asset_id"])],
                storage_uri="artifacts/vnext/derived/forged.json",
            )
            requirement = load_requirement_snapshot(
                snapshot_dir=(
                    REPO_ROOT / "requirements" / "ai_first_v3_3_1"
                )
            )
            create_run(
                run_dir=run_dir,
                run_id="run:derived:fixture",
                company_id="company_fixture",
                company_traits=["non_financial"],
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
                source_references=[source],
                missing_required_source_roles=[],
                spec_file_hashes={},
                requirement_hashes=requirement["hashes"],
            )
            for record in (raw, source, forged_asset):
                append_run_record(run_dir=run_dir, record=record)
            with self.assertRaisesRegex(RunStoreError, "DerivedAsset bytes"):
                freeze_run(run_dir=run_dir, repo_root=REPO_ROOT)

    def test_human_rejection_materializes_withheld_results(self) -> None:
        """Freeze missing-source audit only with WITHHELD results."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            unit = [
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            ][0]
            required = compiled_specs()["DISCLOSURE"]["compiled"][
                "required_claims"
            ]
            decision = create_review_decision(
                review_unit=unit,
                decision="REJECT",
                approved_claims={},
                required_claims=required,
                reviewer_id="human:reviewer:fixture",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Fixture claims rejected.",
                supersedes_decision_id=None,
            )
            append_review_decision(run_dir=run_dir, decision=decision)
            finalized = finalize_reviewed_direct_results(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            results = [
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
            ]
            self.assertEqual(2, len(finalized["result_ids"]))
            self.assertEqual(
                {"WITHHELD"}, {result["publication"] for result in results}
            )
            self.assertEqual(
                {"HUMAN_REVIEW_REJECTED"},
                {result["reason_code"] for result in results},
            )
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["missing_required_source_roles"] = ["target_primary"]
            manifest_path.write_text(
                json.dumps(
                    manifest, ensure_ascii=False, indent=2, sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
            frozen = freeze_fixture(run_dir=run_dir)
            self.assertEqual("FROZEN", frozen["status"])
            self.assertEqual(
                ["target_primary"], frozen["missing_required_source_roles"],
            )

    def test_freeze_rejects_trace_values_detached_from_observations(
        self,
    ) -> None:
        """Bind final resolved values to exact input observations at freeze."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            trace = next(
                record
                for record in records
                if record["record_type"] == "EXECUTION_TRACE"
                and record["metric_id"] == "B10"
            )
            result = next(
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
                and record["metric_id"] == "B10"
            )
            changed_trace = copy.deepcopy(trace)
            final = next(
                step
                for step in changed_trace["steps"]
                if step["event"] == "FORMULA_RESULT"
            )
            final["resolved_values"]["occupancy"] = "0.7"
            final["value"] = "0.7"
            changed_trace["result"] = "0.7"
            changed_result = copy.deepcopy(result)
            changed_result["value"] = "0.7"
            rewrite_result_trace(
                run_dir=run_dir,
                records=records,
                original_trace=trace,
                changed_trace=changed_trace,
                original_result=result,
                changed_result=changed_result,
            )
            with self.assertRaisesRegex(
                RunStoreError, "Trace resolved value"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_observation_source_identity_detached_from_run(
        self,
    ) -> None:
        """Bind every Observation provenance field to its SourceReference."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            manifest, _records, _decisions = load_open_run(run_dir=run_dir)
            source = manifest["source_references"][0]
            forged = structured_observation(
                metric_id="B01",
                semantic_role="detached_probe",
                company_id="marriott_international",
                period_start="2025-01-01",
                period_end="2025-12-31",
                scope={"consolidation": "entity"},
                value="1",
                unit="USD",
                quality="EXACT",
                source_binding={
                    "raw_asset_id": "sha256:" + "0" * 64,
                    "source_reference_id": source["source_reference_id"],
                    "accession": "0000000000-25-999999",
                    "document_name": "forged.htm",
                    "source_role": "forged_role",
                },
            )
            append_run_record(run_dir=run_dir, record=forged)
            with self.assertRaisesRegex(
                RunStoreError, "SourceReference field differs"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_result_fields_detached_from_trace(self) -> None:
        """Make one Trace bind the complete publishable result contract."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            original = next(
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
            )
            forged = copy.deepcopy(original)
            forged["scope_key"] = "sha256:" + "d" * 64
            result_fields = (
                "company_id",
                "metric_id",
                "period_start",
                "period_end",
                "scope_key",
                "spec_closure_hash",
                "applicability",
                "quality",
                "publication",
                "reason_code",
                "value",
                "unit",
                "trace_id",
            )
            forged["result_id"] = content_hash(
                value={key: forged[key] for key in result_fields}
            )
            rewritten = [
                forged if record is original else record for record in records
            ]
            records_text = "\n".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True)
                for record in rewritten
            ) + "\n"
            (run_dir / "records.jsonl").write_text(
                records_text, encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RunStoreError, "calculation target differs"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_candidate_without_its_ai_attempt(self) -> None:
        """Require a Candidate to bind one successful recorded attempt."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            without_attempt = [
                record
                for record in records
                if record["record_type"] != "AI_EXTRACTION_ATTEMPT"
            ]
            records_text = "\n".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True)
                for record in without_attempt
            ) + "\n"
            (run_dir / "records.jsonl").write_text(
                records_text, encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RunStoreError, "AI attempt is absent|artifact exact set"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_replays_evidence_instead_of_trusting_pass(self) -> None:
        """Reject a self-hashed PASS record that differs from source cells."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            original = next(
                record
                for record in records
                if record["record_type"] == "EVIDENCE_CHECK"
            )
            forged = copy.deepcopy(original)
            forged["normalized_values"]["occupancy"] = "0.999"
            evidence_fields = (
                "candidate_hash",
                "status",
                "normalized_values",
                "checks",
                "reason_codes",
                "identity_constraints",
            )
            forged["evidence_check_id"] = content_hash(
                value={key: forged[key] for key in evidence_fields}
            )
            append_run_record(run_dir=run_dir, record=forged)
            with self.assertRaisesRegex(
                RunStoreError, "differs from mechanical replay"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_trace_formula_detached_from_result(self) -> None:
        """Recalculate the final formula before a Run becomes immutable."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            trace = next(
                record
                for record in records
                if record["record_type"] == "EXECUTION_TRACE"
                and record["metric_id"] == "B10"
            )
            result = next(
                record
                for record in records
                if record["record_type"] == "METRIC_RESULT"
                and record["metric_id"] == "B10"
            )
            changed_trace = copy.deepcopy(trace)
            final = next(
                step
                for step in changed_trace["steps"]
                if step["event"] == "FORMULA_RESULT"
            )
            final["formula"] = {
                "op": "multiply",
                "args": ["occupancy", "occupancy"],
            }
            rewrite_result_trace(
                run_dir=run_dir,
                records=records,
                original_trace=trace,
                changed_trace=changed_trace,
                original_result=result,
                changed_result=copy.deepcopy(result),
            )
            with self.assertRaisesRegex(
                RunStoreError, "formula cannot be recalculated"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_rejects_unapproved_observation_effect(self) -> None:
        """Require every reviewed observation to bind an effective approval."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            forged = copy.deepcopy(
                next(
                    record
                    for record in records
                    if record["record_type"] == "VERIFIED_OBSERVATION"
                )
            )
            forged["semantic_role"] = "forged_reviewed_role"
            forged["approval_effect_hash"] = "sha256:" + "0" * 64
            observation_fields = (
                "semantic_role",
                "metric_id",
                "company_id",
                "period_start",
                "period_end",
                "scope",
                "scope_key",
                "value",
                "unit",
                "source_binding",
            )
            forged["observation_id"] = content_hash(
                value={key: forged[key] for key in observation_fields}
            )
            append_run_record(run_dir=run_dir, record=forged)
            with self.assertRaisesRegex(
                RunStoreError, "approval effect"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_review_bytes_are_reread_before_freeze(self) -> None:
        """Close review TOCTOU by rejecting changed rendered bytes."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            review_files = list((run_dir / "review").glob("*/review.md"))
            self.assertEqual(1, len(review_files))
            review_files[0].write_bytes(
                review_files[0].read_bytes() + b"tamper"
            )
            with self.assertRaisesRegex(
                RunStoreError, "Rendered review changed"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_freeze_reconstructs_review_context_from_records(self) -> None:
        """Do not trust a self-consistent but misleading review document."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            unit = next(
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            )
            review_dir = run_dir / "review" / str(unit["review_unit_hash"])
            context = json.loads(
                (review_dir / "review_context.json").read_text(
                    encoding="utf-8"
                )
            )
            context["untrusted_filing_notice"] = (
                "Misleading context not reconstructed from Run records."
            )
            context_bytes = canonical_json_bytes(value=context)
            rendered = render_review_markdown(review_context=context)
            changed = copy.deepcopy(unit)
            changed["review_context_hash"] = sha256_bytes(
                content=context_bytes
            )
            changed["rendered_review_hash"] = rendered[
                "rendered_review_hash"
            ]
            unit_fields = (
                "selected",
                "competing_candidates",
                "unresolved_competing_claims",
                "candidate_hashes",
                "source_bindings",
                "spec_semantic_hash",
                "compiled_spec",
                "required_claims",
                "evidence_check_id",
                "review_context_hash",
                "rendered_review_hash",
                "review_renderer_semantic_version",
            )
            changed["review_unit_hash"] = content_hash(
                value={key: changed[key] for key in unit_fields}
            )
            changed_dir = run_dir / "review" / str(
                changed["review_unit_hash"]
            )
            review_dir.rename(changed_dir)
            (changed_dir / "review_context.json").write_bytes(context_bytes)
            (changed_dir / "review.md").write_bytes(rendered["bytes"])
            rewritten = [
                changed if record is unit else record for record in records
            ]
            records_text = "\n".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True)
                for record in rewritten
            ) + "\n"
            (run_dir / "records.jsonl").write_text(
                records_text, encoding="utf-8",
            )
            decision = create_review_decision(
                review_unit=changed,
                decision="APPROVE",
                approved_claims=changed["required_claims"],
                required_claims=changed["required_claims"],
                reviewer_id="human:reviewer:context-fixture",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Self-consistent but misleading fixture.",
                supersedes_decision_id=None,
            )
            append_review_decision(run_dir=run_dir, decision=decision)
            finalize_reviewed_direct_results(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            with self.assertRaisesRegex(
                RunStoreError, "context differs from records"
            ):
                freeze_fixture(run_dir=run_dir)

    def test_frozen_files_cannot_be_appended_or_tampered(self) -> None:
        """Reject API mutation and byte-level record drift after freeze."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            create_review_run(run_dir=run_dir)
            approve_and_finalize(run_dir=run_dir)
            freeze_fixture(run_dir=run_dir)
            _manifest, records, _decisions = load_frozen_run(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            with self.assertRaisesRegex(RunStoreError, "cannot be modified"):
                append_run_record(run_dir=run_dir, record=records[0])
            records_path = run_dir / "records.jsonl"
            records_path.write_bytes(records_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ReplayError, "verification failed"):
                replay_frozen_results(
                    run_dir=run_dir, repo_root=REPO_ROOT,
                )


if __name__ == "__main__":
    unittest.main()
