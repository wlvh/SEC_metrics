from pathlib import Path
import argparse,contextlib,csv,io,json,subprocess,sys,tempfile,time,socket,hashlib
from unittest.mock import patch
from tools.vnext_company import main
from vnext.normal_governance_input import _Sources
from vnext import historical_event_cases
parser=argparse.ArgumentParser()
parser.add_argument('--source-root',type=Path,default=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs'))
options=parser.parse_args();source=options.source_root
program=Path.cwd();state=Path(tempfile.mkdtemp(prefix='issue28-event-reporter-')).resolve()
rows=[];cases=[]
real=historical_event_cases.prepare_historical_event_year_case
for metric,year,value in [('C01',2025,'3'),('E05',2021,'1')]:
    base=state/(metric+str(year));args=['run','--company','marriott_international','--period','fiscal-years','--fiscal-year-start',str(year),'--fiscal-year-end',str(year),'--metric',metric,'--source-root',str(source),'--work-dir',str(base/'state'),'--output-dir',str(base/'out')]
    captured=[]
    def capture(frame,event,value):
        if event=="return" and frame.f_code is real.__code__:
            captured.append(value)

    def no_primary(*a,**kw):raise AssertionError("No extra annual primary in event reader")
    stream=io.StringIO();start=time.monotonic()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(_Sources,'primary',new=no_primary),contextlib.redirect_stdout(stream):
        sys.setprofile(capture)
        try:code=main(args)
        finally:sys.setprofile(None)
    elapsed=time.monotonic()-start;report=json.loads(stream.getvalue());case=captured[0]
    reused_first_material=False
    print(metric,year,code,report['status'],elapsed)
    assert code==0,report
    annual=case['prepared_annual_input']
    # Execute the previous public helper against exactly the actual new case.
    import types
    text=subprocess.check_output(['git','show','8789b7bd:scripts/vnext/ordinary_projection.py'],text=True)
    previous=types.ModuleType('vnext._previous_projection');previous.__package__='vnext';exec(compile(text,'old_projection','exec'),previous.__dict__)
    company=next(c for c in previous.projector._load_registry(repo_root=source) if c['company_id']=='marriott_international')
    target=case['traces'][metric]['calculation_target']
    try:
        previous._reporting_company_view(data_root=source,company=company,annual=annual,calculation_target=target,source_references=case['references'])
        raise AssertionError('Original reporter unexpectedly accepted')
    except ValueError as e:
        assert str(e)=='ORDINARY_PROJECTION_REPORTER_SOURCE_NOT_PROVEN',str(e)
        old_error=str(e)
    protected={str(p.relative_to(base/'state')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (base/'state').rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in {'current-result.json','completed-check.json'})}
    start=time.monotonic();repeat_stream=io.StringIO()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No compute on repeat')),contextlib.redirect_stdout(repeat_stream):
        repeat_code=main(args)
    repeat_elapsed=time.monotonic()-start
    assert repeat_code==0,repeat_stream.getvalue()
    assert protected=={str(p.relative_to(base/'state')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (base/'state').rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in {'current-result.json','completed-check.json'})}
    start=time.monotonic();read=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','marriott_international','--state-root',str(base/'state'),'--output-root',str(base/'read')],capture_output=True,text=True);read_elapsed=time.monotonic()-start
    assert read.returncode==0,read.stderr
    row=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))[0]
    assert row['value']==value and row['cik']=='1048286',row
    assert list(csv.DictReader((base/'read/metric_evidence.csv').open()))
    rows.append({'metric':metric,'year':year,'args':args,'reused_existing_first_material':reused_first_material,'first_seconds':elapsed,'repeat_seconds':repeat_elapsed,'read_seconds':read_elapsed,'old_error':old_error,'actual_row':row,'case_source_urls':[r['source_url'] for r in case['references']],'result_id':case['results'][metric]['result_id'],'protected_files':protected,'first_report':report,'repeat_report':json.loads(repeat_stream.getvalue()),'read_output':read.stdout})
result={'program_root':str(program),'git_parent':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'uncommitted_at_execution':True,'source_root':str(source),'state_root':str(state),'rows':rows,'calls':{'provider':0,'paid':0,'sec':0},'source_read_only':True,'extra_event_primary_reads':0,'original_partial_resume_state':'/private/var/folders/md/_hc45tnd7_l8yzvhmkhm29j40000gn/T/issue28-event-reporter-58vh_m77','verifier_failure':'original broad state hash included mutable latest-check and new check receipts; final protects only results/current/completed' ,'scope':'actual existing-event source claims -> company CLI -> save -> forbidden repeat -> independent results -> CSV; preserved count semantics, not new content-defined E01'}
Path('docs/evidence/issue28_reporting_cik_20261009/historical-event-company.json').write_text(json.dumps(result,indent=2)+'\n')
