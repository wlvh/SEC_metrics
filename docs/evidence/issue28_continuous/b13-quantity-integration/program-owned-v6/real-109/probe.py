from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import json,hashlib
from vnext.capacity_semantic_review import _restore_units,validate_response
from vnext.r6_semantic_review import _source_items
from vnext.capacity_native_assessment import build_acceptance
from vnext.canonical import canonical_json_bytes
slot=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0109')
request=json.loads((slot/'semantic-request.json').read_bytes());source=json.loads((slot/'source.json').read_bytes());response=json.loads((slot/'wire/assistant-output.bin').read_bytes())
plan=json.loads(next((slot/'invocation_control/plans').glob('*.json')).read_bytes())
prepared=SimpleNamespace(source_bytes=(slot/'source.json').read_bytes(),request_bytes=(slot/'semantic-request.json').read_bytes())
units=_restore_units(request['units'],request['shared_source_dictionaries']);inventory=[];owners={}
for number,unit in enumerate(units):
 kind,items=_source_items(unit);indices=sorted(items)
 inventory.append({'unit_number_zero_based':number,'unit_id':unit['unit_id'],'kind':kind,'source_index_min':min(indices),'source_index_max':max(indices),'supplied_count':len(indices),'all_source_indices':indices})
 for index,item in items.items():owners.setdefault((kind,index),[]).append((unit['unit_id'],item))
findings=[]
for output in response['units']:
 for finding in output['findings']:
  for ref in finding['evidence']:
   supplied=owners.get((ref['kind'],ref['source_index']),[])
   findings.append({'response_unit_id':output['unit_id'],'reference':ref,'supplied_owner_unit_ids':[u for u,_ in supplied],
    'same_unit':any(u==output['unit_id'] for u,_ in supplied),'supplied_text':[item.get('text') for _,item in supplied]})
def check(value):
 try:
  checked=validate_response(request=request,raw_response=canonical_json_bytes(value=value),source=source)
  accepted=build_acceptance(prepared=prepared,plan=plan,response_body=canonical_json_bytes(value=value))
  return {'status':'ACCEPTED','unresolved':checked['unresolved'],'accepted_finding_count':len(checked['findings']),'native_evidence':accepted['evidence_status']}
 except Exception as error:return {'status':'REJECTED','error_type':type(error).__name__,'reason':str(error)}
original=check(response);synthetic=deepcopy(response)
wrong=[f for f in findings if not f['same_unit']];assert len(wrong)==1 and wrong[0]['reference']['source_index']==834 and len(wrong[0]['supplied_owner_unit_ids'])==1
bad=wrong[0];origin=next(u for u in synthetic['units'] if u['unit_id']==bad['response_unit_id']);target=next(u for u in synthetic['units'] if u['unit_id']==bad['supplied_owner_unit_ids'][0])
moved=next(f for f in origin['findings'] if any(e['source_index']==834 for e in f['evidence']));origin['findings'].remove(moved);target['findings'].append(moved)
result={'ordinal':109,'evidence_kind':'REAL_SAVED_RESPONSE_READ_ONLY_REPLAY_AND_EXPLICIT_SYNTHETIC_VARIANT','original':original,'inventory':inventory,'finding_references':findings,
 'synthetic_only_move_834_to_unique_supplied_owner':check(synthetic),'original_state_preserved':True,'new_calls':[0,0,0],
 'no_real_coordinate_credit':True,'native_run_executed':False,'original_files':{str(p.relative_to(slot)):hashlib.sha256(p.read_bytes()).hexdigest() for p in slot.rglob('*') if p.is_file()}}
base=Path('/tmp/sec_metrics_issue28_continuous/b13-v6-109');(base/'probe.json').write_text(json.dumps(result,indent=2)+'\n');(base/'synthetic-relocated-834.json').write_bytes(canonical_json_bytes(value=synthetic))
print(json.dumps({k:v for k,v in result.items() if k in {'original','synthetic_only_move_834_to_unique_supplied_owner','new_calls'}},indent=2))
