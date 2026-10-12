import contextlib,csv,io,json,os,socket,subprocess,sys,tempfile,time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext.canonical import sha256_file
root=Path.cwd();baseline=Path('/Users/lyuhongwang/.codex/worktrees/issue28-source-proof-main-c6f/SEC_metrics');source=baseline
base=Path(tempfile.mkdtemp(prefix='issue28-b02-main-source-regression-'))
evidence=root/'docs/evidence/issue28_current_complete_revenue_20261011/prior-xml-receiving'
companies=['lumen_technologies','macys']
records=[]
def rows(directory):return list(csv.DictReader(next(directory.rglob('metrics_matrix.csv')).open()))
def snap(state):return {str(p.relative_to(state)):sha256_file(path=p) for p in state.rglob('*') if p.is_file()}
for company in companies:
 args=['run','--company',company,'--source-root',str(source),'--metric','B01','--metric','B02','--metric','B03']
 before_state=base/(company+'-main');before_out=base/(company+'-main-out')
 before_args=args+['--work-dir',str(before_state),'--output-dir',str(before_out)]
 code='import json,socket,sys; from tools.vnext_company import main; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network")); sys.exit(main(json.loads(sys.argv[1])))'
 before_record=next(r for r in json.loads((evidence/'actual-company-comparison.json').read_text())['records'] if r['company']==company)
 before_seconds=before_record['main_seconds'];old={r['metric_id']:r for r in before_record['main_rows']};before=type('Baseline',(),{'returncode':before_record['main_exit'],'stderr':''})()
 state=base/(company+'-candidate');out=base/(company+'-candidate-out');read=base/(company+'-read')
 current_args=args+['--work-dir',str(state),'--output-dir',str(out)];stream=io.StringIO();start=time.monotonic()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),contextlib.redirect_stdout(stream):first=main(current_args)
 first_seconds=time.monotonic()-start;new={r['metric_id']:r for r in rows(out)}
 assert before.returncode in (0,2) and first in (0,2),(company,before.stderr,stream.getvalue())
 if company=='lumen_technologies':
  assert Decimal(new['B01']['value'])==Decimal('12402000000')
  assert Decimal(new['B02']['value'])==(Decimal('12402')-Decimal('13108'))/Decimal('13108')
  assert Decimal(new['B03']['value'])==(Decimal('-812')+Decimal('2749'))/Decimal('12402')
 elif company=='macys':
  assert Decimal(new['B02']['value'])==(Decimal('22621')-Decimal('23006'))/Decimal('23006')
 for metric in ('B01','B02','B03'):
  if company=='lumen_technologies' or (company=='macys' and metric=='B02'):continue
  keys=('value','unit','status','period_start','period_end','fiscal_year','result_id')
  assert {k:new[metric][k] for k in keys}=={k:old[metric][k] for k in keys},(company,metric,old[metric],new[metric])
 protected={p:h for p,h in snap(state).items() if '/results/' in '/'+p};start=time.monotonic()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No repeat calculation')),patch('vnext.ordinary_current_update.save_calculated_case',side_effect=AssertionError('No repeat write')),contextlib.redirect_stdout(stream):repeat=main(current_args)
 repeat_seconds=time.monotonic()-start
 assert repeat==first and protected=={p:h for p,h in snap(state).items() if '/results/' in '/'+p},company
 before_read=snap(state);start=time.monotonic();reader=subprocess.run([sys.executable,'-c','import runpy,socket,sys; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network")); sys.argv='+repr(['tools/vnext_company.py','results','--company',company,'--state-root',str(state),'--output-root',str(read)])+'; runpy.run_path("tools/vnext_company.py",run_name="__main__")'],cwd=root,capture_output=True,text=True)
 read_seconds=time.monotonic()-start;assert reader.returncode==0 and before_read==snap(state),(company,reader.stderr)
 for r in [*old.values(),*new.values()]:r.pop('context_or_dimension',None)
 result={'company':company,'source_root':str(source),'main_args':before_args,'candidate_args':current_args,'main_exit':before.returncode,'candidate_exit':first,'repeat_exit':repeat,'main_seconds':before_seconds,'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,'main_rows':list(old.values()),'new_rows':list(new.values()),'unchanged_repeat_result_files':True,'independent_read_state_unchanged':True,'result_file_count':len(protected),'new_calls':[0,0,0]}
 records.append(result);(evidence/'actual-final-guarded.json').write_text(json.dumps({'base':str(base),'code_root':str(root),'baseline':str(baseline),'records':records},indent=2)+'\n')
 print(json.dumps({'company':company,'before_B02':old['B02']['value'],'after_B02':new['B02']['value'],'first':first_seconds,'repeat':repeat_seconds,'read':read_seconds}),flush=True)
assert len(records)==2
