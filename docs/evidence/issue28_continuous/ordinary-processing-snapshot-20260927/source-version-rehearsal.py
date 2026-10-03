"""Recorded source-ledger advance; current processing copies keep Run history."""
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from sec_urls import submissions_url
from vnext.continuous_sec_acquisition import (
    initialize_source_inputs, recorded_sec_session)
from vnext.ordinary_refresh_cycle import refresh_and_process
from vnext.normal_source_authority import ROOT
from vnext.canonical import strict_json_file

ROOT_OUT = Path('/private/tmp/issue28-processing-version-rehearsal-20260927')
assert not ROOT_OUT.exists()
session = recorded_sec_session(root=ROOT_OUT/'ledger', response=b'RECORDED_ONLY')
with session.ledger.locked():
    pass
initialize_source_inputs(root=session.data_root, requirement=session.requirement)
policy = session.data_root/'config/issue28_normal_results_v2.json'
old_policy = json.loads(policy.read_text())
old_policy['freeze_enabled'] = not old_policy['freeze_enabled']
policy.write_text(json.dumps(old_policy, ensure_ascii=False) + '\n')
state = ROOT_OUT/'state'
active = ROOT/'outputs/active_publication.json'
active_before = hashlib.sha256(active.read_bytes()).hexdigest()


def run():
    return refresh_and_process(session=session, state_root=state,
        company_ids=['salesforce'], metric_ids=['B01', 'C04'],
        max_sec_requests=0, max_provider_requests=0, c04_successor=True)


with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen',
           side_effect=AssertionError('HTTP_FORBIDDEN')):
    first = run()
    first_metrics = {m['metric_id']: m for m in
        first['companies'][0]['updates']['metrics']}
    assert first_metrics['B01']['status'] == 'CANDIDATE_READY'
    successful = first_metrics['B01']['successful_attempt']
    # This is an identical recorded metadata response, never a forged earlier
    # HTTP snapshot or real SEC credit. It changes the source-ledger version.
    current = ROOT/'evidence/request_attempts/fe/fec572bf941ad9aa543f5aa82c563227a0409486a12f0e1fad9a6e7fde59a911/CIK0001108524.json'
    session.response = current.read_bytes()
    capture = session.capture(company_id='salesforce',
        url=submissions_url(cik=1108524), refresh_metadata=True,
        source_only_c04=True)
    assert capture['status'] == 'SUCCEEDED'
    second = run()
    second_metrics = {m['metric_id']: m for m in
        second['companies'][0]['updates']['metrics']}

assert second_metrics['B01']['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert second_metrics['B01']['successful_attempt'] == successful
assert not second_metrics['B01']['new_candidate_created']
assert first['current_processing_source_snapshot_id'] != second[
    'current_processing_source_snapshot_id']
assert hashlib.sha256(active.read_bytes()).hexdigest() == active_before
print(json.dumps({'record_type': 'ISSUE28_RECORDED_PROCESSING_SOURCE_VERSION_REHEARSAL',
    'company_id': 'salesforce', 'metric_ids': ['B01', 'C04'],
    'first_snapshot_id': first['current_processing_source_snapshot_id'],
    'second_snapshot_id': second['current_processing_source_snapshot_id'],
    'first_b01_status': first_metrics['B01']['status'],
    'second_b01_status': second_metrics['B01']['status'],
    'successful_b01_attempt_unchanged': True,
    'second_b01_candidate_created': False,
    'recorded_capture_status': capture['status'],
    'recorded_ledger_counts': second['ledger_counts_after'],
    'actual_calls': second['calls'],
    'old_response_fabricated': False,
    'active_pointer_unchanged': True,
    'complete_39_update_proven': False,
    'production_authorized': False}, sort_keys=True))
