"""Match two new #47 C02 omission leads to #28 exact current Results."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_run_v3 import prepare_case
from vnext.text_results_v2 import prepare_business_text_sources
from vnext.canonical import sha256_file

PEER_SHA='0e80eb60b4ebc570abf788b8a371c22759973cd3'
PEER_ADJ='docs/evidence/issue47_history/c02-composition-facts/adjudication.json'
PEER_REG='docs/evidence/issue47_history/known_result_defects.json'
CASES=(('lumen_technologies','2025-12-31',864,'CHAIR_CEO_STRUCTURE'),
       ('macys','2026-01-31',508,'NOMINEES_ARE_SITTING_DIRECTORS'))
adj=json.loads(subprocess.check_output(['git','show',f'{PEER_SHA}:{PEER_ADJ}'],cwd=ROOT))
index_path=ROOT/'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
index=json.loads(index_path.read_text())
source_log=ROOT/'evidence/requests_log.csv'; before=sha256_file(path=source_log)
rows=[]
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 for company,period,i,rule in CASES:
  case=prepare_case(data_root=ROOT,company_id=company,metric_id='C02')
  assert case['target_period']['period_end']==period
  args={k:v for k,v in case['text_arguments'].items() if k!='compiled_spec'}
  prepared=prepare_business_text_sources(metric_id='C02',**args)
  gov=next((sid,p) for sid,p in prepared['proposals'].items() if p.get('metric_id')=='C02')
  sid,proposal=gov; doc=prepared['documents'][sid]; block=doc['blocks'][i]
  text=block['text'];sha='sha256:'+hashlib.sha256(text.encode()).hexdigest()
  judgement=next(x for x in adj['decisions'] if x.get('position')==f'{company}:{period}' and x.get('i')==i)
  assert judgement['text_sha256']==sha and judgement['rule']==rule and judgement['decision']=='FACT'
  assert i not in {x['block_index'] for x in proposal['candidates']}
  root=next(Path('/private/tmp').glob('issue28-'+company+'-current-36-cli-20260929'))
  records_path=next(root.glob('**/metrics/C02/attempts/*/runs/C02/records.jsonl'))
  records=[json.loads(s) for s in records_path.read_text().splitlines()]
  candidate=next(x for x in records if x['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
  result=next(x for x in records if x['record_type']=='METRIC_RESULT')
  manifest=json.loads((records_path.parent/'manifest.json').read_text())
  archived=next(x for x in index['rows'] if x['company_id']==company and x['metric_id']=='C02')
  assert manifest['target_period']['period_end']==result['period_end']==period
  assert result['result_id']==archived['implementation_identity']['result_id']
  assert i not in {v['block_index'] for v in candidate['selected'].values()}
  rows.append({'company_id':company,'metric_id':'C02','period_end':period,
      'archived_result_id':result['result_id'],'archived_run_id':archived['implementation_identity']['run_id'],
      'private_run_id':manifest['run_id'],'private_result_id':result['result_id'],
      'source_reference_id':sid,'document_id':doc['text_document_id'],
      'omitted_block_index':i,'omitted_text':text,'omitted_text_sha256':sha,
      'peer_rule':rule,'peer_decision':'FACT',
      'own_read':'The saved source explicitly states current chair/CEO separation.' if company=='lumen_technologies' else 'The saved source explicitly says each listed nominee is currently a Board member.',
      'old_candidate_selected_count':len(candidate['selected']),
      'original_records_path':str(records_path)})
assert before==sha256_file(path=source_log)
out={'record_type':'ISSUE28_C02_PEER_0E80_CURRENT_RESULT_OMISSIONS',
     'peer_commit':PEER_SHA,'peer_register_path':PEER_REG,
     'peer_register_git_blob':subprocess.check_output(['git','rev-parse',f'{PEER_SHA}:{PEER_REG}'],cwd=ROOT,text=True).strip(),
     'peer_adjudication_path':PEER_ADJ,
     'archived_index_path':str(index_path.relative_to(ROOT)),
     'archived_index_sha256':hashlib.sha256(index_path.read_bytes()).hexdigest(),
     'affected_new_coordinate_count':len(rows),'affected_new_result_id_count':len({r['archived_result_id'] for r in rows}),
     'rows':rows,'source_log_unchanged':True,'new_real_calls':[0,0,0],
     'scope_limit':'Two exact #28 current C02 Result identities and two saved source blocks; no full 390 or all-ten C02 audit.'}
(HERE/'peer-0e80-new-current-impact.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'new_coordinates':len(rows),'new_result_ids':[r['archived_result_id'] for r in rows]},sort_keys=True))
