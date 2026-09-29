"""Independently reopen one Ford B03 private complete-version preparation."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUTPUT = Path('/private/tmp/issue28-ford-b03-unified-release-20260929')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def tree(root):
    return {str(path.relative_to(root)):
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob('*') if path.is_file()}


prepared = json.loads((HERE/'release.json').read_text())
before = tree(OUTPUT)
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    from vnext.ordinary_release_preparation import verify
    checked = verify(preparation_root=OUTPUT,
        expected_preparation_id=prepared['preparation_id'])
after = tree(OUTPUT)
assert before == after
report = checked['composition']
assert len(report['selected_results']) == 1
assert report['selected_results'][0]['result_id'] == \
       prepared['selected_result_id']
assert report['full390_acceptance'] is False
assert report['production_authorized'] is False
body = {'record_type': 'ISSUE28_FORD_B03_EXACT_PRIVATE_RELEASE_COLD_READ',
    'preparation_id': checked['preparation_id'],
    'file_count': len(after), 'package_bytes_unchanged': True,
    'selected_result_id': prepared['selected_result_id'],
    'full390_acceptance': False,
    'new_real_calls': [0, 0, 0],
    'formal_adoption': False}
(HERE/'release-cold.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'preparation_id': body['preparation_id'],
    'file_count':body['file_count'],
    'result_id':body['selected_result_id'],
    'calls':[0,0,0]},sort_keys=True),flush=True)
