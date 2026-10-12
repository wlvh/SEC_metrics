"""Public-checkout replay, plus old default financial adapter identity control."""
import csv,io,json,socket,subprocess,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update,ordinary_financial_results as financial
ROOT=Path.cwd();E=Path(__file__).parent;base=Path(tempfile.mkdtemp(prefix='issue28-a13-repository-'))
args=['run','--company','jpmorgan_chase','--source-root',str(ROOT),'--metric','A13',
      '--work-dir',str(base/'state'),'--output-dir',str(base/'out')]
out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):code=main(args)
first=json.loads(out.getvalue());first_seconds=time.perf_counter()-start
assert code in (0,2) and first['metrics'][0]['status']=='CANDIDATE_READY',first
first_exit=code
record=Path(first['metrics'][0]['result_root']);row=list(csv.DictReader((record/'metrics_matrix.csv').open()))[0]
assert row['value']=='42758000000' and row['unit']=='USD',row
assert row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated repository calculation')),patch('sys.stdout',out):code=main(args)
repeat=json.loads(out.getvalue());repeat_seconds=time.perf_counter()-start
assert code==first_exit and repeat['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
assert first['metrics'][0]['result_id']==repeat['metrics'][0]['result_id']
previous=subprocess.check_output(['git','show','e24a5271325a2a39e8329df45f526f2629b543b0:scripts/vnext/ordinary_financial_results.py'],text=True)
namespace={'__name__':'vnext._prior_financial_default_control','__package__':'vnext'}
exec(compile(previous,'<base financial adapter, unchanged installed helpers>','exec'),namespace)
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    old=namespace['resolve_current_financial_metric'](repo_root=ROOT,company_id='jpmorgan_chase',metric_id='A13')
    new=financial.resolve_current_financial_metric(repo_root=ROOT,company_id='jpmorgan_chase',metric_id='A13')
assert old==new,'Default financial adapter output changed'
(E/'repository-source.json').write_text(json.dumps({'args':args,'first':first,'first_seconds':first_seconds,
    'first_exit':first_exit,'repeat':repeat,'repeat_seconds':repeat_seconds,'value':row['value'],'unit':row['unit'],
    'default_adapter_exact_equal':True,'default_result_id':old['result']['result_id'],
    'compatibility_scope':'Base adapter function bytes with unchanged installed helpers versus new default; not full old checkout execution',
    'new_calls':[0,0,0]},indent=2)+'\n')
print('PASS_PUBLIC_REPOSITORY_SOURCE_A13',row['value'],first_seconds,repeat_seconds,first['metrics'][0]['result_id'],flush=True)
print('REPOSITORY_SOURCE_OBSERVATION',first_exit,first['metrics'][0]['source_observation_errors'],flush=True)
print('PASS_DEFAULT_FINANCIAL_ADAPTER_EXACT_OUTPUT_EQUAL',old['result']['result_id'],flush=True)
