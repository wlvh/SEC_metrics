"""Actual current Ford debt source relationship, without a new B06 ratio."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update
ROOT=Path.cwd();SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');E=Path(__file__).parent;STATE=Path(tempfile.mkdtemp(prefix='issue28-current-lease-'))
args=['run','--company','ford_motor_company','--source-root',str(SOURCE),'--metric','B06','--work-dir',str(STATE/'state'),'--output-dir',str(STATE/'out')]
def snapshot(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def run(forbid=False):
 out=io.StringIO();start=time.perf_counter()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):
  if forbid:
   with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeat currentB06')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No new debt result write')):code=main(args)
  else:code=main(args)
 return code,json.loads(out.getvalue()),time.perf_counter()-start
first_code,first,first_seconds=run();row=first['metrics'][0];assert row['status']=='CANDIDATE_WITHHELD',(first_code,first);root=Path(row['result_root']);assessment=json.loads((root/'input-assessments.json').read_text())['assessments']['B06'];scope=assessment['selection']['scope_source'];relation=scope['lease_inclusion'];assert relation['status']=='REPORTED_INCLUDED' and relation['additional_debt_amount']=='0' and relation['component_total']=='890000000',relation;assert scope['ratio'] is None and scope['definition_complete'] is False;assert 'INDUSTRIAL_ATTRIBUTABLE_EQUITY_NOT_ESTABLISHED' in scope['limitations'];assert scope['reported_subtotal']=='21919000000'
protected=snapshot(root);repeat_code,repeat,repeat_seconds=run(True);assert repeat['metrics'][0]['status']=='PREVIOUS_INPUT_WITHHELD' and repeat['metrics'][0]['result_id']==row['result_id'];assert snapshot(root)==protected
before=snapshot(STATE/'state');start=time.perf_counter();code='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network"));sys.argv='+repr(['tools/vnext_company.py','results','--company','ford_motor_company','--state-root',str(STATE/'state'),'--output-root',str(STATE/'read')])+';runpy.run_path("tools/vnext_company.py",run_name="__main__")';read=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True);seconds=time.perf_counter()-start;assert read.returncode==0,read.stderr;assert before==snapshot(STATE/'state');csvrows=list(csv.DictReader((STATE/'read/metrics_matrix.csv').open()));assert csvrows[0]['value']=='' and csvrows[0]['status']=='WITHHELD';report={'code_root':str(ROOT),'source_root':str(SOURCE),'test_state':str(STATE),'args':args,'first':first,'repeat':repeat,'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':seconds,'csv':csvrows[0],'scope_summary':{k:scope[k] for k in ('scope_class','reported_subtotal','same_scope_attributable_equity','limitations','definition_complete','ratio')},'lease_relation':relation,'saved_result_read_state_unchanged':True,'new_calls':[0,0,0]};(E/'actual-company.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'first':first_seconds,'repeat':repeat_seconds,'read':seconds,'result_id':row['result_id'],'lease_status':relation['status'],'lease_amount':relation['component_total'],'additional_debt':relation['additional_debt_amount'],'publication':csvrows[0]['status'],'value':csvrows[0]['value'],'new_calls':[0,0,0]}))
