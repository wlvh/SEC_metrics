"""Final byte/source/log checks; does not rerun the full integration suite."""
from pathlib import Path
import sys,json,hashlib,csv,subprocess,datetime
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');O=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');W=O/'continuation';D=W/'offline-02';sys.path.insert(0,str(R/'scripts'))
from vnext import annual_continuity as f,annual_publication as annual,publication as pub,invocation_control as ctl
from vnext.canonical import strict_json_file,strict_json_loads,canonical_json_bytes,sha256_file
from vnext.records import validate_record

def read(p):return strict_json_file(path=p)
def proof(p):return {'path':str(p),'sha256':sha256_file(path=p),'size':p.stat().st_size}
def records(p):return [strict_json_loads(text=l) for l in p.read_text().splitlines() if l.strip()]
code=f.code_identity();assert code['exact_head']=='1ea60fd44a0e401963515102ed2eadfc28f7e851'
command=read(W/'offline-02-command.json');log=(W/'offline-02-command.log').read_text()
assert command['exit_code']==0 and command['head']==command['head_after']==code['exact_head']
assert command['log_sha256']==sha256_file(path=W/'offline-02-command.log')=='95f66067cf77ebc4bbe367f63d2c8cba8693febe1dab627cdde8ff9712445676' and command['log_size']==639
assert log.count(' ... ok')==3 and 'Ran 3 tests in 4383.794s\n\nOK' in log and 'skip' not in log.lower()
binding=read(D/'binding.json');assert binding['code']==code and binding['status']=='PASSED_OFFLINE_HTTP_REPLAY_NOT_FRESH_PROVIDER' and binding['actual_new_provider_paid_sec_calls']==[0,0,0]
stage_binding=read(D/'stage/stage-binding.json');stage=stage_binding['stage'];f.validate_stage(stage);assert stage['stage_id']==binding['stage_id'] and stage['maximum_provider_paid_sec_calls']==[2,2,0] and stage['update_period_ends']==['2024-12-31','2025-12-31']
assert stage['previous_stage']['counts']['provider']==stage['previous_stage']['counts']['paid']==1 and stage['previous_stage']['counts']['sec_reserved']==0
output={'record_type':'INDEPENDENT_FINAL_OFFLINE_MATERIAL_VERIFICATION','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','reviewer_task':'/root/runtime_boundary_review','code':code,'command':proof(W/'offline-02-command.json'),'log':proof(W/'offline-02-command.log'),'packages':[],'candidate_io':[],'actual_new_provider_paid_sec_calls':[0,0,0]}
first,second,repeat1,repeat2=[read(D/n) for n in ('first.json','second.json','repeat-first.json','repeat-second.json')]
assert first['status']==second['status']=='COMPLETE_UPDATE_COMMITTED' and first['execution']==second['execution']=='EXECUTED'
for r in (first,second,repeat1,repeat2):assert r['inspection']=={'execution':'NOT_EXECUTED','provider_paid_sec_calls':[0,0,0]} and 'provider_paid_sec_calls' not in r
assert repeat1['status']==repeat2['status']=='NO_CHANGE' and repeat1['counts']['provider']==1 and repeat2['counts']['provider']==2
assert first['published_before']['provenance']['publication_id']==binding['s0'] and first['current_published']['provenance']['publication_id']==binding['s1']
assert second['published_before']['provenance']['publication_id']==binding['s1'] and second['current_published']['provenance']['publication_id']==binding['s2']
io=read(D/'synthetic-io-binding.json');mapping={}
for row in io['entries']:
 old=Path(row['run_directory']);a=next(x for x in records(old/'records.jsonl') if x['record_type']=='AI_EXTRACTION_ATTEMPT');req=(old/a['request_body_path']).read_bytes();res=(old/a['raw_response_path']).read_bytes()
 assert hashlib.sha256(req).hexdigest()==row['original_request_sha256'] and hashlib.sha256(res).hexdigest()==row['original_response_sha256']
 request=canonical_json_bytes(value={**json.loads(req),'model':'deepseek-flash'});response=canonical_json_bytes(value={**json.loads(res),'model':'deepseek-flash','id':'SIMULATED_MODEL_ENVELOPE'})
 assert hashlib.sha256(request).hexdigest()==row['synthetic_request_sha256'] and hashlib.sha256(response).hexdigest()==row['synthetic_response_sha256'] and json.loads(response)['choices']==json.loads(res)['choices']
 mapping[row['synthetic_request_sha256']]=(request,response,row)
previous=stage['initial_publication_pointer']['publication_id']
expected=[('s0',2023,'23713000000','0.692'),('s1',2024,'25100000000','0.698'),('s2',2025,'26186000000','0.693')]
for label,year,b01,b10 in expected:
 p=D/'stage/publication/outputs/publications'/binding[label];m=validate_record(record=read(p/'publication_manifest.json'))
 assert m['publication_id']==binding[label] and m['previous_publication_id']==previous
 files={x['path'] for x in m['files']}|{'publication_manifest.json'};actual=set()
 for q in p.rglob('*'):
  assert not q.is_symlink()
  if q.is_file():actual.add(q.relative_to(p).as_posix())
 assert actual==files
 for row in m['files']:
  q=p/row['path'];assert q.stat().st_size==row['size'] and sha256_file(path=q)==row['sha256']
 meta=read(p/annual.META);assert meta['implementation_head']==code['exact_head']
 batch=read(p/annual.BATCH);assert (len(batch['cumulative_result_bindings']),batch['selected_result_count'],batch['inherited_result_count'])==(240,2,238)
 with (p/'metrics_matrix.csv').open() as stream:assert len(list(csv.DictReader(stream)))==327
 view=pub.PublicationView(publication_id=m['publication_id'],bundle_dir=p,manifest=m);selected={}
 for metric,value in [('B01',b01),('B10',b10)]:
  native=view.native_result(company_id='marriott_international',metric_id=metric);result=native['result'];assert result['period_end']==str(year)+'-12-31' and result['value']==value and native['owner_publication_id']==m['publication_id']
  source_records=[strict_json_loads(text=l) for l in native['records_raw'].decode().splitlines()];sources=[]
  for src in native['sources']:
   raw=next(x for x in source_records if x['record_type']=='RAW_BLOB' and x['raw_asset_id']==src['raw_asset_id']);relative='internal/annual_snapshot/data/'+raw['storage_uri'];body=view.read_bytes(relative_path=relative)
   assert hashlib.sha256(body).hexdigest()==raw['raw_asset_id'][7:] and len(body)==raw['byte_length'];sources.append({'reference':src,'bundle_path':relative,'sha256':hashlib.sha256(body).hexdigest(),'size':len(body)})
  selected[metric]={'result':result,'manifest_sha256':hashlib.sha256(native['manifest_raw']).hexdigest(),'records_sha256':hashlib.sha256(native['records_raw']).hexdigest(),'sources':sources}
 output['packages'].append({'label':label,'publication_id':m['publication_id'],'predecessor':previous,'manifest':proof(p/'publication_manifest.json'),'exact_bound_file_count':len(m['files']),'selected':selected,'verification_scope':'Independent all-file byte checks and native result/source resolution. Full semantic replay supplied by completed integration log.'});previous=m['publication_id']
 print(label,'verified',flush=True)
for c in sorted((D/'stage/candidates').iterdir()):
 plan=read(c/'plan.json');rs=records(c/'b10/records.jsonl');a=next(x for x in rs if x['record_type']=='AI_EXTRACTION_ATTEMPT');request,response,ioentry=mapping[a['request_body_sha256']]
 assert (c/'b10'/a['request_body_path']).read_bytes()==request and (c/'b10'/a['raw_response_path']).read_bytes()==response
 assert a['status']=='SUCCEEDED' and a['model_requested']==a['model_returned']=='deepseek-flash' and a['provider_request_id']=='SIMULATED_HTTP_REPLAY'
 p=next((c/'invocation_control/executions').glob('*.json'));terminal=read(p);ctl._load_execution_receipt(root=c/'invocation_control',path=p,execution_id=terminal['execution_id'])
 assert terminal['status']=='SUCCEEDED' and terminal['counters']=={'real_model_provider_egress_count':1,'paid_model_provider_call_count':1,'mock_transport_invocation_count':0}
 output['candidate_io'].append({'plan_id':plan['plan_id'],'ordinal':plan['ordinal'],'period':plan['prepared_input']['table_input']['target_period'],'request':proof(c/'b10'/a['request_body_path']),'response':proof(c/'b10'/a['raw_response_path']),'derivation':ioentry,'native_execution_id':terminal['execution_id'],'evidence_scope':'SYNTHETIC_HTTP_IO_NOT_REAL_API_RESPONSE'})
assert len(output['candidate_io'])==2 and set(binding['request_hashes'])=={x['request']['sha256'] for x in output['candidate_io']}
assert f.budget_counts(stage)==binding['simulated_native_controller_calls']
# Independently refresh old complete live tree and protected current repository files.
old=read(W/'original-live-file-proofs.json');oldroot=Path(old['root']);actual={p.relative_to(oldroot).as_posix() for p in oldroot.rglob('*') if p.is_file()};assert actual==set(old['files'])
for relative,expected in old['files'].items():
 p=oldroot/relative;assert p.stat().st_size==expected['size'] and sha256_file(path=p)==expected['sha256']
base=read(W/'tracked-baseline.json');basehead=read(W/'baseline.json')['head'];changed=set(subprocess.check_output(['git','diff','--name-only',basehead,'HEAD'],cwd=R,text=True).splitlines());count=0
for relative,expected in base.items():
 if relative in changed:continue
 p=R/relative;assert p.stat().st_size==expected['size'] and sha256_file(path=p)==expected['sha256'];count+=1
assert read(R/'outputs/active_publication.json')==read(W/'baseline.json')['active']
ci=read(W/'ci-1ea60fd.json');fast=read(W/'ci-1ea60fd-fast-record.json');cilog=(W/'ci-1ea60fd.log').read_text()
assert ci['headSha']==code['exact_head'] and ci['conclusion']=='success'
lines=[line[line.index('{'):].strip() for line in cilog.splitlines() if '{"duration_seconds"' in line and '"evidence_tier"' in line];assert len(lines)==1 and strict_json_loads(text=lines[0])==fast
assert fast['status']=='PASSED' and len(fast['tests'])==40 and all(x['return_code']==0 for x in fast['tests'])
assert f.code_identity()==code
output.update(status='PASS',old_live_files_unchanged=len(old['files']),current_tracked_files_unchanged=count,ci={'metadata':proof(W/'ci-1ea60fd.json'),'raw_log':proof(W/'ci-1ea60fd.log'),'raw_result_exact_match':True,'entries':40},timing={'unittest_reported_seconds':'4383.794','command_elapsed_seconds':str(command['elapsed_seconds']),'started_at_utc':command['started_at_utc'],'finished_at_utc':command['finished_at_utc'],'utc_difference_seconds':str((datetime.datetime.fromisoformat(command['finished_at_utc'])-datetime.datetime.fromisoformat(command['started_at_utc'])).total_seconds()),'discrepancy_cause':'NOT_INDEPENDENTLY_INVESTIGATED','performance_pass_claimed':False},third_method_verified=True,full_suite_independently_reexecuted=False)
(W/'independent-offline-final-checks.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str)+'\n')
print('PASS',len(old['files']),'old files',count,'tracked files',flush=True)
