"""Reopen the 35-coordinate Ford private preparation in another process."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUTPUT = Path('/private/tmp/issue28-ford-b03-35-release-20260929')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

expected = json.loads((HERE/'ford-35-release.json').read_text())
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    from vnext.ordinary_release_preparation import verify
    checked = verify(preparation_root=OUTPUT,
                     expected_preparation_id=expected['preparation_id'])
report = checked['composition']
selected = report['selected_results']
assert len(selected) == 35
assert {row['company_id'] for row in selected} == {'ford_motor_company'}
assert {row['metric_id']: row['result_id'] for row in selected} == \
       expected['selected_result_ids']
assert all(row['requirement_closure_hash'] ==
           expected['native_run_closure'] for row in selected)
assert len(report['unselected_coordinate_keys']) == 355
assert report['full390_acceptance'] is False
assert report['production_authorized'] is False
assert report['switch_available'] is False
body = {'record_type': 'ISSUE28_FORD_B03_CURRENT_CLOSURE_35_PRIVATE_COLD_READ',
    'preparation_id': checked['preparation_id'],
    'selected_count': 35, 'unselected_coordinate_count': 355,
    'package_file_count': len(checked['files']) + 1,
    'package_bytes_verified_unchanged': True,
    'ford_b03_result_id': expected['selected_result_ids']['B03'],
    'new_real_calls': [0, 0, 0], 'full390_acceptance': False,
    'formal_adoption': False}
(HERE/'ford-35-cold.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'preparation_id': body['preparation_id'],
    'selected': 35, 'file_count': body['package_file_count'],
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
