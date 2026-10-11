"""Existing complete real D04 responses; raw-change append is recorded only."""
import csv,hashlib,io,json,socket,subprocess,sys,tarfile,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext.continuous_call_ledger import CallLedger
from vnext import ordinary_current_update as update
from vnext.recorded_sec_http import RecordedSecHttpClient
ROOT=Path.cwd();E=Path(__file__).parent;CODE_FILES=('current_d04_result.py','ordinary_d04_task_input.py','ordinary_task_input.py','ordinary_current_update.py','ordinary_d04_saved_route.py','continuous_semantic_calls.py');CODE_HASHES={p:hashlib.sha256((ROOT/'scripts/vnext'/p).read_bytes()).hexdigest() for p in CODE_FILES};ARCHIVE=Path('/private/tmp/issue28-d04-r2-original-live2.tar.xz')
BASE=Path(tempfile.mkdtemp(prefix='issue28-d04-r2-'));SOURCE=BASE/'d04-original-source'
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()=='10d5e21437f3ceea4d3fd5b20b41076bca35ec0bcdd31173ba0dcd538833db34'
with tarfile.open(ARCHIVE,'r:xz') as t:
 members=[m for m in t.getmembers() if m.name.startswith('./d04-original-source/')]
 t.extractall(BASE,members=members,filter='data')
LEDGER=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
protected=[LEDGER/'claims.jsonl',LEDGER/'binding.json']
for i in range(115,119):protected.extend(p for p in (LEDGER/'calls'/f'{i:04d}').rglob('*') if p.is_file())
def hashes(paths):return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def tree(root):return hashes([p for p in root.rglob('*') if p.is_file()])
original=hashes(protected);ops=[]
REAL_SOURCE=LEDGER/'source-inputs'
args=['run','--company','marriott_international','--source-root',str(SOURCE),'--metric','D04','--work-dir',str(BASE/'state'),'--output-dir',str(BASE/'out')]
def run(label,forbid=False,no_parse=False):
 out=io.StringIO();start=time.perf_counter()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch.object(CallLedger,'claim',side_effect=AssertionError('No new actual claims')),patch('sys.stdout',out):
  if forbid:
   with patch.object(update,'create_saved_result',side_effect=AssertionError('No full D04 assessment replay')):
    if no_parse:
     with patch('vnext.ordinary_d04_task_input.fingerprint',side_effect=AssertionError('No second task parse')):code=main(args)
    else:code=main(args)
  else:code=main(args)
 result=json.loads(out.getvalue());item={'label':label,'code':code,'seconds':time.perf_counter()-start,'report':result};ops.append(item);(E/'actual-progress.json').write_text(json.dumps({'base':str(BASE),'operations':ops},indent=2)+'\n');print(label,code,item['seconds'],[(x['status'],x.get('source_comparison')) for x in result.get('metrics',[])],flush=True);assert code in (0,2) and result['metrics'][0]['status'] in {'CANDIDATE_WITHHELD','PREVIOUS_INPUT_WITHHELD'},(label,result)
 return result
if '--resume' in sys.argv:
 previous=json.loads((E/'actual-progress.json').read_text());BASE=Path(previous['base']);SOURCE=BASE/'d04-original-source';ops=previous['operations'];first=ops[0]['report']
else:
 first=run('first-current-complete-D04')
# All operations use one stable isolated source root; original archive and
# private actual ledger are unchanged.
real_args=list(args)
r=first['metrics'][0];assert r['status']=='CANDIDATE_WITHHELD' and r['result_reason_code']=='D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE'
result_root=Path(r['result_root']);before_result=tree(result_root)
client=RecordedSecHttpClient(recorded_root=SOURCE,workdir=SOURCE,config_path=ROOT/'config/sec_config.json',log_path=SOURCE/'evidence/requests_log.csv')
url='https://www.sec.gov/Archives/edgar/data/1048286/000104828626000007/mar-20251231.htm'
with tarfile.open(ARCHIVE,'r:xz') as t:
 member=next(m for m in t.getmembers() if m.name.endswith('/2068d81830ea882910ef7043026445bae69f925c094dbb40d030de4afc001151/mar-20251231.htm'))
 raw=t.extractfile(member).read()
assert hashlib.sha256(raw).hexdigest()=='2068d81830ea882910ef7043026445bae69f925c094dbb40d030de4afc001151'
with patch.object(client,'reply',return_value=(200,raw,{},'')):
 client._fetch_once(url=url,purpose='ISOLATED_R2_EXISTING_SAVED_BODY_TEST',local_path=SOURCE/'evidence/raw/r2-live2/mar-20251231.htm',attempt=0)
second=run('same-task-new-original-bytes',True)
second=second['metrics'][0]
assert second['status']=='PREVIOUS_INPUT_WITHHELD',second;assert second['source_comparison']=='PARSED_D04_TASK_INPUT_UNCHANGED';assert second['result_id']==r['result_id'];assert tree(result_root)==before_result
third=run('same-checked-raw-no-task-parse',True,True)['metrics'][0];assert third['result_id']==r['result_id'];assert tree(result_root)==before_result
before=tree(BASE/'state');start=time.perf_counter()
code='import runpy,socket,sys; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network")); sys.argv='+repr(['tools/vnext_company.py','results','--company','marriott_international','--state-root',str(BASE/'state'),'--output-root',str(BASE/'read')])+'; runpy.run_path("tools/vnext_company.py",run_name="__main__")'
read=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True);read_seconds=time.perf_counter()-start;assert read.returncode==0,read.stderr;assert before==tree(BASE/'state');assert hashes(protected)==original
rows=list(csv.DictReader((BASE/'read/metrics_matrix.csv').open()));assert rows[0]['status']=='TEXT_QUAL' and rows[0]['period_end']=='2025-12-31'
assert CODE_HASHES=={p:hashlib.sha256((ROOT/'scripts/vnext'/p).read_bytes()).hexdigest() for p in CODE_FILES},'Code changed during run'
summary={'code_hashes':CODE_HASHES,'code_root':str(ROOT),'code_identity':'working-tree hashes recorded separately','source_root':str(SOURCE),'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),'state':str(BASE/'state'),'operations':ops,'read_seconds':read_seconds,'rows':rows,'old_result_files_unchanged':True,'ledger_and_real115_118_files_unchanged':True,'new_calls':[0,0,0],'source_comparison_test_adaptation':'None: all phases use the same formal company task and fixed isolated source root; saved-response-only request factory blocks actual execution', 'source_append':'Isolated recorded persistence of already saved real live2 body; not new SEC acquisition'};(E/'actual-company.json').write_text(json.dumps(summary,indent=2)+'\n');print('PASS_ACTUAL_COMPANY_PARSE_REUSE',read_seconds,flush=True)
