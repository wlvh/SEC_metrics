"""Actual public saved sources at formal CLI, failure record and independent reader."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import current_auditor_case as auditor,ordinary_current_update as update
ROOT=Path.cwd();E=Path(__file__).parent;source=ROOT
old_code=subprocess.check_output(['git','show','b2a7210f9d92c725bdf63862d906c7b1435a162d:scripts/vnext/current_auditor_case.py'],text=True)
namespace={'__name__':'vnext._old_current_auditor_control','__package__':'vnext'}
exec(compile(old_code,'<base current wrapper with unchanged installed helpers>','exec'),namespace)
old_factory=namespace['prepare_current_auditor_case']
def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
protected=[source/p for p in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')]
source_before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
def run(args,old=False,forbid=False):
    out=io.StringIO();start=time.perf_counter()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):
        if old:
            with patch.object(auditor,'prepare_current_auditor_case',side_effect=old_factory):code=main(args)
        elif forbid:
            with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated C04 calculation')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No new C04 result')):code=main(args)
        else:code=main(args)
    return code,json.loads(out.getvalue()),time.perf_counter()-start
rows=[]
for company in ('jpmorgan_chase','salesforce','marriott_international'):
    base=Path(tempfile.mkdtemp(prefix='issue28-c04-detail-'+company+'-'))
    args=['run','--company',company,'--source-root',str(source),'--metric','C04',
          '--work-dir',str(base/'after'),'--output-dir',str(base/'out')]
    if company!='marriott_international':
        prior=list(args);prior[prior.index('--work-dir')+1]=str(base/'before')
        code,before,before_seconds=run(prior,old=True)
        assert code==2 and before['metrics'][0]['reason']=='C04_REGISTRATION_BASE_INPUT_UNRESOLVED',before
    else:before=None;before_seconds=None
    code,after,after_seconds=run(args)
    metric=after['metrics'][0]
    if company!='marriott_international':
        assert code==2 and metric['status']=='INPUT_OR_EXECUTION_FAILED',after
        assert metric['reason'].startswith('C04_REGISTRATION_BASE_INPUT_UNRESOLVED:'),metric
        failures=list((base/'after').glob('updates/C04/results/*/failure.json'))
        assert len(failures)==1
        failure=json.loads(failures[0].read_text());assert failure['error']==metric['reason']
        assert not list((base/'after').glob('updates/C04/results/*/manifest.json'))
        if company=='jpmorgan_chase':
            for item in ('SAVED_HISTORY_INDEX_AND_BODY_ARE_NOT_A_COHERENT_SNAPSHOT',
                         'CIK0000019617-submissions-001.json','2025-07-15','2025-08-13'):
                assert item in metric['reason'],metric
        else:
            assert 'LATEST_SOURCE_REQUEST_FAILED' in metric['reason'] and '.hdr.sgml' in metric['reason'],metric
        repeated=None;repeat_seconds=None
    else:
        assert code==0 and metric['status']=='CANDIDATE_READY',after
        record=Path(metric['result_root']);record_before=snapshot(record)
        code,repeated,repeat_seconds=run(args,forbid=True)
        assert code==0 and repeated['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
        assert repeated['metrics'][0]['result_id']==metric['result_id'] and record_before==snapshot(record)
    state_before=snapshot(base/'after');start=time.perf_counter()
    command='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network"));sys.argv='+repr(['tools/vnext_company.py','results','--company',company,'--state-root',str(base/'after'),'--output-root',str(base/'read')])+';runpy.run_path("tools/vnext_company.py",run_name="__main__")'
    read=subprocess.run([sys.executable,'-c',command],cwd=ROOT,capture_output=True,text=True);read_seconds=time.perf_counter()-start
    assert read.returncode==0,read.stderr
    view=json.loads(read.stdout);assert snapshot(base/'after')==state_before
    row=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))[0]
    if company=='marriott_international':assert row['value']=='0' and row['fiscal_year']=='2025',row
    else:
        assert row['value']=='',row
        assert view['metrics'][0]['latest_observation']=='INPUT_OR_EXECUTION_FAILED',view
        assert view['metrics'][0]['reason']==metric['reason'],view
    result={'company':company,'args':args,'before':before,'before_seconds':before_seconds,
            'after':after,'after_seconds':after_seconds,'repeat':repeated,'repeat_seconds':repeat_seconds,
            'read_seconds':read_seconds,'csv':row,'read':view}
    rows.append(result);(E/'actual-company.json').write_text(json.dumps({'code_root':str(ROOT),
        'source_root':str(source),'before_scope':'Base wrapper function with unchanged installed helpers, not full old-checkout execution',
        'source_hashes_before':source_before,'rows':rows,'new_calls':[0,0,0]},indent=2)+'\n')
    print(company,round(after_seconds,3),metric['status'],metric.get('reason',metric.get('result_id')),flush=True)
assert source_before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
print('PASS_REAL_CURRENT_C04_FAILURE_DETAILS_AND_POSITIVE_REUSE',flush=True)
