import sys,pathlib,json,hashlib
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(root),str(root/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
base=pathlib.Path('/tmp/sec_metrics_issue28_continuous');p=base/'companyfacts-amendment-route-candidate.py'
ns={'__package__':'vnext','__file__':str(p),'__name__':'vnext._isolated_companyfacts_amendment_probe'}
exec(compile(p.read_text(),str(p),'exec'),ns)
out=base/'companyfacts-amendment-candidate-test';out.mkdir(exist_ok=False)
with original_sources_only():d=ns['resolve_ordinary_companyfacts_metrics'](repo_root=root,company_id='southwest_airlines')
(out/'result.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
rows=[]
for metric,item in d['metrics'].items():
 row={'metric_id':metric,'result':item['result'],'selection':item['selection'],'projection_claim_count':len(item['projection_claims'])}
 rows.append(row);print(json.dumps(row),flush=True)
index={'results':rows,'prior_error':d['prior_error'],'amendment_input_decision':d['amendment_input']['decision'],
       'amendment_scope_ids':[s['scope_id'] for s in d['amendment_input']['scopes']],
       'repository_route_changed':False,'native_run_created':False,'scratch_route_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
       'calls':{'provider':0,'paid':0,'sec':0}}
(out/'index.json').write_text(json.dumps(index,indent=2))
assert d['amendment_input']['decision']=='INPUT_PROPERTY_PROVEN'
assert all(item['result']['publication']=='PUBLISHED' for item in d['metrics'].values()), 'Source route still has unresolved results; inspect exact records'
