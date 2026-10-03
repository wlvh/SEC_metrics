import os,json,shutil,socket,sys,hashlib
from pathlib import Path
from unittest.mock import patch
from vnext.capacity_run import prepare_case
from vnext.canonical import content_hash,canonical_json_bytes
from vnext.continuous_request_context import FORMAT_VERSION
root=Path('/tmp/sec_metrics_issue28_continuous/format-registration-review-5207290213')
original=Path('/tmp/sec_metrics_issue28_continuous/d04-reference-5207290213/data')
clone=root/'data'
assert clone.is_dir()
export=clone/'config/ordinary_going_concern_assessment.json'
original_file=original/'config/ordinary_going_concern_assessment.json'
raw=export.read_bytes();original_hash=hashlib.sha256(raw).hexdigest();export.write_bytes(raw)
value=json.loads(raw); rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
 positive=prepare_case(data_root=clone,company_id='enphase_energy',metric_id='D04')
 assert positive['text_arguments']['source']['request_context_format']==FORMAT_VERSION
 assert positive['registered_input']==value
 rows.append({'case':'auto_restore_registered_supported_format','result':'PASS','source_id':positive['text_arguments']['source']['semantic_source_id']})
 print(rows[-1],flush=True)
 for case in ['remove_format','explicit_null','unsupported_format','forge_supported_format_input_identity','explicit_hint_conflict']:
  bad=json.loads(raw)
  if case=='remove_format':bad.pop('request_context_format')
  elif case=='explicit_null':bad['request_context_format']=None
  elif case=='unsupported_format':bad['request_context_format']='unapproved-format'
  elif case=='forge_supported_format_input_identity':bad['new_untrusted_metadata']='rewritten by caller'
  bad['input_record_id']=content_hash(value={k:v for k,v in bad.items() if k!='input_record_id'})
  export.write_bytes(canonical_json_bytes(value=bad))
  try:
   prepare_case(data_root=clone,company_id='enphase_energy',metric_id='D04',request_context_format='unapproved-format' if case=='explicit_hint_conflict' else None)
  except ValueError as e:
   rows.append({'case':case,'result':'REJECTED','reason':str(e)})
  else:raise AssertionError('accepted forged export '+case)
  print(rows[-1],flush=True)
  export.write_bytes(raw)
assert hashlib.sha256(original_file.read_bytes()).hexdigest()==original_hash
(root/'results.json').write_text(json.dumps({'scope':'root changes to capacity_run.py and capacity_assessment_input.py only','rows':rows,'original_material_unchanged':True,'new_provider_paid_sec_calls':[0,0,0]},indent=2)+'\n')
