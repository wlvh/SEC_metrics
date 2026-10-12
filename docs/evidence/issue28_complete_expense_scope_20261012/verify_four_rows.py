"""Four exact receiving-return rows at formal company CLI; no old CSV answer input."""
import argparse,csv,hashlib,io,json,socket,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--state-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);p.add_argument('--resume-first',type=Path);a=p.parse_args();assert a.resume_first is not None or not a.state_root.exists()
a.output_root.mkdir(parents=True,exist_ok=True)
from tools.vnext_company import main
from vnext import historical_statement_cases,calculator,company_fiscal_range
company='paramount_skydance_paramount_global'
args=['run','--company',company,'--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2022','--metric','B01','--metric','B03','--source-root',str(a.source_root),'--work-dir',str(a.state_root),'--output-dir',str(a.output_root/'first')]
blocked={historical_statement_cases.prepare_historical_statement_year_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__,company_fiscal_range.discover_fiscal_range.__code__}
def trace(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_REPEAT_OR_READ_MUST_NOT_CALCULATE')
def snap(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def invoke(arguments,forbid=False):
 out=io.StringIO();start=time.perf_counter()
 if forbid:sys.setprofile(trace)
 try:
  with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch('sys.stdout',out):code=main(arguments)
 finally:sys.setprofile(None)
 return {'exit':code,'seconds':time.perf_counter()-start,'report':json.loads(out.getvalue()),'args':arguments}
if a.resume_first is None:
 first=invoke(args)
else:
 report=json.loads(a.resume_first.read_text())
 assert report['source_root']==str(a.source_root) and report['selected_fiscal_years']==[2021,2022] and sorted(report['selected_metrics'])==['B01','B03']
 assert report['program_root']==str(Path.cwd())
 first={'exit':None,'seconds':None,'report':report,'args':args,'elapsed_unavailable_reason':'Original outer harness failed after complete official run; resumed existing result without computation'}
rows=list(csv.DictReader((Path(first['report']['output_root'])/'metrics_matrix.csv').open()))
assert len(rows)==4 and all(r['status']=='OK' and r['value'] for r in rows),rows
amounts={(r['metric_id'],r['fiscal_year']):r['value'] for r in rows}
assert amounts['B01','2021']=='28586000000' and amounts['B01','2022']=='30154000000',amounts
old_results={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.state_root.rglob('*') if p.is_file() and '/results/' in str(p)}
repeat_args=list(args);repeat_args[-1]=str(a.output_root/'repeat');repeat=invoke(repeat_args,True)
assert all(not r['calculation_performed'] and r['status']=='NO_SOURCE_CONTENT_CHANGE' for r in repeat['report']['metrics'])
assert old_results=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.state_root.rglob('*') if p.is_file() and '/results/' in str(p)}
state_before=snap(a.state_root);read_args=['tools/vnext_company.py','results','--company',company,'--state-root',str(a.state_root),'--output-root',str(a.output_root/'read')]
command='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("NETWORK_FORBIDDEN"));sys.argv='+repr(read_args)+';runpy.run_path("tools/vnext_company.py",run_name="__main__")'
start=time.perf_counter();read=subprocess.run([sys.executable,'-c',command],cwd=Path.cwd(),capture_output=True,text=True);elapsed=time.perf_counter()-start
assert read.returncode==0,read.stderr;assert state_before==snap(a.state_root)
read_report=json.loads(read.stdout)
read_rows=list(csv.DictReader((Path(read_report['output_root'])/'metrics_matrix.csv').open()))
key=lambda r:(r['metric_id'],r['fiscal_year'])
fields=('metric_id','value','unit','fiscal_year','period_start','period_end','status','result_id')
assert {key(r):{k:r[k] for k in fields} for r in rows}=={key(r):{k:r[k] for k in fields} for r in read_rows}
result={'code_root':str(Path.cwd()),'source_root':str(a.source_root),'state_root':str(a.state_root),'first':first,'repeat':repeat,'read':{'seconds':elapsed,'args':read_args,'rows':read_rows},'rows':rows,'state_files':len(state_before),'new_calls':[0,0,0]}
(a.output_root/'verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'code_root':str(Path.cwd()),'first_seconds':first['seconds'],'repeat_seconds':repeat['seconds'],'read_seconds':elapsed,'amounts':{str(k):v for k,v in amounts.items()},'new_calls':[0,0,0]}))
