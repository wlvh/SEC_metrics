"""Withdraw only the #28 Pfizer FY2025 E01 old-zero Result identity."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
path = ROOT / 'docs/evidence/issue28_continuous/known_result_defects.json'
register = json.loads(path.read_text())
audit = json.loads((HERE / 'audit.json').read_text())
summary = register['current_trusted_summary']
key = 'pfizer|E01|2025-12-31'
assert audit['status'] == 'CONFIRMED_OLD_ZERO_EXCLUDES_RELEVANT_8_01_BODY'
assert summary['newly_excluded_coordinate_count'] == 12
assert summary['newly_excluded_result_id_count'] == 18
assert key not in summary['excluded_coordinate_keys']
assert not any(row['result_id'] == audit['old_result_id'] for row in register['defects'])
register['defects'].append({
    'defect_id': 'E01_PFIZER_2025_8_01_BODY_NOT_READ',
    'metric_id': 'E01', 'company_id': 'pfizer', 'period_end': '2025-12-31',
    'result_id': audit['old_result_id'], 'run_id': audit['old_run_id'],
    'historical_index_same_result_id': True, 'reported_quality': 'EXACT',
    'repair_state': 'CURRENT_8_01_BODY_ROUTE_NOT_YET_IMPLEMENTED',
    'current_credit': 'WITHDRAWN_CONFIRMED_FALSE_ZERO_FOR_CONTENT_CONFIRMED_M_AND_A',
    'summary': 'The exact #28 old Result reports zero although its authenticated 2025-11-13 Pfizer 8.01 primary body says Pfizer completed the Metsera acquisition under a merger agreement; the old matcher tests a generated hdr item label instead of this body.',
    'source': {'accession': audit['accession'],
               'source_references': audit['source_references'],
               'raw_assets': audit['raw_assets'],
               'old_hdr_generated_brief': audit['old_hdr_generated_brief']},
    'peer_origin': {'fixed_commit': audit['peer_fixed_read'],
                    'defect_id': audit['peer_defect_id'],
                    'register_path': 'docs/evidence/issue47_history/known_result_defects.json',
                    'peer_result_credit_not_copied': True},
    'evidence': ['docs/evidence/issue28_continuous/collab-e01-pfizer-20261002/audit.json',
                 'docs/evidence/issue28_continuous/ordinary-pfizer-current-36-cli-20260929/comparison.json'],
    'released': [], 'original_record_retained': True,
})
summary['excluded_coordinate_keys'] = sorted([*summary['excluded_coordinate_keys'], key])
summary['newly_excluded_coordinate_count'] = 13
summary['newly_excluded_result_id_count'] = 19
register['latest_peer_read_commit'] = audit['peer_fixed_read']
path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'excluded_coordinates': 13, 'excluded_exact_result_ids': 19,
                  'new_e01_result_id': audit['old_result_id']}))
