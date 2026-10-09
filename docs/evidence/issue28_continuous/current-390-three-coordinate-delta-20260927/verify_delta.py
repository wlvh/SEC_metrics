"""Bind three later current candidates to the existing call-169 390 index."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_name('delta.json')


def read(relative):
    path = ROOT/relative
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


parent_path = 'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
parent, parent_sha = read(parent_path)
assert parent['coordinate_count'] == len(parent['rows']) == 390
assert parent['as_of'] == '2026-09-22_THROUGH_CALL169_SIX_NEW_D04_NATIVE_CANDIDATES'
rows = {(row['company_id'], row['metric_id']): row for row in parent['rows']}
assert len(rows) == 390

changes = []
for company, label in [('enphase_energy', 'd04-enphase-real'),
                       ('paramount_skydance_paramount_global', 'd04-paramount-real')]:
    prefix = 'docs/evidence/issue28_continuous/batch33-authorization/' + label + '/'
    finish, finish_sha = read(prefix+'finish-summary.json')
    cold, cold_sha = read(prefix+'cold-summary.json')
    prior = rows[(company, 'D04')]
    assert prior['result_category'] == 'VALIDATION_OR_IMPLEMENTATION_PENDING'
    assert finish['company_id'] == cold['company_id'] == company
    assert finish['run_id'] == cold['run_id'] and finish['result_id'] == cold['result_id']
    assert finish['status'] == 'COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS'
    assert cold['status'] == 'PASS_PERSISTED_COMPLETE_CANDIDATE_AND_COLD_READ'
    assert finish['reason_code'] == 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE'
    assert finish['value_kind'] == 'TEXT_V1' and finish['value'] is None
    assert finish['quality'] == 'NONE' and finish['applicability'] == 'APPLICABLE'
    assert finish['production_authorized'] is False and cold['production_authorized'] is False
    changes.append({'company_id': company, 'metric_id': 'D04',
        'prior_category': prior['result_category'],
        'current_category': 'DEFINED_SCOPE_TEXT_STATEMENT',
        'period_from_parent_index': prior['source_period'],
        'result_id': finish['result_id'], 'run_id': finish['run_id'],
        'reason_code': finish['reason_code'], 'value_kind': finish['value_kind'],
        'value': None, 'public_candidate_only': True,
        'source_summary_sha256': {prefix+'finish-summary.json': finish_sha,
                                  prefix+'cold-summary.json': cold_sha}})

relative = 'docs/evidence/issue28_continuous/c04-real-refresh-second-20260927/real-second-summary.json'
current, current_sha = read(relative)
prior = rows[('marriott_international', 'C04')]
assert prior['result_category'] == 'NUMERIC_RESULT' and prior['value'] == '0'
assert current['status'] == 'COMPLETE_CURRENT_MARRIOTT_C04_SOURCE_REFRESH_ZERO_MODEL'
assert current['sec_ordinal'] == 194 and current['prior_ordinal_from_resume'] == 193
assert current['c04_update_status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert current['c04_result_id'] != prior['implementation_identity']['result_id']
assert current['c04_publication'] == 'PUBLISHED' and current['c04_value'] == '0'
assert current['old_and_new_native_cold_read'] == 'PASS_NETWORK_AND_SUBPROCESS_FORBIDDEN'
assert current['new_fiscal_year_proven'] is False and current['formal_publication_authorized'] is False
changes.append({'company_id': 'marriott_international', 'metric_id': 'C04',
    'prior_category': 'NUMERIC_RESULT', 'current_category': 'NUMERIC_RESULT',
    'period_from_parent_index': prior['source_period'],
    'prior_result_id': prior['implementation_identity']['result_id'],
    'current_result_id': current['c04_result_id'], 'current_value': '0',
    'current_successful_attempt': current['c04_successful_attempt'],
    'underlying_real_sec_ordinals': [193, 194],
    'old_and_new_readback': current['old_and_new_native_cold_read'],
    'new_fiscal_year_proven': False, 'formal_publication_authorized': False,
    'source_summary_sha256': {relative: current_sha}})

delta = {'record_type': 'ISSUE28_CURRENT_390_THREE_COORDINATE_DELTA',
    'parent_index': parent_path, 'parent_index_sha256': parent_sha,
    'parent_as_of': parent['as_of'], 'coordinate_count': 390,
    'changed_coordinates': changes, 'new_complete_coordinates_in_this_delta': 2,
    'category_changes_for_these_coordinates_only': {
        'VALIDATION_OR_IMPLEMENTATION_PENDING': -2,
        'DEFINED_SCOPE_TEXT_STATEMENT': 2, 'NUMERIC_RESULT': 0},
    'full_current_head_reexecution': False, 'all390_acceptance': False,
    'other_post_parent_changes_reconciled': False,
    'new_calls_for_this_read_only_delta': [0, 0, 0],
    'formal_adoption_or_active_credit': False}
OUT.write_text(json.dumps(delta, ensure_ascii=False, indent=2)+'\n')
print('THREE_COORDINATE_DELTA_PASS', len(changes), parent_sha)
