"""Discover ordinary source dependencies without fetching or metric answers.

Saved metadata drives the current/prior filing, amendment, proxy, event and
accession-instance requirements. Incoherent metadata produces a refresh set;
it cannot be presented as a complete source inventory. This is the read-only
front of normal source updates, not an acquisition grant or execution result.
"""
from pathlib import Path
from datetime import date,timedelta
import re

from sec_urls import submissions_url,submissions_file_url,companyfacts_url,accession_document_url,accession_directory_url,hdr_sgml_url
from .annual_update import AnnualUpdateError
from .batch_workflow import BatchWorkflowError
from .canonical import CanonicalError,content_hash,sha256_file,strict_json_loads
from .normal_annual_input import _registry_rows,select_filing,annual_period,NormalAnnualInputError
from .normal_annual_input_v2 import prepare_saved_annual_input,exact_json_value
from .normal_governance_input import _Sources,_filings,_history_index,history_body_alignment,select_governance_metadata,NormalGovernanceInputError
from .normal_source_authority import ROOT,verify_saved_source_proofs,NormalSourceAuthorityError
from .sources import SourceError
from .fiscal_year_labels import FiscalYearLabelError


class SourceRequirementsError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise SourceRequirementsError(reason)


_SOURCE_ERRORS=(AnnualUpdateError,BatchWorkflowError,CanonicalError,NormalAnnualInputError,NormalGovernanceInputError,NormalSourceAuthorityError,SourceError,SourceRequirementsError,FiscalYearLabelError,UnicodeError)


def _instance_names(payload,company,filing):
    _need(type(payload) is dict and type(payload.get('directory')) is dict,
          'SOURCE_REQUIREMENT_DIRECTORY_SCHEMA_INVALID')
    directory=payload['directory'];cik=company['primary_cik'];accession=filing['accessionNumber']
    _need(directory.get('name')=='/Archives/edgar/data/'+cik+'/'+accession.replace('-',''),'SOURCE_REQUIREMENT_DIRECTORY_IDENTITY_CHANGED')
    items=directory.get('item')
    _need(type(items) is list and all(type(x) is dict and type(x.get('name')) is str
        and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*',x['name']) for x in items),'SOURCE_REQUIREMENT_DIRECTORY_NAMES_INVALID')
    names=[x['name'] for x in items]
    _need(len(names)==len(set(names)) and filing['primaryDocument'] in names,'SOURCE_REQUIREMENT_PRIMARY_OR_DIRECTORY_SET_CHANGED')
    return sorted(n for n in names if n.lower().endswith('.xml') and n.lower()!='filingsummary.xml'
        and not n.lower().endswith(('_cal.xml','_def.xml','_lab.xml','_pre.xml')) and re.match(r'r\d',n,re.I) is None)


def _declared_selection(payload,company):
    _need(type(payload) is dict and type(payload.get('filings')) is dict
          and {'recent','files'} <= set(payload['filings']),
          'SOURCE_REQUIREMENT_SUBMISSIONS_SCHEMA_INVALID')
    _history_index(payload,company['primary_cik'])
    _filings(payload,inventory_name='current_submissions')
    return select_filing(company=company,submissions=payload)


class _Requirements:
    def __init__(self,root,company):
        self.root,self.company=root,company
        self.reader=_Sources(root,company['company_id'],company['primary_cik'])
        self.requests={};self.payloads={}

    def require(self,url,role,media_type,accession='',refresh=False):
        if url in self.requests:
            item=self.requests[url]
            if role not in item['roles']:item['roles'].append(role)
            item['refresh_for_new_discovery'] |= refresh
            return self.payloads.get(url)
        item={'source_url':url,'method':'GET','roles':[role],'accession':accession,'media_type':media_type,
              'refresh_for_new_discovery':refresh,'saved_status':'NOT_CHECKED','source_acquisition_credit':False}
        self.requests[url]=item
        try:
            source=self.reader.read(url,accession=accession,role=role,media_type=media_type,required=False)
            if source is None:item['saved_status']='MISSING_SAVED_SOURCE'
            else:
                proof=next(v['proof'] for v in self.reader.proofs.values()
                           if v['source_reference_id']==source['source_reference']['source_reference_id'])
                from .ordinary_source_authority import verify_ordinary_source_proofs
                verify_ordinary_source_proofs(data_root=self.root,proofs=[proof])
                item.update(saved_status='VERIFIED_SAVED_SOURCE',source_reference=source['source_reference'],proof=proof)
                self.payloads[url]=source
        except _SOURCE_ERRORS as error:
            item.update(saved_status='SAVED_SOURCE_BLOCKED',reason=str(error),error_type=type(error).__name__)
        return self.payloads.get(url)


def source_dependency_satisfied(requirement):
    """A missing file stays missing even when its sole required role is met."""
    return requirement['saved_status']=='VERIFIED_SAVED_SOURCE' or (
        requirement['saved_status']=='MISSING_SAVED_SOURCE'
        and requirement['roles']==['prior_annual_primary']
        and requirement.get('alternative_dependency',{}).get('status')=='VERIFIED_PRIOR_NATIVE_INSTANCE')


def _same_source_observation(left,right):
    # Reader roles name different uses of the exact same source and attempt.
    omitted={'source_reference_id','source_role'}
    return {k:v for k,v in left.items() if k not in omitted}=={k:v for k,v in right.items() if k not in omitted}


def _satisfy_prior_primary_alternatives(plan,prepared,selection):
    """Reuse the existing annual-period/auditor XML routes, without fetching.

    Only a primary used solely for the prior annual dependency can be optional.
    All declared native instances and their accession index must already have
    verified saved proofs. This does not establish any metric result or freshness.
    """
    from .governance_signals import _auditor_filing,GovernanceSignalError
    if prepared is None or selection is None:return
    cik=plan.company['primary_cik']
    for filing in selection['prior_filing_chain']:
        url=accession_document_url(cik=int(cik),accession=filing['accessionNumber'],document_name=filing['primaryDocument'])
        item=plan.requests.get(url)
        if item is None or item['saved_status']!='MISSING_SAVED_SOURCE' or item['roles']!=['prior_annual_primary']:continue
        try:
            _need(prepared['entity']==cik,'SOURCE_REQUIREMENT_ALTERNATIVE_SUBJECT_CHANGED')
            documents=plan.reader.auditor_filing(filing)
            file_set=plan.reader.file_sets[-1]
            _need(file_set['primary_saved'] is False and bool(file_set['expected_xml_documents']),
                  'SOURCE_REQUIREMENT_ALTERNATIVE_NATIVE_INSTANCE_REQUIRED')
            index_url=accession_directory_url(cik=int(cik),accession=filing['accessionNumber'])
            index=plan.requests.get(index_url,{})
            _need(index.get('saved_status')=='VERIFIED_SAVED_SOURCE'
                  and _same_source_observation(index['source_reference'],plan.reader.records[file_set['index_source_reference_id']]),
                  'SOURCE_REQUIREMENT_ALTERNATIVE_INDEX_NOT_VERIFIED')
            for source in documents:
                ref=source['source_reference'];declared=plan.requests.get(ref['source_url'],{})
                _need(declared.get('saved_status')=='VERIFIED_SAVED_SOURCE'
                      and _same_source_observation(declared['source_reference'],ref),'SOURCE_REQUIREMENT_ALTERNATIVE_INSTANCE_NOT_VERIFIED')
            periods=[annual_period(raw=s['raw_bytes'],cik=cik,filing=filing) for s in documents]
            _need(bool(periods) and all(p==periods[0] for p in periods),
                  'SOURCE_REQUIREMENT_ALTERNATIVE_PERIOD_CONFLICT')
            prior=periods[0]
            _need(date.fromisoformat(prior['period_end'])+timedelta(days=1)
                  ==date.fromisoformat(prepared['table_input']['target_period']['period_start']),
                  'SOURCE_REQUIREMENT_ALTERNATIVE_PRIOR_NOT_ADJACENT')
            auditor=_auditor_filing(sources=documents,company_id=plan.company['company_id'],cik=cik,period_end=prior['period_end'])
            _need(auditor['status']=='FOUND','SOURCE_REQUIREMENT_ALTERNATIVE_AUDITOR_NOT_ESTABLISHED')
            item['alternative_dependency']={'status':'VERIFIED_PRIOR_NATIVE_INSTANCE',
                'satisfied_roles':['prior_annual_primary'],'prior_period':prior,'file_set':file_set,
                'source_references':[s['source_reference'] for s in documents],
                'auditor_facts':auditor['facts'],'auditor_fact_status':auditor['status'],
                'source_acquisition_credit':False,'metric_executed':False,
                'all_39_metric_source_acceptance_proven':False}
        except _SOURCE_ERRORS+(GovernanceSignalError,) as error:
            item['alternative_dependency']={'status':'NOT_ESTABLISHED','reason':str(error),'error_type':type(error).__name__}


_REGISTRATION_EVENT_FORMS = frozenset({'8-K12B','8-K12B/A'})


def _discovery_filings(payload,*,inventory_name):
    """Validate through the frozen parser without changing its form contract."""
    from copy import deepcopy
    original=_filings(payload,inventory_name=inventory_name)
    block=payload['filings']['recent'] if 'filings' in payload else payload
    if not any(form in _REGISTRATION_EVENT_FORMS for form in block['form']):return original
    copied=deepcopy(payload)
    temporary=copied['filings']['recent'] if 'filings' in copied else copied
    temporary['form']=['8-K' if form in _REGISTRATION_EVENT_FORMS else form for form in block['form']]
    checked=_filings(copied,inventory_name=inventory_name)
    # Restore from the original row, not by normalizing the accepted form.
    return [{**{key:values[row['metadata_origin']['row_index']] for key,values in block.items()},
             'metadata_origin':row['metadata_origin']} for row in checked]


def _registration_event_requirements(plan,rows,cik,window):
    """Discover originals without changing the accepted C04/six-event forms."""
    filings=[r for r in rows if r['form'] in _REGISTRATION_EVENT_FORMS
             and window['period_start']<=r['filingDate']<=window['period_end']]
    accessions=[r['accessionNumber'] for r in rows]
    _need(all(accessions.count(filing['accessionNumber'])==1 for filing in filings),
          'SOURCE_REQUIREMENT_REGISTRATION_INVENTORIES_OVERLAP')
    for filing in filings:
        accession=filing['accessionNumber']
        for url,role,media in (
            (accession_document_url(cik=int(cik),accession=accession,document_name=filing['primaryDocument']),
             'registration_event_primary','text/html'),
            (hdr_sgml_url(cik=int(cik),accession=accession),'registration_event_header','text/plain')):
            plan.require(url,role,media,accession)
            plan.requests[url].update(filing_form=filing['form'],
                semantic_form_scope='SOURCE_DISCOVERY_ONLY_NOT_EXISTING_EVENT_ACCEPTANCE')
    return sorted(filings,key=lambda r:(r['filingDate'],r['accessionNumber']))


def _metadata_requirements(plan,prepared,inventory):
    company=plan.company;cik=company['primary_cik'];period=prepared['table_input']['target_period']
    payload=strict_json_loads(text=inventory['raw_bytes'].decode('utf-8'))
    shards=_history_index(payload,cik);rows=_discovery_filings(payload,inventory_name=inventory['source_reference']['document_name'])
    inventories=[{'name':inventory['source_reference']['document_name'],'payload':payload,'source':inventory}]
    conflicts=[];unavailable=[]
    for shard in shards:
        prior=max((r['reportDate'] for r in rows if r['form']=='10-K' and r['reportDate']<period['period_end']),default='')
        cutoff=min(prior,period['period_start']) if prior else '0001-01-01'
        if shard['filingTo']<cutoff:break
        url=submissions_file_url(file_name=shard['name'])
        source=plan.require(url,'sec_submissions_history','application/json',refresh=True)
        if source is None:
            unavailable.append(url)
            # Without this shard, do not claim an earlier filing is the nearest
            # predecessor. Continue listing remaining potentially relevant shards.
            continue
        body=strict_json_loads(text=source['raw_bytes'].decode('utf-8'))
        _need('cik' not in body or str(body['cik']).isdigit() and int(body['cik'])==int(cik),
              'SOURCE_REQUIREMENT_HISTORY_ENTITY_CHANGED')
        shard_rows=_discovery_filings(body,inventory_name=shard['name'])
        problem=history_body_alignment(shard=shard,rows=shard_rows)
        if problem:conflicts.append(problem)
        rows.extend(shard_rows);inventories.append({'name':shard['name'],'payload':body,'source':source})
    if conflicts or unavailable:
        return None,{'status':'METADATA_REFRESH_REQUIRED','history_conflicts':conflicts,'unavailable_history_urls':unavailable,
                     'complete_filing_inventory_proven':False}
    selection=select_governance_metadata(company=company,prepared_input=prepared,inventories=inventories)
    selection['registration_event_filings']=_registration_event_requirements(plan,rows,cik,period)
    return selection,{'status':'SAVED_METADATA_COHERENT','history_conflicts':[],
                      'unavailable_history_urls':[],'complete_filing_inventory_proven':True}


def _registered_event_requirements(plan,prepared):
    """Keep the approved event window and every registered reporting CIK.

    This is source discovery only. It cannot combine financial statements or
    treat the current registrant's smaller filing set as the whole event scope.
    """
    from .public_projection import event_target_period
    from .traits import repository_company_ciks
    catalog_path='catalog/zero_ai_public_projection.json'
    _need(sha256_file(path=plan.root/catalog_path)==sha256_file(path=ROOT/catalog_path),
          'SOURCE_REQUIREMENT_EVENT_POLICY_CHANGED')
    catalog=strict_json_loads(text=(plan.root/catalog_path).read_text())
    window=event_target_period(target_period=prepared['table_input']['target_period'],
        continuity_status=plan.company['entity_continuity_status'],catalog=catalog)
    ciks=repository_company_ciks(repo_root=plan.root,company_id=plan.company['company_id'])
    scopes=[]
    for cik in ciks:
        scope={'cik':cik,'window':window,'metadata_complete':False,'issues':[],'event_filings':[]}
        scopes.append(scope)
        source=plan.require(submissions_url(cik=int(cik)),'registered_event_submissions','application/json',
                            accession='SUBMISSIONS-'+cik,refresh=True)
        if source is None:
            scope['issues'].append('REGISTERED_EVENT_SUBMISSIONS_UNAVAILABLE');continue
        try:
            payload=strict_json_loads(text=source['raw_bytes'].decode('utf-8'))
            _need(type(payload.get('cik')) in (str,int) and str(payload['cik']).isdigit()
                  and int(payload['cik'])==int(cik),'SOURCE_REQUIREMENT_EVENT_CIK_CHANGED')
            shards=_history_index(payload,cik)
            rows=_discovery_filings(payload,inventory_name=source['source_reference']['document_name'])
            for shard in shards:
                if shard['filingFrom']>window['period_end'] or shard['filingTo']<window['period_start']:continue
                saved=plan.require(submissions_file_url(file_name=shard['name']),
                    'registered_event_submissions_history','application/json',accession='SUBMISSIONS-'+cik,refresh=True)
                if saved is None:
                    scope['issues'].append('REGISTERED_EVENT_HISTORY_UNAVAILABLE:'+shard['name']);continue
                body=strict_json_loads(text=saved['raw_bytes'].decode('utf-8'))
                _need('cik' not in body or str(body['cik']).isdigit() and int(body['cik'])==int(cik),
                      'SOURCE_REQUIREMENT_EVENT_HISTORY_CIK_CHANGED')
                history_rows=_discovery_filings(body,inventory_name=shard['name'])
                conflict=history_body_alignment(shard=shard,rows=history_rows)
                if conflict:scope['issues'].append(conflict)
                rows.extend(history_rows)
            if not scope['issues']:
                scope['registration_variant_filings']=_registration_event_requirements(plan,rows,cik,window)
            events=[r for r in rows if r['form'] in {'8-K','8-K/A'}
                    and window['period_start']<=r['filingDate']<=window['period_end']]
            seen=set()
            for filing in sorted(events,key=lambda r:(r['filingDate'],r['accessionNumber'])):
                accession=filing['accessionNumber']
                if accession in seen:
                    scope['issues'].append('REGISTERED_EVENT_INVENTORY_OVERLAP:'+accession);continue
                seen.add(accession);scope['event_filings'].append(filing)
                plan.require(accession_document_url(cik=int(cik),accession=accession,document_name=filing['primaryDocument']),
                             'registered_event_primary','text/html',accession)
                plan.require(hdr_sgml_url(cik=int(cik),accession=accession),'registered_event_header','text/plain',accession)
            scope['metadata_complete']=not scope['issues']
        except _SOURCE_ERRORS as error:
            scope['issues'].append({'reason':str(error),'error_type':type(error).__name__})
    return {'record_type':'REGISTERED_EVENT_SOURCE_REQUIREMENTS','window':window,'registered_ciks':ciks,
            'catalog_sha256':sha256_file(path=plan.root/catalog_path),'scopes':scopes,
            'complete_registered_metadata':all(s['metadata_complete'] for s in scopes),
            'financial_cross_entity_combination_authorized':False,'metric_executed':False}


def discover_saved_source_requirements(*,repo_root:Path,company_id:str):
    _need(sha256_file(path=repo_root/'config/company_registry.csv')==sha256_file(path=ROOT/'config/company_registry.csv'),
          'SOURCE_REQUIREMENT_INSTALLED_COMPANY_SCOPE_CHANGED')
    company=next((c for c in _registry_rows(repo_root=repo_root) if c['company_id']==company_id),None)
    _need(company is not None,'SOURCE_REQUIREMENT_COMPANY_NOT_CONFIGURED')
    plan=_Requirements(repo_root,company);cik=company['primary_cik']
    inventory=plan.require(submissions_url(cik=int(cik)),'sec_submissions_inventory','application/json',refresh=True)
    prepared=None;declared=None;selection=None
    metadata={'status':'CURRENT_METADATA_UNAVAILABLE','complete_filing_inventory_proven':False}
    limitations=[]
    if inventory is not None:
        try:
            declared=_declared_selection(strict_json_loads(text=inventory['raw_bytes'].decode('utf-8')),company)
            metadata={'status':'ANNUAL_SOURCE_IDENTITY_PENDING','complete_filing_inventory_proven':False}
            filing=declared['filing'];accession=filing['accessionNumber']
            # Naming the new primary must precede reading it. Metadata identity
            # is explicitly unverified until its original DEI/context is read.
            plan.require(accession_document_url(cik=int(cik),accession=accession,document_name=filing['primaryDocument']),
                         'current_annual_primary','text/html',accession)
            plan.require(companyfacts_url(cik=int(cik)),'companyfacts','application/json',accession,refresh=True)
            prepared=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
            _need(prepared['filing']==declared['filing'],'SOURCE_REQUIREMENT_PREPARED_FILING_CHANGED')
            selection,metadata=_metadata_requirements(plan,prepared,inventory)
        except _SOURCE_ERRORS as error:
            limitations.append({'phase':'ANNUAL_IDENTITY_OR_METADATA','reason':str(error),'error_type':type(error).__name__})
            plan.require(companyfacts_url(cik=int(cik)),'companyfacts','application/json',refresh=True)
    else:
        plan.require(companyfacts_url(cik=int(cik)),'companyfacts','application/json',refresh=True)
    if selection is not None:
        filings={}
        for role,values in [('current_annual',selection['current_filing_chain']),('prior_annual',selection['prior_filing_chain']),
                            ('proxy',([selection['latest_def14a']] if selection['latest_def14a'] else [])+selection['def14a_amendments']),
                            ('fiscal_event',selection['events'])]:
            for filing in values:
                accession=filing['accessionNumber']
                if accession not in filings:filings[accession]={'filing':filing,'roles':[]}
                filings[accession]['roles'].append(role)
        for item in filings.values():
            filing=item['filing'];accession=filing['accessionNumber']
            url=accession_document_url(cik=int(cik),accession=accession,document_name=filing['primaryDocument'])
            for role in item['roles']:plan.require(url,role+'_primary','text/html',accession)
            if filing['form'] in {'8-K','8-K/A'}:
                plan.require(hdr_sgml_url(cik=int(cik),accession=accession),'fiscal_event_header','text/plain',accession)
            if filing['form'] in {'10-K','10-K/A'}:
                url=accession_directory_url(cik=int(cik),accession=accession)
                directory=plan.require(url,'annual_accession_index','application/json',accession)
                if directory is None:
                    limitations.append({'phase':'ACCESSION_INDEX','accession':accession,'source_url':url,
                                        'reason':'INSTANCE_DOCUMENT_NAMES_NOT_YET_DISCOVERED'})
                else:
                    try:
                        names=_instance_names(strict_json_loads(text=directory['raw_bytes'].decode('utf-8')),company,filing)
                        for name in names:
                            plan.require(accession_document_url(cik=int(cik),accession=accession,document_name=name),
                                         'annual_accession_instance','application/xml',accession)
                    except _SOURCE_ERRORS as error:
                        limitations.append({'phase':'ACCESSION_INDEX','accession':accession,'reason':str(error),'error_type':type(error).__name__})
    event_scope=None
    if prepared is not None and company['entity_continuity_status']!='continuous':
        event_scope=_registered_event_requirements(plan,prepared)
        if not event_scope['complete_registered_metadata']:
            limitations.append({'phase':'REGISTERED_EVENT_METADATA',
                                'reason':'APPROVED_EVENT_SCOPE_METADATA_INCOMPLETE'})
    _satisfy_prior_primary_alternatives(plan,prepared,selection)
    requests=list(plan.requests.values())
    missing=[r['source_url'] for r in requests if r['saved_status']!='VERIFIED_SAVED_SOURCE']
    pending=[r['source_url'] for r in requests if not source_dependency_satisfied(r)]
    refresh=[r['source_url'] for r in requests if r['refresh_for_new_discovery']]
    status=('METADATA_REFRESH_REQUIRED' if not metadata['complete_filing_inventory_proven'] else
            'SOURCE_DEPENDENCIES_UNRESOLVED' if pending or limitations else 'SAVED_SOURCE_DEPENDENCIES_AVAILABLE')
    body={'record_type':'ORDINARY_SOURCE_REQUIREMENTS','schema_version':1,'company_id':company_id,'primary_cik':cik,
          'status':status,'metadata':metadata,'prepared_annual_input':prepared,'filing_selection':selection,
          'metadata_declared_annual_selection':declared,'annual_source_identity_verified':prepared is not None,
          **({'registered_event_scope':event_scope} if event_scope is not None else {}),
          'requirements':requests,'missing_or_failed_source_urls':missing,'unresolved_dependency_urls':pending,
          'new_discovery_dataset_urls':refresh,
          'limitations':limitations,'unique_known_get_count':len(requests),'complete_new_source_graph_known':selection is not None and not limitations,
          'discovery_scope':'CURRENT_AND_PRIOR_ANNUAL_LATEST_PROXY_AND_FISCAL_8K_DOCUMENTS',
          'all_39_metric_source_acceptance_proven':False,
          'current_sec_freshness_proven':False,'fetch_authorized':False,'source_acquisition_credit':False,
          'metric_executed':False,'production_authorized':False,'calls':{'provider':0,'paid':0,'sec':0},
          'module_sha256':sha256_file(path=Path(__file__))}
    body=exact_json_value(body)
    return {**body,'requirements_id':content_hash(value=body)}


def inspect_source_requirements(*,repo_root:Path,company_ids=None):
    configured=[c['company_id'] for c in _registry_rows(repo_root=repo_root)]
    selected=configured if company_ids is None else list(company_ids)
    _need(bool(selected) and len(selected)==len(set(selected)) and set(selected)<=set(configured),
          'SOURCE_REQUIREMENT_COMPANY_SET_INVALID')
    reports=[]
    for company_id in selected:
        try:
            reports.append(discover_saved_source_requirements(repo_root=repo_root,company_id=company_id))
        except (ValueError,KeyError,TypeError,OSError) as error:
            # Preserve a real per-company parser/I/O failure. It is neither an
            # empty inventory nor a financial non-disclosure conclusion.
            reports.append({'company_id':company_id,'status':'SOURCE_DISCOVERY_FAILED',
                            'reason':str(error),'error_type':type(error).__name__})
    return {'record_type':'ORDINARY_SOURCE_REQUIREMENTS_REPORT','companies':reports,
            'execution':'NOT_EXECUTED','calls':{'provider':0,'paid':0,'sec':0},
            'fetch_authorized':False,'production_authorized':False}
