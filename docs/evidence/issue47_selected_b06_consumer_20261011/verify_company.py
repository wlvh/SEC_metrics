import argparse,csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
from decimal import Decimal
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output-root',type=Path,required=True);args=parser.parse_args()
source=args.source_root.resolve();base=args.output_root.resolve();base.mkdir(parents=True,exist_ok=False)
records=[]
def digest(state):return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
def invoke(name,args,forbid=False):
 code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import historical_b06_case as h,current_b06_case as b,calculator\nblocked={h.prepare_selected_debt_sources.__code__,b.prepare_selected_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}\ndef guard(frame,event,arg):\n if event=="call" and frame.f_code in blocked:raise AssertionError("Unchanged/read must not prepare or compute")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No real network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-t,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'arguments':args};records.append(r);(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,round(r['seconds'],3),p.returncode,flush=True);assert not p.stderr and p.returncode in (0,2),r;return json.loads(p.stdout)
summary=[]
for company,year in [('enphase_energy',2024),('marriott_international',2024)]:
 state=base/company/'state';out=base/company/'runs'
 args=['run','--company',company,'--period','fiscal-years','--fiscal-year-start',str(year),'--fiscal-year-end',str(year),'--metric','B06','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out)]
 first=invoke(company+'-first',args);m=first['metrics'][0]
 assert m['status']=='CANDIDATE_READY',m
 protected={p:h for p,h in digest(state).items() if '/results/' in p or '/shared-inputs/' in p or p.endswith(('current-result.json','completed-check.json')) or p=='company-task.json'}
 repeat=invoke(company+'-repeat',args,True);assert not repeat['metrics'][0]['calculation_performed'] and not repeat['metrics'][0]['new_candidate_created']
 assert all(digest(state).get(p)==h for p,h in protected.items())
 before=digest(state);read=base/company/'read';invoke(company+'-read',['results','--company',company,'--state-root',str(state),'--output-root',str(read)],True);assert before==digest(state)
 rows=list(csv.DictReader((read/'metrics_matrix.csv').open()));assert len(rows)==1;row=rows[0]
 assert row['fiscal_year']==str(year) and row['period_start']==row['period_end']=='2024-12-31'
 if company=='enphase_energy':assert Decimal(row['value'])==Decimal('1302380000')/Decimal('833016000') and row['unit']=='ratio',row
 else:assert not row['value'] and 'NOT_MEANINGFUL' in row['status'],row
 summary.append({'company_id':company,'state_root':str(state),'row':row,'protected':protected,'read_state_files_unchanged':len(before)})
(base/'receipt.json').write_text(json.dumps({'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'base':str(base),'records':records,'companies':summary,'new_calls':[0,0,0]},indent=2)+'\n');print('selected positive and real nonpositive-equity state complete',flush=True)
