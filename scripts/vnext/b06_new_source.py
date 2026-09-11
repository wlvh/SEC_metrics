"""Normal zero-model B06 entry, using native Run, Calculator and cold replay."""
from pathlib import Path
from datetime import date,datetime
import shutil
from .canonical import canonical_json_bytes,content_hash,sha256_file,strict_json_file,strict_json_loads
from .r5_b06_structured import need
from . import b06_disclosure as disclosure
from . import b06_source_admission as admission
from .sources import raw_blob_record,source_reference_record,companyfacts_structured_facts,resolve_repository_file
from .batch_workflow import _registry_rows,repository_company_traits,repository_company_ciks,validate_request_attempt_binding
from .specs import compile_spec_file
from .requirements import load_requirement_snapshot
from .observations import scope_key
from .run_store import create_run,append_run_record,validate_and_freeze_run,load_frozen_run
from .r5_b06_scope import resolve_financing

REQUIREMENT_ID='issue_28_v10'
PREFIX='run:b06-new-source:'


def _write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=canonical_json_bytes(value=value)
    if path.exists():need(path.read_bytes()==data,'IMMUTABLE_B06_RECORD_CHANGED')
    else:
        with path.open('xb') as f:f.write(data)


def _external(path):
    path=path.resolve();root=admission.ROOT.resolve()
    need(path!=root and root not in path.parents and not (path/'outputs/active_publication.json').exists(),'B06_EXTERNAL_CANDIDATE_ROOT_REQUIRED')
    return path


def install_rules(data_root):
    """Copy code-owned data authority; never execute Python from the input root."""
    from .annual_runtime import _authority_files
    from .annual_continuity_sources import frozen_foundation_receipts
    data_root=_external(data_root)
    root=admission.ROOT;requirement=load_requirement_snapshot(snapshot_dir=root/'requirements'/REQUIREMENT_ID)
    paths=set(_authority_files(requirement))|set(requirement['baseline']['new_rule_files'])
    cursor=requirement
    while cursor:
        paths.update(cursor.get('execution_authority',{}).get('files',{}))
        cursor=cursor.get('parent_snapshot')
    paths.update(str(p.relative_to(root)) for p in (root/'requirements').rglob('*') if p.is_file())
    paths.update([disclosure.SPEC_PATH,'config/r5_b06_debt_sets_v3.json',admission.POLICY])
    receipts=frozen_foundation_receipts()
    for rel in sorted(paths):
        p=root/rel
        if not p.is_file():continue
        out=data_root/rel;out.parent.mkdir(parents=True,exist_ok=True)
        body=receipts[rel]['bytes'] if rel in receipts else p.read_bytes()
        if out.exists():need(out.read_bytes()==body,'DATA_RULE_ALREADY_FROZEN:'+rel)
        else:out.write_bytes(body)


def _verify_source(data_root,p):
    # Trust admission deliberately precedes format/hash checks: caller-created
    # self-consistent bodies, headers and ledger cannot self-enrol.
    entry=admission.verify_admission(proof=p)
    binding=validate_request_attempt_binding(repo_root=data_root,source_url=p['source_url'],content_sha256=p['content_sha256'],accession=p['accession'],document_name=p['document_name'],request_attempt_id=p['request_attempt_id'],require_immutable=entry['kind']=='SEC_FETCH')
    need(binding=={k:v for k,v in p.items() if k not in {'source_url','accession','document_name','content_sha256'}},'PINNED_SOURCE_BINDING_CHANGED')
    return entry


def _period(raw,filing,cik):
    from .deterministic_router import parse_accession_xbrl_source
    parsed=parse_accession_xbrl_source(raw_bytes=raw);cs=[]
    def dei(name):
        fs=[f for f in parsed.facts if f['qualified_name'].casefold()==('dei:'+name).casefold()]
        pairs={(f['text'].strip(),f['context_ref']) for f in fs};need(len(pairs)==1,'DEI_IDENTITY_AMBIGUOUS:'+name)
        val,ref=pairs.pop();c=parsed.contexts[ref]
        need(not c['dimensions'] and not c['typed_dimension_count'] and int(c['entity_identifier'])==cik,'DEI_SUBJECT_CONFLICT');cs.append(c);return val
    form=dei('DocumentType');end=dei('DocumentPeriodEndDate');fy=dei('DocumentFiscalYearFocus');fp=dei('DocumentFiscalPeriodFocus');am=dei('AmendmentFlag');entity=dei('EntityCentralIndexKey')
    if end!=filing['reportDate']:end=datetime.strptime(end,'%B %d, %Y').date().isoformat()
    need(form==filing['form']=='10-K' and fp=='FY' and am.casefold()=='false' and int(entity)==cik and end==filing['reportDate'],'AS_FILED_IDENTITY_CONFLICT')
    start=cs[0]['period_start'];need(all(c['period_start']==start and c['period_end']==end for c in cs),'DEI_PERIOD_CONFLICT')
    need(350<=(date.fromisoformat(end)-date.fromisoformat(start)).days+1<=380,'ANNUAL_DURATION_UNSUPPORTED')
    return {'fiscal_year':int(fy),'period_start':end,'period_end':end,'actual_year_start':start}


def select_input(*,data_root,company_id):
    from .annual_input import _saved_source
    from .annual_update import _rows
    from sec_urls import submissions_url,companyfacts_url,accession_document_url
    company=next(c for c in _registry_rows(repo_root=data_root) if c['company_id']==company_id)
    need(company['entity_continuity_status']=='continuous','CONTINUOUS_PRIMARY_REQUIRED')
    rows=_rows(data_root);cik=int(company['primary_cik'])
    sp,sraw=_saved_source(repo_root=data_root,rows=rows,url=submissions_url(cik=cik));_verify_source(data_root,sp)
    payload=strict_json_loads(text=sraw.decode());recent=payload['filings']['recent']
    need(int(payload['cik'])==cik and recent and all(isinstance(v,list) for v in recent.values()) and len({len(v) for v in recent.values()})==1,'SUBMISSIONS_IDENTITY_OR_COLUMNS_CONFLICT')
    annual=[]
    for i,form in enumerate(recent['form']):
        if form not in {'10-K','10-K/A'}:continue
        f={k:v[i] for k,v in recent.items()}
        for field in ['reportDate','filingDate']:need(date.fromisoformat(f[field]).isoformat()==f[field],'FILING_DATE_INVALID')
        need(f['filingDate']>=f['reportDate'],'FILING_DATE_CONFLICT');annual.append(f)
    ordinary=sorted([f for f in annual if f['form']=='10-K'],key=lambda f:(f['reportDate'],f['filingDate']),reverse=True)
    need(len(ordinary)>=2,'PRECEDING_ANNUAL_MISSING');filing=ordinary[1]
    need(len([f for f in ordinary if f['reportDate']==filing['reportDate']])==1,'ANNUAL_ACCESSION_AMBIGUOUS')
    need(all(s['filingTo']<filing['reportDate'] for s in payload['filings']['files']),'RELEVANT_HISTORY_SHARD_REQUIRED')
    fixed=admission.policy()['samples'][company_id]
    need((str(cik),filing['accessionNumber'],filing['reportDate'],filing['primaryDocument'])==(fixed['cik'],fixed['accession'],fixed['period_end'],fixed['primary_document']),'FIXED_SAMPLE_CHANGED')
    proofs=[sp];raws={}
    for role,url in [('companyfacts',companyfacts_url(cik=cik)),('accession_xbrl',accession_document_url(cik=cik,accession=filing['accessionNumber'],document_name=filing['primaryDocument'].replace('.htm','_htm.xml'))),('target_primary',accession_document_url(cik=cik,accession=filing['accessionNumber'],document_name=filing['primaryDocument']))]:
        p,b=_saved_source(repo_root=data_root,rows=rows,url=url,accession=filing['accessionNumber']);_verify_source(data_root,p);proofs.append(p);raws[role]=b
    period=_period(raws['accession_xbrl'],filing,cik)
    need(_period(raws['target_primary'],filing,cik)==period,'PRIMARY_XML_PERIOD_CONFLICT')
    facts=strict_json_loads(text=raws['companyfacts'].decode());need(int(facts['cik'])==cik,'COMPANYFACTS_ENTITY_CHANGED')
    years={f['fy'] for c in facts['facts'].get('us-gaap',{}).values() for fs in c['units'].values() for f in fs if f.get('accn')==filing['accessionNumber'] and f.get('end')==filing['reportDate'] and f.get('form')=='10-K' and f.get('fp')=='FY'}
    need(years=={period['fiscal_year']},'COMPANYFACTS_FISCAL_LABEL_CONFLICT')
    amendments=[f for f in annual if f['form']=='10-K/A' and f['reportDate']==filing['reportDate']]
    return {'company_id':company_id,'entity':str(cik),'filing':filing,'target_period':{k:v for k,v in period.items() if k!='actual_year_start'},'actual_year_start':period['actual_year_start'],'proofs':proofs,
            'selection_rule':'PREVIOUS_ORDINARY_10K_IN_PINNED_SUBMISSIONS','simulated_historical_visibility':True,'amendments':amendments,
            'current_use_status':'AMENDMENT_REVIEW_REQUIRED' if amendments else 'AS_FILED_ONLY_NO_KNOWN_AMENDMENT_IN_PINNED_LIST','current_latest_verified':False}


def _verify_selected(data_root,selected):
    """Recheck sealed historical identity against its original, admitted bytes."""
    proofs=selected['proofs'];need(len(proofs)==4,'B06_REQUIRED_SOURCE_SET_CHANGED')
    for p in proofs:_verify_source(data_root,p)
    raw=lambda p:resolve_repository_file(repo_root=data_root,repo_relative_path=p['request_repo_relative_path']).read_bytes()
    payload=strict_json_loads(text=raw(proofs[0]).decode());recent=payload['filings']['recent']
    need(all(isinstance(v,list) for v in recent.values()) and len({len(v) for v in recent.values()})==1,'SUBMISSIONS_COLUMNS_CONFLICT')
    annual=[{k:v[i] for k,v in recent.items()} for i in range(len(recent['form'])) if recent['form'][i] in {'10-K','10-K/A'}]
    ordinary=sorted([f for f in annual if f['form']=='10-K'],key=lambda f:(f['reportDate'],f['filingDate']),reverse=True)
    need(len(ordinary)>=2 and selected['filing']==ordinary[1],'SEALED_HISTORICAL_SELECTION_CHANGED')
    f=selected['filing'];cik=int(selected['entity'])
    need(int(payload['cik'])==cik,'SEALED_SUBMISSIONS_ENTITY_CHANGED')
    period=_period(raw(proofs[2]),f,cik)
    need(_period(raw(proofs[3]),f,cik)==period and selected['target_period']=={k:v for k,v in period.items() if k!='actual_year_start'} and selected['actual_year_start']==period['actual_year_start'],'SEALED_FISCAL_IDENTITY_CHANGED')
    amendments=[z for z in annual if z['form']=='10-K/A' and z['reportDate']==f['reportDate']]
    expected='AMENDMENT_REVIEW_REQUIRED' if amendments else 'AS_FILED_ONLY_NO_KNOWN_AMENDMENT_IN_PINNED_LIST'
    need(selected['amendments']==amendments and selected['current_use_status']==expected and selected['current_latest_verified'] is False,'SEALED_AMENDMENT_STATUS_CHANGED')
    cf=strict_json_loads(text=raw(proofs[1]).decode())
    years={z['fy'] for concept in cf['facts'].get('us-gaap',{}).values() for fs in concept['units'].values() for z in fs if z.get('accn')==f['accessionNumber'] and z.get('end')==f['reportDate'] and z.get('form')=='10-K' and z.get('fp')=='FY'}
    need(int(cf['cik'])==cik and years=={period['fiscal_year']},'SEALED_COMPANYFACTS_FISCAL_IDENTITY_CHANGED')
    need(selected['selection_rule']=='PREVIOUS_ORDINARY_10K_IN_PINNED_SUBMISSIONS' and selected['simulated_historical_visibility'] is True,'SEALED_SELECTION_RULE_CHANGED')
    company=next(c for c in _registry_rows(repo_root=data_root) if c['company_id']==selected['company_id'])
    need(company['primary_cik']==str(cik),'SEALED_COMPANY_IDENTITY_CHANGED')
    from sec_urls import submissions_url,companyfacts_url,accession_document_url
    expected_urls=[submissions_url(cik=cik),companyfacts_url(cik=cik),accession_document_url(cik=cik,accession=f['accessionNumber'],document_name=f['primaryDocument'].replace('.htm','_htm.xml')),accession_document_url(cik=cik,accession=f['accessionNumber'],document_name=f['primaryDocument'])]
    need([p['source_url'] for p in proofs]==expected_urls and all(p['accession']==f['accessionNumber'] for p in proofs[1:]),'SEALED_REQUIRED_SOURCE_IDENTITY_CHANGED')


def _records(data_root,selected):
    records=[]
    for role,p in zip(['submissions','companyfacts','accession_xbrl','target_primary'],selected['proofs']):
        _verify_source(data_root,p)
        blob=raw_blob_record(repo_root=data_root,repo_relative_path=p['request_repo_relative_path'],media_type='application/json' if role in {'submissions','companyfacts'} else 'application/xml' if role=='accession_xbrl' else 'text/html')
        ref=source_reference_record(raw_blob=blob,company_id=selected['company_id'],source_url=p['source_url'],accession=selected['filing']['accessionNumber'],document_name=p['document_name'],source_role=role,request_attempt_id=p['request_attempt_id']);records.extend([blob,ref])
    return records


def _target(selected):
    scope={'entity_scope':'consolidated'}
    return {'company_id':selected['company_id'],'period_start':selected['target_period']['period_end'],'period_end':selected['target_period']['period_end'],'accession':selected['filing']['accessionNumber'],'entity':selected['entity'],'scope':scope,'scope_key':scope_key(scope=scope)}


def compute(*,data_root,selected,spec,proposal=None):
    from .r5_b06_structured import concepts
    _verify_selected(data_root,selected)
    recs=_records(data_root,selected);refs={r['source_role']:r for r in recs if r['record_type']=='SOURCE_REFERENCE'}
    raw={r['raw_asset_id']:resolve_repository_file(repo_root=data_root,repo_relative_path=r['storage_uri']).read_bytes() for r in recs if r['record_type']=='RAW_BLOB'}
    xml=raw[refs['accession_xbrl']['raw_asset_id']];primary=raw[refs['target_primary']['raw_asset_id']];target=_target(selected)
    proposed=disclosure.propose(raw=xml,primary=primary,target=target) if proposal is None else proposal
    proof=disclosure.verify(raw=xml,primary=primary,source=refs['accession_xbrl'],spec=spec,target=target,filed=selected['filing']['filingDate'],data_root=data_root,proposal=proposed)
    facts=companyfacts_structured_facts(raw_bytes=raw[refs['companyfacts']['raw_asset_id']],source_reference=refs['companyfacts'],approved_concepts=concepts(spec,data_root=data_root),allowed_ciks=[selected['entity']],include_instant=True)
    traits=repository_company_traits(repo_root=data_root,company_id=selected['company_id'])
    result,trace,observations,audit=resolve_financing(spec=spec,target=target,traits=traits,facts=facts,measurement=proof)
    return recs,result,trace,observations,audit,proposed,proof


def create_primary_run(*,data_root,run_dir,company_id):
    data_root=_external(data_root);run_dir=_external(run_dir)
    selected=select_input(data_root=data_root,company_id=company_id);spec=compile_spec_file(path=data_root/disclosure.SPEC_PATH,dependency_specs={})
    need(spec['compiled']['quality_rule']['resolver']==disclosure.RESOLVER,'NEW_SOURCE_SPEC_REQUIRED')
    requirement=load_requirement_snapshot(snapshot_dir=data_root/'requirements'/REQUIREMENT_ID)
    recs,result,trace,obs,audit,proposal,proof=compute(data_root=data_root,selected=selected,spec=spec)
    binding={'selected':selected,'proposal':proposal,'verification':proof,'spec_closure_hash':spec['spec_closure_hash'],'requirement_closure_hash':requirement['requirement_closure_hash']}
    binding_id=content_hash(value=binding);run_id=PREFIX+binding_id[7:]
    _write(data_root/'b06_bindings'/(binding_id[7:]+'.json'),binding)
    if run_dir.exists():
        manifest,_,_=load_frozen_run(run_dir=run_dir,repo_root=data_root);need(manifest['run_id']==run_id,'RUN_REENTRY_INPUT_CHANGED')
    else:
        create_run(run_dir=run_dir,run_id=run_id,company_id=company_id,company_traits=repository_company_traits(repo_root=data_root,company_id=company_id),target_period=selected['target_period'],source_references=[r for r in recs if r['record_type']=='SOURCE_REFERENCE'],missing_required_source_roles=[],spec_file_hashes={disclosure.SPEC_PATH:sha256_file(path=data_root/disclosure.SPEC_PATH)},requirement_hashes=requirement['hashes'],requirement_id=REQUIREMENT_ID,requirement_closure_hash=requirement['requirement_closure_hash'],artifact_requirement_generation='EXPLICIT_REQUIREMENT_V1')
        for r in [*recs,*obs,trace,result]:append_run_record(run_dir=run_dir,record=r)
        manifest=validate_and_freeze_run(run_dir=run_dir,repo_root=data_root)
    return {'run_id':run_id,'manifest':manifest,'result':result,'audit':audit,'binding_id':binding_id,'original_proposal':proposal,'calls':{'provider':0,'paid':0,'sec':0},'current_use_status':selected['current_use_status'],'current_latest_verified':False}


def replay(*,data_root,manifest,spec):
    need(manifest['run_id'].startswith(PREFIX) and manifest['requirement_id']==REQUIREMENT_ID,'NEW_SOURCE_RUN_IDENTITY_REQUIRED')
    key=manifest['run_id'][len(PREFIX):];binding=strict_json_file(path=data_root/'b06_bindings'/(key+'.json'))
    need(content_hash(value=binding)=='sha256:'+key and binding['spec_closure_hash']==spec['spec_closure_hash'] and binding['requirement_closure_hash']==manifest['requirement_closure_hash'],'B06_RUN_BINDING_CHANGED')
    selected=binding['selected'];need(selected['company_id']==manifest['company_id'] and selected['target_period']==manifest['target_period'],'B06_RUN_TARGET_CHANGED')
    # Sealed selection is checked against its original submissions, not today's
    # latest metadata. Every source still requires its independent admission.
    recs,result,trace,obs,audit,proposal,proof=compute(data_root=data_root,selected=selected,spec=spec,proposal=binding['proposal'])
    need([r for r in recs if r['record_type']=='SOURCE_REFERENCE']==manifest['source_references'],'B06_REQUIRED_SOURCE_SET_CHANGED')
    need(proof==binding['verification'],'B06_SAVED_VERIFICATION_CHANGED')
    return result,trace,obs,audit
