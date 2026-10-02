"""Describe an already-written v2 native Run after the report script failed."""
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
state=Path('/private/tmp/issue28-d02-versioned-v2-20261002/state/lumen_technologies/metrics/D02-item8-v2')
current=json.loads((state/'current.json').read_text())
attempt=current['successful_attempt']
assert attempt and attempt==current['latest_attempt']
work=state/'attempts'/attempt
terminal=json.loads((work/'terminal.json').read_text())
assert terminal['status']=='CANDIDATE_READY' and terminal['attempt_id']==attempt
run=work/'runs/D02'
manifest=json.loads((run/'manifest.json').read_text())
records=[json.loads(line) for line in (run/'records.jsonl').read_bytes().splitlines()]
selected=next(row for row in records if row['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
result=next(row for row in records if row['record_type']=='METRIC_RESULT'
            and row['metric_id']=='D02')
evidence=next(row for row in records if row['record_type']=='EVIDENCE_CHECK')
indexes={(row['section_id'],row['block_index']) for row in selected['selected'].values()}
old=json.loads((ROOT/'docs/evidence/issue28_continuous/collab-d02-lumen-20261002/audit.json').read_text())
assert len(indexes)==14 and ('ITEM_8',1670) not in indexes
assert result['result_id']==terminal['metrics']['D02']['result_id']
assert result['result_id']!=old['result_id']
assert result['publication']=='PUBLISHED' and evidence['status']=='PASS'
binding=json.loads((HERE/'binding-after.json').read_text())
summary={'record_type':'ISSUE28_D02_V2_EXISTING_PRIVATE_NATIVE_RUN_RECOVERY',
    'tested_tree':'UNCOMMITTED_WORKTREE_WITH_BOUND_V13_V14_IDS',
    'original_report_script_exit':1,
    'original_report_failure':'KEYERROR_BINDING_SUMMARY_FIELD_AFTER_NATIVE_RUN_WRITE',
    'code_root':str(ROOT),'state_root':str(state),
    'requirement_closure_hash':binding['child_closure'],
    'status':terminal['status'],'attempt_id':attempt,'run_id':manifest['run_id'],
    'old_result_id_withdrawn':old['result_id'],
    'new_private_result_id':result['result_id'],
    'old_selected_count':15,'new_selected_count':len(indexes),
    'removed_known_block':1670,'native_evidence_status':evidence['status'],
    'new_result_content_acceptance':False,'current_390_credit':False,
    'reported_calls':terminal['calls'],'new_real_calls':[0,0,0],
    'production_authorized':False,
    'protected_hash_before_after_from_original_script':'NOT_PERSISTED_AFTER_REPORT_ERROR'}
(HERE/'run.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':summary['status'],'attempt':attempt,
    'result_id':summary['new_private_result_id'],'selected':len(indexes),
    'calls':terminal['calls']}))
