import json,time,hashlib,socket,gzip
from pathlib import Path
from unittest.mock import patch
from vnext.historical_saved_case import case_from_historical_component
from vnext.ordinary_saved_result import save_calculated_case,read_saved_result
root=Path.cwd();base=root/'docs/evidence/issue47_history/historical-income-receiving-2026-10-08';parent=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence')
out=parent/'historical-income-conflict-cases-20261008'
for n in range(100):
 p=out if n==0 else out.with_name(out.name+'-'+str(n))
 if not p.exists():out=p;out.mkdir();break
start=time.monotonic();summary={}
with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')),patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',side_effect=AssertionError('Already selected input must not be replaced by latest')):
 for m in ['B01','B03']:
  c=json.loads(gzip.decompress((base/(m+'-component.json.gz')).read_bytes()));case=case_from_historical_component(component=c,rules_root=root)
  r=save_calculated_case(source_root=root,output_root=out/m,company_id=c['company_id'],metric_id=m,case=case)
  held=read_saved_result(output_root=out/m)
  assert held['result']['result_id']==c['result']['result_id'] and held['result']['value'] is None
  assert held['input_assessments']['income_period']['evidence']['native_period'][0]=='2025-08-08'
  assert held['input_assessments']['income_period']['evidence']['visible_periods'][0][0]=='2025-08-07'
  summary[m]={'result_id':held['result']['result_id'],'record_root':str(out/m),'publication':held['result']['publication'],'reason':held['result']['reason_code'],'record_bytes':sum(p.stat().st_size for p in (out/m).iterdir() if p.is_file())}
record={'output_root':str(out),'metrics':summary,'seconds':time.monotonic()-start,'case_writer_not_selecting_or_calculating':True,'new_calls':{'sec':0,'provider':0,'paid':0},'new_native_run':False,'old_runs_modified':False}
(base/'saved-case-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
