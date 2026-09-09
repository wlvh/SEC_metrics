"""Offline diagnosis of the original failed response; never create a Run or call a provider."""
from pathlib import Path
import json,sys,hashlib,socket,copy
from unittest.mock import patch
root=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(root/'scripts'))
from vnext.reader import validate_reader_output
from vnext.evidence import check_evidence
from vnext.canonical import sha256_file,content_hash
base=Path('/Users/lyuhongwang/Documents/Codex/2026-09-08/marriott-annual-runtime')
report=json.loads((base/'live-run.json').read_text());run=Path(report['new_candidate']['run_directory'])
records=[json.loads(l) for l in (run/'records.jsonl').read_text().splitlines()]
attempt=next(r for r in records if r['record_type']=='AI_EXTRACTION_ATTEMPT')
grid=next(r for r in records if r['record_type']=='DERIVED_ASSET')
manifest=next(r for r in records if r['record_type']=='READER_INPUT_MANIFEST')
sources=[r for r in records if r['record_type']=='SOURCE_REFERENCE']
payload=json.loads((run/attempt['reader_payload_path']).read_text());task=payload['task_contract']
response_path=run/attempt['assistant_output_path'];response=response_path.read_bytes()
assert sha256_file(path=response_path)==attempt['assistant_output_sha256']
raw_path=run/attempt['raw_response_path'];raw=json.loads(raw_path.read_text())
assert sha256_file(path=raw_path)==attempt['raw_response_sha256']
checks=[]
def check(body):
 candidate=validate_reader_output(response_text=body,attempt_id=attempt['attempt_id'],
  required_roles=task['required_roles'],scope_contract=task['scope_contract'],
  source_reference_ids=manifest['source_reference_ids'],derived_asset_ids=[grid['derived_asset_id']])
 return check_evidence(candidate=candidate,derived_asset=grid,reader_manifest=manifest,
  reader_payload_body=payload,source_references=sources,
  identity_constraints=task['identity_constraints'],scope_contract=task['scope_contract'])
with patch.object(socket.socket,'connect',side_effect=AssertionError('DIAGNOSTIC_NETWORK_FORBIDDEN')):
 evidence=check(response.decode())
 body=json.loads(response);variant=copy.deepcopy(body)
 for ci,claim in enumerate(body['candidates']):
  for li,label in enumerate(claim['scope_evidence_locators']):
   loc=label['locator'];t=next(t for t in grid['tables'] if t['table_id']==loc['table_id'])
   cell=next(c for c in t['rows'][loc['row_index']]['cells'] if c['column_index']==loc['column_index'])
   checks.append({'id':label['id'],'locator':loc,'response_raw_text':label['raw_text'],
       'source_raw_text':cell['raw_text'],'source_normalized_text':cell['text'],
       'exact_match':label['raw_text']==cell['raw_text']})
   if label['raw_text']!=cell['raw_text']:
    variant['candidates'][ci]['scope_evidence_locators'][li]['raw_text']=cell['raw_text']
 diagnostic_only=check(json.dumps(variant,ensure_ascii=False))
 print('ORIGINAL', json.dumps(evidence,ensure_ascii=False)); print('DIAGNOSTIC_VARIANT',json.dumps(diagnostic_only,ensure_ascii=False))
 assert evidence['status']=='REJECTED' and evidence['reason_codes']==['SCOPE_LABEL_TEXT_MISMATCH']
 assert diagnostic_only['status']=='PASS'
 original_records=hashlib.sha256((run/'records.jsonl').read_bytes()).hexdigest()
 assert not list(r for r in records if r['record_type']=='METRIC_RESULT')
 assert not (base/'stage/successful-candidate.json').exists()
 result={'status':'LIVE_FAILED_OFFLINE_DIAGNOSIS_COMPLETE','original_evidence':evidence,
  'scope_text_comparison':checks,'counterfactual':{'scope':'DIAGNOSTIC_ONLY_NOT_A_PROVIDER_RESPONSE_OR_CANDIDATE',
      'change':'Replace only mismatching scope raw_text with exact same-cell source raw_text',
      'evidence_status':diagnostic_only['status'],'qualification_credit':'NONE','publication_credit':'NONE',
      'native_run_created':False,'original_response_or_records_modified':False},
  'provider_request_id':attempt['provider_request_id'],'raw_response_sha256':attempt['raw_response_sha256'],
  'assistant_output_sha256':attempt['assistant_output_sha256'],'usage':raw['usage'],
  'new_b10_result_count':0,'new_success_reference_exists':False,'b01':report['structured_candidate']['B01'],
  'real_provider_paid_sec_calls':[1,1,0],'additional_diagnostic_calls':[0,0,0],
  'run_records_sha256':original_records,'execution_code':report['execution_code']}
 (base/'native-evidence-failure.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
 (base/'failure-diagnosis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'native_evidence':evidence,'scope_comparison':checks,'diagnostic_only_variant':diagnostic_only['status']},ensure_ascii=False))
