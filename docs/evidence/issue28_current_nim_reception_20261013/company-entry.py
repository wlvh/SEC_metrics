"""Recheck this main combination through the existing company CLI; zero egress."""
import csv,hashlib,io,json,socket,sys,time,shutil,subprocess
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from vnext.normal_annual_input import prepare_saved_annual_input
from tools.vnext_company import main
from vnext import ordinary_saved_result
HERE=Path(__file__).resolve().parent
BASE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/nim-reception-20261013')
source=BASE/'source';state=BASE/'state';outputs=BASE/'outputs'
assert not state.exists(),'Use the existing receipt to resume; do not repeat a first run.'
source.mkdir(exist_ok=True)
selected=prepare_saved_annual_input(repo_root=ROOT,company_id='jpmorgan_chase')
paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for proof in selected['source_proofs']:
 paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
for relative in paths:
 target=source/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
protected={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
result={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'code_root':str(ROOT),'source_root':str(source),'state_root':str(state),'operations':[],
 'uncommitted_code_diff':subprocess.check_output(['git','diff','HEAD','--','scripts','tools'],cwd=ROOT,text=True),
 'source_files':len(protected),'new_calls':[0,0,0]}
args=['run','--company','jpmorgan_chase','--source-root',str(source),'--metric','A04','--work-dir',str(state),'--output-dir',str(outputs)]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
 for name,forbid in [('first',False),('repeat',True)]:
  stream=io.StringIO();started=time.monotonic()
  if forbid:
   with patch.object(ordinary_saved_result,'_current_financial_case',side_effect=AssertionError('No repeated NIM calculation')),redirect_stdout(stream):code=main(args)
  else:
   with redirect_stdout(stream):code=main(args)
  report=json.loads(stream.getvalue());metric=report['metrics'][0]
  result['operations'].append({'name':name,'seconds':time.monotonic()-started,'exit_code':code,'metric':metric})
  (HERE/'company-entry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  assert code in (0,2),report
  assert metric['result_id']=='sha256:b0cc257695b62ebdca2e14b9f733040499b171e2b6598253a161bce9d5d2db64',report
  if not forbid:
   assert metric['status']=='CANDIDATE_READY',report
   original={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'updates/A04/results').rglob('*') if p.is_file()}
  else:
   assert metric['status']=='NO_SOURCE_CONTENT_CHANGE' and not metric['calculation_performed'],report
   assert original=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'updates/A04/results').rglob('*') if p.is_file()}
  print(name,code,result['operations'][-1]['seconds'],metric['status'],flush=True)
read=BASE/'reader';started=time.monotonic()
r=subprocess.run([sys.executable,str(ROOT/'tools/vnext_company.py'),'results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(read)],capture_output=True,text=True)
assert r.returncode==0,r.stderr
rows=list(csv.DictReader((read/'metrics_matrix.csv').open()));assert len(rows)==1
row=rows[0]
assert (row['metric_id'],row['value'],row['unit'],row['period_start'],row['period_end'],row['cik'])==('A04','0.025','ratio','2025-01-01','2025-12-31','19617'),row
assert original=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'updates/A04/results').rglob('*') if p.is_file()}
assert protected=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in protected}
result.update(independent_read_seconds=time.monotonic()-started,row=row,
 source_unchanged=True,result_files_preserved=len(original),business_content_not_newly_accepted=True)
result['uncommitted_code_diff_sha256']=hashlib.sha256(result.pop('uncommitted_code_diff').encode()).hexdigest()
(HERE/'company-entry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('independent-read',result['independent_read_seconds'],'files',len(original),'value',row['value'],flush=True)
