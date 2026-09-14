#!/usr/bin/env python3
"""Prepare or execute one explicitly bound D03/D04 feasibility request."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.canonical import canonical_json_bytes,strict_json_loads
from vnext.continuous_semantic_calls import prepare_requests,build_plan,execute_feasibility,execute_capacity_assessment
from vnext.continuous_call_ledger import live_ledger


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','execute','verify'])
    parser.add_argument('--company',required=True)
    parser.add_argument('--metric',choices=['B13','D03','D04'],default='D04')
    parser.add_argument('--prior-call',type=int)
    parser.add_argument('--control-id')
    parser.add_argument('--request-id')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    output=args.output.resolve()
    if output==ROOT or ROOT in output.parents or output.exists():
        parser.error('Output must be a new file outside the source checkout')
    if args.command=='verify' and (args.metric!='D03' or args.prior_call is None):
        parser.error('Verify requires --metric D03 and one --prior-call ordinal')
    requests=prepare_requests(company_id=args.company,metric_id=args.metric,prior_call_ordinal=args.prior_call,control_id=args.control_id)
    if args.command in {'execute','verify'}:
        selected=(requests if args.command=='verify' else
                  [p for p in requests if strict_json_loads(text=p.request_bytes.decode())['request_id']==args.request_id])
        if len(selected)!=1:parser.error('Execute requires one exact prepared request id')
        ledger=live_ledger(requirement=selected[0].requirement)
        execute = execute_capacity_assessment if args.metric == 'B13' else execute_feasibility
        path,observed=execute(prepared=selected[0],ledger=ledger)
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('xb') as file:
            file.write(canonical_json_bytes(value={'call_path':str(path),'outcome':observed}))
        print(output)
        if args.command=='verify' and not observed.get('response_check',{}).get('all_proposals_supported',False):
            return 2
        return 0 if 'response_check' in observed and not observed['terminal']['stop_reason'] else 2
    rows=[]
    for prepared in requests:
        request=strict_json_loads(text=prepared.request_bytes.decode())
        row={'request_id':request['request_id'],'document_id':request['document_context']['document_id'],
             'unit_ids':[u['unit_id'] for u in request['units']],
             'unit_kinds':[u['kind'] for u in request['units']],
             'request_bytes':len(prepared.provider_request_body_bytes)}
        try:
            _,plan=build_plan(prepared)
            row.update(status='REQUEST_PREPARED',estimated_context_tokens=plan['observability']['estimated_context_tokens'])
        except ValueError as error:row.update(status='REQUEST_NOT_READY',reason=str(error))
        rows.append(row)
    result={'company_id':args.company,'metric_id':args.metric,'requests':rows,
        'calls':{'provider':0,'paid':0,'sec':0},'semantic_correctness_verified':False,'production_authorized':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as file:file.write(canonical_json_bytes(value=result))
    print(output)
    return 0


if __name__=='__main__':raise SystemExit(main())
