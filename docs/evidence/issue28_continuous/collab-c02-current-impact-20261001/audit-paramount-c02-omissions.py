"""Exact #28 Paramount C02 old/private Result identities with omitted source facts."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_run_v3 import prepare_case
from vnext.text_results_v2 import prepare_business_text_sources
from vnext.canonical import sha256_file
COMP='paramount_skydance_paramount_global'
old_run=next(Path('/private/tmp/issue28-paramount_skydance_paramount_global-current-36-cli-20260929').glob('**/metrics/C02/attempts/*/runs/C02'))
new_run=next(Path('/private/tmp/issue28-c02-normal-update-paramount-peer60aa-20261001/metrics/C02/attempts').glob('*/runs/C02'))
idx_path=ROOT/'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
archived=next(x for x in json.loads(idx_path.read_text())['rows'] if x['company_id']==COMP and x['metric_id']=='C02')
source_log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=source_log)
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 case=prepare_case(data_root=ROOT,company_id=COMP,metric_id='C02',c02_composition=True)
 args={k:v for k,v in case['text_arguments'].items() if k not in ('compiled_spec','c02_selection_policy')}
 prepared=prepare_business_text_sources(metric_id='C02',**args)
 sid,_=next((sid,p) for sid,p in prepared['proposals'].items() if p.get('metric_id')=='C02')
 doc=prepared['documents'][sid]
def run(path):
 rows=[json.loads(s) for s in (path/'records.jsonl').read_text().splitlines()]
 c=next(x for x in rows if x['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
 r=next(x for x in rows if x['record_type']=='METRIC_RESULT')
 m=json.loads((path/'manifest.json').read_text())
 return c,r,m
old_c,old_r,old_m=run(old_run);new_c,new_r,new_m=run(new_run)
old_sel={v['block_index'] for v in old_c['selected'].values()};new_sel={v['block_index'] for v in new_c['selected'].values()}
assert old_r['result_id']==archived['implementation_identity']['result_id']
assert old_m['target_period']['period_end']==new_m['target_period']['period_end']=='2025-12-31'
assert new_r['result_id']=='sha256:4d469eff63d687acdc24b8ba2e22d5b2f18bc3f8c61eab8f0f7d146b19e9fc68'
blocks=[]
for i in (110,117,168):
 text=doc['blocks'][i]['text'];sha=hashlib.sha256(text.encode()).hexdigest()
 assert i not in new_sel
 if i in (117,168): assert i not in old_sel
 assert 'qualified to serve as a member of our Board' in text
 blocks.append({'block_index':i,'text_sha256':sha,'text':text,'in_old_result':i in old_sel,'in_private_successor':False})
assert 'since January 2026' in blocks[1]['text']
assert before==sha256_file(path=source_log)
body={'record_type':'ISSUE28_C02_PARAMOUNT_EXACT_RESULT_OMISSIONS','company_id':COMP,'metric_id':'C02',
      'period_end':'2025-12-31','source_reference_id':sid,'document_id':doc['text_document_id'],
      'old_archived_result_id':old_r['result_id'],'old_archived_run_id':archived['implementation_identity']['run_id'],
      'old_private_run_id':old_m['run_id'],'old_selected_count':len(old_sel),
      'new_private_result_id':new_r['result_id'],'new_private_run_id':new_m['run_id'],
      'new_selected_count':len(new_sel),'source_blocks':blocks,
      'independent_content_report':'docs/evidence/issue28_continuous/collab-c02-normal-20261001/independent-paramount54-content/conclusion.md',
      'parent_verification':'Read exact #28 original blocks 110, 117 and 168; qualification determinations and dated own-board membership are not represented by a bare current roster.',
      'source_log_unchanged':True,'new_real_calls':[0,0,0],
      'scope_limit':'Only these exact old and new #28 Result identities; not all C02 coordinates or all text omissions.'}
(HERE/'paramount-c02-exact-omissions.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'old_result':old_r['result_id'],'new_result':new_r['result_id'],'witness_blocks':[x['block_index'] for x in blocks]},sort_keys=True))
