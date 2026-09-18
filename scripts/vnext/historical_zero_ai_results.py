"""Rebuild the revenue route for an explicitly selected historical period.

Like ``historical_results``, this is a source adapter rather than a second
calculator: the installed B01/B03 Spec documents, ``_structured_concepts``,
``companyfacts_structured_facts``, ``adapt_companyfacts`` and ``calculate_metric``
are imported unchanged from the frozen modules. What this module owns is which
filing the Company Facts accession role means when the period is pinned.

It exists as a successor file because ``scripts/vnext/normal_zero_ai_results.py``
is byte-bound by the ``issue_28_v13`` rule set; changing it would stop every
existing ordinary Run from loading its own Requirement.

Only the revenue routes are wired. Event windows, the successor-registrant
income statement and an amended historical target are refused as explicit
implementation gaps, because each is defined relative to the current period and
answering them from today's latest filing would be a wrong answer.
"""
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url

from .annual_update import AnnualUpdateError
from .batch_workflow import BatchWorkflowError, _structured_concepts
from .calculator import calculate_metric, withheld_metric_result
from .canonical import content_hash, sha256_file
from .historical_annual_input import prepare_historical_annual_input
from .normal_annual_input_v2 import exact_json_value
from .normal_governance_input import _Sources, NormalGovernanceInputError
from .normal_zero_ai_results import (B01_SPEC_PATH, B03_SPEC_PATH, NormalZeroAiError,
                                     _authority, _exact_set)
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import companyfacts_structured_facts, SourceError
from .specs import compile_spec_file
from .traits import repository_company_traits
from .deterministic_router import adapt_companyfacts


RECORD_TYPE = "HISTORICAL_ZERO_AI_SOURCE_RESULT"
SUPPORTED_METRICS = ("B01", "B03")
_SOURCE_ERRORS = (NormalZeroAiError, NormalGovernanceInputError, AnnualUpdateError,
                  BatchWorkflowError, SourceError)


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise NormalZeroAiError(reason, category)


def resolve_historical_zero_ai_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                      period_selection):
    """Resolve revenue, or EBITDA margin with its rebuilt revenue dependency.

    Values come from the selected filing's own accession, which is the same
    first-report semantics the current route uses, applied to a past target.
    """
    _need(metric_id in SUPPORTED_METRICS,
          "HISTORICAL_ZERO_AI_METRIC_NOT_WIRED:" + metric_id, "IMPLEMENTATION_GAP")
    authority = _authority(repo_root)
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    _need(not prepared["amendments"], "HISTORICAL_ZERO_AI_AMENDED_TARGET_NOT_IMPLEMENTED",
          "IMPLEMENTATION_GAP")
    _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY",
          "HISTORICAL_ZERO_AI_SUCCESSOR_SCOPE_NOT_IMPLEMENTED", "IMPLEMENTATION_GAP")
    period = prepared["table_input"]["target_period"]
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])),
                            role="sec_submissions_inventory", media_type="application/json")
    reader.primary(prepared["filing"])
    facts_source = reader.read(companyfacts_url(cik=int(prepared["entity"])),
                               accession=prepared["filing"]["accessionNumber"],
                               role="companyfacts", media_type="application/json")
    traits = repository_company_traits(repo_root=repo_root, company_id=company_id)
    dependency_specs = {}
    spec_path = B01_SPEC_PATH if metric_id == "B01" else B03_SPEC_PATH
    if metric_id == "B03":
        dependency_specs["B01"] = compile_spec_file(path=repo_root / B01_SPEC_PATH,
                                                    dependency_specs={})
    spec = compile_spec_file(path=repo_root / spec_path, dependency_specs=dependency_specs)
    scope = {"entity_scope": "registrant", "period_basis": "source_annual_duration"}
    target = {"company_id": company_id, "period_start": period["period_start"],
              "period_end": period["period_end"], "scope": scope,
              "scope_key": scope_key(scope=scope)}
    claims, source_sets, observations, dependency_records = [], [], [], []
    selection = {}
    try:
        manifest = _exact_set(prepared, inventory, facts_source, "companyfacts")
        source_sets = [manifest]
        approved = sorted(set(_structured_concepts(compiled_spec=spec)) | {
            concept for dependency in dependency_specs.values()
            for concept in _structured_concepts(compiled_spec=dependency)})
        facts = companyfacts_structured_facts(
            raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
            approved_concepts=approved, allowed_ciks=[prepared["entity"]], include_instant=False)
        claims = adapt_companyfacts(
            raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
            source_set_manifest=manifest, approved_concepts=approved,
            allowed_ciks=[prepared["entity"]], include_instant=False)
        execution_target = {**target, "entity": prepared["entity"],
                            "accession": prepared["filing"]["accessionNumber"]}
        reusable = []
        for dependency in dependency_specs.values():
            dep_result, dep_trace, dep_observations = calculate_metric(
                compiled_spec=dependency, target=execution_target, company_traits=traits,
                structured_facts=facts, verified_observations=[])
            dependency_records.extend([*dep_observations, dep_trace, dep_result])
            reusable.extend(dep_observations)
        result, trace, observations = calculate_metric(
            compiled_spec=spec, target=execution_target, company_traits=traits,
            structured_facts=facts, verified_observations=reusable)
        selection = {"source_candidate_count": len(facts),
                     "selected_fact_ids": [o["source_binding"]["fact_id"] for o in observations],
                     "source_reported_periods": sorted({(f["period_start"], f["period_end"])
                                                        for f in facts}),
                     "reason_code": result["reason_code"]}
    except _SOURCE_ERRORS as error:
        reason = str(error)
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code="HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED")
        observations = []
        selection = {"reason_code": result["reason_code"], "reason": reason,
                     "category": getattr(error, "category", "SOURCE_INTEGRITY_ERROR")}
    proofs = list({content_hash(value=p): p for p in
                   [*prepared["source_proofs"],
                    *[entry["proof"] for entry in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    source_records = list(reader.records.values())
    input_binding = {"prepared_input": prepared, "target": target, "target_period": period,
                     "period_selection": period_selection, "amendment_input": None,
                     "spec_origin": {"spec_path": spec_path},
                     "spec_closure_hash": spec["spec_closure_hash"],
                     "authority_file_hashes": authority,
                     "dependency_spec_closure_hashes": {key: value["spec_closure_hash"]
                                                        for key, value in dependency_specs.items()},
                     "source_proofs": proofs, "source_admission": admission,
                     "source_set_manifests": source_sets,
                     "failed_source_attempts": list(reader.failed_attempts.values()),
                     "selection": selection,
                     "resolver_sha256": sha256_file(path=Path(__file__))}
    body = {"record_type": RECORD_TYPE, "company_id": company_id, "metric_id": metric_id,
            "period_selection": period_selection, "spec_path": spec_path,
            "spec_origin": {"spec_path": spec_path}, "compiled_spec": spec,
            "authority_file_hashes": authority, "dependency_specs": dependency_specs,
            "dependency_records": dependency_records, "input_binding": input_binding,
            "prepared_input": prepared, "target_period": period, "target": target,
            "source_records": source_records,
            "source_references": [r for r in source_records
                                  if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": proofs, "source_admission": admission,
            "source_set_manifests": source_sets, "filings": [prepared["filing"]],
            "claims": claims, "selection": selection, "observations": observations,
            "result": result, "trace": trace,
            "records": list({content_hash(value=r): r for r in
                             [*source_records, *dependency_records, *observations,
                              trace, result]}.values()),
            "failed_source_attempts": list(reader.failed_attempts.values()),
            "native_run_status": "NOT_CREATED", "current_latest_verified": False,
            "latest_restated_values_used": False,
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_binding_id": content_hash(value=body["input_binding"]),
            "component_id": content_hash(value=body)}


def verify_historical_zero_ai_metric(*, candidate, repo_root: Path, company_id: str,
                                     metric_id: str, period_selection):
    rebuilt = resolve_historical_zero_ai_metric(repo_root=repo_root, company_id=company_id,
                                                metric_id=metric_id,
                                                period_selection=period_selection)
    _need(candidate == rebuilt, "HISTORICAL_ZERO_AI_SOURCE_REPLAY_CHANGED",
          "SOURCE_REPLAY_CONFLICT")
    return rebuilt
