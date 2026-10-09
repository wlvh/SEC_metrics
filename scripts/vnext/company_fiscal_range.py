"""Discover issuer fiscal years and reuse the one ordinary company controller.

Only source/label discovery lives here. The historical owner supplies the label
reader and business cases; no fiscal-date arithmetic, second Calculator or
capture client is introduced. A processing factory discovers lazily so an
unchanged saved result need not prepare annual input just to compare changes.
"""
from pathlib import Path

from sec_urls import accession_document_url, companyfacts_url
from .canonical import content_hash, sha256_file
from .normal_annual_input import _registry_rows, _subject_policy
from .normal_history_catalog import load_history_for_period, annual_periods
from .normal_period_selection import restore_period_selection
from .normal_source_authority import ROOT
from .normal_source_requirements import _Requirements
from .selected_source_requirements import discover_selected_annual_requirements

METRIC_IDS = frozenset({'B01', 'B02'})
PROCESSING_FILES = (
    'scripts/vnext/company_fiscal_range.py',
    'scripts/vnext/selected_source_requirements.py',
    'scripts/vnext/fiscal_year_labels.py',
    'scripts/vnext/historical_fiscal_labels.py',
    'scripts/vnext/historical_dei.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'config/normal_fiscal_year_labels_v1.json',
)


def _need(condition, reason):
    if not condition:raise ValueError('COMPANY_FISCAL_RANGE_'+reason)


def _years(first,last):
    _need(type(first) is int and type(last) is int and
          1900<=first<=last<=9998 and last-first<5, 'INVALID')
    return list(range(first,last+1))


def _issue(phase,error,**fields):
    return {'phase':phase,'reason':str(error),'error_type':type(error).__name__,
        'category':getattr(error,'category','SOURCE_OR_READER_ERROR'),**fields}


def _candidates(source,company,first,last):
    """Existing metadata window and predecessor rule, never raw-year selection."""
    history=load_history_for_period(repo_root=source,company_id=company['company_id'],
                                    report_end=str(first)+'-01-01')
    _need(not history['limitations'] and not history['unloaded_history_reaching_period'],
          'METADATA_WINDOW_INCOMPLETE')
    periods=annual_periods(history=history)
    scope={'target_report_end':history['target_report_end'],
        'window_oldest_report_end':history['window_oldest_report_end'],
        'loaded_inventories':history['loaded_inventories'],
        'outside_window_report_ends':[p['report_date'] for p in periods
                                     if p['report_date']<history['window_oldest_report_end']],
        'unloaded_older_history_files':[s['name'] for s in history['declared_shards']
                                       if s['name'] not in history['loaded_inventories']]}
    candidates=[{'reporting_cik':history['reporting_cik'],'period':p,'metadata_scope':scope}
                for p in periods if p['report_date']>=history['window_oldest_report_end']]
    oldest=periods[-1]['report_date'] if periods else None
    for cik in _subject_policy(company).get('related_predecessor_ciks',()):
        earlier=load_history_for_period(repo_root=source,company_id=company['company_id'],
            report_end=str(first)+'-01-01',cik=cik)
        _need(not earlier['limitations'] and not earlier['unloaded_history_reaching_period'],
              'PREDECESSOR_METADATA_WINDOW_INCOMPLETE')
        candidates.extend({'reporting_cik':earlier['reporting_cik'],'period':p,
            'metadata_scope':{'target_report_end':earlier['target_report_end'],
                'window_oldest_report_end':earlier['window_oldest_report_end'],
                'loaded_inventories':earlier['loaded_inventories']}}
            for p in annual_periods(history=earlier) if p['report_date']>=earlier['window_oldest_report_end']
            and (oldest is None or p['report_date']<oldest))
    return candidates


def discover_fiscal_range(*,repo_root,company_id,fiscal_year_start,fiscal_year_end,metric_ids):
    years=_years(fiscal_year_start,fiscal_year_end)
    _need(type(metric_ids) in (tuple,list) and metric_ids and
          len(metric_ids)==len(set(metric_ids)) and set(metric_ids)<=METRIC_IDS, 'METRIC_NOT_CONNECTED')
    source=Path(repo_root).resolve()
    _need(sha256_file(path=source/'config/company_registry.csv')==
          sha256_file(path=ROOT/'config/company_registry.csv'),'SOURCE_COMPANY_REGISTRY_CHANGED')
    companies=[r for r in _registry_rows(repo_root=source) if r['company_id']==company_id]
    _need(len(companies)==1,'COMPANY_NOT_CONFIGURED')
    company=companies[0]; failures=[]; entries=[]
    try:candidates=_candidates(source,company,years[0],years[-1])
    except (ValueError,KeyError,TypeError) as error:
        candidates=[];failures.append(_issue('ANNUAL_METADATA',error))
    from .historical_fiscal_labels import resolve_selected_fiscal_year_label
    readers={}
    for candidate in candidates:
        row={'report_end':candidate['period']['report_date'],
             'reporting_cik':candidate['reporting_cik'],'source_fiscal_year_resolved':False,
             'metadata_scope':candidate.get('metadata_scope',{})}
        try:
            p=candidate['period'];_need(p['original_status']=='SINGLE_ORIGINAL_ANNUAL','ORIGINAL_MISSING_OR_AMBIGUOUS')
            filing=p['original'];cik=str(candidate['reporting_cik'])
            if cik not in readers:readers[cik]=_Requirements(source,{**company,'primary_cik':cik})
            reader=readers[cik]
            primary=reader.require(accession_document_url(cik=int(cik),accession=filing['accessionNumber'],
                document_name=filing['primaryDocument']),'fiscal_label_primary','text/html',filing['accessionNumber'])
            facts=reader.require(companyfacts_url(cik=int(cik)), 'fiscal_label_companyfacts','application/json')
            _need(primary is not None and facts is not None,'LABEL_SOURCE_MISSING')
            primary_proof=reader.requests[primary['source_reference']['source_url']]['proof']
            facts_proof=reader.requests[facts['source_reference']['source_url']]['proof']
            label=resolve_selected_fiscal_year_label(primary_bytes=primary['raw_bytes'],companyfacts_bytes=facts['raw_bytes'],
                expected_primary_sha256=primary_proof['content_sha256'],
                expected_companyfacts_sha256=facts_proof['content_sha256'],expected_cik=cik,filing=filing)
            _need(type(label['selected_fiscal_year']) is int and 1900<=label['selected_fiscal_year']<=9998,'LABEL_READER_OUTPUT_INVALID')
            _need(label['actual_period']['period_end']==row['report_end'],'LABEL_ACTUAL_PERIOD_CHANGED')
            row.update(source_fiscal_year_resolved=True,filing=filing,fiscal_year=label['selected_fiscal_year'],
                original_dei_fiscal_year=label['original_dei_fiscal_year'],basis=label['basis'],
                actual_period=label['actual_period'],inspection_id=label['source_inspection']['inspection_id'],
                label_status=label['source_inspection']['status'],primary_proof=primary_proof,companyfacts_proof=facts_proof)
        except (ValueError,KeyError,TypeError) as error:
            row['limitation']=_issue('FISCAL_LABEL',error,report_end=row['report_end'])
        entries.append(row)
    tasks=[]
    for year in years:
        task={'fiscal_year':year,'status':'FISCAL_YEAR_SOURCE_UNRESOLVED','limitations':list(failures)}
        # Issuer definitions, not date arithmetic, determine membership.
        # An unread original in this metadata window cannot be dismissed merely
        # because a known source already supplies the requested label.
        unread=[e['limitation'] for e in entries if not e['source_fiscal_year_resolved']]
        matches=[e for e in entries if e.get('fiscal_year')==year]
        task['limitations'].extend(unread)
        if not task['limitations'] and len(matches)==1:
            match=matches[0]
            try:
                prepared=discover_selected_annual_requirements(repo_root=source,company_id=company_id,
                    report_end=match['report_end'],metric_ids=metric_ids)
                selection=restore_period_selection(repo_root=source,company_id=company_id,
                    target_report_end=match['report_end'],requested_fiscal_year=year,rules_root=ROOT)
                _need(selection['reporting_cik']==match['reporting_cik'],'SELECTED_REPORTING_ENTITY_CHANGED')
                task.update(status='FISCAL_YEAR_RESOLVED',report_end=match['report_end'],
                    reporting_cik=match['reporting_cik'],label=match,period_selection=selection,
                    source_preflight=prepared,source_bytes_available=prepared['status']=='SAVED_SOURCE_BYTES_AVAILABLE')
            except (ValueError,KeyError,TypeError) as error:
                task['limitations'].append(_issue('SELECTED_SOURCE_PREFLIGHT',error))
        elif not task['limitations']:
            task['limitations'].append({'phase':'FISCAL_LABEL_UNIQUENESS',
                'reason':'FISCAL_YEAR_MISSING_OR_AMBIGUOUS','matching_report_ends':[m['report_end'] for m in matches]})
        tasks.append(task)
    body={'record_type':'COMPANY_FISCAL_RANGE_SOURCE_V1','company_id':company_id,
        'fiscal_years':years,'metric_ids':list(metric_ids),'candidates':entries,'tasks':tasks,
        'status':'FISCAL_RANGE_RESOLVED' if all(t['status']=='FISCAL_YEAR_RESOLVED' for t in tasks)
                 else 'FISCAL_RANGE_UNRESOLVED',
        'all_source_bytes_available':all(t.get('source_bytes_available',False) for t in tasks),
        'discovery_scope':'EXISTING_TARGET_AND_NEAREST_PRIOR_METADATA_WINDOW',
        'all_older_history_excluded_by_fiscal_label':False,
        'current_sec_freshness_proven':False,
        'calls':{'provider':0,'paid':0,'sec':0},'fetch_authorized':False,'metric_executed':False,
        'metric_acceptance_proven':False,'production_authorized':False}
    return {**body,'range_id':content_hash(value=body)}


def range_case_factories(*,company_id,fiscal_years,metric_ids,case_factories):
    """Operation-local lazy source discovery, only after the updater needs work."""
    _need(fiscal_years==_years(min(fiscal_years),max(fiscal_years)), 'YEARS_NOT_CONTIGUOUS')
    selected=set(metric_ids)&METRIC_IDS
    _need(selected<=set(case_factories),'BUSINESS_CASE_MISSING')
    cache={}; result=dict(case_factories); expected_company=company_id
    def make(producer,metric):
        def prepare_year_case(*,repo_root,company_id,metric_id,fiscal_year):
            _need(company_id==expected_company and metric_id==metric and fiscal_year in fiscal_years,'FACTORY_SCOPE_CHANGED')
            source=Path(repo_root).resolve()
            key=(str(source),sha256_file(path=source/'evidence/requests_log.csv'),
                 sha256_file(path=source/'config/company_registry.csv'))
            if key not in cache:
                cache[key]=discover_fiscal_range(repo_root=source,company_id=company_id,
                    fiscal_year_start=fiscal_years[0],fiscal_year_end=fiscal_years[-1],metric_ids=sorted(selected))
            task=next(t for t in cache[key]['tasks'] if t['fiscal_year']==fiscal_year)
            _need(task['status']=='FISCAL_YEAR_RESOLVED','YEAR_UNRESOLVED:'+str(task['limitations']))
            # The actual business case still revalidates the supplied selection,
            # periods, amendment semantics and complete sources before saving.
            return producer(repo_root=source,company_id=company_id,metric_id=metric_id,
                fiscal_year=fiscal_year,period_selection=task['period_selection'])
        prepare_year_case.__qualname__='prepared_fiscal_range_'+metric
        return prepare_year_case
    for metric in selected:result[metric]=make(case_factories[metric],metric)
    return result
