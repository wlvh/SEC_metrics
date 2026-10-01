"""No-network complete candidate and Evidence check for all ten target sources."""
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
from vnext.canonical import sha256_file
from vnext.normal_run_v3 import prepare_case
from vnext.c02_composition_text_results import create_deterministic_text_candidate,build_text_evidence
base=json.load(open(HERE/'c02-capacity-census.json'))
log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=log)
signal.alarm(110);rows=[]
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 for old in base['companies']:
  company=old['company_id']
  try:
   case=prepare_case(data_root=ROOT,company_id=company,metric_id='C02',c02_composition=True,c02_grouped=True)
   candidate=create_deterministic_text_candidate(**case['text_arguments'])
   evidence=build_text_evidence(candidate=candidate,**case['text_arguments'])
   assert evidence['status']=='PASS'
   rows.append({'company_id':company,'status':'COMPLETE_GROUPED_CANDIDATE_AND_EVIDENCE_PASS',
                'period_end':case['target_period']['period_end'],
                'original_selected_block_count':old['candidate_count'],
                'grouped_excerpt_count':len(candidate['selected']),
                'candidate_hash':candidate['candidate_hash'],
                'spec_closure_hash':case['compiled_specs']['C02']['spec_closure_hash']})
  except Exception as exc:
   rows.append({'company_id':company,'status':'GROUPED_CANDIDATE_OR_EVIDENCE_FAILED',
                'error_type':type(exc).__name__,'error':str(exc)[:320]})
  print(json.dumps(rows[-1],sort_keys=True),flush=True)
assert before==sha256_file(path=log)
out={'record_type':'ISSUE28_C02_TEN_COMPANY_GROUPED_MAPPED_CANDIDATE_EVIDENCE_CENSUS',
     'code_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
     'worktree_has_uncommitted_grouping_code':True,'source_log_unchanged':True,
     'rows':rows,'new_real_calls':[0,0,0],
     'scope_limit':'Complete saved-source candidate/Evidence creation only. Does not prove selector semantics, source-content completeness, native Run for all ten, or current 390 credit.'}
(HERE/'c02-grouped-candidate-census-map.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
