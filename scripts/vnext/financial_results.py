"""Ordinary saved-source financial results through the existing Calculator.

No caller supplies a selected table, number, receipt, SourceSet or applicability
flag. The entrypoint rediscovers the configured company's annual input, checks
the installed saved-source authority, and reconstructs every economic witness.
It creates native records only; Run/Requirement binding and production actions
remain with the ordinary orchestrator.
"""

from pathlib import Path

from .calculator import calculate_metric, calculate_observation_metric, metric_is_applicable, withheld_metric_result
from .batch_workflow import BatchWorkflowError
from .annual_input import AnnualInputError
from .annual_update import AnnualUpdateError
from .canonical import content_hash, sha256_bytes, sha256_file
from .deterministic_router import source_set_manifest
from .financial_balance_scope import inspect_aum_balance, inspect_total_var
from .financial_candidates import inspect_lcr_disclosed_fact
from .financial_relationships import inspect_nim_relationships
from .financial_structured import inspect_inline_financial_claims, inspect_ordinary_a09_source_fact
from .normal_annual_input import prepare_saved_annual_input
from .normal_source_authority import ROOT, NormalSourceAuthorityError, verify_saved_source_proofs
from .observations import scope_key, structured_observation
from .sources import raw_blob_record, resolve_repository_file, source_reference_record
from .specs import compile_spec_file
from .traits import repository_company_traits


RESOLVER = "ordinary_financial_source_v1"
SPEC_PATHS = {
    "A03": "catalog/r4_normal/A03_liquidity_coverage_ratio.md",
    "A04": "catalog/r4_normal/A04_net_interest_margin.md",
    "A09": "catalog/r4_normal/A09_nonperforming_loan_ratio.md",
    "A11": "catalog/r4_normal/A11_assets_under_management.md",
    "A12": "catalog/r4_normal/A12_trading_exposure.md",
    "A13": "catalog/r4_normal/A13_geographic_exposure.md",
}
_ROLES = {
    "A03": "lcr_disclosed_average", "A04": "managed_net_interest_margin",
    "A09": "firmwide_nonperforming_loan_ratio", "A11": "complete_assets_under_management",
    "A12": "firmwide_annual_average_var", "A13": "international_net_revenue",
}
_TRAIT_FILES = ("config/company_registry.csv", "config/metric_applicability.yaml", "catalog/company_traits.yaml")


class FinancialResultError(ValueError):
    """An ordinary input/authority/implementation failure, never an invented value."""

    def __init__(self, reason, category="SOURCE_INTEGRITY_ERROR"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise FinancialResultError(reason, category)


def _installed_rule(*, repo_root, metric_id):
    _need(metric_id in SPEC_PATHS, "FINANCIAL_METRIC_UNSUPPORTED", "IMPLEMENTATION_GAP")
    path = SPEC_PATHS[metric_id]
    local = resolve_repository_file(repo_root=repo_root, repo_relative_path=path)
    _need(sha256_file(path=local) == sha256_file(path=ROOT / path),
          "NORMAL_FINANCIAL_SPEC_DIFFERS_FROM_INSTALLED_RULE")
    spec = compile_spec_file(path=local, dependency_specs={})
    installed = compile_spec_file(path=ROOT / path, dependency_specs={})
    _need(spec == installed, "NORMAL_FINANCIAL_SPEC_DIFFERS_FROM_INSTALLED_RULE")
    semantic = spec["compiled"]
    expected_period = ("source_disclosed_average_ending_at_filing_end" if metric_id == "A03"
                       else "filing_end_instant" if metric_id in {"A09", "A11"}
                       else "exact_annual_filing_period")
    _need(semantic["metric_id"] == metric_id and semantic["kind"] == "direct_numeric"
          and semantic["source_mode"] == "structured"
          and semantic["quality_rule"] == {
              "resolver": RESOLVER, "semantic_role": _ROLES[metric_id],
              "measurement_period": expected_period, "filing_period_role": "separate_annual_reporting_group",
              "source_admission": "trusted_saved_normal_source_set",
              "scope_gate": "complete_source_semantic_fact_with_no_unresolved_competitors",
              "selection": "recompute_from_original_bytes", "ai_calls": 0,
              "fixture_answer_or_receipt_input": False}, "NORMAL_FINANCIAL_RULE_NOT_SUPPORTED")
    trait_hashes = {}
    for relative in _TRAIT_FILES:
        expected = sha256_file(path=ROOT / relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=repo_root, repo_relative_path=relative)) == expected,
              "NORMAL_FINANCIAL_TRAIT_AUTHORITY_CHANGED:" + relative)
        trait_hashes[relative] = expected
    return path, spec, trait_hashes


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
        admission = verify_saved_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    except NormalSourceAuthorityError as error:
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


def _fact(*, metric_id, bundle):
    # Data-root catalogs cannot widen the installed original business vocabulary.
    args = {"repo_root": ROOT, "source_bytes": bundle["source_bytes"],
            "expected_source_sha256": sha256_bytes(content=bundle["source_bytes"]),
            "expected_cik": bundle["expected_cik"], "target_period": bundle["target_period"]}
    if metric_id == "A03":
        fact = inspect_lcr_disclosed_fact(**args)
        return fact, fact["status"] == "SINGLE_SOURCE_SEMANTIC_FACT", fact["value"]
    if metric_id == "A04":
        fact = inspect_nim_relationships(**args)
        passed = fact["semantic_status"] == "SINGLE_SOURCE_SEMANTIC_FACT"
        return fact, passed, fact["relations"][0]["rate_check"]["disclosed_ratio"] if passed else None
    if metric_id == "A09":
        fact = inspect_ordinary_a09_source_fact(repo_root=ROOT, **bundle)
        passed = fact["outcome"] in {"STRUCTURED_PRIMARY_RESOLVED", "HTML_FALLBACK_SOURCE_SEMANTIC_FACT"}
        _need(fact["structured_primary"]["source_set_scope"] == "NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET",
              "FIXTURE_CANNOT_CREATE_ORDINARY_FINANCIAL_RESULT")
        return fact, passed, fact["value"]
    if metric_id == "A11":
        fact = inspect_aum_balance(**args)
        return fact, fact["semantic_status"] == "SINGLE_SOURCE_SEMANTIC_FACT", fact["value"]
    if metric_id == "A12":
        fact = inspect_total_var(**args)
        passed = fact["semantic_status"] == "SINGLE_SOURCE_SEMANTIC_FACT"
        return fact, passed, fact["totals"][0]["value"]["canonical_value"] if passed else None
    fact = inspect_inline_financial_claims(repo_root=ROOT, metric_id="A13", **bundle)
    _need(fact["source_set_scope"] == "NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET",
          "FIXTURE_CANNOT_CREATE_ORDINARY_FINANCIAL_RESULT")
    return fact, fact["outcome"] == "STRUCTURED_PRIMARY_RESOLVED", fact["value"]


def _actual_period(*, metric_id, annual, fact, applicable, passed):
    if not applicable:
        return dict(annual), "STRUCTURAL_NO_MEASUREMENT"
    if metric_id in {"A09", "A11"}:
        return {**annual, "period_start": annual["period_end"]}, "FILING_END_INSTANT"
    if metric_id == "A03":
        if passed:
            period = fact["measurement_period"]
            return {"fiscal_year": annual["fiscal_year"], "period_start": period["period_start"],
                    "period_end": period["period_end"]}, "SOURCE_DISCLOSED_AVERAGE"
        return dict(annual), "NO_MEASUREMENT_RESOLVED_FILING_GROUP_ONLY"
    return dict(annual), "SOURCE_ANNUAL_MEASUREMENT"


def _failure_classification(fact):
    """Read machine reasons, never a word match over quoted source prose."""
    if not isinstance(fact, dict):
        return "IMPLEMENTATION_GAP"
    if fact.get("outcome") == "STRUCTURED_SOURCE_CONFLICT" or fact.get("source_conflicts"):
        return "SOURCE_CONFLICT"
    for field in ("unresolved", "rejected_candidates"):
        for item in fact.get(field, []):
            reason = item.get("reason", item.get("disposition", ""))
            if "CONFLICT" in reason:
                return "SOURCE_CONFLICT"
    return "IMPLEMENTATION_GAP"


def resolve_ordinary_financial_metric(*, repo_root: Path, company_id: str, metric_id: str) -> dict:
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
