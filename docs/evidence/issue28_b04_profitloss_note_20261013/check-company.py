"""Read actual selected facts; run/store/read the shared current company entry."""
import csv,hashlib,io,json,socket,subprocess,sys,time,types
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from vnext import ordinary_projection as current,current_statement_metric_case as producer
from tools.vnext_company import main
BASE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/profitloss-note-20261013')
SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
HERE=Path(__file__).parent;case=json.loads((BASE/'case.json').read_text())
baseline=types.ModuleType('vnext._baseline_projection');baseline.__package__='vnext';baseline.__file__=str(ROOT/'scripts/vnext/ordinary_projection.py')
exec(compile(subprocess.check_output(['git','show','ffd0765a:scripts/vnext/ordinary_projection.py']),baseline.__file__,'exec'),baseline.__dict__)
manifest={'company_id':'ford_motor_company','target_period':case['target_period'],'source_references':case['references'],'run_id':'ordinary:projection-test','status':'CALCULATED'}
kwargs=dict(data_root=SOURCE,manifest=manifest,records=case['expected_records'],case=case,
 receipt_status='SAVED_SOURCE_TEST',source_validation='SOURCE_CALCULATOR_AND_RECORD_CHECKS',prepared_annual_input=case['prepared_annual_input'])
a=baseline.render_ordinary_records(**kwargs);b=current.render_ordinary_records(**kwargs)
def rows(raw):return list(csv.DictReader(io.StringIO(raw.decode())))
before,after=rows(a['files']['metrics_matrix.csv'])[0],rows(b['files']['metrics_matrix.csv'])[0]
assert before['value']==after['value']=='-8162000000' and 'non-controlling interest' not in before['notes']
assert 'ProfitLoss may include non-controlling interest.' in after['notes']
assert {k:v for k,v in before.items() if k!='notes'}=={k:v for k,v in after.items() if k!='notes'}
assert a['files']['metric_evidence.csv']==b['files']['metric_evidence.csv']
state=BASE/'state';out=BASE/'outputs';assert not state.exists(),'Do not repeat an already executed first run'
args=['run','--company','ford_motor_company','--source-root',str(SOURCE),'--metric','B04','--work-dir',str(state),'--output-dir',str(out)]
results=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
 for name,forbid in [('first',False),('repeat',True)]:
  stream=io.StringIO();start=time.monotonic()
  if forbid:
   with patch.object(producer,'prepare_current_statement_metric_case',side_effect=AssertionError('No repeated calculation')),redirect_stdout(stream):code=main(args)
  else:
   with redirect_stdout(stream):code=main(args)
  report=json.loads(stream.getvalue());metric=report['metrics'][0]
  assert code in (0,2) and metric['status']==('NO_SOURCE_CONTENT_CHANGE' if forbid else 'CANDIDATE_READY'),report
  results.append({'name':name,'seconds':time.monotonic()-start,'exit_code':code,'metric':metric})
  if not forbid:
   root=Path(metric['result_root']);protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
  else:assert protected=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in protected}
start=time.monotonic();reader=BASE/'reader'
r=subprocess.run([sys.executable,str(ROOT/'tools/vnext_company.py'),'results','--company','ford_motor_company','--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True)
assert r.returncode==0,r.stderr
actual=list(csv.DictReader((reader/'metrics_matrix.csv').open()));assert len(actual)==1
row=actual[0];assert row['value']=='-8162000000' and row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31' and row['cik']=='37996'
assert 'ProfitLoss may include non-controlling interest.' in row['notes']
assert protected=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in protected}
receipt={'code_root':str(ROOT),'source_root':str(SOURCE),'state_root':str(state),'tested_state':'mainffd plus named uncommitted renderer/test diff',
 'baseline_row':before,'new_row':after,'evidence_csv_bytes_unchanged':True,'operations':results,
 'independent_read_seconds':time.monotonic()-start,'read_row':row,'result_files_unchanged':len(protected),
 'new_calls':[0,0,0],'reference_comment':6144895876,'business_value_not_changed':True}
(HERE/'company-check.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print('run/repeat',[(r['name'],r['seconds']) for r in results],'read',receipt['independent_read_seconds'],'files',len(protected),flush=True)
