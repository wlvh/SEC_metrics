"""Project source-replayed ordinary Runs, including dependencies and claims.

An OPEN preview and a frozen candidate carry different receipt states. Neither
writes a publication or changes a Spec. Composite evidence exposes each source
fact rather than presenting the computed ratio as a verbatim source amount.
"""
import json
from pathlib import Path

from . import projector, publication
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .normal_annual_input_v2 import prepare_saved_annual_input
from .normal_numeric_projection import _period_label, _objects, _filings, _selected_financial_locators, _evidence_context, _raw_value
from .normal_run_v3 import REQUIREMENT_ID, replay_case
from .run_store import _mechanically_replay_open_run, load_frozen_run


POLICY_PATH = "config/ordinary_public_projection_v1.json"


def _need(condition, reason):
    if not condition:raise ValueError(reason)


def _claims(case):
    result = {}
    for value in _objects(case["input_binding"]):
        if value.get("record_type") == "DETERMINISTIC_VERIFIED_CLAIM":
            key = value["verified_claim_id"]
            _need(key not in result or result[key] == value,"ORDINARY_PROJECTION_CLAIM_CONFLICT")
            result[key] = value
    return result


def _claim_evidence(claim, observation, result, company, projection, indexes, fiscal_year):
    entry = projector._evidence_row(observation=observation,result=result,company=company,projection=projection,
        source_index=indexes["sources"],raw_index=indexes["raw"],fiscal_year=fiscal_year)
    source = indexes["sources"][claim["source_reference_id"]]
    raw = indexes["raw"][source["raw_asset_id"]]
    attrs = claim["attributes"];locator = claim["locator"]
    event = claim["claim_kind"] == "DETERMINISTIC_8K_ITEM_BRIEF"
    period = attrs.get("context",locator)
    entry.update(source_url=source["source_url"],repo_relative_path=raw["storage_uri"],
        content_sha256=source["raw_asset_id"].split(":",1)[1],accession=source["accession"],document_name=source["document_name"],
        concept_or_section="Item "+attrs["item_code"] if event else locator.get("concept",locator.get("qualified_name","")),
        context_or_dimension=json.dumps({"verified_claim_id":claim["verified_claim_id"],"locator":locator,"attributes":attrs},ensure_ascii=False,sort_keys=True),
        unit="count" if event else claim["unit"],value_raw="",value_normalized="1" if event else claim["value"],
        period_start=period.get("period_start",result["period_start"]),period_end=period.get("period_end",result["period_end"]),
        evidence_quote="Parsed source fact: "+json.dumps({"value":claim["value"],"unit":claim["unit"],"locator":locator},ensure_ascii=False,sort_keys=True))
    return entry


def render_ordinary_run(*, data_root: Path, run_dir: Path, frozen=False):
    if frozen:
        manifest,records,_ = load_frozen_run(run_dir=run_dir,repo_root=data_root)
    else:
        manifest,records,_ = _mechanically_replay_open_run(run_dir=run_dir,repo_root=data_root,require_complete_results=True)
    _need(manifest["requirement_id"] == REQUIREMENT_ID,"ORDINARY_PROJECTION_REQUIREMENT_CHANGED")
    case = replay_case(data_root=data_root,manifest=manifest)
    metric = case["primary_metric_id"]
    results = [r for r in records if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == metric]
    _need(len(results) == 1,"ORDINARY_PROJECTION_PRIMARY_RESULT_NOT_UNIQUE")
    result = results[0];spec = case["compiled_specs"][metric]
    policy = strict_json_file(path=ROOT/POLICY_PATH)
    _need(policy["record_type"] == "ORDINARY_INTEGRATED_PRESENTATION_POLICY" and policy["schema_version"] == 1
          and policy["production_authorized"] is False and policy["confidence_inferred"] is False,
          "ORDINARY_PRESENTATION_POLICY_CHANGED")
    item = policy["metrics"][metric]
    projection = {**item["projection"],**item["spec_overrides"].get(case["spec_paths"][metric],{})}
    is_text = result.get("value_kind") == "TEXT_V1"
    _need(projection["unit"] == spec["compiled"]["canonical_unit"] and (is_text or projection["value_multiplier"] == "1"),
          "ORDINARY_PROJECTION_UNIT_CHANGED")
    company = next(c for c in projector._load_registry(repo_root=data_root) if c["company_id"] == manifest["company_id"])
    annual = prepare_saved_annual_input(repo_root=data_root,company_id=manifest["company_id"])
    period = annual["table_input"]["target_period"]
    _need(period["fiscal_year"] == manifest["target_period"]["fiscal_year"],"ORDINARY_PROJECTION_FISCAL_LABEL_CHANGED")
    indexes = projector._record_indexes(runs=[(manifest,records)])
    trace = indexes["traces"][result["trace_id"]]
    ordered,_ = projector._ordered_observations(trace=trace,observations=indexes["observations"],projection=projection)
    view = {"compiled":{"name":item["name"] or spec["compiled"]["name"],"reported_unit":spec["compiled"]["reported_unit"],"legacy_projection":projection}}
    baseline = {key:"" for key in publication.METRIC_FIELDS}
    baseline.update(form=annual["filing"]["form"],filed_date=annual["filing"]["filingDate"])
    if result["publication"] == "WITHHELD":
        row = dict(baseline);evidence=[]
        row.update(company=company["display_name"],cik=company["primary_cik"],metric_id=metric,metric_name=view["compiled"]["name"],
            unit=projection["unit"],status="WITHHELD",source_class=projection["source_class"],formula=projection.get("formula",""),
            period_start=result["period_start"],period_end=result["period_end"],fiscal_year=str(period["fiscal_year"]),notes=projection.get("notes",""))
    else:
        row,evidence,_ = projector._project_result(result=result,trace=trace,company=company,spec=view,baseline_row=baseline,
            indexes=indexes,fiscal_year=str(period["fiscal_year"]),metric_fields=publication.METRIC_FIELDS)
    if not is_text:
        evidence=[];claims=_claims(case)
        financial_locators=_selected_financial_locators(metric,case.get("selection"))
        for observation in ordered:
            binding=observation["source_binding"]
            identifiers=binding.get("verified_claim_ids",binding.get("matched_verified_claim_ids",[]))
            if identifiers:
                for identity in identifiers:
                    _need(identity in claims,"ORDINARY_PROJECTION_SELECTED_CLAIM_MISSING")
                    evidence.append(_claim_evidence(claims[identity],observation,result,company,projection,indexes,str(period["fiscal_year"])))
            else:
                entry=projector._evidence_row(observation=observation,result=result,company=company,projection=projection,
                    source_index=indexes["sources"],raw_index=indexes["raw"],fiscal_year=str(period["fiscal_year"]))
                entry.update(value_raw=_raw_value(observation,financial_locators,case.get("selection")),
                    context_or_dimension=json.dumps({"source_binding":binding,"source_cells":financial_locators},ensure_ascii=False,sort_keys=True),
                    evidence_quote="Normalized source-derived observation: "+entry["evidence_quote"])
                evidence.append(entry)
        label,note=_period_label(result,period);row["fiscal_period"]=label
        row["notes"]=" ".join([row.get("notes",""),note,"Native state: "+result["publication"]+"; reason: "+result["reason_code"]+"."])
        row["context_or_dimension"]=json.dumps({"scope":trace["calculation_target"]["scope"],"measurement_kind":label,
            "annual_filing_period":period,"selection":case.get("selection"),
            "source_reference_ids":[r["source_reference_id"] for r in case["references"]]},ensure_ascii=False,sort_keys=True)
    else:
        _need(len(evidence)==len(result["text_payload"]["items"]),"ORDINARY_TEXT_EVIDENCE_SET_CHANGED")
    filings=_filings(case["input_binding"])
    accessions=list(dict.fromkeys(e["accession"] for e in evidence))
    known=[filings[a] for a in accessions if a in filings]
    row.update(accession=";".join(accessions),confidence="")
    if known:
        row.update(form=";".join(dict.fromkeys(f["form"] for f in known)),filed_date=";".join(dict.fromkeys(f["filingDate"] for f in known)))
    if metric=="C02":row["source_class"]="PROXY" if known and all(f["form"]=="DEF 14A" for f in known) else "TEXT"
    if annual["fiscal_year_label_resolution"]["metadata_conflict_retained"]:
        row["notes"]+=" Fiscal label follows the explicit issuer definition; original DEI/Company Facts labels remain in the source binding."
    _need(set(row)==set(publication.METRIC_FIELDS) and all(set(e)==set(publication.EVIDENCE_FIELDS) for e in evidence),
          "ORDINARY_PUBLIC_ROW_SCHEMA_CHANGED")
    receipt={"record_type":"ORDINARY_INTEGRATED_ROW_RECEIPT","status":"FROZEN_CANDIDATE" if frozen else "VERIFIED_OPEN_PREVIEW",
        "run_id":manifest["run_id"],"run_status":manifest["status"],"result_id":result["result_id"],
        "primary_metric_id":metric,"source_required_metric_ids":sorted(case["compiled_specs"]),
        "presentation_policy_sha256":sha256_file(path=ROOT/POLICY_PATH),"renderer_sha256":sha256_file(path=Path(__file__)),
        "row_hash":content_hash(value=row),"evidence_hash":content_hash(value=evidence),"evidence_count":len(evidence),
        "source_validation":"FULL_NATIVE_RUN_REPLAY","production_authorized":False}
    return {"row":row,"evidence":evidence,"receipt":{**receipt,"receipt_id":content_hash(value=receipt)},
        "files":{"metrics_matrix.csv":publication._csv_bytes(rows=[row],fieldnames=publication.METRIC_FIELDS),
                 "metric_evidence.csv":publication._csv_bytes(rows=evidence,fieldnames=publication.EVIDENCE_FIELDS)}}
