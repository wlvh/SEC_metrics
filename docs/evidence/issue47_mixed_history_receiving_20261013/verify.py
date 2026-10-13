"""Consume main's mixed-history entry with the existing five-year hotel task."""
import argparse
import csv
import hashlib
import io
import json
import socket
import subprocess
import sys
import time
from contextlib import ExitStack,redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_lodging_results,normal_lodging_results,calculator,batch_workflow


def hashes(root,results=False):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()
            and (not results or '/results/' in str(p.relative_to(root)))}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.receipt.exists():raise FileExistsError('USE_NEW_OUTPUT')
    args.output.mkdir(parents=True)
    state=args.state
    source=Path(json.loads((state/'company-task.json').read_text())['source_root'])
    before=hashes(state);results=hashes(state,True)
    command=['run','--company','marriott_international','--period','fiscal-years',
        '--fiscal-year-start','2024','--fiscal-year-end','2024','--metric','B10','--metric','D02',
        '--source-root',str(source),'--work-dir',str(state)]
    blocked={f.__code__ for f in (historical_lodging_results.prepare_historical_lodging_year_case,
        normal_lodging_results.calculate_selected_lodging_metric,calculator.calculate_metric,
        calculator.calculate_observation_metric,batch_workflow.calculate_metric)}
    phases=[]
    for phase in ('mixed','repeat'):
        stream=io.StringIO();start=time.perf_counter();previous=sys.getprofile()
        def profile(frame,event,arg):
            if event=='call' and frame.f_code in blocked:raise AssertionError('NO_CALCULATION')
            if previous is not None:previous(frame,event,arg)
        try:
            sys.setprofile(profile)
            with ExitStack() as stack:
                stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
                with redirect_stdout(stream):code=main(command+['--output-dir',str(args.output/phase)])
        finally:sys.setprofile(previous)
        body=json.loads(stream.getvalue());(args.output/(phase+'.json')).write_text(stream.getvalue())
        assert code==2,body
        metrics={r['metric_id']:r for r in body['metrics']}
        assert metrics['B10']['status']=='NO_SOURCE_CONTENT_CHANGE'
        assert metrics['D02']['status']=='PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED'
        assert not metrics['D02'].get('record_root') and not metrics['D02'].get('read_result_id')
        assert hashes(state,True)==results
        phases.append({'phase':phase,'seconds':time.perf_counter()-start,'exit_code':code,'report':body})
    snapshot=hashes(state);start=time.perf_counter()
    read=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company',
        'marriott_international','--state-root',str(state),'--output-root',str(args.output/'read')],
        capture_output=True,text=True,timeout=60)
    assert read.returncode==0,read.stdout+read.stderr
    readsec=time.perf_counter()-start;assert hashes(state)==snapshot
    rows=[]
    for p in (args.output/'read').rglob('metrics_matrix.csv'):rows.extend(csv.DictReader(p.open()))
    assert len([r for r in rows if r['metric_id'] in ('B10','B11')])==10
    d02=next(r for r in rows if r['metric_id']=='D02')
    assert d02['value']=='' and d02['result_validity']=='NO_CURRENT_RESULT'
    receipt={'main':'293e495f74ed111b9c0e3365b9f4d35f977949ce','before_state_files':len(before),
        'after_state_files':len(snapshot),'old_result_files_preserved':len(results),
        'phases':phases,'read_seconds':readsec,'read_state_unchanged':True,'csv_rows':rows,
        'state_root':str(state),'source_root':str(source),'output_root':str(args.output),'new_calls':[0,0,0]}
    args.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'phases':[(r['seconds'],r['exit_code']) for r in phases],
        'read_seconds':readsec,'rows':len(rows),'state_files':len(snapshot),'new_calls':[0,0,0]}))


if __name__=='__main__':run()
