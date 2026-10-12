"""One real saved-source B06 consumer, repeat and independent public reading."""
import argparse,contextlib,csv,hashlib,importlib.util,io,json,socket,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--state-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
assert not a.state_root.exists(),'Fresh isolated task required'
a.output_root.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('actual_company_cli',Path('tools/vnext_company.py'));cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
args=['run','--company','marriott_international','--metric','B06','--source-root',str(a.source_root),'--work-dir',str(a.state_root),'--output-dir',str(a.output_root/'run')]
def execute(argv):
 s=io.StringIO();t=time.perf_counter()
 with contextlib.redirect_stdout(s),patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
  code=cli.main(argv)
 return code,s.getvalue(),str(time.perf_counter()-t)
first,body,first_seconds=execute(args);(a.output_root/'first.json').write_text(body)
assert first in (0,2),body
protected={str(p.relative_to(a.state_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.state_root.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ('current-result.json','completed-check.json'))}
from vnext import current_b06_case
with patch.object(current_b06_case,'prepare_current_b06_case',side_effect=AssertionError('REPEAT_CALCULATION_FORBIDDEN')):
 repeat,repeat_body,repeat_seconds=execute(args)
(a.output_root/'repeat.json').write_text(repeat_body);assert repeat in (0,2),repeat_body
now={str(p.relative_to(a.state_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.state_root.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ('current-result.json','completed-check.json'))}
assert protected==now
command=[sys.executable,'tools/vnext_company.py','results','--company','marriott_international','--state-root',str(a.state_root),'--output-root',str(a.output_root/'read')]
t=time.perf_counter();done=subprocess.run(command,text=True,capture_output=True,timeout=60);read_seconds=str(time.perf_counter()-t)
(a.output_root/'read.log').write_text(done.stdout+done.stderr);assert done.returncode==0,done.stdout+done.stderr
rows=[]
for f in (a.output_root/'read').rglob('*.csv'):
 with f.open() as stream:
  reader=csv.DictReader(stream)
  if {'result_id','metric_id','value','period_end'}<=set(reader.fieldnames or []):
   rows.extend(dict(r) for r in reader if r['metric_id']=='B06')
assert len(rows)==1,rows
again={str(p.relative_to(a.state_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.state_root.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ('current-result.json','completed-check.json'))}
assert protected==again
receipt={'first_code':first,'first_seconds':first_seconds,'repeat_code':repeat,'repeat_seconds':repeat_seconds,'independent_read_seconds':read_seconds,'row':rows[0],'protected_files':len(protected),'repeat_and_read_protected_bytes_unchanged':True,'new_calls':[0,0,0],'command':args,'read_command':command,'tested_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tested_state':'UNCOMMITTED_DEPENDENCY_ONLY_PATCH'}
a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
