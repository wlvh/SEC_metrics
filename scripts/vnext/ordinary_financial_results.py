"""Current source admission for unchanged financial interpretation and formulas.

Only input ownership is new. Frozen semantic inspectors, Specs, period rules
and Calculator functions remain the business authority.
"""
from pathlib import Path
from .financial_results import (RESOLVER,_ROLES,FinancialResultError,_need,_installed_rule,
    _fact,_actual_period,_failure_classification)
from .calculator import calculate_metric,calculate_observation_metric,metric_is_applicable,withheld_metric_result
from .batch_workflow import BatchWorkflowError
from .annual_input import AnnualInputError
from .annual_update import AnnualUpdateError
from .canonical import content_hash,sha256_bytes,sha256_file
from .deterministic_router import source_set_manifest
from .normal_annual_input import prepare_saved_annual_input
from .normal_source_authority import ROOT,NormalSourceAuthorityError
from .ordinary_source_authority import verify_ordinary_source_proofs,OrdinarySourceAuthorityError
from .observations import scope_key,structured_observation
from .sources import raw_blob_record,resolve_repository_file,source_reference_record
from .traits import repository_company_traits


def _ordinary_sources(*, repo_root, company_id):
    try:
        prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    except BatchWorkflowError as error:
        raise FinancialResultError("NORMAL_FINANCIAL_SOURCE_PROVENANCE_FAILED:" + str(error)) from error
    except (AnnualInputError, AnnualUpdateError) as error:
        reason = str(error)
        category = ("SOURCE_ACCESS_FAILED" if reason.startswith("LATEST_SOURCE_REQUEST_FAILED")
                    else "SOURCE_UNAVAILABLE" if reason.startswith("SAVED_SOURCE_MISSING") else "SOURCE_INTEGRITY_ERROR")
        raise FinancialResultError(reason, category) from error
    _need(len(prepared["source_proofs"]) == 3, "NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE")
    try:
        admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    except (NormalSourceAuthorityError,OrdinarySourceAuthorityError) as error:
        raise FinancialResultError("NORMAL_FINANCIAL_SOURCE_ADMISSION_FAILED:" + str(error)) from error
    records, references, raw = [], [], []
    for role, proof in zip(("sec_submissions_inventory", "target_primary", "companyfacts"), prepared["source_proofs"]):
        media = "text/html" if role == "target_primary" else "application/json"
        blob = raw_blob_record(repo_root=repo_root, repo_relative_path=proof["request_repo_relative_path"], media_type=media)
        content = resolve_repository_file(repo_root=repo_root, repo_relative_path=proof["request_repo_relative_path"]).read_bytes()
        _need(blob["raw_asset_id"] == "sha256:" + proof["content_sha256"]
              and sha256_bytes(content=content) == proof["content_sha256"], "ORDINARY_SOURCE_CHANGED_AFTER_ADMISSION")
        dataset = "SEC_SUBMISSIONS_INVENTORY" if role == "sec_submissions_inventory" else "SEC_COMPANYFACTS_INVENTORY"
        reference = source_reference_record(raw_blob=blob, company_id=company_id,
            source_url=proof["source_url"], accession=proof["accession"] or dataset,
            document_name=proof["document_name"], source_role=role,
            request_attempt_id=proof["request_attempt_id"])
        records.extend([blob, reference])
        references.append(reference)
        raw.append(content)
    _need(len(references) == 3 and references[1]["accession"] == prepared["filing"]["accessionNumber"],
          "NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE")
    filing_day = prepared["filing"]["filingDate"]
    manifest = source_set_manifest(company_id=company_id, source_role="target_primary", form_types=["10-K"],
        fiscal_or_date_window={"period_start": filing_day, "period_end": filing_day},
        discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1", inventory_source_reference=references[0],
        inventory_bytes=raw[0], ordered_source_references=[references[1]],
        cutoff_timestamp_or_pinned_submissions_attempt=references[0]["request_attempt_id"])
    bundle = {"source_bytes": raw[1], "source_reference": references[1], "source_set_manifest": manifest,
              "inventory_source_reference": references[0], "inventory_bytes": raw[0],
              "expected_cik": prepared["entity"], "target_period": prepared["table_input"]["target_period"]}
    return prepared, admission, records, references, bundle


def resolve_current_financial_metric(*, repo_root: Path, company_id: str, metric_id: str) -> dict:
    """Create native records from current saved inputs with no Run or writes.

    A PUBLISHED field on the Calculator's metric record is its native result
    state. It does not mean the result has entered a publication or active Run.
    The returned filing period is a separate reporting group from actual
    quarter/instant measurement targets.
    """
    path, spec, trait_hashes = _installed_rule(repo_root=repo_root, metric_id=metric_id)
    prepared, admission, source_records, references, bundle = _ordinary_sources(repo_root=repo_root, company_id=company_id)
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    applicable = metric_is_applicable(applicability=spec["compiled"]["applicability"], traits=traits)
    fact, passed, value, reason = None, False, None, "TRAIT_NOT_APPLICABLE"
    if applicable:
        if prepared["update_status"] != "ORIGINAL_INPUT_READY":
            reason = "FINANCIAL_NORMAL_INPUT_REQUIRES_AMENDMENT_OR_SUBJECT_PROCESSING"
        else:
            fact, passed, value = _fact(metric_id=metric_id, bundle=bundle)
            reason = "PASS" if passed else "FINANCIAL_SOURCE_SEMANTICS_UNRESOLVED"
    annual = prepared["table_input"]["target_period"]
    actual, time_basis = _actual_period(metric_id=metric_id, annual=annual, fact=fact, applicable=applicable, passed=passed)
    scope = dict(spec["compiled"]["required_claims"])
    target = {"company_id": company_id, "period_start": actual["period_start"], "period_end": actual["period_end"],
              "scope": scope, "scope_key": scope_key(scope=scope)}
    input_body = {"record_type": "ORDINARY_FINANCIAL_INPUT_BINDING", "resolver": RESOLVER, "metric_id": metric_id,
        "company_id": company_id, "prepared_input": prepared, "source_proofs": prepared["source_proofs"],
        "source_admission": admission, "source_set_manifest": bundle["source_set_manifest"],
        "source_reference_ids": [r["source_reference_id"] for r in references], "trait_authority_sha256": trait_hashes,
        "company_traits": traits, "spec_path": path, "spec_closure_hash": spec["spec_closure_hash"],
        "spec_file_sha256": sha256_file(path=repo_root / path), "filing_period": annual,
        "actual_target": target, "actual_target_period": actual, "measurement_time_basis": time_basis,
        "source_fact_hash": content_hash(value=fact) if fact is not None else None,
        "source_semantics_passed": passed, "reason_code": reason, "production_authorized": False}
    binding = {**input_body, "input_binding_id": content_hash(value=input_body)}
    observations = []
    if not applicable:
        result, trace, observations = calculate_metric(compiled_spec=spec,
            target={**target, "accession": prepared["filing"]["accessionNumber"], "entity": prepared["entity"]},
            company_traits=traits, structured_facts=[], verified_observations=[])
    elif not passed:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target, reason_code=reason)
    else:
        primary = bundle["source_reference"]
        observation = structured_observation(metric_id=metric_id, semantic_role=_ROLES[metric_id],
            company_id=company_id, period_start=actual["period_start"], period_end=actual["period_end"],
            scope=scope, value=value, unit=spec["compiled"]["canonical_unit"], quality="EXACT",
            source_binding={"raw_asset_id": primary["raw_asset_id"], "source_reference_id": primary["source_reference_id"],
                "accession": primary["accession"], "document_name": primary["document_name"], "source_role": primary["source_role"],
                "entity": prepared["entity"], "resolver": RESOLVER, "input_binding_id": binding["input_binding_id"],
                "source_set_manifest_id": bundle["source_set_manifest"]["source_set_manifest_id"],
                "source_fact_hash": binding["source_fact_hash"], "measurement_time_basis": time_basis,
                "filing_period": annual, "actual_measurement_period": actual})
        result, trace = calculate_observation_metric(compiled_spec=spec, target=target, company_traits=traits, observation=observation)
        observations = [observation]
    return {"record_type": "ORDINARY_FINANCIAL_RESOLUTION", "resolver": RESOLVER, "metric_id": metric_id,
        "company_id": company_id, "spec_path": path, "compiled_spec": spec, "prepared_input": prepared,
        "source_records": source_records, "source_references": references, "source_proofs": prepared["source_proofs"],
        "source_admission": admission, "input_binding": binding, "source_fact": fact, "company_traits": traits,
        "filing_period": dict(annual), "target_period": actual, "target": target, "observations": observations,
        "result": result, "trace": trace, "records": [*source_records, *observations, trace, result],
        "selection": {"reason_code": reason, "source_semantics_passed": passed,
                      "classification": "STRUCTURAL" if not applicable else "VERIFIED_SOURCE_FACT" if passed else _failure_classification(fact)},
        "calls": {"provider": 0, "paid": 0, "sec": 0}, "native_run_status": "NOT_CREATED",
        "qualification_credit": "NONE", "formal_publication_authorized": False}
