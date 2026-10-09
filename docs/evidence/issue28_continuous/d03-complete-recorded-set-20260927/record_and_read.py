"""Separate-process recorded D03 packet proof; synthetic answers have no credit."""
import json
from pathlib import Path
import sys

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.continuous_request_context import FORMAT_VERSION
from vnext.d03_recorded_response_set import (
    record_offline_set, replay_offline_set)
from vnext.normal_source_authority import ROOT
from vnext.r6_regulatory_semantics import (
    prepare_regulatory_semantic_source, requests_from_source)


def record(root):
    source = prepare_regulatory_semantic_source(repo_root=ROOT,
        company_id='marriott_international',
        request_context_format=FORMAT_VERSION)
    requests = requests_from_source(source)
    responses = {}
    for request in requests:
        units = []
        for unit in request['units']:
            context = [row['source_index'] for row in
                request['required_candidate_assessments']
                if row['unit_id'] == unit['unit_id']]
            units.append({'unit_id': unit['unit_id'], 'reviewed': True,
                'findings': [], 'context_only_source_indices': context,
                'unresolved': ['Synthetic recorded test; no semantic conclusion.']})
        responses[request['request_id']] = (
            json.dumps({'request_id': request['request_id'], 'units': units},
                       ensure_ascii=False, indent=2) + '\n').encode()
    result = record_offline_set(output_root=root, source=source,
        responses_by_original_id=responses)
    return {'status': 'RECORDED_ONLY', 'company_id': source['company_id'],
        'source_id': source['semantic_source_id'], **result}


def read(root, expected):
    result = replay_offline_set(packet_root=root, expected_packet_id=expected)
    return {'status': 'INDEPENDENT_PROCESS_COLD_READ_PASS',
        'packet_id': result['packet_id'],
        'request_count': result['request_count'],
        'unresolved_request_count': result['unresolved_request_count'],
        'calls': result['calls'],
        'native_result_created': result['native_result_created']}


if __name__ == '__main__':
    mode, root = sys.argv[1], Path(sys.argv[2]).resolve()
    with original_sources_only():
        value = record(root) if mode == 'record' else read(root, sys.argv[3])
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
