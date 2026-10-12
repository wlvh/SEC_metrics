"""One actual historical B02 consumes the ordinary saved-source export, offline."""
import argparse,contextlib,csv,hashlib,io,json,socket,subprocess,sys,time
from decimal import Decimal,localcontext
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as cases,historical_paired_revenue as paired,calculator

def hashes(root):
 return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def verify(source,work):
 work.mkdir(parents=True,exist_ok=False)
 watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json']
 before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
 def invoke(name,args,forbidden=False):
  blocked={cases.prepare_historical_statement_year_case.__code__,cases._prepare_historical_statement_case.__code__,paired.revenue_claims_admitted_by_original.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
  def guard(frame,event,arg):
   if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
  old=sys.getprofile();start=time.perf_counter()
  try:
   if forbidden:sys.setprofile(guard)
   with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),contextlib.redirect_stdout(io.StringIO()) as stream:
    code=main(args)
  finally:sys.setprofile(old)
  record={'seconds':time.perf_counter()-start,'exit_code':code,'arguments':args,'stdout':stream.getvalue()}
  (work/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
  print(name,round(record['seconds'],3),code,flush=True)
  assert code==0,record
  return json.loads(record['stdout']),record
 export,export_record=invoke('export',['export','--company','marriott_international','--metric','B02','--history-years','5','--source-root',str(source),'--output-root',str(work/'package')])
 assert export['status']=='EXPORTED',export
 assert export['source_discovery']['fiscal_range']['fiscal_years']==[2021,2022,2023,2024,2025]
 for relative in export['files']:assert (work/'package'/relative).read_bytes()==(source/relative).read_bytes(),relative
 assert (work/'package/evidence/requests_log.csv').read_bytes()==(source/'evidence/requests_log.csv').read_bytes()
 args=['run','--company','marriott_international','--metric','B02','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2023','--source-root',str(work/'package'),'--work-dir',str(work/'task'),'--output-dir',str(work/'first')]
 first,first_record=invoke('first-execution',args)
 item=first['metrics'][0];assert item['calculation_performed'] and item['new_candidate_created'],first
 result_hashes={p:h for p,h in hashes(work/'task').items() if '/results/' in p}
 folders=sorted(str(p) for p in (work/'task').glob('updates/B02/periods/*/results/*'))
 repeat,repeat_record=invoke('repeat-forbidden',args[:-1]+[str(work/'repeat')],True)
 item2=repeat['metrics'][0];assert not item2['calculation_performed'] and not item2['new_candidate_created'],repeat
 assert item2['result_id']==item['result_id']
 assert {p:h for p,h in hashes(work/'task').items() if '/results/' in p}==result_hashes
 assert sorted(str(p) for p in (work/'task').glob('updates/B02/periods/*/results/*'))==folders
 before_read=hashes(work/'task');start=time.perf_counter()
 child=subprocess.run([sys.executable,'-B',str(Path.cwd()/'tools/vnext_company.py'),'results','--company','marriott_international','--state-root',str(work/'task'),'--output-root',str(work/'read')],capture_output=True,text=True)
 read_record={'seconds':time.perf_counter()-start,'exit_code':child.returncode,'stdout':child.stdout,'stderr':child.stderr}
 (work/'independent-read.json').write_text(json.dumps(read_record,indent=2)+'\n')
 assert child.returncode==0 and not child.stderr,read_record
 assert hashes(work/'task')==before_read
 rows=list(csv.DictReader((work/'read/metrics_matrix.csv').open(encoding='utf-8-sig')));assert len(rows)==1,rows
 row=rows[0];assert row['unit']=='ratio' and row['fiscal_year']=='2023' and row['cik']=='1048286',row
 assert (row['period_start'],row['period_end'])==('2023-01-01','2023-12-31')
 with localcontext() as ctx:
  ctx.prec=28;expected=(Decimal('23713000000')-Decimal('20773000000'))/Decimal('20773000000')
 assert Decimal(row['value'])==expected,row
 record_root=Path(row['record_root']);assessment=json.loads((record_root/'input-assessments.json').read_text())['assessments']['historical_statement']
 scopes=assessment['paired_revenue_scopes'];assert all(s['complete_scope_proven'] for s in scopes.values())
 claims=[r for r in [json.loads(x) for x in (record_root/'records.jsonl').read_text().splitlines()] if r['record_type']=='DETERMINISTIC_VERIFIED_CLAIM']
 assert sorted(Decimal(c['value']) for c in claims)==[Decimal('20773000000'),Decimal('23713000000')],claims
 (work/'selected-source-scopes.json').write_text(json.dumps(scopes,indent=2)+'\n');(work/'selected-native-claims.json').write_text(json.dumps(claims,indent=2)+'\n')
 assert before=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
 result={'code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_root':str(source),'work_root':str(work),'export':{'seconds':export_record['seconds'],'package_id':export['package_id'],'files':len(export['files']),'fiscal_years':export['source_discovery']['fiscal_range']['fiscal_years'],'copied_originals_equal':True},'first':{'seconds':first_record['seconds'],'calculation_performed':True,'result_id':item['result_id']},'repeat':{'seconds':repeat_record['seconds'],'calculation_forbidden':True,'unchanged_result_files':len(result_hashes),'no_new_result_directory':True},'independent_read':{'seconds':read_record['seconds'],'state_files_unchanged':len(before_read),'row':row},'source_hashes':before,'new_calls':[0,0,0],'limits':['One FY2023 B02 result computed; five-year package readiness is not full business acceptance.','No online discovery or missing-source acquisition performed.','Existing tasks/results and original source ledger are untouched.']}
 (work/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.source_root.resolve(),a.work_root.resolve()),indent=2))
