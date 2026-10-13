"""Current B04/B07 through the public saved-source company command."""
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
from vnext import current_statement_metric_case


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--work-root',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    args=p.parse_args();assert not args.work_root.exists() and not args.receipt.exists()
    args.work_root.mkdir(parents=True);state=args.work_root/'state';reports=[]
    protected=[args.source_root/x for x in ('config/company_registry.csv',
        'evidence/requests_log.csv','evidence/requests_log_manifest.json')]
    before={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    command=['run','--company','marriott_international','--source-root',str(args.source_root),
             '--work-dir',str(state),'--metric','B04','--metric','B07']
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_CLAIM')))
        for phase in ('first','repeat-forbidden'):
            if phase=='repeat-forbidden':
                stack.enter_context(patch.object(current_statement_metric_case,'prepare_current_statement_metric_case',
                    side_effect=AssertionError('NO_REPEAT_CURRENT_SELECTION_OR_CALCULATION')))
            stream=io.StringIO();started=time.perf_counter()
            with redirect_stdout(stream):code=main(command+['--output-dir',str(args.work_root/phase)])
            report=json.loads(stream.getvalue());seconds=time.perf_counter()-started
            (args.work_root/(phase+'.json')).write_text(stream.getvalue())
            reports.append({'phase':phase,'seconds':seconds,'exit_code':code,'report':report})
            print(phase,code,seconds,flush=True)
            assert code==0,report
            if phase=='first':saved={k:v for k,v in hashes(state).items() if '/results/' in k}
            else:
                assert saved=={k:v for k,v in hashes(state).items() if '/results/' in k}
                assert all(not m['calculation_performed'] for m in report['metrics'])
    assert before=={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    snapshot=hashes(state);started=time.perf_counter()
    read=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','marriott_international',
        '--state-root',str(state),'--output-root',str(args.work_root/'independent-read')],capture_output=True,text=True,timeout=60)
    assert read.returncode==0,read.stdout+read.stderr
    assert snapshot==hashes(state),'READ_CHANGED_STATE'
    rows=[]
    for path in (args.work_root/'independent-read').rglob('metrics_matrix.csv'):
        with path.open() as f:rows.extend(csv.DictReader(f))
    assert len(rows)==2 and {r['metric_id'] for r in rows}=={'B04','B07'}
    body={'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'working_tree_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            Path('scripts/vnext/current_statement_metric_case.py'),Path('scripts/vnext/ordinary_saved_result.py'),
            Path('scripts/vnext/ordinary_current_update.py'))},'code_root':str(Path.cwd()),
        'source_root':str(args.source_root),'state_root':str(state),'phases':reports,
        'independent_read_seconds':time.perf_counter()-started,'state_files_preserved':len(snapshot),
        'source_registration_and_log_unchanged':True,'csv_rows':rows,'new_calls':[0,0,0],
        'business_adopted':False}
    args.receipt.write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
    print('independent read',body['independent_read_seconds'],'state files',len(snapshot),flush=True)


if __name__=='__main__':run()
