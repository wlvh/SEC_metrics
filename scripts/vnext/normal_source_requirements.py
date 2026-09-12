"""Discover ordinary source dependencies without fetching or metric answers.

Saved metadata drives the current/prior filing, amendment, proxy, event and
accession-instance requirements. Incoherent metadata produces a refresh set;
it cannot be presented as a complete source inventory. This is the read-only
front of normal source updates, not an acquisition grant or execution result.
"""
from pathlib import Path
import re

from sec_urls import submissions_url,submissions_file_url,companyfacts_url,accession_document_url,accession_directory_url,hdr_sgml_url
from .annual_update import AnnualUpdateError
from .batch_workflow import BatchWorkflowError
from .canonical import CanonicalError,content_hash,sha256_file,strict_json_loads
from .normal_annual_input import _registry_rows,select_filing,NormalAnnualInputError
from .normal_annual_input_v2 import prepare_saved_annual_input,exact_json_value
from .normal_governance_input import _Sources,_filings,_history_index,history_body_alignment,select_governance_metadata,NormalGovernanceInputError
from .normal_source_authority import ROOT,verify_saved_source_proofs,NormalSourceAuthorityError
from .sources import SourceError


class SourceRequirementsError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise SourceRequirementsError(reason)


_SOURCE_ERRORS=(AnnualUpdateError,BatchWorkflowError,CanonicalError,NormalAnnualInputError,NormalGovernanceInputError,NormalSourceAuthorityError,SourceError,SourceRequirementsError,UnicodeError)


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
                verify_saved_source_proofs(data_root=self.root,proofs=[proof])
                item.update(saved_status='VERIFIED_SAVED_SOURCE',source_reference=source['source_reference'],proof=proof)
                self.payloads[url]=source
        except _SOURCE_ERRORS as error:
            item.update(saved_status='SAVED_SOURCE_BLOCKED',reason=str(error),error_type=type(error).__name__)
        return self.payloads.get(url)


def _metadata_requirements(plan,prepared,inventory):
    company=plan.company;cik=company['primary_cik'];period=prepared['table_input']['target_period']
    payload=strict_json_loads(text=inventory['raw_bytes'].decode('utf-8'))
    shards=_history_index(payload,cik);rows=_filings(payload,inventory_name=inventory['source_reference']['document_name'])
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
        shard_rows=_filings(body,inventory_name=shard['name'])
        problem=history_body_alignment(shard=shard,rows=shard_rows)
        if problem:conflicts.append(problem)
        rows.extend(shard_rows);inventories.append({'name':shard['name'],'payload':body,'source':source})
    if conflicts or unavailable:
        return None,{'status':'METADATA_REFRESH_REQUIRED','history_conflicts':conflicts,'unavailable_history_urls':unavailable,
                     'complete_filing_inventory_proven':False}
    selection=select_governance_metadata(company=company,prepared_input=prepared,inventories=inventories)
    return selection,{'status':'SAVED_METADATA_COHERENT','history_conflicts':[],
                      'unavailable_history_urls':[],'complete_filing_inventory_proven':True}


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
    requests=list(plan.requests.values())
    pending=[r['source_url'] for r in requests if r['saved_status']!='VERIFIED_SAVED_SOURCE']
    refresh=[r['source_url'] for r in requests if r['refresh_for_new_discovery']]
    status=('METADATA_REFRESH_REQUIRED' if not metadata['complete_filing_inventory_proven'] else
            'SOURCE_DEPENDENCIES_UNRESOLVED' if pending or limitations else 'SAVED_SOURCE_DEPENDENCIES_AVAILABLE')
    body={'record_type':'ORDINARY_SOURCE_REQUIREMENTS','schema_version':1,'company_id':company_id,'primary_cik':cik,
          'status':status,'metadata':metadata,'prepared_annual_input':prepared,'filing_selection':selection,
          'metadata_declared_annual_selection':declared,'annual_source_identity_verified':prepared is not None,
          'requirements':requests,'missing_or_failed_source_urls':pending,'new_discovery_dataset_urls':refresh,
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
