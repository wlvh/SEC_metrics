"""Make one current-rule private copy of the unchanged #28 acquisition root."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
PRIVATE = Path('/private/tmp/issue28-b03-ford-exact-20260929')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import (
        current_processing_source, verify_processing_source)
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    created = current_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        output_parent=PRIVATE/'sources', requirement=requirement)
    verified = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=created['data_root'], requirement=requirement)
assert before == {key: digest(path) for key, path in originals.items()}
assert created['snapshot_id'] == verified['snapshot_id']
body = {'record_type': 'ISSUE28_B03_FORD_EXACT_PRIVATE_PROCESSING_SOURCE',
    'source_snapshot_id': created['snapshot_id'],
    'processing_root': str(created['data_root']),
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'created_new_copy': not created['reused'],
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'native_result_created': False,
    'formal_adoption': False}
(HERE/'processing.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'snapshot_id': created['snapshot_id'],
    'path': str(created['data_root']), 'reused': created['reused'],
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
