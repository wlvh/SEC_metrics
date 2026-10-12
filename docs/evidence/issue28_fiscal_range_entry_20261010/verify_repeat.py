"""Actual company replay/read; protect immutable results, not latest reports."""
import csv,hashlib,json,subprocess,sys,time
from pathlib import Path
record=json.loads(Path(__file__).with_name('first-company-cli.json').read_text());state=Path(record['state_root'])
def protected():
 return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()
         and (p.name in {'company-task.json','current-result.json','completed-check.json'}
              or 'results' in p.parts or 'shared-inputs' in p.parts)}
before=protected();dirs=sorted(str(p) for p in state.glob('updates/*/periods/*/results/*/manifest.json'))
prelude="""import sys,runpy,socket,urllib.request
sys.path[:0]=['.','scripts']
def forbidden(*a,**k):raise AssertionError('No discovery or calculation in unchanged repeat')
socket.socket.connect=forbidden;urllib.request.urlopen=forbidden
from vnext import company_fiscal_range as ranges,historical_statement_cases as cases,calculator
ranges.discover_fiscal_range=forbidden
cases.prepare_historical_statement_year_case=forbidden
calculator.calculate_metric=forbidden
calculator.calculate_text_metric=forbidden
sys.argv=['tools/vnext_company.py',*sys.argv[1:]]
runpy.run_path('tools/vnext_company.py',run_name='__main__')
"""
start=time.monotonic();r=subprocess.run([sys.executable,'-B','-c',prelude,*record['arguments']],capture_output=True,text=True);seconds=time.monotonic()-start
report=json.loads(r.stdout);assert not r.stderr
assert r.returncode==2 and report['status']=='FLOW_COMPLETED_WITH_LIMITATIONS'
assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in report['metrics'])
assert before==protected() and dirs==sorted(str(p) for p in state.glob('updates/*/periods/*/results/*/manifest.json'))
out=state.parent/'independent-reader-verified';args=['results','--company','macys','--state-root',str(state),'--output-root',str(out)]
start=time.monotonic();reader=subprocess.run([sys.executable,'-B','tools/vnext_company.py',*args],capture_output=True,text=True);reader_seconds=time.monotonic()-start
view=json.loads(reader.stdout);assert reader.returncode==0 and not reader.stderr
rows=list(csv.DictReader((out/'metrics_matrix.csv').open()))
assert len(rows)==4
assert all(not row['value'] and row['status']=='WITHHELD_KNOWN_DEFECT' for row in rows if row['period_end']=='2024-02-03')
assert before==protected()
result={'first_company_seconds':record['seconds'],'repeat_seconds':seconds,'repeat_exit':r.returncode,'repeat':report,
        'independent_results_seconds':reader_seconds,'read_exit':reader.returncode,'read':view,
        'protected_files':before,'protected_files_preserved':True,'result_directory_count_before_after':len(dirs),
        'csv_rows':rows,'latest_execution_operational_report_is_mutable':True,
        'FY2023_exact_known_defects_held':'B01 5f17 / B02 db60; not resolved by source range',
        'FY2022_scope':'unconfirmed source-scope lead; not diagnosed wrong, not final business acceptance'}
Path(__file__).with_name('repeat-and-read.json').write_text(json.dumps(result,indent=2)+'\n')
print('repeat',r.returncode,seconds,'read',reader.returncode,reader_seconds,'protected',len(before),'resultdirs',len(dirs))
