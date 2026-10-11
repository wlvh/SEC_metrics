"""Real read-only company CLI; only the program registry is an isolated input."""
import hashlib,io,json,socket,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import selected_source_requirements as selected,company_fiscal_range as ranges
ROOT=Path(__file__).resolve().parents[3]
SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
OUT=Path(__file__).parent
WATCH=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log.manifest.json']
def hashes():
 return {p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in WATCH if (SOURCE/p).is_file()}
def execute(args):
 capture=io.StringIO();start=time.perf_counter()
 with patch('sys.stdout',capture):code=main(args)
 return code,json.loads(capture.getvalue()),time.perf_counter()-start
before=hashes();rows=[]
with tempfile.TemporaryDirectory(prefix='source-registry-scope-') as d:
 program=Path(d);(program/'config').mkdir()
 registry=program/'config/company_registry.csv'
 original=(ROOT/'config/company_registry.csv').read_bytes()
 registry.write_bytes(original.replace(b'pfizer,Pfizer,',b'pfizer,Pfizer unrelated program display,'))
 policy='config/normal_period_selection_v1.json';(program/policy).write_bytes((ROOT/policy).read_bytes())
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No real network')),patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No metric calculation')):
  for scope in (['--report-end','2025-12-31'],['--fiscal-year-start','2025','--fiscal-year-end','2025']):
   args=['sources','--company','southwest_airlines','--source-root',str(SOURCE),'--metric','B01',*scope]
   code,baseline,elapsed=execute(args)
   with patch.object(selected,'ROOT',program),patch.object(ranges,'ROOT',program):
    altered_code,altered,altered_elapsed=execute(args)
   assert code==altered_code==0,(code,altered_code,altered)
   assert {k:v for k,v in baseline.items() if k!='elapsed_seconds'}=={k:v for k,v in altered.items() if k!='elapsed_seconds'},'Source/period plan changed'
   rows.append({'args':args,'baseline_seconds':elapsed,'unrelated_program_row_seconds':altered_elapsed,'exit_code':code,'result':altered})
assert before==hashes(),'Source proofs or registry changed'
summary={'code_root':str(ROOT),'source_root':str(SOURCE),'code_identity':'working tree, exact commit/tree recorded separately','runs':rows,'before':before,'after':hashes(),'sec':0,'provider':0,'paid':0,'metric_executed':False,'business_acceptance':False}
(OUT/'saved-source-cli.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'runs':[{'args':r['args'],'baseline_seconds':r['baseline_seconds'],'unrelated_program_row_seconds':r['unrelated_program_row_seconds'],'status':r['result']['status'],'exit_code':r['exit_code']} for r in rows],'source_bytes_unchanged':True,'calls':{'sec':0,'provider':0,'paid':0}},indent=2))
