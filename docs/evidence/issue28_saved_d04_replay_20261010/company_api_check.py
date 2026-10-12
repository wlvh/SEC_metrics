import sys,json,time,socket,tempfile,hashlib,importlib.util,subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from vnext.company_current_records import run_saved_company
from vnext.saved_d04_replay import prepare_selected_saved_d04_case
spec=importlib.util.spec_from_file_location('vnext._peer_d04_selector','/tmp/issue28-saved-d04-current/historical_d04_selection.py');peer=importlib.util.module_from_spec(spec);spec.loader.exec_module(peer)
x=json.loads(Path('/tmp/issue28-saved-d04-current/selected-marriott2023.json').read_text());package=Path(x['saved_call_package'])
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
base=Path(tempfile.mkdtemp(prefix='issue28-selected-d04-',dir='/private/tmp'));here=ROOT/'docs/evidence/issue28_saved_d04_replay_20261010'
controls={'forbid':False}
def factory(*,repo_root,company_id,metric_id,fiscal_year):
 if controls['forbid']:raise AssertionError('unchanged original D04 must not replay')
 selected=peer.prepare_historical_d04_selection(source_root=repo_root,company_id=company_id,fiscal_year=fiscal_year,saved_call_package=package)
 return prepare_selected_saved_d04_case(source_root=repo_root,selection=selected)
f=factory
protected={str(package):hashlib.sha256(package.read_bytes()).hexdigest()};ops=[]
args=dict(company_id='marriott_international',source_root=source,work_dir=base/'state',output_dir=base/'output',metric_ids=['D04'],fiscal_years=[2023],case_factories={'D04':f},processing_files_by_metric={'D04':['scripts/vnext/saved_d04_replay.py','scripts/vnext/current_d04_result.py','scripts/vnext/d04_native_assessment.py','scripts/vnext/capacity_native_assessment.py','scripts/vnext/native_unit_index.py','scripts/vnext/continuous_semantic_calls.py','scripts/vnext/continuous_request_context.py','scripts/vnext/native_request_construction.py']},processing_inputs_by_metric={'D04':[package]})
with patch.object(socket.socket,'connect',side_effect=AssertionError('no network')):
 for label in ['first','repeat-forbid-factory']:
  controls['forbid']=label!='first';start=time.perf_counter();got=run_saved_company(**args);elapsed=time.perf_counter()-start
  (here/(label+'-company.json')).write_text(json.dumps(got,ensure_ascii=False,indent=2)+'\n');print(label,elapsed,got['metrics'],flush=True);ops.append({'label':label,'seconds':elapsed,'report':got})
  m=got['metrics'][0];assert m['result_reason_code']=='D04_SAVED_FILING_MEDIA_COVERAGE_NOT_VERIFIED'
  if label!='first':assert m['status']=='PREVIOUS_INPUT_WITHHELD' and not m['calculation_performed']
assert protected[str(package)]==hashlib.sha256(package.read_bytes()).hexdigest()
(here/'company-api-summary.json').write_text(json.dumps({'code_root':str(ROOT),'source_root':str(source),'state_root':str(base/'state'),'package_sha256':protected[str(package)],'operations':ops,'new_calls':[0,0,0],'formal_history_CLI_not_yet_connected':True},ensure_ascii=False,indent=2)+'\n')
