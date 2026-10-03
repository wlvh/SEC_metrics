"""Check the known Paramount original through D03's current offline factory."""
from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))

from vnext.canonical import strict_json_loads
from vnext.continuous_semantic_calls import (
    _json, build_plan, prepare_d03_replay_only_requests,
    validate_source_unit_bytes,
)


with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(
                  socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    rows = prepare_d03_replay_only_requests(
        company_id='paramount_skydance_paramount_global')
    source = strict_json_loads(text=rows[0].source_bytes.decode())
    assert len(rows) == 14 and len(source['units']) == 51
    assert all(row.replay_only and row.source_bytes == rows[0].source_bytes
               for row in rows)
    validate_source_unit_bytes(source)
    selected = next(row for row in rows if ';' in row.request_bytes.decode())
    policy, plan = build_plan(selected)
    request = strict_json_loads(text=selected.request_bytes.decode())
    envelope = json.loads(selected.provider_request_body_bytes)
    sent = json.loads(envelope['messages'][1]['content'])
    assert sent['units'] == request['units']
    assert selected.source_bytes.count(';'.encode()) == 4
    assert selected.request_bytes.count(';'.encode()) == 4
    assert selected.provider_request_body_bytes.count(';'.encode()) == 4
    try:
        build_plan(replace(selected, source_bytes=_json(source)))
    except ValueError as error:
        assert 'CONTINUOUS_SOURCE_UNIT_SERIALIZATION_CHANGED' in str(error)
    else:
        raise AssertionError('LOSSY_SOURCE_WAS_ACCEPTED')
    print(json.dumps({
        'status': 'PASS', 'company_id': source['company_id'],
        'groups': len(rows), 'source_units': len(source['units']),
        'original_u037e_count': selected.source_bytes.count(';'.encode()),
        'request_u037e_count': selected.request_bytes.count(';'.encode()),
        'wire_u037e_count': selected.provider_request_body_bytes.count(';'.encode()),
        'context_tokens': plan['observability']['estimated_context_tokens'],
        'lossy_copy_rejected_before_claim': True,
        'execution_entry_called': False, 'real_calls': [0, 0, 0],
        'semantic_answer_verified': False, 'native_result_created': False,
    }, sort_keys=True))
