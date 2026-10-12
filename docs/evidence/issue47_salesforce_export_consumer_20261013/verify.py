"""Noncalendar historical consumer of the existing saved-source company export."""
import argparse,contextlib,csv,hashlib,io,json,socket,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as cases,calculator
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root',type=Path,required=True)
parser.add_argument('--output-root',type=Path,required=True)
options=parser.parse_args()
source=options.source_root.resolve();work=options.output_root.resolve()
assert source.is_dir() and not work.exists()
work.mkdir(parents=True)
watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'];original={x:hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch}
def files(root):return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def invoke(name,args,forbidden=False):
 blocked={cases.prepare_historical_statement_year_case.__code__,cases._prepare_historical_statement_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
 def guard(frame,event,arg):
  if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
 prior=sys.getprofile();start=time.perf_counter()
 try:
  if forbidden:sys.setprofile(guard)
  with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),contextlib.redirect_stdout(io.StringIO()) as stream:code=main(args)
 finally:sys.setprofile(prior)
 data={'seconds':time.perf_counter()-start,'exit_code':code,'arguments':args,'stdout':stream.getvalue()};(work/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n');print(name,round(data['seconds'],3),code,flush=True);assert code==0,data;return json.loads(data['stdout']),data
export,export_record=invoke('export',['export','--company','salesforce','--metric','B01','--history-years','5','--source-root',str(source),'--output-root',str(work/'package')]);assert export['status']=='EXPORTED';assert export['source_discovery']['fiscal_range']['fiscal_years']==[2022,2023,2024,2025,2026]
for relative in export['files']:assert (work/'package'/relative).read_bytes()==(source/relative).read_bytes(),relative
args=['run','--company','salesforce','--metric','B01','--period','fiscal-years','--fiscal-year-start','2026','--fiscal-year-end','2026','--source-root',str(work/'package'),'--work-dir',str(work/'state'),'--output-dir',str(work/'first')]
first,first_record=invoke('first',args);m=first['metrics'][0];assert m['calculation_performed'] and m['new_candidate_created'];saved={k:v for k,v in files(work/'state').items() if '/results/' in k};folders=sorted(str(p) for p in (work/'state').glob('updates/B01/periods/*/results/*'))
repeat,repeat_record=invoke('repeat-forbidden',args[:-1]+[str(work/'repeat')],True);r=repeat['metrics'][0];assert not r['calculation_performed'] and not r['new_candidate_created'];assert r['result_id']==m['result_id'];assert saved=={k:v for k,v in files(work/'state').items() if '/results/' in k};assert folders==sorted(str(p) for p in (work/'state').glob('updates/B01/periods/*/results/*'))
before=files(work/'state');start=time.perf_counter();child=subprocess.run([sys.executable,'-B','tools/vnext_company.py','results','--company','salesforce','--state-root',str(work/'state'),'--output-root',str(work/'read')],capture_output=True,text=True);elapsed=time.perf_counter()-start;assert child.returncode==0 and not child.stderr;assert files(work/'state')==before
read_record={'seconds':elapsed,'exit_code':0,'stdout':child.stdout,'state_files_preserved':len(before)};(work/'read.json').write_text(json.dumps(read_record,indent=2)+'\n');rows=list(csv.DictReader((work/'read/metrics_matrix.csv').open(encoding='utf-8-sig')));assert len(rows)==1;row=rows[0];assert (row['fiscal_year'],row['period_start'],row['period_end'],row['value'],row['unit'])==('2026','2025-02-01','2026-01-31','41525000000','USD'),row
assert original=={x:hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch}
summary={'code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'export':{'seconds':export_record['seconds'],'fiscal_years':export['source_discovery']['fiscal_range']['fiscal_years'],'files':len(export['files']),'package_id':export['package_id'],'copied_originals_equal':True},'first':{'seconds':first_record['seconds'],'calculation_performed':True},'repeat':{'seconds':repeat_record['seconds'],'calculation_forbidden':True,'result_files_preserved':len(saved)},'read':read_record,'row':row,'source_hashes':original,'new_calls':[0,0,0],'limits':['One B01 FY2026 calculated; original five-year pilot and other metrics not replayed.','Saved-source export is not online discovery/completion.']};(work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'value':row['value'],'fy':row['fiscal_year'],'actual_dates':[row['period_start'],row['period_end']],'result_id':row['result_id']}))
