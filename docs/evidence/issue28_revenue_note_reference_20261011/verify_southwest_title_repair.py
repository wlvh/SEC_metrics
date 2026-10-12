"""Affected real saved-source company entry; no old all-company rerun."""
import contextlib,csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
root=Path.cwd();e=root/'docs/evidence/issue28_revenue_note_reference_20261011'
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
work=Path(tempfile.mkdtemp(prefix='issue28-sw-loss-title-'));state=work/'state';output=work/'output'
args=['run','--company','southwest_airlines','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2023','--metric','B01','--metric','B02','--metric','B03','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(output)]
def hashes(p):return {str(x.relative_to(p)):hashlib.sha256(x.read_bytes()).hexdigest() for x in p.rglob('*') if x.is_file()}
def invoke(forbid=False):
 stream=io.StringIO();started=time.perf_counter()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),contextlib.redirect_stdout(stream):
  if forbid:
   with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No unchanged calculation')):code=main(args)
  else:code=main(args)
 return code,time.perf_counter()-started,json.loads(stream.getvalue())
if '--resume' in sys.argv:
 previous=json.loads((e/'sw-loss-title-first.json').read_text());first=previous['exit'];seconds=previous['seconds'];first_report=previous['report']
 state=Path(first_report['record_root']);work=state.parent;output=work/'output'
 args[args.index('--work-dir')+1]=str(state);args[args.index('--output-dir')+1]=str(output)
else:
 first,seconds,first_report=invoke();(e/'sw-loss-title-first.json').write_text(json.dumps({'seconds':seconds,'exit':first,'report':first_report},indent=2)+'\n');print('FIRST',first,seconds,flush=True)
assert first==0,first_report
saved={k:v for k,v in hashes(state).items() if '/results/' in k}
repeat,rsec,repeat_report=invoke(True)
assert repeat==0 and all(m.get('calculation_performed') is False and m.get('new_candidate_created') is False for m in repeat_report['metrics']),repeat_report
assert saved=={k:v for k,v in hashes(state).items() if '/results/' in k}
reader=work/'reader';start=time.perf_counter();p=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','southwest_airlines','--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True);read=time.perf_counter()-start;assert p.returncode==0,p.stderr
rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));assert len(rows)==9,rows
by={(r['metric_id'],int(r['fiscal_year'])):r for r in rows};assert by['B01',2021]['value']=='15790000000' and by['B01',2022]['value']=='23814000000'
for m,y in [('B01',2021),('B01',2022),('B02',2021),('B02',2022),('B02',2023),('B03',2021),('B03',2022)]:assert by[m,y]['value']!='' and by[m,y]['status']=='OK',(m,y,by[m,y])
refs=list(csv.DictReader((reader/'metric_evidence.csv').open()));assert refs and all(r['source_url'].startswith('https://') for r in refs);assert saved=={k:v for k,v in hashes(state).items() if '/results/' in k}
summary={'program_root':str(root),'base_local':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'actual_working_source_sha256':hashlib.sha256((root/'scripts/vnext/selected_revenue_scope_v1.py').read_bytes()).hexdigest(),'source_root':str(source),'state_root':str(state),'cli':args,'first_seconds':seconds,'forbidden_repeat_seconds':rsec,'independent_reader_seconds':read,'protected_state_files':len(saved),'rows':[{k:r[k] for k in ('metric_id','fiscal_year','value','unit','period_start','period_end','result_id','status')} for r in rows],'new_calls':[0,0,0]}
(e/'sw-loss-title-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('PASS_AFFECTED_SEVEN_AND_UNCHANGED_NEIGHBOURS',seconds,rsec,read,[(r['metric_id'],r['fiscal_year'],r['value']) for r in rows],flush=True)
