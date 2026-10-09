"""Previously created private D02 candidate cannot regain update credit."""
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.ordinary_d02_category_update import run_company

state = Path('/private/tmp/issue28-d02-versioned-20261002/state/lumen_technologies')
current = state/'metrics/D02-item8-v1/current.json'
before = hashlib.sha256(current.read_bytes()).hexdigest()
row, = run_company(state_root=state, source_root=ROOT,
                   company_id='lumen_technologies', metric_ids=['D02'])['metrics']
after = hashlib.sha256(current.read_bytes()).hexdigest()
assert row['status'] == 'UPDATE_BLOCKED'
assert 'UPDATE_D02_CATEGORY_RULE_VALIDATION_SUSPENDED' in row['reason']
assert row['last_verified_candidate'] is None
assert before == after
summary = {'record_type':'ISSUE28_D02_POST_REVIEW_EXISTING_PRIVATE_CREDIT_STOP',
    'status':row['status'],'reason':row['reason'],
    'previous_private_run_preserved':True,
    'previous_success_pointer_sha256_unchanged':before,
    'new_result_or_attempt_created':False,'new_real_calls':[0,0,0]}
(HERE/'guard-existing.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'status':row['status'],'old_pointer_unchanged':before==after,
                  'new_real_calls':[0,0,0]}))
