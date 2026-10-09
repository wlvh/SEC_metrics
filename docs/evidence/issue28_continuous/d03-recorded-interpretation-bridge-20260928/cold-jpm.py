"""Separate-process cold read of JPM complete synthetic D03 packet."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(REPO), str(REPO/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import strict_json_file
from vnext.continuous_call_ledger import CallLedger, _FACTORY
from vnext.d03_complete_interpretation import (
    replay_recorded_complete_interpretation)

PACKET = Path('/private/tmp/issue28-d03-jpm-recorded-bridge-20260928')
EXPECTED = 'sha256:72536bbfb017dacb048a8549dd93a56f53c6604f4841d26c52324d48a8946972'
RECORD = 'sha256:bd5eaf873ddfa2cefde9ed1c1cf3896370800eb4ccf645e85d038624ad07cdba'
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')


def tree():
    return {str(path.relative_to(PACKET)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PACKET.rglob('*') if path.is_file()}


def no_network(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


before_tree = tree()
ledger = CallLedger(factory=_FACTORY, root=LEDGER,
    binding=strict_json_file(path=LEDGER/'binding.json'), live=True)
with ledger.locked():
    before = ledger.snapshot()
started = time.monotonic()
with original_sources_only(), \
     patch.object(socket.socket, 'connect', side_effect=no_network), \
     patch.object(socket, 'getaddrinfo', side_effect=no_network), \
     patch('sec_http.urlopen', side_effect=no_network):
    result = replay_recorded_complete_interpretation(packet_root=PACKET,
        expected_packet_id=EXPECTED, company_id='jpmorgan_chase')
with ledger.locked():
    after = ledger.snapshot()
after_tree = tree()
assert result['record_id'] == RECORD
assert result['recorded_packet_id'] == EXPECTED
assert result['group_count'] == 38
assert len(result['unresolved_group_indices']) == 38
assert sum(row['source_anchor_successor'] for row in
           result['request_mapping']) == 1
assert before_tree == after_tree
assert before['counts'] == after['counts'] == [143, 143, 52]
assert len(before['rows']) == len(after['rows']) == 195
assert result['provider_execution_identity_verified'] is False
assert result['native_result_or_run_created'] is False
receipt = {'record_type': 'ISSUE28_JPM_D03_COMPLETE_RECORDED_BRIDGE_COLD_READ',
    'status': 'PASS_INDEPENDENT_PROCESS_SAME_PACKET_AND_PROPOSAL',
    'packet_id': EXPECTED, 'record_id': RECORD,
    'group_count': result['group_count'],
    'source_anchor_successor_group_count': 1,
    'unresolved_group_count': len(result['unresolved_group_indices']),
    'proposed_branch': result['proposed_branch'],
    'packet_file_count_before_after': [len(before_tree), len(after_tree)],
    'packet_bytes_unchanged': True,
    'ledger_counts_before_after': [before['counts'], after['counts']],
    'real_calls': [0, 0, 0],
    'native_result_or_run_created': False,
    'production_authorized': False,
    'seconds': round(time.monotonic()-started, 3)}
(HERE/'jpm-cold-result.json').write_text(json.dumps(receipt,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key: receipt[key] for key in (
    'status', 'packet_id', 'record_id', 'group_count',
    'source_anchor_successor_group_count', 'unresolved_group_count',
    'packet_file_count_before_after', 'seconds')}, ensure_ascii=False), flush=True)
