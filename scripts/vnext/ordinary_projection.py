"""Project source-replayed ordinary Runs, including dependencies and claims.

An OPEN preview and a frozen candidate carry different receipt states. Neither
writes a publication or changes a Spec. Composite evidence exposes each source
fact rather than presenting the computed ratio as a verbatim source amount.
"""
import json
from pathlib import Path

from . import projector, csv_output
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .normal_annual_input_v2 import prepare_saved_annual_input
from .normal_numeric_projection import _period_label, _objects, _filings, _selected_financial_locators, _evidence_context, _raw_value
from .normal_run_v3 import A05_FORMULA_POLICY, REQUIREMENT_ID, replay_case
from .run_store import _mechanically_replay_open_run, load_frozen_run


POLICY_PATH = "config/ordinary_public_projection_v1.json"
A05_FORMULA_TEXT = ("Selected net income / ((current period-end total assets + "
                    "prior period-end total assets) / 2)")


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


def render_ordinary_run(*, data_root: Path, run_dir: Path, frozen=False,
                        _return_replay_context=False):
    if frozen:
        manifest,records,_ = load_frozen_run(run_dir=run_dir,repo_root=data_root)
    else:
        manifest,records,_ = _mechanically_replay_open_run(run_dir=run_dir,repo_root=data_root,require_complete_results=True)
    _need(manifest["requirement_id"] in {REQUIREMENT_ID, 'issue_28_v14'},"ORDINARY_PROJECTION_REQUIREMENT_CHANGED")
    case = replay_case(data_root=data_root,manifest=manifest)
    rendered = render_ordinary_records(data_root=data_root, manifest=manifest,
        records=records, case=case,
        receipt_status="FROZEN_CANDIDATE" if frozen else "VERIFIED_OPEN_PREVIEW",
        source_validation="FULL_NATIVE_RUN_REPLAY")
    if _return_replay_context:
        # Same-operation callers can consume the Run/source replay already
        # performed above. A later invocation still starts from disk.
        rendered["replay_context"] = {"manifest":manifest,"records":records,"case":case}
    return rendered


def render_ordinary_records(*, data_root, manifest, records, case,
                            receipt_status, source_validation, prepared_annual_input=None):
    """Project already calculated records; the caller owns validation and state.

    This renderer does not load a Requirement or replay a Run. Its receipt
    names the caller's actual checks rather than granting native replay credit.
    """
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
    same_unit = projection["unit"] == spec["compiled"]["canonical_unit"] and (is_text or projection["value_multiplier"] == "1")
    percent_unit = (spec["compiled"]["canonical_unit"] == "ratio" and projection["unit"] == "percent"
        and projection["value_multiplier"] == "100" and spec["compiled"]["legacy_projection"].get("unit") == "percent"
        and spec["compiled"]["legacy_projection"].get("value_multiplier") == "100")
    _need(same_unit or percent_unit,
          "ORDINARY_PROJECTION_UNIT_CHANGED")
    company = next(c for c in projector._load_registry(repo_root=data_root) if c["company_id"] == manifest["company_id"])
    annual = (prepare_saved_annual_input(repo_root=data_root,company_id=manifest["company_id"])
              if prepared_annual_input is None else prepared_annual_input)
    period = annual["table_input"]["target_period"]
    _need(period["fiscal_year"] == manifest["target_period"]["fiscal_year"],"ORDINARY_PROJECTION_FISCAL_LABEL_CHANGED")
    income = case.get('prepared_income_input')
    income_period_proven = False
    if income is not None:
        income_period_proven = (metric in {'B01','B03'}
            and income['company_id'] == manifest['company_id']
            and income['annual_input'] == annual.get('original_input',annual)
            and income['statement_period'] == manifest['target_period']
            and all(result[key] == income['statement_period'][key]
                    for key in ('period_start','period_end'))
            and income['financial_cross_entity_combination_authorized'] is False
            and period['period_start'] <= result['period_start'] < result['period_end'] == period['period_end'])
        _need(income_period_proven, 'ORDINARY_PROJECTION_INCOME_PERIOD_PROOF_CHANGED')
    if prepared_annual_input is not None:
        from .traits import repository_company_ciks
        _need(annual['company_id'] == manifest['company_id']
              and str(int(annual['entity'])) in {str(int(c)) for c in
                  repository_company_ciks(repo_root=data_root, company_id=manifest['company_id'])},
              'ORDINARY_PROJECTION_PREPARED_SUBJECT_CHANGED')
        _need(annual['filing']['reportDate'] == period['period_end']
              and result['period_end'] == period['period_end']
              and (result['period_start'] == period['period_start'] or
                   result['period_start'] == result['period_end'] or income_period_proven),
              'ORDINARY_PROJECTION_PREPARED_PERIOD_CHANGED')
    indexes = projector._record_indexes(runs=[(manifest,records)])
    trace = indexes["traces"][result["trace_id"]]
    if income_period_proven and result.get('value') is not None:
        checked = {c['observation_id'] for c in case.get('income_observation_checks',[])}
        _need(set(trace['input_observation_ids']) <= checked,
              'ORDINARY_PROJECTION_INCOME_OBSERVATION_PROOF_MISSING')
    ordered,_ = projector._ordered_observations(trace=trace,observations=indexes["observations"],projection=projection)
    presentation = case.get('presentation_policy')
    _need(presentation in {None, A05_FORMULA_POLICY},
          'ORDINARY_PRESENTATION_SUCCESSOR_UNKNOWN')
    if presentation is not None:
        _need(metric == 'A05' and projection.get('formula','') == '' and
              spec['compiled']['canonical_unit'] == 'ratio',
              'ORDINARY_A05_PRESENTATION_SCOPE_CHANGED')
        route = strict_json_file(path=data_root/'catalog/deterministic_metrics.json')['metrics']['A05']
        branches = route['branches']
        _need(len(branches) == 1 and branches[0]['branch_id'] == 'average_assets'
              and branches[0]['formula_id'] == 'average_denominator_ratio'
              and [component['role'] for component in branches[0]['components']] ==
                  ['net_income','assets_current','assets_prior'],
              'ORDINARY_A05_APPROVED_FORMULA_CHANGED')
        if result['publication'] == 'PUBLISHED':
            if result['applicability'] == 'N_A_STRUCTURAL':
                _need(result['quality'] == 'NONE' and result['value'] is None
                      and result['reason_code'] == 'TRAIT_NOT_APPLICABLE'
                      and not ordered,
                      'ORDINARY_A05_STRUCTURAL_RESULT_CHANGED')
            else:
                _need(result['applicability'] == 'APPLICABLE'
                      and result['quality'] == 'EXACT'
                      and result['value'] is not None
                      and len(ordered) == 1
                      and ordered[0]['source_binding'].get('selected_branch_id') ==
                          'average_assets',
                      'ORDINARY_A05_SELECTED_BRANCH_CHANGED')
                projection = {**projection, 'formula': A05_FORMULA_TEXT}
    view = {"compiled":{"name":item["name"] or spec["compiled"]["name"],"reported_unit":spec["compiled"]["reported_unit"],"legacy_projection":projection}}
    baseline = {key:"" for key in csv_output.METRIC_FIELDS}
    baseline.update(company=company["display_name"],cik=company["primary_cik"],metric_id=metric,
        metric_name=view["compiled"]["name"],unit=projection["unit"],status=result["quality"],
        source_class=projection["source_class"],formula=projection.get("formula",""),
        period_start=result["period_start"],period_end=result["period_end"],fiscal_year=str(period["fiscal_year"]),
        notes=projection.get("notes",""),form=annual["filing"]["form"],filed_date=annual["filing"]["filingDate"])
    if result["publication"] == "WITHHELD":
        row = dict(baseline);evidence=[]
        row.update(company=company["display_name"],cik=company["primary_cik"],metric_id=metric,metric_name=view["compiled"]["name"],
            unit=projection["unit"],status="WITHHELD",source_class=projection["source_class"],formula=projection.get("formula",""),
            period_start=result["period_start"],period_end=result["period_end"],fiscal_year=str(period["fiscal_year"]),notes=projection.get("notes",""))
    else:
        row,evidence,_ = projector._project_result(result=result,trace=trace,company=company,spec=view,baseline_row=baseline,
            indexes=indexes,fiscal_year=str(period["fiscal_year"]),metric_fields=csv_output.METRIC_FIELDS)
    if metric in {'B13', 'D04'} and result['reason_code'] in {
            'B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE', 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE'}:
        from .capacity_run import project_defined_absence
        row, evidence = project_defined_absence(case=case, result=result, row=row, company=company)
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
                if "table_locator" in binding:
                    entry.update(value_raw=binding["reported_raw_text"],
                        context_or_dimension=json.dumps({"source_binding":binding,"source_cells":binding["source_witnesses"]},ensure_ascii=False,sort_keys=True),
                        evidence_quote="Source table cell: "+binding["reported_raw_text"])
                if metric == 'B13' and 'quantity_statement' in binding:
                    proof = binding['quantity_statement']
                    entry.update(value_raw=' '.join(x for x in (proof['reported_number'], proof['reported_scale']) if x),
                        evidence_quote=proof['statement_text'],
                        extraction_method='source_verified_annual_production_quantity',
                        context_or_dimension=json.dumps(binding, ensure_ascii=False, sort_keys=True))
                evidence.append(entry)
        label,note=_period_label(result,period);row["fiscal_period"]=label
        row["notes"]=" ".join([row.get("notes",""),note,"Native state: "+result["publication"]+"; reason: "+result["reason_code"]+"."])
        row["context_or_dimension"]=json.dumps({"scope":trace["calculation_target"]["scope"],"measurement_kind":label,
            "annual_filing_period":period,"selection":case.get("selection"),
            "source_reference_ids":[r["source_reference_id"] for r in case["references"]]},ensure_ascii=False,sort_keys=True)
    elif result['text_payload'] is not None:
        _need(len(evidence)==len(result["text_payload"]["items"]),"ORDINARY_TEXT_EVIDENCE_SET_CHANGED")
    elif metric in {'B13', 'D04'}:
        structural = case['selection']['status'] == 'N_A_STRUCTURAL'
        _need((structural and result['applicability'] == 'N_A_STRUCTURAL' and not evidence)
              or (case['selection']['status'] == ('NOT_AVAILABLE_SEC' if metric == 'B13' else 'TEXT_QUAL')
                  and result['reason_code'] in {'B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE',
                                                'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE'}
                  and len(evidence) == len(case['text_arguments']['source']['documents'])),
              'B13_NULL_TEXT_PROJECTION_CHANGED')
        if structural:
            row['notes'] = 'Outside the approved B13 company scope. No disclosure-absence or utilization claim is made.'
    else:
        raise ValueError('ORDINARY_NULL_TEXT_PROJECTION_UNSUPPORTED')
    filings=_filings(case["input_binding"])
    accessions=list(dict.fromkeys(e["accession"] for e in evidence))
    known=[filings[a] for a in accessions if a in filings]
    row.update(accession=";".join(accessions),confidence="")
    if known:
        row.update(form=";".join(dict.fromkeys(f["form"] for f in known)),filed_date=";".join(dict.fromkeys(f["filingDate"] for f in known)))
    if metric=="C02":row["source_class"]="PROXY" if known and all(f["form"]=="DEF 14A" for f in known) else "TEXT"
    if annual["fiscal_year_label_resolution"]["metadata_conflict_retained"]:
        row["notes"]+=" Fiscal label follows the explicit issuer definition; original DEI/Company Facts labels remain in the source binding."
    recorded = case["admission"]["source_credit"] == "RECORDED_TEST_ONLY"
    if case['input_binding'].get('mode') == 'RECORDED_TEST_ONLY':
        row['notes'] += ' Source classifications use recorded test responses; no real model execution credit.'
    if recorded:
        row["notes"] += " Recorded source refresh test using preexisting SEC content; no new SEC acquisition."
    elif case["admission"].get("real_sec_credit") is True:
        row["notes"] += " Selected source inputs include new SEC acquisition records; each input retains its own acquisition identity."
    _need(set(row)==set(csv_output.METRIC_FIELDS) and all(set(e)==set(csv_output.EVIDENCE_FIELDS) for e in evidence),
          "ORDINARY_PUBLIC_ROW_SCHEMA_CHANGED")
    receipt={"record_type":"ORDINARY_INTEGRATED_ROW_RECEIPT","status":receipt_status,
        "run_id":manifest["run_id"],"run_status":manifest["status"],"result_id":result["result_id"],
        "primary_metric_id":metric,"source_required_metric_ids":sorted(case["compiled_specs"]),
        "presentation_policy_sha256":sha256_file(path=ROOT/POLICY_PATH),"renderer_sha256":sha256_file(path=Path(__file__)),
        "row_hash":content_hash(value=row),"evidence_hash":content_hash(value=evidence),"evidence_count":len(evidence),
        "source_validation":source_validation,"production_authorized":False}
    if 'mode' in case['input_binding']:
        receipt['semantic_assessment_mode'] = case['input_binding']['mode']
    if recorded:
        receipt.update(source_credit="RECORDED_TEST_ONLY",source_checkpoint_id=case["admission"]["checkpoint_id"],
                       real_sec_credit=False)
    elif "checkpoint_id" in case["admission"]:
        receipt.update(source_credit=case["admission"]["source_credit"],
                       source_checkpoint_id=case["admission"]["checkpoint_id"],
                       real_sec_credit=case["admission"]["real_sec_credit"],
                       selected_new_request_attempt_ids=case["admission"]["selected_new_request_attempt_ids"])
    rendered = {"row":row,"evidence":evidence,"receipt":{**receipt,"receipt_id":content_hash(value=receipt)},
        "files":{"metrics_matrix.csv":csv_output._csv_bytes(rows=[row],fieldnames=csv_output.METRIC_FIELDS),
                 "metric_evidence.csv":csv_output._csv_bytes(rows=evidence,fieldnames=csv_output.EVIDENCE_FIELDS)}}
    return rendered
