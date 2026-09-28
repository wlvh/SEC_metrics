"""Private, zero-egress preparation of two existing real D04 native Runs."""
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

from vnext.ordinary_release_preparation import prepare
from vnext.canonical import strict_json_file

EVIDENCE = REPO / 'docs/evidence/issue28_continuous/d04-unified-release-20260928'
OUTPUT = Path('/private/tmp/issue28-d04-unified-release-a863-20260928')
STATES = {
    'enphase_energy': Path('/private/tmp/issue28-d04-enphase-normal-b868-20260928/metrics/D04'),
    'paramount_skydance_paramount_global': Path('/private/tmp/issue28-d04-paramount-normal-77f-20260928/metrics/D04'),
}


def tree_hash(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def forbidden(*_args, **_kwargs):
    raise AssertionError('PRIVATE_RELEASE_NETWORK_FORBIDDEN')


def main():
    assert not OUTPUT.exists(), 'OUTPUT_ALREADY_EXISTS'
    selected = []
    before = {}
    for company, state in STATES.items():
        pointer = strict_json_file(path=state / 'current.json')
        identity = pointer['successful_attempt']
        assert identity is not None, company
        work = state / 'attempts' / identity
        terminal = strict_json_file(path=work / 'terminal.json')
        assert terminal['status'] == 'CANDIDATE_READY', company
        assert terminal['metrics']['D04']['native_assessment_completed'] is True, company
        before[company] = {'attempt_id': identity, 'tree_hashes': tree_hash(work)}
        selected.append({'data_root': work / 'data', 'run_dir': work / 'runs/D04'})
    pointer = REPO / 'outputs/active_publication.json'
    active_before = hashlib.sha256(pointer.read_bytes()).hexdigest()
    with patch.object(socket.socket, 'connect', side_effect=forbidden), \
         patch.object(socket, 'getaddrinfo', side_effect=forbidden), \
         patch('sec_http.urlopen', side_effect=forbidden):
        prepared = prepare(native_runs=selected, output_root=OUTPUT)
    active_after = hashlib.sha256(pointer.read_bytes()).hexdigest()
    assert active_before == active_after, 'ACTIVE_POINTER_CHANGED'
    for company, state in STATES.items():
        work = state / 'attempts' / before[company]['attempt_id']
        assert tree_hash(work) == before[company]['tree_hashes'], company
    report = prepared['composition']
    assert report['full390_acceptance'] is False
    assert report['production_authorized'] is False
    assert report['switch_available'] is False
    assert len(report['selected_results']) == 2
    assert {(x['company_id'], x['metric_id']) for x in report['selected_results']} == {
        ('enphase_energy', 'D04'), ('paramount_skydance_paramount_global', 'D04')}
    with (OUTPUT / 'metrics_matrix.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    selected_rows = [r for r in rows if r['metric_id'] == 'D04' and
        r['company'] in {'Enphase Energy', 'Paramount Skydance / Paramount Global'}]
    assert len(selected_rows) == 2, selected_rows
    assert all(r['status'] == 'TEXT_QUAL' and not r['value'] for r in selected_rows)
    result = {'tested_head': 'a863f722324d89f4ee23bc9dd284787b6e18789d',
        'output_root': str(OUTPUT), 'preparation_id': prepared['preparation_id'],
        'selected': [{'company_id': x['company_id'], 'metric_id': x['metric_id'],
            'result_id': x['result_id'], 'run_id': x['run_id'],
            'selection_basis': x['selection_basis']} for x in report['selected_results']],
        'public_row_count': report['public_row_count'],
        'unselected_coordinate_count': len(report['unselected_coordinate_keys']),
        'active_pointer_unchanged': True,
        'original_success_packages_unchanged': True,
        'selected_rows': selected_rows,
        'calls': [0, 0, 0], 'production_authorized': False,
        'full390_acceptance': False}
    (EVIDENCE / 'result.json').write_text(json.dumps(result, ensure_ascii=False,
        indent=2) + '\n')
    print(json.dumps({key: result[key] for key in (
        'preparation_id', 'public_row_count', 'unselected_coordinate_count',
        'selected', 'active_pointer_unchanged')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
