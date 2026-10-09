"""Read the saved preparation after a reporting-script row-count error."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path('/private/tmp/issue28-ford-b03-35-release-20260929')
saved = json.loads((OUTPUT/'ordinary_release_preparation.json').read_text())
report = saved['composition']
complement = json.loads((HERE/'complement.json').read_text())
b03 = json.loads((HERE/'private-result.json').read_text())
selected = report['selected_results']
assert len(selected) == 35
assert all(row['company_id'] == 'ford_motor_company'
           and row['origin'] == 'VERIFIED_ORDINARY_RUN' for row in selected)
expected = {row['metric_id']: row['result_id'] for row in complement['rows']}
expected['B03'] = b03['result_id']
assert {row['metric_id']: row['result_id'] for row in selected} == expected
assert all(row['requirement_closure_hash'] ==
           'sha256:33ee286c21be8262e550939e2a94512775996635c569bcd12531efca2014ed83'
           for row in selected)
assert report['public_row_count'] == 333
assert report['inherited_public_row_count'] == 298
assert len(report['unselected_coordinate_keys']) == 355
assert report['full390_acceptance'] is False
assert report['switch_available'] is False
assert report['production_authorized'] is False
predecessor = OUTPUT/'predecessor'/report['predecessor']['publication_id']
with (predecessor/'metrics_matrix.csv').open(newline='') as handle:
    old_rows = list(csv.DictReader(handle))
with (OUTPUT/'metrics_matrix.csv').open(newline='') as handle:
    rows = list(csv.DictReader(handle))
assert len(old_rows) == 327 and len(rows) == 333
old_ford = {row['metric_id'] for row in old_rows if row['cik'] == '37996'}
ford = {row['metric_id'] for row in rows if row['cik'] == '37996'}
added = sorted(ford - old_ford)
assert len(old_ford) == 33 and len(ford) == 39
assert added == ['A03', 'A04', 'A09', 'A11', 'A12', 'A13']
assert sorted(ford - set(expected)) == ['B06', 'B13', 'D03', 'D04']
ford_b03, = [row for row in rows if row['cik'] == '37996'
              and row['metric_id'] == 'B03']
assert ford_b03['status'] == 'OK' and ford_b03['value'] == b03['value']
body = {'record_type': 'ISSUE28_FORD_B03_CURRENT_CLOSURE_35_PRIVATE_PREPARATION',
    'preparation_id': saved['preparation_id'],
    'source_snapshot_id': b03['source_snapshot_id'],
    'request_requirement_closure_hash': b03['requirement_closure_hash'],
    'native_run_closure': selected[0]['requirement_closure_hash'],
    'selected_metric_ids': [row['metric_id'] for row in selected],
    'selected_result_ids': expected,
    'ford_b03_row': ford_b03,
    'predecessor_public_row_count': len(old_rows),
    'public_row_count': len(rows),
    'selected_coordinate_count': len(selected),
    'unselected_coordinate_count': 355,
    'new_ford_public_row_metric_ids': added,
    'ford_inherited_not_currently_selected': sorted(ford - set(expected)),
    'first_script_exit': 1,
    'first_script_failed_after_successful_prepare': True,
    'first_script_error': 'EVIDENCE_SCRIPT_ASSUMED_PUBLIC_ROW_COUNT_327',
    'new_real_calls': [0, 0, 0], 'full390_acceptance': False,
    'formal_adoption': False}
(HERE/'ford-35-release.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'preparation_id': body['preparation_id'],
    'selected': len(selected), 'public_rows': len(rows),
    'added_ford_rows': added, 'calls': [0, 0, 0]},
    sort_keys=True), flush=True)
