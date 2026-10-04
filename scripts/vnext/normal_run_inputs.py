"""Prepare exact ordinary zero-AI graphs for a shared Run successor.

This is input preparation only. A requested B03 includes its source-rebuilt
B01 dependency; no caller chooses a Spec, period, dependency or answer. Source
graphs and installed Specs are checked before a later Run factory may use them.
"""
from pathlib import Path

from .canonical import content_hash
from .normal_annual_input_v2 import exact_json_value
from .normal_run_specs import validate_ordinary_spec_files
from .normal_zero_ai_results import SUPPORTED_METRICS, EVENT_METRICS, resolve_ordinary_zero_ai_metric
from .normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
from .normal_accession_results import resolve_ordinary_accession_metrics


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def prepare_ordinary_zero_ai_run_input(*, repo_root: Path, company_id: str, metric_id: str):
    specifications = validate_ordinary_spec_files(repo_root=repo_root)
    _need(metric_id in specifications,"ORDINARY_RUN_METRIC_NOT_IN_ZERO_AI_SET")
    expected_ids = {metric_id, *specifications[metric_id]["compiled_spec"]["compiled"]["dependencies"]}
    if metric_id in SUPPORTED_METRICS:
        component = resolve_ordinary_zero_ai_metric(repo_root=repo_root,company_id=company_id,metric_id=metric_id)
        specs = {metric_id:component["compiled_spec"],**component["dependency_specs"]}
        records = list(component["records"])
        if metric_id in EVENT_METRICS:
            records.extend(component["claims"])
        source_records = component["source_records"]
        present_results = {r["metric_id"] for r in records if r["record_type"] == "METRIC_RESULT"}
        # An early source limitation may withhold B03 before the Calculator
        # evaluates revenue. Rebuild that declared dependency through its real
        # entry as well, so a complete Run never invents or omits its result.
        for dependency in sorted(expected_ids-present_results):
            value = resolve_ordinary_zero_ai_metric(repo_root=repo_root,company_id=company_id,metric_id=dependency)
            _need(value["source_records"] == source_records and value["source_proofs"] == component["source_proofs"],
                  "ORDINARY_RUN_DEPENDENCY_SOURCE_SET_DIFFERS")
            records.extend(value["records"])
    else:
        component = (resolve_ordinary_accession_metrics(repo_root=repo_root,company_id=company_id)
            if metric_id in {"A01","A02","B12"} else
            resolve_ordinary_companyfacts_metrics(repo_root=repo_root,company_id=company_id))
        metric = component["metrics"][metric_id]
        specs = {metric_id:metric["compiled_spec"]}
        source_records = component["source_records"]
        records = [*source_records,*metric["claims"],*metric["records"]]
    _need(set(specs) == expected_ids,"ORDINARY_RUN_DEPENDENCY_SPEC_SET_CHANGED")
    for metric,spec in specs.items():
        _need(spec == specifications[metric]["compiled_spec"],"ORDINARY_RUN_INSTALLED_SPEC_DIFFERS_FROM_SOURCE_ROUTE:"+metric)
    # Exact duplicate dependency observations may be shared. Equal canonical
    # hashes with different original strings are not silently deduplicated.
    unique = {}
    for record in records:
        key = content_hash(value=record)
        _need(key not in unique or unique[key] == record,"ORDINARY_RUN_RECORD_HASH_COLLISION_WITH_DIFFERENT_BYTES")
        unique.setdefault(key,record)
    records = list(unique.values())
    results = {r["metric_id"]:r for r in records if r["record_type"] == "METRIC_RESULT"}
    traces = {r["metric_id"]:r for r in records if r["record_type"] == "EXECUTION_TRACE"}
    _need(sum(r["record_type"] == "METRIC_RESULT" for r in records) == len(results)
          and sum(r["record_type"] == "EXECUTION_TRACE" for r in records) == len(traces),
          "ORDINARY_RUN_DUPLICATE_RESULT_OR_TRACE")
    _need(set(results) == set(traces) == expected_ids,"ORDINARY_RUN_RESULT_DEPENDENCY_SET_INCOMPLETE")
    for metric,result in results.items():
        _need(result["trace_id"] == traces[metric]["trace_id"] and result["spec_closure_hash"] == specs[metric]["spec_closure_hash"],
              "ORDINARY_RUN_RESULT_TRACE_OR_SPEC_CHANGED")
    primary = results[metric_id]
    period = component["prepared_input"]["table_input"]["target_period"]
    body = {"record_type":"ORDINARY_ZERO_AI_RUN_INPUT","company_id":company_id,"primary_metric_id":metric_id,
        "requested_metric_ids":[metric_id],"required_metric_ids":sorted(expected_ids),
        "spec_paths":{m:specifications[m]["path"] for m in sorted(expected_ids)},"compiled_specs":specs,
        "records":records,"source_records":source_records,
        "source_references":[r for r in source_records if r["record_type"] == "SOURCE_REFERENCE"],
        "source_proofs":component["source_proofs"],"source_admission":component["source_admission"],
        "primary_result":primary,"results":results,"traces":traces,
        "target_period":{"fiscal_year":period["fiscal_year"],"period_start":primary["period_start"],"period_end":primary["period_end"]},
        "component":component,"kind":"STRUCTURED","calls":{"provider":0,"paid":0,"sec":0},
        "native_run_status":"NOT_CREATED","production_authorized":False}
    body = exact_json_value(body)
    return {**body,"input_id":content_hash(value=body)}
