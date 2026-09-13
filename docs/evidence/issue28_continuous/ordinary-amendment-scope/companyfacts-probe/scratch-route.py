"""Rebuild ordinary catalog metrics from original current/prior SEC facts.

The existing catalog owns formulas and concept priority. This source adapter
supplies filing identities and actual periods without reading old results or
entering the historical release planner. It creates native records, not Runs.
"""
from datetime import date, timedelta
from decimal import DecimalException
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url, submissions_file_url
from .annual_update import AnnualUpdateError
from .batch_workflow import BatchWorkflowError
from .calculator import metric_is_applicable, withheld_metric_result
from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_loads
from .deterministic_router import adapt_companyfacts
from .normal_annual_input import annual_period, _registry_rows, NormalAnnualInputError
from .annual_amendment_scope import prepare_saved_amendment_input
from .normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value, POLICY_PATH as FISCAL_LABEL_POLICY_PATH
from .normal_governance_input import _Sources, _filings, _history_index, history_body_alignment, NormalGovernanceInputError
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .observations import scope_key
from .sources import resolve_repository_file, SourceError
from .traits import repository_company_traits
from .zero_ai_r2 import (_load_deterministic_catalog, _compiled_deterministic_spec,
    _deterministic_metric_graph, _manual_result_trace, _exact_filing_source_set)
from .zero_ai_release import ZeroAiReleaseError


CATALOG_PATH = "catalog/deterministic_metrics.json"
_AUTHORITY_PATHS = (CATALOG_PATH, FISCAL_LABEL_POLICY_PATH, "config/company_registry.csv", "catalog/company_traits.yaml",
                    "config/metric_applicability.yaml")
_SOURCE_ERRORS = (AnnualUpdateError, BatchWorkflowError, NormalAnnualInputError,
                  NormalGovernanceInputError, SourceError, ZeroAiReleaseError)


class NormalCompanyfactsError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise NormalCompanyfactsError(reason)


def _authority(root):
    files = {}
    for relative in _AUTHORITY_PATHS:
        expected = sha256_file(path=ROOT / relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=root, repo_relative_path=relative)) == expected,
              "NORMAL_COMPANYFACTS_INSTALLED_AUTHORITY_CHANGED:" + relative)
        files[relative] = expected
    return files


def _prior_filing(reader, inventory, prepared):
    """Prove the immediately preceding ordinary filing in relevant metadata."""
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    rows = [(r, inventory) for r in _filings(payload, inventory_name=inventory["source_reference"]["document_name"])]
    current_end = prepared["filing"]["reportDate"]
    for shard in _history_index(payload, prepared["entity"]):
        prior_end = max((r["reportDate"] for r, _ in rows if r["form"] == "10-K" and r["reportDate"] < current_end), default="")
        if prior_end and shard["filingTo"] < prior_end:
            break
        source = reader.read(submissions_file_url(file_name=shard["name"]), role="sec_submissions_history", media_type="application/json")
        body = strict_json_loads(text=source["raw_bytes"].decode("utf-8"))
        _need("cik" not in body or str(body["cik"]).isdigit() and int(body["cik"]) == int(prepared["entity"]),
              "NORMAL_COMPANYFACTS_PRIOR_HISTORY_ENTITY_CONFLICT")
        values = _filings(body, inventory_name=shard["name"])
        _need(history_body_alignment(shard=shard, rows=values) is None,
              "NORMAL_COMPANYFACTS_PRIOR_HISTORY_SNAPSHOT_CONFLICT")
        rows.extend((r, source) for r in values)
    _need(len({r["accessionNumber"] for r, _ in rows}) == len(rows), "NORMAL_COMPANYFACTS_PRIOR_METADATA_OVERLAP")
    prior_end = max((r["reportDate"] for r, _ in rows if r["form"] == "10-K" and r["reportDate"] < current_end), default="")
    matches = [(r, s) for r, s in rows if r["form"] == "10-K" and r["reportDate"] == prior_end]
    _need(len(matches) == 1, "NORMAL_COMPANYFACTS_PRIOR_ORDINARY_MISSING_OR_AMBIGUOUS")
    _need(not any(r["form"] == "10-K/A" and r["reportDate"] == prior_end for r, _ in rows),
          "NORMAL_COMPANYFACTS_PRIOR_AMENDMENT_REPLAY_NOT_IMPLEMENTED")
    return matches[0]


def _filing_source(reader, prepared, filing, inventory, concepts):
    source = reader.read(companyfacts_url(cik=int(prepared["entity"])), accession=filing["accessionNumber"],
                         role="companyfacts", media_type="application/json")
    manifest = _exact_filing_source_set(company_id=prepared["company_id"], source_role="companyfacts",
        reference=source["source_reference"], inventory_reference=inventory["source_reference"], inventory_bytes=inventory["raw_bytes"])
    claims = adapt_companyfacts(raw_bytes=source["raw_bytes"], source_reference=source["source_reference"],
        source_set_manifest=manifest, approved_concepts=concepts, allowed_ciks=[prepared["entity"]], include_instant=True)
    return {"reference":source["source_reference"], "manifest":manifest}, claims


def resolve_ordinary_companyfacts_metrics(*, repo_root: Path, company_id: str):
    """Resolve all eleven catalog Company Facts metrics from saved originals.

    Current-only metrics can succeed when a required prior source for another
    metric is unavailable. No caller period, answer, filing or proof is accepted.
    """
    authority = _authority(repo_root)
    catalog = _load_deterministic_catalog(repo_root=repo_root)
    routes = {key:value for key,value in catalog["metrics"].items() if value["adapter_id"] == "companyfacts"}
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    verify_saved_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    period = prepared["table_input"]["target_period"]
    registry = next(r for r in _registry_rows(repo_root=repo_root) if r["company_id"] == company_id)
    traits = repository_company_traits(repo_root=repo_root, company_id=company_id)
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])), role="sec_submissions_inventory", media_type="application/json")
    reader.primary(prepared["filing"])
    concepts = sorted({concept for route in routes.values() for branch in route["branches"]
                       for component in branch["components"] for concept in component["approved_concepts"]})
    sources, claims_by_role = [], {}
    source, claims_by_role["current"] = _filing_source(reader, prepared, prepared["filing"], inventory, concepts)
    sources.append({**source, "accession_role":"current"})
    periods, filings = {"current":period, "prior":None}, {"current":prepared["filing"], "prior":None}
    prior_error = None
    amendment_input = None
    common_error = "NORMAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED" if prepared["subject_policy"]["mode"] != "CONTINUOUS_PRIMARY" else None
    if prepared["amendments"] and common_error is None:
        amendment_input = prepare_saved_amendment_input(repo_root=repo_root,company_id=company_id,input_class="ORIGINAL_STATEMENT_VALUES")
        _need(amendment_input["prepared_input"] == prepared.get("original_input",prepared), "NORMAL_AMENDMENT_ORIGINAL_INPUT_DIFFERS")
        if amendment_input["decision"] != "INPUT_PROPERTY_PROVEN":
            common_error = "NORMAL_COMPANYFACTS_AMENDMENT_INPUT_SCOPE_UNRESOLVED"
    needs_prior = any(metric_is_applicable(applicability=route["applicability"], traits=traits)
        and any(c["accession_role"] == "prior" for b in route["branches"] for c in b["components"]) for route in routes.values())
    if needs_prior and not common_error:
        try:
            filing, prior_inventory = _prior_filing(reader, inventory, prepared)
            primary = reader.primary(filing, required=False)
            # A missing saved HTML body can still have its exact accession
            # instance from the authenticated directory index. The same DEI
            # identity/context checks apply to every supplied native document.
            # A failed final GET propagates; it is never replaced by an older
            # success or treated as an optional missing body.
            documents = [primary] if primary else reader.auditor_filing(filing)
            source_periods = [annual_period(raw=s["raw_bytes"], cik=prepared["entity"], filing=filing) for s in documents]
            _need(bool(source_periods) and all(p == source_periods[0] for p in source_periods),
                  "NORMAL_COMPANYFACTS_PRIOR_NATIVE_PERIOD_CONFLICT")
            prior = source_periods[0]
            _need(date.fromisoformat(prior["period_end"]) + timedelta(days=1) == date.fromisoformat(period["period_start"]),
                  "NORMAL_COMPANYFACTS_PRIOR_PERIOD_NOT_ADJACENT")
            source, claims_by_role["prior"] = _filing_source(reader, prepared, filing, prior_inventory, concepts)
            sources.append({**source,"accession_role":"prior"})
            periods["prior"], filings["prior"] = prior, filing
        except (*_SOURCE_ERRORS, NormalCompanyfactsError) as error:
            prior_error = {"reason":str(error), "error_type":type(error).__name__}
    context = {"repo_root":repo_root, "deterministic_catalog":catalog,
        "role_context":{(company_id,"companyfacts"):{"sources":sources,"claims_by_accession_role":claims_by_role}},
        "target_periods":{company_id:periods},"targets":{company_id:period},"registry":{company_id:registry},
        "filings_by_company":{company_id:{role:({"accession":filing["accessionNumber"]} if filing else None) for role,filing in filings.items()}}}
    results = {}
    for metric_id, route in routes.items():
        spec = _compiled_deterministic_spec(metric_id=metric_id, route=route)
        instant = route["result_period_role"] == "current_instant"
        scope = {"coverage":"deterministic_source_set", "fiscal_year":period["fiscal_year"]}
        target = {"company_id":company_id,"period_start":period["period_end"] if instant else period["period_start"],
                  "period_end":period["period_end"],"scope":scope,"scope_key":scope_key(scope=scope)}
        detail = None
        graph = {"claims":[],"projection_claims":[],"observation":None}
        if not metric_is_applicable(applicability=route["applicability"], traits=traits):
            result, trace = _manual_result_trace(metric_id=metric_id, company_id=company_id,
                period_start=target["period_start"],period_end=target["period_end"],scope=scope,spec_closure_hash=spec["spec_closure_hash"],
                applicability="N_A_STRUCTURAL",quality="NONE",reason_code="TRAIT_NOT_APPLICABLE",input_observation_ids=[],
                steps=[{"event":"N_A_STRUCTURAL"}],accession=None,entity=None,unit=None)
        else:
            try:
                _need(not common_error, common_error)
                requires_prior = any(c["accession_role"] == "prior" for b in route["branches"] for c in b["components"])
                _need(not requires_prior or prior_error is None, (prior_error or {}).get("reason"))
                graph = _deterministic_metric_graph(context=context, company_id=company_id, metric_id=metric_id)
                result, trace = graph["result"], graph["trace"]
            except (*_SOURCE_ERRORS, NormalCompanyfactsError, DecimalException) as error:
                detail = {"reason":str(error),"error_type":type(error).__name__,
                          "category":"SOURCE_OR_IMPLEMENTATION_UNRESOLVED"}
                result, trace = withheld_metric_result(compiled_spec=spec,target=target,reason_code="NORMAL_COMPANYFACTS_ROUTE_UNRESOLVED")
        observations = [graph["observation"]] if graph["observation"] else []
        results[metric_id] = {"metric_id":metric_id,"compiled_spec":spec,"target":target,
            "selection":detail,"claims":graph["claims"],"projection_claims":graph["projection_claims"],
            "observations":observations,"result":result,"trace":trace,"records":[*observations,trace,result]}
    proofs = list({content_hash(value=p):p for p in [*prepared["source_proofs"],*[s["proof"] for s in reader.proofs.values()]]}.values())
    if amendment_input is not None:
        proofs = list({content_hash(value=p):p for p in [*proofs,*amendment_input["source_proofs"]]}.values())
    admission = verify_saved_source_proofs(data_root=repo_root, proofs=proofs)
    source_records = list(reader.records.values())
    if amendment_input is not None:
        source_records = list({content_hash(value=r):r for r in [*source_records,*amendment_input["source_records"]]}.values())
    body = {"record_type":"NORMAL_COMPANYFACTS_NATIVE_RESULTS","company_id":company_id,
        "prepared_input":prepared,"filings":filings,"periods":periods,"prior_error":prior_error,
        "authority_file_hashes":authority,"source_records":source_records,"amendment_input":amendment_input,"source_proofs":proofs,
        "source_admission":admission,"source_sets":[s["manifest"] for s in sources],"claims_by_accession_role":claims_by_role,
        "failed_source_attempts":list(reader.failed_attempts.values()),"metrics":results,
        "resolver_sha256":sha256_file(path=Path(__file__)),"calls":{"provider":0,"paid":0,"sec":0},
        "native_run_status":"NOT_CREATED","current_latest_verified":False,"production_authorized":False}
    body = exact_json_value(body)
    return {**body,"component_id":content_hash(value=body)}


def verify_ordinary_companyfacts_metrics(*, candidate, repo_root: Path, company_id: str):
    rebuilt = resolve_ordinary_companyfacts_metrics(repo_root=repo_root, company_id=company_id)
    _need(candidate == rebuilt, "NORMAL_COMPANYFACTS_SOURCE_REPLAY_CHANGED")
    return rebuilt
