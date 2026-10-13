"""Existing complete Southwest D04 responses through formal company run/results.

No source acquisition, model execution, response correction or adoption.
"""
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
from vnext import current_d04_result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_files(root):
    return {p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file()}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--ledger-root',type=Path,required=True)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();assert (args.resume or not args.work_root.exists()) and not args.receipt.exists()
    args.work_root.mkdir(parents=True,exist_ok=args.resume);state=args.work_root/'state'
    protected=[args.ledger_root/'claims.jsonl',args.ledger_root/'binding.json']
    protected.extend(args.source_root/p for p in ('config/company_registry.csv',
        'evidence/requests_log.csv','evidence/requests_log_manifest.json'))
    for number in range(119,125):
        protected.extend(p for p in (args.ledger_root/'calls'/f'{number:04d}').rglob('*') if p.is_file())
    before={str(p):digest(p) for p in protected}
    command=['run','--company','southwest_airlines','--source-root',str(args.source_root),
             '--work-dir',str(state),'--metric','D04']
    reports=[]
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_NEW_CLAIM')))
        labels=('resumed-first','resumed-repeat-forbidden') if args.resume else ('first','repeat-forbidden')
        for label in labels:
            started=time.perf_counter();stream=io.StringIO()
            if label.endswith('repeat-forbidden'):
                stack.enter_context(patch.object(current_d04_result,'prepare_current_d04_case',
                    side_effect=AssertionError('NO_REPEAT_MODEL_INPUT_OR_AGGREGATION')))
            with redirect_stdout(stream):
                code=main(command+['--output-dir',str(args.work_root/label)])
            body=json.loads(stream.getvalue());(args.work_root/(label+'.json')).write_text(stream.getvalue())
            reports.append({'name':label,'exit_code':code,'elapsed_seconds':time.perf_counter()-started,'report':body})
            print(label,code,reports[-1]['elapsed_seconds'],flush=True)
            metric=body['metrics'][0]
            if code not in (0,2) or metric.get('result_reason_code')!='D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE':break
    assert before=={str(p):digest(p) for p in protected},'ORIGINALS_OR_LEDGER_CHANGED'
    result_files={p:h for p,h in state_files(state).items() if '/results/' in p}
    snapshot=state_files(state);started=time.perf_counter()
    read_root=args.work_root/('resumed-independent-read' if args.resume else 'independent-read')
    completed=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','southwest_airlines',
        '--state-root',str(state),'--output-root',str(read_root)],
        text=True,capture_output=True,timeout=60)
    read_time=time.perf_counter()-started
    assert completed.returncode==0,completed.stdout+completed.stderr
    assert snapshot==state_files(state),'READ_CHANGED_STATE'
    rows=[];evidence=[]
    for path in read_root.rglob('*.csv'):
        with path.open() as stream:
            reader=csv.DictReader(stream)
            if {'metric_id','value','result_id'}<=set(reader.fieldnames or ()):
                rows.extend(dict(r) for r in reader if r['metric_id']=='D04')
            elif {'metric_id','source_url'}<=set(reader.fieldnames or ()):
                evidence.extend(dict(r) for r in reader if r['metric_id']=='D04')
    receipt={'code_root':str(Path.cwd()),'committed_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'source_root':str(args.source_root),'ledger_root':str(args.ledger_root),'operations':reports,
        'independent_read_seconds':read_time,'rows':rows,'evidence':evidence,
        'original_protected_files':len(before),'originals_unchanged':True,'saved_result_files':result_files,
        'new_calls':[0,0,0],'production_adopted':False}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    assert len(reports)==2 and reports[-1]['report']['metrics'][0]['status']=='PREVIOUS_INPUT_WITHHELD',receipt
    assert not reports[-1]['report']['metrics'][0]['calculation_performed']
    assert len(rows)==1 and rows[0]['status']=='TEXT_QUAL',rows
    assert rows[0]['fiscal_year']=='2025',rows
    assert evidence, 'SOURCE_EVIDENCE_NOT_EXPORTED'


if __name__=='__main__':run()
