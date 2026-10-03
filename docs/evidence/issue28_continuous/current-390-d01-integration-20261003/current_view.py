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
CHECKED_PATH = BASE / 'collab-d01-content-20261002/mechanical-corrected-summary.json'
REQUIRED_PROOF_PATHS = frozenset({
    'docs/evidence/issue28_continuous/collab-d01-content-20261002/conclusion.md',
    str(CHECKED_PATH.relative_to(ROOT)),
    'docs/evidence/issue28_continuous/collab-d01-content-20261002/mechanical-receipts.md',
    'docs/evidence/issue28_continuous/collab-d01-page-boundary-20261002/independent-review-865d822/conclusion.md',
})
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.records import validate_record

LEGACY_PRODUCT_SPEC_PATHS = {
    'C02': 'catalog/r6/C02_board_disclosures_v1.md',
    'E01': 'catalog/ordinary_zero_ai/E01.md',
}
CURRENT_PRODUCT_GOALS = {
    'C02': "adopt 'composition facts' (构成事实)",
    'E01': "adopt 'content-confirmed M&A announcements' (经内容确认的并购公告)",
}


def apply_product_scope_limits(rows, parent, register):
    """Keep exact old-contract results outside new-goal acceptance.

    This labels an acceptance gap, not a newly established content defect.
    A differently identified successor gets no acceptance from this function.
    """
    from vnext.specs import compile_spec_file

    limits = register.get('product_scope_acceptance_limits')
    if not isinstance(limits, dict) or limits.get('record_type') != 'ISSUE28_FINITE_LEGACY_PRODUCT_SCOPE_ACCEPTANCE_LIMITS':
        raise ValueError('CURRENT_PRODUCT_SCOPE_LIMITS_REQUIRED')
    authority = limits.get('authority', {})
    if (authority.get('collaboration_version') != 'COLLAB-28-47-v1.1'
            or authority.get('owner_decision_commit') != '48b46a2d742eb3e3b8bd5a6404908745046b5d2f'
            or authority.get('owner_decision_path') != 'docs/evidence/issue47_history/owner-decisions-2026-09-27/decisions.json'
            or authority.get('calls_or_production_authorized') is not False):
        raise ValueError('CURRENT_PRODUCT_SCOPE_AUTHORITY_CHANGED')
    old_specs = {metric: compile_spec_file(path=ROOT/path, dependency_specs={})['spec_closure_hash']
                 for metric, path in LEGACY_PRODUCT_SPEC_PATHS.items()}
    expected = {row['implementation_identity']['result_id']: row for row in parent['rows']
                if row['metric_id'] in old_specs
                and row['implementation_identity']['spec_closure_hash'] == old_specs[row['metric_id']]}
    entries = limits.get('limits', [])
    if (limits.get('scope_count') != len(entries) or len(expected) != 20
            or len(entries) != len(expected)
            or {entry.get('result_id') for entry in entries} != set(expected)):
        raise ValueError('CURRENT_PRODUCT_SCOPE_LIMIT_SET_CHANGED')
    selected = set()
    for entry in entries:
        old = expected[entry['result_id']]
        metric = old['metric_id']
        key = (old['company_id'], metric)
        if (entry.get('company_id') != key[0] or entry.get('metric_id') != metric
                or entry.get('source_period') != old['source_period']
                or entry.get('spec_closure_hash') != old_specs[metric]
                or entry.get('legacy_spec_path') != LEGACY_PRODUCT_SPEC_PATHS[metric]
                or entry.get('current_product_goal') != CURRENT_PRODUCT_GOALS[metric]
                or entry.get('status') != 'LEGACY_CONTRACT_NOT_ACCEPTED_UNDER_CURRENT_PRODUCT_GOAL'
                or entry.get('confirmed_content_defect_inferred') is not False):
            raise ValueError('CURRENT_PRODUCT_SCOPE_LIMIT_IDENTITY_CHANGED')
        row = rows[key]
        if row['implementation_identity'].get('result_id') != entry['result_id']:
            continue
        if (row['source_period'] != entry['source_period']
                or row['implementation_identity'].get('spec_closure_hash') != entry['spec_closure_hash']):
            raise ValueError('CURRENT_PRODUCT_SCOPE_SELECTED_IDENTITY_CHANGED')
        row['historical_contract_value'] = row['value']
        row['value'] = None
        row['current_display_status'] = 'PENDING_CURRENT_PRODUCT_SCOPE_ACCEPTANCE'
        row['current_product_scope_limit'] = deepcopy(entry)
        row['current_product_scope_credit'] = False
        row['selected_result_validation_scope'] = 'HISTORICAL_CONTRACT_ONLY_CURRENT_PRODUCT_GOAL_NOT_ACCEPTED'
        selected.add(key)
    return selected


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def apply_d01_delta(rows, delta, mechanically_checked):
    if delta['coordinate_count'] != 390 or len(delta['changed_coordinates']) != 2:
        raise ValueError('D01_DELTA_SCOPE_INVALID')
    keys = set()
    checked = {entry['company_id']: entry for entry in mechanically_checked['results']}
    if (mechanically_checked['status'] != 'PASS_TWO_EXACT_RUN_COPY_MECHANICAL_RECEIPTS'
            or len(checked) != 2 or len(mechanically_checked['results']) != 2):
        raise ValueError('D01_CHECKED_SUMMARY_SCOPE_INVALID')
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
        proof = checked.get(key[0])
        if proof is None or not proof['original_files_unchanged'] or proof['return_code'] != 0:
            raise ValueError('D01_CHECKED_SUMMARY_COORDINATE_INVALID')
        exact = proof['mechanical_result']
        if ((current['company_id'], current['metric_id']) != key
                or current['implementation_identity']['result_id'] != item['result_id']
                or item['content_review_result_id'] != item['result_id']
                or item['mechanical_receipt_status'] != 'PASSED'
                or native['result_id'] != item['result_id']
                or (native['company_id'], native['metric_id']) != key
                or native['period_start'] != current['source_period']['period_start']
                or native['period_end'] != current['source_period']['period_end']
                or item['result_id'] != exact['result_id']
                or current['implementation_identity']['run_id'] != exact['run_id']
                or current['implementation_identity']['requirement_closure_hash'] != exact['requirement_closure_hash']
                or current['implementation_identity']['semantic_execution_root'] != proof['installed_code_data_root']
                or current['implementation_identity']['spec_closure_hash'] != native['spec_closure_hash']
                or receipt != exact['receipt']
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


def assemble(parent, prior_deltas, d01_delta, defects, mechanically_checked):
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
    apply_d01_delta(rows, d01_delta, mechanically_checked)
    product_scope_pending = apply_product_scope_limits(rows, parent, defects)
    withheld = set()
    for defect in defects['defects']:
        key = (defect['company_id'], defect['metric_id'])
        result_id = rows[key]['implementation_identity'].get('result_id')
        # The register keeps the defective identity; releases describe separately
        # verified successors and cannot clear that original content identity.
        if result_id and result_id == defect.get('result_id'):
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
            'selected_product_scope_pending_count': len(product_scope_pending),
            'selected_nondefect_product_scope_pending_count': len(product_scope_pending - withheld),
            'selected_saved_scope_D01_restorations': 2,
            'other_coordinates_newly_validated_by_this_delta': False,
            'full_current_head_reexecution': False, 'all390_acceptance': False,
            'production_authorized': False, 'new_business_calls': [0, 0, 0]}


def load_current_view():
    d01 = read(Path(__file__).with_name('delta.json'))
    if set(d01['proof_file_sha256']) != REQUIRED_PROOF_PATHS:
        raise ValueError('D01_REQUIRED_PROOF_SET_CHANGED')
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
    defects = read(BASE / 'known_result_defects.json')
    limits = defects.get('product_scope_acceptance_limits', {})
    if limits.get('parent_index_sha256') != digest(PARENT):
        raise ValueError('CURRENT_PRODUCT_SCOPE_PARENT_BYTES_CHANGED')
    return assemble(read(PARENT), list(map(read, prior_paths)), d01,
                    defects, read(CHECKED_PATH))


if __name__ == '__main__':
    import sys
    result = load_current_view()
    output = Path(sys.argv[1])
    if not output.is_absolute() or output == ROOT or ROOT in output.parents:
        raise ValueError('VIEW_OUTPUT_MUST_BE_EXTERNAL')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}, indent=2))
