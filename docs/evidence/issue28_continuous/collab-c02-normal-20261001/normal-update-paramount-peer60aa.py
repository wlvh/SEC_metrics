"""No-network ordinary C02 Paramount FY2025 candidate and repeat test."""
import json
from pathlib import Path
import signal
import socket
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.canonical import sha256_file
from vnext.ordinary_update_cycle import run_company

STATE=Path('/private/tmp/issue28-c02-normal-update-paramount-peer60aa-20261001')
assert not STATE.exists()
log=ROOT/'evidence/requests_log.csv'; before=sha256_file(path=log)
signal.alarm(110)
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
    first=run_company(state_root=STATE,source_root=ROOT,company_id='paramount_skydance_paramount_global',metric_ids=['C02'])
    second=run_company(state_root=STATE,source_root=ROOT,company_id='paramount_skydance_paramount_global',metric_ids=['C02'])
assert before==sha256_file(path=log)
one,two=first['metrics'][0],second['metrics'][0]
assert one['status']=='CANDIDATE_READY' and two['status']=='NO_SOURCE_CONTENT_CHANGE'
assert one['successful_attempt']==two['successful_attempt']
result=one['last_verified_candidate']['results']['C02']
body={'record_type':'ISSUE28_C02_PARAMOUNT_ORDINARY_PRIVATE_UPDATE','first_status':one['status'],
      'repeat_status':two['status'],'result_id':result['result_id'],
      'run_id':one['last_verified_candidate']['run_ids']['C02'] if 'run_ids' in one['last_verified_candidate'] else None,
      'source_log_unchanged':True,'new_real_calls':[0,0,0],
      'business_content_acceptance':False,'production_authorized':False,
      'state_root':str(STATE)}
(HERE/'paramount-update-peer60aa.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(body,sort_keys=True),flush=True)
