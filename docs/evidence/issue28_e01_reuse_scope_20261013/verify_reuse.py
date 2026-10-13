"""Real CLI reuse of a copied review task; source/factory/calculator forbidden."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-root',required=True,type=Path)
    parser.add_argument('--output-root',required=True,type=Path)
    parser.add_argument('--original-state',required=True,type=Path)
    args=parser.parse_args()
    state=args.state_root.resolve();out=args.output_root.resolve()
    out.mkdir(exist_ok=False)
    source=Path(json.loads((state/'company-task.json').read_text())['source_root'])
    original_before=hashes(args.original_state)
    saved_before={p:h for p,h in hashes(state).items() if '/results/' in p}
    assert len(saved_before)==7
    source_watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json']
    source_before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in source_watch}
    worker="""import json,sys,socket
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_e01_company_case as h,historical_event_items as i,historical_ma_confirmation as m,calculator
from vnext.continuous_call_ledger import CallLedger
from scripts import securegpt_sdk
blocked={h.prepare_historical_e01_year_case.__code__,i.content_confirmation_candidates.__code__,m.confirmation_request.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__,calculator.withheld_metric_result.__code__}
calls=[]
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:
  calls.append(frame.f_code.co_name);raise AssertionError('Stable saved input entered producer/calculator')
def forbidden(*args,**kwargs):raise AssertionError('No network, model or claim')
sys.setprofile(guard)
with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden),patch.object(CallLedger,'claim',forbidden),patch.object(securegpt_sdk,'send',forbidden):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
    def invoke(name,argv):
        start=time.perf_counter()
        completed=subprocess.run([sys.executable,'-B','-c',worker,json.dumps(argv)],capture_output=True,text=True)
        seconds=time.perf_counter()-start
        raw={'argv':argv,'seconds':seconds,'exit_code':completed.returncode,
             'stdout':completed.stdout,'stderr':completed.stderr}
        (out/(name+'.json')).write_text(json.dumps(raw,indent=2)+'\n')
        assert completed.returncode in (0,2) and not completed.stderr,(name,raw)
        report=json.loads(completed.stdout)
        return {'seconds':seconds,'exit_code':completed.returncode,'report':report}
    cli=['run','--company','pfizer','--period','fiscal-years','--fiscal-year-start','2023',
         '--fiscal-year-end','2023','--metric','E01','--source-root',str(source),
         '--work-dir',str(state),'--output-dir',str(out/'runs')]
    first=invoke('first-reuse',cli);metric=first['report']['metrics'][0]
    assert metric['status']=='PREVIOUS_INPUT_WITHHELD',metric
    assert metric['result_reason_code']=='E01_ITEM_METADATA_BODY_CONFLICT'
    assert metric['configuration_compatibility']=='FINITE_INSPECTED_E01_DISPATCH_ONLY'
    assert not metric['calculation_performed'] and not metric['new_candidate_created']
    second=invoke('second-reuse',cli)
    assert second['report']['metrics'][0]['status']=='PREVIOUS_INPUT_WITHHELD'
    assert second['report']['metrics'][0]['result_id']==metric['result_id']
    before_read=hashes(state)
    read=invoke('read',['results','--company','pfizer','--state-root',str(state),'--output-root',str(out/'read')])
    assert hashes(state)==before_read
    rows=list(csv.DictReader((out/'read/metrics_matrix.csv').open()))
    assert len(rows)==1
    row=rows[0]
    assert row['value']=='' and row['status']=='WITHHELD' and row['fiscal_year']=='2023'
    assert row['cik']=='78003' and row['period_start']=='2023-01-01' and row['period_end']=='2023-12-31'
    assert row['result_id']==metric['result_id']
    assert saved_before=={p:h for p,h in hashes(state).items() if '/results/' in p}
    assert hashes(args.original_state)==original_before
    assert source_before=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in source_watch}
    receipt={'state_root':str(state),'original_state':str(args.original_state),'source_root':str(source),
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'uncommitted_paths':subprocess.check_output(['git','status','--porcelain'],text=True).splitlines(),
        'phases':{name:{k:v for k,v in item.items() if k!='report'} for name,item in
                  [('first-reuse',first),('second-reuse',second),('read',read)]},
        'first_metric':metric,'second_metric':second['report']['metrics'][0],'csv_row':row,
        'original_task_files_unchanged':len(original_before),'saved_result_files_unchanged':len(saved_before),
        'source_metadata_unchanged':source_before,'reader_state_files_unchanged':len(before_read),
        'new_calls':{'provider':0,'paid':0,'sec':0},'complete_annual_ma_count_proven':False}
    (out/'summary.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('first_metric','second_metric','csv_row')},indent=2))


if __name__=='__main__':main()
