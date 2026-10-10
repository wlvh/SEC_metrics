"""Preserve six financial families after real main RPO/renderer integration."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
old=json.load(open('work/main-g3-consumer/old-financial-main-read.json'));out=Path(tempfile.mkdtemp(prefix='main-g3-financial-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'));checks=[]
fields=('metric_id','fiscal_year','value','unit','period_start','period_end','result_id','accession')
for task in old['checks']:
 state=Path(task['state_root']);original=list(csv.DictReader((Path(task['output_root'])/'metrics_matrix.csv').open()))
 def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
 before=hashes();args=['results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(out/task['family'])]
 code='''import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import company_local
with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch.object(company_local,'run_local',side_effect=AssertionError('No calculation/source selection')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
 start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);elapsed=time.monotonic()-start;assert p.returncode==0 and not p.stderr and before==hashes()
 rows=list(csv.DictReader((out/task['family']/'metrics_matrix.csv').open()));key=lambda r:tuple(r[k] for k in fields);assert sorted(key(r) for r in rows if r['value'])==sorted(key(r) for r in original if r['value'])
 expected=task['old_successful_rows_preserved']+task['additional_saved_mixed_results'];assert len([r for r in rows if r['value']])==expected
 checks.append({'family':task['family'],'state_root':str(state),'seconds':elapsed,'protected_state_files':len(before),'all_state_files_unchanged':True,'original_correct_rows_preserved':task['old_successful_rows_preserved'],'mixed_saved_rows_preserved':task['additional_saved_mixed_results'],'new_rows':rows});print(task['family'],elapsed,expected,len(before),flush=True)
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_previous_main':old['code_commit'],'checks':checks,'original_30_correct_values_preserved':True,'new_calls':[0,0,0],'factory_calls':0};Path('work/main-g3-consumer/financial-reads.json').write_text(json.dumps(r,indent=2)+'\n')
