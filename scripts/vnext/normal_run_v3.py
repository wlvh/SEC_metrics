"""Ordinary integrated Runs with exact dependencies and source fiscal labels.

This successor reuses the existing Run/Review/Calculator machinery. The old
V13 source routes and frozen rules stay unchanged; new creation uses its own
Requirement and installs exact source-owned Spec files before any Run exists.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .normal_run_inputs import prepare_ordinary_zero_ai_run_input
from .normal_run_specs import installed_ordinary_spec_documents
from .requirements import load_requirement_snapshot
from .sources import resolve_repository_file
from .traits import repository_company_traits


REQUIREMENT_ID = "issue_28_v13"
PREFIX = "run:ordinary-integrated:"
POLICY_PATH = "config/issue28_normal_results_v2.json"
BINDING_DIRECTORY = "ordinary_integrated_bindings"


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _external(path):
    from .b06_new_source import _external as check
    return check(Path(path))


def _write(path, content):
    from sec_http import write_immutable_bytes
    write_immutable_bytes(path=path,content=content)


def _bytes(value):
    return (json.dumps(exact_json_value(value),ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")


def _policy(root):
    value = strict_json_file(path=resolve_repository_file(repo_root=root,repo_relative_path=POLICY_PATH))
    _need(value == strict_json_file(path=ROOT/POLICY_PATH),"ORDINARY_INTEGRATED_INSTALLED_POLICY_CHANGED")
    return value


def prepare_case(*, data_root, company_id, metric_id):
    policy = _policy(data_root)
    _need(metric_id in policy["metric_ids"],"ORDINARY_INTEGRATED_METRIC_NOT_ENABLED")
    if metric_id in installed_ordinary_spec_documents():
        original = prepare_ordinary_zero_ai_run_input(repo_root=data_root,company_id=company_id,metric_id=metric_id)
        case = {"kind":"STRUCTURED","primary_metric_id":metric_id,"input_binding":original,
            "source_records":original["source_records"],"references":original["source_references"],
            "source_proofs":original["source_proofs"],"admission":original["source_admission"],
            "spec_paths":original["spec_paths"],"compiled_specs":original["compiled_specs"],
            "target_period":original["target_period"],"expected_records":original["records"],
            "results":original["results"],"traces":original["traces"],
            "observations":[r for r in original["records"] if r["record_type"] == "VERIFIED_OBSERVATION"],
            "selection":original["component"].get("selection")}
    else:
        from .normal_run_v2 import _prepare_case
        old = _prepare_case(data_root=data_root,company_id=company_id,metric_id=metric_id)
        annual = prepare_saved_annual_input(repo_root=data_root,company_id=company_id)
        year = annual["table_input"]["target_period"]["fiscal_year"]
        if year != old["target_period"]["fiscal_year"]:
            _need(old["compiled_spec"]["compiled"]["quality_rule"].get("resolver") != "reported_compensation_table_v2",
                  "ORDINARY_SCT_SOURCE_YEAR_REPLAY_REQUIRED")
            if old["kind"] == "STRUCTURED":
                _need("fiscal_year" not in old["trace"]["calculation_target"]["scope"],
                      "ORDINARY_SOURCE_SCOPE_YEAR_REPLAY_REQUIRED")
        period = {**old["target_period"],"fiscal_year":year}
        source_records = [r for r in old["records"] if r["record_type"] in {"RAW_BLOB","SOURCE_REFERENCE"}]
        case = {"kind":old["kind"],"primary_metric_id":metric_id,
            "input_binding":{"original_source_route":old["input_binding"],"annual_label_input":annual},
            "source_records":source_records,"references":old["references"],
            "source_proofs":old["source_proofs"],"admission":old["admission"],
            "spec_paths":{metric_id:old["spec_path"]},"compiled_specs":{metric_id:old["compiled_spec"]},
            "target_period":period,"selection":old.get("selection")}
        if old["kind"] == "STRUCTURED":
            case.update(results={metric_id:old["result"]},traces={metric_id:old["trace"]},observations=old["observations"],
                expected_records=[*old["records"],*old.get("derived_assets",[]),*old["observations"],old["trace"],old["result"]])
        else:
            case.update(text_arguments=old["text_arguments"],expected_records=old["records"])
    _need(set(case["compiled_specs"]) == {metric_id,*case["compiled_specs"][metric_id]["compiled"]["dependencies"]},
          "ORDINARY_INTEGRATED_DEPENDENCY_SET_CHANGED")
    for metric,path in case["spec_paths"].items():
        _need(path in policy["metric_spec_paths"][metric],"ORDINARY_INTEGRATED_SPEC_ROUTE_NOT_ENABLED")
    return case


def _binding(case, requirement):
    return exact_json_value({"record_type":"ORDINARY_INTEGRATED_RUN_BINDING","kind":case["kind"],
        "primary_metric_id":case["primary_metric_id"],"input_binding":case["input_binding"],
        "source_admission":case["admission"],"spec_paths":case["spec_paths"],
        "spec_closure_hashes":{key:value["spec_closure_hash"] for key,value in case["compiled_specs"].items()},
        "target_period":case["target_period"],"requirement_closure_hash":requirement["requirement_closure_hash"],
        "production_authorized":False})


def install_normal_inputs(*, data_root, company_id, metric_id):
    data_root = _external(data_root)
    case = prepare_case(data_root=ROOT,company_id=company_id,metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/"requirements"/REQUIREMENT_ID)
    verify_saved_source_proofs(data_root=ROOT,proofs=case["source_proofs"])
    from .annual_runtime import _authority_files
    from .annual_continuity_sources import frozen_foundation_receipts
    paths = set(_authority_files(requirement))
    cursor = requirement
    while cursor:
        paths.update(cursor.get("execution_authority",{}).get("files",{}))
        paths.update(cursor.get("baseline",{}).get("new_rule_files",{}))
        cursor = cursor.get("parent_snapshot")
    paths.update(str(p.relative_to(ROOT)) for p in (ROOT/"requirements").rglob("*") if p.is_file())
    parent_index = strict_json_file(path=ROOT/"docs/evidence/issue28_continuous/frozen-parent-v10-index.json")
    paths.update("docs/evidence/issue28_continuous/frozen-parent-v10/"+p for p in parent_index["files"])
    paths.update(["config/company_registry.csv","evidence/requests_log.csv","evidence/requests_log_manifest.json"])
    for proof in case["source_proofs"]:
        paths.update([proof["request_repo_relative_path"],proof["request_headers_repo_relative_path"]])
    # Event completeness also compares the authenticated acquisition census.
    # Header bytes used by that census are bound original inputs, not answers.
    if case["primary_metric_id"] in {"C01","E01","E02","E03","E04","E05"}:
        from .normal_annual_input import _registry_rows
        cik = next(c["primary_cik"] for c in _registry_rows(repo_root=ROOT) if c["company_id"] == company_id)
        for directory in (ROOT/"evidence/accession_materials").iterdir():
            fields = directory.name.rsplit("_",2)
            if directory.is_dir() and len(fields)==3 and fields[1].isdigit() and int(fields[1])==int(cik):
                paths.update(str(p.relative_to(ROOT)) for p in directory.glob("*.hdr.sgml"))
    receipts = frozen_foundation_receipts()
    for relative in sorted(paths):
        source = resolve_repository_file(repo_root=ROOT,repo_relative_path=relative)
        _write(data_root/relative,receipts[relative]["bytes"] if relative in receipts else source.read_bytes())
    rebuilt = prepare_case(data_root=data_root,company_id=company_id,metric_id=metric_id)
    _need(_binding(rebuilt,requirement) == _binding(case,requirement),"ORDINARY_INTEGRATED_IMPORTED_INPUT_CHANGED")
    return rebuilt


def text_api(metric_id):
    from .normal_run_v2 import text_api as select
    return select(metric_id)


def create_normal_run(*, data_root, run_dir, company_id, metric_id, freeze=False):
    from .run_store import (create_run,append_run_record,append_review_decision,write_review_assets,
        validate_and_freeze_run,load_frozen_run,_mechanically_replay_open_run)
    data_root,run_dir = _external(data_root),_external(run_dir)
    _need(not run_dir.exists(),"ORDINARY_INTEGRATED_RUN_PATH_EXISTS")
    _need(not freeze or _policy(data_root)["freeze_enabled"],"ORDINARY_INTEGRATED_DRAFT_FREEZE_DISABLED")
    case = prepare_case(data_root=data_root,company_id=company_id,metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=data_root/"requirements"/REQUIREMENT_ID)
    binding = _binding(case,requirement);key = content_hash(value=binding)[7:]
    _write(data_root/BINDING_DIRECTORY/(key+".json"),_bytes(binding))
    traits = repository_company_traits(repo_root=data_root,company_id=company_id)
    decision,unit,assets = None,None,None
    terminal_records = []
    if case["kind"] == "TEXT":
        api,review_builder = text_api(metric_id)
        spec = case["compiled_specs"][metric_id]
        candidate = api.create_deterministic_text_candidate(**case["text_arguments"])
        evidence = api.build_text_evidence(candidate=candidate,**case["text_arguments"])
        unit,assets = review_builder(compiled_spec=spec,candidate=candidate,evidence_check=evidence,
                                    source_bindings=case["text_arguments"]["source_references"])
        from .review import create_system_review_decision
        decision = create_system_review_decision(review_unit=unit,required_claims=spec["compiled"]["required_claims"],
            decided_at_utc=datetime.now(timezone.utc).isoformat(),requirement=requirement)
        result,trace,observations = api.replay_text_result(company_traits=traits,candidate=candidate,evidence_check=evidence,
            review_unit=unit,review_decisions=[decision],**case["text_arguments"])
        records = [*case["expected_records"],candidate,evidence,unit]
        terminal_records = [*observations,trace,result]
    else:
        records = case["expected_records"];result = case["results"][metric_id]
    create_run(run_dir=run_dir,run_id=PREFIX+key,company_id=company_id,company_traits=traits,
        target_period=case["target_period"],source_references=case["references"],missing_required_source_roles=[],
        spec_file_hashes={p:sha256_file(path=data_root/p) for p in case["spec_paths"].values()},
        requirement_hashes=requirement["hashes"],requirement_id=REQUIREMENT_ID,
        requirement_closure_hash=requirement["requirement_closure_hash"],artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1")
    seen = {}
    for record in records:
        identity = content_hash(value=record)
        _need(identity not in seen or seen[identity] == record,"ORDINARY_INTEGRATED_RECORD_COLLISION")
        if identity not in seen:
            append_run_record(run_dir=run_dir,record=record);seen[identity] = record
    if decision:
        write_review_assets(run_dir=run_dir,review_unit=unit,review_context_bytes=assets["review_context_bytes"],
                            rendered_review_bytes=assets["rendered_review_bytes"])
        append_review_decision(run_dir=run_dir,decision=decision)
    for record in terminal_records:
        append_run_record(run_dir=run_dir,record=record)
    if freeze:
        validate_and_freeze_run(run_dir=run_dir,repo_root=data_root)
        manifest,stored,_ = load_frozen_run(run_dir=run_dir,repo_root=data_root)
    else:
        manifest,stored,_ = _mechanically_replay_open_run(run_dir=run_dir,repo_root=data_root,require_complete_results=True)
    _need(result in stored,"ORDINARY_INTEGRATED_RESULT_CHANGED")
    return {"manifest":manifest,"result":result,"input_binding":binding,"selection":case.get("selection"),
            "new_calls":{"provider":0,"paid":0,"sec":0},"production_authorized":False}


def replay_case(*, data_root, manifest, spec=None):
    _need(manifest["requirement_id"] == REQUIREMENT_ID and manifest["run_id"].startswith(PREFIX),
          "ORDINARY_INTEGRATED_RUN_IDENTITY_REQUIRED")
    key = manifest["run_id"][len(PREFIX):]
    saved = strict_json_file(path=resolve_repository_file(repo_root=data_root,repo_relative_path=BINDING_DIRECTORY+"/"+key+".json"))
    metric_id = saved["primary_metric_id"]
    case = prepare_case(data_root=data_root,company_id=manifest["company_id"],metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=data_root/"requirements"/REQUIREMENT_ID)
    expected = _binding(case,requirement)
    _need(saved == expected and content_hash(value=expected)[7:] == key,"ORDINARY_INTEGRATED_INPUT_BINDING_CHANGED")
    _need(manifest["target_period"] == case["target_period"] and manifest["source_references"] == case["references"]
          and manifest["requirement_closure_hash"] == requirement["requirement_closure_hash"]
          and manifest["spec_file_hashes"] == {p:sha256_file(path=data_root/p) for p in case["spec_paths"].values()},
          "ORDINARY_INTEGRATED_SOURCE_SPEC_OR_PERIOD_CHANGED")
    if spec is not None:
        _need(case["compiled_specs"].get(spec["compiled"]["metric_id"]) == spec,"ORDINARY_INTEGRATED_SPEC_NOT_IN_GRAPH")
    return case


def validate_normal_run_authority(*, repo_root, manifest, records, compiled_specs):
    case = replay_case(data_root=repo_root,manifest=manifest)
    _need(compiled_specs == case["compiled_specs"],"ORDINARY_INTEGRATED_EXACT_SPEC_SET_REQUIRED")
    source_records = [r for r in records if r["record_type"] in {"RAW_BLOB","SOURCE_REFERENCE"}]
    _need(sorted(source_records,key=lambda r:content_hash(value=r)) == sorted(case["source_records"],key=lambda r:content_hash(value=r)),
          "ORDINARY_INTEGRATED_SOURCE_RECORD_SET_CHANGED")
    if case["kind"] == "STRUCTURED":
        kinds = {"DETERMINISTIC_VERIFIED_CLAIM","VERIFIED_OBSERVATION","EXECUTION_TRACE","METRIC_RESULT"}
        expected = {content_hash(value=r):r for r in case["expected_records"] if r["record_type"] in kinds}
        actual = [r for r in records if r["record_type"] in kinds]
        _need(sorted(actual,key=lambda r:content_hash(value=r)) == [expected[k] for k in sorted(expected)],
              "ORDINARY_INTEGRATED_COMPLETE_COMPUTATION_GRAPH_CHANGED")
    return case


def prepare_text_contexts(*, repo_root, manifest, records, compiled_specs, **unused):
    candidates = [r for r in records if r["record_type"] == "DETERMINISTIC_TEXT_CANDIDATE"]
    if not candidates:
        return {}
    _need(len(candidates) == len(compiled_specs) == 1,"ORDINARY_INTEGRATED_TEXT_EXACT_SET_REQUIRED")
    spec = next(iter(compiled_specs.values()))
    case = replay_case(data_root=repo_root,manifest=manifest,spec=spec)
    _need(case["kind"] == "TEXT","ORDINARY_INTEGRATED_TEXT_ROUTE_REQUIRED")
    api,_ = text_api(spec["compiled"]["metric_id"])
    expected = api.create_deterministic_text_candidate(**case["text_arguments"])
    _need(candidates[0] == expected,"ORDINARY_INTEGRATED_TEXT_CANDIDATE_CHANGED")
    return {expected["candidate_hash"]:case["text_arguments"]}
