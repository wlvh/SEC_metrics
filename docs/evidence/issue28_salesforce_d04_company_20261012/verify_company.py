"""One new ordinary company task from existing real D04 answers; no sockets."""
import argparse, hashlib, io, json, socket, sys, time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

p=argparse.ArgumentParser()
p.add_argument('--program-root',type=Path,required=True)
p.add_argument('--ledger-root',type=Path,required=True)
p.add_argument('--work-root',type=Path,required=True)
p.add_argument('--evidence-root',type=Path,required=True)
p.add_argument('--resume-existing-failed-task',action='store_true')
a=p.parse_args()
if a.work_root.exists():
 assert a.resume_existing_failed_task,'Use a new task or explicitly resume the preserved failure'
 old=json.loads((a.evidence_root/'first-environment-missing.json').read_text())
 assert len(old['metrics'])==1 and old['metrics'][0]['reason']=='CONTINUOUS_CONTEXT_REFERENCE_REQUIRED:TOKENIZER_DEPENDENCY_UNAVAILABLE'
 assert not old['metrics'][0].get('result_id'),'Do not replace a previous result'
else:
 assert not a.resume_existing_failed_task
 a.work_root.mkdir(parents=True)
a.evidence_root.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(a.program_root/'scripts'),str(a.program_root/'tools'),str(a.program_root)]
from vnext_company import main
from vnext.continuous_call_ledger import CallLedger
from vnext import current_d04_result

protected=[a.ledger_root/'claims.jsonl',a.ledger_root/'binding.json']
for ordinal in range(152,157):
 protected.extend(x for x in (a.ledger_root/'calls'/f'{ordinal:04d}').rglob('*') if x.is_file())
def hashes():return {str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
before=hashes()
arguments=['run','--company','salesforce','--source-root',str(a.ledger_root/'source-inputs'),
           '--metric','D04','--work-dir',str(a.work_root/'state'),'--output-dir',str(a.work_root/'output')]
rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch.object(CallLedger,'claim',side_effect=AssertionError('NEW_CLAIM_FORBIDDEN')):
 for name,repeated in [('first',False),('repeat_forbidden_processing',True)]:
  text=io.StringIO();started=time.perf_counter()
  if repeated:
   with patch.object(current_d04_result,'prepare_current_d04_case',side_effect=AssertionError('NO_REPEAT_PROCESSING')),redirect_stdout(text):
    rc=main(arguments)
  else:
   with redirect_stdout(text):rc=main(arguments)
  raw=text.getvalue();(a.evidence_root/(name+'.json')).write_text(raw)
  report=json.loads(raw)
  row={'name':name,'seconds':str(time.perf_counter()-started),'return_code':rc,
       'report':report}
  rows.append(row)
  summary={'program_root':str(a.program_root),'ledger_root':str(a.ledger_root),
           'state_root':str(a.work_root/'state'),'output_root':str(a.work_root/'output'),
           'protected_files':len(before),'protected_unchanged':before==hashes(),
           'operations':rows,'new_calls':[0,0,0],
           'scope':'Actual company run and saved answer processing, no new model execution or formal adoption'}
  (a.evidence_root/'company-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'name':name,'seconds':row['seconds'],'return_code':rc,
       'metrics':report.get('metrics'),'failure':report.get('failure')},ensure_ascii=False),flush=True)
  metric=report.get('metrics',[{}])[0]
  if not metric.get('result_id'):break
assert before==hashes(),'Original claims or saved call bytes changed'
assert len(rows)==2 and all(x['report']['metrics'][0].get('result_id') for x in rows), 'Company task did not complete'
assert rows[0]['report']['metrics'][0]['result_id']==rows[1]['report']['metrics'][0]['result_id']
