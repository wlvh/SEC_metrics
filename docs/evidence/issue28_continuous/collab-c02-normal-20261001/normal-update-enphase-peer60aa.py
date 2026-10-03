"""No-network native Enphase C02 update under the fixed shared 60aa selector."""
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
STATE=Path('/private/tmp/issue28-c02-normal-update-enphase-peer60aa-20261001')
assert not STATE.exists()
log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=log)
signal.alarm(110)
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 first=run_company(state_root=STATE,source_root=ROOT,company_id='enphase_energy',metric_ids=['C02'])
 second=run_company(state_root=STATE,source_root=ROOT,company_id='enphase_energy',metric_ids=['C02'])
assert before==sha256_file(path=log)
one,two=first['metrics'][0],second['metrics'][0]
assert one['status']=='CANDIDATE_READY' and two['status']=='NO_SOURCE_CONTENT_CHANGE'
assert one['successful_attempt']==two['successful_attempt']
result=one['last_verified_candidate']['results']['C02']
run=STATE/'metrics/C02/attempts'/one['successful_attempt']/'runs/C02'
manifest=json.loads((run/'manifest.json').read_text())
rows=[json.loads(s) for s in (run/'records.jsonl').read_text().splitlines()]
candidate=next(x for x in rows if x['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
blocks={x['block_index'] for x in candidate['selected'].values()}
assert len(blocks)==48 and not blocks.intersection({57,210,212,232,243,2338,294}) and 415 in blocks
old=json.loads((HERE/'enphase-update-docfix.json').read_text())
assert result['result_id']!=old['result_id']
body={'record_type':'ISSUE28_C02_PEER60AA_PRIVATE_NORMAL_UPDATE','company_id':'enphase_energy',
      'first_status':one['status'],'repeat_status':two['status'],
      'run_id':manifest['run_id'],'result_id':result['result_id'],
      'prior_54_result_id_retained':old['result_id'],
      'candidate_hash':candidate['candidate_hash'],'selected_count':len(blocks),
      'six_bad_blocks_excluded':True,'current_board_card_415_retained':True,
      'source_log_unchanged':True,'new_real_calls':[0,0,0],
      'business_content_acceptance':False,'production_authorized':False,
      'state_root':str(STATE)}
(HERE/'enphase-update-peer60aa.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(body,sort_keys=True),flush=True)
