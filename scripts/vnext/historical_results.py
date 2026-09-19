"""Rebuild catalog metrics for an explicitly selected historical period.

This is a source adapter, not a second calculator. The metric catalog, the
compiled Specs, the deterministic metric graph, the applicability rules and the
withheld-result constructor are the installed current ones, imported unchanged
from ``normal_companyfacts_results`` and ``zero_ai_r2``. What this module owns
is which filing each accession role means when the period is pinned.

It exists as a successor file because ``scripts/vnext/normal_companyfacts_results.py``
and ``scripts/vnext/normal_run_inputs.py`` are byte-bound by the ``issue_28_v13``
rule set: changing them would stop every existing ordinary Run from loading its
own Requirement.

Routes whose source scope is defined relative to the current period — amendment
scope, successor-registrant income statements, event windows — are refused here
as implementation gaps. Resolving them against today's latest filing under a
historical request would be a wrong answer, not a missing feature.
"""
from datetime import date, timedelta
from decimal import DecimalException
from pathlib import Path

from sec_urls import submissions_url

from .calculator import metric_is_applicable, withheld_metric_result
from .canonical import content_hash, sha256_file
from .historical_annual_input import prepare_historical_annual_input
from .normal_annual_input import annual_period, _registry_rows
from .normal_companyfacts_results import (CATALOG_PATH, NormalCompanyfactsError,
                                          _SOURCE_ERRORS, _authority, _filing_source,
                                          _prior_filing)
from .normal_annual_input_v2 import exact_json_value
from .historical_spec_revision import compile_historical_spec_file
from .normal_governance_input import _Sources
from .normal_run_specs import validate_ordinary_spec_files
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .traits import repository_company_traits
from .zero_ai_r2 import (_load_deterministic_catalog, _compiled_deterministic_spec,
                         _deterministic_metric_graph, _manual_result_trace)


RESULT_RECORD_TYPE = "HISTORICAL_COMPANYFACTS_NATIVE_RESULTS"
RUN_INPUT_RECORD_TYPE = "HISTORICAL_ZERO_AI_RUN_INPUT"


def _need(condition, reason):
    if not condition:
        raise NormalCompanyfactsError(reason)


def resolve_historical_companyfacts_metrics(*, repo_root: Path, company_id: str, period_selection):
    """Resolve the Company Facts catalog metrics for one pinned period.

    Current values come from the selected filing's own accession; prior values
    come from the filing immediately preceding it, each from its own selected
    report. That is the frozen first-report semantics, applied to a past target
    rather than to the latest one, and it is not a restated view.
    """
    authority = _authority(repo_root)
    catalog = _load_deterministic_catalog(repo_root=repo_root)
    routes = {key: value for key, value in catalog["metrics"].items()
              if value["adapter_id"] == "companyfacts"}
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    _need(not prepared["amendments"], "HISTORICAL_COMPANYFACTS_AMENDED_TARGET_NOT_IMPLEMENTED")
    _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY",
          "HISTORICAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED")
    period = prepared["table_input"]["target_period"]
    registry = next(r for r in _registry_rows(repo_root=repo_root) if r["company_id"] == company_id)
    traits = repository_company_traits(repo_root=repo_root, company_id=company_id)
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])),
                            role="sec_submissions_inventory", media_type="application/json")
    reader.primary(prepared["filing"])
    concepts = sorted({concept for route in routes.values() for branch in route["branches"]
                       for component in branch["components"] for concept in component["approved_concepts"]})
    sources, claims_by_role = [], {}
    source, claims_by_role["current"] = _filing_source(reader, prepared, prepared["filing"],
                                                       inventory, concepts)
    sources.append({**source, "accession_role": "current"})
    periods = {"current": period, "prior": None}
    filings = {"current": prepared["filing"], "prior": None}
    prior_error = None
    needs_prior = any(metric_is_applicable(applicability=route["applicability"], traits=traits)
                      and any(c["accession_role"] == "prior" for b in route["branches"]
                              for c in b["components"]) for route in routes.values())
    if needs_prior:
        try:
            filing, prior_inventory = _prior_filing(reader, inventory, prepared)
            # The selected period already proved which filing precedes it from
            # the complete saved catalog; the source walk must land on it.
            _need(period_selection["prior_filing"] is not None
                  and filing["accessionNumber"] == period_selection["prior_filing"]["accessionNumber"],
                  "HISTORICAL_COMPANYFACTS_PRIOR_DIFFERS_FROM_SELECTION")
            # The prior role needs that filing's own annual interval and its
            # adjacency to the target, not an issuer fiscal-year label, so the
            # accession's own authenticated instance is a valid substitute here
            # exactly as it is on the frozen current route. The target role is a
            # different question and still requires the full primary document.
            primary = reader.primary(filing, required=False)
            documents = [primary] if primary else reader.auditor_filing(filing)
            source_periods = [annual_period(raw=s["raw_bytes"], cik=prepared["entity"], filing=filing)
                              for s in documents]
            _need(bool(source_periods) and all(p == source_periods[0] for p in source_periods),
                  "HISTORICAL_COMPANYFACTS_PRIOR_NATIVE_PERIOD_CONFLICT")
            prior = source_periods[0]
            _need(date.fromisoformat(prior["period_end"]) + timedelta(days=1)
                  == date.fromisoformat(period["period_start"]),
                  "HISTORICAL_COMPANYFACTS_PRIOR_PERIOD_NOT_ADJACENT")
            source, claims_by_role["prior"] = _filing_source(reader, prepared, filing,
                                                             prior_inventory, concepts)
            sources.append({**source, "accession_role": "prior"})
            periods["prior"], filings["prior"] = prior, filing
        except (*_SOURCE_ERRORS, NormalCompanyfactsError) as error:
            prior_error = {"reason": str(error), "error_type": type(error).__name__}
    context = {"repo_root": repo_root, "deterministic_catalog": catalog,
               "role_context": {(company_id, "companyfacts"):
                                {"sources": sources, "claims_by_accession_role": claims_by_role}},
               "target_periods": {company_id: periods}, "targets": {company_id: period},
               "registry": {company_id: registry},
               "filings_by_company": {company_id: {role: ({"accession": filing["accessionNumber"]}
                                                          if filing else None)
                                                   for role, filing in filings.items()}}}
    results = {}
    for metric_id, route in routes.items():
        spec = _compiled_deterministic_spec(metric_id=metric_id, route=route)
        instant = route["result_period_role"] == "current_instant"
        scope = {"coverage": "deterministic_source_set", "fiscal_year": period["fiscal_year"]}
        target = {"company_id": company_id,
                  "period_start": period["period_end"] if instant else period["period_start"],
                  "period_end": period["period_end"], "scope": scope,
                  "scope_key": scope_key(scope=scope)}
        detail = None
        graph = {"claims": [], "projection_claims": [], "observation": None}
        if not metric_is_applicable(applicability=route["applicability"], traits=traits):
            result, trace = _manual_result_trace(
                metric_id=metric_id, company_id=company_id, period_start=target["period_start"],
                period_end=target["period_end"], scope=scope, spec_closure_hash=spec["spec_closure_hash"],
                applicability="N_A_STRUCTURAL", quality="NONE", reason_code="TRAIT_NOT_APPLICABLE",
                input_observation_ids=[], steps=[{"event": "N_A_STRUCTURAL"}], accession=None,
                entity=None, unit=None)
        else:
            try:
                requires_prior = any(c["accession_role"] == "prior" for b in route["branches"]
                                     for c in b["components"])
                _need(not requires_prior or prior_error is None,
                      (prior_error or {}).get("reason"))
                graph = _deterministic_metric_graph(context=context, company_id=company_id,
                                                    metric_id=metric_id)
                result, trace = graph["result"], graph["trace"]
            except (*_SOURCE_ERRORS, NormalCompanyfactsError, DecimalException) as error:
                detail = {"reason": str(error), "error_type": type(error).__name__,
                          "category": "SOURCE_OR_IMPLEMENTATION_UNRESOLVED"}
                graph = {"claims": [], "projection_claims": [], "observation": None}
                result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                                       reason_code="HISTORICAL_COMPANYFACTS_ROUTE_UNRESOLVED")
        observations = [graph["observation"]] if graph["observation"] else []
        results[metric_id] = {"metric_id": metric_id, "compiled_spec": spec, "target": target,
                              "selection": detail, "claims": graph["claims"],
                              "projection_claims": graph["projection_claims"],
                              "observations": observations, "result": result, "trace": trace,
                              "records": [*observations, trace, result]}
    proofs = list({content_hash(value=p): p for p in
                   [*prepared["source_proofs"], *[s["proof"] for s in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    body = {"record_type": RESULT_RECORD_TYPE, "company_id": company_id,
            "period_selection": period_selection,
            "prepared_input": prepared, "filings": filings, "periods": periods,
            "prior_error": prior_error, "authority_file_hashes": authority,
            "source_records": list(reader.records.values()), "amendment_input": None,
            "instant_amendment_input": None, "source_proofs": proofs,
            "source_admission": admission, "source_sets": [s["manifest"] for s in sources],
            "claims_by_accession_role": claims_by_role,
            "failed_source_attempts": list(reader.failed_attempts.values()), "metrics": results,
            "resolver_sha256": sha256_file(path=Path(__file__)),
            "catalog_path": CATALOG_PATH,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "current_latest_verified": False,
            "latest_restated_values_used": False, "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "component_id": content_hash(value=body)}


def verify_historical_companyfacts_metrics(*, candidate, repo_root: Path, company_id: str,
                                           period_selection):
    rebuilt = resolve_historical_companyfacts_metrics(repo_root=repo_root, company_id=company_id,
                                                      period_selection=period_selection)
    _need(candidate == rebuilt, "HISTORICAL_COMPANYFACTS_SOURCE_REPLAY_CHANGED")
    return rebuilt


# A text metric does not live in the 22 zero-AI Spec set, and its result is not
# computed here: the review decision binds the Requirement, which only the Run
# factory holds. So this assembles the identity and the sources, and
# create_historical_run computes the text result from them, exactly as the
# current route splits the same work between normal_run_v2 and normal_run_v3.
TEXT_METRICS = ("D02",)
# v2 declares max_items 192 where v1 declares 64. 64 was two bounds wearing one
# number: what a Spec may declare, which historical_spec_revision raises without
# touching the frozen compiler, and what ORDERED_NEWLINE_V1 will render, which
# historical_text_protocol carries for this generation. Both are wired, so the
# route can declare the capacity the runtime actually honours. v1 keeps its
# bytes and its identity, because the Runs frozen under it declare it.
TEXT_SPEC_PATHS = {"D02": "catalog/r6/D02_legal_disclosures_v2.md"}


def _historical_text_run_input(*, repo_root, company_id, metric_id, period_selection):
    """Assemble the text case's identity without its raw bytes.

    ``text_arguments`` carries the filing's bytes, which cannot enter a binding
    that has to be JSON and content-addressed. The binding therefore records
    which sources were admitted, and the Run factory re-prepares the same input
    from the data root to obtain the bytes again.
    """
    from .historical_text_input import prepare_historical_business_text_input
    prepared = prepare_historical_business_text_input(
        repo_root=repo_root, company_id=company_id, metric_id=metric_id,
        period_selection=period_selection)
    _need(prepared["input_status"] != "BLOCKED",
          "HISTORICAL_TEXT_RUN_INPUT_BLOCKED:" + str(prepared["input_binding"]["limitations"]))
    spec_path = TEXT_SPEC_PATHS[metric_id]
    spec = compile_historical_spec_file(repo_root=repo_root, repo_relative_path=spec_path,
                                        dependency_specs={})
    period = prepared["target_period"]
    body = {"record_type": RUN_INPUT_RECORD_TYPE, "company_id": company_id,
            "primary_metric_id": metric_id, "period_selection": period_selection,
            "requested_metric_ids": [metric_id], "required_metric_ids": [metric_id],
            "spec_paths": {metric_id: spec_path}, "compiled_specs": {metric_id: spec},
            "records": prepared["records"], "source_records": prepared["records"],
            "source_references": prepared["source_references"],
            "source_proofs": prepared["source_proofs"],
            "source_admission": prepared["admission"],
            "primary_result": None, "results": {}, "traces": {},
            "target_period": {"fiscal_year": period["fiscal_year"],
                              "period_start": period["period_start"],
                              "period_end": period["period_end"]},
            "component": prepared["input_binding"], "kind": "TEXT",
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_id": content_hash(value=body)}


def prepare_historical_run_input(*, repo_root: Path, company_id: str, metric_id: str,
                                 period_selection):
    """Assemble one metric's complete historical graph for a Run factory.

    The installed Spec set, dependency closure and record-collision rules are
    the frozen current ones. Only the period is explicit.
    """
    from .historical_accession_results import resolve_historical_accession_metrics
    # Revenue and the 8-K event windows share one adapter, as they do in the
    # current route, so this follows that module's own supported set.
    from .historical_zero_ai_results import (SUPPORTED_METRICS as ZERO_AI_METRICS,
                                             resolve_historical_zero_ai_metric)
    ACCESSION_METRICS = ("A01", "A02", "B12")
    if metric_id in TEXT_METRICS:
        return _historical_text_run_input(repo_root=repo_root, company_id=company_id,
                                          metric_id=metric_id,
                                          period_selection=period_selection)
    specifications = validate_ordinary_spec_files(repo_root=repo_root)
    _need(metric_id in specifications, "HISTORICAL_RUN_METRIC_NOT_IN_ZERO_AI_SET")
    expected_ids = {metric_id, *specifications[metric_id]["compiled_spec"]["compiled"]["dependencies"]}
    if metric_id in ZERO_AI_METRICS:
        component = resolve_historical_zero_ai_metric(repo_root=repo_root, company_id=company_id,
                                                      metric_id=metric_id,
                                                      period_selection=period_selection)
        specs = {metric_id: component["compiled_spec"], **component["dependency_specs"]}
        source_records = component["source_records"]
        records = [*component["records"], *component["claims"]]
    elif metric_id in ACCESSION_METRICS:
        _need(expected_ids == {metric_id}, "HISTORICAL_RUN_DEPENDENT_METRIC_NOT_IMPLEMENTED")
        component = resolve_historical_accession_metrics(repo_root=repo_root,
                                                         company_id=company_id,
                                                         period_selection=period_selection)
        metric = component["metrics"][metric_id]
        specs = {metric_id: metric["compiled_spec"]}
        source_records = component["source_records"]
        records = [*source_records, *metric["claims"], *metric["records"]]
    else:
        _need(expected_ids == {metric_id}, "HISTORICAL_RUN_DEPENDENT_METRIC_NOT_IMPLEMENTED")
        component = resolve_historical_companyfacts_metrics(repo_root=repo_root,
                                                            company_id=company_id,
                                                            period_selection=period_selection)
        _need(metric_id in component["metrics"], "HISTORICAL_RUN_METRIC_NOT_IN_COMPANYFACTS_ROUTE")
        metric = component["metrics"][metric_id]
        specs = {metric_id: metric["compiled_spec"]}
        source_records = component["source_records"]
        records = [*source_records, *metric["claims"], *metric["records"]]
    unique = {}
    for record in records:
        key = content_hash(value=record)
        _need(key not in unique or unique[key] == record,
              "HISTORICAL_RUN_RECORD_HASH_COLLISION_WITH_DIFFERENT_BYTES")
        unique.setdefault(key, record)
    records = list(unique.values())
    results = {r["metric_id"]: r for r in records if r["record_type"] == "METRIC_RESULT"}
    traces = {r["metric_id"]: r for r in records if r["record_type"] == "EXECUTION_TRACE"}
    _need(sum(r["record_type"] == "METRIC_RESULT" for r in records) == len(results)
          and sum(r["record_type"] == "EXECUTION_TRACE" for r in records) == len(traces),
          "HISTORICAL_RUN_DUPLICATE_RESULT_OR_TRACE")
    _need(set(results) == set(traces) == expected_ids,
          "HISTORICAL_RUN_RESULT_DEPENDENCY_SET_INCOMPLETE")
    for metric_key, result in results.items():
        _need(result["trace_id"] == traces[metric_key]["trace_id"]
              and result["spec_closure_hash"] == specs[metric_key]["spec_closure_hash"],
              "HISTORICAL_RUN_RESULT_TRACE_OR_SPEC_CHANGED")
    for metric_key, spec in specs.items():
        _need(spec == specifications[metric_key]["compiled_spec"],
              "HISTORICAL_RUN_INSTALLED_SPEC_DIFFERS_FROM_SOURCE_ROUTE:" + metric_key)
    _need(set(specs) == expected_ids, "HISTORICAL_RUN_DEPENDENCY_SPEC_SET_CHANGED")
    primary = results[metric_id]
    period = component["prepared_input"]["table_input"]["target_period"]
    body = {"record_type": RUN_INPUT_RECORD_TYPE, "company_id": company_id,
            "primary_metric_id": metric_id, "period_selection": period_selection,
            "requested_metric_ids": [metric_id], "required_metric_ids": sorted(expected_ids),
            "spec_paths": {m: specifications[m]["path"] for m in sorted(expected_ids)},
            "compiled_specs": specs, "records": records, "source_records": source_records,
            "source_references": [r for r in source_records if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": component["source_proofs"],
            "source_admission": component["source_admission"],
            "primary_result": primary, "results": results, "traces": traces,
            "target_period": {"fiscal_year": period["fiscal_year"],
                              "period_start": primary["period_start"],
                              "period_end": primary["period_end"]},
            "component": component, "kind": "STRUCTURED",
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_id": content_hash(value=body)}
