"""Read a retained v2 Run using its own installed code and Requirement bytes."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
base=Path('/private/tmp/issue28-c02-normal-update-enphase-peer60aa-20261001/metrics/C02/attempts')
run=next(base.glob('*/runs/C02'))
data=run.parents[1]/'data'
sys.path[:0]=[str(data),str(data/'scripts')]
from vnext.run_store import _mechanically_replay_open_run
from vnext.requirements import load_requirement_snapshot
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 requirement=load_requirement_snapshot(snapshot_dir=data/'requirements/issue_28_v13')
 manifest,stored,_=_mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
results=[r for r in stored if r['record_type']=='METRIC_RESULT']
assert len(results)==1
assert results[0]['result_id']=='sha256:8fb7d6e3ee0a8eeefd58b9187c701b11a3b1bb3aa4954dc339da4b704044f234'
assert manifest['requirement_closure_hash']==requirement['requirement_closure_hash']
body={'record_type':'ISSUE28_C02_V2_ORIGINAL_INSTALLED_CODE_REPLAY',
      'run_id':manifest['run_id'],'result_id':results[0]['result_id'],
      'requirement_closure_hash':requirement['requirement_closure_hash'],
      'installed_root':str(data),'installed_run_status':manifest['status'],
      'current_tree_not_used_to_reinterpret_old_installed_requirement':True,
      'new_real_calls':[0,0,0],'production_authorized':False}
(HERE/'old-v2-installed-replay.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(body,sort_keys=True),flush=True)
