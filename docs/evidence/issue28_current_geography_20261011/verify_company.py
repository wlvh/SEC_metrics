"""Formal latest A13 paths, forbidden-calculation reuse and independent reading."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update

ROOT=Path.cwd();E=Path(__file__).parent
old=json.loads((E/'first.json').read_text())
SOURCE=Path(old['report']['source_root'])
def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}
def run(args,forbid=False):
    output=io.StringIO();start=time.perf_counter()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',output):
        if forbid:
            with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated calculation')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No new result write')):
                code=main(args)
        else:code=main(args)
    return code,json.loads(output.getvalue()),time.perf_counter()-start

source_hashes={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest()
               for p in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')}
reports=[]
for company in ('jpmorgan_chase','marriott_international','salesforce'):
    base=Path(tempfile.mkdtemp(prefix='issue28-a13-'+company+'-'))
    args=['run','--company',company,'--source-root',str(SOURCE),'--metric','A13',
          '--work-dir',str(base/'state'),'--output-dir',str(base/'out')]
    first_code,first,first_seconds=run(args)
    metric=first['metrics'][0];assert first_code==0 and metric['status']=='CANDIDATE_READY',first
    record=Path(metric['result_root']);before=snapshot(record)
    code,repeated,repeat_seconds=run(args,True)
    assert code==0 and repeated['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE',repeated
    assert repeated['metrics'][0]['result_id']==metric['result_id'] and before==snapshot(record)
    state_before=snapshot(base/'state');start=time.perf_counter()
    command='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network"));sys.argv='+repr(['tools/vnext_company.py','results','--company',company,'--state-root',str(base/'state'),'--output-root',str(base/'read')])+';runpy.run_path("tools/vnext_company.py",run_name="__main__")'
    read=subprocess.run([sys.executable,'-c',command],cwd=ROOT,capture_output=True,text=True)
    read_seconds=time.perf_counter()-start
    assert read.returncode==0,read.stderr
    assert state_before==snapshot(base/'state')
    row=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))[0]
    if company=='jpmorgan_chase':
        assert row['value']=='42758000000' and row['unit']=='USD',row
        assert row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
    else:
        assert row['value']=='' and row['status']=='N_A_STRUCTURAL',row
    if company=='salesforce':
        assert row['fiscal_year']=='2026' and row['period_start']=='2025-02-01' and row['period_end']=='2026-01-31',row
    result={'company':company,'args':args,'first':first,'first_seconds':first_seconds,
            'repeat':repeated,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,'csv':row,
            'record_files_unchanged':True,'read_state_unchanged':True,'new_calls':[0,0,0]}
    reports.append(result)
    (E/'actual-company.json').write_text(json.dumps({'code_root':str(ROOT),'source_root':str(SOURCE),
        'source_hashes':source_hashes,'results':reports},indent=2)+'\n')
    print(company,row['value'],row['status'],round(first_seconds,3),round(repeat_seconds,3),round(read_seconds,3),flush=True)
assert source_hashes=={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in source_hashes}
print('PASS_ACTUAL_CURRENT_A13_FIRST_REPEAT_INDEPENDENT_READ',flush=True)
