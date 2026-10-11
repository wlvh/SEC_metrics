"""Actual current C04 through formal CLI, repeats and independent reading."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update
ROOT=Path.cwd();SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');E=Path(__file__).parent;BASE=Path(tempfile.mkdtemp(prefix='issue28-current-c04-'));results=[]
def snap(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
before_source={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')}
if '--paramount-only' in sys.argv:
    results=json.loads((E/'actual-company.json').read_text())['results']
    companies=('paramount_skydance_paramount_global',)
    SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
    before_source={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in before_source}
else:
    companies=('marriott_international','salesforce','paramount_skydance_paramount_global')
for company in companies:
 state=BASE/company;args=['run','--company',company,'--source-root',str(SOURCE),'--metric','C04','--work-dir',str(state/'state'),'--output-dir',str(state/'out')]
 def run(forbid=False):
  out=io.StringIO();start=time.perf_counter()
  with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):
   if forbid:
    with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated C04 sources/calc')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No new C04 write')):code=main(args)
   else:code=main(args)
  return code,json.loads(out.getvalue()),time.perf_counter()-start
 code,first,seconds=run();metric=first['metrics'][0];assert metric['status'] in {'CANDIDATE_READY','CANDIDATE_WITHHELD'},(company,first);root=Path(metric['result_root']);old=snap(root);repeat_code,repeat,repeat_seconds=run(True);assert repeat['metrics'][0]['status'] in {'NO_SOURCE_CONTENT_CHANGE','PREVIOUS_INPUT_WITHHELD'};assert repeat['metrics'][0]['result_id']==metric['result_id'];assert old==snap(root)
 before=snap(state/'state');start=time.perf_counter();command='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network"));sys.argv='+repr(['tools/vnext_company.py','results','--company',company,'--state-root',str(state/'state'),'--output-root',str(state/'read')])+';runpy.run_path("tools/vnext_company.py",run_name="__main__")';read=subprocess.run([sys.executable,'-c',command],cwd=ROOT,capture_output=True,text=True);read_seconds=time.perf_counter()-start;assert read.returncode==0,read.stderr;assert before==snap(state/'state');row=list(csv.DictReader((state/'read/metrics_matrix.csv').open()))[0]
 if company=='marriott_international':assert row['value']=='0' and row['fiscal_year']=='2025' and row['period_end']=='2025-12-31',row
 if company=='salesforce':assert row['fiscal_year']=='2026' and row['period_start']=='2025-02-01' and row['period_end']=='2026-01-31',row
 if company.startswith('paramount'):assert row['value']=='' and row['status']=='WITHHELD',row
 assessment=json.loads((root/'input-assessments.json').read_text())['assessments']['current_auditor'];result={'source_root':str(SOURCE),'company':company,'args':args,'state_root':str(state/'state'),'first_exit':code,'first_seconds':seconds,'first':first,'repeat_exit':repeat_code,'repeat_seconds':repeat_seconds,'repeat':repeat,'read_seconds':read_seconds,'csv':row,'source_selection':{k:assessment[k] for k in ('selected_current_accession','names_differ','same_cik_prior_status','reason_code','event_forms','matched_item_4_01_claim_ids') if k in assessment},'saved_result_and_read_state_unchanged':True,'new_calls':[0,0,0]};results.append(result);(E/'actual-company.json').write_text(json.dumps({'code_root':str(ROOT),'source_root':str(SOURCE),'base':str(BASE),'results':results,'source_hashes_before':before_source},indent=2)+'\n');print(company,code,round(seconds,3),row['value'],row['status'],row['fiscal_year'],round(repeat_seconds,3),round(read_seconds,3),flush=True)
assert before_source=={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in before_source};print('PASS_THREE_CURRENT_C04_COMPANY_PATHS',flush=True)
