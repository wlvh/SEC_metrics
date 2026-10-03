"""Bound existing complete D03 packet to the current offline interpretation."""
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

PACKET = Path('/private/tmp/issue28-d03-complete-recorded-20260927')
EXPECTED = 'sha256:198ade1a29070ec2737f8372618415e1e1da6b5155b507ea748d5f5550029162'
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')


def no_network(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


ledger = CallLedger(factory=_FACTORY, root=LEDGER,
    binding=strict_json_file(path=LEDGER/'binding.json'), live=True)
with ledger.locked():
    before = ledger.snapshot()
packet_before = hashlib.sha256((PACKET/'packet.json').read_bytes()).hexdigest()
started = time.monotonic()
with original_sources_only(), \
     patch.object(socket.socket, 'connect', side_effect=no_network), \
     patch.object(socket, 'getaddrinfo', side_effect=no_network), \
     patch('sec_http.urlopen', side_effect=no_network):
    result = replay_recorded_complete_interpretation(
        packet_root=PACKET, expected_packet_id=EXPECTED,
        company_id='marriott_international')
    try:
        replay_recorded_complete_interpretation(
            packet_root=PACKET, expected_packet_id='sha256:'+'0'*64,
            company_id='marriott_international')
    except ValueError as error:
        wrong_id = str(error)
    else:
        raise AssertionError('WRONG_PACKET_ID_ACCEPTED')
with ledger.locked():
    after = ledger.snapshot()
packet_after = hashlib.sha256((PACKET/'packet.json').read_bytes()).hexdigest()
assert before['counts'] == after['counts'] == [143, 143, 52]
assert len(before['rows']) == len(after['rows']) == 195
assert packet_before == packet_after
assert result['group_count'] == 5
assert result['unresolved_group_indices'] == list(range(5))
assert all(not row['source_anchor_successor']
           for row in result['request_mapping'])
assert result['proposed_branch'] == 'UNRESOLVED_REQUIRES_REVIEW'
assert result['provider_execution_identity_verified'] is False
assert result['native_result_or_run_created'] is False
assert result['calls'] == [0, 0, 0]
assert wrong_id == 'D03_RECORDED_SET_IDENTITY_OR_CREDIT_CHANGED'
receipt = {key: result[key] for key in (
    'record_type', 'record_id', 'recorded_packet_id', 'company_id',
    'source_id', 'prepared_input_id', 'request_mapping',
    'interpretation_proposal_id', 'group_count',
    'unresolved_group_indices', 'proposed_branch',
    'provider_execution_identity_verified', 'native_result_or_run_created',
    'calls', 'production_authorized')}
receipt.update(recorded_packet_file_sha256=packet_after,
    wrong_packet_id_rejected=wrong_id,
    real_ledger_counts_before_after=[before['counts'], after['counts']],
    real_ledger_rows_before_after=[len(before['rows']), len(after['rows'])],
    packet_root=str(PACKET),
    real_calls=[0, 0, 0],
    seconds=round(time.monotonic()-started, 3))
(HERE/'receipt.json').write_text(json.dumps(receipt,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key: receipt[key] for key in (
    'record_id', 'recorded_packet_id', 'group_count',
    'unresolved_group_indices', 'proposed_branch',
    'wrong_packet_id_rejected', 'real_ledger_counts_before_after',
    'seconds')}, ensure_ascii=False), flush=True)
