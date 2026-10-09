"""Measure complete ordinary C02 source proposals for the ten Issue28 companies."""
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
from vnext.canonical import content_hash,sha256_file
from vnext.normal_run_v3 import prepare_case
from vnext.c02_composition_text_results import _prepared
COMPANIES=('enphase_energy','ford_motor_company','jpmorgan_chase','lumen_technologies','macys',
           'marriott_international','paramount_skydance_paramount_global','pfizer','salesforce','southwest_airlines')
log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=log)
signal.alarm(110)
rows=[]
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 for company in COMPANIES:
  try:
   case=prepare_case(data_root=ROOT,company_id=company,metric_id='C02',c02_composition=True)
   prepared=_prepared(**{k:v for k,v in case['text_arguments'].items() if k!='compiled_spec'})
   found=[(sid,p) for sid,p in prepared['proposals'].items() if p.get('metric_id')=='C02']
   assert len(found)==1
   sid,proposal=found[0];doc=prepared['documents'][sid]
   candidates=proposal['candidates'];texts=[doc['blocks'][v['block_index']]['text'] for v in candidates]
   total=sum(map(len,texts))+max(0,len(texts)-1)
   rows.append({'company_id':company,'status':'SOURCE_PROPOSAL_READY',
                'period_end':case['target_period']['period_end'],
                'source_reference_id':sid,'document_id':doc['text_document_id'],
                'candidate_count':len(candidates),'max_text_chars_in_one_block':max(map(len,texts),default=0),
                'rendered_text_chars':total,'fits_item_64':len(candidates)<=64,
                'fits_text_64000':total<=64000,
                'candidate_indexes_hash':content_hash(value=[v['block_index'] for v in candidates])})
  except Exception as exc:
   rows.append({'company_id':company,'status':'SOURCE_PREPARATION_FAILED','error_type':type(exc).__name__,
                'reason':str(exc)[:280]})
  print(json.dumps({k:v for k,v in rows[-1].items() if k!='complete_candidate_indexes'},sort_keys=True),flush=True)
assert before==sha256_file(path=log)
out={'record_type':'ISSUE28_C02_TEN_COMPANY_COMPLETE_PROPOSAL_CAPACITY_CENSUS',
     'code_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
     'source_log_sha256':before,'source_log_unchanged':True,'companies':rows,'new_real_calls':[0,0,0],
     'limits':'Structural source-item and character census only; not independent semantic acceptance or a native >64 Result.'}
(HERE/'c02-capacity-census.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
