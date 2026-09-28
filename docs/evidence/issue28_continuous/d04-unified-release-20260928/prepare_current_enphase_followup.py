"""Prepare one current-bound real D04 Result in the existing private version."""
import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]

from vnext.canonical import strict_json_file
from vnext.ordinary_release_preparation import prepare

HERE = REPO / 'docs/evidence/issue28_continuous/d04-unified-release-20260928'
STATE = Path('/private/tmp/issue28-d04-enphase-release-current-dea6-20260928/metrics/D04')
OUTPUT = Path('/private/tmp/issue28-d04-unified-release-current-enphase-dea6-20260928')


def tree(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def forbidden(*_args, **_kwargs):
    raise AssertionError('PRIVATE_VERSION_NETWORK_FORBIDDEN')


def main():
    assert not OUTPUT.exists(), 'PRIVATE_VERSION_OUTPUT_ALREADY_EXISTS'
    current = json.loads((HERE / 'current-enphase-followup-result.json').read_text())
    assert current['status'] == 'CANDIDATE_READY' and current['old_result_id'] == current['current_result_id']
    pointer = strict_json_file(path=STATE / 'current.json')
    work = STATE / 'attempts' / pointer['successful_attempt']
    prior = tree(work)
    active = REPO / 'outputs/active_publication.json'
    active_before = hashlib.sha256(active.read_bytes()).hexdigest()
    with patch.object(socket.socket, 'connect', side_effect=forbidden), \
         patch.object(socket, 'getaddrinfo', side_effect=forbidden), \
         patch('sec_http.urlopen', side_effect=forbidden):
        prepared = prepare(native_runs=[{'data_root': work / 'data',
            'run_dir': work / 'runs/D04'}], output_root=OUTPUT)
    report = prepared['composition']
    assert hashlib.sha256(active.read_bytes()).hexdigest() == active_before
    assert tree(work) == prior, 'CURRENT_D04_RUN_CHANGED_DURING_PREPARATION'
    assert report['full390_acceptance'] is False and report['production_authorized'] is False
    assert report['switch_available'] is False and len(report['selected_results']) == 1
    selected = report['selected_results'][0]
    assert selected['company_id'] == 'enphase_energy' and selected['metric_id'] == 'D04'
    assert selected['result_id'] == current['current_result_id']
    assert selected['selection_basis'] == 'NATIVE_REVIEWED_DEFINED_SCOPE_STATEMENT'
    with (OUTPUT / 'metrics_matrix.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    matched = [row for row in rows if row['company'] == 'Enphase Energy'
               and row['metric_id'] == 'D04']
    assert len(matched) == 1 and matched[0]['status'] == 'TEXT_QUAL'
    assert matched[0]['value'] == ''
    result = {'tested_head': 'dea6e4a0',
        'output_root': str(OUTPUT),
        'preparation_id': prepared['preparation_id'],
        'selected_result_id': selected['result_id'],
        'selected_run_id': selected['run_id'],
        'selected_basis': selected['selection_basis'],
        'selected_row': matched[0],
        'public_row_count': report['public_row_count'],
        'unselected_coordinate_count': len(report['unselected_coordinate_keys']),
        'active_pointer_unchanged': True,
        'current_run_package_unchanged': True,
        'full390_acceptance': False,
        'new_real_calls': [0, 0, 0],
        'production_authorized': False}
    (HERE / 'current-preparation-followup-result.json').write_text(json.dumps(result,
        ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('preparation_id',
        'selected_result_id', 'selected_run_id', 'selected_basis',
        'public_row_count', 'unselected_coordinate_count')},
        ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
