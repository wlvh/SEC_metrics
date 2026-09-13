"""Current ownership adapter for the twelve frozen ordinary source routes.

The old entrypoints and policies remain unchanged. This wrapper selects the
same business functions after current source admission; the existing V14 Run
builder still owns the complete graph, review and fiscal presentation.
"""
from .canonical import content_hash
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .normal_run_v2 import _policy,_need,TEXT_PATHS
from .sources import resolve_repository_file
from .specs import compile_spec_file


def _current_structured_preparation(*,data_root,company_id,metric_id):
    from .normal_candidates import _prepare_b06,_b06_resolution,_governance_resolution
    if metric_id=='B06':
        prepared=_prepare_b06(repo_root=data_root,company_id=company_id)
    else:
        from .normal_governance_input import prepare_saved_governance_input
        prepared=prepare_saved_governance_input(repo_root=data_root,company_id=company_id)
    proofs=[*prepared['input_binding']['source_proofs'],*prepared['input_binding']['prepared_annual_input']['source_proofs']]
    admission=verify_ordinary_source_proofs(data_root=data_root,proofs=proofs)
    if metric_id=='B06':path,resolution=_b06_resolution(data_root=data_root,preparation=prepared)
    else:path,resolution=_governance_resolution(data_root=data_root,preparation=prepared,metric_id=metric_id)
    _need(admission==verify_ordinary_source_proofs(data_root=data_root,proofs=proofs),'ORDINARY_CURRENT_SOURCE_CHANGED_DURING_RESOLUTION')
    return prepared,path,resolution,admission


def prepare_current_source_case(*, data_root, company_id, metric_id):
    """Pure discovery and source reconstruction; no caller-owned business facts."""
    policy = _policy(data_root)
    _need(metric_id in policy["metric_ids"], "NORMAL_CURRENT_METRIC_NOT_ENABLED")
    _need(metric_id not in policy.get("temporarily_blocked_metrics", []),
          "NORMAL_CURRENT_SOURCE_REPAIR_PENDING")
    if metric_id in {"C02", "D02"}:
        from .ordinary_text_input import prepare_current_business_text_input
        prepared = prepare_current_business_text_input(repo_root=data_root, company_id=company_id, metric_id=metric_id)
        _need(prepared["input_status"] != "BLOCKED", "NORMAL_CURRENT_TEXT_INPUT_BLOCKED:" + str(prepared["input_binding"]["limitations"]))
        case = {"kind": "TEXT", "input_binding": prepared["input_binding"],
                "records": prepared["records"], "references": prepared["source_references"],
                "source_proofs": prepared["source_proofs"], "admission": prepared["admission"],
                "target_period": prepared["prepared_input"]["table_input"]["target_period"],
                "target": prepared["text_arguments"]["target"], "text_arguments": prepared["text_arguments"],
                "spec_path": TEXT_PATHS[metric_id]}
    elif metric_id == "D01":
        from .ordinary_text_input import current_text_sources
        prepared, admission, records, references = current_text_sources(repo_root=data_root, company_id=company_id)
        blobs = {r["raw_asset_id"]: r for r in records if r["record_type"] == "RAW_BLOB"}
        raw = {key: resolve_repository_file(repo_root=data_root, repo_relative_path=r["storage_uri"]).read_bytes()
               for key, r in blobs.items()}
        scope = {"entity_scope": "registrant"}
        period = prepared["table_input"]["target_period"]
        target = {"company_id": company_id, "entity": prepared["entity"], "accession": prepared["filing"]["accessionNumber"],
                  "period_start": period["period_start"], "period_end": period["period_end"],
                  "scope": scope, "scope_key": content_hash(value=scope)}
        args = {"target": target, "source_references": [r for r in references if r["source_role"] == "target_primary"],
                "raw_blobs": blobs, "raw_bytes_by_id": raw}
        case = {"kind": "TEXT", "input_binding": prepared, "records": records,
                "references": references, "source_proofs": prepared["source_proofs"], "admission": admission,
                "target_period": period, "target": target, "text_arguments": args, "spec_path": TEXT_PATHS[metric_id]}
    elif metric_id in {"B06", "C03", "C04"}:
        guarded = None
        if metric_id == "B06":
            from .ordinary_debt_guard import prepare_current_guarded_b06_result
            guarded = prepare_current_guarded_b06_result(repo_root=data_root, company_id=company_id)
        if guarded is not None and guarded["status"] == "NOT_MEANINGFUL":
            original = guarded["input_binding"]
            annual = guarded["filing_period"]
            case = {"kind": "STRUCTURED", "input_binding": {"guarded_result": guarded},
                "records": guarded["source_records"], "references": guarded["source_references"],
                "source_proofs": [*original["source_proofs"], *original["prepared_annual_input"]["source_proofs"]],
                "admission": guarded["source_admission"], "spec_path": guarded["spec_path"],
                "result": guarded["result"], "trace": guarded["trace"], "observations": guarded["observations"],
                "derived_assets": [], "selection": {"reason_code": guarded["reason_code"],
                    "debt_completeness": "NOT_EVALUATED", "equity_proof": guarded["equity_proof"]},
                "target_period": {"fiscal_year": annual["fiscal_year"],
                    "period_start": guarded["target"]["period_start"], "period_end": guarded["target"]["period_end"]}}
        else:
            prepared, path, resolution, admission = _current_structured_preparation(data_root=data_root, company_id=company_id, metric_id=metric_id)
            result = resolution["result"]
            annual = prepared["input_binding"]["prepared_annual_input"]["table_input"]["target_period"]
            observations = resolution.get("observations", [resolution["observation"]] if resolution.get("observation") else [])
            case = {"kind": "STRUCTURED", "input_binding": prepared["input_binding"], "records": prepared["records"],
                    "references": [r for r in prepared["records"] if r["record_type"] == "SOURCE_REFERENCE"],
                    "source_proofs": [*prepared["input_binding"]["source_proofs"], *prepared["input_binding"]["prepared_annual_input"]["source_proofs"]],
                    "admission": admission, "spec_path": path, "result": result, "trace": resolution["trace"],
                    "observations": observations, "derived_assets": resolution.get("derived_assets", []),
                    "selection": resolution["selection"],
                    "target_period": {"fiscal_year": annual["fiscal_year"], "period_start": result["period_start"], "period_end": result["period_end"]}}
            if guarded is not None:
                case["input_binding"] = {"denominator_guard": guarded, "debt_input": case["input_binding"]}
    else:
        from .ordinary_financial_results import resolve_current_financial_metric
        result = resolve_current_financial_metric(repo_root=data_root, company_id=company_id, metric_id=metric_id)
        case = {"kind": "STRUCTURED", "input_binding": result["input_binding"], "records": result["source_records"],
                "references": [r for r in result["source_records"] if r["record_type"] == "SOURCE_REFERENCE"],
                "source_proofs": result["source_proofs"], "admission": result["source_admission"],
                "spec_path": result["spec_path"], "target_period": result["target_period"],
                "result": result["result"], "trace": result["trace"], "observations": result["observations"],
                "derived_assets": [], "selection": {**result["selection"], "source_fact": result["source_fact"]}}
    path = case["spec_path"]
    _need(path in policy["metric_spec_paths"][metric_id], "NORMAL_CURRENT_SPEC_ROUTE_NOT_ENABLED")
    spec = compile_spec_file(path=resolve_repository_file(repo_root=data_root, repo_relative_path=path), dependency_specs={})
    _need(spec == compile_spec_file(path=ROOT / path, dependency_specs={}), "NORMAL_CURRENT_SPEC_DIFFERS_FROM_INSTALLED")
    case["compiled_spec"] = spec
    if case["kind"] == "TEXT":
        case["text_arguments"] = {"compiled_spec": spec, **case["text_arguments"]}
    return case
