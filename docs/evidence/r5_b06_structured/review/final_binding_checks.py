from pathlib import Path
import json,subprocess,hashlib,copy
from unittest.mock import patch
from vnext import r5_b06_structured as route,r5_b06_publication as pub
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');OUT=Path('/Users/lyuhongwang/Documents/Codex/2026-09-11/r5-b06-structured/independent-discovery');head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
paths=pub._verify_saved_input_origin(ROOT,head)
assert len(paths)>20
manifest=json.loads((OUT.parent/'trial-04/runs/ford_motor_company/manifest.json').read_text())
route.validate_input_binding(data_root=ROOT,manifest=manifest)
bad=copy.deepcopy(manifest);bad['source_references']=[s for s in bad['source_references'] if s['source_role']=='companyfacts']
try:route.validate_input_binding(data_root=ROOT,manifest=bad)
except ValueError as e:assert 'R5_REQUIRED_SOURCE_SET_CHANGED' in str(e);missing=str(e)
else:raise AssertionError('omitted scope accepted')
bad=copy.deepcopy(manifest);bad['target_period']['fiscal_year']-=1
try:route.validate_input_binding(data_root=ROOT,manifest=bad)
except ValueError as e:assert 'R5_DISCOVERED_PERIOD_CHANGED' in str(e);period=str(e)
else:raise AssertionError('wrong fiscal year accepted')
selected=route.discover(data_root=ROOT,company={'company_id':'enphase_energy','primary_cik':'1463101'});path=next(x['request_repo_relative_path'] for x in selected['sources'] if '/companyfacts/' in x['source_url']);original=subprocess.check_output
# Inject only external Git-object bytes; same real validator runs.
def changed(args,**kwargs):
 result=original(args,**kwargs)
 return result+b' ' if args[:2]==['git','show'] and args[2]==head+':'+path else result
with patch.object(pub.subprocess,'check_output',changed):
 try:pub._verify_saved_input_origin(ROOT,head)
 except ValueError as e:assert 'R5_SAVED_SOURCE_ORIGIN_CHANGED' in str(e);origin=str(e)
 else:raise AssertionError('source origin mismatch accepted')
print(json.dumps({'status':'PASS_INDEPENDENT_BINDING_CHECKS','head':head,'trusted_source_paths_verified':len(paths),'ford_exact_required_source_set':'PASS','omitted_scope_rejection':missing,'fiscal_label_rejection':period,'independent_origin_rejection':origin,'validator_mocked':False,'injection':'Git external byte I/O only','business_calls':[0,0,0]},indent=2))
