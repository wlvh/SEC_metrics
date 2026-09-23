#!/usr/bin/env python3
"""Execute exactly one approved Issue28 D04/B13 group on the original ledger."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))

from vnext.canonical import canonical_json_bytes, strict_json_loads, strict_json_file
from vnext.continuous_batch33 import group_for_request, group_id, groups_for, read_authorization
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import (build_plan, execute_capacity_assessment,
    execute_d04_assessment, prepare_requests, request_digest, select_native_request_variants)
from vnext.native_request_construction import request_construction_session
from vnext.requirements import load_requirement_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metric', choices=('D04', 'B13'), required=True)
    parser.add_argument('--company', required=True)
    parser.add_argument('--group-index', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents or output.exists():
        parser.error('Output must be a new file outside the source checkout')
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
    ledger = live_ledger(requirement=requirement)
    with request_construction_session(requirement):
        prepared = prepare_requests(company_id=args.company, metric_id=args.metric,
            native=args.metric=='D04', reference_context=True,
            complete_response_contract=args.metric=='D04',
            program_quantity_roles=args.metric=='B13')
        selected, report = select_native_request_variants(prepared_requests=prepared,
            ledger=ledger, source_references=args.metric=='B13',
            compact_references=args.metric=='B13',
            semantic_role_labels=args.metric=='B13')
    if not 0 <= args.group_index < len(selected):
        parser.error('Group index is outside the complete source partition')
    authorization = read_authorization(ledger)
    expected = [row for row in groups_for(authorization)
        if row['metric_id'] == args.metric and row['company_id'] == args.company
        and row['group_index'] == args.group_index]
    if len(expected) != 1:
        parser.error('The group is outside the exact approved batch')
    prepared_group = selected[args.group_index]
    request = strict_json_loads(text=prepared_group.request_bytes.decode())
    policy, plan = build_plan(prepared_group)
    digest = request_digest(request, policy)
    if group_for_request(authorization=authorization, request=request,
                         request_digest=digest) != group_id(expected[0]):
        parser.error('Current request differs from the approved business group')
    execute = execute_d04_assessment if args.metric == 'D04' else execute_capacity_assessment
    path, outcome = execute(prepared=prepared_group, ledger=ledger)
    intent = strict_json_file(path=path/'intent.json')
    body = {'record_type':'ISSUE28_BATCH33_ONE_GROUP_EXECUTION',
        'metric_id':args.metric,'company_id':args.company,'group_index':args.group_index,
        'request_id':request['request_id'],'request_digest':digest,
        'source_id':request['source_id'],'ledger_ordinal':intent['ordinal'],
        'call_path':str(path),'batch_authorization_id':intent['batch_authorization_id'],
        'batch_group_id':intent['batch_group_id'],
        'batch_attempt_index':intent['batch_attempt_index'],
        'terminal_status':outcome['terminal']['status'],
        'stop_reason':outcome['terminal']['stop_reason'],
        'counts':outcome['terminal']['counts'],
        'native_candidate_evidence_created':outcome['native_candidate_evidence_created'],
        'response_check_error':outcome.get('response_check_error'),
        'company_result_created':False,'production_authorized':False,
        'selected_prior_success_ordinals':[row['original_ordinal'] for row in report
            if row['original_ordinal'] is not None]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(canonical_json_bytes(value=body))
    print(output)
    return 0 if body['terminal_status']=='SUCCEEDED' and not body['stop_reason'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
