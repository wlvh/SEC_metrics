"""The receiver's real JPM current-only regression through company run/read."""
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
from vnext import current_statement_metric_case as current
from vnext.ordinary_saved_result import _ordinary_case


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--resume-first',type=Path)
    parser.add_argument('--read-name',default='read')
    args=parser.parse_args();assert not args.receipt.exists()
    if args.resume_first is None:
        assert not args.work_root.exists();args.work_root.mkdir(parents=True)
    else:assert args.work_root.is_dir()
    source=Path.cwd();state=args.work_root/'state'
    command=['run','--company','jpmorgan_chase','--source-root',str(source),
        '--work-dir',str(state),'--metric','B04','--metric','B05','--metric','B07']
    protected=[source/p for p in ('evidence/submissions/CIK0000019617.json',
        'evidence/submissions/CIK0000019617-submissions-001.json',
        'evidence/requests_log.csv','evidence/requests_log_manifest.json')]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    reports=[]
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_CLAIM')))
        from vnext import historical_statement_cases as shared
        stack.enter_context(patch.object(shared,'resolve_period_selection',side_effect=AssertionError('NO_IRRELEVANT_HISTORY')))
        baseline={m:_ordinary_case(source,'jpmorgan_chase',m)['results'][m] for m in ('B04','B05','B07')}
        for phase in ('first','repeat-forbidden'):
            if phase=='first' and args.resume_first is not None:
                report=json.loads(args.resume_first.read_text())
                assert report['record_root']==str(state) and report['source_root']==str(source)
                assert all(m['status']=='CANDIDATE_READY' for m in report['metrics'])
                reports.append({'phase':phase,'seconds':report['elapsed_seconds'],
                    'exit_code':2,'report':report,'execution_reused_from_retained_log':True})
                saved={n:h for n,h in hashes(state).items() if '/results/' in n}
                continue
            if phase=='repeat-forbidden':
                stack.enter_context(patch.object(current,'prepare_current_statement_metric_case',
                    side_effect=AssertionError('NO_REPEAT_FACTORY')))
            stream=io.StringIO();started=time.perf_counter()
            with redirect_stdout(stream):code=main(command+['--output-dir',str(args.work_root/phase)])
            report=json.loads(stream.getvalue())
            warnings=any(m.get('source_observation_errors') for m in report['metrics'])
            assert code==(2 if warnings else 0),report
            assert report['status']==('FLOW_COMPLETED_WITH_LIMITATIONS' if warnings else 'FLOW_COMPLETED')
            assert all(m['status']==('CANDIDATE_READY' if phase=='first' else 'NO_SOURCE_CONTENT_CHANGE')
                       for m in report['metrics'])
            reports.append({'phase':phase,'seconds':time.perf_counter()-started,'exit_code':code,'report':report})
            (args.work_root/(phase+'.json')).write_text(stream.getvalue())
            result_files={n:h for n,h in hashes(state).items() if '/results/' in n}
            if phase=='first':saved=result_files
            else:assert saved==result_files
    snapshot=hashes(state);started=time.perf_counter()
    read=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','jpmorgan_chase',
        '--state-root',str(state),'--output-root',str(args.work_root/args.read_name)],capture_output=True,text=True,timeout=60)
    assert read.returncode==0,read.stdout+read.stderr
    seconds=time.perf_counter()-started;assert snapshot==hashes(state)
    rows=[]
    for path in (args.work_root/args.read_name).rglob('metrics_matrix.csv'):
        with path.open() as f:rows.extend(csv.DictReader(f))
    assert {r['metric_id'] for r in rows}=={'B04','B05','B07'} and len(rows)==3
    for row in rows:
        old=baseline[row['metric_id']]
        assert row['result_id']==old['result_id']
        from vnext.normal_run_specs import installed_ordinary_spec_documents
        expected_unit=installed_ordinary_spec_documents()[row['metric_id']]['compiled_spec']['compiled']['canonical_unit']
        assert row['value']==(old['value'] or '') and row['unit']==expected_unit
        assert row['period_start']==old['period_start'] and row['period_end']==old['period_end']
        if row['metric_id'] in ('B04','B07'):assert old['applicability']=='N_A_STRUCTURAL'
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    receipt={'code_root':str(source),'source_root':str(source),
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'working_tree_test':True,'state_root':str(state),'phases':reports,'read_seconds':seconds,
        'state_files_preserved':len(snapshot),'csv_rows':rows,'baseline_results':baseline,
        'protected_hashes':before,'new_calls':[0,0,0],
        'verification':'ACTUAL_CURRENT_BANK_NA_WITH_UNRELATED_HISTORY_CONFLICT'}
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'phases':[(r['phase'],r['seconds']) for r in reports],
        'read_seconds':seconds,'state_files':len(snapshot),'new_calls':[0,0,0]}))


if __name__=='__main__':run()
