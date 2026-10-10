"""Resume the successfully saved first NIM case; do not recalculate it."""
import csv,hashlib,io,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from tools.vnext_company import main
from vnext import ordinary_saved_result,ordinary_current_update
HERE=Path(__file__).resolve().parent
summary=json.loads((HERE/'current-runtime-path.json').read_text());source=Path(summary['source_root']);state=Path(summary['state_root']);outputs=Path(summary['output_root']);base=state.parent
first=json.loads((HERE/'current-first.json').read_text());record=Path(first['metrics'][0]['record_root'])
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in record.rglob('*') if p.is_file()}
source_before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
summary['operations']=[{'name':'first','seconds':first['elapsed_seconds'],'exit_code':2,'report':first}]
summary['initial_harness_error']='Wrong expected exit0; actual NIM ready, global source census retained unrelated historical event-header error; resume saved result without first calculation'
args=['run','--company','jpmorgan_chase','--source-root',str(source),'--metric','A04','--work-dir',str(state),'--output-dir',str(outputs)]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(ordinary_saved_result,'_current_financial_case',side_effect=AssertionError('No NIM recalculation')):
 for name,argv in [('repeat',args),('read',['results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(base/'reader')])]:
  stream=io.StringIO();start=time.monotonic()
  with redirect_stdout(stream):rc=main(argv)
  report=json.loads(stream.getvalue());(HERE/('current-'+name+'.json')).write_text(stream.getvalue());summary['operations'].append({'name':name,'seconds':time.monotonic()-start,'exit_code':rc,'report':report})
  assert rc==(0 if name=='read' else 2),report
  if name=='repeat':assert report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and report['metrics'][0]['calculation_performed'] is False
  assert protected=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in protected}
  print(name,rc,summary['operations'][-1]['seconds'],flush=True)
summary.update(record_root=str(record),result_files=len(protected),result_files_unchanged=True,source_unchanged_during_repeat_read=source_before=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in source_before})
summary['rows']=list(csv.DictReader((base/'reader/metrics_matrix.csv').open()));summary['evidence']=list(csv.DictReader((base/'reader/metric_evidence.csv').open()))
(HERE/'current-company-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');print('ROWS',json.dumps([{k:r[k] for k in ('cik','metric_id','value','unit','period_start','period_end','status')} for r in summary['rows']],ensure_ascii=False),flush=True)
