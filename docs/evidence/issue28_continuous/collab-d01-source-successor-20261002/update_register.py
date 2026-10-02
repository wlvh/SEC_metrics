"""Add only the independently source-mapped #28 Marriott D01 old Result."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
path = ROOT / 'docs/evidence/issue28_continuous/known_result_defects.json'
register = json.loads(path.read_text())
audit = json.loads((HERE / 'audit-marriott.json').read_text())
paramount = json.loads((HERE / 'paramount-private-update.json').read_text())
marriott = json.loads((HERE / 'marriott-private-update.json').read_text())
assert audit['status'] == 'CONFIRMED_EXACT_OLD_RESULT_OMITS_FOUR_SOURCE_CATEGORY_HEADINGS'
assert audit['old_result_id'] != audit['new_private_result_id']
assert len(register['defects']) == 17
assert register['current_trusted_summary']['newly_excluded_coordinate_count'] == 11
assert register['current_trusted_summary']['newly_excluded_result_id_count'] == 17
assert not any(row['result_id'] == audit['old_result_id'] for row in register['defects'])
key = 'marriott_international|D01|2025-12-31'
assert key not in register['current_trusted_summary']['excluded_coordinate_keys']
register['defects'].append({
    'defect_id': 'D01_MARRIOTT_2025_UNDERLINED_CATEGORY_HEADINGS_OMITTED',
    'metric_id': 'D01', 'company_id': 'marriott_international',
    'period_end': '2025-12-31', 'result_id': audit['old_result_id'],
    'run_id': audit['old_run_id'], 'historical_index_same_result_id': True,
    'reported_quality': 'EXACT',
    'repair_state': 'EXPLICIT_SUCCESSOR_PRIVATE_RUN_AND_COLD_PASS_CONTENT_REVIEW_PENDING',
    'current_credit': 'WITHDRAWN_CONFIRMED_FOUR_MISSING_SOURCE_HEADINGS',
    'summary': 'Original Item 1A includes four underlined risk-category headings omitted by the old bold-only D01 Result; exact #28 old Result appears in current private Run and retained 390 comparison.',
    'source_headings': audit['added_headings'],
    'peer_origin': {'fixed_commit': '2b4f571ef18274299145c63b4c355aa97c45d030',
                    'defect_id': 'D01_MARRIOTT_2025_12_31_UNDERLINE_GROUP_HEADINGS_DROPPED',
                    'register_path': 'docs/evidence/issue47_history/known_result_defects.json',
                    'peer_result_credit_not_copied': True},
    'evidence': ['docs/evidence/issue28_continuous/collab-d01-source-successor-20261002/audit-marriott.json',
                 'docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/comparison.json'],
    'released': [], 'original_record_retained': True,
})
existing = next(row for row in register['defects'] if row['defect_id'] ==
                'D01_PARAMOUNT_2025_HEADING_TRUNCATED_AT_US_PERIOD')
assert existing['released'] == []
existing['repair_state'] = 'EXPLICIT_SUCCESSOR_PRIVATE_RUN_AND_COLD_PASS_CONTENT_REVIEW_PENDING'
summary = register['current_trusted_summary']
summary['excluded_coordinate_keys'] = sorted([*summary['excluded_coordinate_keys'], key])
summary['newly_excluded_coordinate_count'] = 12
summary['newly_excluded_result_id_count'] = 18
summary['d01_private_successor'] = {
    'source_policy': 'D01_EMPHASIS_SOURCE_V2',
    'paramount_old_result_id': existing['result_id'],
    'paramount_private_result_id': paramount['result_id'],
    'marriott_old_result_id': audit['old_result_id'],
    'marriott_private_result_id': marriott['result_id'],
    'program_status': 'TWO_PRIVATE_NATIVE_UPDATES_AND_COLD_READS_PASS; NOT_CURRENT_390_OR_PRODUCTION_CREDIT',
    'evidence': 'docs/evidence/issue28_continuous/collab-d01-source-successor-20261002/',
}
register['latest_peer_read_commit'] = '2b4f571ef18274299145c63b4c355aa97c45d030'
path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'excluded_coordinates': summary['newly_excluded_coordinate_count'],
                  'excluded_exact_result_ids': summary['newly_excluded_result_id_count']}))
