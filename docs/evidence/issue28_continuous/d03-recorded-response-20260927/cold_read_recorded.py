"""Cold-read the saved D03 recorded packet without network or subprocesses."""
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from vnext.d03_recorded_response_store import replay_offline_response


PACKET = Path('/private/tmp/issue28-d03-recorded-packet-20260927-02')


def main():
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         patch.object(subprocess, 'Popen',
                      side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
        result = replay_offline_response(packet_root=PACKET)
    raw = result['raw_response_bytes']
    assert raw == (PACKET/'raw-response.bin').read_bytes()
    assert '\u037e'.encode('utf-8') in raw
    assert result['checked']['unresolved']
    assert not result['native_result_created']
    assert result['calls'] == [0, 0, 0]
    print(json.dumps({'status': 'PASS_D03_RAW_RECORDED_RESPONSE_COLD_READ',
        'packet_id': result['packet_id'],
        'raw_response_sha256': result['response_raw_sha256'],
        'raw_response_bytes': len(raw), 'u037e_preserved': True,
        'unresolved_count': len(result['checked']['unresolved']),
        'network_and_subprocess_forbidden': True,
        'native_result_created': False, 'new_real_calls': [0, 0, 0],
        'production_authorized': False}, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
