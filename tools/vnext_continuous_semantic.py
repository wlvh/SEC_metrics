#!/usr/bin/env python3
"""Prepare or execute one explicitly bound D04 feasibility request."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.canonical import canonical_json_bytes,strict_json_loads
from vnext.continuous_semantic_calls import prepare_requests,build_plan,execute_feasibility
from vnext.continuous_call_ledger import live_ledger


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','execute'])
    parser.add_argument('--company',required=True)
    parser.add_argument('--request-id')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    output=args.output.resolve()
    if output==ROOT or ROOT in output.parents or output.exists():
        parser.error('Output must be a new file outside the source checkout')
    requests=prepare_requests(company_id=args.company)
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
    result={'company_id':args.company,'metric_id':'D04','requests':rows,
        'calls':{'provider':0,'paid':0,'sec':0},'semantic_correctness_verified':False,'production_authorized':False}
    if args.command=='execute':
        selected=[p for p in requests if strict_json_loads(text=p.request_bytes.decode())['request_id']==args.request_id]
        if len(selected)!=1:parser.error('Execute requires one exact prepared request id')
        ledger=live_ledger(requirement=selected[0].requirement)
        path,observed=execute_feasibility(prepared=selected[0],ledger=ledger)
        result={'call_path':str(path),'outcome':observed}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as file:file.write(canonical_json_bytes(value=result))
    print(output)
    return 0


if __name__=='__main__':raise SystemExit(main())
