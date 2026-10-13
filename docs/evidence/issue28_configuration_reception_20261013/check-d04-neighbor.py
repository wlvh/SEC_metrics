"""Current finance reception must keep an unrelated real D04 conclusion reusable."""
import csv,hashlib,io,json,shutil,socket,subprocess,sys,time
from contextlib import redirect_stdout
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from tools.vnext_company import main
from vnext import current_d04_result,calculator
original=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/macys-d04-control-version-20261013/state')
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/config-reception-20261013')
state=base/'state';assert not state.exists(),'Existing receipt/state must be resumed without recopy'
base.mkdir(exist_ok=True);shutil.copytree(original,state)
configuration=json.loads((state/'updates/D04/completed-check.json').read_text())['configuration']
source=Path(configuration['source_root']);reader=base/'reader';out=base/'outputs'
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'updates/D04/results').rglob('*') if p.is_file()}
old_protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
def forbidden(*args,**kwargs):raise AssertionError('UNCHANGED_D04_PROCESSING_FORBIDDEN')
functions=[current_d04_result.prepare_current_d04_case,calculator.calculate_text_metric]
oldcodes=[fn.__code__ for fn in functions];old_connect=socket.socket.connect;old_dns=socket.getaddrinfo
try:
 for fn,code in zip(functions,oldcodes):fn.__code__=forbidden.__code__.replace(co_filename=code.co_filename,co_firstlineno=code.co_firstlineno)
 socket.socket.connect=forbidden;socket.getaddrinfo=forbidden
 stdout=io.StringIO();start=time.monotonic()
 with redirect_stdout(stdout):rc=main(['run','--company','macys','--source-root',str(source),'--metric','D04','--work-dir',str(state),'--output-dir',str(out)])
 seconds=time.monotonic()-start;report=json.loads(stdout.getvalue());metric=report['metrics'][0]
 assert rc==2 and metric['status']=='PREVIOUS_INPUT_WITHHELD' and not metric['calculation_performed'],report
 assert metric['result_id']=='sha256:a2a0bb5fe143c07d445284f9b0d3def00f887440032ac1031a3e31bfc3aa2069',metric
finally:
 for fn,code in zip(functions,oldcodes):fn.__code__=code
 socket.socket.connect=old_connect;socket.getaddrinfo=old_dns
started=time.monotonic();r=subprocess.run([sys.executable,str(ROOT/'tools/vnext_company.py'),'results','--company','macys','--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True)
assert r.returncode==0,r.stderr
rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));assert len(rows)==1
row=rows[0];assert row['value']=='' and row['period_start']=='2025-02-02' and row['period_end']=='2026-01-31' and row['status']=='TEXT_QUAL',row
assert protected=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'updates/D04/results').rglob('*') if p.is_file()}
assert old_protected=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
result={'code_root':str(ROOT),'copied_original_state':str(original),'test_state':str(state),'source_root':str(source),
 'run_seconds':seconds,'independent_read_seconds':time.monotonic()-started,'metric':metric,'row':row,
 'result_layer_files_preserved':len(protected),'original_state_files_preserved':len(old_protected),
 'producer_and_calculator_forbidden':True,'new_calls':[0,0,0],'business_content_not_newly_accepted':True}
(Path(__file__).parent/'d04-neighbor.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('real-D04-reuse',seconds,'independent-read',result['independent_read_seconds'],'result files kept',len(protected),flush=True)
