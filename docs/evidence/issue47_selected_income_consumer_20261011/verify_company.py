import json,csv,time,sys,subprocess,hashlib,argparse
from pathlib import Path
from decimal import Decimal
p=argparse.ArgumentParser();p.add_argument('--output-root',required=True,type=Path);p.add_argument('--source-root',required=True,type=Path);a=p.parse_args();base=a.output_root.resolve();base.mkdir(parents=True,exist_ok=False);state=base/'state'
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
def invoke(name,args,forbid=False):
 code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import historical_b03_case as h, selected_income_calculation as s, calculator\n'
  code+='blocked={h.prepare_historical_income_year_case.__code__,h.prepare_selected_income_sources.__code__,s.calculate_selected_income.__code__,calculator.calculate_metric.__code__}\ndef guard(frame,event,arg):\n if event=="call" and frame.f_code in blocked:raise AssertionError("forbidden processing")\nsys.setprofile(guard)\n'
  code+='with patch("socket.socket.connect",side_effect=AssertionError("offline")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 else:code+='with patch("socket.socket.connect",side_effect=AssertionError("offline")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 t=time.monotonic();r=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],text=True,capture_output=True);v={'seconds':time.monotonic()-t,'exit':r.returncode,'args':args,'stdout':r.stdout,'stderr':r.stderr};(base/(name+'.json')).write_text(json.dumps(v,indent=2)+'\n');print(name,round(v['seconds'],3),r.returncode,flush=True);assert r.returncode==0 and not r.stderr,v;return json.loads(r.stdout)
args=['run','--company','marriott_international','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2024','--metric','B03','--source-root',str(a.source_root.resolve()),'--work-dir',str(state),'--output-dir',str(base/'runs')]
first=invoke('fresh',args)
assert first['metrics'][0]['status']=='CANDIDATE_READY',first
old={p:h for p,h in hashes().items() if '/results/' in p};rep=invoke('forbidden-repeat',args,True);assert all(not m['calculation_performed'] and not m['new_candidate_created'] for m in rep['metrics']);assert all(hashes().get(p)==h for p,h in old.items())
before=hashes()
read=base/('read-'+str(time.time_ns()));invoke('independent-read',['results','--company','marriott_international','--state-root',str(state),'--output-root',str(read)],True);assert before==hashes()
rows=list(csv.DictReader((read/'metrics_matrix.csv').open()));row=next(r for r in rows if r['metric_id']=='B03');assert Decimal(row['value'])==Decimal('0.1653386454183266932270916335') and row['unit']=='ratio' and row['fiscal_year']=='2024',row
(base/'summary.json').write_text(json.dumps({'rows':rows,'preserved_state_files':len(old),'new_calls':[0,0,0]},indent=2)+'\n')
