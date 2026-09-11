"""Native Run checks for explicitly delegated deterministic source excerpts."""

from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input import prepare_saved_annual_input
from .normal_source_authority import verify_saved_source_proofs
from .sources import raw_blob_record, source_reference_record, resolve_repository_file
from .specs import compile_spec_file
from .text_results import DETERMINISTIC_CANDIDATE_TYPE, verify_deterministic_text_candidate


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


D01_SPEC_PATH = "catalog/r6/D01_risk_factor_headings.md"


def normal_text_binding(*, prepared, admission, spec, requirement):
    return {"record_type": "NORMAL_SOURCE_CANDIDATE_BINDING", "metric_id": "D01",
        "prepared_input": prepared, "source_admission": admission,
        "spec_closure_hash": spec["spec_closure_hash"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "scope": {"entity_scope": "registrant"}, "production_authorized": False}


def normal_text_sources(*, repo_root, company_id):
    """Rebuild the complete input set from pinned discovery, not the candidate."""
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    admission = verify_saved_source_proofs(data_root=repo_root,
                                          proofs=prepared["source_proofs"])
    records, references = [], []
    for role, proof in zip(["submissions", "target_primary", "companyfacts"],
                           prepared["source_proofs"]):
        blob = raw_blob_record(repo_root=repo_root,
            repo_relative_path=proof["request_repo_relative_path"],
            media_type="text/html" if role == "target_primary" else "application/json")
        ref = source_reference_record(raw_blob=blob, company_id=company_id,
            source_url=proof["source_url"], accession=prepared["filing"]["accessionNumber"],
            document_name=proof["document_name"], source_role=role,
            request_attempt_id=proof["request_attempt_id"])
        records.extend([blob, ref])
        references.append(ref)
    return prepared, admission, records, references


def prepare_text_run_contexts(*, repo_root, manifest, records, compiled_specs,
                              raw_bytes_by_id, requirement):
    """Enforce native policy, discovered source exact set and byte replay."""
    candidates = [r for r in records if r["record_type"] == DETERMINISTIC_CANDIDATE_TYPE]
    if not candidates:
        return {}
    allowed = requirement.get("policy", {}).get("native_deterministic_text_methods", [])
    _need(allowed == ["RISK_FACTOR_HEADINGS_V1"], "NATIVE_DETERMINISTIC_TEXT_POLICY_NOT_ENABLED")
    path = resolve_repository_file(repo_root=repo_root, repo_relative_path=D01_SPEC_PATH)
    installed_spec = compile_spec_file(path=path, dependency_specs={})
    _need(compiled_specs == {"D01": installed_spec}
          and manifest["spec_file_hashes"] == {D01_SPEC_PATH: sha256_file(path=path)},
          "TEXT_RUN_INSTALLED_D01_SPEC_REQUIRED")
    prepared, admission, expected_records, expected_sources = normal_text_sources(
        repo_root=repo_root, company_id=manifest["company_id"])
    expected_binding = normal_text_binding(prepared=prepared, admission=admission,
                                          spec=installed_spec, requirement=requirement)
    key = content_hash(value=expected_binding)[7:]
    _need(manifest["run_id"] == "run:normal-saved:" + key,
          "TEXT_RUN_NORMAL_INPUT_IDENTITY_CHANGED")
    binding_path = resolve_repository_file(repo_root=repo_root,
        repo_relative_path="normal_bindings/" + key + ".json")
    _need(strict_json_file(path=binding_path) == expected_binding,
          "TEXT_RUN_NORMAL_INPUT_BINDING_CHANGED")
    _need(manifest["target_period"] == prepared["table_input"]["target_period"],
          "TEXT_RUN_DISCOVERED_PERIOD_CHANGED")
    _need(manifest["source_references"] == expected_sources,
          "TEXT_RUN_DISCOVERED_SOURCE_SET_CHANGED")
    for expected in expected_records:
        _need(expected in records, "TEXT_RUN_DISCOVERED_SOURCE_RECORD_MISSING")
    raw_blobs = {r["raw_asset_id"]: r for r in expected_records if r["record_type"] == "RAW_BLOB"}
    text_sources = [r for r in expected_sources if r["source_role"] == "target_primary"]
    _need(len(text_sources) == 1, "TEXT_RUN_ORDINARY_SOURCE_NOT_UNIQUE")
    contexts = {}
    used_metrics = set()
    for candidate in candidates:
        specs = [s for s in compiled_specs.values()
                 if s["spec_closure_hash"] == candidate["spec_closure_hash"]]
        _need(len(specs) == 1, "TEXT_CANDIDATE_RUN_SPEC_CHANGED")
        spec = specs[0]
        semantic = spec["compiled"]
        metric_id = semantic["metric_id"]
        _need(metric_id not in used_metrics and semantic["kind"] == "direct_text"
              and semantic["required_claims"] == {"entity_scope": "registrant"}
              and semantic["quality_rule"].get("deterministic_text_method") in allowed,
              "TEXT_RUN_METHOD_OR_REGISTRANT_SCOPE_CHANGED")
        used_metrics.add(metric_id)
        target = {"company_id": manifest["company_id"], "entity": prepared["entity"],
                  "accession": prepared["filing"]["accessionNumber"],
                  "period_start": manifest["target_period"]["period_start"],
                  "period_end": manifest["target_period"]["period_end"],
                  "scope": dict(semantic["required_claims"]),
                  "scope_key": content_hash(value=semantic["required_claims"])}
        args = {"compiled_spec": spec, "target": target,
                "source_references": text_sources, "raw_blobs": raw_blobs,
                "raw_bytes_by_id": raw_bytes_by_id}
        verify_deterministic_text_candidate(candidate=candidate, **args)
        contexts[candidate["candidate_hash"]] = args
    return contexts
