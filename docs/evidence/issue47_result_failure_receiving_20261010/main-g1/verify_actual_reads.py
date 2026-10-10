"""Read-only consumer of the actually merged public failures/defect changes."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
BASE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence');output=Path(tempfile.mkdtemp(prefix='main-g1-history-read-',dir=BASE));checks=[]
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
for name,company,path in [('paramount-failed','paramount_skydance_paramount_global','d01-paramount-selected-20261010'),('salesforce-missing','salesforce','fiscal-range-salesforce-20261010'),('pfizer-defect','pfizer','pfizer-statements-company-nvw2pcdt')]:
 state=BASE/path/'state';before=hashes(state);args=['results','--company',company,'--state-root',str(state),'--output-root',str(output/name)]
 code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import company_local
with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch.object(company_local,'run_local',side_effect=AssertionError('No calculation/source selection')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
 start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);seconds=time.monotonic()-start
 assert p.returncode==0 and not p.stderr and before==hashes(state),(name,p.returncode,p.stderr)
 view=json.loads(p.stdout);rows=list(csv.DictReader((output/name/'metrics_matrix.csv').open()));check={'name':name,'company_id':company,'state_root':str(state),'seconds':seconds,'arguments':args,'rows':rows,'view':view,'protected_files':before,'all_state_files_unchanged':True}
 if name=='paramount-failed':
  row=rows[0];metric=view['metrics'][0];assert len(rows)==1 and not row['value'] and row['fiscal_year']=='2025';assert metric['reason']=='HISTORICAL_RISK_HEADINGS_AMENDMENT_NOT_RECEIVED' and metric['error_category']=='IMPLEMENTATION_GAP';assert 'AMENDMENT_NOT_RECEIVED' in row['notes']
 elif name=='salesforce-missing':
  good=next(r for r in rows if r['fiscal_year']=='2026');failed=next(r for r in rows if r['fiscal_year']=='2027');assert good['value']=='41525000000' and good['period_start']=='2025-02-01' and good['period_end']=='2026-01-31';assert not failed['value'] and 'FISCAL_YEAR_MISSING_OR_AMBIGUOUS' in failed['notes']
 else:
  good=next(r for r in rows if r['metric_id']=='B01' and r['fiscal_year']=='2023');assert good['value']=='58496000000' and good['status']=='OK' and not json.loads(good['defect_holds']);assert good['result_id']=='sha256:128c170a19b5505f3ce22e837aaea836159b4652e334aa4b5bdf298e007786da';assert len(rows)==25
 checks.append(check);print(name,seconds,len(rows),len(before),flush=True)
result={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'actual_main_base':'6c57ddc22daa3a9f31da20d8294e52e3d54990d0','checks':checks,'new_calls':[0,0,0],'calculation_or_source_selection_calls':0};Path('work/main-g1-consumer/actual-main-reads.json').write_text(json.dumps(result,indent=2)+'\n')
