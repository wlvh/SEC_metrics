"""Independent read-only byte/identity checks; full semantic replay is log-reviewed."""
from pathlib import Path
import csv,json,hashlib,sys,subprocess
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.canonical import strict_json_file,strict_json_loads,content_hash,sha256_file
from vnext.records import validate_record
from vnext.publication import PublicationView
from vnext.annual_continuity import code_identity,_requirement
from vnext import annual_publication as annual,invocation_control as controller

def read(p):return strict_json_file(path=p)
def proof(p):return {'path':str(p),'sha256':sha256_file(path=p),'size':p.stat().st_size}
code=code_identity();assert code['exact_head']=='ab4992486b8cb219fd11d4e2bbacc72db24fbc30'
run=OUT/'offline-acceptance-04';binding=read(run/'binding.json');assert binding['code']==code
command=read(OUT/'offline-acceptance-04-command.json');log=(OUT/'offline-acceptance-04-command.log').read_text()
assert command['exit_code']==0 and command['head']==command['head_after']==code['exact_head']
assert command['log_sha256']==sha256_file(path=Path(command['log']))=='f7bd2fcf6ad77e8b67b596f275a91632c91f9cde4f644be662958ff5aa6c3239'
assert command['log_size']==Path(command['log']).stat().st_size
assert 'Ran 3 tests in 3807.637s\n\nOK' in log and 'skipped' not in log.lower() and log.count(' ... ok')==3
ci=read(OUT/'ci-ab49924.json');fast=read(OUT/'ci-ab49924-fast-result.json');ci_log=(OUT/'ci-ab49924.log').read_text()
assert ci['headSha']==code['exact_head'] and ci['conclusion']=='success'
json_lines=[l[l.index('{'):].strip() for l in ci_log.splitlines() if '{"duration_seconds"' in l and '"evidence_tier"' in l]
assert len(json_lines)==1 and strict_json_loads(text=json_lines[0])==fast
assert fast['status']=='PASSED' and all(x['return_code']==0 for x in fast['tests'])
entry=next(x for x in fast['tests'] if x['test']=='tests.vnext.test_annual_continuity')
assert 'Ran 12 tests' in entry['stderr_tail'] and '\nOK\n' in entry['stderr_tail']
content=read(OUT/'independent-content-regression.json')
assert content['head']==code['exact_head'] and content['runtime_tree']==code['runtime_tree'] and content['test_tree']==code['test_tree']
assert content['status']=='PASS' and content['case_count']==26 and all(x['expected']==x['observed'] for x in content['cases'])
assert content['regression_id']==content_hash(value={k:v for k,v in content.items() if k!='regression_id'})
result={'code':code,'requirement':{k:_requirement()[k] for k in ('requirement_id','requirement_closure_hash')},
 'command_binding':proof(OUT/'offline-acceptance-04-command.json'),'full_suite_log':proof(OUT/'offline-acceptance-04-command.log'),
 'ci':{'metadata':proof(OUT/'ci-ab49924.json'),'raw_log':proof(OUT/'ci-ab49924.log'),'fast_record_matches_raw_log':True,'entries':len(fast['tests']),'annual_module_tests':12,'actual_merge_ref':'989dac9270d55befb5f64652a04fe08b1b4ba446','note':'CI raw checkout log names this synthetic merge of reviewed head into base48b233; that merge object was not fetched/reconstructed locally.'},
 'content_regression':proof(OUT/'independent-content-regression.json'),'packages':[],'candidate_terminals':[]}

# These checks do not invoke an exemption to native replay. They independently
# verify all files and resolve real selected records; the full test's native
# PublicationView/Run replay is retained as separately log-reviewed evidence.
previous=read(ROOT/'outputs/active_publication.json')['publication_id']
expected=[('s0','2023-12-31','23713000000','0.692','3e59d9a02dea905a6abcd375b111d2d3113c784561aefcec3a2d36bf16e1ae17'),
 ('s1','2024-12-31','25100000000','0.698','32a365d594e905c7b4fa8dac8efa501c9ca4ffeabe2579baf8e96bd52e08b131'),
 ('s2','2025-12-31','26186000000','0.693','c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547')]
for label,period,b01value,b10value,table_sha in expected:
 directory=run/'stage/publication/outputs/publications'/binding[label]
 m=validate_record(record=read(directory/'publication_manifest.json'));assert m['publication_id']==binding[label] and m['previous_publication_id']==previous
 expected_files={x['path'] for x in m['files']}|{'publication_manifest.json'}
 actual=set()
 for p in directory.rglob('*'):
  assert not p.is_symlink()
  if p.is_file():actual.add(p.relative_to(directory).as_posix())
 assert actual==expected_files
 for item in m['files']:
  p=directory/item['path'];assert p.stat().st_size==item['size'] and sha256_file(path=p)==item['sha256'],str(p)
 meta=read(directory/annual.META);assert meta['implementation_head']==code['exact_head']
 batch=read(directory/annual.BATCH);assert (len(batch['cumulative_result_bindings']),batch['selected_result_count'],batch['inherited_result_count'])==(240,2,238)
 with (directory/'metrics_matrix.csv').open() as f:assert len(list(csv.DictReader(f)))==327
 view=PublicationView(publication_id=m['publication_id'],bundle_dir=directory,manifest=m)
 selected={}
 for metric,want in [('B01',b01value),('B10',b10value)]:
  native=view.native_result(company_id='marriott_international',metric_id=metric);r=native['result']
  assert native['owner_publication_id']==m['publication_id'] and r['period_end']==period and str(r['value'])==want
  records=[strict_json_loads(text=l) for l in native['records_raw'].decode().splitlines()]
  source_details=[]
  for src in native['sources']:
   raw=next(x for x in records if x['record_type']=='RAW_BLOB' and x['raw_asset_id']==src['raw_asset_id'])
   path='internal/annual_snapshot/data/'+raw['storage_uri'];b=view.read_bytes(relative_path=path)
   assert len(b)==raw['byte_length'] and hashlib.sha256(b).hexdigest()==raw['raw_asset_id'][7:]
   assert raw['raw_asset_id'][7:]==('af2fea717f696acfa6f5f2436aa6e4175c3c56ab1628a2e3198964300f32422a' if metric=='B01' else table_sha)
   source_details.append({'source_reference':src,'original_raw_blob':raw,'bundle_path':path})
  selected[metric]={'result':r,'run_path':native['run_path'],'manifest_sha256':hashlib.sha256(native['manifest_raw']).hexdigest(),'records_sha256':hashlib.sha256(native['records_raw']).hexdigest(),'reviews_sha256':hashlib.sha256(native['reviews_raw']).hexdigest(),'sources':source_details}
 result['packages'].append({'label':label,'publication_id':m['publication_id'],'previous_publication_id':previous,'file_count':len(m['files']),'manifest':proof(directory/'publication_manifest.json'),'native_results':selected,'verification_scope':'ALL_FILE_BYTES_AND_NATIVE_RESULT_SOURCE_LINKS; full native semantic replay is separately supplied by completed integration log'})
 previous=m['publication_id'];print('package',label,'bytes and sources checked',flush=True)
for stage_root in (run/'stage',run/'failure-case/stage'):
 for candidate in sorted((stage_root/'candidates').iterdir()):
  if not candidate.is_dir():continue
  plan=read(candidate/'plan.json');records=[strict_json_loads(text=l) for l in (candidate/'b10/records.jsonl').read_text().splitlines()]
  attempt=next(x for x in records if x['record_type']=='AI_EXTRACTION_ATTEMPT')
  request=candidate/'b10'/attempt['request_body_path'];assert sha256_file(path=request)==plan['request']['provider_request_body_sha256']
  paths=list((candidate/'invocation_control/executions').glob('*.json'));assert len(paths)==1
  raw=read(paths[0]);terminal=controller._load_execution_receipt(root=candidate/'invocation_control',path=paths[0],execution_id=raw['execution_id'])
  assert terminal['counters']['real_model_provider_egress_count']==terminal['counters']['paid_model_provider_call_count']==1
  if stage_root==run/'stage':assert terminal['status']=='SUCCEEDED' and sha256_file(path=request) in binding['request_hashes']
  b01=[strict_json_loads(text=l) for l in (candidate/'b01/records.jsonl').read_text().splitlines()]
  b01res=[x for x in b01 if x['record_type']=='METRIC_RESULT' and x['metric_id']=='B01'];assert len(b01res)==1 and b01res[0]['reason_code']=='PASS'
  b10res=[x for x in records if x['record_type']=='METRIC_RESULT' and x['metric_id']=='B10']
  assert len(b10res)==(1 if terminal['status']=='SUCCEEDED' else 0)
  result['candidate_terminals'].append({'candidate':str(candidate),'plan_id':plan['plan_id'],'request_sha256':sha256_file(path=request),'execution_id':terminal['execution_id'],'status':terminal['status'],'counters':terminal['counters'],'scope':'NATIVE_TEST_CONTROLLER_OVER_INJECTED_HTTP_NOT_REAL_BUSINESS_CALLS','b01_pass':True,'b10_result_count':len(b10res)})
first,second,repeat1,repeat2=(read(run/n) for n in ('first.json','second.json','repeat-first.json','repeat-second.json'))
assert first['status']==second['status']=='COMPLETE_UPDATE_COMMITTED'
assert first['current_published']['provenance']['publication_id']==binding['s1'] and first['published_before']['provenance']['publication_id']==binding['s0']
assert second['current_published']['provenance']['publication_id']==binding['s2'] and second['published_before']['provenance']['publication_id']==binding['s1']
assert repeat1['status']==repeat2['status']=='NO_CHANGE' and repeat1['counts']['provider']==1 and repeat2['counts']['provider']==2
negative=read(run/'failure-case/negative-binding.json');recovery=read(run/'failure-case/recovery.json');failed=read(run/'failure-case/failure.json')
assert negative['code']==code and recovery['status']=='RECOVERED_PRIOR_TRANSACTION' and failed['status']=='CANDIDATE_UPDATE_FAILED'
assert read(run/'failure-case/stage/publication/outputs/active_publication.json')['publication_id']==negative['recovered_publication']==recovery['current_published']['provenance']['publication_id']
assert read(run/'failure-case/stage/successful-candidate.json')['plan_id'] not in negative['simulated_native_counts']['failed_plans']
assert failed['counts']['provider']==2 and len(failed['counts']['failed_plans'])==1 and not failed['counts']['uncertain_plans']
current=read(run/'current-start/result.json');assert current['status']=='NO_CHANGE' and current['counts']['provider']==current['counts']['sec_reserved']==0 and current['start_mode']=='CURRENT_ACTIVE'
assert not (run/'current-start/stage/seed-candidate').exists() and not (run/'current-start/stage/seed-publication-result.json').exists()
assert current['current_published']['provenance']['publication_id']==read(ROOT/'outputs/active_publication.json')['publication_id']
# Refresh protection after the completed integration instead of trusting its earlier snapshot.
base=read(OUT/'tracked-baseline.json');base_head=read(OUT/'baseline.json')['base_head']
changed=set(subprocess.check_output(['git','diff','--name-only',base_head,code['exact_head']],cwd=ROOT,text=True).splitlines())
count=0
for path,expected in base.items():
 if path in changed:continue
 p=ROOT/path;assert p.stat().st_size==expected['size'] and sha256_file(path=p)==expected['sha256'],path;count+=1
assert read(ROOT/'outputs/active_publication.json')==read(OUT/'baseline.json')['active']
assert code_identity()==code
result.update(status='PASS',refreshed_unchanged_tracked_file_count=count,actual_active=read(ROOT/'outputs/active_publication.json'),new_business_calls=[0,0,0],semantic_full_integration_independently_rerun=False)
(OUT/'final-review-material-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
print('PASS',count,'protected original files',flush=True)
