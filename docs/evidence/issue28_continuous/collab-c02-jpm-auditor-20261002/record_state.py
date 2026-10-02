"""Withhold two exact old C02 Result IDs for one JPMorgan FY2025 coordinate."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
audit = json.loads((HERE/'audit.json').read_text())
v3 = json.loads((HERE/'v3-impact.json').read_text())
assert v3['selected_source_blocks'] == [3367]
path = ROOT/'docs/evidence/issue28_continuous/known_result_defects.json'
register = json.loads(path.read_text())
summary = register['current_trusted_summary']
assert summary['newly_excluded_coordinate_count'] == 18
assert summary['newly_excluded_result_id_count'] == 25
key = 'jpmorgan_chase|C02|2025-12-31'
assert key not in summary['excluded_coordinate_keys']
existing = {row['result_id'] for row in register['defects'] if 'result_id' in row}
assert audit['old_private_result_id'] not in existing
assert audit['old_archived_390_result_id'] not in existing
common = {'metric_id':'C02','company_id':'jpmorgan_chase',
    'period_end':'2025-12-31','reported_quality':'EXACT',
    'repair_state':'SHARED_COMPOSITION_SELECTOR_CONTENT_SCOPE_REPAIR_PENDING',
    'current_credit':'WITHDRAWN_AUDITOR_RETENTION_IS_NOT_BOARD_COMPOSITION',
    'summary':('A selected original proxy block reports the Audit Committee and '
               'Board view about retaining PwC as external auditor, not a fact '
               'about board size, membership, committees, independence or '
               'director qualifications under the adopted C02 target.'),
    'source_block':audit['out_of_target_source_block'],
    'evidence':['docs/evidence/issue28_continuous/'
                'collab-c02-jpm-auditor-20261002/audit.json',
                'docs/evidence/issue28_continuous/'
                'collab-c02-jpm-auditor-20261002/v3-impact.json'],
    'released':[],'original_record_retained':True}
register['defects'].append({**common,
    'defect_id':'C02_JPMORGAN_2025_AUDITOR_RETENTION_PRIVATE_NORMAL_UPDATE',
    'result_id':audit['old_private_result_id'],
    'run_id':audit['old_private_run_id'],
    'native_evidence_status':'PASS_BUT_OUT_OF_TARGET_CONTENT'})
register['defects'].append({**common,
    'defect_id':'C02_JPMORGAN_2025_AUDITOR_RETENTION_ARCHIVED_390',
    'result_id':audit['old_archived_390_result_id'],
    'run_id':audit['old_archived_390_run_id'],
    'archived_390_value_contains_excerpt':True})
summary['excluded_coordinate_keys'].append(key)
summary['excluded_coordinate_keys'].sort()
summary['newly_excluded_coordinate_count'] = len(summary['excluded_coordinate_keys'])
summary['newly_excluded_result_id_count'] = len({
    row['result_id'] for row in register['defects'] if 'result_id' in row})
assert summary['newly_excluded_coordinate_count'] == 19
assert summary['newly_excluded_result_id_count'] == 27
register['latest_peer_read_commit'] = 'ebac1015497b97d35e2357781fbbfc0b613fb57a'
path.write_text(json.dumps(register,ensure_ascii=False,indent=2)+'\n')

state_path = ROOT/'docs/evidence/issue28_continuous/execution-state.json'
text = state_path.read_text()
state = json.loads(text)
name = 'c02_jpm_auditor_retention_current_20261002'
assert name not in state
entry = {'status':'TWO_EXACT_OLD_C02_RESULT_IDS_WITHDRAWN_ONE_COORDINATE',
    'old_private_result_id':audit['old_private_result_id'],
    'old_archived_390_result_id':audit['old_archived_390_result_id'],
    'original_source_block_index':3367,
    'current_grouped_v3_still_selects_original_block':True,
    'current_grouped_v3_view_block_index':v3['grouped_view_block_index'],
    'trusted_summary':{'excluded_coordinates':19,'excluded_exact_result_ids':27},
    'old_runs_results_source_retained':True,'new_result_or_run':False,
    'new_real_calls':[0,0,0],
    'evidence':'docs/evidence/issue28_continuous/'
               'collab-c02-jpm-auditor-20261002/'}
end = text.rfind('\n}')
assert end > 0 and text[end:].strip() == '}'
formatted = json.dumps({name:entry},ensure_ascii=False,indent=2)
formatted = '\n'.join(formatted.splitlines()[1:-1])
state_path.write_text(text[:end].rstrip()+',\n'+formatted+'\n}\n')
json.loads(state_path.read_text())
print(json.dumps({'excluded_coordinates':19,'excluded_result_ids':27,
                  'new_real_calls':[0,0,0]}))
