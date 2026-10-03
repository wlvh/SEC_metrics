import sys,pathlib,json,hashlib
sys.path[:0]=['/Users/lyuhongwang/Developer/SEC_metrics','/Users/lyuhongwang/Developer/SEC_metrics/scripts']
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import content_hash
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics');base=pathlib.Path('/tmp/sec_metrics_issue28_continuous')
p=base/'zero-ai-amendment-route-candidate.py';ns={'__package__':'vnext','__file__':str(p),'__name__':'vnext._isolated_amendment_probe'}
exec(compile(p.read_text(),str(p),'exec'),ns)
out=base/'amendment-route-candidate-test';out.mkdir(exist_ok=False);index=[]
for metric in ['B01','B03','E03']:
 with original_sources_only():d=ns['resolve_ordinary_zero_ai_metric'](repo_root=root,company_id='southwest_airlines',metric_id=metric)
 assert d['result']['publication']=='PUBLISHED', d['selection']
 packet=d['input_binding']['amendment_input'];assert packet['decision']=='INPUT_PROPERTY_PROVEN'
 amendment=packet['scopes'][0]['amendment']['source_reference'];assert amendment in d['source_references']
 assert len(d['observations'])>0
 (out/(metric+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2))
 row={'metric_id':metric,'result':d['result'],'source_reference_count':len(d['source_references']),
      'scope_id':packet['scopes'][0]['scope_id'],'observation_count':len(d['observations']),
      'dependency_metric_ids':sorted(d['dependency_specs']),'repository_route_changed':False,'native_run_created':False,
      'scratch_route_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'calls':{'provider':0,'paid':0,'sec':0}}
 index.append(row);print(json.dumps(row),flush=True)
(out/'index.json').write_text(json.dumps(index,indent=2))
