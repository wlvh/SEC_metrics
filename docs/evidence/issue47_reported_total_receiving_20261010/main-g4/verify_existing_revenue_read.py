"""Only actual main result reading; no reprocessing for documentation or integration."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
states=[('macys','/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/statement-pilot-macys-20261009/state'),('pfizer','/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/pfizer-statements-company-nvw2pcdt/state')]
base=Path(tempfile.mkdtemp(prefix='main-g4-revenue-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'));checks=[]
for company,path in states:
 state=Path(path)
 def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
 before=hashes();args=['results','--company',company,'--state-root',str(state),'--output-root',str(base/company)]
 code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import company_local
with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch.object(company_local,'run_local',side_effect=AssertionError('Read must not calculate or select sources')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
 start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);elapsed=time.monotonic()-start;assert p.returncode==0 and not p.stderr and before==hashes()
 rows=list(csv.DictReader((base/company/'metrics_matrix.csv').open()));year='2023';b01=next(r for r in rows if r['metric_id']=='B01' and r['fiscal_year']==year);b02=next(r for r in rows if r['metric_id']=='B02' and r['fiscal_year']==year)
 assert b01['value']==('23866000000' if company=='macys' else '58496000000') and b01['unit']=='USD'
 if company=='macys':assert b01['period_start']=='2023-01-29' and b01['period_end']=='2024-02-03' and not b02['value'] and b02['status']=='WITHHELD_KNOWN_DEFECT'
 else:assert b01['period_start']=='2023-01-01' and b01['period_end']=='2023-12-31';assert b02['value']=='-0.4169640187381640586065982259'
 checks.append({'company_id':company,'seconds':elapsed,'arguments':args,'state_root':str(state),'all_state_files_unchanged':len(before),'B01':b01,'B02':b02,'row_count':len(rows),'max_existing_csv_field_chars':max(len(v) for r in rows for v in r.values())});print(company,elapsed,len(before),len(rows),flush=True)
record={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'checks':checks,'new_calls':[0,0,0],'factory_calls':0,'pfizer_B02_new_single_line_result_still_development_no_adoption':True,'main_does_not_grant_saved_candidate_new_source_review_credit':True};Path('work/main-g4-consumer/existing-revenue-read.json').write_text(json.dumps(record,indent=2)+'\n')
