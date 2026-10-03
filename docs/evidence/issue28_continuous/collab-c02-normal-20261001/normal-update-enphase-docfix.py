"""Exercise the ordinary update controller's explicit C02 route without network."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import sha256_file
from vnext.ordinary_update_cycle import run_company

STATE = Path('/private/tmp/issue28-c02-normal-update-enphase-docfix-20261001')
assert not STATE.exists()
source_log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=source_log)
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    first = run_company(state_root=STATE, source_root=ROOT,
        company_id='enphase_energy', metric_ids=['C02'])
    second = run_company(state_root=STATE, source_root=ROOT,
        company_id='enphase_energy', metric_ids=['C02'])
assert before == sha256_file(path=source_log)
one, two = first['metrics'][0], second['metrics'][0]
assert first['status'] == second['status'] == 'UPDATES_READY'
assert one['status'] == 'CANDIDATE_READY'
assert two['status'] == 'NO_SOURCE_CONTENT_CHANGE'
result = one['last_verified_candidate']['results']['C02']
expected = json.loads((HERE / 'enphase-update-877.json').read_text())
assert result['result_id'] == expected['result_id']
assert two['successful_attempt'] == one['successful_attempt']
run = STATE / 'metrics/C02/attempts' / one['successful_attempt'] / 'runs/C02'
records = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
candidate = next(r for r in records if r['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
blocks = {r['block_index'] for r in candidate['selected'].values()}
assert len(blocks) == 54 and 294 not in blocks and 210 in blocks and 415 in blocks
manifest = json.loads((run / 'manifest.json').read_text())
old_run = (Path('/private/tmp/issue28-c02-normal-update-enphase-877-20261001')
           / 'metrics/C02/attempts/7e227d5829a64faa905910ad74beb27f/runs/C02')
old_manifest = json.loads((old_run / 'manifest.json').read_text())
spec_path = 'catalog/r6/C02_board_disclosures_v2.md'
assert manifest['spec_file_hashes'][spec_path] != old_manifest['spec_file_hashes'][spec_path]
assert manifest['requirement_closure_hash'] != old_manifest['requirement_closure_hash']
body = {'record_type': 'ISSUE28_C02_COMPOSITION_NORMAL_UPDATE',
        'company_id': 'enphase_energy', 'first_status': one['status'],
        'repeat_status': two['status'], 'result_id': result['result_id'],
        'same_successful_attempt_on_repeat': True,
        'selected_composition_fact_count': len(blocks),
        'new_unlabelled_committee_card_block_415': True,
        'result_identity_equal_to_877_before_wording_fix': True,
        'spec_file_hash_changed': True,
        'requirement_closure_changed': True,
        'original_source_log_unchanged': True,
        'calls': [0, 0, 0], 'production_authorized': False}
(HERE / 'enphase-update-docfix.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
