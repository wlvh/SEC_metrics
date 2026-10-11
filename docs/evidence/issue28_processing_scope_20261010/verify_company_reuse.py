"""Real saved-source user CLI and independent reading, with network disabled."""
import argparse, contextlib, csv, hashlib, io, json, runpy, socket, sys, time
from pathlib import Path
from unittest.mock import patch

p=argparse.ArgumentParser()
p.add_argument('--program-root',required=True,type=Path)
p.add_argument('--source-root',required=True,type=Path)
p.add_argument('--state-root',required=True,type=Path)
p.add_argument('--output-root',required=True,type=Path)
p.add_argument('--mode',required=True,choices=('first','repeat','read'))
p.add_argument('--baseline',type=Path)
a=p.parse_args();program=a.program_root.resolve()
sys.path[:0]=[str(program),str(program/'scripts')]
from vnext.canonical import strict_json_file

def protected():
    return {str(q.relative_to(a.state_root)):hashlib.sha256(q.read_bytes()).hexdigest()
            for q in a.state_root.rglob('*') if q.is_file() and
            ('/results/' in str(q) or q.name=='current-result.json')}

before=protected();args=['results','--company','marriott_international','--state-root',str(a.state_root),
    '--output-root',str(a.output_root)] if a.mode=='read' else ['run','--company','marriott_international',
    '--source-root',str(a.source_root),'--work-dir',str(a.state_root),'--output-dir',str(a.output_root),'--metric','B04']
stream=io.StringIO();started=time.monotonic();code=0
with contextlib.ExitStack() as stack:
    stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('No network')))
    stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')))
    if a.mode=='repeat':
        stack.enter_context(patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No repeated calculation')))
    if a.mode=='read':
        stack.enter_context(patch('vnext.ordinary_current_update.run_once',side_effect=AssertionError('No update on independent reading')))
    sys.argv=['vnext_company.py']+args
    with contextlib.redirect_stdout(stream):
        try:runpy.run_path(str(program/'tools/vnext_company.py'),run_name='__main__')
        except SystemExit as e:code=e.code or 0
elapsed=time.monotonic()-started;payload=json.loads(stream.getvalue())
if a.mode=='read':output=a.output_root;report=payload
else:report=strict_json_file(path=a.state_root/'latest-execution.json');output=Path(report['output_root'])
rows=list(csv.DictReader((output/'metrics_matrix.csv').open()))
row=next(x for x in rows if x['metric_id']=='B04')
evidence=list(csv.DictReader((output/'metric_evidence.csv').open()))
assert row['value'] and row['unit']=='USD' and row['fiscal_year']=='2025' and row['cik']=='1048286',row
assert row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
assert evidence and any('0001048286-26-000007' in str(x) for x in evidence), evidence
assert code==0,(code,payload)
if a.mode=='repeat':assert report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE',report
if a.baseline:
    previous=json.loads(a.baseline.read_bytes())
    for field in ('value','unit','period_start','period_end','fiscal_year','cik','result_id'):
        assert row[field]==previous['row'][field],(field,row[field],previous['row'][field])
after=protected()
if a.mode!='first':assert before==after
print(json.dumps({'mode':a.mode,'program_root':str(program),'source_root':str(a.source_root),'state_root':str(a.state_root),
    'output_root':str(output),'seconds':elapsed,'exit_code':code,'row':row,
    'metric_status':report.get('metrics',[{}])[0].get('status'),'result_files_and_success_pointer':len(after),
    'protected_files_unchanged':before==after,'configuration_compatibility':report.get('metrics',[{}])[0].get('configuration_compatibility'),
    'new_calls':[0,0,0]},ensure_ascii=False,indent=2))
