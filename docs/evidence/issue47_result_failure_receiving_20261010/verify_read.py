"""Consume the shared reader against existing real historical task states."""
import csv,hashlib,json,subprocess,sys,time,tempfile
from pathlib import Path
base=Path(tempfile.mkdtemp(prefix='history-failure-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
scenes=[('d01','paramount_skydance_paramount_global',Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/d01-paramount-selected-20261010/state')),
        ('range','salesforce',Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/fiscal-range-salesforce-20261010/state'))]
receipts=[]
for name,company,state in scenes:
    before={str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
    args=['results','--company',company,'--state-root',str(state),'--output-root',str(base/name)]
    code="""import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import company_local,company_current_records
with patch('socket.socket.connect',side_effect=AssertionError('No HTTP')),patch.object(company_local,'run_local',side_effect=AssertionError('Read must not run')),patch.object(company_current_records,'run_saved_company',side_effect=AssertionError('No calculations')):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
    start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True)
    elapsed=time.monotonic()-start
    assert p.returncode==0 and not p.stderr,(p.stdout,p.stderr)
    view=json.loads(p.stdout);rows=list(csv.DictReader((base/name/'metrics_matrix.csv').open()))
    if name=='d01':
        item=view['metrics'][0];assert item['reason']=='HISTORICAL_RISK_HEADINGS_AMENDMENT_NOT_RECEIVED'
        assert item['error_category']=='IMPLEMENTATION_GAP' and item['error_type']=='RiskHeadingCaseError'
        assert item['fiscal_year']==2025 and item['value'] is None
        assert 'AMENDMENT_NOT_RECEIVED' in rows[0]['notes'] and 'IMPLEMENTATION_GAP' in rows[0]['notes']
    else:
        by_year={item['fiscal_year']:item for item in view['metrics']}
        assert by_year[2026]['value']=='41525000000'
        assert by_year[2027]['value'] is None and 'FISCAL_YEAR_MISSING_OR_AMBIGUOUS' in by_year[2027]['reason']
        assert by_year[2027]['error_type']=='ValueError'
        failed=next(row for row in rows if row['fiscal_year']=='2027')
        assert 'FISCAL_YEAR_MISSING_OR_AMBIGUOUS' in failed['notes']
    assert before=={str(q.relative_to(state)):hashlib.sha256(q.read_bytes()).hexdigest() for q in state.rglob('*') if q.is_file()}
    receipts.append({'scene':name,'company_id':company,'state_root':str(state),'seconds':elapsed,'exit_code':p.returncode,
                     'arguments':args,'view':view,'csv_rows':rows,'protected_files':before,'all_state_preserved':True,
                     'source_or_calculation_calls':0})
record={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'receipts':receipts,'new_calls':[0,0,0]}
Path('work/result-failure-consumer/actual-read.json').write_text(json.dumps(record,indent=2)+'\n')
print([(r['scene'],round(r['seconds'],3),len(r['protected_files'])) for r in receipts])
