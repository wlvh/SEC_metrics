from pathlib import Path
import json,socket,time
from unittest.mock import patch
from vnext.continuous_semantic_calls import prepare_requests
from vnext.continuous_request_context import measure_request
rows=[];started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 for company in ['ford_motor_company','enphase_energy']:
  prepared=prepare_requests(company_id=company,metric_id='B13',reference_context=True,program_quantity_roles=True)
  measurements=[measure_request(p.provider_request_body_bytes,require_reference=True) for p in prepared]
  assert all(m['fits'] and m['request_bytes']<=8*1024*1024 for m in measurements)
  row={'company_id':company,'request_count':len(prepared),'max_input_tokens':max(m['input_tokens'] for m in measurements),
   'max_total_context':max(m['context_tokens'] for m in measurements),'output_reserve':4096,
   'all_units_preserved':len(json.loads(prepared[0].source_bytes)['units']),
   'measurements':measurements,'new_real_calls':[0,0,0]}
  rows.append(row);print({k:v for k,v in row.items() if k!='measurements'},flush=True)
Path(__file__).with_name('final-request-counts.json').write_text(json.dumps({'version':'B13_PROGRAM_QUANTITY_ROLES_V1',
 'companies':rows,'total_required_requests':sum(r['request_count'] for r in rows),'seconds':time.monotonic()-started,
 'additional_compression_optimization_performed':False,'new_real_calls':[0,0,0]},indent=2)+'\n')
