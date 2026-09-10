#!/usr/bin/env python3
"""Run bounded continuous annual updates in the stage-authorized isolated root."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import annual_continuity as continuity
from vnext.canonical import canonical_json_bytes


def write_result(output, result):
    # Serialize completely before opening the evidence file. Strict source
    # records can contain Decimal; use the same identity encoding as storage.
    payload=canonical_json_bytes(value=result)+b'\n'
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as out:out.write(payload)
    print(payload.decode('utf-8'),end='')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    init=commands.add_parser('initialize-data');init.add_argument('--data-root',type=Path,required=True)
    stage=commands.add_parser('stage-proposal')
    for name in ('stage-root','data-root','budget-root','review-file'):
        stage.add_argument('--'+name,type=Path,required=True)
    for name in ('seed-b01','seed-b10','visibility-file'):
        stage.add_argument('--'+name,type=Path)
    for name in ('expires-at-utc','historical-period-start','historical-period-end'):
        stage.add_argument('--'+name,required=True)
    run=commands.add_parser('run-once');run.add_argument('--refresh-submissions',action='store_true')
    close=commands.add_parser('close-stage')
    trigger=commands.add_parser('trigger');trigger.add_argument('--max-invocations',type=int,required=True);trigger.add_argument('--interval-seconds',type=float,default=1)
    stop=commands.add_parser('stop-trigger')
    status=commands.add_parser('trigger-status')
    for p in (run,close,trigger,stop,status):p.add_argument('--approval-url',required=True)
    for p in (init,stage,run,close,trigger,stop,status):p.add_argument('--output-json',type=Path,required=True)
    args=parser.parse_args(argv);output=continuity._external(args.output_json)
    if output.exists():parser.error('Output exists; choose a new evidence filename')
    try:
        with redirect_stdout(sys.stderr):
            if args.command=='initialize-data':result=continuity.initialize_data(data_root=args.data_root)
            elif args.command=='stage-proposal':
                result=continuity.stage_proposal(**{k:v for k,v in vars(args).items() if k not in {'command','output_json'}})
            elif args.command=='run-once':result=continuity.run_once(approval_url=args.approval_url,refresh_submissions=args.refresh_submissions)
            elif args.command=='close-stage':result=continuity.close_stage(approval_url=args.approval_url)
            else:
                from vnext import annual_continuity_trigger as triggers
                if args.command=='trigger':result=triggers.run(approval_url=args.approval_url,max_invocations=args.max_invocations,interval_seconds=args.interval_seconds)
                elif args.command=='stop-trigger':result=triggers.stop(approval_url=args.approval_url)
                else:result=triggers.status(approval_url=args.approval_url)
        code=0 if result.get('status') not in {'CHECK_FAILED','CANDIDATE_UPDATE_FAILED','CREDENTIAL_REQUIRED','INPUTS_MISSING'} else 2
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as error:
        result={'status':'CONTINUITY_STOPPED','error':str(error),'error_type':type(error).__name__,
            'note':'Inspect the same stage budget, native candidate and publication intent; do not reset or retry unknown calls.'}
        code=2
    write_result(output,result);return code

if __name__=='__main__':raise SystemExit(main())
