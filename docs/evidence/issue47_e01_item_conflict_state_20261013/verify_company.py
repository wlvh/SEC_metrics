"""Existing Pfizer FY2023 item conflict: saved withholding, forbidden repeat and independent read."""
import argparse, csv, hashlib, json, subprocess, sys, time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--source-root',required=True,type=Path);parser.add_argument('--output-root',required=True,type=Path);args=parser.parse_args()
root=args.output_root.resolve();root.mkdir(parents=True,exist_ok=False);state=root/'state';source=args.source_root.resolve()
watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json']
source_before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
def invoke(name,cli,forbidden):
 code="""import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_e01_company_case as h,historical_event_items as i,historical_ma_confirmation as m,calculator
blocked={h.prepare_historical_e01_year_case.__code__,i.content_confirmation_candidates.__code__,m.confirmation_request.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__,calculator.withheld_metric_result.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('No source/candidate/request/calculation during stable repeat or read')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
 t=time.perf_counter();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(cli),'1' if forbidden else '0'],text=True,capture_output=True)
 d={'arguments':cli,'seconds_subprocess_inclusive':time.perf_counter()-t,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr};(root/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n')
 assert p.returncode in (0,2) and not p.stderr,(name,d)
 print(name,round(d['seconds_subprocess_inclusive'],3),p.returncode,flush=True);return d,json.loads(p.stdout)
cli=['run','--company','pfizer','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2023','--metric','E01','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(root/'runs')]
first,result=invoke('first',cli,False);assert len(result['metrics'])==1
metric=result['metrics'][0];assert metric['status']=='CANDIDATE_WITHHELD' and metric['result_reason_code']=='E01_ITEM_METADATA_BODY_CONFLICT'

assessment_files=list(state.rglob('input-assessments.json'))
assert len(assessment_files)==1
saved=json.loads(assessment_files[0].read_text())['assessments']['e01_content']
assert saved['item_source_conflict']['reason']=='EVENT_ITEM_HEADED_BUT_NOT_LISTED:0001193125-23-294930:2.01'
assert saved['complete_annual_count'] is None and saved['matching_response_available'] is False
after_first=hashes();results_first={p:h for p,h in after_first.items() if '/results/' in p}
again,repeated=invoke('repeat',cli,True);current=repeated['metrics'][0]
assert current['result_id']==metric['result_id'] and not current['calculation_performed'] and not current['new_candidate_created']
assert results_first=={p:h for p,h in hashes().items() if '/results/' in p}
before_read=hashes();read,display=invoke('read',['results','--company','pfizer','--state-root',str(state),'--output-root',str(root/'read')],True);assert hashes()==before_read
rows=list(csv.DictReader((root/'read/metrics_matrix.csv').open()));assert len(rows)==1
row=rows[0];assert row['value']=='' and row['status']=='WITHHELD' and row['fiscal_year']=='2023' and row['period_start']=='2023-01-01' and row['period_end']=='2023-12-31' and row['cik']=='78003'
assert row['result_id']==metric['result_id']
assert source_before=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
d={'execution':'main293 with the historical E01 conflict-state consumer change','local_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'phases':{n:{k:d[k] for k in ['arguments','seconds_subprocess_inclusive','exit']} for n,d in [('first',first),('repeat',again),('read',read)]},'saved_conflict':saved['item_source_conflict'],'metric':metric,'repeat_metric':current,'row':row,'stable_result_files':len(results_first),'read_state_files_unchanged':len(before_read),'source_metadata_hashes_unchanged':source_before,'new_calls':[0,0,0]};(root/'summary.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
