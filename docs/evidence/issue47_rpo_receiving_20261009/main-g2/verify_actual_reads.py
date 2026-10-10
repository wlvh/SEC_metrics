"""Read merged RPO and the actual affected historical event coordinate."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
base=Path(tempfile.mkdtemp(prefix='main-g2-history-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
original_rpo=json.load(open('docs/evidence/issue47_rpo_receiving_20261009/salesforce-fiveyear.json'));original_event=json.load(open('docs/evidence/issue47_rpo_receiving_20261009/event-source-receiving/actual-company.json'));checks=[]
for name,company,reference in [('salesforce-rpo','salesforce',original_rpo),('paramount-event','paramount_skydance_paramount_global',original_event)]:
 state=Path(reference['state_root'])
 def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
 before=hashes();args=['results','--company',company,'--state-root',str(state),'--output-root',str(base/name)]
 code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import company_local
with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch.object(company_local,'run_local',side_effect=AssertionError('No processing')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
 started=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);elapsed=time.monotonic()-started
 assert p.returncode==0 and not p.stderr and before==hashes(),(name,p.returncode,p.stderr)
 rows=list(csv.DictReader((base/name/'metrics_matrix.csv').open()));evidence=list(csv.DictReader((base/name/'metric_evidence.csv').open()));r={'name':name,'seconds':elapsed,'state_root':str(state),'arguments':args,'rows':rows,'all_state_files_unchanged':before,'factory_or_network_calls':0}
 if name=='salesforce-rpo':
  values={int(row['fiscal_year']):row for row in rows if row['metric_id']=='B12' and row['value']};assert set(values)==set(range(2022,2027))
  for year,value in zip(range(2022,2027),['43700000000','48600000000','56900000000','63400000000','72400000000']):
   row=values[year];assert row['value']==value and row['unit']=='USD' and row['period_start']==row['period_end']==str(year)+'-01-31'
  old={r['fiscal_year']:r['result_id'] for r in reference['rows'] if r['metric_id']=='B12' and r['value']};assert all(old[str(y)]==row['result_id'] for y,row in values.items())
  r['five_original_values_ids_and_instant_dates_preserved']=True
 else:
  selected=next(row for row in rows if row['metric_id']=='C01' and row['fiscal_year']=='2021');assert selected['cik']=='813828' and selected['value']=='1' and selected['result_id']==reference['new_result_id'];assert selected['period_start']=='2021-01-01' and selected['period_end']=='2021-12-31'
  hits=[e for e in evidence if e['metric_id']=='C01' and e['period_start']=='2021-01-01' and e['period_end']=='2021-12-31'];assert hits and all(e['cik']=='813828' for e in hits)
  r['selected_affected_row']=selected;r['selected_affected_evidence_rows']=hits
  r['all_other_coordinates_only_read_no_new_reporter_credit']=True
 checks.append(r);print(name,elapsed,len(rows),len(before),flush=True)
record={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'checks':checks,'output_root':str(base),'new_calls':[0,0,0],'old_run_unchanged':True};Path('work/main-g2-consumer/actual-main-reads.json').write_text(json.dumps(record,indent=2)+'\n')
