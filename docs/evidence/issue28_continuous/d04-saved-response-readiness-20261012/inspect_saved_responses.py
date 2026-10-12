"""Read-only D04 material checks; never register, replay, or execute a call."""
import argparse, hashlib, json, socket, time
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch
from vnext.d04_native_assessment import validate_response

p=argparse.ArgumentParser()
p.add_argument('--ledger-root',type=Path,required=True)
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
hashes={}
def digest(path):
 stat=path.stat();key=(str(path),stat.st_size,stat.st_mtime_ns)
 if key not in hashes:hashes[key]=hashlib.sha256(path.read_bytes()).hexdigest()
 after=path.stat()
 assert (stat.st_size,stat.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'File changed during audit'
 return hashes[key]
claims=a.ledger_root/'claims.jsonl';before=digest(claims)
intents=[json.loads(line) for line in claims.read_text().splitlines()]
rows=[];started=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 for intent in intents:
  if intent['channel']!='PROVIDER':continue
  directory=a.ledger_root/'calls'/f"{intent['ordinal']:04d}"
  request_path=directory/'semantic-request.json'
  if not request_path.is_file():continue
  request=json.loads(request_path.read_text())
  if request.get('metric_id')!='D04':continue
  terminal=json.loads((directory/'terminal.json').read_text())
  source=json.loads((directory/'source.json').read_text())
  row={'ordinal':intent['ordinal'],'company':request['company_id'],
       'original_status':terminal['status'],'request_id':request['request_id'],
       'response_contract':request.get('response_contract_version'),
       'request_context_format':request.get('request_context_format'),
       'call_directory':str(directory),'material_problems':[]}
  for relative,expected in terminal.get('evidence',{}).items():
   path=directory/relative
   if not path.is_file():row['material_problems'].append('missing:'+relative)
   elif digest(path)!=expected:row['material_problems'].append('changed:'+relative)
  original=source['prepared_annual_input']
  for proof in original['source_proofs']:
   for relative_key,hash_key in [('request_repo_relative_path','content_sha256'),
                                 ('request_headers_repo_relative_path','request_headers_sha256')]:
    relative=proof.get(relative_key)
    if not relative:continue
    path=a.source_root/relative
    if not path.is_file():row['material_problems'].append('source_missing:'+relative)
    elif digest(path)!=proof[hash_key]:row['material_problems'].append('source_changed:'+relative)
  row['fiscal_year']=request.get('fiscal_label_context',{}).get('issuer_fiscal_year')
  row['original_period']=request.get('target_period')
  output=directory/'wire/assistant-output.bin'
  if row['material_problems']:
   row['classification']='MATERIAL_INTEGRITY_CHECK_FAILED'
  elif terminal['status']!='SUCCEEDED':
   row['classification']='HISTORICAL_FAILURE_ONLY'
  elif not output.is_file():
   row['classification']='ORIGINAL_ASSISTANT_OUTPUT_MISSING'
  else:
   try:
    checked=validate_response(request=request,raw_response=output.read_bytes())
    row['classification']='CURRENT_RESPONSE_CHECK_PASSED_REQUIRES_SELECTED_INPUT_MATCH'
    row['response_check_keys']=list(checked)
    row['unresolved_count']=len(checked.get('unresolved',[]))
    if row['unresolved_count']:row['classification']='CURRENT_RESPONSE_UNRESOLVED'
   except Exception as error:
    row['classification']='CURRENT_RESPONSE_CHECK_REJECTED'
    row['current_rejection']={'type':type(error).__name__,'reason':str(error)}
  rows.append(row)
assert digest(claims)==before,'Ledger claims changed during audit'
by_company=defaultdict(Counter)
for row in rows:by_company[row['company']][row['classification']]+=1
body={'scope':'Original D04 artifacts, source-proof file hashes and current response checker only; no current request construction, complete-company acceptance, media completion, backup restore, or new business credit',
      'ledger_root':str(a.ledger_root),'source_root':str(a.source_root),
      'code_root':str(Path(__import__('vnext.d04_native_assessment',fromlist=['x']).__file__).resolve().parents[2]),
      'claims_sha256':before,'claims_count':len(intents),
      'counts':dict(Counter(r['classification'] for r in rows)),
      'by_company':{c:dict(count) for c,count in sorted(by_company.items())},
      'rows':rows,'seconds':str(time.perf_counter()-started),'new_calls':[0,0,0]}
a.output.write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:body[k] for k in ['counts','by_company','claims_count','seconds','new_calls']},ensure_ascii=False))
