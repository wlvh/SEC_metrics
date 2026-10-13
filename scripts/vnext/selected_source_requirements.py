"""Read-only source preflight for one selected annual B01/B02/B03 task.

This names source dependencies from existing saved metadata, not financial
answers or a fetch allowance. Report end is an SEC metadata date; fiscal-year
labels, if established, come from the original annual DEI contexts.
"""
from datetime import date, timedelta
from pathlib import Path

from sec_http import request_log_attempt_id
from sec_urls import (accession_directory_url, accession_document_url,
                      companyfacts_url, submissions_file_url, submissions_url)
from .canonical import content_hash, sha256_file, strict_json_loads
from .normal_annual_input import _cik, annual_period
from .ordinary_registry_scope import registered_company_row
from .normal_history_catalog import load_history_for_period
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .normal_source_requirements import _Requirements, _instance_names, _same_source_observation

METRIC_IDS = frozenset({'B01', 'B02', 'B03'})
SOURCE_METRIC_IDS = METRIC_IDS | frozenset({'E01'})


def _need(condition, reason):
    if not condition:
        raise ValueError('SELECTED_SOURCE_' + reason)


def _limitation(errors, phase, error, **context):
    # The saved metadata reader can expose missing/wrong-shaped fields as
    # KeyError/TypeError. Report this layer explicitly, never disclosure absence.
    category = ('SOURCE_SCHEMA_OR_READER_ERROR' if isinstance(error, (KeyError, TypeError))
                else getattr(error, 'category', 'SOURCE_INTEGRITY_ERROR'))
    errors.append({'phase':phase, 'reason':str(error),
                   'error_type':type(error).__name__,
                   'category':category, **context})


def _component_source_observation_matches(left, right, *, facts_url):
    if _same_source_observation(left, right):
        return True
    # Company Facts spans filings. Annual and event readers can attach the
    # selected filing or no filing; both original component proofs remain.
    # Only that exact registered aggregate permits this contextual difference.
    if left.get('source_url') != facts_url or right.get('source_url') != facts_url:
        return False
    return _same_source_observation(
        {k:v for k,v in left.items() if k!='accession'},
        {k:v for k,v in right.items() if k!='accession'})


def _catalog_requirements(plan, selection):
    """Keep every actual metadata dependency, including predecessor selection."""
    def read_catalog(cik, names):
        _need(bool(names), 'CATALOG_NAMES_MISSING')
        source = plan.require(submissions_url(cik=int(cik)),
            'selected_submissions_inventory', 'application/json', 'SUBMISSIONS-'+str(cik))
        if source is not None:
            payload = strict_json_loads(text=source['raw_bytes'].decode('utf-8'))
            _need(type(payload) is dict and 'cik' in payload and _cik(payload['cik']) == _cik(cik), 'SUBMISSIONS_ENTITY_CONFLICT')
        for name in names[1:]:
            source = plan.require(submissions_file_url(file_name=name),
                'selected_submissions_history', 'application/json')
            if source is not None:
                payload = strict_json_loads(text=source['raw_bytes'].decode('utf-8'))
                _need(type(payload) is dict and ('cik' not in payload or _cik(payload['cik']) == _cik(cik)),
                      'HISTORY_ENTITY_CONFLICT')
    read_catalog(selection['reporting_cik'], selection['loaded_inventories'])
    if selection.get('period_registrant'):
        read_catalog(plan.company['primary_cik'],
            selection['period_registrant']['primary_catalog']['loaded_inventories'])


def _annual_requirements(plan, filing, role, errors):
    """Keep the entire selected primary/index/instance set; never select an answer."""
    cik, accession = plan.company['primary_cik'], filing['accessionNumber']
    primary_url = accession_document_url(cik=int(cik), accession=accession,
                                         document_name=filing['primaryDocument'])
    primary = plan.require(primary_url, role+'_primary', 'text/html', accession)
    index_url = accession_directory_url(cik=int(cik), accession=accession)
    index = plan.require(index_url, role+'_accession_index', 'application/json', accession)
    documents = []
    if index is None:
        errors.append({'phase':'ACCESSION_INDEX', 'accession':accession,
            'source_url':index_url, 'reason':'INSTANCE_DOCUMENT_NAMES_NOT_YET_DISCOVERED',
            'category':'SOURCE_UNAVAILABLE'})
    else:
        try:
            names = _instance_names(strict_json_loads(text=index['raw_bytes'].decode('utf-8')),
                                    plan.company, filing)
            for name in names:
                source = plan.require(accession_document_url(cik=int(cik),
                    accession=accession, document_name=name), role+'_instance',
                    'application/xml', accession)
                if source is not None:documents.append(source)
        except ValueError as error:
            _limitation(errors, 'ACCESSION_INDEX', error, accession=accession)
    period = None
    if filing['form'] == '10-K' and primary is not None:
        try:
            period = annual_period(raw=primary['raw_bytes'], cik=int(cik), filing=filing,
                                   dei_release='YEAR_QUARTER_OR_DATE')
        except ValueError as error:
            _limitation(errors, 'ANNUAL_IDENTITY', error, accession=accession)
    return {'filing':filing, 'primary_url':primary_url, 'primary':primary,
            'instances':documents, 'period':period}


def _prior_alternative(plan, prior, current_period, errors):
    """The existing B02 native-instance alternative, with exact annual dates.

    This never excuses a failed GET, an amendment primary or a missing target.
    Every declared instance and its index must be present. No auditor meaning
    is asserted: B02 needs the prior annual context, not an auditor decision.
    """
    item = plan.requests[prior['primary_url']]
    if item['saved_status'] != 'MISSING_SAVED_SOURCE' or current_period is None:
        return
    filing, cik = prior['filing'], int(plan.company['primary_cik'])
    prefix = accession_directory_url(cik=cik, accession=filing['accessionNumber'])
    if (plan.requests[prefix]['saved_status'] != 'VERIFIED_SAVED_SOURCE'
        or not prior['instances']
        or any(r['saved_status'] != 'VERIFIED_SAVED_SOURCE' for r in plan.requests.values()
               if r['accession'] == filing['accessionNumber'] and 'prior_annual_instance' in r['roles'])):
        return
    try:
        periods = [annual_period(raw=s['raw_bytes'], cik=cik, filing=filing,
                                 dei_release='YEAR_QUARTER_OR_DATE') for s in prior['instances']]
        _need(all(p == periods[0] for p in periods), 'PRIOR_NATIVE_PERIOD_CONFLICT')
        _need(date.fromisoformat(periods[0]['period_end']) + timedelta(days=1)
              == date.fromisoformat(current_period['period_start']), 'PRIOR_NOT_ADJACENT')
        item['alternative_dependency'] = {'status':'VERIFIED_PRIOR_NATIVE_INSTANCE',
            'prior_period':periods[0],
            'source_reference_ids':[s['source_reference']['source_reference_id'] for s in prior['instances']],
            'source_acquisition_credit':False, 'metric_executed':False}
    except ValueError as error:
        _limitation(errors, 'PRIOR_NATIVE_ALTERNATIVE', error, accession=filing['accessionNumber'])


def discover_selected_annual_requirements(*, repo_root, company_id, report_end, metric_ids):
    """Inspect one task's saved source bytes; no writes, calls or Calculator."""
    _need(type(report_end) is str and len(report_end)==10, 'REPORT_END_INVALID')
    _need(date.fromisoformat(report_end).isoformat()==report_end, 'REPORT_END_INVALID')
    source = Path(repo_root).resolve()
    _need(type(metric_ids) in (list,tuple) and metric_ids and
          len(metric_ids) == len(set(metric_ids)) and set(metric_ids) <= METRIC_IDS,
          'METRIC_SCOPE_NOT_CONNECTED')
    company = registered_company_row(repo_root=source, company_id=company_id)
    # Validate both complete registries, but only this task's company context
    # must match. Other valid company rows cannot change its source plan.
    _need(company == registered_company_row(repo_root=ROOT, company_id=company_id),
          'COMPANY_REGISTRY_CHANGED')
    # Re-use the metadata selection by report end. In particular this does not
    # run the issuer-year resolver's full annual preparation just to name URLs.
    plan = _Requirements(source, company)
    errors, selection, current_period = [], None, None
    try:
        selection = resolve_period_selection(repo_root=source, company_id=company_id,
            report_end=report_end, rules_root=ROOT)
        _catalog_requirements(plan, selection)
    except (ValueError, KeyError, TypeError) as error:
        _limitation(errors, 'PERIOD_METADATA', error)
        plan.require(submissions_url(cik=int(company['primary_cik'])),
                     'selected_submissions_inventory', 'application/json')
        try:
            history = load_history_for_period(repo_root=source, company_id=company_id, report_end=report_end)
            for name in history['considered_shards']:
                plan.require(submissions_file_url(file_name=name),
                             'selected_submissions_history', 'application/json')
        except (ValueError, KeyError, TypeError) as detail:
            if str(detail) != str(error):_limitation(errors, 'METADATA_DEPENDENCIES', detail)
    if selection is not None and not errors:
        # The selected reporting CIK is already established from its own catalog;
        # a predecessor's bytes are never treated as successor financial values.
        plan.company = {**company, 'primary_cik':selection['reporting_cik']}
        from .normal_governance_input import _Sources
        plan.reader = _Sources(source, company_id, selection['reporting_cik'])
        current = _annual_requirements(plan, selection['current_filing'], 'target_annual', errors)
        current_period = current['period']
        for filing in selection['current_amendments']:
            if set(metric_ids)=={'B03'}:
                # B03's existing amendment relation reader consumes the whole
                # inline primary. It does not consume an amendment instance
                # or directory; do not invent unused required dependencies.
                plan.require(accession_document_url(cik=int(selection['reporting_cik']),
                    accession=filing['accessionNumber'],document_name=filing['primaryDocument']),
                    'target_amendment_primary','text/html',filing['accessionNumber'])
            else:
                _annual_requirements(plan, filing, 'target_amendment', errors)
        facts = plan.require(companyfacts_url(cik=int(selection['reporting_cik'])),
                             'selected_companyfacts', 'application/json')
        if facts is not None:
            try:
                payload = strict_json_loads(text=facts['raw_bytes'].decode('utf-8'))
                _need(type(payload) is dict and 'cik' in payload and _cik(payload['cik'])
                      == _cik(selection['reporting_cik']), 'COMPANYFACTS_ENTITY_CONFLICT')
            except (ValueError, KeyError) as error:_limitation(errors, 'COMPANYFACTS_IDENTITY', error)
        needs_prior = 'B02' in metric_ids and selection['subject_policy']['mode']=='CONTINUOUS_PRIMARY'
        if needs_prior:
            if selection['prior_filing'] is None:
                errors.append({'phase':'PRIOR_SELECTION', 'reason':'NO_SAME_CIK_PRIOR_IN_SAVED_METADATA',
                               'category':'SOURCE_UNAVAILABLE'})
            else:
                prior = _annual_requirements(plan, selection['prior_filing'], 'prior_annual', errors)
                _prior_alternative(plan, prior, current_period, errors)
                for filing in selection['prior_amendments']:
                    _annual_requirements(plan, filing, 'prior_amendment', errors)
    requirements = list(plan.requests.values())
    unresolved = [r['source_url'] for r in requirements if r['saved_status']!='VERIFIED_SAVED_SOURCE'
        and r.get('alternative_dependency',{}).get('status')!='VERIFIED_PRIOR_NATIVE_INSTANCE']
    body = {'record_type':'SELECTED_ANNUAL_SOURCE_REQUIREMENTS_V1', 'company_id':company_id,
        'metric_ids':list(metric_ids), 'requested_report_end':report_end,
        'filing_selection':selection, 'original_annual_period':current_period,
        'annual_period_label_source':'RAW_ORIGINAL_DEI_CONTEXT',
        'consumer_fiscal_year_resolution_performed':False,
        'requirements':requirements, 'unresolved_dependency_urls':unresolved, 'limitations':errors,
        'status':'SAVED_SOURCE_BYTES_AVAILABLE' if selection is not None and not unresolved and not errors
                 else 'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED',
        'complete_known_source_graph':selection is not None and
            not any(e['phase'] in {'PERIOD_METADATA','ACCESSION_INDEX','METADATA_DEPENDENCIES'} for e in errors),
        'unique_known_get_count':len(requirements), 'unknown_instance_frontier':[
            e for e in errors if e['phase']=='ACCESSION_INDEX'],
        'fiscal_year_claimed_from_report_date':False, 'current_sec_freshness_proven':False,
        'amendment_effect_on_metric_verified':False, 'metric_acceptance_proven':False,
        'all_39_source_acceptance_proven':False, 'fetch_authorized':False,
        'metric_executed':False, 'production_authorized':False,
        'calls':{'provider':0,'paid':0,'sec':0},
        'program_sha256':sha256_file(path=Path(__file__))}
    return {**body, 'requirements_id':content_hash(value=body)}


def discover_selected_source_requirements(*, repo_root, company_id, report_end, metric_ids):
    """Retain the annual path; explicit event source preparation is separate."""
    _need(type(metric_ids) in (list,tuple) and metric_ids
          and len(metric_ids)==len(set(metric_ids)) and set(metric_ids)<=SOURCE_METRIC_IDS,
          'METRIC_SCOPE_NOT_CONNECTED')
    if 'E01' not in metric_ids:
        return discover_selected_annual_requirements(repo_root=repo_root,company_id=company_id,
            report_end=report_end,metric_ids=metric_ids)
    return _discover_selected_event_requirements(repo_root=repo_root,company_id=company_id,
        report_end=report_end,metric_ids=metric_ids)


def _discover_selected_event_requirements(*, repo_root, company_id, report_end, metric_ids):
    """Use the existing selected annual/event consumers; never interpret an answer."""
    _need(type(report_end) is str and date.fromisoformat(report_end).isoformat()==report_end,
          'REPORT_END_INVALID')
    source=Path(repo_root).resolve()
    company=registered_company_row(repo_root=source,company_id=company_id)
    _need(company==registered_company_row(repo_root=ROOT,company_id=company_id),'COMPANY_REGISTRY_CHANGED')
    plan=_Requirements(source,company);errors=[];selection=prepared=event=None
    try:
        selection=resolve_period_selection(repo_root=source,company_id=company_id,report_end=report_end,rules_root=ROOT)
        _catalog_requirements(plan,selection)
        from .historical_annual_input import prepare_historical_annual_input
        prepared=prepare_historical_annual_input(repo_root=source,company_id=company_id,
            period_selection=selection,rules_root=ROOT)
        # Registry identity still owns the primary catalog used to prove a
        # predecessor's selection. Only document reading uses its reporter.
        from .normal_governance_input import _Sources
        plan.reader=_Sources(source,company_id,prepared['entity'])
        from .historical_e01_company_case import collect_historical_e01_requirements
        event=collect_historical_e01_requirements(plan,prepared=prepared,period_selection=selection)
        _need(type(event) is dict and type(event.get('source_graph_known')) is bool,
              'EVENT_SOURCE_CONSUMER_SHAPE_INVALID')
        errors.extend(event.get('errors',[]))
    except ImportError as error:
        errors.append({'phase':'E01_SOURCE_CONSUMER','category':'IMPLEMENTATION_GAP','reason':str(error)})
    except (ValueError,KeyError,TypeError) as error:
        _limitation(errors,'E01_SELECTED_SOURCE',error)
        if str(error).startswith(('SAVED_SOURCE_MISSING:','LATEST_SOURCE_REQUEST_FAILED:')):
            # Keep the existing reader's exact missing/failed URL. Its exception
            # supplies no media/proof, so do not fabricate a checked row.
            url=str(error).partition(':')[2].strip()
            errors[-1]['source_url']=url
            if str(error).startswith('LATEST_SOURCE_REQUEST_FAILED:'):
                from .annual_sources import _rows
                matches=[(i,r) for i,r in enumerate(_rows(source))
                         if r['source_url']==url and r['method']=='GET']
                errors[-1]['category']='SOURCE_ACCESS_FAILED'
                if matches:
                    index,row=matches[-1]
                    if row['status_code']!='200' or row['error']:
                        errors[-1]['failed_request']={'request_attempt_id':
                            request_log_attempt_id(row_index=index,row=row),
                            **{k:row[k] for k in ('timestamp_utc','source_url',
                                'status_code','error','retry_attempt')}}
        if selection is not None:
            filing=selection['current_filing']
            plan.require(accession_document_url(cik=int(selection['reporting_cik']),
                accession=filing['accessionNumber'],document_name=filing['primaryDocument']),
                'selected_event_annual_primary','text/html',filing['accessionNumber'])
    components=[]
    annual=[metric for metric in metric_ids if metric in METRIC_IDS]
    if annual:components.append(discover_selected_annual_requirements(repo_root=source,
        company_id=company_id,report_end=report_end,metric_ids=annual))
    requirements={r['source_url']:dict(r) for r in plan.requests.values()}
    for component in components:
        errors.extend(component['limitations'])
        for row in component['requirements']:
            prior=requirements.get(row['source_url'])
            if prior is None:requirements[row['source_url']]=dict(row)
            else:
                _need(prior['saved_status']==row['saved_status']
                      and _component_source_observation_matches(prior.get('proof',{}),row.get('proof',{}),
                          facts_url=companyfacts_url(cik=int(prepared['entity'])) if prepared else None),
                      'COMPONENT_SOURCE_OBSERVATION_CHANGED')
                prior['roles']=list(dict.fromkeys((*prior['roles'],*row['roles'])))
                if row.get('alternative_dependency'):
                    prior['alternative_dependency']=row['alternative_dependency']
    rows=list(requirements.values())
    unresolved=[r['source_url'] for r in rows if r['saved_status']!='VERIFIED_SAVED_SOURCE'
        and r.get('alternative_dependency',{}).get('status')!='VERIFIED_PRIOR_NATIVE_INSTANCE']
    unresolved=list(dict.fromkeys((*unresolved,
        *(e['source_url'] for e in errors if e.get('source_url')))))
    graph=bool(event and event['source_graph_known'] and all(c['complete_known_source_graph'] for c in components))
    body={'record_type':'SELECTED_COMPANY_TASK_SOURCE_REQUIREMENTS_V1','company_id':company_id,
        'metric_ids':list(metric_ids),'requested_report_end':report_end,'filing_selection':selection,
        'original_annual_period':prepared['table_input']['target_period'] if prepared else None,
        'event_source_context':event,'component_source_plans':components,
        'requirements':rows,'limitations':errors,'unresolved_dependency_urls':unresolved,
        'complete_known_source_graph':graph,
        'unique_known_get_count':len({r['source_url'] for r in rows}|set(unresolved)),
        'status':'SAVED_SOURCE_BYTES_AVAILABLE' if graph and not unresolved and not errors else 'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED',
        'current_sec_freshness_proven':False,'metric_acceptance_proven':False,'all_39_source_acceptance_proven':False,
        'metric_executed':False,'fetch_authorized':False,'production_authorized':False,
        'calls':{'provider':0,'paid':0,'sec':0},'program_sha256':sha256_file(path=Path(__file__))}
    return {**body,'requirements_id':content_hash(value=body)}
