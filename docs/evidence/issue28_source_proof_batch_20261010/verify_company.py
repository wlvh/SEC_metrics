from pathlib import Path
import json,shutil,tempfile,time,io,contextlib,subprocess,sys,socket
from unittest.mock import patch
from tools.vnext_company import main
from vnext.canonical import sha256_file
old=json.load(open('docs/evidence/issue28_source_proof_batch_20261010/actual-update.json'));base=Path(tempfile.mkdtemp(prefix='issue28-proof-batch-company-'));state=base/'state';state.mkdir()
shutil.copytree(Path(old['isolated_state_root']),state/'updates/B01')
# An independent current task pins the same read-only source. No peer task is
# modified, and no runtime/source tree is copied into this ordinary state.
(state/'company-task.json').write_text(json.dumps({'record_type':'ORDINARY_COMPANY_TASK_V1','company_id':'jpmorgan_chase','source_root':old['source_root']}))
args=['run','--company','jpmorgan_chase','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021','--metric','B01','--source-root',old['source_root'],'--work-dir',str(state),'--output-dir',str(base/'output')]
initial={str(p.relative_to(state)):sha256_file(path=p) for p in (state/'updates').rglob('*') if p.is_file() and '/results/' in str(p)}
s=io.StringIO()
with patch('vnext.historical_statement_cases.resolve_period_selection',side_effect=AssertionError('No preparation')),patch('vnext.ordinary_current_update.save_calculated_case',side_effect=AssertionError('No calculation')),patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 start=time.perf_counter()
 with contextlib.redirect_stdout(s):rc=main(args)
 elapsed=time.perf_counter()-start
assert rc==0,s.getvalue();after={str(p.relative_to(state)):sha256_file(path=p) for p in (state/'updates').rglob('*') if p.is_file() and '/results/' in str(p)};assert after==initial
start=time.perf_counter();r=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(base/'reader')],capture_output=True,text=True);read=time.perf_counter()-start;assert r.returncode==0,r.stderr
result={'base_main':'f6ef7886d6630f7675c25cd42e306c373ab05769','program_root':str(Path.cwd()),'product_changes_uncommitted':True,'source_root':old['source_root'],'state_root':str(state),'argv':args,'cli_seconds':elapsed,'cli_exit':rc,'independent_read_seconds':read,'reader_exit':r.returncode,'result_files_unchanged':initial,'cli_output':s.getvalue(),'reader_output':r.stdout,'new_calls':[0,0,0]}
Path('docs/evidence/issue28_source_proof_batch_20261010/actual-company.json').write_text(json.dumps(result,indent=2)+'\n');print('company',elapsed,rc,'reader',read,r.returncode,'unchanged_result_files',len(initial))
