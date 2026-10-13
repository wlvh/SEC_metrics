"""Targeted consumer check; run only after the public scope repair is committed."""
import argparse,csv,hashlib,json,subprocess,sys,tempfile,time
from decimal import Decimal
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--source-root',required=True,type=Path);parser.add_argument('--output-root',required=True,type=Path);a=parser.parse_args()
base=a.output_root.resolve();base.mkdir(parents=True,exist_ok=False);state=base/'state';records=[]
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
def invoke(name,args,forbid=False):
 code='import sys,json\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import historical_statement_cases as h,company_fiscal_range as f,calculator\nblocked={h.prepare_historical_statement_year_case.__code__,f.discover_fiscal_range.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}\ndef guard(frame,event,arg):\n if event=="call" and frame.f_code in blocked:raise AssertionError("Stable repeat/read must not discover or calculate")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("Saved-source check must not network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-t,'exit':p.returncode,'arguments':args,'stdout':p.stdout,'stderr':p.stderr};records.append(r);(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,round(r['seconds'],3),p.returncode,flush=True);assert p.returncode==0 and not p.stderr,r;return json.loads(p.stdout)
args=['run','--company','lumen_technologies','--period','fiscal-years','--fiscal-year-start','2022','--fiscal-year-end','2022','--metric','B01','--metric','B02','--source-root',str(a.source_root.resolve()),'--work-dir',str(state),'--output-dir',str(base/'runs')]
first=invoke('fresh-B01-B02',args)
assert all(m['status']=='CANDIDATE_READY' for m in first['metrics']),first
protected={p:h for p,h in hashes().items() if '/results/' in p}
repeat=invoke('forbidden-repeat',args,True);assert all(not m['calculation_performed'] and not m['new_candidate_created'] for m in repeat['metrics'])
assert all(hashes().get(p)==h for p,h in protected.items())
before=hashes();read=base/'read';invoke('independent-read',['results','--company','lumen_technologies','--state-root',str(state),'--output-root',str(read)],True);assert before==hashes()
rows=list(csv.DictReader((read/'metrics_matrix.csv').open()));b01=next(x for x in rows if x['metric_id']=='B01');b02=next(x for x in rows if x['metric_id']=='B02')
assert Decimal(b01['value'])==Decimal('17478000000') and b01['unit']=='USD'
assert Decimal(b02['value'])==(Decimal('17478000000')-Decimal('19687000000'))/Decimal('19687000000') and b02['unit']=='ratio'
assert all(x['fiscal_year']=='2022' and x['period_start']=='2022-01-01' and x['period_end']=='2022-12-31' for x in rows)
assessments=[]
for path in state.rglob('input-assessments.json'):
 data=json.loads(path.read_text());assessments.append({'path':str(path),'data':data})
receipt={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'records':records,'rows':rows,'read_state_files_unchanged':len(before),'protected_results':len(protected),'assessments':assessments,'new_calls':[0,0,0]}
(base/'summary.json').write_text(json.dumps(receipt,indent=2)+'\n');print('Fresh/repeat/read complete; total 17478m vs original prior 19687m, not contract subtotal16108m')
