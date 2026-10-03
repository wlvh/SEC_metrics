"""Ordinary successor candidates on the existing Run, review and replay chain."""
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file, strict_json_loads
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .requirements import load_requirement_snapshot
from .run_store import (create_run, append_run_record, append_review_decision,
                        write_review_assets, validate_and_freeze_run, load_frozen_run,
                        _mechanically_replay_open_run)
from .sources import resolve_repository_file
from .specs import compile_spec_file
from .traits import repository_company_traits


REQUIREMENT_ID = "issue_28_v12"
PREFIX = "run:normal-current:"
POLICY_PATH = "config/issue28_normal_results_v1.json"
TEXT_PATHS = {"D01": "catalog/r6/D01_risk_factor_headings.md",
              "C02": "catalog/r6/C02_board_disclosures_v1.md",
              "D02": "catalog/r6/D02_legal_disclosures_v1.md"}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _write(path, raw):
    from sec_http import write_immutable_bytes
    write_immutable_bytes(path=path, content=raw)


def _external(path):
    from .b06_new_source import _external as checked
    return checked(Path(path))


def _policy(root):
    value = strict_json_file(path=resolve_repository_file(repo_root=root, repo_relative_path=POLICY_PATH))
    _need(value == strict_json_file(path=ROOT / POLICY_PATH), "NORMAL_CURRENT_INSTALLED_POLICY_CHANGED")
    return value


def _prepare_case(*, data_root, company_id, metric_id):
    """Pure discovery and source reconstruction; no caller-owned business facts."""
    policy = _policy(data_root)
    _need(metric_id in policy["metric_ids"], "NORMAL_CURRENT_METRIC_NOT_ENABLED")
    _need(metric_id not in policy.get("temporarily_blocked_metrics", []),
          "NORMAL_CURRENT_SOURCE_REPAIR_PENDING")
    if metric_id in {"C02", "D02"}:
        from .normal_text_input_v2 import prepare_normal_business_text_input
        prepared = prepare_normal_business_text_input(repo_root=data_root, company_id=company_id, metric_id=metric_id)
        _need(prepared["input_status"] != "BLOCKED", "NORMAL_CURRENT_TEXT_INPUT_BLOCKED:" + str(prepared["input_binding"]["limitations"]))
        case = {"kind": "TEXT", "input_binding": prepared["input_binding"],
                "records": prepared["records"], "references": prepared["source_references"],
                "source_proofs": prepared["source_proofs"], "admission": prepared["admission"],
                "target_period": prepared["prepared_input"]["table_input"]["target_period"],
                "target": prepared["text_arguments"]["target"], "text_arguments": prepared["text_arguments"],
                "spec_path": TEXT_PATHS[metric_id]}
    elif metric_id == "D01":
        from .text_run_validation import normal_text_sources
        prepared, admission, records, references = normal_text_sources(repo_root=data_root, company_id=company_id)
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
            from .b06_guarded_result_v3 import prepare_guarded_b06_result
            guarded = prepare_guarded_b06_result(repo_root=data_root, company_id=company_id)
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
            from .normal_candidates import _structured_preparation
            prepared, path, resolution, admission = _structured_preparation(data_root=data_root, company_id=company_id, metric_id=metric_id)
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
        from .financial_results import resolve_ordinary_financial_metric
        result = resolve_ordinary_financial_metric(repo_root=data_root, company_id=company_id, metric_id=metric_id)
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


def _binding(case, requirement):
    body = {"record_type": "NORMAL_SUCCESSOR_CANDIDATE_BINDING", "kind": case["kind"],
        "metric_id": case["compiled_spec"]["compiled"]["metric_id"], "input_binding": case["input_binding"],
        "source_admission": case["admission"], "spec_path": case["spec_path"],
        "spec_closure_hash": case["compiled_spec"]["spec_closure_hash"], "target_period": case["target_period"],
        "requirement_closure_hash": requirement["requirement_closure_hash"], "production_authorized": False}
    return strict_json_loads(text=canonical_json_bytes(value=body).decode("utf-8"))


def install_normal_inputs(*, data_root, company_id, metric_id):
    """Copy the current installed authority and original admitted input bytes."""
    data_root = _external(data_root)
    case = _prepare_case(data_root=ROOT, company_id=company_id, metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=ROOT / "requirements" / REQUIREMENT_ID)
    verify_saved_source_proofs(data_root=ROOT, proofs=case["source_proofs"])
    from .annual_runtime import _authority_files
    from .annual_continuity_sources import frozen_foundation_receipts
    paths = set(_authority_files(requirement))
    cursor = requirement
    while cursor:
        paths.update(cursor.get("execution_authority", {}).get("files", {}))
        paths.update(cursor.get("baseline", {}).get("new_rule_files", {}))
        cursor = cursor.get("parent_snapshot")
    paths.update(str(p.relative_to(ROOT)) for p in (ROOT / "requirements").rglob("*") if p.is_file())
    parent_index = strict_json_file(path=ROOT / "docs/evidence/issue28_continuous/frozen-parent-v10-index.json")
    paths.update("docs/evidence/issue28_continuous/frozen-parent-v10/" + p for p in parent_index["files"])
    paths.update(["config/company_registry.csv", "evidence/requests_log.csv", "evidence/requests_log_manifest.json"])
    for proof in case["source_proofs"]:
        paths.update([proof["request_repo_relative_path"], proof["request_headers_repo_relative_path"]])
    receipts = frozen_foundation_receipts()
    for relative in sorted(paths):
        source = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative)
        _write(data_root / relative, receipts[relative]["bytes"] if relative in receipts else source.read_bytes())
    rebuilt = _prepare_case(data_root=data_root, company_id=company_id, metric_id=metric_id)
    _need(_binding(rebuilt, requirement) == _binding(case, requirement), "NORMAL_CURRENT_IMPORTED_INPUT_DIFFERS")
    return rebuilt


def text_api(metric_id):
    if metric_id == "D01":
        from . import text_results
        from .text_review import build_text_review_unit
        return text_results, build_text_review_unit
    from . import text_results_v2
    return text_results_v2, text_results_v2.build_text_review_unit


def create_normal_run(*, data_root, run_dir, company_id, metric_id, freeze=False):
    data_root, run_dir = _external(data_root), _external(run_dir)
    _need(not run_dir.exists(), "NORMAL_CURRENT_RUN_PATH_ALREADY_EXISTS")
    case = _prepare_case(data_root=data_root, company_id=company_id, metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=data_root / "requirements" / REQUIREMENT_ID)
    binding = _binding(case, requirement)
    key = content_hash(value=binding)[7:]
    _write(data_root / "normal_current_bindings" / (key + ".json"), canonical_json_bytes(value=binding))
    traits = repository_company_traits(repo_root=data_root, company_id=company_id)
    extra, assets, decision = [], None, None
    if case["kind"] == "TEXT":
        api, review_builder = text_api(metric_id)
        candidate = api.create_deterministic_text_candidate(**case["text_arguments"])
        evidence = api.build_text_evidence(candidate=candidate, **case["text_arguments"])
        unit, assets = review_builder(compiled_spec=case["compiled_spec"], candidate=candidate,
            evidence_check=evidence, source_bindings=case["text_arguments"]["source_references"])
        from .review import create_system_review_decision
        decision = create_system_review_decision(review_unit=unit,
            required_claims=case["compiled_spec"]["compiled"]["required_claims"],
            decided_at_utc=datetime.now(timezone.utc).isoformat(), requirement=requirement)
        result, trace, observations = api.replay_text_result(company_traits=traits, candidate=candidate,
            evidence_check=evidence, review_unit=unit, review_decisions=[decision], **case["text_arguments"])
        extra = [candidate, evidence, unit]
    else:
        result, trace, observations = case["result"], case["trace"], case["observations"]
        extra = case["derived_assets"]
    create_run(run_dir=run_dir, run_id=PREFIX + key, company_id=company_id, company_traits=traits,
        target_period=case["target_period"], source_references=case["references"], missing_required_source_roles=[],
        spec_file_hashes={case["spec_path"]: sha256_file(path=data_root / case["spec_path"])},
        requirement_hashes=requirement["hashes"], requirement_id=REQUIREMENT_ID,
        requirement_closure_hash=requirement["requirement_closure_hash"],
        artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1")
    for record in [*case["records"], *extra]:
        append_run_record(run_dir=run_dir, record=record)
    if decision:
        write_review_assets(run_dir=run_dir, review_unit=unit,
            review_context_bytes=assets["review_context_bytes"], rendered_review_bytes=assets["rendered_review_bytes"])
        append_review_decision(run_dir=run_dir, decision=decision)
    for record in [*observations, trace, result]:
        append_run_record(run_dir=run_dir, record=record)
    if freeze:
        validate_and_freeze_run(run_dir=run_dir, repo_root=data_root)
        manifest, stored, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
    else:
        manifest, stored, _ = _mechanically_replay_open_run(run_dir=run_dir, repo_root=data_root, require_complete_results=True)
    _need(result in stored, "NORMAL_CURRENT_RESULT_REPLAY_CHANGED")
    return {"manifest": manifest, "result": result, "input_binding": binding,
            "selection": case.get("selection"), "new_calls": {"provider": 0, "paid": 0, "sec": 0},
            "production_authorized": False}


def replay_case(*, data_root, manifest, spec):
    _need(manifest["requirement_id"] == REQUIREMENT_ID and manifest["run_id"].startswith(PREFIX),
          "NORMAL_CURRENT_RUN_IDENTITY_REQUIRED")
    policy = _policy(data_root)
    metric_id = spec["compiled"]["metric_id"]
    paths = policy["metric_spec_paths"].get(metric_id, [])
    _need(len(manifest["spec_file_hashes"]) == 1
          and next(iter(manifest["spec_file_hashes"])) in paths,
          "NORMAL_CURRENT_SPEC_ROUTE_NOT_ENABLED")
    requirement = load_requirement_snapshot(snapshot_dir=data_root / "requirements" / REQUIREMENT_ID)
    case = _prepare_case(data_root=data_root, company_id=manifest["company_id"], metric_id=spec["compiled"]["metric_id"])
    expected = _binding(case, requirement)
    key = content_hash(value=expected)[7:]
    _need(manifest["run_id"] == PREFIX + key and manifest["target_period"] == case["target_period"]
          and manifest["requirement_closure_hash"] == requirement["requirement_closure_hash"]
          and manifest["source_references"] == case["references"] and spec == case["compiled_spec"]
          and manifest["spec_file_hashes"] == {case["spec_path"]: sha256_file(path=data_root / case["spec_path"])},
          "NORMAL_CURRENT_SOURCE_SPEC_OR_TARGET_CHANGED")
    path = resolve_repository_file(repo_root=data_root, repo_relative_path="normal_current_bindings/" + key + ".json")
    _need(strict_json_file(path=path) == expected, "NORMAL_CURRENT_INPUT_BINDING_CHANGED")
    return case


def validate_normal_run_authority(*, repo_root, manifest, records, compiled_specs):
    """Require the ordinary input route before any caller-selected Spec branch."""
    _need(len(compiled_specs) == 1, "NORMAL_CURRENT_RUN_ONE_SPEC_REQUIRED")
    case = replay_case(data_root=repo_root, manifest=manifest,
                       spec=next(iter(compiled_specs.values())))
    source_types = {"SOURCE_REFERENCE", "RAW_BLOB"}
    actual_sources = [r for r in records if r["record_type"] in source_types]
    expected_sources = [r for r in case["records"] if r["record_type"] in source_types]
    _need(sorted(actual_sources, key=lambda r: content_hash(value=r))
          == sorted(expected_sources, key=lambda r: content_hash(value=r)),
          "NORMAL_CURRENT_SOURCE_RECORD_SET_CHANGED")
    return case


def prepare_text_contexts(*, repo_root, manifest, records, compiled_specs, **unused):
    candidates = [r for r in records if r["record_type"] == "DETERMINISTIC_TEXT_CANDIDATE"]
    if not candidates:
        return {}
    _need(len(candidates) == len(compiled_specs) == 1, "NORMAL_CURRENT_TEXT_RUN_EXACT_SET_REQUIRED")
    spec = next(iter(compiled_specs.values()))
    case = replay_case(data_root=repo_root, manifest=manifest, spec=spec)
    _need(case["kind"] == "TEXT" and all(r in records for r in case["records"]),
          "NORMAL_CURRENT_TEXT_SOURCE_RECORDS_CHANGED")
    api, _ = text_api(spec["compiled"]["metric_id"])
    expected = api.create_deterministic_text_candidate(**case["text_arguments"])
    _need(candidates[0] == expected, "NORMAL_CURRENT_TEXT_CANDIDATE_CHANGED")
    return {expected["candidate_hash"]: case["text_arguments"]}
