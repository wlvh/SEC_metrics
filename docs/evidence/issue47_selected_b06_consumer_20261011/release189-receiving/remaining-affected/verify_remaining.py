"""Nine previously failing FY2021 coordinates; real company CLI, no network."""
import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args();root=a.output_root.resolve();root.mkdir(parents=True,exist_ok=False)
source=a.source_root.resolve();watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'];source_hash={x:hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch}
def hashes(state):return {str(x.relative_to(state)):hashlib.sha256(x.read_bytes()).hexdigest() for x in state.rglob('*') if x.is_file()}
def invoke(name,args,guard):
 code="""import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_b06_case as h,current_b06_case as b,calculator
blocked={h.prepare_selected_debt_sources.__code__,h.prepare_selected_debt_input.__code__,b.prepare_selected_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def forbid(f,e,a):
 if e=='call' and f.f_code in blocked:raise AssertionError('Stable repeat/read entered source or calculation')
if sys.argv[2]=='1':sys.setprofile(forbid)
with patch('socket.socket.connect',side_effect=AssertionError('No real network')):raise SystemExit(main(json.loads(sys.argv[1])))
"""
 t=time.perf_counter();r=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args),str(int(guard))],text=True,capture_output=True);d={'arguments':args,'seconds':time.perf_counter()-t,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(root/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n');assert r.returncode in (0,2) and not r.stderr,(name,r.returncode,r.stderr);print(name,round(d['seconds'],3),r.returncode,flush=True);return d,json.loads(r.stdout)
rows=[]
companies=['marriott_international','southwest_airlines','ford_motor_company','pfizer','jpmorgan_chase','salesforce','lumen_technologies','macys','paramount_skydance_paramount_global']
for company in companies:
 state=root/company/'state';args=['run','--company',company,'--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021','--metric','B06','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(root/company/'runs')]
 first,out=invoke(company+'-first',args,False);m=out['metrics'][0];assert len(out['metrics'])==1
 entry={'company':company,'fiscal_year':2021,'first_metric':m,'first_seconds':first['seconds']};after=hashes(state);saved=m.get('result_id') is not None
 if saved:
  protected={x:v for x,v in after.items() if '/results/' in x or x.endswith('completed-check.json') or x=='company-task.json'}
  repeat,rep=invoke(company+'-repeat',args,True);rm=rep['metrics'][0];assert not rm['calculation_performed'] and not rm['new_candidate_created'] and rm['result_id']==m['result_id'];assert all(hashes(state).get(x)==v for x,v in protected.items());entry.update(repeat_seconds=repeat['seconds'],repeat_metric=rm,protected_file_count=len(protected))
 else:entry['repeat_not_run']='Execution failures are not stable completed checks; do not demand zero processing for an unresolved failure.'
 before=hashes(state);read,view=invoke(company+'-read',['results','--company',company,'--state-root',str(state),'--output-root',str(root/company/'read')],True);assert hashes(state)==before;csvrows=list(csv.DictReader((root/company/'read/metrics_matrix.csv').open()));assert len(csvrows)==1;entry.update(read_seconds=read['seconds'],read_state_files=len(before),row=csvrows[0]);rows.append(entry)
 (root/'summary.json').write_text(json.dumps({'code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'scope':'Nine existing FY2021 formerly default-DEI failures, not all50 B06','rows':rows,'source_metadata_hashes':source_hash,'calls':[0,0,0]},indent=2)+'\n')
assert source_hash=={x:hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch}
print('Nine affected coordinates processed; exact remaining failures retained',flush=True)
