"""A prior private v2 Run remains, but cannot be accepted by a new update."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.ordinary_d02_category_update_v2 import run_company


state=Path('/private/tmp/issue28-d02-versioned-v2-final-20261002/state/lumen_technologies')
root=state/'metrics/D02-item8-v2'
current=root/'current.json'
before=hashlib.sha256(current.read_bytes()).hexdigest()
attempts_before=sorted(x.name for x in (root/'attempts').iterdir())


def blocked(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked)):
    row,=run_company(state_root=state,source_root=ROOT,
        company_id='lumen_technologies',metric_ids=['D02'])['metrics']
after=hashlib.sha256(current.read_bytes()).hexdigest()
attempts_after=sorted(x.name for x in (root/'attempts').iterdir())
assert row['status']=='UPDATE_BLOCKED'
assert 'UPDATE_D02_V2_CATEGORY_RULE_VALIDATION_SUSPENDED' in row['reason']
assert row['last_verified_candidate'] is None
assert before==after and attempts_before==attempts_after
result={'record_type':'ISSUE28_D02_V2_POST_REVIEW_EXISTING_PRIVATE_CREDIT_STOP',
    'prior_private_result_id':json.loads((HERE/'run-final.json').read_text())['new_private_result_id'],
    'status':row['status'],'reason':row['reason'],
    'prior_pointer_sha256_unchanged':before,
    'attempt_ids_unchanged':attempts_before,
    'new_result_or_attempt_created':False,'new_real_calls':[0,0,0]}
(HERE/'guard-existing-v2.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':row['status'],'pointer_unchanged':before==after,
    'attempts_unchanged':attempts_before==attempts_after,'calls':[0,0,0]}))
