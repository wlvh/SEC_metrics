"""Actual new company revenue and zero-recalculation under unrelated debt edits."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update
ROOT=Path.cwd();SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');E=Path(__file__).parent;STATE=Path(tempfile.mkdtemp(prefix='issue28-debt-scope-'))
args=['run','--company','marriott_international','--source-root',str(SOURCE),'--metric','B01','--work-dir',str(STATE/'state'),'--output-dir',str(STATE/'output')]
def snap(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def run(forbid=False):
 output=io.StringIO();start=time.perf_counter()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',output):
  if forbid:
   original=update.sha256_file
   def debt_edit(*,path):return 'TEST_ONLY_NEW_DEBT_NOTE_VERSION' if path==ROOT/'scripts/vnext/b06_note_carrying.py' else original(path=path)
   with patch.object(update,'sha256_file',side_effect=debt_edit),patch.object(update,'create_saved_result',side_effect=AssertionError('No revenue recalculation for debt-only edit')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No new revenue write')):code=main(args)
  else:code=main(args)
 return code,json.loads(output.getvalue()),time.perf_counter()-start
before_source={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')}
first_code,first,first_seconds=run();assert first_code==0,first
row=list(csv.DictReader((Path(first['output_root'])/'metrics_matrix.csv').open()))[0];assert row['value']=='26186000000' and row['unit']=='USD' and row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
result_root=Path(first['metrics'][0]['result_root']);before_result=snap(result_root);repeat_code,repeat,repeat_seconds=run(True);assert repeat_code==0 and repeat['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE',repeat;assert repeat['metrics'][0]['result_id']==first['metrics'][0]['result_id'];assert before_result==snap(result_root)
before=snap(STATE/'state');start=time.perf_counter();command='import runpy,socket,sys; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network"));sys.argv='+repr(['tools/vnext_company.py','results','--company','marriott_international','--state-root',str(STATE/'state'),'--output-root',str(STATE/'read')])+';runpy.run_path("tools/vnext_company.py",run_name="__main__")';r=subprocess.run([sys.executable,'-c',command],cwd=ROOT,capture_output=True,text=True);read_seconds=time.perf_counter()-start;assert r.returncode==0,r.stderr;assert before==snap(STATE/'state');assert before_source=={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in before_source}
report={'code_root':str(ROOT),'source_root':str(SOURCE),'test_state':str(STATE),'args':args,'first':first,'repeat':repeat,'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,'csv':row,'source_registry_log_manifest_unchanged':True,'result_unchanged_under_debt_note_edit':True,'independent_read_state_unchanged':True,'new_calls':[0,0,0],'scope':'Synthetic hash change at only the unrelated b06_note_carrying file; actual revenue factory/Calculator/save/CLI/read untouched; no financial answer supplied'};(E/'actual-company.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,'value':row['value'],'unit':row['unit'],'result_id':row['result_id'],'repeat':repeat['metrics'][0]['status'],'new_calls':[0,0,0]}))
