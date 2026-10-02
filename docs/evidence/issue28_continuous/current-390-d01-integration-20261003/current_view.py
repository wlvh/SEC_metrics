"""Read the existing 390 index, its finite deltas and precise defect register.

This is a development evidence view, not a producer, new ledger or publication.
Unchanged coordinates retain their prior scope; no global acceptance is granted.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'docs/evidence/issue28_continuous'
PARENT = BASE / 'd04-remaining-20260922/current-390.json'
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.records import validate_record


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def apply_d01_delta(rows, delta):
    if delta['coordinate_count'] != 390 or len(delta['changed_coordinates']) != 2:
        raise ValueError('D01_DELTA_SCOPE_INVALID')
    keys = set()
    for item in delta['changed_coordinates']:
        key = (item['company_id'], item['metric_id'])
        if key in keys or key not in rows or key[1] != 'D01':
            raise ValueError('D01_DELTA_COORDINATE_INVALID')
        keys.add(key)
        prior = rows[key]
        if (prior['implementation_identity']['result_id'] != item['prior_result_id']
                or prior['source_period'] != item['current_row']['source_period']):
            raise ValueError('D01_DELTA_PREDECESSOR_OR_PERIOD_CHANGED')
        current = deepcopy(item['current_row'])
        native = validate_record(record=item['native_result'])
        receipt = validate_record(record=item['mechanical_receipt'])
        if ((current['company_id'], current['metric_id']) != key
                or current['implementation_identity']['result_id'] != item['result_id']
                or item['content_review_result_id'] != item['result_id']
                or item['mechanical_receipt_status'] != 'PASSED'
                or native['result_id'] != item['result_id']
                or receipt['status'] != 'PASSED'
                or receipt['validation_receipt_id'] != item['mechanical_receipt_id']
                or any(current[field] != native[field] for field in
                       ('value', 'unit', 'quality', 'applicability', 'reason_code'))
                or current['quality'] != 'EXACT'
                or current['formal_adoption_or_active_credit'] is not False):
            raise ValueError('D01_DELTA_VALIDATION_IDENTITY_INVALID')
        current['evidence_history'] = [*prior['evidence_history'], prior['selected_evidence']]
        current['selected_result_validation_scope'] = 'SAVED_SCOPE_CONTENT_AND_MECHANICAL_RECEIPT_VALIDATED'
        rows[key] = current


def assemble(parent, prior_deltas, d01_delta, defects):
    rows = {(row['company_id'], row['metric_id']): deepcopy(row) for row in parent['rows']}
    if len(rows) != 390 or parent['coordinate_count'] != 390:
        raise ValueError('CURRENT_INDEX_COORDINATE_SET_INVALID')
    original_keys = set(rows)
    for delta in prior_deltas:
        if delta['coordinate_count'] != 390:
            raise ValueError('PRIOR_DELTA_COORDINATE_SET_INVALID')
        entries = delta.get('changed_coordinates', [delta])
        for item in entries:
            key = (item['company_id'], item['metric_id'])
            row = rows[key]
            identity = row['implementation_identity']
            previous = item.get('prior_result_id')
            if previous and identity.get('result_id') != previous:
                raise ValueError('PRIOR_DELTA_PREDECESSOR_CHANGED')
            row['prior_implementation_identity'] = deepcopy(identity)
            row['implementation_identity'] = {
                'result_id': item.get('current_result_id', item.get('result_id')),
                # A delta without the new Run's identity cannot inherit the old Run.
                'run_id': item.get('current_run_id', item.get('run_id')),
                'identity_scope': 'ONLY_FIELDS_EXPLICITLY_RECORDED_BY_PRIOR_DELTA',
            }
            row['result_category'] = item['current_category']
            if 'current_value' in item or 'value' in item:
                row['value'] = item.get('current_value', item.get('value'))
            if 'reason_code' in item:
                row['reason_code'] = item['reason_code']
            row['selected_result_validation_scope'] = 'PRIOR_BOUNDED_DELTA_SCOPE_ONLY'
            row['source_credit'] = 'SEE_SELECTED_BOUNDED_DELTA_ORIGINAL_SCOPE'
            row['selected_evidence'] = {'delta': delta['record_type'], 'coordinate': ':'.join(key)}
    apply_d01_delta(rows, d01_delta)
    withheld = set()
    for defect in defects['defects']:
        key = (defect['company_id'], defect['metric_id'])
        result_id = rows[key]['implementation_identity'].get('result_id')
        if result_id and result_id == defect.get('result_id') and not defect.get('released'):
            row = rows[key]
            row['value'] = None
            row['current_display_status'] = 'WITHHELD_KNOWN_RESULT_DEFECT'
            row['selected_result_validation_scope'] = 'KNOWN_DEFECT_NO_CURRENT_CREDIT'
            row.setdefault('current_defect_ids', []).append(defect['defect_id'])
            withheld.add(key)
    if set(rows) != original_keys:
        raise ValueError('CURRENT_VIEW_CHANGED_DENOMINATOR')
    return {'record_type': 'ISSUE28_EXISTING_390_DEVELOPMENT_VIEW', 'coordinate_count': 390,
            'rows': list(rows.values()), 'selected_known_defect_coordinate_count': len(withheld),
            'selected_saved_scope_D01_restorations': 2,
            'other_coordinates_newly_validated_by_this_delta': False,
            'full_current_head_reexecution': False, 'all390_acceptance': False,
            'production_authorized': False, 'new_business_calls': [0, 0, 0]}


def load_current_view():
    d01 = read(Path(__file__).with_name('delta.json'))
    prior_paths = [BASE / 'current-390-three-coordinate-delta-20260927/delta.json',
                   BASE / 'current-390-southwest-c04-20260927/delta.json']
    for delta in [d01, *map(read, prior_paths)]:
        if delta['parent_index_sha256'] != digest(PARENT):
            raise ValueError('CURRENT_VIEW_PARENT_BYTES_CHANGED')
        for item in delta.get('changed_coordinates', []):
            for relative, expected in item.get('source_summary_sha256', {}).items():
                if digest(ROOT / relative) != expected:
                    raise ValueError('PRIOR_DELTA_PROOF_BYTES_CHANGED:' + relative)
    for relative, expected in d01['proof_file_sha256'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError('D01_CURRENT_PROOF_BYTES_CHANGED:' + relative)
    return assemble(read(PARENT), list(map(read, prior_paths)), d01,
                    read(BASE / 'known_result_defects.json'))


if __name__ == '__main__':
    import sys
    result = load_current_view()
    output = Path(sys.argv[1])
    if not output.is_absolute() or output == ROOT or ROOT in output.parents:
        raise ValueError('VIEW_OUTPUT_MUST_BE_EXTERNAL')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}, indent=2))
