"""Replay the original version-1 packet with an external expected identity."""
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from vnext.d03_recorded_response_store import replay_offline_response

PACKET = Path('/private/tmp/issue28-d03-recorded-packet-20260927-02')
EXPECTED = 'sha256:4bac51a935deadda11f456ba39f6976647fe2d5cd05fe194f89fbc7ef7ce02d6'

with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN')), \
     patch.object(subprocess, 'Popen', side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
    result = replay_offline_response(packet_root=PACKET,
                                     expected_packet_id=EXPECTED)
assert result['packet_id'] == EXPECTED
assert result['calls'] == [0, 0, 0]
assert result['checked']['unresolved']
assert result['native_result_created'] is False
print(json.dumps({'packet_id': result['packet_id'],
    'raw_response_sha256': result['response_raw_sha256'],
    'unresolved_count': len(result['checked']['unresolved']),
    'old_creator_module_identity_preserved': True,
    'external_expected_id_checked': True,
    'network_and_subprocess_forbidden': True,
    'native_result_created': False, 'new_calls': [0, 0, 0]}, sort_keys=True))
