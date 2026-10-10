import contextlib,csv,hashlib,io,json,runpy,socket,sys,time
from pathlib import Path
from unittest.mock import patch
from vnext import ordinary_current_update as update
state=Path('/private/tmp/issue28-current-b06-macys-20261011')
exports=Path('/private/tmp/issue28-current-b06-macys-20261011-final')
phase=sys.argv[1];destination=exports/phase
source=Path('/Users/lyuhongwang/Developer/SEC_metrics')
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name=='current-result.json')}
directories=set(state.glob('updates/B06/results/*'))
socket.socket.connect=lambda *a,**k:(_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN'))
args=['tools/vnext_company.py','run','--company','macys','--metric','B06','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(destination)]
if phase=='read':args=['tools/vnext_company.py','results','--company','macys','--state-root',str(state),'--output-root',str(destination)]
start=time.monotonic();stream=io.StringIO();code=0
with contextlib.ExitStack() as stack:
 if phase=='repeat':stack.enter_context(patch.object(update,'create_saved_result',side_effect=AssertionError('REPEATED_HOLD_MUST_NOT_CALCULATE')))
 if phase=='read':stack.enter_context(patch.object(update,'run_once',side_effect=AssertionError('READ_MUST_NOT_UPDATE')))
 sys.argv=args
 with contextlib.redirect_stdout(stream):
  try:runpy.run_path('tools/vnext_company.py',run_name='__main__')
  except SystemExit as e:code=e.code or 0
value=json.loads(stream.getvalue());seconds=time.monotonic()-start
assert code==(0 if phase=='read' else 2),(code,value)
if phase!='read':assert value['metrics'][0]['status']==('CANDIDATE_WITHHELD' if phase=='first' else 'PREVIOUS_INPUT_WITHHELD'),value
out=destination if phase=='read' else Path(value['output_root'])
with (out/'metrics_matrix.csv').open() as f:row=next(r for r in csv.DictReader(f) if r['metric_id']=='B06')
assert row['value']=='',row
assert row['period_end']=='2026-01-31' and row['fiscal_year']=='2025' and row['cik']=='794367',row
assert all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items())
if phase!='first':assert directories==set(state.glob('updates/B06/results/*'))
result={'phase':phase,'seconds':seconds,'exit':code,'code_root':str(Path.cwd()),'source_root':str(source),'state_root':str(state),'command':args,'old_files_preserved':len(protected),'no_new_result_directory':phase!='first','row':row,'metrics':value.get('metrics'),'new_calls':[0,0,0],'method':'Actual public CLI/source/case/writer/read; repeat only forbids factory, read only forbids update; socket denied'}
Path('docs/evidence/issue28_current_b06_20261010/'+phase+'-macy-hold-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('phase','seconds','exit','old_files_preserved','metrics')},ensure_ascii=False))
