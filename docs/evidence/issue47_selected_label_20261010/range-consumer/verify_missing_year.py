"""A genuinely unavailable year must not erase the saved adjacent year."""
import csv, hashlib, json, subprocess, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent
first = json.loads((here/'first-salesforce.json').read_text())
state = Path(first['state_root'])
def protected():
    return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in state.rglob('*') if p.is_file() and
            (p.name in {'company-task.json','current-result.json','completed-check.json'}
             or 'results' in p.parts or 'shared-inputs' in p.parts)}
before = protected()
args = list(first['arguments']);args[args.index('--fiscal-year-end')+1]='2027'
prelude = """import sys,runpy,socket,urllib.request
sys.path[:0]=['.','scripts','tools']
def forbidden(*a,**k):raise AssertionError('No HTTP, successful year factory or calculation')
socket.socket.connect=forbidden;urllib.request.urlopen=forbidden
from vnext import historical_statement_cases as cases,calculator
cases.prepare_historical_statement_year_case=forbidden
calculator.calculate_metric=forbidden;calculator.calculate_text_metric=forbidden
sys.argv=['tools/vnext_company.py',*sys.argv[1:]]
runpy.run_path('tools/vnext_company.py',run_name='__main__')
"""
start=time.monotonic()
p=subprocess.run([sys.executable,'-B','-c',prelude,*args],capture_output=True,text=True)
elapsed=time.monotonic()-start
record={'seconds':elapsed,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'arguments':args}
(here/'missing-year-raw.json').write_text(json.dumps(record,indent=2)+'\n')
assert p.returncode==2 and not p.stderr, record
report=json.loads(p.stdout)
by_year={m['requested_fiscal_year']:m for m in report['metrics']}
assert by_year[2026]['status']=='NO_SOURCE_CONTENT_CHANGE'
assert not by_year[2026]['calculation_performed']
assert by_year[2027]['status']=='INPUT_OR_EXECUTION_FAILED'
assert 'FISCAL_YEAR_MISSING_OR_AMBIGUOUS' in by_year[2027]['reason']
assert all(protected().get(k)==v for k,v in before.items())
out=state.parent/'missing-year-independent-read'
start=time.monotonic()
q=subprocess.run([sys.executable,'-B','tools/vnext_company.py','results','--company','salesforce',
                  '--state-root',str(state),'--output-root',str(out)],capture_output=True,text=True)
read_seconds=time.monotonic()-start
assert q.returncode==0 and not q.stderr
rows=list(csv.DictReader((out/'metrics_matrix.csv').open()))
by_year={r['fiscal_year']:r for r in rows}
assert by_year['2026']['value']=='41525000000'
assert by_year['2027']['value']=='' and by_year['2027']['result_validity']=='NO_CURRENT_RESULT'
assert all(protected().get(k)==v for k,v in before.items())
(here/'missing-year.json').write_text(json.dumps({**record,'independent_read_seconds':read_seconds,
    'independent_read_stdout':q.stdout,'rows':rows,'old_files_preserved':before,
    'saved_FY2026_preparation_or_calculation_calls':0,'new_calls':[0,0,0]},indent=2)+'\n')
print('Missing FY2027:',elapsed,'read:',read_seconds,'FY2026 unchanged:',len(before))
