"""Compose current-closure Ford B03 plus 34 ordinary Runs, without B06."""
import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
COMPLEMENT = Path('/private/tmp/issue28-ford-b03-complement-20260929/state')
B03 = Path('/private/tmp/issue28-b03-ford-exact-20260929/state-repair')
OUTPUT = Path('/private/tmp/issue28-ford-b03-35-release-20260929')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


from vnext.canonical import strict_json_file
from vnext.ordinary_release_preparation import prepare
from vnext.requirements import load_requirement_snapshot

complement = json.loads((HERE/'complement.json').read_text())
b03 = json.loads((HERE/'private-result.json').read_text())
assert complement['company_status'] == 'UPDATES_READY'
assert len(complement['rows']) == 34
assert all(row['status'] == 'CANDIDATE_READY' for row in complement['rows'])
assert {row['metric_id'] for row in complement['rows']}.isdisjoint({'B03', 'B06'})
assert complement['source_snapshot_id'] == b03['source_snapshot_id']
assert complement['requirement_closure_hash'] == b03['requirement_closure_hash']
assert not OUTPUT.exists()
items = []
pointers = {}
for row in complement['rows']:
    metric = row['metric_id']
    state = COMPLEMENT/'ford_motor_company/metrics'/(
        'C04-registration-v3' if metric == 'C04' else metric)
    pointer = strict_json_file(path=state/'current.json')
    assert pointer['successful_attempt'] is not None
    work = state/'attempts'/pointer['successful_attempt']
    items.append({'data_root': work/'data', 'run_dir': work/'runs'/metric})
    pointers[metric] = {'path': str(state/'current.json'),
                        'sha256': digest(state/'current.json')}
state = B03/'ford_motor_company/metrics/B03'
pointer = strict_json_file(path=state/'current.json')
assert pointer['successful_attempt'] == b03['attempt_id']
work = state/'attempts'/pointer['successful_attempt']
items.append({'data_root': work/'data', 'run_dir': work/'runs/B03'})
pointers['B03'] = {'path': str(state/'current.json'),
                   'sha256': digest(state/'current.json')}
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
    prepared = prepare(native_runs=items, output_root=OUTPUT)
assert before == {key: digest(path) for key, path in originals.items()}
assert all(digest(Path(row['path'])) == row['sha256'] for row in pointers.values())
report = prepared['composition']
selected = report['selected_results']
normal_requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v13')
assert len(selected) == 35
assert {row['company_id'] for row in selected} == {'ford_motor_company'}
assert {row['metric_id'] for row in selected} == set(pointers)
assert all(row['origin'] == 'VERIFIED_ORDINARY_RUN' for row in selected)
assert all(row['requirement_closure_hash'] ==
           normal_requirement['requirement_closure_hash'] for row in selected)
assert next(row for row in selected if row['metric_id'] == 'B03')['result_id'] == \
       b03['result_id']
assert report['public_row_count'] == 327
assert len(report['unselected_coordinate_keys']) == 355
assert not report['full390_acceptance'] and not report['switch_available']
assert not report['production_authorized']
with (OUTPUT/'metrics_matrix.csv').open(newline='') as handle:
    rows = list(csv.DictReader(handle))
ford_b03 = [row for row in rows if row['cik'] == '37996'
            and row['metric_id'] == 'B03']
assert len(ford_b03) == 1 and ford_b03[0]['value'] == b03['value']
body = {'record_type': 'ISSUE28_FORD_B03_CURRENT_CLOSURE_35_PRIVATE_PREPARATION',
    'preparation_id': prepared['preparation_id'],
    'source_snapshot_id': b03['source_snapshot_id'],
    'requirement_closure_hash': b03['requirement_closure_hash'],
    'native_run_closure': normal_requirement['requirement_closure_hash'],
    'selected_metric_ids': [row['metric_id'] for row in selected],
    'selected_result_ids': {row['metric_id']: row['result_id'] for row in selected},
    'ford_b03_row': ford_b03[0], 'public_row_count': 327,
    'unselected_coordinate_count': 355,
    'originals_and_pointers_unchanged': True,
    'new_real_calls': [0, 0, 0], 'full390_acceptance': False,
    'formal_adoption': False}
(HERE/'ford-35-release.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'preparation_id': body['preparation_id'],
    'selected': 35, 'unselected': 355,
    'b03_result_id': b03['result_id'], 'calls': [0, 0, 0]},
    sort_keys=True), flush=True)
