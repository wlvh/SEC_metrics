import contextlib,csv,hashlib,io,json,runpy,socket,sys,time
from pathlib import Path
from unittest.mock import patch
from vnext import ordinary_registry_scope as registry
from vnext import ordinary_current_update as update

source=Path('/Users/lyuhongwang/Developer/SEC_metrics')
state=Path('/private/tmp/issue28-processing-company-20261010')
output=Path('/private/tmp/issue28-registry-row-scope-20261010')
program=Path.cwd();phase=sys.argv[1]
socket.socket.connect=lambda *a,**kw: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN'))
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and '/results/' in str(p)}
original=registry._registry_rows

def rows(*,repo_root):
    result=[dict(r) for r in original(repo_root=repo_root)]
    if phase=='unrelated':
        other=next(r for r in result if r['company_id']=='southwest_airlines');other['display_name']='TEST_ONLY changed unrelated name'
        added=dict(other);added.update(company_id='TEST_ONLY_UNRELATED',display_name='TEST_ONLY new unrelated',primary_cik='9999999');result.append(added)
    elif phase=='target':
        next(r for r in result if r['company_id']=='marriott_international')['primary_cik']='1048287'
    return result

args=['tools/vnext_company.py','run','--company','marriott_international','--metric','B04',
      '--source-root',str(source),'--work-dir',str(state),'--output-dir',str(output/(phase+'-out'))]
if phase=='read':args=['tools/vnext_company.py','results','--company','marriott_international',
                      '--state-root',str(state),'--output-root',str(output/'read-out-fixed')]
start=time.monotonic();stream=io.StringIO();code=0
with contextlib.ExitStack() as stack:
    if phase in ('unrelated','target'):
        stack.enter_context(patch.object(registry,'_registry_rows',side_effect=rows))
        stack.enter_context(patch.object(update,'create_saved_result',side_effect=AssertionError('FACTORY_FORBIDDEN_FOR_CHECK')))
    if phase=='read':stack.enter_context(patch.object(update,'run_once',side_effect=AssertionError('NO_UPDATE_ON_READ')))
    sys.argv=args
    with contextlib.redirect_stdout(stream):
        try:runpy.run_path('tools/vnext_company.py',run_name='__main__')
        except SystemExit as e:code=e.code or 0
payload=json.loads(stream.getvalue());elapsed=time.monotonic()-start
expected=2 if phase=='target' else 0;assert code==expected,(code,payload)
if phase=='unrelated':assert payload['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE',payload
if phase=='target':assert payload['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED' and 'FACTORY_FORBIDDEN' in payload['metrics'][0]['reason'],payload
out=Path(payload['output_root']) if phase!='read' else output/'read-out-fixed'
with (out/'metrics_matrix.csv').open() as f:row=next(r for r in csv.DictReader(f) if r['metric_id']=='B04')
if phase not in ('target','read'):assert row['value']=='2601000000' and row['unit']=='USD' and row['cik']=='1048286' and row['period_end']=='2025-12-31'
if phase=='read':
    assert row['value']=='' and row['period_role']=='PREVIOUS_RESULT' and row['status']=='INPUT_OR_EXECUTION_FAILED'
    pointer=json.loads((state/'updates/B04/current-result.json').read_text())
    result_root=state/'updates/B04/results'/pointer['version']
    stored=next(json.loads(line) for line in (result_root/'records.jsonl').read_text().splitlines() if json.loads(line)['record_type']=='METRIC_RESULT')
    assert stored['value']=='2601000000' and stored['result_id'].endswith('c87ee735d9b6f33bbecd5c35658a4f5791dac5956341ab46244076781cade5d2')
assert all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in protected.items())
result={'phase':phase,'code_root':str(program),'source_root':str(source),'state_root':str(state),'command':args,
        'seconds':elapsed,'exit':code,'old_result_files_preserved':len(protected),'metrics':payload.get('metrics'),
        'row':row,'method':'Actual CLI/controller/source/calculator/save/read; repeat/target only inject registry row input and forbid factory. No source/HTTP/business-answer stub. Target must fail before value credit; initial migration actually processes.','new_calls':[0,0,0]}
(output/(phase+'-consumer.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('phase','seconds','exit','old_result_files_preserved','metrics')},ensure_ascii=False))
