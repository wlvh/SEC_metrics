"""Independent-process no-network read of Pfizer grouped-v3 private C02 update."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import ordinary_update_cycle as cycle
from vnext.canonical import sha256_file
STATE=Path('/private/tmp/issue28-c02-normal-update-pfizer-grouped-v3-20261001')
metric_root=STATE/'metrics/C02'
source_log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=source_log)
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 config=cycle._config(metric_root,ROOT,'pfizer',['C02'],'LIVE')
 state=cycle._state(metric_root,config)
 success=cycle._terminal(metric_root,state['successful_attempt'])
 latest=cycle._terminal(metric_root,state['latest_attempt'])
 result=cycle._verify_candidate(metric_root,success,config)['C02']
assert before==sha256_file(path=source_log)
assert success['status']=='CANDIDATE_READY' and latest['status']=='NO_SOURCE_CONTENT_CHANGE'
assert result['publication']=='PUBLISHED' and result['quality']=='EXACT'
run=metric_root/'attempts'/state['successful_attempt']/'runs/C02'
manifest=json.loads((run/'manifest.json').read_text())
rows=[json.loads(s) for s in (run/'records.jsonl').read_text().splitlines()]
candidate=next(r for r in rows if r['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
assert len(candidate['selected'])==25
prior=json.loads((HERE/'pfizer-grouped-v3-update.json').read_text())
assert prior['result_id']==result['result_id']
body={'record_type':'ISSUE28_C02_PFIZER_GROUPED_V3_PRIVATE_COLD_READ','run_id':manifest['run_id'],
      'result_id':result['result_id'],'selected_count':len(candidate['selected']),
      'candidate_hash':candidate['candidate_hash'],'first_status':success['status'],
      'repeat_status':latest['status'],'publication':result['publication'],'quality':result['quality'],
      'requirement_closure_hash':manifest['requirement_closure_hash'],
      'source_log_unchanged':True,'new_real_calls':[0,0,0],
      'business_content_acceptance':False,'production_authorized':False}
(HERE/'pfizer-grouped-v3-cold.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(body,sort_keys=True),flush=True)
