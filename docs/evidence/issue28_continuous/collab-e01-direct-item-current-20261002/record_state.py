"""Withdraw only the four exact old E01 Result identities proved by audit.py."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
register_path = ROOT / 'docs/evidence/issue28_continuous/known_result_defects.json'
state_path = ROOT / 'docs/evidence/issue28_continuous/execution-state.json'
audit = json.loads((HERE / 'audit.json').read_text())
register = json.loads(register_path.read_text())
summary = register['current_trusted_summary']
assert summary['newly_excluded_coordinate_count'] == 13
assert summary['newly_excluded_result_id_count'] == 19
assert len(audit['results']) == 4
existing = {entry['result_id'] for entry in register['defects'] if 'result_id' in entry}
for row in audit['results']:
    key = '|'.join((row['company_id'], 'E01', row['period_end']))
    assert key not in summary['excluded_coordinate_keys']
    assert row['old_result_id'] not in existing
    register['defects'].append({
        'defect_id': 'E01_' + row['company_id'].upper() + '_2025_DIRECT_ITEM_FINANCING',
        'metric_id': 'E01', 'company_id': row['company_id'],
        'period_end': row['period_end'], 'result_id': row['old_result_id'],
        'run_id': row['old_run_id'], 'historical_index_same_result_id': True,
        'reported_quality': 'EXACT',
        'repair_state': 'CONTENT_CONFIRMED_M_AND_A_SUCCESSOR_NOT_YET_ACCEPTED',
        'current_credit': 'WITHDRAWN_SELECTED_1_01_FINANCING_IS_NOT_M_AND_A_ANNOUNCEMENT',
        'summary': ('The old direct-item count includes a verified 1.01 claim whose '
                    'original primary 8-K describes financing rather than a '
                    'content-confirmed M&A announcement. The old Result remains '
                    'historically intact but cannot satisfy the adopted E01 target.'),
        'source': {'accession': row['accession'],
                   'selected_claim_id': row['selected_claim_id'],
                   'primary_source_reference_id': row['primary_source_reference_id'],
                   'primary_raw_asset_id': row['primary_raw_asset_id'],
                   'header_source_reference_id': row['header_source_reference_id'],
                   'header_raw_asset_id': row['header_raw_asset_id'],
                   'visible_anchor': row['visible_anchor']},
        'evidence': ['docs/evidence/issue28_continuous/'
                     'collab-e01-direct-item-current-20261002/audit.json'],
        'released': [], 'original_record_retained': True,
    })
    summary['excluded_coordinate_keys'].append(key)
summary['excluded_coordinate_keys'].sort()
summary['newly_excluded_coordinate_count'] = len(summary['excluded_coordinate_keys'])
summary['newly_excluded_result_id_count'] = len({
    entry['result_id'] for entry in register['defects'] if 'result_id' in entry})
assert summary['newly_excluded_coordinate_count'] == 17
assert summary['newly_excluded_result_id_count'] == 23
register['latest_peer_read_commit'] = audit['peer_fixed_read']
register_path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + '\n')

original_state = state_path.read_text()
state = json.loads(original_state)
assert 'e01_direct_item_financing_current_20261002' not in state
state['e01_direct_item_financing_current_20261002'] = {
    'status': 'FOUR_EXACT_OLD_E01_RESULTS_WITHDRAWN_FOR_ADOPTED_CONTENT_TARGET',
    'evidence': 'docs/evidence/issue28_continuous/collab-e01-direct-item-current-20261002/',
    'own_old_result_ids': [row['old_result_id'] for row in audit['results']],
    'companies': [row['company_id'] for row in audit['results']],
    'old_values': {row['company_id']: row['old_value'] for row in audit['results']},
    'current_trusted_summary': {'excluded_coordinates': 17,
                                'excluded_exact_result_ids': 23},
    'paramount_and_salesforce_current_1_01': 'POSSIBLE_FINANCING_AND_M_AND_A_CONTEXT_NOT_CLASSIFIED',
    'old_runs_and_results_preserved': True, 'new_result_or_run': False,
    'new_real_calls': [0, 0, 0],
}
# This large hand-maintained state file has intentionally compact nested
# entries. Append this one key without rewriting thousands of unrelated lines.
end = original_state.rfind('\n}')
assert end > 0 and original_state[end:].strip() == '}'
new_entry = json.dumps({'e01_direct_item_financing_current_20261002':
                        state['e01_direct_item_financing_current_20261002']},
                       ensure_ascii=False, indent=2)
new_entry = '\n'.join(new_entry.splitlines()[1:-1])
state_path.write_text(original_state[:end].rstrip() + ',\n' + new_entry + '\n}\n')
print(json.dumps({'excluded_coordinates': 17, 'excluded_exact_result_ids': 23,
                  'new_real_calls': [0, 0, 0]}))
