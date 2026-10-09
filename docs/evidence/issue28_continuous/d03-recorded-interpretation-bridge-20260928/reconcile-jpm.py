"""Short mechanical reconciliation of the saved JPM packet and cold read."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO/'scripts')]
from vnext.canonical import content_hash

PACKET = Path('/private/tmp/issue28-d03-jpm-recorded-bridge-20260928')


def read(path):
    return json.loads(path.read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


first = read(HERE/'jpm-recorded-summary.json')
cold = read(HERE/'jpm-cold-result.json')
packet = read(PACKET/'packet.json')
body = {key: value for key, value in packet.items() if key != 'packet_id'}
assert packet['packet_id'] == first['packet_id'] == cold['packet_id'] == \
    content_hash(value=body)
assert first['record_id'] == cold['record_id']
assert first['source_id'] == packet['source_id']
assert packet['request_count'] == len(packet['rows']) == \
    first['group_count'] == cold['group_count'] == 38
assert sum(row['source_anchor_successor'] for row in packet['rows']) == 1
assert first['successor_mapping'][0]['original_request_id'] != \
    first['successor_mapping'][0]['effective_request_id']
assert packet['provider_execution_credit'] == 'RECORDED_TEST_ONLY'
assert packet['native_result_created'] is False
assert packet['calls'] == [0, 0, 0]
source = (PACKET/'source.json').read_bytes()
assert len(source) == packet['source_size']
assert sha(source) == packet['source_sha256']
for row in packet['rows']:
    raw = (PACKET/row['response_file']).read_bytes()
    assert len(raw) == row['response_size']
    assert sha(raw) == row['response_sha256']
assert cold['packet_file_count_before_after'] == [40, 40]
assert cold['packet_bytes_unchanged'] is True
assert first['real_ledger_counts_before_after'] == \
    cold['ledger_counts_before_after'] == [[143, 143, 52], [143, 143, 52]]
assert first['unresolved_group_count'] == cold['unresolved_group_count'] == 38
assert first['native_result_or_run_created'] is False
assert cold['native_result_or_run_created'] is False
assert first['real_calls'] == cold['real_calls'] == [0, 0, 0]
report = {'record_type': 'ISSUE28_JPM_D03_RECORDED_BRIDGE_RECONCILIATION',
    'status': 'PASS_PACKET_BYTES_AND_TWO_PROCESS_IDENTITIES_BOUND',
    'packet_id': first['packet_id'], 'record_id': first['record_id'],
    'request_count': 38, 'successor_group_count': 1,
    'unresolved_group_count': 38,
    'packet_file_count': 40,
    'first_process_seconds': first['seconds'],
    'cold_process_seconds': cold['seconds'],
    'real_calls': [0, 0, 0],
    'model_semantics_proven': False,
    'native_result_or_run_created': False}
(HERE/'jpm-reconciliation.json').write_text(json.dumps(report,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False))
