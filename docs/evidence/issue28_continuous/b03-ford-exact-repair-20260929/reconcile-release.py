"""Read the saved preparation after the first reporting-script field error."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path('/private/tmp/issue28-ford-b03-unified-release-20260929')
saved = json.loads((OUTPUT/'ordinary_release_preparation.json').read_text())
report = saved['composition']
current = json.loads((HERE/'private-result.json').read_text())
assert report['full390_acceptance'] is False
assert report['switch_available'] is False
assert report['production_authorized'] is False
assert len(report['selected_results']) == 1
selected = report['selected_results'][0]
assert selected['company_id'] == 'ford_motor_company'
assert selected['metric_id'] == 'B03'
assert selected['origin'] == 'VERIFIED_ORDINARY_RUN'
assert selected['result_id'] == current['result_id']
with (OUTPUT/'metrics_matrix.csv').open(newline='') as handle:
    rows = list(csv.DictReader(handle))
matched = [row for row in rows if row['metric_id'] == 'B03'
           and row['cik'] == '37996']
assert len(matched) == 1
assert matched[0]['value'] == current['value']
body = {'record_type': 'ISSUE28_FORD_B03_EXACT_PRIVATE_RELEASE_PREPARATION',
    'preparation_id': saved['preparation_id'],
    'selected_result_id': selected['result_id'],
    'selected_run_id': selected['run_id'],
    'selected_origin': selected['origin'],
    'selected_row': matched[0],
    'public_row_count': report['public_row_count'],
    'unselected_coordinate_count': len(report['unselected_coordinate_keys']),
    'first_script_exit': 1,
    'first_script_failed_after_successful_prepare': True,
    'new_real_calls': [0, 0, 0],
    'full390_acceptance': False,
    'formal_adoption': False}
(HERE/'release.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'preparation_id': body['preparation_id'],
    'result_id': body['selected_result_id'],
    'origin': body['selected_origin'],
    'public_rows': body['public_row_count'],
    'calls': [0, 0, 0]}, sort_keys=True))
