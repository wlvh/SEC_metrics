"""Actual user entry with old real inputs, no network or new paid execution."""
import json,os,sys,time,socket,tempfile,hashlib,io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tools'),str(ROOT)]
from vnext_company import main
from vnext import current_d04_result
LEDGER=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
HERE=Path(__file__).resolve().parent
BASE=Path(tempfile.mkdtemp(prefix='issue28-d04-company-model-',dir='/private/tmp'))
(HERE/'runtime-path.json').write_text(json.dumps({'state_root':str(BASE/'state'),'output_root':str(BASE/'output'),'source_root':str(LEDGER/'source-inputs')})+'\n')
protected=[LEDGER/'claims.jsonl',LEDGER/'binding.json']
for ordinal in range(173,179):protected.extend(p for p in (LEDGER/'calls'/f'{ordinal:04d}').rglob('*') if p.is_file())
def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=hashes();args=['run','--company','enphase_energy','--source-root',str(LEDGER/'source-inputs'),'--work-dir',str(BASE/'state'),'--output-dir',str(BASE/'output'),'--metric','D04']
operations=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')):
 for name,forbid in [('first',False),('repeat-forbid-processing',True)]:
  stream=io.StringIO();start=time.perf_counter()
  if forbid:
   with patch.object(current_d04_result,'prepare_current_d04_case',side_effect=AssertionError('unchanged company must not process again')),redirect_stdout(stream):rc=main(args)
  else:
   with redirect_stdout(stream):rc=main(args)
  text=stream.getvalue();(HERE/(name+'.json')).write_text(text)
  report=json.loads(text);operations.append({'name':name,'seconds':time.perf_counter()-start,'return_code':rc,'report':report})
  print(name,rc,operations[-1]['seconds'],flush=True)
  if rc not in (0,2) or report['metrics'][0].get('result_reason_code') != 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE':break
summary={'operations':operations,'state_root':str(BASE/'state'),'output_root':str(BASE/'output'),'source_root':str(LEDGER/'source-inputs'),'protected_files':len(before),'protected_unchanged':before==hashes(),'new_calls':[0,0,0]}
(HERE/'company-cli-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
assert all(r['return_code'] in (0,2) and r['report']['metrics'][0].get('result_reason_code')=='D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE' for r in operations) and len(operations)==2
assert summary['protected_unchanged']
