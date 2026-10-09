"""Contrast the old D03 summary predicate with the repaired one, offline."""
import hashlib
import json
import socket
from pathlib import Path
from unittest.mock import patch

from vnext import d03_complete_interpretation as interpretation
from vnext.canonical import canonical_json_bytes
from vnext.d03_complete_interpretation import validate_complete_interpretation
from vnext.d03_native_preparation import prepare_native_input


with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN')):
    prepared = prepare_native_input(company_id='marriott_international')
    responses = {}
    for group in prepared['groups']:
        request = group['effective_request']
        units = []
        for unit in request['units']:
            required = sorted({item['source_index'] for item in
                request['required_candidate_assessments']
                if item['unit_id'] == unit['unit_id']})
            units.append({'unit_id': unit['unit_id'], 'reviewed': True,
                'findings': [], 'context_only_source_indices': required,
                'unresolved': []})
        responses[request['request_id']] = canonical_json_bytes(value={
            'request_id': request['request_id'], 'units': units})
    checked = validate_complete_interpretation(prepared_input=prepared,
        response_bytes_by_request=responses)
    old_unresolved = [row['group_index'] for row in checked['group_rows']
        if row['unresolved'] or any(finding['kind'] == 'UNRESOLVED'
            or finding['subject'] == 'UNRESOLVED'
            or finding['timing'] == 'UNRESOLVED'
            for finding in row['findings'])]
    assert old_unresolved and checked['unresolved_group_indices'] == []
    assert checked['proposed_branch'] == 'ABSENCE_RULE_NOT_APPROVED'
    assert not checked['provider_execution_identity_verified']
    assert not checked['native_result_or_run_created']
    print(json.dumps({'actual_saved_source_id': prepared['source_id'],
        'effective_group_count': len(prepared['groups']),
        'old_predicate_false_unresolved_groups': old_unresolved,
        'repaired_unresolved_groups': checked['unresolved_group_indices'],
        'repaired_proposed_branch': checked['proposed_branch'],
        'provider_execution_identity_verified': False,
        'native_result_or_run_created': False,
        'semantic_classification_verified': False,
        'response_origin': 'SYNTHETIC_CONTEXT_ONLY_ANSWER_ON_SAVED_SOURCE',
        'module_sha256': hashlib.sha256(Path(
            interpretation.__file__).read_bytes()).hexdigest()}, sort_keys=True))
