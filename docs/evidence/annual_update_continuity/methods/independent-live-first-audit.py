"""Read-only audit of a failed real response; never creates a Run or permission."""
from pathlib import Path
import sys,json,hashlib,datetime
from decimal import Decimal
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT/'scripts'))
from vnext.canonical import strict_json_file,strict_json_loads,sha256_file,content_hash,canonical_json_bytes
from vnext import annual_continuity as flow,annual_runtime as runtime,annual_input,invocation_control as control
from vnext.run_store import _mechanically_replay_open_run
from vnext.records import validate_record
from vnext.sources import load_raw_blob_bytes
from vnext.table_grid import build_table_grid,resolve_cell
from vnext.reader import validate_reader_output
from vnext.annual_evidence import check_annual_evidence
from vnext.ai_adapter import _controller_usage

def read(p):return strict_json_file(path=p)
def proof(p):return {'path':str(p),'sha256':sha256_file(path=p),'size':p.stat().st_size}
def recs(p):return [strict_json_loads(text=l) for l in p.read_text().splitlines() if l.strip()]
def tree(p):return {str(x.relative_to(p)):proof(x) for x in p.rglob('*') if x.is_file()}
def save(name,value):
 p=OUT/name;p.write_bytes(canonical_json_bytes(value=value)+b'\n');return proof(p)
C=OUT/'live/stage/candidates/6867f54821e36e70159fe83e9ca8abb5d51828c9e151a5819fca048650cd53cc';STAGE=OUT/'live/stage'
before=tree(C);code=flow.code_identity();binding=read(STAGE/'stage-binding.json');stage=binding['stage'];owner=binding['owner_comment'];plan=read(C/'plan.json')
assert code==stage['reviewed_code'] and code['exact_head']=='fce015270de0cc4a265ce0fb0d2179ef11ef98a7'
flow.check_id(stage,'stage_id');flow.validate_owner(stage,owner);flow.check_id(plan,'plan_id')
assert stage['stage_id']=='sha256:7db4fef84baa329b7c17effa9808ae55244d08ec27e9cc318302044622231688'
slot=read(OUT/'live/budget/provider-1.json');flow.check_id(slot,'slot_id');assert slot['stage_id']==stage['stage_id'] and slot['plan_id']==plan['plan_id']
assert len(list((OUT/'live/budget').glob('provider-*.json')))==1 and not list((OUT/'live/budget').glob('sec-*.json'))
req=flow._requirement();data=runtime.verify_data_root(Path(plan['data_root']),req)
prepared=annual_input.prepare_annual_input(repo_root=data,company_id=stage['policy']['company_id'],fiscal_year=plan['prepared_input']['table_input']['target_period']['fiscal_year'])
assert prepared==plan['prepared_input']
period=prepared['table_input']['target_period'];assert period=={'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}
# B01: real current structured replay plus an independent read of original facts.
m1,r1,_=_mechanically_replay_open_run(run_dir=C/'b01',repo_root=data,require_complete_results=True)
b01=next(x for x in r1 if x['record_type']=='METRIC_RESULT' and x['metric_id']=='B01')
trace=next(x for x in r1 if x['record_type']=='EXECUTION_TRACE' and x['trace_id']==b01['trace_id'])
obs=[x for x in r1 if x['record_type']=='VERIFIED_OBSERVATION' and x['observation_id'] in trace['input_observation_ids']]
assert len(obs)==1 and obs[0]['metric_id']=='B01';o=obs[0];source=o['source_binding']
raw1=next(x for x in r1 if x['record_type']=='RAW_BLOB' and x['raw_asset_id']==source['raw_asset_id'])
facts=read(data/raw1['storage_uri']);assert int(facts['cik'])==int(source['entity'])==int(prepared['company']['primary_cik']) if 'company' in prepared else int(facts['cik'])==int(source['entity'])==1048286
ns,concept=source['concept'].split(':');assert source['concept']=='us-gaap:Revenues' and o['unit']==b01['unit']=='USD'
matched=[f for f in facts['facts'][ns][concept]['units']['USD'] if f.get('start')==period['period_start'] and f.get('end')==period['period_end'] and f.get('accn')==source['accession'] and f.get('form')=='10-K' and f.get('fp')=='FY']
assert matched and {Decimal(str(f['val'])) for f in matched}=={Decimal(o['value'])}
assert b01['value']==trace['result']==o['value']=='25100000000' and trace['steps'][-1]['formula']=='revenue'
assert trace['steps'][-1]['resolved_values']=={'revenue':o['value']} and m1['target_period']==period
# Real provider marker, terminal, immutable response and usage.
r10=recs(C/'b10/records.jsonl');m10=read(C/'b10/manifest.json');a=next(x for x in r10 if x['record_type']=='AI_EXTRACTION_ATTEMPT')
for label in ('raw_response','assistant_output','request_body','reader_payload','output_schema'):
 assert sha256_file(path=C/'b10'/a[label+'_path'])==a[label+'_sha256']
raw_response=read(C/'b10'/a['raw_response_path']);request=read(C/'b10'/a['request_body_path'])
assert request['model']==plan['request']['model']==a['model_requested']=='deepseek-v4-flash'
assert raw_response['model']==a['model_returned']=='deepseek-flash'
assert raw_response['id']==a['provider_request_id']=='8483ddda-af4f-43aa-89ef-353e62c8e005'
assert raw_response['choices'][0]['message']['content'].encode()==(C/'b10'/a['assistant_output_path']).read_bytes()
assert a['status']=='FAILED' and a['error_class']=='DEEPSEEK_MODEL_IDENTITY_MISMATCH'
invocation=read(next((C/'invocation_control/plans').glob('*.json')))
history=control.prepare_historical_annual_invocation_view(repo_root=data,requirement_id=req['requirement_id'])
control.validate_ai_invocation_plan(plan=invocation,_historical_view=history)
execution_id=control.execution_identity(ai_invocation_plan_id=invocation['ai_invocation_plan_id'],owner_token=stage['stage_id'],authorized_at_utc=owner['created_at'])
e=control._load_execution_receipt(root=C/'invocation_control',path=control._execution_path(root=C/'invocation_control',execution_id=execution_id),execution_id=execution_id)
markers=control._egress_markers_for_execution(root=C/'invocation_control',execution_id=execution_id)
assert len(markers)==len(e['attempts'])==1 and e['status']=='FAILED_TERMINAL' and e['success_response_receipt_id'] is None
assert e['attempts']==control._attempt_receipts_for_execution(root=C/'invocation_control',execution_id=execution_id,plan=invocation,markers=markers)
assert e['counters']==control._counters_from_egress_markers(markers=markers,plan=invocation)=={'real_model_provider_egress_count':1,'paid_model_provider_call_count':1,'mock_transport_invocation_count':0}
usage=_controller_usage(raw_response_bytes=(C/'b10'/a['raw_response_path']).read_bytes());assert usage==e['attempts'][0]['usage']
u=raw_response['usage'];assert u['prompt_tokens']==159653 and u['completion_tokens']==776 and u['total_tokens']==160429
assert u['prompt_cache_hit_tokens']+u['prompt_cache_miss_tokens']==u['prompt_tokens']<=200000 and u['prompt_tokens']+u['completion_tokens']==u['total_tokens']
assert a['transport_observation']['retries_performed']==a['transport_observation']['retry_count']==0
assert not [x for x in r10 if x['record_type'] in {'METRIC_RESULT','EVIDENCE_CHECK','VERIFIED_OBSERVATION'}]
assert (C/'b10/review_decisions.jsonl').read_bytes()==b''
assert flow._provider_terminal(stage,slot,C)=={'provider':1,'status':'FAILED'}
# Fresh response distinct from known prior actual responses and offline replay ID.
old_ids=[];old_hashes=[]
audit=read(OUT/'historical-material-audit.json')
for item in audit['existing_real_provider_B10_runs']:
 rs=recs(Path(item['run_directory'])/'records.jsonl');old=next(x for x in rs if x['record_type']=='AI_EXTRACTION_ATTEMPT');old_ids.append(old['provider_request_id']);old_hashes.append(old['raw_response_sha256'])
assert a['provider_request_id'] not in old_ids and a['provider_request_id']!='SIMULATED_HTTP_REPLAY' and a['raw_response_sha256'] not in old_hashes
command=read(OUT/'live-logs/first-run-command.json');assert command['head']==command['head_after']==code['exact_head'] and command['exit_code']==2 and command['log_sha256']==sha256_file(path=Path(command['log']))
# Separate no-credit content diagnosis; the original failed model identity is untouched.
grid=next(x for x in r10 if x['record_type']=='DERIVED_ASSET');rm=next(x for x in r10 if x['record_type']=='READER_INPUT_MANIFEST');raw10=next(x for x in r10 if x['record_type']=='RAW_BLOB');sources=[x for x in r10 if x['record_type']=='SOURCE_REFERENCE']
source_bytes=load_raw_blob_bytes(repo_root=data,raw_blob=raw10)
assert build_table_grid(html_bytes=source_bytes,parent_raw_asset_ids=grid['parent_raw_asset_ids'],storage_uri=grid['storage_uri'])==grid
payload=read(C/'b10'/a['reader_payload_path']);task=payload['task_contract']
candidate=validate_reader_output(response_text=(C/'b10'/a['assistant_output_path']).read_text(),attempt_id=a['attempt_id'],required_roles=task['required_roles'],scope_contract=task['scope_contract'],source_reference_ids=rm['source_reference_ids'],derived_asset_ids=[grid['derived_asset_id']])
evidence=check_annual_evidence(requirement=req,target_period=period,candidate=candidate,derived_asset=grid,reader_manifest=rm,reader_payload_body=payload,source_references=sources,identity_constraints=task['identity_constraints'],scope_contract=task['scope_contract'])
assert evidence['status']=='REJECTED' and evidence['reason_codes']==['ANNUAL_SCOPE_VALUE_GROUP_MISMATCH']
claim=json.loads((C/'b10'/a['assistant_output_path']).read_text())['candidates'][0];value=resolve_cell(derived_asset=grid,locator=claim['locator']);table=next(t for t in grid['tables'] if t['table_id']==claim['locator']['table_id'])
labels=[{'response_label':x,'original_cell':resolve_cell(derived_asset=grid,locator=x['locator'])} for x in claim['scope_evidence_locators']]
assert all(x['response_label']['raw_text'] in (x['original_cell']['raw_text'],x['original_cell']['text']) for x in labels)
selected_row=value['origin_row_index'];headers=[c for row in table['rows'][:selected_row] for c in row['cells'] if c['is_origin'] and c['text']=='Comparable Company-Operated Properties']
assert selected_row==18 and value['text']=='69.7' and headers[-1]['origin_row_index']==8
correct_group=next(c for row in table['rows'] for c in row['cells'] if c['is_origin'] and c['text']=='Comparable Systemwide Properties')
correct_row=next(row for row in table['rows'][correct_group['origin_row_index']+1:] if any(c['is_origin'] and c['text']=='Worldwide (2)' for c in row['cells']))
correct_value=next(c for c in correct_row['cells'] if c['is_origin'] and c['origin_column_index']==value['origin_column_index'])
assert correct_group['origin_row_index']==19 and correct_row['row_index']==28 and correct_value['text']=='69.8'
diag={'record_type':'INDEPENDENT_LIVE_FAILURE_CONTENT_DIAGNOSIS','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','reviewer_task':'/root/runtime_boundary_review','status':'CONTENT_REJECTED_IN_SEPARATE_OFFLINE_DIAGNOSIS','original_model_identity_failure_preserved':True,'new_Run_created':False,'new_provider_paid_sec_calls':[0,0,0],'raw_response':proof(C/'b10'/a['raw_response_path']),'assistant_output':proof(C/'b10'/a['assistant_output_path']),'original_source':proof(data/raw10['storage_uri']),'full_source_grid_rebuilt_equal':True,'requirement_id':req['requirement_id'],'requirement_closure_hash':req['requirement_closure_hash'],'reader_result':'PASS','evidence':evidence,'claimed_value_cell':value,'claimed_scope_labels':labels,'actual_selected_group':headers[-1],'actual_systemwide_group':correct_group,'actual_systemwide_worldwide_cell':correct_value,'raw_text_correction':'FY2024 source grid itself contains literal backslash+n in Worldwide raw_text, exactly matching this response. Earlier reviewer leading-LF mismatch speculation was withdrawn after actual source comparison. Rejection is group ownership, not whitespace.','credit':'NO_EXECUTION_SUCCESS_NO_RESULT_NO_QUALIFICATION_NO_PUBLICATION','interpretation':'The returned claim69.7 uses Company-Operated Worldwide row18 and borrows Systemwide group row19 below it. Unchanged current Evidence rejects it; source Systemwide Worldwide is69.8 at row28. No response or locator was repaired.'}
diagnostic=save('independent-live-first-content-diagnosis.json',diag)
# Only S0 exists; no new complete success reference or publication is possible.
active=read(STAGE/'publication/outputs/active_publication.json');seed=read(STAGE/'seed-publication-result.json')
assert active['publication_id']==seed['publication_id'] and not (STAGE/'successful-candidate.json').exists()
formal=read(ROOT/'outputs/active_publication.json');assert formal==read(OUT/'baseline.json')['active']
report=read(OUT/'live-logs/first-run.json');assert report['counts']['provider']==report['counts']['paid']==1 and not report['counts']['uncertain_plans'] and report['counts']['sec_reserved']==0
assert before==tree(C) and flow.code_identity()==code
final={'record_type':'INDEPENDENT_REAL_FIRST_ANNUAL_FAILURE_AUDIT','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','reviewer_task':'/root/runtime_boundary_review','status':'CONFIRMED_REAL_FAILURE_NO_COMPLETE_ANNUAL_UPDATE','reviewed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code':code,'stage_id':stage['stage_id'],'approval_url':owner['html_url'],'approval_source_scope':'Saved real owner response and operator real-command evidence; reviewer did not issue approval or make network requests.','plan_id':plan['plan_id'],'source_preparation_rebuilt_equal':True,'prepared_sources':prepared['source_proofs'],'target_period':period,'B01':{'original_source':proof(data/raw1['storage_uri']),'companyfacts_cik':facts['cik'],'entity_name':facts.get('entityName'),'concept':source['concept'],'unit':'USD','original_matching_facts':matched,'observation':o,'trace':trace,'result':b01,'native_structured_replay':'PASS','Run_status':m1['status'],'attached_B03_retained':any(x.get('metric_id')=='B03' and x['record_type']=='METRIC_RESULT' for x in r1),'publication_limit':'Native candidate Result PUBLISHED flag is not a committed complete S1 or production publication.'},'B10':{'requested_model':request['model'],'returned_model':raw_response['model'],'error':a['error_class'],'attempt_status':a['status'],'Run_status':m10['status'],'raw_response':proof(C/'b10'/a['raw_response_path']),'assistant_output':proof(C/'b10'/a['assistant_output_path']),'provider_request_id':a['provider_request_id'],'source':proof(data/raw10['storage_uri']),'native_Evidence_count':0,'native_Review_count':0,'native_Result_count':0,'content_diagnosis':diagnostic},'execution':e,'usage':{'provider_usage':u,'native_usage':usage,'input_below_200000':True,'complete_arithmetic':True,'meaning':'Usage is observable despite failure and does not accept returned model identity or content. Native error receipt records status_code0; do not relabel that field as HTTP200.'},'actual_new_provider_paid_sec_calls':[1,1,0],'reviewer_new_provider_paid_sec_calls':[0,0,0],'retry':0,'unknown':False,'fresh_response_distinct_from_known_historical_fixture_ids_and_raw_hashes':True,'real_command':proof(OUT/'live-logs/first-run-command.json'),'real_command_log':proof(Path(command['log'])),'isolated_current_active':active,'formal_current_active':formal,'successful_candidate_reference_created':False,'candidate_original_files_unchanged_by_audit':True,'candidate_file_proofs':before,'output_scope_defect':{'status':'CONFIRMED_UNFIXED','native_counts_authoritative':report['counts'],'legacy_inspection_provider_paid_sec_calls':report['provider_paid_sec_calls'],'note':'Top-level inherited inspection zero counters must not be interpreted as actual zero execution; this live report saysEXECUTED with one real failure. Earlier offline successful report also wrongly retained NOT_EXECUTED. A future reviewed output-only patch must scope inspection fields explicitly; current executed code and raw reports are preserved.'},'limits':['No S1 complete candidate/publication; no FY2025 second real run.','No model alias or routing exception inferred or authorized.','Separate content diagnosis creates neither a native success nor a qualification/publication result.'],'script':proof(Path(__file__))}
print(json.dumps({'audit':save('independent-live-first-source-audit.json',final),'diagnostic':diagnostic,'status':final['status'],'counts':[1,1,0]},ensure_ascii=False))
