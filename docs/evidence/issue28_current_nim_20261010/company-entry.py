"""Actual source-only current NIM company entry, no network/model answers."""
import csv,hashlib,io,json,socket,sys,tempfile,time,shutil,subprocess
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from vnext.normal_annual_input import prepare_saved_annual_input
from tools.vnext_company import main
from vnext import ordinary_saved_result
HERE=Path(__file__).resolve().parent
BASE=Path(tempfile.mkdtemp(prefix='issue28-current-nim-complete-',dir='/private/tmp'))
source=BASE/'source';source.mkdir();state=BASE/'state';outputs=BASE/'outputs'
selected=prepare_saved_annual_input(repo_root=ROOT,company_id='jpmorgan_chase')
paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for proof in selected['source_proofs']:
 paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
for relative in paths:
 target=source/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
protected={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
summary={'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_code_state':'a823 prototype plus staged mainf6 and uncommitted optional current-record resolver','code_root':str(ROOT),'source_root':str(source),'state_root':str(state),'output_root':str(outputs),'source_files':len(protected),'source_contains_program':(source/'scripts').exists() or (source/'catalog').exists(),'new_calls':[0,0,0],'operations':[]}
(HERE/'current-runtime-path.json').write_text(json.dumps(summary,indent=2)+'\n')
args=['run','--company','jpmorgan_chase','--source-root',str(source),'--metric','A04','--work-dir',str(state),'--output-dir',str(outputs)]
with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')):
 for name,argv,forbid in [('first',args,False),('repeat',args,True),('read',['results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(BASE/'reader')],True)]:
  stream=io.StringIO();start=time.monotonic()
  if forbid:
   with patch.object(ordinary_saved_result,'_current_financial_case',side_effect=AssertionError('No repeated NIM calculation')),redirect_stdout(stream):rc=main(argv)
  else:
   with redirect_stdout(stream):rc=main(argv)
  text=stream.getvalue();(HERE/('current-'+name+'.json')).write_text(text);report=json.loads(text)
  summary['operations'].append({'name':name,'seconds':time.monotonic()-start,'exit_code':rc,'report':report});print(name,rc,summary['operations'][-1]['seconds'],flush=True)
  if rc not in (0,2) or name=='first' and report['metrics'][0]['status']!='CANDIDATE_READY':raise AssertionError(report)
  if name=='first':
   record=Path(report['metrics'][0]['record_root']);kept={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in record.rglob('*') if p.is_file()};summary['record_root']=str(record);summary['result_files']=len(kept)
  else:assert kept=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in kept}
  if name=='repeat':assert report['metrics'][0]['calculation_performed'] is False
summary['source_unchanged']=protected=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in protected}
summary['rows']=list(csv.DictReader((BASE/'reader/metrics_matrix.csv').open()))
assert summary['source_unchanged'] and len(summary['rows'])==1
(HERE/'current-company-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');print('SUMMARY',json.dumps({k:v for k,v in summary.items() if k not in ('operations','rows')},ensure_ascii=False),flush=True)
