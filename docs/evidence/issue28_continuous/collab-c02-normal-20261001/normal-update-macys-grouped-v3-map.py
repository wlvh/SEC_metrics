"""No-network full ordinary C02 native update from Macy's 99 original facts."""
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
STATE=Path('/private/tmp/issue28-c02-normal-update-macys-grouped-v3-map-20261001')
assert not STATE.exists()
source_log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=source_log)
signal.alarm(1200)
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 first=run_company(state_root=STATE,source_root=ROOT,company_id='macys',metric_ids=['C02'])
 second=run_company(state_root=STATE,source_root=ROOT,company_id='macys',metric_ids=['C02'])
assert before==sha256_file(path=source_log)
one,two=first['metrics'][0],second['metrics'][0]
assert one['status']=='CANDIDATE_READY' and two['status']=='NO_SOURCE_CONTENT_CHANGE'
assert one['successful_attempt']==two['successful_attempt']
result=one['last_verified_candidate']['results']['C02']
run=STATE/'metrics/C02/attempts'/one['successful_attempt']/'runs/C02'
manifest=json.loads((run/'manifest.json').read_text())
rows=[json.loads(s) for s in (run/'records.jsonl').read_text().splitlines()]
candidate=next(x for x in rows if x['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
assert len(candidate['selected'])==29
body={'record_type':'ISSUE28_C02_MACYS_GROUPED_MAPPED_PRIVATE_NORMAL_UPDATE',
      'company_id':'macys','fiscal_year':2025,'period_end':'2026-01-31',
      'original_selected_source_blocks':99,'grouped_excerpt_count':29,
      'first_status':one['status'],'repeat_status':two['status'],
      'run_id':manifest['run_id'],'result_id':result['result_id'],
      'candidate_hash':candidate['candidate_hash'],'spec_file_hashes':manifest['spec_file_hashes'],
      'requirement_closure_hash':manifest['requirement_closure_hash'],
      'source_log_unchanged':True,'new_real_calls':[0,0,0],
      'business_content_acceptance':False,'production_authorized':False,
      'state_root':str(STATE)}
(HERE/'macys-grouped-v3-map-update.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in body.items() if k!='spec_file_hashes'},sort_keys=True),flush=True)
