"""Independent read-only failure audit. No HTTP, permission creation or Run writes."""
from pathlib import Path
import sys,json,datetime
from decimal import Decimal
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');OUT=Path(__file__).parent;OLD=OUT.parent
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.canonical import strict_json_file,strict_json_loads,sha256_file,canonical_json_bytes
from vnext import annual_continuity as flow,annual_runtime as runtime,annual_input,invocation_control as control
from vnext.run_store import _mechanically_replay_open_run
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
C=OUT/'live/stage/candidates/31e2acf0bede067f8e9b21f1d266d326a9097e5b24b377b441672cbdcda700fe';STAGE=OUT/'live/stage'
OC=OLD/'live/stage/candidates/6867f54821e36e70159fe83e9ca8abb5d51828c9e151a5819fca048650cd53cc'
before=tree(C);old_before=tree(OC);code=flow.code_identity();binding=read(STAGE/'stage-binding.json');stage=binding['stage'];owner=binding['owner_comment'];plan=read(C/'plan.json')
assert code==stage['reviewed_code'] and code['exact_head']=='1ea60fd44a0e401963515102ed2eadfc28f7e851'
flow.check_id(stage,'stage_id');flow.validate_owner(stage,owner);flow.check_id(plan,'plan_id')
assert stage['stage_id']=='sha256:046b38a3d3f8a06187e1ab0fcd3ad89607b1ea7ec98a8b9926f4b23744678059'
previous=flow._previous_stage_proof(read(Path(stage['previous_stage']['stage_root'])/'stage-binding.json'))
assert previous==stage['previous_stage']
slot=read(OUT/'live/budget/provider-1.json');flow.check_id(slot,'slot_id');assert slot['stage_id']==stage['stage_id'] and slot['plan_id']==plan['plan_id']
assert len(list((OUT/'live/budget').glob('provider-*.json')))==1 and not list((OUT/'live/budget').glob('sec-*.json'))
req=flow._requirement();data=runtime.verify_data_root(Path(plan['data_root']),req)
prepared=annual_input.prepare_annual_input(repo_root=data,company_id=stage['policy']['company_id'],fiscal_year=2024)
assert prepared==plan['prepared_input']
period=prepared['table_input']['target_period'];assert period=={'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}
print('PASS stage, exact code, previous closed stage, input and source preparation',flush=True)
m1,r1,_=_mechanically_replay_open_run(run_dir=C/'b01',repo_root=data,require_complete_results=True)
b01=next(x for x in r1 if x['record_type']=='METRIC_RESULT' and x['metric_id']=='B01')
trace=next(x for x in r1 if x['record_type']=='EXECUTION_TRACE' and x['trace_id']==b01['trace_id'])
obs=[x for x in r1 if x['record_type']=='VERIFIED_OBSERVATION' and x['observation_id'] in trace['input_observation_ids']]
assert len(obs)==1 and obs[0]['metric_id']=='B01';o=obs[0];source=o['source_binding']
raw1=next(x for x in r1 if x['record_type']=='RAW_BLOB' and x['raw_asset_id']==source['raw_asset_id'])
facts=read(data/raw1['storage_uri']);assert int(facts['cik'])==int(source['entity'])==1048286
ns,concept=source['concept'].split(':');assert source['concept']=='us-gaap:Revenues' and o['unit']==b01['unit']=='USD'
matched=[f for f in facts['facts'][ns][concept]['units']['USD'] if f.get('start')==period['period_start'] and f.get('end')==period['period_end'] and f.get('accn')==source['accession'] and f.get('form')=='10-K' and f.get('fp')=='FY']
assert matched and {Decimal(str(f['val'])) for f in matched}=={Decimal(o['value'])}
assert b01['value']==trace['result']==o['value']=='25100000000' and trace['steps'][-1]['formula']=='revenue'
assert trace['steps'][-1]['resolved_values']=={'revenue':o['value']} and m1['target_period']==period
assert source['accession']=='0001628280-25-004818' and sha256_file(path=data/raw1['storage_uri'])=='af2fea717f696acfa6f5f2436aa6e4175c3c56ab1628a2e3198964300f32422a'
print('PASS B01 native replay and original CompanyFacts CIK, concept, annual period, USD, accession and calculation',flush=True)
r10=recs(C/'b10/records.jsonl');m10=read(C/'b10/manifest.json');a=next(x for x in r10 if x['record_type']=='AI_EXTRACTION_ATTEMPT')
for label in ('raw_response','assistant_output','request_body','reader_payload','output_schema'):
 assert sha256_file(path=C/'b10'/a[label+'_path'])==a[label+'_sha256']
raw_response=read(C/'b10'/a['raw_response_path']);request=read(C/'b10'/a['request_body_path'])
assert request['model']==plan['request']['model']==a['model_requested']==raw_response['model']==a['model_returned']=='deepseek-flash'
assert raw_response['id']==a['provider_request_id']=='fcfda19a-0aa8-4126-8963-e4e21703d5a2'
assert a['raw_response_sha256']=='c14db83fa4259075870fd5dd9e0160650f8627aa81b505c41bc9d827d0d5139c'
assert a['assistant_output_sha256']=='0314bedbdcfe8e80020093ff23fd8903b301a0740d07d41ce1966091c9b2772e'
assert raw_response['choices'][0]['message']['content'].encode()==(C/'b10'/a['assistant_output_path']).read_bytes()
assert a['status']=='FAILED' and a['error_class']=='EVIDENCE_FAILURE'
invocation=read(next((C/'invocation_control/plans').glob('*.json')))
history=control.prepare_historical_annual_invocation_view(repo_root=data,requirement_id=req['requirement_id'])
control.validate_ai_invocation_plan(plan=invocation,_historical_view=history)
execution_id=control.execution_identity(ai_invocation_plan_id=invocation['ai_invocation_plan_id'],owner_token=stage['stage_id'],authorized_at_utc=owner['created_at'])
assert execution_id=='sha256:489a130e61376e6516c9e9eb35cf07bfc27cbacbdb456f508551fcd03c4670d0'
e=control._load_execution_receipt(root=C/'invocation_control',path=control._execution_path(root=C/'invocation_control',execution_id=execution_id),execution_id=execution_id)
markers=control._egress_markers_for_execution(root=C/'invocation_control',execution_id=execution_id)
assert len(markers)==len(e['attempts'])==1 and e['status']=='FAILED_TERMINAL' and e['success_response_receipt_id'] is None
assert e['attempts']==control._attempt_receipts_for_execution(root=C/'invocation_control',execution_id=execution_id,plan=invocation,markers=markers)
assert e['counters']==control._counters_from_egress_markers(markers=markers,plan=invocation)=={'real_model_provider_egress_count':1,'paid_model_provider_call_count':1,'mock_transport_invocation_count':0}
usage=_controller_usage(raw_response_bytes=(C/'b10'/a['raw_response_path']).read_bytes());assert usage==e['attempts'][0]['usage']
terminal=e['attempts'][0];assert terminal['status_code']==200 and terminal['response_body_sha256']==a['assistant_output_sha256']
u=raw_response['usage'];assert u['prompt_tokens']==159653 and u['completion_tokens']==784 and u['total_tokens']==160437
assert u['prompt_cache_hit_tokens']==159488 and u['prompt_cache_miss_tokens']==165
assert u['prompt_cache_hit_tokens']+u['prompt_cache_miss_tokens']==u['prompt_tokens']<=200000 and u['prompt_tokens']+u['completion_tokens']==u['total_tokens']
assert a['transport_observation']['retries_performed']==a['transport_observation']['retry_count']==0
assert not [x for x in r10 if x['record_type'] in {'METRIC_RESULT','EVIDENCE_CHECK','VERIFIED_OBSERVATION'}]
assert (C/'b10/review_decisions.jsonl').read_bytes()==b''
assert flow._provider_terminal(stage,slot,C)=={'provider':1,'status':'FAILED'}
counts=flow.budget_counts(stage);assert counts['provider']==counts['paid']==counts['provider_reserved']==1 and counts['sec_reserved']==0 and not counts['uncertain_plans']
command=read(OUT/'live-logs/first-run-command.json');assert command['head']==command['head_after']==code['exact_head'] and command['exit_code']==2 and command['log_sha256']==sha256_file(path=Path(command['log']))
print('PASS fresh raw response identity, HTTP200, native failed terminal, actual usage and 1/1/0 counters',flush=True)
# Diagnose unchanged content separately: no Run, Evidence record or Review is saved by this checker.
grid=next(x for x in r10 if x['record_type']=='DERIVED_ASSET');rm=next(x for x in r10 if x['record_type']=='READER_INPUT_MANIFEST');raw10=next(x for x in r10 if x['record_type']=='RAW_BLOB');sources=[x for x in r10 if x['record_type']=='SOURCE_REFERENCE']
source_bytes=load_raw_blob_bytes(repo_root=data,raw_blob=raw10)
assert build_table_grid(html_bytes=source_bytes,parent_raw_asset_ids=grid['parent_raw_asset_ids'],storage_uri=grid['storage_uri'])==grid
assert sha256_file(path=data/raw10['storage_uri'])=='32a365d594e905c7b4fa8dac8efa501c9ca4ffeabe2579baf8e96bd52e08b131'
payload=read(C/'b10'/a['reader_payload_path']);task=payload['task_contract']
candidate=validate_reader_output(response_text=(C/'b10'/a['assistant_output_path']).read_text(),attempt_id=a['attempt_id'],required_roles=task['required_roles'],scope_contract=task['scope_contract'],source_reference_ids=rm['source_reference_ids'],derived_asset_ids=[grid['derived_asset_id']])
evidence=check_annual_evidence(requirement=req,target_period=period,candidate=candidate,derived_asset=grid,reader_manifest=rm,reader_payload_body=payload,source_references=sources,identity_constraints=task['identity_constraints'],scope_contract=task['scope_contract'])
assert evidence['status']=='REJECTED' and evidence['reason_codes']==['ANNUAL_SCOPE_VALUE_GROUP_MISMATCH']
claim=read(C/'b10'/a['assistant_output_path'])['candidates'][0];value=resolve_cell(derived_asset=grid,locator=claim['locator']);table=next(t for t in grid['tables'] if t['table_id']==claim['locator']['table_id'])
labels=[{'response_label':x,'original_cell':resolve_cell(derived_asset=grid,locator=x['locator'])} for x in claim['scope_evidence_locators']]
assert all(x['response_label']['raw_text']==x['original_cell']['raw_text'] for x in labels)
worldwide=labels[1]['original_cell'];assert worldwide['raw_text']=='\nWorldwide (2)' and [ord(c) for c in worldwide['raw_text'][:2]]==[10,87]
selected_row=value['origin_row_index'];headers=[c for row in table['rows'][:selected_row] for c in row['cells'] if c['is_origin'] and c['text']=='Comparable Company-Operated Properties']
assert selected_row==18 and value['text']=='69.7' and headers[-1]['origin_row_index']==8
correct_group=next(c for row in table['rows'] for c in row['cells'] if c['is_origin'] and c['text']=='Comparable Systemwide Properties')
correct_row=next(row for row in table['rows'][correct_group['origin_row_index']+1:] if any(c['is_origin'] and c['text']=='Worldwide (2)' for c in row['cells']))
correct_value=next(c for c in correct_row['cells'] if c['is_origin'] and c['origin_column_index']==value['origin_column_index'])
assert correct_group['origin_row_index']==19 and correct_row['row_index']==28 and correct_value['text']=='69.8'
column_header=[c for row in table['rows'][:4] for c in row['cells'] if c['origin_column_index']==15 and c['is_origin']]
assert any(c['text']=='Occupancy' for c in column_header) and any(c['text']=='2024' for c in column_header)
percent_cells=[c for c in correct_row['cells'] if c['is_origin'] and 15<=c['origin_column_index']<=17]
assert any(c['text']=='%' for c in percent_cells)
old_a=next(x for x in recs(OC/'b10/records.jsonl') if x['record_type']=='AI_EXTRACTION_ATTEMPT')
old_response=read(OC/'b10'/old_a['raw_response_path']);old_request=read(OC/'b10'/old_a['request_body_path']);old_claim=read(OC/'b10'/old_a['assistant_output_path'])['candidates'][0]
request_delta={k:{'old':old_request.get(k),'new':request.get(k)} for k in old_request.keys()|request.keys() if old_request.get(k)!=request.get(k)}
assert request_delta=={'model':{'old':'deepseek-v4-flash','new':'deepseek-flash'}}
assert old_a['error_class']=='DEEPSEEK_MODEL_IDENTITY_MISMATCH' and old_response['model']=='deepseek-flash'
assert old_a['raw_response_sha256']!=a['raw_response_sha256'] and old_a['assistant_output_sha256']!=a['assistant_output_sha256'] and old_a['provider_request_id']!=a['provider_request_id']
for field in ('claimed_value','claimed_unit','claimed_period','locator','claimed_scope','scope_evidence_locators'):
 assert claim[field]==old_claim[field],field
print('PASS unchanged Reader output; original-source Evidence REJECTED ANNUAL_SCOPE_VALUE_GROUP_MISMATCH; same wrong group selection as old response',flush=True)
diag={'record_type':'INDEPENDENT_REAL_CONTINUATION_FAILURE_CONTENT_DIAGNOSIS','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','reviewer_task':'/root/runtime_boundary_review','code':code,'requirement_id':req['requirement_id'],'requirement_closure_hash':req['requirement_closure_hash'],'raw_response':proof(C/'b10'/a['raw_response_path']),'assistant_output':proof(C/'b10'/a['assistant_output_path']),'original_source':proof(data/raw10['storage_uri']),'full_original_source_grid_rebuilt_equal':True,'reader_result':'PASS','evidence':evidence,'native_failed_run_unchanged':True,'new_Run_created':False,'new_Evidence_Review_Result_created':False,'claimed_value_cell':value,'claimed_scope_labels':labels,'selected_value_actual_group':headers[-1],'actual_systemwide_group':correct_group,'actual_systemwide_worldwide_value_cell':correct_value,'occupancy_year_column_headers':column_header,'source_percent_cells':percent_cells,'raw_character_proof':{'raw_text':worldwide['raw_text'],'prefix_codepoints':[ord(c) for c in worldwide['raw_text'][:2]],'meaning':'Actual leading LF (10), followed by W (87); length14. Both old and new response and original source grid match exactly including footnote (2). Earlier reviewer claims of literal backslash+n were incorrect interpretations of escaped display and are explicitly withdrawn. The first audit-script character assertion failed and is retained as attempt-1; no production or original history was edited. No whitespace or footnote mismatch is claimed.'},'source_business_interpretation':'69.7 at row18/col15 is Worldwide (2) within Comparable Company-Operated Properties beginning at row8. Systemwide begins at row19, after this value. Its own Worldwide (2) row28/col15 is69.8 for2024 Occupancy, source percent. Indices are zero-based and are observations, not manually supplied execution inputs.','old_failure_comparison':{'old_attempt':old_a,'request_json_delta':request_delta,'new_request_bytes':(C/'b10'/a['request_body_path']).stat().st_size,'old_request_bytes':(OC/'b10'/old_a['request_body_path']).stat().st_size,'same_selected_value_period_unit_locator_and_scope_labels':True,'new_raw_response_provider_id_and_assistant_bytes_differ':True,'interpretation':'Requested/returned model identity now matches. The newly acquired content repeats the old wrong business-group selection; the current native boundary fails on Evidence instead of the earlier model identity error.'},'minimum_future_change_suggestion':{'status':'PROPOSAL_ONLY_NOT_IMPLEMENTED_NOT_AUTHORIZED_FOR_CURRENT_CLOSED_STAGE','proposal':'Clarify the existing B10 prompt with the general group-boundary rule: choose the Worldwide value inside the block whose preceding group heading matches Comparable Systemwide Properties, ending at the next group heading. A heading below a value cannot establish that value\'s scope. Require each selected numeric cell and its scope evidence to belong to that same block. Keep full-source input and current deterministic Evidence guard; no hardcoded table, row, year or answer value.','limits':'This is a plausible targeted improvement, not a proven fix or permission to retry. Do not relabel the current failure, overwrite a response, relax the group guard, or spend the unused second FY2025 call as repair.'},'credit':'NO_EXECUTION_SUCCESS_NO_RESULT_NO_QUALIFICATION_NO_PUBLICATION','reviewer_provider_paid_sec_calls':[0,0,0]}
diagnostic=save('independent-continuation-first-content-diagnosis.json',diag)
active=read(STAGE/'publication/outputs/active_publication.json');seed=read(STAGE/'seed-publication-result.json')
assert active['publication_id']==seed['publication_id'] and not (STAGE/'successful-candidate.json').exists()
assert len(list((STAGE/'candidates').iterdir()))==1
formal=read(ROOT/'outputs/active_publication.json');assert formal==stage['initial_publication_pointer']
report=read(OUT/'live-logs/first-run.json');assert report['status']=='CANDIDATE_UPDATE_FAILED' and report['execution']=='EXECUTED'
assert report['inspection']['execution']=='NOT_EXECUTED' and report['inspection']['provider_paid_sec_calls']==[0,0,0] and 'provider_paid_sec_calls' not in report
assert report['counts']==counts
closed=read(OUT/'live/budget/closed.json');assert closed['counts']==counts and closed['stage_id']==stage['stage_id']
reentry=read(OUT/'live-logs/failed-reentry.json');assert reentry['error']=='CONTINUITY_FAILED_INPUT_REQUIRES_REVIEWED_REPAIR'
stop=read(OUT/'live-logs/stop-trigger.json');assert stop=={'running':False,'status':'TRIGGER_DISABLED'}
close=read(OUT/'live-logs/close-stage.json');assert close=={'counts':counts,'status':'STAGE_CLOSED'}
cold=read(OUT/'live-logs/cold-s0.json');assert cold['status']=='PASS_COLD_NATIVE_READ' and cold['actual_active_unchanged'] and cold['code']==code
assert before==tree(C) and old_before==tree(OC) and flow.code_identity()==code
out={'record_type':'INDEPENDENT_REAL_CONTINUATION_FIRST_FAILURE_AUDIT','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','reviewer_task':'/root/runtime_boundary_review','status':'CONFIRMED_REAL_FAILURE_NO_COMPLETE_ANNUAL_UPDATE','reviewed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code':code,'stage_id':stage['stage_id'],'approval_url':owner['html_url'],'approval_verification_scope':'Personally validated saved owner body, stage ID and recorded native authorization timestamp; no reviewer GitHub fetch, comment or permission creation.','plan_id':plan['plan_id'],'requirement_id':req['requirement_id'],'requirement_closure_hash':req['requirement_closure_hash'],'source_preparation_rebuilt_equal':True,'prepared_sources':prepared['source_proofs'],'period':period,'B01':{'native_replay':'PASS','source':proof(data/raw1['storage_uri']),'companyfacts_cik':facts['cik'],'entity_name':facts.get('entityName'),'concept':source['concept'],'original_matching_facts':matched,'observation':o,'trace':trace,'result':b01,'Run_status':m1['status'],'B03_retained':any(x.get('metric_id')=='B03' and x['record_type']=='METRIC_RESULT' for x in r1),'credit_limit':'Structured B01 candidate success does not constitute a complete annual update or isolated/production publication.'},'B10':{'model_requested':request['model'],'model_returned':raw_response['model'],'model_identity':'EXACT_MATCH','error_class':a['error_class'],'native_attempt_status':a['status'],'Run_status':m10['status'],'raw_response':proof(C/'b10'/a['raw_response_path']),'assistant_output':proof(C/'b10'/a['assistant_output_path']),'request':proof(C/'b10'/a['request_body_path']),'provider_request_id':a['provider_request_id'],'native_Evidence_count':0,'native_Review_count':0,'native_Result_count':0,'content_diagnosis':diagnostic,'no_credit':'Native acceptance stopped before Evidence/Review/Result persistence. Separate reviewer diagnosis is not a new native result.'},'execution':e,'usage':{'provider_usage':u,'native_usage':usage,'complete_arithmetic':True,'input_below_200000':True,'HTTP_status':200,'native_receipt_response_hash_meaning':'Evidence failure receipt binds parsed assistant output SHA; raw provider envelope has its separate SHA.'},'new_stage_actual_provider_paid_sec_calls':[1,1,0],'previous_stage_actual_provider_paid_sec_calls':[1,1,0],'cumulative_actual_provider_paid_sec_calls':[2,2,0],'reviewer_provider_paid_sec_calls':[0,0,0],'retry_count':0,'unknown':False,'previous_stage_proof_revalidated':previous,'new_counts':counts,'inspection_fields_correctly_scoped':True,'isolated_current_active':active,'formal_current_active':formal,'S1_S2_generated':False,'successful_candidate_reference_exists':False,'first_real_command':proof(OUT/'live-logs/first-run-command.json'),'first_real_command_log':proof(Path(command['log'])),'closed_stage':proof(OUT/'live/budget/closed.json'),'failure_reentry':{'file':proof(OUT/'live-logs/failed-reentry.json'),'result':reentry},'trigger_disabled':stop,'current_stage_closed':close,'cold_native_read':'Parent cold-read result/log read, not independently replayed expensive whole publication in this audit. Current active and seed files directly compared.','cold_native_read_evidence':proof(OUT/'live-logs/cold-s0.json'),'candidate_original_files_unchanged_by_audit':True,'old_failed_candidate_original_files_unchanged_by_audit':True,'candidate_file_proofs':before,'actual_review_scope':{'personally_executed':['stage/plan/slot content IDs and saved owner binding','previous closed stage proof and native counters','exact source preparation and full source-grid rebuild','B01 native replay and independent raw CompanyFacts matching','native WB3 invocation/marker/attempt/execution/usage validation','unmodified assistant Reader and Evidence rejection reproduction','original response semantic and byte identity comparison','no success reference, no S1/S2, actual active unchanged, closed stage and stopped trigger'], 'read_existing_evidence':['first real-command exact-head/log binding','parent cold native publication read'], 'not_performed':['provider or SEC requests','new GitHub approval verification over network','whole publication native graph replay again','future prompt fix or retry','production write']},'minimum_future_change_suggestion':diag['minimum_future_change_suggestion'],'script':proof(Path(__file__))}
print(json.dumps({'audit':save('independent-continuation-first-source-audit.json',out),'diagnosis':diagnostic,'status':out['status'],'new_counts':[1,1,0],'cumulative_counts':[2,2,0]},ensure_ascii=False),flush=True)
