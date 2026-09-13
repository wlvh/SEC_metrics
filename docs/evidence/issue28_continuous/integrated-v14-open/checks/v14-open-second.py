import json,sys,time,traceback
from pathlib import Path
root=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(root),str(root/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import normal_run_v3 as module
from vnext.normal_run_v3 import install_normal_inputs,create_normal_run
original_prepare = module.prepare_case
def guarded_prepare(**kwargs):
 with original_sources_only():return original_prepare(**kwargs)
module.prepare_case = guarded_prepare
def no_network(event,args):
 if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo'):raise RuntimeError('OFFLINE_MATERIAL_NO_NETWORK')
sys.addaudithook(no_network)
out=Path('/tmp/sec_metrics_issue28_continuous/v14-open-961d-second');out.mkdir(exist_ok=False)
rows=[]
if True:
 for company,metric in [('marriott_international','B03'),('salesforce','B12'),('jpmorgan_chase','A03'),('marriott_international','D01'),('salesforce','C03')]:
  case=out/(company+'-'+metric);case.mkdir();start=time.monotonic();row={'company_id':company,'metric_id':metric}
  try:
   install_normal_inputs(data_root=case/'data',company_id=company,metric_id=metric)
   value=create_normal_run(data_root=case/'data',run_dir=case/'run',company_id=company,metric_id=metric,freeze=False)
   (case/'outcome.json').write_text(json.dumps(value,ensure_ascii=False,indent=2))
   row.update(status=value['manifest']['status'],value=value['result']['value'],target=value['manifest']['target_period'])
  except Exception as e:
   row.update(status='FAILED',error=repr(e));(case/'first-failure.log').write_text(traceback.format_exc())
  row['seconds']=round(time.monotonic()-start,3);rows.append(row);(out/'index.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
