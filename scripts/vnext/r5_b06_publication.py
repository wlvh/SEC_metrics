"""B06 draft candidate adapter for the existing complete publication core.

It prepares complete, read-only candidates, including explicit blocked rows.
It cannot grant deploy, switch, rollback, restore, recover or mirror writes.
"""
from pathlib import Path
import csv,io,json,subprocess
from . import publication as pub, projector
from . import r5_b06_structured as primary
from .annual_adoption import record, _tree_files
from .annual_publication import BATCH, SNAPSHOT, _ledger
from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file, strict_json_loads, sha256_bytes
from .records import validate_record, ANNUAL_PUBLICATION_MANIFEST_TYPE
from .run_store import load_frozen_run
from .requirements import load_requirement_snapshot
from .specs import compile_spec_file

CREDIT='NONE_ISOLATED_STRUCTURED_MIGRATION'
META='internal/r5_primary.json'
ROOT=Path(__file__).resolve().parents[2]
need=primary.need

def _json(value):return canonical_json_bytes(value=value)+b'\n'
def _rows(data):return list(csv.DictReader(io.StringIO(data.decode())))
def _code_head():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()

def _code_identity(head):
    need(subprocess.check_output(['git','merge-base',head,'HEAD'],cwd=ROOT,text=True).strip()==head,'R5_IMPLEMENTATION_NOT_ANCESTOR')
    return content_hash(value=subprocess.check_output(['git','ls-tree','-r',head,'scripts','tools','config','catalog','requirements'],cwd=ROOT,text=True))


def _verify_saved_input_origin(data, head):
    """This zero-fetch work package uses the already committed SEC attempts.

    It is a bounded candidate provenance rule, not a future per-filing workflow.
    The input identities are discovered automatically, never answer fixtures.
    """
    from .batch_workflow import _registry_rows
    paths={'evidence/requests_log.csv','evidence/requests_log_manifest.json'}
    for company in _registry_rows(repo_root=data):
        for proof in primary.discover(data_root=data,company=company)['sources']:
            paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
    for relative in sorted(paths):
        expected=subprocess.check_output(['git','show',head+':'+relative],cwd=ROOT)
        need((data/relative).read_bytes()==expected,'R5_SAVED_SOURCE_ORIGIN_CHANGED:'+relative)
    return sorted(paths)

def _evidence_for_blocked(company, selected):
    source=next(p for p in selected['input']['sources'] if '/companyfacts/' in p['source_url'])
    audit=selected['selection'];period=selected['input']['target_period'];rows=[]
    for fact in audit['debt_candidates']:
        row={k:'' for k in pub.EVIDENCE_FIELDS}
        row.update(company=company['display_name'],cik=company['primary_cik'],metric_id='B06',source_url=source['source_url'],repo_relative_path=source['request_repo_relative_path'],content_sha256=source['content_sha256'],accession=source['accession'],document_name=source['document_name'],concept_or_section=fact['concept'],context_or_dimension='CANDIDATE_ONLY:'+fact['fact_id'],unit=fact['unit'],period_start=period['period_start'],period_end=period['period_end'],value_raw=str(fact['value']),value_normalized='',evidence_quote='Unaccepted component; '+ ';'.join(audit['reasons']),extraction_method='structured_primary_candidate_not_accepted',parser_version='r5_primary_v1')
        rows.append(row)
    return rows


def _projection(data, run_root, predecessor):
    from .batch_workflow import _registry_rows
    companies=_registry_rows(repo_root=data);need(len(companies)==10,'R5_COMPANY_SET_CHANGED')
    old_rows=_rows(predecessor.read_bytes(relative_path='metrics_matrix.csv'));old_ev=_rows(predecessor.read_bytes(relative_path='metric_evidence.csv'))
    key=lambda r:(r['company'],r['metric_id']);keys={(c['display_name'],'B06') for c in companies}
    old_keys={key(r) for r in old_rows}
    need(len(old_keys)==len(old_rows),'R5_PREDECESSOR_DUPLICATE_COORDINATE')
    runs={};selections={};replacements={};ev_replacements={};bindings=[];coverage=[]
    spec=compile_spec_file(path=data/primary.SPEC_PATH,dependency_specs={})
    for company in companies:
        cid=company['company_id'];directory=run_root/cid
        manifest,records,decisions=load_frozen_run(run_dir=directory,repo_root=data)
        need(manifest['requirement_id']==primary.REQUIREMENT_ID and list(manifest['spec_file_hashes'])==[primary.SPEC_PATH],'R5_RUN_AUTHORITY_CHANGED')
        results=[r for r in records if r['record_type']=='METRIC_RESULT'];need(len(results)==1 and results[0]['metric_id']=='B06','R5_RESULT_SET_CHANGED');result=results[0]
        selected=strict_json_file(path=run_root/(cid+'-selection.json'));fresh_input=primary.discover(data_root=data,company=company);need(selected['input']==fresh_input,'R5_INPUT_SELECTION_CHANGED')
        trace=next(r for r in records if r['record_type']=='EXECUTION_TRACE');sources={r['source_reference_id']:r for r in records if r['record_type']=='SOURCE_REFERENCE'}
        raw={r['raw_asset_id']:(data/r['storage_uri']).read_bytes() for r in records if r['record_type']=='RAW_BLOB'}
        rebuilt=primary.replay_result(manifest=manifest,spec=spec,trace=trace,source_references=sources,raw_bytes_by_id=raw,company_ciks=[company['primary_cik']])
        need(rebuilt[3]==selected['selection'],'R5_SELECTION_AUDIT_CHANGED');audit=selected['selection'];selections[cid]=selected
        indexes=projector._record_indexes(runs=[(manifest,records)])
        baseline={field:'' for field in pub.METRIC_FIELDS}
        if result['value'] is not None:
            row,ev,_=projector._project_result(result=result,trace=trace,company=company,spec=spec,baseline_row=baseline,indexes=indexes,fiscal_year=str(manifest['target_period']['fiscal_year']),metric_fields=pub.METRIC_FIELDS)
        else:
            status='NOT_MEANINGFUL' if result['quality']=='NOT_MEANINGFUL' else 'NEEDS_REVIEW'
            baseline.update(company=company['display_name'],cik=company['primary_cik'],metric_id='B06',metric_name=spec['compiled']['name'],status=status,unit='ratio',source_class='DERIVED',formula=spec['compiled']['legacy_projection']['formula'],period_start=result['period_start'],period_end=result['period_end'],fiscal_year=str(manifest['target_period']['fiscal_year']),fiscal_period='FY',accession=selected['input']['filing']['accessionNumber'],form='10-K',filed_date=selected['input']['filing']['filingDate'],notes=result['reason_code']+';'+ ';'.join(audit['reasons']))
            if status=='NOT_MEANINGFUL':
                row,_,_=projector._project_result(result=result,trace=trace,company=company,spec=spec,baseline_row=baseline,indexes=indexes,fiscal_year=str(manifest['target_period']['fiscal_year']),metric_fields=pub.METRIC_FIELDS)
                ordered,_=projector._ordered_observations(trace=trace,observations=indexes['observations'],projection=spec['compiled']['legacy_projection'])
                ev=[projector._evidence_row(observation=o,result=result,company=company,projection=spec['compiled']['legacy_projection'],source_index=indexes['sources'],raw_index=indexes['raw'],fiscal_year=str(manifest['target_period']['fiscal_year'])) for o in ordered]
            else:row,ev=baseline,_evidence_for_blocked(company,selected)
        blockers=list(audit['reasons'])+selected['input']['adoption_blockers']
        row['notes']+='; exact saved ordinary filing; '+(';'.join(blockers) if blockers else 'STRUCTURED_PRIMARY_VERIFIED')
        if selected['input']['adoption_blockers']:
            # Keep native as-filed Result and evidence, but never expose it as
            # an accepted replacement while amendment relevance is unresolved.
            row['notes']+='; native as-filed value='+str(result['value']);row['value']='';row['status']='NEEDS_REVIEW'
        replacements[key(row)]=row;ev_replacements[key(row)]=ev
        coverage.append({'company_id':cid,'company':company['display_name'],'applicability':result['applicability'],'result':result,'public_status':row['status'],'as_filed_value':result['value'],'actual_period':manifest['target_period'],'source':selected['input']['sources'],'debt_branch':audit['branch'],'debt':audit['debt'],'equity':audit['equity'],'nonpositive_equity':audit['nonpositive_equity'],'blockers':blockers,'amendments':selected['input']['later_amendments']})
        bindings.append({'company_id':cid,'metric_id':'B06','origin':'ADOPTED_NATIVE_CANDIDATE','run_id':manifest['run_id'],'run_status':manifest['status'],'result_id':result['result_id'],'snapshot_run_path':'runs/'+cid,'adoption_status':'BLOCKED' if blockers else 'PRIMARY_VERIFIED_PENDING_APPROVAL','row_hash':content_hash(value=row),'evidence_hash':content_hash(value=ev)})
        runs[cid]=(manifest,records)
    metrics=projector.project_metric_rows(legacy_rows=old_rows,migrated_keys=keys,replacement_rows=replacements,fieldnames=pub.METRIC_FIELDS)
    evidence=projector.project_evidence_rows(legacy_rows=old_ev,migrated_keys=keys,replacement_rows=ev_replacements,fieldnames=pub.EVIDENCE_FIELDS)
    need([r for r in metrics if key(r) not in keys]==[r for r in old_rows if key(r) not in keys] and [r for r in evidence if key(r) not in keys]==[r for r in old_ev if key(r) not in keys],'R5_INHERITED_ROWS_CHANGED')
    prior=strict_json_loads(text=predecessor.read_bytes(relative_path=BATCH).decode());need(len(prior['cumulative_result_bindings'])==240,'R5_PREDECESSOR_SCOPE_CHANGED')
    policy=strict_json_file(path=data/primary.POLICY_PATH)
    plan=strict_json_file(path=data/policy['draft_release_plan'])
    need(plan['draft_plan_id']==content_hash(value={k:v for k,v in plan.items() if k!='draft_plan_id'})==policy['draft_release_plan_id'] and plan['production_authorized'] is False and plan['r4_completed'] is False,'R5_DRAFT_RELEASE_PLAN_CHANGED')
    need({(r['company_id'],r['metric_id']) for r in prior['cumulative_result_bindings']}=={(r['company_id'],r['metric_id']) for r in plan['parent_scope_keys']} and {(c['company_id'],'B06') for c in companies}=={(r['company_id'],r['metric_id']) for r in plan['proposed_new_keys']},'R5_DRAFT_COMPLETE_SCOPE_CHANGED')
    retained=[{'company_id':r['company_id'],'metric_id':r['metric_id'],'origin':'PINNED_PREDECESSOR','publication_id':predecessor.publication_id} for r in prior['cumulative_result_bindings']]
    need(not any(r['metric_id']=='B06' for r in retained),'R5_ALREADY_IN_PREDECESSOR')
    need({key(r) for r in metrics}==old_keys|keys and len(metrics)==len(old_keys|keys),'R5_PUBLIC_KEY_UNION_CHANGED')
    batch=record({'record_type':'R5_COMPLETE_CANDIDATE_BINDINGS','schema_version':1,'previous_publication_id':predecessor.publication_id,'cumulative_result_bindings':retained+bindings,'selected_result_count':10,'inherited_result_count':240,'public_row_count':len(metrics),'predecessor_public_row_count':len(old_rows),'new_public_keys':sorted(keys-old_keys),'unchanged_public_row_count':len(old_keys-keys),'formal_metric_count_unchanged':24,'candidate_scope_only':True},'batch_manifest_id')
    indexes=projector._record_indexes(runs=list(runs.values()))
    # Include rejected source references in ledger closure, too.
    indexes['used_source_reference_ids']=set(indexes['sources'])
    return metrics,evidence,batch,coverage,indexes


def _compose(snapshot, predecessor, meta):
    data=snapshot/'data';requirement=load_requirement_snapshot(snapshot_dir=data/'requirements'/primary.REQUIREMENT_ID)
    need(meta['policy']==requirement['policy'],'R5_POLICY_CHANGED')
    metrics,evidence,batch,coverage,indexes=_projection(data,snapshot/'runs',predecessor)
    ledger,provenance=_ledger(snapshot,indexes)
    blocked=[r['company_id'] for r in coverage if r['blockers']]
    adoption=record({'record_type':'R5_STRUCTURED_CANDIDATE_RECEIPT','status':'BLOCKED' if blocked else 'PENDING_APPROVAL','requirement_id':requirement['requirement_id'],'requirement_closure_hash':requirement['requirement_closure_hash'],'batch_manifest_id':batch['batch_manifest_id'],'coverage':coverage,'business_calls':[0,0,0],'formal_adoption':False},'adoption_receipt_id')
    # Receipt references the complete batch, never the reverse: both IDs keep
    # their ordinary whole-object content-hash definition without a cycle.
    projection=record({'record_type':'R5_PROJECTION_CANDIDATE','batch_manifest_id':batch['batch_manifest_id'],'adoption_receipt_id':adoption['adoption_receipt_id'],'publication_candidate_status':'BLOCKED','source_coverage_blockers':blocked,'requirement_id':requirement['requirement_id'],'requirement_hashes':requirement['hashes'],'requirement_closure_hash':requirement['requirement_closure_hash']},'projection_manifest_id')
    files={'metrics_matrix.csv':pub._csv_bytes(rows=metrics,fieldnames=pub.METRIC_FIELDS),'metric_evidence.csv':pub._csv_bytes(rows=evidence,fieldnames=pub.EVIDENCE_FIELDS),'coverage_matrix.csv':pub._csv_bytes(rows=pub._expected_coverage_rows(metrics=metrics,evidence=evidence),fieldnames=pub.COVERAGE_FIELDS),'stratified_audit.csv':pub._csv_bytes(rows=pub._expected_stratified_rows(metrics=metrics,evidence=evidence,migrated_ids={r['metric_id'] for r in batch['cumulative_result_bindings']}),fieldnames=pub.STRATIFIED_FIELDS),'projection_manifest.json':_json(projection)}
    for n in ['semantic_audit_receipt.json','scalability_audit.csv','legacy_invariant_migration_receipt.json']:
        files[n]=predecessor.read_bytes(relative_path=n)
    checks={'NATIVE_RUNS_REPLAYED':True,'TEN_NEW_COORDINATES':len(coverage)==10,'COMPLETE_PUBLIC_KEY_UNION':len(metrics)==batch['predecessor_public_row_count']+len(batch['new_public_keys']),'NO_OLD_B06_FILL':True,'PRODUCTION_NOT_AUTHORIZED':True}
    files['golden_results.csv']=pub._csv_bytes(rows=[{'assertion_id':k,'description':k,'expected':'True','actual':str(v),'status':'PASS','evidence_path':BATCH,'notes':'Candidate content check only; source blockers remain.'} for k,v in checks.items()],fieldnames=pub.GOLDEN_FIELDS)
    files['repair_validation_results.csv']=pub._csv_bytes(rows=[{'check_id':k,'severity':'ERROR','status':'PASS','details':'Candidate content; not production acceptance'} for k in checks],fieldnames=pub.REPAIR_FIELDS)
    files['validation_run_manifest.json']=_json({'run_id':'r5:'+adoption['adoption_receipt_id'],'mode':pub.RECORDED_VALIDATION_MODE,'result':'BLOCKED','source_commit':meta['implementation_head'],'blocked_coordinates':blocked,'production_authorized':False,'inherited_audits_not_reexecuted':['semantic_audit_receipt.json','scalability_audit.csv','legacy_invariant_migration_receipt.json']})
    files.update(pub._expected_documents(metrics=metrics,projection=projection,validation_mode=pub.RECORDED_VALIDATION_MODE))
    files['README_RUN.md']+=b'\nB06 structured-primary draft. BLOCKED: unresolved source coverage/amendments and production authority. Inherited audit files retain their original scope; they are not a new-code certification.\n'
    validation=record({'record_type':'R5_CANDIDATE_VALIDATION','status':'BLOCKED','content_checks':checks,'source_coverage_blockers':blocked,'publication_credit':CREDIT,'adoption_receipt_id':adoption['adoption_receipt_id'],'ledger_binding':ledger,'artifacts':{p:{'sha256':sha256_bytes(content=b),'size':len(b)} for p,b in sorted(files.items())}},'validation_receipt_id')
    files['publication_validation_receipt.json']=_json(validation)
    need(set(files)==pub.REQUIRED_BUNDLE_FILES,'R5_COMPLETE_PUBLIC_FILE_SET_CHANGED')
    return files,requirement,batch,adoption,projection,validation,ledger,provenance


def prepare(*, candidate_root):
    from .annual_publication import safe_root
    from .batch_workflow import _registry_rows
    root=safe_root(candidate_root);need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT).strip(),'R5_CLEAN_CODE_REQUIRED')
    done=root/'prepared.json'
    if done.exists():
        saved=strict_json_file(path=done);pub.verify_publication_bundle(bundle_dir=root/'outputs/publications'/saved['publication_id']);return {**saved,'status':'REUSED_COMPLETE_CANDIDATE'}
    need(not root.exists(),'R5_CANDIDATE_ROOT_EXISTS');root.mkdir()
    predecessor=pub.PublicationView.open(publication_root=ROOT);pointer=(ROOT/'outputs/active_publication.json').read_bytes();head=_code_head()
    snapshot=root/'snapshot';data=snapshot/'data';primary.prepare_data(code_root=ROOT,data_root=data)
    for company in _registry_rows(repo_root=data):primary.create_primary_run(data_root=data,run_dir=snapshot/'runs'/company['company_id'],company=company)
    meta={'record_type':'R5_CANDIDATE_IMPLEMENTATION','implementation_head':head,'implementation_tree':_code_identity(head),'policy':strict_json_file(path=ROOT/primary.POLICY_PATH),'predecessor_publication_id':predecessor.publication_id,'predecessor_manifest_sha256':sha256_file(path=predecessor.bundle_dir/'publication_manifest.json'),'snapshot_files':_tree_files(root=snapshot)}
    meta['saved_source_origin_paths']=_verify_saved_input_origin(data,head)
    public,requirement,batch,adoption,projection,validation,ledger,provenance=_compose(snapshot,predecessor,meta)
    files={**public,META:_json(meta),BATCH:_json(batch),'internal/r5_adoption.json':_json(adoption),'internal/r5_locator_provenance.json':_json(provenance)}
    pub._copy_tree_into_closure(source_root=snapshot,destination_root=Path(SNAPSHOT),files=files)
    pub._copy_tree_into_closure(source_root=predecessor.bundle_dir,destination_root=Path('internal/predecessor')/predecessor.publication_id,files=files)
    body={'candidate_status':'BLOCKED','artifact_requirement_generation':'EXPLICIT_REQUIREMENT_V1','requirement_id':requirement['requirement_id'],'requirement_closure_hash':requirement['requirement_closure_hash'],'requirement_hashes':requirement['hashes'],'projection_requirement_hashes':requirement['hashes'],'batch_manifest_id':batch['batch_manifest_id'],'projection_manifest_id':projection['projection_manifest_id'],'validation_receipt_id':validation['validation_receipt_id'],'ledger_binding':ledger,'previous_publication_id':predecessor.publication_id,'annual_adoption_receipt_id':adoption['adoption_receipt_id'],'publication_credit':CREDIT,'files':[{'path':p,'sha256':sha256_bytes(content=b),'size':len(b)} for p,b in sorted(files.items())]}
    manifest=validate_record(record={'record_type':ANNUAL_PUBLICATION_MANIFEST_TYPE,'publication_id':'publication_'+content_hash(value=body)[7:],**body})
    need(pointer==(ROOT/'outputs/active_publication.json').read_bytes() and _code_head()==head,'R5_PREDECESSOR_OR_CODE_CHANGED')
    pub._persist_prepared_publication_bundle(publications_dir=root/'outputs/publications',files=files,manifest=manifest)
    result={'status':'COMPLETE_CANDIDATE_BLOCKED','publication_id':manifest['publication_id'],'manifest_sha256':sha256_file(path=root/'outputs/publications'/manifest['publication_id']/'publication_manifest.json'),'previous_publication_id':predecessor.publication_id,'code':meta,'coverage':adoption['coverage'],'new_provider_paid_sec_calls':[0,0,0],'formal_active_unchanged':True}
    done.write_bytes(_json(result));return result


def verify_annual_bundle(*, bundle_dir, manifest):
    need(manifest['publication_credit']==CREDIT and manifest['candidate_status']=='BLOCKED','R5_DRAFT_CREDIT_REQUIRED')
    meta=strict_json_file(path=bundle_dir/META)
    need(meta['implementation_tree']==_code_identity(meta['implementation_head']),'R5_IMPLEMENTATION_CHANGED')
    expected_policy=json.loads(subprocess.check_output(['git','show',meta['implementation_head']+':'+primary.POLICY_PATH],cwd=ROOT))
    need(meta['policy']==expected_policy,'R5_TRUSTED_POLICY_CHANGED')
    snapshot=bundle_dir/SNAPSHOT;need(_tree_files(root=snapshot)==meta['snapshot_files'],'R5_SNAPSHOT_CHANGED')
    need(_verify_saved_input_origin(snapshot/'data',meta['implementation_head'])==meta['saved_source_origin_paths'],'R5_SOURCE_ORIGIN_SET_CHANGED')
    original_pointer=json.loads(subprocess.check_output(['git','show',meta['implementation_head']+':outputs/active_publication.json'],cwd=ROOT))
    need(original_pointer['publication_id']==meta['predecessor_publication_id'] and original_pointer['bundle_manifest_sha256']==meta['predecessor_manifest_sha256'],'R5_PREDECESSOR_ORIGIN_CHANGED')
    for rel in [primary.SPEC_PATH,primary.POLICY_PATH,expected_policy['draft_release_plan']]+['requirements/'+primary.REQUIREMENT_ID+'/'+n for n in ['CONTRACT.md','baseline_manifest.json','decision_register.json','transfer_manifest.json','invariant_profile.json']]:
        expected=subprocess.check_output(['git','show',meta['implementation_head']+':'+rel],cwd=ROOT)
        need((snapshot/'data'/rel).read_bytes()==expected,'R5_TRUSTED_RULE_BYTES_CHANGED')
    pred_dir=bundle_dir/'internal/predecessor'/manifest['previous_publication_id'];old=pub.verify_publication_bundle(bundle_dir=pred_dir)
    need(old['publication_id']==meta['predecessor_publication_id'] and sha256_file(path=pred_dir/'publication_manifest.json')==meta['predecessor_manifest_sha256'],'R5_PREDECESSOR_CHANGED')
    pred=pub.PublicationView(publication_id=old['publication_id'],bundle_dir=pred_dir,manifest=old)
    files,req,batch,adoption,projection,validation,ledger,provenance=_compose(snapshot,pred,meta)
    need(manifest['requirement_id']==req['requirement_id'] and manifest['requirement_hashes']==req['hashes'] and manifest['projection_requirement_hashes']==req['hashes'] and manifest['batch_manifest_id']==batch['batch_manifest_id'] and manifest['annual_adoption_receipt_id']==adoption['adoption_receipt_id'] and manifest['projection_manifest_id']==projection['projection_manifest_id'] and manifest['validation_receipt_id']==validation['validation_receipt_id'] and manifest['ledger_binding']==ledger,'R5_REPLAY_BINDING_CHANGED')
    files.update({META:_json(meta),BATCH:_json(batch),'internal/r5_adoption.json':_json(adoption),'internal/r5_locator_provenance.json':_json(provenance)})
    for rel,b in files.items():need((bundle_dir/rel).read_bytes()==b,'R5_PROJECTED_BYTES_CHANGED:'+rel)
    expected=set(files)|{SNAPSHOT+'/'+p for p in meta['snapshot_files']}|{'internal/predecessor/'+old['publication_id']+'/'+p for p in _tree_files(root=pred_dir)}
    need(expected=={p['path'] for p in manifest['files']},'R5_COMPLETE_FILE_SET_CHANGED')
    return manifest


def commit_authority(**kwargs):raise pub.PublicationError('R5_PRODUCTION_AND_SWITCH_NOT_AUTHORIZED')
def guard_switch(**kwargs):raise pub.PublicationError('R5_PRODUCTION_AND_SWITCH_NOT_AUTHORIZED')
def guard_recovery(**kwargs):raise pub.PublicationError('R5_RECOVERY_NOT_AUTHORIZED')
def guard_mirror_repair(**kwargs):raise pub.PublicationError('R5_MIRROR_WRITE_NOT_AUTHORIZED')
