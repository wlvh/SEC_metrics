"""Try one Ford B03 corrected Run in the existing private release preparer."""
import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-b03-ford-exact-20260929/state-repair/ford_motor_company/metrics/B03')
OUTPUT = Path('/private/tmp/issue28-ford-b03-unified-release-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root):
    return {str(path.relative_to(root)): digest(path)
        for path in root.rglob('*') if path.is_file()}


assert not OUTPUT.exists()
from vnext.canonical import strict_json_file
from vnext.ordinary_release_preparation import prepare
current = json.loads((HERE/'private-result.json').read_text())
pointer = strict_json_file(path=STATE/'current.json')
assert pointer['successful_attempt'] == current['attempt_id']
work = STATE/'attempts'/pointer['successful_attempt']
before_run = tree(work)
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
    prepared = prepare(native_runs=[{'data_root': work/'data',
        'run_dir': work/'runs/B03'}], output_root=OUTPUT)
assert tree(work) == before_run
assert before == {key: digest(path) for key, path in originals.items()}
report = prepared['composition']
assert report['full390_acceptance'] is False
assert report['production_authorized'] is False
assert report['switch_available'] is False
assert len(report['selected_results']) == 1
selected = report['selected_results'][0]
assert selected['company_id'] == 'ford_motor_company'
assert selected['metric_id'] == 'B03'
assert selected['result_id'] == current['result_id']
with (OUTPUT/'metrics_matrix.csv').open(newline='') as handle:
    rows = list(csv.DictReader(handle))
matched = [row for row in rows if row['metric_id'] == 'B03'
           and row['cik'] == '37996']
assert len(matched) == 1
assert matched[0]['value'] == current['value']
body = {'record_type': 'ISSUE28_FORD_B03_EXACT_PRIVATE_RELEASE_PREPARATION',
    'preparation_id': prepared['preparation_id'],
    'selected_result_id': selected['result_id'],
    'selected_run_id': selected['run_id'],
    'selected_origin': selected['origin'],
    'selected_row': matched[0],
    'public_row_count': report['public_row_count'],
    'unselected_coordinate_count': len(report['unselected_coordinate_keys']),
    'original_run_and_ledger_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'full390_acceptance': False,
    'formal_adoption': False}
(HERE/'release.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'preparation_id': body['preparation_id'],
    'result_id': body['selected_result_id'],
    'origin': body['selected_origin'],
    'public_rows': body['public_row_count'],
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
