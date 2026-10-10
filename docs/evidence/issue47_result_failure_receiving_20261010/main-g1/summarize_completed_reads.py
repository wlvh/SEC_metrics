"""Inspect already written real main reads, without repeating the CLI."""
import csv,hashlib,json,subprocess
from pathlib import Path
from vnext.company_current_records import _defects,_registry
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/main-g1-history-read-ua7tfv6o');states={'paramount-failed':'d01-paramount-selected-20261010','salesforce-missing':'fiscal-range-salesforce-20261010','pfizer-defect':'pfizer-statements-company-nvw2pcdt'};checks=[]
for name,state_name in states.items():
 rows=list(csv.DictReader((base/name/'metrics_matrix.csv').open()));view=json.loads((base/name/'company-results.json').read_text());checks.append({'name':name,'rows':rows,'view':view,'state_root':str(base.parent/state_name/'state')})
 if name=='paramount-failed':assert view['metrics'][0]['reason']=='HISTORICAL_RISK_HEADINGS_AMENDMENT_NOT_RECEIVED' and view['metrics'][0]['error_category']=='IMPLEMENTATION_GAP'
 elif name=='salesforce-missing':assert {r['fiscal_year']:r['value'] for r in rows}=={'2026':'41525000000','2027':''}
 else:
  good=next(r for r in rows if r['metric_id']=='B01' and r['fiscal_year']=='2023');assert good['value']=='58496000000' and good['status']=='OK' and json.loads(good['defect_holds'])==[]
  old_state=base.parent/state_name/'state';oldpath=old_state/'updates/B01/periods/FY2023/results/f163b5dac27e4ad69abb9661b52123a1/records.jsonl';records=[json.loads(l) for l in oldpath.read_text().splitlines()];old=next(r for r in records if r['record_type']=='METRIC_RESULT');assert old['value']=='50914000000'
  assert 'ISSUE47_PFIZER_2023_REVENUE_COMPONENT_IS_NOT_TOTAL' in _defects(old,_registry());checks[-1]['old_subtotal_id']=old['result_id'];checks[-1]['old_saved_value_preserved']=old['value'];checks[-1]['old_subtotal_hold_applies_only_to_old_id']=True
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'read_output_root':str(base),'actual_main_reads_completed_before_summary':True,'summary_only_no_reexecution':True,'checks':checks,'calls':[0,0,0]};Path('work/main-g1-consumer/actual-main-reads-summary.json').write_text(json.dumps(r,indent=2)+'\n');print('Saved main reads verified; old subtotal held, new correct total retained')
