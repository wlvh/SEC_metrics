"""Rebuild the A01/A02/B12 instant facts for a selected historical period.

Another source adapter, not another engine: the installed accession policy, the
frozen catalog, ``inspect_ordinary_accession_facts``, the compiled Specs, the
applicability rules and ``calculate_observation_metric`` are imported unchanged.
What this module owns is which filing's own inline XBRL document the instant
facts are read from when the period is pinned.

It exists as a successor file because ``scripts/vnext/normal_accession_results.py``
is byte-bound by the ``issue_28_v13`` rule set; changing it would stop every
existing ordinary Run from loading its own Requirement.
"""
import copy
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url

from .calculator import metric_is_applicable, withheld_metric_result, calculate_observation_metric
from .canonical import content_hash, sha256_file, strict_json_file
from .historical_annual_input import prepare_historical_annual_input
from .normal_accession_results import (POLICY_PATH, _AUTHORITY, NormalAccessionError,
                                       inspect_ordinary_accession_facts)
from .normal_annual_input_v2 import exact_json_value
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import resolve_repository_file
from .traits import repository_company_traits
from .zero_ai_r2 import (_load_deterministic_catalog, _compiled_deterministic_spec,
                         _manual_result_trace, _exact_filing_source_set)


RECORD_TYPE = "HISTORICAL_ACCESSION_NATIVE_RESULTS"


def _need(condition, reason):
    if not condition:
        raise NormalAccessionError(reason)


def resolve_historical_accession_metrics(*, repo_root: Path, company_id: str, period_selection):
    """Resolve the instant-grain accession metrics for one pinned period.

    The facts come from the selected filing's own inline XBRL document at that
    filing's own period end, so a past instant is never answered with today's
    balance.
    """
    authority = {}
    for relative in _AUTHORITY:
        digest = sha256_file(path=ROOT / relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=repo_root,
                                                       repo_relative_path=relative)) == digest,
              "HISTORICAL_ACCESSION_INSTALLED_AUTHORITY_CHANGED:" + relative)
        authority[relative] = digest
    policy = strict_json_file(path=repo_root / POLICY_PATH)
    _need(policy["record_type"] == "ORDINARY_ACCESSION_METRIC_POLICY"
          and policy["schema_version"] == 1 and policy["creates_run"] is False
          and policy["production_authorized"] is False, "HISTORICAL_ACCESSION_POLICY_INVALID")
    catalog = _load_deterministic_catalog(repo_root=repo_root)
    current = copy.deepcopy(catalog)
    for metric_id, item in policy["metrics"].items():
        route = current["metrics"][metric_id]
        route["canonical_unit"] = item["canonical_unit"]
        route["result_period_role"] = "current_instant"
        for branch in route["branches"]:
            for component in branch["components"]:
                component["unit"] = item["canonical_unit"]
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    period = prepared["table_input"]["target_period"]
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])),
                            role="sec_submissions_inventory", media_type="application/json")
    source = reader.primary(prepared["filing"])
    reader.read(companyfacts_url(cik=int(prepared["entity"])),
                accession=prepared["filing"]["accessionNumber"], role="companyfacts",
                media_type="application/json")
    manifest = _exact_filing_source_set(company_id=company_id,
                                        source_role="target_accession_instance",
                                        reference=source["source_reference"],
                                        inventory_reference=inventory["source_reference"],
                                        inventory_bytes=inventory["raw_bytes"])
    traits = repository_company_traits(repo_root=repo_root, company_id=company_id)
    rows = {}
    for metric_id, item in policy["metrics"].items():
        route = current["metrics"][metric_id]
        spec = _compiled_deterministic_spec(metric_id=metric_id, route=route)
        scope = {"coverage": "deterministic_source_set", "fiscal_year": period["fiscal_year"]}
        target = {"company_id": company_id, "period_start": period["period_end"],
                  "period_end": period["period_end"], "scope": scope,
                  "scope_key": scope_key(scope=scope)}
        inspection, observations, selected = None, [], []
        if not metric_is_applicable(applicability=route["applicability"], traits=traits):
            result, trace = _manual_result_trace(
                metric_id=metric_id, company_id=company_id, period_start=period["period_end"],
                period_end=period["period_end"], scope=scope,
                spec_closure_hash=spec["spec_closure_hash"], applicability="N_A_STRUCTURAL",
                quality="NONE", reason_code="TRAIT_NOT_APPLICABLE", input_observation_ids=[],
                steps=[{"event": "N_A_STRUCTURAL"}], accession=None, entity=None, unit=None)
        else:
            try:
                _need(not prepared["amendments"],
                      "HISTORICAL_ACCESSION_AMENDED_TARGET_NOT_IMPLEMENTED")
                _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY",
                      "HISTORICAL_ACCESSION_SUCCESSOR_SCOPE_NOT_IMPLEMENTED")
                inspection = inspect_ordinary_accession_facts(
                    raw_bytes=source["raw_bytes"], source_reference=source["source_reference"],
                    source_set_manifest=manifest, expected_cik=prepared["entity"],
                    period_end=period["period_end"], route=catalog["metrics"][metric_id],
                    metric_id=metric_id, policy=policy)
                _need(inspection["status"] == "SOURCE_SCOPE_PROVEN",
                      "HISTORICAL_ACCESSION_SOURCE_SCOPE_UNRESOLVED")
                selected = sorted(inspection["selected_claims"],
                                  key=lambda claim: claim["verified_claim_id"])
                reference = source["source_reference"]
                observation = structured_observation(
                    metric_id=metric_id, semantic_role="deterministic_value",
                    company_id=company_id, period_start=period["period_end"],
                    period_end=period["period_end"], scope=scope, value=selected[0]["value"],
                    unit=item["canonical_unit"], quality="EXACT",
                    source_binding={"raw_asset_id": reference["raw_asset_id"],
                                    "source_reference_id": reference["source_reference_id"],
                                    "accession": reference["accession"],
                                    "document_name": reference["document_name"],
                                    "source_role": reference["source_role"],
                                    "source_set_manifest_id": manifest["source_set_manifest_id"],
                                    "verified_claim_ids": [c["verified_claim_id"] for c in selected],
                                    "ordinary_policy_hash": content_hash(value=policy),
                                    "source_measure": item["measure"]})
                result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
                                                             company_traits=traits,
                                                             observation=observation)
                observations = [observation]
            except ValueError as error:
                inspection = {**(inspection or {}), "status": "UNRESOLVED", "reason": str(error)}
                result, trace = withheld_metric_result(
                    compiled_spec=spec, target=target,
                    reason_code="HISTORICAL_ACCESSION_ROUTE_UNRESOLVED")
        rows[metric_id] = {"metric_id": metric_id, "measure": item["measure"],
                           "compiled_spec": spec, "target": target, "inspection": inspection,
                           "claims": selected, "observations": observations, "result": result,
                           "trace": trace, "records": [*observations, trace, result]}
    proofs = list({content_hash(value=p): p for p in
                   [*prepared["source_proofs"],
                    *[s["proof"] for s in reader.proofs.values()]]}.values())
    body = {"record_type": RECORD_TYPE, "company_id": company_id,
            "period_selection": period_selection, "prepared_input": prepared,
            "authority_file_hashes": authority, "policy_hash": content_hash(value=policy),
            "source_records": list(reader.records.values()), "source_set": manifest,
            "source_proofs": proofs,
            "source_admission": verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs),
            "metrics": rows, "resolver_sha256": sha256_file(path=Path(__file__)),
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "native_run_status": "NOT_CREATED",
            "current_latest_verified": False, "latest_restated_values_used": False,
            "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "component_id": content_hash(value=body)}


def verify_historical_accession_metrics(*, candidate, repo_root: Path, company_id: str,
                                        period_selection):
    rebuilt = resolve_historical_accession_metrics(repo_root=repo_root, company_id=company_id,
                                                   period_selection=period_selection)
    _need(candidate == rebuilt, "HISTORICAL_ACCESSION_SOURCE_REPLAY_CHANGED")
    return rebuilt
