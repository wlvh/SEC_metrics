"""Formal new company, forbidden repeat and independent results using saved SEC sources."""
import argparse,csv,hashlib,io,json,socket,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
assert not a.work_dir.exists(),'Use a new task; do not write a peer or existing task'
a.output_root.mkdir(parents=True,exist_ok=True)
from tools.vnext_company import main
from vnext import historical_statement_cases,historical_paired_revenue,calculator,company_fiscal_range
company='paramount_skydance_paramount_global'
args=['run','--company',company,'--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2024','--metric','B02','--source-root',str(a.source_root),'--work-dir',str(a.work_dir),'--output-dir',str(a.output_root/'first')]
def snap(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
blocked={historical_statement_cases.prepare_historical_statement_year_case.__code__,historical_paired_revenue.revenue_claims_admitted_by_original.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__,company_fiscal_range.discover_fiscal_range.__code__}
def profile(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('REPEAT_MUST_NOT_PREPARE_OR_COMPUTE')
def invoke(arguments,forbid=False):
 stdout=io.StringIO();start=time.perf_counter()
 if forbid:sys.setprofile(profile)
 try:
  with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch('sys.stdout',stdout):code=main(arguments)
 finally:sys.setprofile(None)
 return {'exit_code':code,'seconds':time.perf_counter()-start,'arguments':arguments,'report':json.loads(stdout.getvalue())}
first=invoke(args);metric=first['report']['metrics'][0]
assert metric['status']=='CANDIDATE_READY',first
result_id=metric['result_id'];result_root=Path(metric['result_root']);before_results=snap(result_root)
assert result_id=='sha256:3a8ca984f4be8f2aa8ac4e47bf0e4c789bffa9b66c18cca541dde9d7610adfba',metric
repeat_args=list(args);repeat_args[-1]=str(a.output_root/'repeat');repeat=invoke(repeat_args,True)
assert repeat['report']['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
assert not repeat['report']['metrics'][0]['calculation_performed'] and repeat['report']['metrics'][0]['result_id']==result_id
assert before_results==snap(result_root)
before_state=snap(a.work_dir)
read_args=['tools/vnext_company.py','results','--company',company,'--state-root',str(a.work_dir),'--output-root',str(a.output_root/'read')]
command='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("NETWORK_FORBIDDEN"));sys.argv='+repr(read_args)+';runpy.run_path("tools/vnext_company.py",run_name="__main__")'
start=time.perf_counter();reader=subprocess.run([sys.executable,'-c',command],cwd=Path.cwd(),capture_output=True,text=True);read_seconds=time.perf_counter()-start
assert reader.returncode==0,reader.stderr
assert before_state==snap(a.work_dir)
rows=list(csv.DictReader((a.output_root/'read/metrics_matrix.csv').open()));row=rows[0]
assert len(rows)==1 and row['metric_id']=='B02' and row['fiscal_year']=='2024'
assert row['value']=='-0.01480507217051126399568325914' and row['period_start']=='2024-01-01' and row['period_end']=='2024-12-31',row
record={'code_root':str(Path.cwd()),'source_root':str(a.source_root),'state_root':str(a.work_dir),'first':first,'repeat':repeat,'read':{'seconds':read_seconds,'arguments':read_args,'exit_code':reader.returncode,'report':json.loads(reader.stdout),'rows':rows},'result_files':len(before_results),'read_state_files':len(before_state),'all_result_bytes_preserved_on_repeat':True,'all_state_bytes_preserved_on_read':True,'new_calls':[0,0,0],'timing_scope':'first/repeat CLI main excludes interpreter/import startup; independent results includes its subprocess startup'}
(a.output_root/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'first_seconds':first['seconds'],'repeat_seconds':repeat['seconds'],'read_seconds':read_seconds,'value':row['value'],'result_id':result_id,'new_calls':[0,0,0]}))
