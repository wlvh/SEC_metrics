from pathlib import Path
import csv,json,subprocess,sys,tempfile,time,hashlib
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/d01-paramount-selected-20261010/state')
base=Path(tempfile.mkdtemp(prefix='issue28-read-error-')).resolve()
before={str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
started=time.monotonic()
# Only an independent saved-results reader is invoked; it neither prepares
# sources nor enters a metric producer. The source/controller stay untouched.
r=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','paramount_skydance_paramount_global','--state-root',str(state),'--output-root',str(base/'read')],capture_output=True,text=True)
elapsed=time.monotonic()-started
assert r.returncode==0,r.stderr
view=json.loads((base/'read/company-results.json').read_text());row=next(m for m in view['metrics'] if m['metric_id']=='D01')
assert row['reason'].startswith('HISTORICAL_RISK_HEADINGS_AMENDMENT_NOT_RECEIVED'),row
assert row['error_category']=='IMPLEMENTATION_GAP' and row['value'] is None,row
csvrow=next(m for m in csv.DictReader((base/'read/metrics_matrix.csv').open()) if m['metric_id']=='D01')
assert row['reason'] in csvrow['notes'] and 'IMPLEMENTATION_GAP' in csvrow['notes'],csvrow
assert csvrow['value']=='' and csvrow['fiscal_year']=='2025',csvrow
assert before=={str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
Path('docs/evidence/issue28_result_failure_details_20261010/actual-failed-read.json').write_text(json.dumps({'program_root':str(Path.cwd()),'state_root':str(state),'output_root':str(base/'read'),'seconds':elapsed,'returncode':r.returncode,'row':row,'csv_row':csvrow,'protected_state_files':before,'state_bytes_unchanged':True,'calls':[0,0,0],'scope':'independent read only; no source/metric preparation, old result or business conclusion changed'},indent=2)+'\n')
print('D01 FY2025',row['reason'],row['error_category'],elapsed,'protected',len(before))
