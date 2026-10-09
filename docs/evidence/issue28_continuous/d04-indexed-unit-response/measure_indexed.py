"""Measure exact indexed successors without regrouping or provider execution."""
from pathlib import Path
import json,sys
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.normal_annual_input import _registry_rows
from vnext.canonical import strict_json_loads,canonical_json_bytes
from vnext.continuous_semantic_calls import prepare_requests,request_body
from vnext.continuous_request_context import measure_request
from vnext.native_unit_index import upgrade_request,restore_base_request
rows=[]
for company in _registry_rows(repo_root=ROOT):
 for metric in ('D04','B13'):
  if metric=='B13' and company['company_id'] not in {'ford_motor_company','enphase_energy'}:continue
  prepared=prepare_requests(company_id=company['company_id'],metric_id=metric,native=metric=='D04',reference_context=True,complete_response_contract=metric=='D04')
  requests=[]
  for p in prepared:
   base=strict_json_loads(text=p.request_bytes.decode());new=upgrade_request(base)
   assert restore_base_request(new)==base
   result=measure_request(request_body(new,SimpleNamespace(model='deepseek-flash')),require_reference=True)
   requests.append({**result,'base_request_id':base['request_id'],'request_id':new['request_id'],'units':len(new['units']),'candidates':len(new['required_candidate_assessments'])})
  row={'company_id':company['company_id'],'metric_id':metric,'requests':requests,'original_groups_unchanged':True}
  rows.append(row);print(row['company_id'],metric,len(requests),flush=True)
  Path(sys.argv[1]).write_bytes(canonical_json_bytes(value={'rows':rows,'new_calls':[0,0,0],'business_acceptance':False,'successful_original_retention_separately_checked':True}))
