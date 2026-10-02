"""Withdraw two exact #28 JPM D02 Result IDs, keeping one coordinate."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
audit = json.loads((HERE/'audit.json').read_text())
register_path = ROOT/'docs/evidence/issue28_continuous/known_result_defects.json'
register = json.loads(register_path.read_text())
summary = register['current_trusted_summary']
assert summary['newly_excluded_coordinate_count'] == 17
assert summary['newly_excluded_result_id_count'] == 23
key = 'jpmorgan_chase|D02|2025-12-31'
assert key not in summary['excluded_coordinate_keys']
existing = {row['result_id'] for row in register['defects'] if 'result_id' in row}
assert audit['private_result_id'] not in existing
assert audit['archived_390_result_id'] not in existing
common = {'metric_id':'D02','company_id':'jpmorgan_chase',
    'period_end':'2025-12-31','reported_quality':'EXACT',
    'repair_state':'PAGE_FURNITURE_SELECTION_REPAIR_NOT_YET_OWNED_OR_ACCEPTED',
    'current_credit':'WITHDRAWN_SELECTED_10K_PAGE_FURNITURE_IS_NOT_LEGAL_DISCLOSURE',
    'summary':('The saved D02 text includes the annual-report footer and a running '
               'financial-statement header as if they were litigation disclosures; '
               'source content and the exact affected Result identity are retained.'),
    'peer_origin':{'fixed_read_commit':audit['peer_lead_commit'],
        'register_blob':audit['peer_defect_register_blob'],
        'evidence_path':'docs/evidence/issue47_history/d02-facing-pages/README.md',
        'peer_result_credit_not_copied':True},
    'evidence':['docs/evidence/issue28_continuous/'
                'collab-d02-jpm-page-furniture-20261002/audit.json'],
    'released':[],'original_record_retained':True}
register['defects'].append({**common,
    'defect_id':'D02_JPMORGAN_2025_PAGE_FURNITURE_PRIVATE_NORMAL_UPDATE',
    'result_id':audit['private_result_id'],'run_id':audit['private_run_id'],
    'source_blocks':audit['private_selected_non_disclosures'],
    'native_evidence_status':'PASS_BUT_CONTENT_WRONG'})
register['defects'].append({**common,
    'defect_id':'D02_JPMORGAN_2025_PAGE_FURNITURE_ARCHIVED_390',
    'result_id':audit['archived_390_result_id'],
    'run_id':audit['archived_390_run_id'],
    'archived_value_footer_occurrences':audit['archived_390_value_footer_occurrences'],
    'archived_value_running_head_occurrences':
        audit['archived_390_value_running_head_occurrences']})
summary['excluded_coordinate_keys'].append(key)
summary['excluded_coordinate_keys'].sort()
summary['newly_excluded_coordinate_count'] = len(summary['excluded_coordinate_keys'])
summary['newly_excluded_result_id_count'] = len({
    row['result_id'] for row in register['defects'] if 'result_id' in row})
assert summary['newly_excluded_coordinate_count'] == 18
assert summary['newly_excluded_result_id_count'] == 25
register['latest_peer_read_commit'] = audit['peer_lead_commit']
register_path.write_text(json.dumps(register,ensure_ascii=False,indent=2)+'\n')

state_path = ROOT/'docs/evidence/issue28_continuous/execution-state.json'
text = state_path.read_text()
state = json.loads(text)
name = 'd02_jpm_page_furniture_current_20261002'
assert name not in state
entry = {'status':'TWO_EXACT_28_D02_RESULT_IDS_WITHDRAWN_ONE_COORDINATE',
    'peer_fixed_read_via_github_api':audit['peer_lead_commit'],
    'peer_register_blob':audit['peer_defect_register_blob'],
    'private_result_id':audit['private_result_id'],
    'archived_390_result_id':audit['archived_390_result_id'],
    'original_verified_non_disclosure_block_indexes':
        [row['block_index'] for row in audit['private_selected_non_disclosures']],
    'trusted_summary':{'excluded_coordinates':18,'excluded_exact_result_ids':25},
    'source_and_old_runs_retained':True,'new_result_or_run':False,
    'peer_repair_imported':False,'new_real_calls':[0,0,0],
    'evidence':'docs/evidence/issue28_continuous/'
               'collab-d02-jpm-page-furniture-20261002/'}
end = text.rfind('\n}')
assert end > 0 and text[end:].strip() == '}'
formatted = json.dumps({name:entry},ensure_ascii=False,indent=2)
formatted = '\n'.join(formatted.splitlines()[1:-1])
state_path.write_text(text[:end].rstrip()+',\n'+formatted+'\n}\n')
json.loads(state_path.read_text())
print(json.dumps({'excluded_coordinates':18,'excluded_result_ids':25,
                  'new_real_calls':[0,0,0]}))
