"""Compare #28's installed shared C02 selector with fixed peer 60aa on own sources."""
import hashlib
import types
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_run_v3 import prepare_case
from vnext.text_results_v2 import prepare_business_text_sources
from vnext.historical_board_composition import board_composition_facts as own_reader
from vnext.canonical import sha256_file
PEER_SHA='60aa9f7b5b12289c74776f2320bc827d71b7c857'
peer_file=Path('/private/tmp/issue28-peer60aa-historical_board_composition.py')
assert peer_file.read_bytes()==subprocess.check_output(['git','show',f'{PEER_SHA}:scripts/vnext/historical_board_composition.py'],cwd=ROOT)
peer=types.ModuleType('vnext.historical_board_composition_peer60aa')
peer.__package__='vnext'
peer.__file__=str(ROOT/'scripts/vnext/historical_board_composition.py')
sys.modules[peer.__name__]=peer
exec(compile(peer_file.read_bytes(),peer.__file__,'exec'),peer.__dict__)
assert peer._TERMS_PATH.read_bytes()==subprocess.check_output(['git','show',f'{PEER_SHA}:catalog/r6/C02_board_composition_terms_v1.json'],cwd=ROOT)
source_log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=source_log)
signal.alarm(100);rows=[]
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 for company in ('enphase_energy','lumen_technologies','macys','marriott_international','salesforce'):
  case=prepare_case(data_root=ROOT,company_id=company,metric_id='C02')
  args={k:v for k,v in case['text_arguments'].items() if k!='compiled_spec'}
  prepared=prepare_business_text_sources(metric_id='C02',**args)
  sid,_=next((sid,p) for sid,p in prepared['proposals'].items() if p.get('metric_id')=='C02')
  doc=prepared['documents'][sid]
  old=own_reader(document=doc);new=peer.board_composition_facts(document=doc)
  assert old['document_id']==new['document_id']==doc['text_document_id']
  a={x['block_index'] for x in old['candidates']};b={x['block_index'] for x in new['candidates']}
  row={'company_id':company,'period_end':case['target_period']['period_end'],
       'source_reference_id':sid,'source_document_id':doc['text_document_id'],
       'own_877_count':len(a),'peer_60aa_count':len(b),
       'added_by_peer':sorted(b-a),'removed_by_peer':sorted(a-b),
       'peer_within_native_64':len(b)<=64}
  rows.append(row);print(json.dumps(row,sort_keys=True),flush=True)
assert before==sha256_file(path=source_log)
out={'record_type':'ISSUE28_C02_PEER_60AA_SELECTION_COMPARISON','own_code_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
     'peer_sha':PEER_SHA,'peer_code_file_sha256':hashlib.sha256(peer_file.read_bytes()).hexdigest(),
     'rows':rows,'source_log_unchanged':True,'new_real_calls':[0,0,0],
     'limitation':'Offline proposal comparison only. No new native Run, content acceptance, or use of #47 result credit.'}
(HERE/'peer-60aa-selection-impact.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
