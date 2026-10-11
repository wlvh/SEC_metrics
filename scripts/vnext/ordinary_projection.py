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


def _selected_proxy_display(*, case, annual, evidence):
    """Display the explicit C03 source even when its amount is withheld.

    The producer owns proxy selection and validates its metadata/source
    proofs. This check connects that selected filing to the same input
    binding, reporter and actual primary reference used by the saved case.
    """
    selected=case.get('selected_proxy')
    if selected is None:
        return None
    from sec_urls import accession_document_url
    _need(case['primary_metric_id']=='C03' and type(selected) is dict
          and {'accessionNumber','primaryDocument','form','filingDate'}<=set(selected)
          and selected['form']=='DEF 14A', 'ORDINARY_SELECTED_PROXY_DISPLAY_INVALID')
    identity={k:selected[k] for k in ('accessionNumber','form','filingDate')}
    _need(_filings(case['input_binding']).get(selected['accessionNumber'])==identity,
          'ORDINARY_SELECTED_PROXY_METADATA_NOT_BOUND')
    url=accession_document_url(cik=int(annual['entity']),accession=selected['accessionNumber'],
                              document_name=selected['primaryDocument'])
    matching=[r for r in case['references'] if r.get('company_id')==annual['company_id']
              and r.get('accession')==selected['accessionNumber']
              and r.get('document_name')==selected['primaryDocument']
              and r.get('source_url')==url and r.get('source_role')=='governance_proxy']
    _need(len(matching)==1 and all(e['accession']==selected['accessionNumber'] for e in evidence),
          'ORDINARY_SELECTED_PROXY_SOURCE_NOT_BOUND')
    return identity


def _need(condition, reason):
    if not condition:raise ValueError(reason)


_SCOPE_DISPLAY_KEYS = ('scope_id', 'method', 'status', 'complete_scope_proven', 'selected_fiscal_column_year')


def _display_selection(selection):
    """Public-row context names a revenue scope by identity and outcome only.

    The full scope (prepared annual input, native report rows, statement text,
    cell proofs) stays in the saved input binding and records. The CSV context
    keeps its scope_id, method and status, as the historical company entry
    already does, so one row does not carry hundreds of kilobytes of copied
    source material.
    """
    if not isinstance(selection, dict) or not isinstance(selection.get('revenue_scope'), dict):
        return selection
    scope = selection['revenue_scope']
    return {**selection, 'revenue_scope': {key: scope[key] for key in _SCOPE_DISPLAY_KEYS if key in scope}}


def _reporting_company_view(*, data_root, company, annual, calculation_target,
                            source_references=(), allow_metadata_only=False,
                            event_input_binding=None, event_metric_id=None,
                            registered_event_period_proven=False):
    """Use the verified filing issuer in rows without changing the registry."""
    from .traits import repository_company_ciks
    entity = annual.get('entity')
    _need(isinstance(entity, str) and entity.isdigit() and int(entity) > 0
          and str(int(entity)) in {str(int(cik)) for cik in
              repository_company_ciks(repo_root=data_root, company_id=company['company_id'])},
          'ORDINARY_PROJECTION_REPORTER_NOT_REGISTERED')
    target_entity = calculation_target.get('entity')
    _need(annual.get('company_id') == company['company_id']
          and calculation_target.get('company_id') == company['company_id']
          and 'entity' in calculation_target and 'accession' in calculation_target
          and (target_entity is None or isinstance(target_entity, str)
               and target_entity.isdigit() and int(target_entity) == int(entity)),
          'ORDINARY_PROJECTION_TRACE_SUBJECT_CHANGED')
    # Existing Calculator targets explicitly allow absent issuer/filing facts.
    # Filled fields must agree; null fields rely on the verified annual input
    # rather than inventing facts or modifying the original Trace.
    _need(calculation_target['accession'] is None
          or calculation_target['accession'] == annual['filing']['accessionNumber'],
          'ORDINARY_PROJECTION_TRACE_FILING_CHANGED')
    subject = annual.get('subject_policy', {})
    _need(subject.get('cross_entity_combination_authorized') is False,
          'ORDINARY_PROJECTION_REPORTER_SCOPE_NOT_PROVEN')
    if target_entity is None or calculation_target['accession'] is None:
        from sec_urls import accession_document_url, submissions_url
        filing = annual['filing']
        primary_url = accession_document_url(cik=int(entity),
            accession=filing['accessionNumber'], document_name=filing['primaryDocument'])
        primary = any(ref.get('company_id') == company['company_id']
            and ref.get('accession') == filing['accessionNumber']
            and ref.get('source_url') == primary_url for ref in source_references)
        inventory = any(ref.get('company_id') == company['company_id']
            and ref.get('source_url') == submissions_url(cik=int(entity))
            for ref in source_references)
        event_source = (not primary and not (allow_metadata_only and inventory)
            and event_metric_id in {'C01','E02','E03','E04','E05'}
            and event_input_binding is not None
            and event_input_binding.get('record_type')=='HISTORICAL_EVENT_SOURCE_INPUT'
            and _event_reporter_source(
                company=company, annual=annual, binding=event_input_binding,
                metric_id=event_metric_id, references=source_references,
                registered_period_proven=registered_event_period_proven))
        _need(primary or event_source or allow_metadata_only and inventory,
              'ORDINARY_PROJECTION_REPORTER_SOURCE_NOT_PROVEN')
    return {**company, 'primary_cik': str(int(entity))}


def _event_reporter_source(*, company, annual, binding, metric_id, references,
                          registered_period_proven=False):
    """Use the event case's existing inventory/body set, without reading a 10-K.

    Source bytes and completeness are checked by the source reader/writer.
    This presentation check links those same references to the selected issuer;
    it does not confirm an event or change the original nullable Trace.
    """
    from sec_urls import accession_document_url, submissions_url
    company_id=company['company_id']; entity=annual['entity']
    window=binding.get('event_window',{})
    prepared=binding.get('prepared_input',{})
    _need(binding.get('record_type')=='HISTORICAL_EVENT_SOURCE_INPUT'
          and binding.get('metric_id')==metric_id
          and binding.get('financial_cross_entity_combination_authorized') is False
          and prepared==annual,
          'ORDINARY_PROJECTION_REPORTER_EVENT_SOURCE_NOT_PROVEN')
    registered=binding.get('registered_event_scope')
    _need((registered is None and window==annual['table_input']['target_period'])
        or registered is not None and registered_period_proven is True
        and annual['subject_policy']['mode']=='SUCCESSOR_REGISTRANT_ONLY'
        and window==registered.get('window'),
        'ORDINARY_PROJECTION_REPORTER_EVENT_SOURCE_NOT_PROVEN')
    refs={r.get('source_reference_id'):r for r in references}
    inventory_url=submissions_url(cik=int(entity)); prefix=inventory_url[:-5]+'-submissions-'
    inventories=[r for r in references if r.get('company_id')==company_id
        and r.get('source_url')==inventory_url]
    _need(len(inventories)==1,'ORDINARY_PROJECTION_REPORTER_EVENT_SOURCE_NOT_PROVEN')
    # For a registered union the existing period proof has already checked all
    # registered issuers and manifests. The display still needs this reporter's
    # own inventory/set; it cannot borrow the other issuer's inventory.
    sets=binding.get('source_set_manifests',[])
    if registered is not None:
        sets=[item for item in sets if (refs.get(item.get('inventory_source_reference_id')) or {})
              .get('source_url','').startswith(inventory_url[:-5])]
    _need(bool(sets),'ORDINARY_PROJECTION_REPORTER_EVENT_SOURCE_NOT_PROVEN')
    for item in sets:
        inventory=refs.get(item.get('inventory_source_reference_id'))
        _need(item.get('record_type')=='SOURCE_SET_MANIFEST'
            and item.get('company_id')==company_id
            and item.get('source_role')=='fy_8k_item_inventory'
            and set(item.get('form_types',[]))=={'8-K','8-K/A'}
            and (registered is not None or item.get('discovery_policy') in
                 {'PINNED_SUBMISSIONS','PINNED_SUBMISSIONS_SHARD_UNION_V1'})
            and item.get('fiscal_or_date_window')=={k:window[k] for k in ('period_start','period_end')}
            and inventory is not None and inventory.get('company_id')==company_id
            and (inventory.get('source_url')==inventory_url
                or inventory.get('source_role')=='sec_submissions_history'
                and inventory.get('source_url','').startswith(prefix))
            and item.get('sec_submissions_inventory_hash')==inventory.get('raw_asset_id'),
            'ORDINARY_PROJECTION_REPORTER_EVENT_SOURCE_NOT_PROVEN')
        for ref_id in item.get('ordered_source_reference_ids',[]):
            ref=refs.get(ref_id)
            _need(ref is not None and ref.get('company_id')==company_id
                and ref.get('accession') and ref.get('document_name')
                and ref.get('source_url')==accession_document_url(cik=int(entity),
                    accession=ref['accession'],document_name=ref['document_name']),
                'ORDINARY_PROJECTION_REPORTER_EVENT_SOURCE_NOT_PROVEN')
    return True


def _reported_average_period(*, case, result, annual, records):
    """Bind A03's disclosed average to its observation, not the year label.

    The existing source resolver owns the economic reading; saved records and
    source proofs are checked by the writer. This only checks that its actual
    measurement window is faithfully carried through the shared CSV path.
    """
    if result['metric_id'] != 'A03' or result.get('value') is None:
        return False
    spec = case['compiled_specs']['A03']['compiled']
    _need(spec.get('quality_rule',{}).get('measurement_period') ==
          'source_disclosed_average_ending_at_filing_end',
          'ORDINARY_PROJECTION_AVERAGE_PERIOD_SPEC_CHANGED')
    fact = (case.get('selection') or {}).get('source_fact')
    if fact is None:
        return False
    traces = [r for r in records if r['record_type'] == 'EXECUTION_TRACE'
              and r['trace_id'] == result['trace_id']]
    _need(len(traces) == 1, 'ORDINARY_PROJECTION_AVERAGE_PERIOD_TRACE_CHANGED')
    observations = [r for r in records if r['record_type'] == 'VERIFIED_OBSERVATION'
                    and r['observation_id'] in traces[0]['input_observation_ids']]
    _need(len(observations) == 1,'ORDINARY_PROJECTION_AVERAGE_PERIOD_OBSERVATION_CHANGED')
    observation = observations[0]; binding = observation['source_binding']
    entity = binding.get('entity')
    filing = annual['table_input']['target_period']
    actual = binding.get('actual_measurement_period', {})
    refs = {r['source_reference_id']:r for r in case['references']}
    reference = refs.get(binding.get('source_reference_id'))
    _need(fact.get('status') == 'SINGLE_SOURCE_SEMANTIC_FACT'
          and not fact.get('unresolved') and fact.get('target_filing_period') == filing
          and binding.get('source_fact_hash') == content_hash(value=fact)
          and binding.get('measurement_time_basis') == 'SOURCE_DISCLOSED_AVERAGE'
          and binding.get('filing_period') == filing
          and observation['company_id'] == annual['company_id']
          and observation['metric_id'] == 'A03' and observation['semantic_role'] == 'lcr_disclosed_average'
          and observation['value'] == result['value'] == fact['value']
          and observation['unit'] == result['unit'] == 'ratio'
          and reference is not None and reference['company_id'] == annual['company_id']
          and reference['raw_asset_id'] == binding.get('raw_asset_id') == 'sha256:'+fact['source_sha256']
          and reference['accession'] == binding.get('accession') == annual['filing']['accessionNumber']
          and type(entity) in (str,int) and str(entity).isdigit()
          and str(int(entity)) == str(int(annual['entity']))
          and all(actual.get(k) == result[k] == observation[k] == fact['measurement_period'][k]
                  for k in ('period_start','period_end'))
          and case['target_period']['fiscal_year'] == filing['fiscal_year']
          and filing['period_start'] <= result['period_start'] < result['period_end'] == filing['period_end'],
          'ORDINARY_PROJECTION_AVERAGE_PERIOD_PROOF_CHANGED')
    return True


def _registered_event_period(*, data_root, manifest, annual, case, result):
    """Keep the approved event lookback distinct from the reporting year."""
    if case['primary_metric_id'] not in {'C01', 'E02', 'E03', 'E04', 'E05'}:
        return False
    binding = case['input_binding']
    if 'component' in binding:
        binding = binding['component'].get('input_binding', {})
    scope = binding.get('registered_event_scope')
    if scope is None:
        return False
    from sec_urls import submissions_url
    from .public_projection import event_target_period
    from .traits import repository_company_ciks
    rules = Path(case.get('rules_root', ROOT))
    catalog_path = rules / 'catalog/zero_ai_public_projection.json'
    company = next(row for row in projector._load_registry(repo_root=rules)
                   if row['company_id'] == manifest['company_id'])
    _need(annual['company_id'] == company['company_id']
          and annual['entity'] == company['primary_cik']
          and annual['subject_policy']['mode'] == 'SUCCESSOR_REGISTRANT_ONLY'
          and company['entity_continuity_status'] == 'successor_predecessor',
          'ORDINARY_PROJECTION_EVENT_SCOPE_CHANGED')
    period = annual['table_input']['target_period']
    expected = event_target_period(target_period=period,
        continuity_status=company['entity_continuity_status'], catalog=strict_json_file(path=catalog_path))
    _need(scope.get('window') == expected
          and binding.get('event_window', binding.get('target_period')) == expected
          and manifest['target_period'] in (period, expected)
          and all(result[key] == expected[key] for key in ('period_start', 'period_end')),
          'ORDINARY_PROJECTION_EVENT_PERIOD_PROOF_CHANGED')
    ciks = repository_company_ciks(repo_root=rules, company_id=company['company_id'])
    _need(scope.get('registered_ciks') == ciks
          and scope.get('financial_cross_entity_combination_authorized') is False
          and scope.get('company_registry_sha256') == sha256_file(path=data_root/'config/company_registry.csv')
          == sha256_file(path=rules/'config/company_registry.csv')
          and scope.get('event_projection_catalog_sha256') == sha256_file(path=catalog_path),
          'ORDINARY_PROJECTION_EVENT_SCOPE_CHANGED')
    per_cik = scope.get('per_cik_sources', [])
    _need([row.get('cik') for row in per_cik] == ciks, 'ORDINARY_PROJECTION_EVENT_SCOPE_CHANGED')
    references = {row['source_reference_id']: row for row in case['references']}
    sets = {row['source_set_manifest_id']: row for row in binding.get('source_set_manifests', [])}
    window = {key: expected[key] for key in ('period_start', 'period_end')}
    for row in per_cik:
        ref = row['inventory_source_reference']
        selected_sets = [sets.get(key) for key in row.get('source_set_manifest_ids', [])]
        inventory_prefix = submissions_url(cik=int(row['cik']))[:-5]
        def same_issuer_inventory(item):
            if item is None:
                return False
            inventory = references.get(item.get('inventory_source_reference_id'))
            return inventory is not None and inventory['company_id'] == company['company_id'] and (
                inventory == ref or inventory.get('source_role') == 'sec_submissions_history'
                and inventory['source_url'].startswith(inventory_prefix + '-submissions-'))
        _need(row['source_window'] == expected and ref['company_id'] == company['company_id']
              and ref['source_url'] == submissions_url(cik=int(row['cik']))
              and references.get(ref['source_reference_id']) == ref
              and selected_sets and all(item is not None and item['company_id'] == company['company_id']
                  and item['fiscal_or_date_window'] == window and same_issuer_inventory(item)
                  for item in selected_sets),
              'ORDINARY_PROJECTION_EVENT_SCOPE_CHANGED')
    return True


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
    event_period_proven = False
    if prepared_annual_input is not None:
        from .traits import repository_company_ciks
        _need(annual['company_id'] == manifest['company_id']
              and str(int(annual['entity'])) in {str(int(c)) for c in
                  repository_company_ciks(repo_root=data_root, company_id=manifest['company_id'])},
              'ORDINARY_PROJECTION_PREPARED_SUBJECT_CHANGED')
        event_period_proven = _registered_event_period(
            data_root=data_root, manifest=manifest, annual=annual, case=case, result=result)
        average_period_proven = _reported_average_period(
            case=case,result=result,annual=annual,records=records)
        _need(annual['filing']['reportDate'] == period['period_end']
              and result['period_end'] == period['period_end']
              and (result['period_start'] == period['period_start'] or
                   result['period_start'] == result['period_end'] or income_period_proven
                   or event_period_proven or average_period_proven),
              'ORDINARY_PROJECTION_PREPARED_PERIOD_CHANGED')
    indexes = projector._record_indexes(runs=[(manifest,records)])
    trace = indexes["traces"][result["trace_id"]]
    company = _reporting_company_view(data_root=data_root, company=company,
        annual=annual, calculation_target=trace['calculation_target'],
        source_references=case['references'],
        allow_metadata_only=result['value'] is None and result.get('text_payload') is None,
        event_input_binding=case.get('input_binding'), event_metric_id=case['primary_metric_id'],
        registered_event_period_proven=event_period_proven)
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
            "annual_filing_period":period,"selection":_display_selection(case.get("selection")),
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
    selected_proxy=_selected_proxy_display(case=case,annual=annual,evidence=evidence)
    if selected_proxy is not None:
        row.update(form=selected_proxy['form'],filed_date=selected_proxy['filingDate'],
                   accession=selected_proxy['accessionNumber'])
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
        receipt.update(source_credit="RECORDED_TEST_ONLY",source_checkpoint_id=case["admission"].get("checkpoint_id"),
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
