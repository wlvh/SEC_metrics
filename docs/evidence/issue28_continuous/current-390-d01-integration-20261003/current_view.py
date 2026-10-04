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
JPM_DIR = BASE / 'd01-jpm-content-20261003'
JPM_CONTENT_REVIEW_RESULT = 'sha256:f8da54962750aa727051d66ba699bae53afbf21e2ce19a51abd023666f683f89'
JPM_REQUIRED_PROOF_PATHS = frozenset({
    'docs/evidence/issue28_continuous/d01-jpm-content-20261003/independent-original/conclusion.md',
    'docs/evidence/issue28_continuous/d01-jpm-content-20261003/mechanical-summary.json',
    'docs/evidence/issue28_continuous/collab-d01-running-header-20261003/independent-review-31beeab/conclusion.md',
    'docs/evidence/issue28_continuous/collab-d01-running-header-20261003/cold.log',
})
MARRIOTT_B03_DIR = BASE / 'b03-marriott-390-receiving-20261004'
MARRIOTT_B03_REQUIRED_PROOFS = frozenset({
    'docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/exercise-repair.json',
    'docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/cold-repair.json',
    'docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/independent-review/followup-2bbd769.md',
    'docs/evidence/issue28_continuous/b03-marriott-390-receiving-20261004/mechanical-summary.json',
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


def apply_d01_delta(rows, delta, mechanically_checked, *, expected_count=2):
    # The original two-result path keeps its checks. The explicit one-result
    # successor is only the independently read JPMorgan source, not arbitrary
    # caller-selected coordinates or an inheritance of old validation credit.
    if (type(expected_count) is not int or expected_count not in (1, 2)
            or delta['coordinate_count'] != 390 or len(delta['changed_coordinates']) != expected_count):
        raise ValueError('D01_DELTA_SCOPE_INVALID')
    keys = set()
    checked = {entry['company_id']: entry for entry in mechanically_checked['results']}
    expected_status = ('PASS_ONE_EXACT_JPM_RUN_COPY_MECHANICAL_RECEIPT' if expected_count == 1
                       else 'PASS_TWO_EXACT_RUN_COPY_MECHANICAL_RECEIPTS')
    if (mechanically_checked['status'] != expected_status
            or len(checked) != expected_count or len(mechanically_checked['results']) != expected_count
            or (expected_count == 1 and set(checked) != {'jpmorgan_chase'})):
        raise ValueError('D01_CHECKED_SUMMARY_SCOPE_INVALID')
    for item in delta['changed_coordinates']:
        key = (item['company_id'], item['metric_id'])
        if key in keys or key not in rows or key[1] != 'D01':
            raise ValueError('D01_DELTA_COORDINATE_INVALID')
        keys.add(key)
        if expected_count == 1 and item['result_id'] != JPM_CONTENT_REVIEW_RESULT:
            raise ValueError('D01_JPM_CONTENT_REVIEW_IDENTITY_CHANGED')
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


def apply_marriott_b03_delta(rows, delta, checked):
    """Select a later Run for the same Result, with its repaired admission proof."""
    key = ('marriott_international', 'B03')
    wanted = 'sha256:3043aa63cbf7616f9866fb93b8f69200a2246a33dfec8f1d09502a34af39a72a'
    prior = rows[key]
    current = deepcopy(delta['current_row'])
    native = validate_record(record=delta['native_result'])
    receipt = validate_record(record=delta['mechanical_receipt'])
    exact = checked['mechanical_result']
    if (delta.get('record_type') != 'ISSUE28_MARRIOTT_B03_SAME_RESULT_CURRENT_RUN_PROOF_DELTA'
            or checked.get('changed_copy_files') != ['validation.json']):
        raise ValueError('B03_MARRIOTT_PROOF_TYPE_INVALID')
    if (delta['coordinate_count'] != 390 or (current['company_id'], current['metric_id']) != key
            or checked['status'] != 'PASS_ONE_EXACT_MARRIOTT_B03_RUN_COPY'
            or checked['return_code'] != 0 or checked['original_files_unchanged'] is not True
            or delta['prior_run_id'] != prior['implementation_identity']['run_id']
            or prior['implementation_identity']['result_id'] != wanted
            or native['result_id'] != wanted or exact['native_result'] != native
            or (native['company_id'], native['metric_id']) != key
            or current['source_period'] != prior['source_period']
            or native['period_start'] != current['source_period']['period_start']
            or native['period_end'] != current['source_period']['period_end']
            or current['implementation_identity']['result_id'] != wanted
            or current['implementation_identity']['run_id'] != exact['run_id']
            or exact['run_id'] == delta['prior_run_id']
            or current['implementation_identity']['requirement_closure_hash'] != exact['requirement_closure_hash']
            or current['implementation_identity']['spec_closure_hash'] != native['spec_closure_hash']
            or current['implementation_identity']['semantic_execution_root'] != checked['installed_code_data_root']
            or receipt != exact['receipt'] or receipt['status'] != 'PASSED'
            or delta['repair_admission']['selected_DA_usd'] != '458000000'
            or delta['repair_admission']['excluded_revenue_amortization_usd'] != '135000000'
            or delta['repair_admission']['module_sha256'] != 'acc01df28a45c56c89d0c9c280487434b25efd0ac0ee60d8f659ce25a2b8429f'
            or delta['repair_admission']['economic_all_amortization_proven'] is not False
            or delta['repair_admission']['source_relation_status'] != 'COMPOSED_DA_CONTRACT_REVENUE_DEDUCTION_EXCLUDED'
            or current['formal_adoption_or_active_credit'] is not False
            or any(current[f] != native[f] for f in ('value','unit','quality','applicability','reason_code'))):
        raise ValueError('B03_MARRIOTT_SCOPE_OR_RUN_PROOF_INVALID')
    current['evidence_history'] = [*prior['evidence_history'], prior['selected_evidence']]
    current['prior_implementation_identity'] = deepcopy(prior['implementation_identity'])
    current['selected_result_validation_scope'] = 'BOUND_APPROVED_DA_SCOPE_REPAIRED_ADMISSION_AND_MECHANICAL_RUN_ONLY'
    current['economic_all_amortization_scope_proven'] = False
    rows[key] = current


def assemble(parent, prior_deltas, d01_delta, defects, mechanically_checked,
             *, jpm_delta=None, jpm_checked=None, marriott_b03_delta=None,
             marriott_b03_checked=None):
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
    if (jpm_delta is None) != (jpm_checked is None):
        raise ValueError('D01_JPM_PAIRED_PROOF_REQUIRED')
    if jpm_delta is not None:
        apply_d01_delta(rows, jpm_delta, jpm_checked, expected_count=1)
    if (marriott_b03_delta is None) != (marriott_b03_checked is None):
        raise ValueError('B03_MARRIOTT_PAIRED_PROOF_REQUIRED')
    if marriott_b03_delta is not None:
        apply_marriott_b03_delta(rows, marriott_b03_delta, marriott_b03_checked)
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
            'selected_saved_scope_D01_restorations': 2 + int(jpm_delta is not None),
            **({'selected_saved_scope_Marriott_B03_run_refresh': 1}
               if marriott_b03_delta is not None else {}),
            'other_coordinates_newly_validated_by_this_delta': False,
            'full_current_head_reexecution': False, 'all390_acceptance': False,
            'production_authorized': False, 'new_business_calls': [0, 0, 0]}


def load_current_view(*, include_jpm_reviewed=False, include_marriott_b03_reviewed=False):
    if type(include_jpm_reviewed) is not bool:
        raise ValueError('D01_JPM_SELECTION_INVALID')
    if type(include_marriott_b03_reviewed) is not bool:
        raise ValueError('B03_MARRIOTT_SELECTION_INVALID')
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
    jpm, jpm_checked = None, None
    if include_jpm_reviewed:
        jpm = read(JPM_DIR / 'delta.json')
        if (jpm['parent_index_sha256'] != digest(PARENT)
                or set(jpm['proof_file_sha256']) != JPM_REQUIRED_PROOF_PATHS):
            raise ValueError('D01_JPM_REQUIRED_PROOF_SET_CHANGED')
        for relative, expected in jpm['proof_file_sha256'].items():
            if digest(ROOT / relative) != expected:
                raise ValueError('D01_JPM_PROOF_BYTES_CHANGED:' + relative)
        jpm_checked = read(JPM_DIR / 'mechanical-summary.json')
    marriott, marriott_checked = None, None
    if include_marriott_b03_reviewed:
        marriott = read(MARRIOTT_B03_DIR/'delta.json')
        if (marriott['parent_index_sha256'] != digest(PARENT)
                or set(marriott['proof_file_sha256']) != MARRIOTT_B03_REQUIRED_PROOFS):
            raise ValueError('B03_MARRIOTT_REQUIRED_PROOF_SET_CHANGED')
        for relative, expected in marriott['proof_file_sha256'].items():
            if digest(ROOT/relative) != expected:
                raise ValueError('B03_MARRIOTT_PROOF_BYTES_CHANGED:' + relative)
        marriott_checked = read(MARRIOTT_B03_DIR/'mechanical-summary.json')
        proof_dir = BASE/'b03-marriott-contract-exclusion-20261001'
        admitted = read(proof_dir/'exercise-repair.json')
        cold = read(proof_dir/'cold-repair.json')
        if (admitted['normal_cli_return_code'] != 0
                or admitted['b03_status'] != 'CANDIDATE_READY'
                or admitted['tested_module_sha256'] != marriott['repair_admission']['module_sha256']
                or admitted['result_id'] != marriott['native_result']['result_id']
                or cold['result_id'] != admitted['result_id']
                or cold['run_id'] != marriott_checked['mechanical_result']['run_id']
                or cold['value'] != marriott['native_result']['value']
                or cold['source_relation_status'] != marriott['repair_admission']['source_relation_status']
                or cold['private_release_selection_basis'] != 'NATIVE_PUBLISHED_RESULT'
                or cold['public_row_files_byte_equal'] is not True
                or cold['watched_private_files_unchanged'] is not True):
            raise ValueError('B03_MARRIOTT_REPAIRED_ADMISSION_IDENTITY_CHANGED')
    return assemble(read(PARENT), list(map(read, prior_paths)), d01,
                    defects, read(CHECKED_PATH), jpm_delta=jpm,
                    jpm_checked=jpm_checked, marriott_b03_delta=marriott,
                    marriott_b03_checked=marriott_checked)


if __name__ == '__main__':
    import sys
    options = sys.argv[2:]
    if (len(sys.argv) < 2 or len(options) != len(set(options))
            or not set(options).issubset({'--include-jpm-reviewed', '--include-marriott-b03-reviewed'})):
        raise ValueError('VIEW_ARGUMENTS_INVALID')
    result = load_current_view(include_jpm_reviewed='--include-jpm-reviewed' in options,
                              include_marriott_b03_reviewed='--include-marriott-b03-reviewed' in options)
    output = Path(sys.argv[1])
    if not output.is_absolute() or output == ROOT or ROOT in output.parents:
        raise ValueError('VIEW_OUTPUT_MUST_BE_EXTERNAL')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}, indent=2))
