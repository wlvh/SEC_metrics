"""Actual supported financial neighbour plus an explicitly unfinished metric."""
import argparse
from contextlib import ExitStack,redirect_stdout
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_statement_cases as statements


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();assert not args.work_root.exists() and not args.receipt.exists()
    args.work_root.mkdir(parents=True);state=args.work_root/'state';phases=[]
    protected=[args.source_root/p for p in ('config/company_registry.csv',
        'evidence/requests_log.csv','evidence/requests_log_manifest.json')]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    command=['run','--company','marriott_international','--period','fiscal-years',
        '--fiscal-year-start','2025','--fiscal-year-end','2025','--metric','B04','--metric','D02',
        '--source-root',str(args.source_root),'--work-dir',str(state)]
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_CLAIM')))
        for phase in ('first','repeat-forbidden'):
            stream=io.StringIO();started=time.perf_counter()
            original_profile=sys.getprofile()
            def profile(frame,event,arg):
                if event=='call' and frame.f_code in {
                    statements.prepare_historical_statement_year_case.__code__,
                    statements._prepare_historical_statement_case.__code__}:
                    raise AssertionError('NO_REPEAT_CALCULATION')
            try:
                if phase=='repeat-forbidden':sys.setprofile(profile)
                with redirect_stdout(stream):code=main(command+['--output-dir',str(args.work_root/phase)])
            finally:sys.setprofile(original_profile)
            body=json.loads(stream.getvalue())
            (args.work_root/(phase+'.json')).write_text(stream.getvalue())
            assert code==2 and body['status']=='FLOW_COMPLETED_WITH_LIMITATIONS',body
            metrics={m['metric_id']:m for m in body['metrics']}
            assert metrics['D02']['status']=='PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED'
            assert not metrics['D02'].get('read_result_id') and not metrics['D02'].get('record_root')
            assert metrics['B04']['status']==('CANDIDATE_READY' if phase=='first' else 'NO_SOURCE_CONTENT_CHANGE')
            phases.append({'phase':phase,'seconds':time.perf_counter()-started,'exit_code':code,'report':body})
            result_files={p:h for p,h in hashes(state).items() if '/results/' in p}
            if phase=='first':first_result_files=result_files
            else:assert result_files==first_result_files
    snapshot=hashes(state);started=time.perf_counter()
    read=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','marriott_international',
        '--state-root',str(state),'--output-root',str(args.work_root/'read')],capture_output=True,text=True,timeout=60)
    assert read.returncode==0,read.stdout+read.stderr
    read_seconds=time.perf_counter()-started
    assert snapshot==hashes(state)
    rows=[]
    for path in (args.work_root/'read').rglob('metrics_matrix.csv'):
        with path.open() as f:rows.extend(csv.DictReader(f))
    assert len(rows)==2
    by_metric={r['metric_id']:r for r in rows}
    assert by_metric['B04']['value']=='2601000000' and by_metric['B04']['unit']=='USD'
    assert by_metric['B04']['period_start']=='2025-01-01' and by_metric['B04']['period_end']=='2025-12-31'
    assert by_metric['D02']['value']=='' and by_metric['D02']['unit']==''
    assert by_metric['D02']['status']=='PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED'
    assert by_metric['D02']['fiscal_year']=='2025' and by_metric['D02']['result_validity']=='NO_CURRENT_RESULT'
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    receipt={'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'working_tree_files':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
            'scripts/vnext/company_local.py','scripts/vnext/company_current_records.py')},
        'code_root':str(Path.cwd()),'source_root':str(args.source_root),'state_root':str(state),
        'phases':phases,'read_seconds':read_seconds,'csv_rows':rows,
        'state_files_preserved':len(snapshot),'business_result_files':len(first_result_files),
        'source_registration_and_log_unchanged':True,'new_calls':[0,0,0],
        'verification':'ONE_SUPPORTED_NEIGHBOUR_AND_EXPLICIT_IMPLEMENTATION_GAP'}
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'phases':[(p['phase'],p['seconds'],p['exit_code']) for p in phases],
        'read_seconds':read_seconds,'state_files':len(snapshot),'new_calls':[0,0,0]}))


if __name__=='__main__':run()
