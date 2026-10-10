"""Revalidate only the existing own NIM task after its necessary main merge."""
import csv,hashlib,io,json,socket,subprocess,sys,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from tools.vnext_company import main
from vnext import ordinary_saved_result
HERE=Path(__file__).resolve().parent
old=json.loads((HERE/'final-company-validation.json').read_text())
source,state=Path(old['source_root']),Path(old['state_root']);outputs=state.parent/'main-receiving-runs'
def protected():
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'updates/A04/results').rglob('*') if p.is_file()}
source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
before=protected();operations=[]
# The initial CLI committed successfully before a harness-only empty-lock
# assertion failed. Resume the actual saved terminal, never repeat calculation.
prior=json.loads((state/'latest-execution.json').read_text())
if prior['metrics'][0]['status']!='CANDIDATE_READY':
 current=json.loads((state/'updates/A04/current-result.json').read_text())
 terminals=[json.loads(p.read_text()) for p in (state/'updates/A04/checks').glob('*/terminal.json')]
 matched=[r for r in terminals if r['status']=='CANDIDATE_READY' and r.get('version')==current['version']]
 assert len(matched)==1
 prior={**prior,'metrics':[matched[0]]}
operations.append({'name':'main-revalidation-before-harness-error',
    'seconds':None, 'time_scope':'elapsed_seconds returned only on stdout; initial duration not recovered from persisted report',
    'exit_code':2,'metric':prior['metrics'][0]})
from vnext.ordinary_saved_result import read_saved_result
original_versions={Path(old['operations'][0]['report']['metrics'][0]['result_root']),
    Path(json.loads((HERE/'current-first.json').read_text())['metrics'][0]['result_root'])}
for original in original_versions:read_saved_result(output_root=original)
old_files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for v in original_versions for p in v.rglob('*') if p.is_file()}
after=protected()
args=['run','--company','jpmorgan_chase','--source-root',str(source),'--metric','A04','--work-dir',str(state),'--output-dir',str(outputs)]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
 for name,forbid in [('forbidden-repeat',True)]:
  stream=io.StringIO();started=time.monotonic()
  if forbid:
   with patch.object(ordinary_saved_result,'_current_financial_case',side_effect=AssertionError('No repeated financial calculation')),redirect_stdout(stream):code=main(args)
  else:
   with redirect_stdout(stream):code=main(args)
  report=json.loads(stream.getvalue());operations.append({'name':name,'seconds':time.monotonic()-started,'exit_code':code,'metric':report['metrics'][0]})
  assert code==2 and report['metrics'][0]['source_observation_errors'],report
  assert report['metrics'][0]['result_id']=='sha256:b0cc257695b62ebdca2e14b9f733040499b171e2b6598253a161bce9d5d2db64',report
  assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in before.items())
  if forbid:assert report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not report['metrics'][0]['calculation_performed']
  else:after=protected()
  print(name,operations[-1]['seconds'],report['metrics'][0]['status'],flush=True)
  if forbid:assert protected()==after
reader=state.parent/'main-receiving-reader';started=time.monotonic()
r=subprocess.run([sys.executable,str(ROOT/'tools/vnext_company.py'),'results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True)
assert r.returncode==0,r.stderr
read_seconds=time.monotonic()-started;rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));row=rows[0]
assert len(rows)==1 and row['metric_id']=='A04' and row['value']=='0.025' and row['unit']=='ratio' and row['cik']=='19617',rows
assert row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31' and row['fiscal_year']=='2025',row
assert protected()==after
assert source_hashes=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in source_hashes}
value={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'code_root':str(ROOT),'source_root':str(source),'state_root':str(state),'operations':operations,
 'independent_read_seconds':read_seconds,'independent_read_exit':r.returncode,'row':row,
 'old_result_files_preserved':len(old_files),'post_transition_result_files_preserved':len(after),
 'source_files_unchanged':len(source_hashes),'new_calls':[0,0,0],
 'unrelated_source_error_remains_visible':True,'business_content_not_newly_accepted':True,
 'initial_harness_failure':'empty write.lock incorrectly treated as changed; actual terminal recovered without another calculation',
 'original_records_current_reader_checked':True}
(HERE/'main-company-validation.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
print('read',read_seconds,'old/post result files',len(before),len(after),'current value/period',row['value'],row['period_end'],flush=True)
