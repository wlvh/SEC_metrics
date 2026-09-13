"""Normal saved-input candidates on the existing native Run and review chain."""

from datetime import datetime, timezone
from pathlib import Path

from . import b06_new_source
from .canonical import canonical_json_bytes, content_hash, sha256_file
from .normal_annual_input import prepare_saved_annual_input
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .requirements import load_requirement_snapshot
from .review import create_system_review_decision
from .run_store import (append_review_decision, append_run_record, create_run,
                        load_frozen_run, validate_and_freeze_run, write_review_assets,
                        _mechanically_replay_open_run)
from .sources import resolve_repository_file
from .specs import compile_spec_file
from .text_results import build_text_evidence, create_deterministic_text_candidate, replay_text_result
from .text_review import build_text_review_unit
from .text_run_validation import normal_text_sources, normal_text_binding
from .traits import repository_company_traits


REQUIREMENT_ID = "issue_28_v11"
D01_SPEC_PATH = "catalog/r6/D01_risk_factor_headings.md"
PREFIX = "run:normal-saved:"


def _write_once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError("NORMAL_CANDIDATE_IMMUTABLE_INPUT_CHANGED:" + str(path))
    else:
        with path.open("xb") as handle:
            handle.write(raw)


def install_saved_candidate_inputs(*, data_root: Path, company_id: str, governance=False, b06=False):
    """Snapshot code-owned authority and already trusted source bytes externally."""
    data_root = b06_new_source._external(data_root)
    prepared = prepare_saved_annual_input(repo_root=ROOT, company_id=company_id)
    proofs = list(prepared["source_proofs"])
    if governance:
        from .normal_governance_input import prepare_saved_governance_input
        extra = prepare_saved_governance_input(repo_root=ROOT, company_id=company_id)
        proofs.extend(extra["input_binding"]["source_proofs"])
    if b06:
        extra = _prepare_b06(repo_root=ROOT, company_id=company_id)
        proofs.extend(extra["input_binding"]["source_proofs"])
    requirement = load_requirement_snapshot(snapshot_dir=ROOT / "requirements" / REQUIREMENT_ID)
    admission = verify_saved_source_proofs(data_root=ROOT, proofs=proofs)
    from .annual_runtime import _authority_files
    from .annual_continuity_sources import frozen_foundation_receipts
    from .canonical import strict_json_file
    paths = set(_authority_files(requirement)) | set(requirement["baseline"]["new_rule_files"])
    cursor = requirement
    while cursor:
        paths.update(cursor.get("execution_authority", {}).get("files", {}))
        cursor = cursor.get("parent_snapshot")
    paths.update(str(p.relative_to(ROOT)) for p in (ROOT / "requirements").rglob("*") if p.is_file())
    parent_index = strict_json_file(path=ROOT / requirement["policy"]["frozen_parent_index"])
    paths.update(requirement["policy"]["frozen_parent_root"] + "/" + p for p in parent_index["files"])
    paths.add(requirement["policy"]["frozen_parent_index"])
    receipts = frozen_foundation_receipts()
    paths.add("config/company_registry.csv")
    paths.update(["evidence/requests_log.csv", "evidence/requests_log_manifest.json"])
    for proof in proofs:
        paths.update([proof["request_repo_relative_path"], proof["request_headers_repo_relative_path"]])
    for relative in sorted(paths):
        source = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative)
        _write_once(data_root / relative, receipts[relative]["bytes"] if relative in receipts else source.read_bytes())
    # The fresh snapshot must independently prepare the same logical input.
    rebuilt = prepare_saved_annual_input(repo_root=data_root, company_id=company_id)
    if rebuilt != prepared:
        raise ValueError("NORMAL_CANDIDATE_INPUT_IMPORT_DIFFERS")
    return {"prepared_input": rebuilt, "admission": admission}


def _finish_run(*, data_root, run_dir, freeze):
    if freeze:
        validate_and_freeze_run(run_dir=run_dir, repo_root=data_root)
        return load_frozen_run(run_dir=run_dir, repo_root=data_root)
    return _mechanically_replay_open_run(run_dir=run_dir, repo_root=data_root,
                                        require_complete_results=True)


def create_risk_heading_run(*, data_root: Path, run_dir: Path, company_id: str, freeze=True):
    """Derive all Item 1A headings, review, freeze and cold-read a native Run."""
    data_root = b06_new_source._external(data_root)
    run_dir = b06_new_source._external(run_dir)
    prepared, admission, records, references = normal_text_sources(
        repo_root=data_root, company_id=company_id)
    spec = compile_spec_file(path=data_root / D01_SPEC_PATH, dependency_specs={})
    requirement = load_requirement_snapshot(snapshot_dir=data_root / "requirements" / REQUIREMENT_ID)
    if requirement["policy"]["native_deterministic_text_methods"] != ["RISK_FACTOR_HEADINGS_V1"]:
        raise ValueError("NORMAL_TEXT_POLICY_NOT_ENABLED")
    binding = normal_text_binding(prepared=prepared, admission=admission,
                                  spec=spec, requirement=requirement)
    key = content_hash(value=binding)[7:]
    run_id = PREFIX + key
    if run_dir.exists():
        manifest, stored, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
        if manifest["run_id"] != run_id:
            raise ValueError("NORMAL_CANDIDATE_REENTRY_INPUT_CHANGED")
        return {"manifest": manifest, "result": next(r for r in stored if r["record_type"] == "METRIC_RESULT"),
                "reused": True, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    _write_once(data_root / "normal_bindings" / (key + ".json"), canonical_json_bytes(value=binding))
    blobs = {r["raw_asset_id"]: r for r in records if r["record_type"] == "RAW_BLOB"}
    raw = {key: resolve_repository_file(repo_root=data_root,
                                      repo_relative_path=blob["storage_uri"]).read_bytes()
           for key, blob in blobs.items()}
    text_sources = [r for r in references if r["source_role"] == "target_primary"]
    scope = {"entity_scope": "registrant"}
    target = {"company_id": company_id, "entity": prepared["entity"],
        "accession": prepared["filing"]["accessionNumber"],
        "period_start": prepared["table_input"]["target_period"]["period_start"],
        "period_end": prepared["table_input"]["target_period"]["period_end"],
        "scope": scope, "scope_key": content_hash(value=scope)}
    args = {"compiled_spec": spec, "target": target, "source_references": text_sources,
            "raw_blobs": blobs, "raw_bytes_by_id": raw}
    candidate = create_deterministic_text_candidate(**args)
    evidence = build_text_evidence(candidate=candidate, **args)
    unit, assets = build_text_review_unit(compiled_spec=spec, candidate=candidate,
        evidence_check=evidence, source_bindings=text_sources)
    decision = create_system_review_decision(review_unit=unit, required_claims=scope,
        decided_at_utc=datetime.now(timezone.utc).isoformat(), requirement=requirement)
    traits = repository_company_traits(repo_root=data_root, company_id=company_id)
    result, trace, observations = replay_text_result(company_traits=traits,
        candidate=candidate, evidence_check=evidence, review_unit=unit,
        review_decisions=[decision], **args)
    create_run(run_dir=run_dir, run_id=run_id, company_id=company_id,
        company_traits=traits, target_period=prepared["table_input"]["target_period"],
        source_references=references, missing_required_source_roles=[],
        spec_file_hashes={D01_SPEC_PATH: sha256_file(path=data_root / D01_SPEC_PATH)},
        requirement_hashes=requirement["hashes"], requirement_id=REQUIREMENT_ID,
        requirement_closure_hash=requirement["requirement_closure_hash"],
        artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1")
    for record in [*records, candidate, evidence, unit]:
        append_run_record(run_dir=run_dir, record=record)
    write_review_assets(run_dir=run_dir, review_unit=unit,
        review_context_bytes=assets["review_context_bytes"],
        rendered_review_bytes=assets["rendered_review_bytes"])
    append_review_decision(run_dir=run_dir, decision=decision)
    for record in [*observations, trace, result]:
        append_run_record(run_dir=run_dir, record=record)
    manifest, stored, _ = _finish_run(data_root=data_root, run_dir=run_dir, freeze=freeze)
    if result not in stored:
        raise ValueError("NORMAL_TEXT_COLD_READ_RESULT_CHANGED")
    return {"manifest": manifest, "result": result, "reused": False,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "current_update_status": prepared["update_status"],
            "formal_publication_authorized": False}


def _governance_resolution(*, data_root, preparation, metric_id):
    from .calculator import withheld_metric_result
    from .governance_signals import resolve_c03, resolve_c04, C03_SPEC_PATH, C04_V2_SPEC_PATH
    from .governance_compensation_table import resolve_compensation_table, CompensationTableError
    binding, inputs = preparation["input_binding"], preparation["resolver_inputs"]
    scope = {"entity_scope": "registrant"}
    annual = binding["prepared_annual_input"]["table_input"]["target_period"]
    target = {"company_id": binding["company_id"], "period_start": annual["period_start"],
              "period_end": annual["period_end"], "scope": scope, "scope_key": content_hash(value=scope)}
    default_path = C03_SPEC_PATH if metric_id == "C03" else C04_V2_SPEC_PATH

    def blocked(reason, details):
        spec = compile_spec_file(path=data_root / default_path, dependency_specs={})
        result, trace = withheld_metric_result(compiled_spec=spec, target=target, reason_code=reason)
        return default_path, {"result": result, "trace": trace, "observation": None,
                              "selection": {"reason_code": reason, "details": details}}

    if binding["metric_input_status"][metric_id] == "BLOCKED":
        limits = [r for r in binding["limitations"] if r["metric_id"] == metric_id]
        reason = "NORMAL_INPUT_" + (limits[0]["category"] if limits else "UNAVAILABLE")
        return blocked(reason, limits)
    if metric_id == "C04":
        item = inputs["c04"]
        spec = compile_spec_file(path=data_root / item["spec_path"], dependency_specs={})
        return item["spec_path"], resolve_c04(compiled_spec=spec, **item["arguments"])
    if "c03_ecd" in inputs:
        item = inputs["c03_ecd"]
        spec = compile_spec_file(path=data_root / item["spec_path"], dependency_specs={})
        resolved = resolve_c03(compiled_spec=spec, **item["arguments"])
        if resolved["selection"]["reason_code"] not in {"C03_PEO_FACT_NOT_FOUND", "C03_TARGET_PERIOD_NOT_FOUND"}:
            return item["spec_path"], resolved
    failures = []
    for item in inputs["c03_sct_candidates"]:
        spec = compile_spec_file(path=data_root / item["spec_path"], dependency_specs={})
        try:
            resolved = resolve_compensation_table(compiled_spec=spec, **item["arguments"])
            if resolved["result"]["value"] is not None:
                return item["spec_path"], resolved
            failures.append(resolved["selection"])
            if resolved["selection"]["reason_code"] != "SCT_SUPPORTED_TABLE_NOT_FOUND":
                return blocked("C03_REPORTED_TABLE_UNRESOLVED", failures)
        except CompensationTableError as error:
            failures.append({"filing": item["filing"], "reason": str(error)})
            # An absent table may continue to its original filing. A found but
            # conflicting table cannot be repaired by choosing an older value.
            if "SCT_TABLE_NOT_FOUND" not in str(error) and "SCT_TABLE_TITLE" not in str(error):
                return blocked("C03_REPORTED_TABLE_UNRESOLVED", failures)
    return blocked("C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND", failures)


def _prepare_b06(*, repo_root, company_id):
    from .normal_governance_input import _Sources
    from sec_urls import companyfacts_url, submissions_url
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    reader = _Sources(repo_root, company_id, prepared["entity"])
    reader.read(submissions_url(cik=int(prepared["entity"])), role="submissions", media_type="application/json")
    facts = reader.read(companyfacts_url(cik=int(prepared["entity"])),
        accession=prepared["filing"]["accessionNumber"], role="companyfacts", media_type="application/json")
    sources = reader.auditor_filing(prepared["filing"])
    xml = [s for s in sources if s["raw_blob"]["media_type"] == "application/xml"]
    primary = [s for s in sources if s["raw_blob"]["media_type"] == "text/html"]
    if len(xml) != 1 or len(primary) != 1:
        raise ValueError("B06_NORMAL_ORIGINAL_SOURCE_SET_AMBIGUOUS")
    body = {"record_type": "NORMAL_B06_INPUT_BINDING", "prepared_annual_input": prepared,
            "source_proofs": [r["proof"] for r in reader.proofs.values()],
            "source_sets": reader.file_sets}
    return {"input_binding": {**body, "input_binding_id": content_hash(value=body)},
            "records": list(reader.records.values()), "facts": facts, "xml": xml[0], "primary": primary[0]}


def _b06_resolution(*, data_root, preparation):
    from . import b06_disclosure_v2 as disclosure
    from .calculator import withheld_metric_result
    from .normal_annual_input import _registry_rows
    from .r5_b06_scope import resolve_financing
    from .sources import companyfacts_structured_facts
    from .canonical import strict_json_file
    prepared = preparation["input_binding"]["prepared_annual_input"]
    path = disclosure.SPEC_PATH
    spec = compile_spec_file(path=data_root / path, dependency_specs={})
    scope = {"entity_scope": "consolidated"}
    end = prepared["table_input"]["target_period"]["period_end"]
    target = {"company_id": prepared["company_id"], "entity": prepared["entity"],
              "accession": prepared["filing"]["accessionNumber"], "period_start": end,
              "period_end": end, "scope": scope, "scope_key": content_hash(value=scope)}
    company = next(c for c in _registry_rows(repo_root=data_root) if c["company_id"] == prepared["company_id"])
    try:
        if company["industry_profile"] == "financial_institution":
            raise ValueError("B06_BANK_SCOPE_NOT_IMPLEMENTED_IN_THIS_RESOLVER")
        parsed = disclosure.prior.parse_accession_xbrl_source(raw_bytes=preparation["xml"]["raw_bytes"])
        members = set(spec["compiled"]["quality_rule"]["scope_review_dimension_members"])
        if any(any(str(member).split(":")[-1] in members for member in c["dimensions"].values())
               for c in parsed.contexts.values() if c["period_end"] == end
               and str(int(c["entity_identifier"])) == prepared["entity"]):
            raise ValueError("B06_INDUSTRIAL_SCOPE_REQUIRES_SEPARATE_PROOF")
        proposal = disclosure.propose(raw=preparation["xml"]["raw_bytes"],
            primary=preparation["primary"]["raw_bytes"], target=target)
        measurement = disclosure.verify(raw=preparation["xml"]["raw_bytes"],
            primary=preparation["primary"]["raw_bytes"], source=preparation["xml"]["source_reference"],
            spec=spec, target=target, filed=prepared["filing"]["filingDate"], data_root=data_root, proposal=proposal)
        registry = strict_json_file(path=data_root / spec["compiled"]["quality_rule"]["debt_set_registry"])
        concepts = {spec["compiled"]["quality_rule"]["equity_concept"]}
        for model in registry["debt_set_models"].values():
            concepts.update(model["inputs"].values())
            for check in model.get("checks", []): concepts.update(check["inputs"].values())
        facts = companyfacts_structured_facts(raw_bytes=preparation["facts"]["raw_bytes"],
            source_reference=preparation["facts"]["source_reference"], approved_concepts=sorted(concepts),
            allowed_ciks=[prepared["entity"]], include_instant=True)
        result, trace, observations, audit = resolve_financing(spec=spec, target=target,
            traits=repository_company_traits(repo_root=data_root, company_id=prepared["company_id"]),
            facts=facts, measurement=measurement)
        return path, {"result": result, "trace": trace, "observations": observations,
                      "selection": {"measurement": measurement, "audit": audit}}
    except ValueError as error:
        reason = str(error)
        category = ("RELATIONSHIP_AMBIGUOUS" if reason.startswith("UNRESOLVED_FINANCING_ITEM")
                    else "SOURCE_CONFLICT" if reason.startswith("B06_V2_PRIMARY_XML_AMOUNT_CONFLICT")
                    else "IMPLEMENTATION_GAP")
        simple_target = {k: target[k] for k in ("company_id", "period_start", "period_end", "scope", "scope_key")}
        result, trace = withheld_metric_result(compiled_spec=spec, target=simple_target,
                                             reason_code="B06_SOURCE_RELATIONSHIP_UNRESOLVED")
        return path, {"result": result, "trace": trace, "observations": [],
                      "selection": {"reason": reason, "classification": category}}


def _structured_preparation(*, data_root, company_id, metric_id):
    if metric_id == "B06":
        prepared = _prepare_b06(repo_root=data_root, company_id=company_id)
        path, resolution = _b06_resolution(data_root=data_root, preparation=prepared)
    else:
        from .normal_governance_input import prepare_saved_governance_input
        prepared = prepare_saved_governance_input(repo_root=data_root, company_id=company_id)
        path, resolution = _governance_resolution(data_root=data_root, preparation=prepared, metric_id=metric_id)
    proofs = list(prepared["input_binding"]["source_proofs"])
    proofs.extend(prepared["input_binding"]["prepared_annual_input"]["source_proofs"])
    admission = verify_saved_source_proofs(data_root=data_root, proofs=proofs)
    return prepared, path, resolution, admission


def create_structured_candidate_run(*, data_root: Path, run_dir: Path, company_id: str,
                                    metric_id: str, freeze=True):
    """Create and replay C03/C04/B06, keeping input failures as withheld results."""
    if metric_id not in {"B06", "C03", "C04"}:
        raise ValueError("NORMAL_STRUCTURED_METRIC_NOT_ENABLED")
    data_root = b06_new_source._external(data_root)
    run_dir = b06_new_source._external(run_dir)
    prepared, path, resolution, admission = _structured_preparation(
        data_root=data_root, company_id=company_id, metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=data_root / "requirements" / REQUIREMENT_ID)
    result, trace = resolution["result"], resolution["trace"]
    annual = prepared["input_binding"]["prepared_annual_input"]["table_input"]["target_period"]
    period = {"fiscal_year": annual["fiscal_year"], "period_start": result["period_start"], "period_end": result["period_end"]}
    binding = {"record_type": "NORMAL_SOURCE_CANDIDATE_BINDING", "metric_id": metric_id,
        "input_binding": prepared["input_binding"], "source_admission": admission,
        "spec_path": path, "spec_closure_hash": result["spec_closure_hash"],
        "target_period": period, "requirement_closure_hash": requirement["requirement_closure_hash"],
        "production_authorized": False}
    key = content_hash(value=binding)[7:]
    run_id = PREFIX + key
    _write_once(data_root / "normal_bindings" / (key + ".json"), canonical_json_bytes(value=binding))
    if run_dir.exists():
        manifest, _, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
        if manifest["run_id"] != run_id: raise ValueError("NORMAL_CANDIDATE_REENTRY_INPUT_CHANGED")
        return {"manifest": manifest, "result": result, "reused": True}
    records = prepared["records"]
    references = [r for r in records if r["record_type"] == "SOURCE_REFERENCE"]
    create_run(run_dir=run_dir, run_id=run_id, company_id=company_id,
        company_traits=repository_company_traits(repo_root=data_root, company_id=company_id),
        target_period=period, source_references=references, missing_required_source_roles=[],
        spec_file_hashes={path: sha256_file(path=data_root / path)},
        requirement_hashes=requirement["hashes"], requirement_id=REQUIREMENT_ID,
        requirement_closure_hash=requirement["requirement_closure_hash"],
        artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1")
    observations = resolution.get("observations", [resolution["observation"]] if resolution.get("observation") else [])
    for record in [*records, *resolution.get("derived_assets", []), *observations, trace, result]:
        append_run_record(run_dir=run_dir, record=record)
    manifest, _, _ = _finish_run(data_root=data_root, run_dir=run_dir, freeze=freeze)
    return {"manifest": manifest, "result": result, "selection": resolution["selection"],
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "formal_publication_authorized": False}


def replay_structured_normal_result(*, data_root, manifest, spec):
    """Re-discover pinned inputs and re-execute the complete source resolver."""
    from .canonical import strict_json_file
    if not manifest["run_id"].startswith(PREFIX) or manifest["requirement_id"] != REQUIREMENT_ID:
        raise ValueError("NORMAL_STRUCTURED_RUN_IDENTITY_REQUIRED")
    key = manifest["run_id"][len(PREFIX):]
    binding = strict_json_file(path=data_root / "normal_bindings" / (key + ".json"))
    if content_hash(value=binding) != "sha256:" + key:
        raise ValueError("NORMAL_CANDIDATE_BINDING_CHANGED")
    prepared, path, resolution, admission = _structured_preparation(
        data_root=data_root, company_id=manifest["company_id"], metric_id=spec["compiled"]["metric_id"])
    if (binding["input_binding"] != prepared["input_binding"] or binding["source_admission"] != admission
            or binding["spec_path"] != path or binding["spec_closure_hash"] != spec["spec_closure_hash"]
            or binding["requirement_closure_hash"] != manifest["requirement_closure_hash"]
            or binding["target_period"] != manifest["target_period"]
            or manifest["source_references"] != [r for r in prepared["records"] if r["record_type"] == "SOURCE_REFERENCE"]):
        raise ValueError("NORMAL_CANDIDATE_SOURCE_OR_RULE_REPLAY_CHANGED")
    observations = resolution.get("observations", [resolution["observation"]] if resolution.get("observation") else [])
    return resolution["result"], resolution["trace"], observations, resolution["selection"]
