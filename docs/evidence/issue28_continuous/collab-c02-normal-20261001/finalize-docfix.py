"""Cold-read the completed update after the wording-only receipt assumed a stable Result ID."""
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext import ordinary_update_cycle as cycle
from vnext.specs import compile_spec_file

STATE = Path('/private/tmp/issue28-c02-normal-update-enphase-docfix-20261001')
metric_root = STATE / 'metrics/C02'
old_state = Path('/private/tmp/issue28-c02-normal-update-enphase-877-20261001')
old_run = (old_state / 'metrics/C02/attempts/7e227d5829a64faa905910ad74beb27f/runs/C02')
old_manifest = json.loads((old_run / 'manifest.json').read_text())
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    config = cycle._config(metric_root, ROOT, 'enphase_energy', ['C02'], 'LIVE')
    state = cycle._state(metric_root, config)
    assert state['successful_attempt'] is not None
    success = cycle._terminal(metric_root, state['successful_attempt'])
    latest = cycle._terminal(metric_root, state['latest_attempt'])
    result = cycle._verify_candidate(metric_root, success, config)['C02']
assert success['status'] == 'CANDIDATE_READY'
assert latest['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
run = metric_root / 'attempts' / state['successful_attempt'] / 'runs/C02'
manifest = json.loads((run / 'manifest.json').read_text())
records = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
candidate = next(r for r in records if r['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
blocks = {r['block_index'] for r in candidate['selected'].values()}
assert len(blocks) == 54 and 294 not in blocks and 210 in blocks and 415 in blocks
spec = 'catalog/r6/C02_board_disclosures_v2.md'
assert manifest['spec_file_hashes'][spec] != old_manifest['spec_file_hashes'][spec]
assert manifest['requirement_closure_hash'] != old_manifest['requirement_closure_hash']
old_spec = compile_spec_file(path=old_run.parent.parent / 'data' / spec, dependency_specs={})
new_spec = compile_spec_file(path=ROOT / spec, dependency_specs={})
assert all(old_spec[key] == new_spec[key] for key in (
    'compiled', 'spec_semantic_hash', 'prompt_bundle_hash', 'spec_closure_hash'))
prior = json.loads((HERE / 'enphase-update-877.json').read_text())
assert result['result_id'] != prior['result_id']
source_log = 'evidence/requests_log.csv'
assert (subprocess.check_output(['git', 'hash-object', source_log], cwd=ROOT, text=True).strip()
        == subprocess.check_output(['git', 'rev-parse', 'HEAD:' + source_log], cwd=ROOT, text=True).strip())
body = {'record_type': 'ISSUE28_C02_DOCFIX_UPDATE_COLD_READ',
        'company_id': 'enphase_energy', 'selected_composition_fact_count': len(blocks),
        'first_status': success['status'], 'repeat_status': latest['status'],
        'run_id': manifest['run_id'], 'result_id': result['result_id'],
        'prior_e17_result_id_retained': prior['result_id'],
        'spec_file_hash_changed': True, 'requirement_closure_changed': True,
        'old_compiled_spec_semantics_unchanged': True,
        'source_log_unchanged': True, 'calls': [0, 0, 0],
        'production_authorized': False,
        'first_receipt_script_error': 'enphase-update-docfix.log expected an identical Result ID after the Requirement closure changed; the update itself had succeeded'}
(HERE / 'enphase-update-docfix.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'run_id': manifest['run_id'], 'result_id': result['result_id'],
                  'first': success['status'], 'repeat': latest['status'],
                  'selected': len(blocks)}, sort_keys=True))
