import json
import socket
import subprocess
import time
from pathlib import Path

from vnext.d03_model_processing import read_development_company_assessment

HERE = Path(__file__).resolve().parent


def forbidden(*args, **kwargs):
    raise AssertionError('NETWORK_AND_SUBPROCESS_FORBIDDEN')


socket.socket = forbidden
socket.create_connection = forbidden
subprocess.Popen = forbidden
subprocess.run = forbidden
saved = json.loads((HERE/'build-summary.json').read_text())
start = time.monotonic()
out = read_development_company_assessment(directory=saved['output'], data_root=saved['data_root'],
    company_id='marriott_international', expected_candidate_hash=saved['candidate_hash'],
    expected_review_unit_hash=saved['unit_hash'])
assert out['records'][1]['candidate_hash'] == saved['candidate_hash']
assert out['records'][3]['review_unit_hash'] == saved['unit_hash']
assert out['records'][3]['status'] == 'PENDING'
assert out['records'][3]['system_approval_eligible'] is False
report = {'candidate_hash': saved['candidate_hash'], 'unit_hash': saved['unit_hash'],
    'request_count': len(out['processing']['rows']),
    'findings': sum(len(r['original_response']['findings']) for r in out['processing']['rows']),
    'unresolved': sum(len(r['original_response']['unresolved']) for r in out['processing']['rows']),
    'seconds': round(time.monotonic()-start, 3), 'native_credit': False, 'new_calls': [0, 0, 0]}
(HERE/'cold-summary.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
