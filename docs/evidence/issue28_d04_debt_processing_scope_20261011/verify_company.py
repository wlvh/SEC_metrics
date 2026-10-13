"""Real complete saved D04; unrelated debt edit must not replay or rewrite it."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update
from vnext.continuous_call_ledger import CallLedger
ROOT=Path.cwd();E=Path(__file__).parent
LEDGER=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE=LEDGER/'source-inputs';base=Path(tempfile.mkdtemp(prefix='issue28-d04-debt-version-'))
def hashes(paths):return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def snapshot(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
protected=[LEDGER/'binding.json',LEDGER/'claims.jsonl',SOURCE/'config/company_registry.csv',
           SOURCE/'evidence/requests_log.csv',SOURCE/'evidence/requests_log_manifest.json']
protected += [p for ordinal in range(115,119) for p in (LEDGER/'calls'/('%04d'%ordinal)).rglob('*') if p.is_file()]
original=hashes(protected)
args=['run','--company','marriott_international','--source-root',str(SOURCE),'--metric','D04',
      '--work-dir',str(base/'state'),'--output-dir',str(base/'out')]
out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(CallLedger,'claim',side_effect=AssertionError('No new ledger claim')),patch('sys.stdout',out):code=main(args)
first=json.loads(out.getvalue());first_seconds=time.perf_counter()-start
assert first['metrics'][0]['status']=='CANDIDATE_WITHHELD',first
record=Path(first['metrics'][0]['result_root']);old_result=snapshot(record)
debt=ROOT/'scripts/vnext/b06_note_carrying.py';debt_bytes=debt.read_bytes()
try:
    debt.write_bytes(debt_bytes+b'\n# ISOLATED_TEST_UNUSED_DEBT_VERSION\n')
    out=io.StringIO();start=time.perf_counter()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(CallLedger,'claim',side_effect=AssertionError('No new ledger claim')),patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated D04 preparation or saved-response replay')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No new D04 result')),patch('sys.stdout',out):code=main(args)
    repeat=json.loads(out.getvalue());repeat_seconds=time.perf_counter()-start
    assert repeat['metrics'][0]['status']=='PREVIOUS_INPUT_WITHHELD',repeat
    assert repeat['metrics'][0]['result_id']==first['metrics'][0]['result_id']
    assert snapshot(record)==old_result
finally:debt.write_bytes(debt_bytes)
assert debt.read_bytes()==debt_bytes
state_before=snapshot(base/'state');start=time.perf_counter()
command='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network"));sys.argv='+repr(['tools/vnext_company.py','results','--company','marriott_international','--state-root',str(base/'state'),'--output-root',str(base/'read')])+';runpy.run_path("tools/vnext_company.py",run_name="__main__")'
read=subprocess.run([sys.executable,'-c',command],cwd=ROOT,capture_output=True,text=True);read_seconds=time.perf_counter()-start
assert read.returncode==0,read.stderr
assert snapshot(base/'state')==state_before and hashes(protected)==original
row=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))[0]
assert row['value']=='' and row['status']=='TEXT_QUAL' and row['fiscal_year']=='2025',row
assert row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
(E/'actual-company.json').write_text(json.dumps({'args':args,'first':first,'first_seconds':first_seconds,
 'repeat':repeat,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,'csv':row,
 'protected_source_ledger_response_hashes':original,'old_result_files_unchanged':True,
 'read_state_unchanged':True,'new_calls':[0,0,0],
 'scope':'Existing115-118 complete real responses/current semantic checks. Defined-scope absence remainsWITHHELD/publicTEXT_QUAL, no financial-health guarantee'},indent=2)+'\n')
print('PASS_REAL_D04_UNUSED_DEBT_EDIT_REUSE',first_seconds,repeat_seconds,read_seconds,first['metrics'][0]['result_id'],flush=True)
