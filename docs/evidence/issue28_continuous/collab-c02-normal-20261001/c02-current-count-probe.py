"""Bounded no-network ordinary C02 source-count probe; grants no result credit."""
import json
from pathlib import Path
import socket
import signal
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from vnext.normal_run_v3 import prepare_case
from vnext.c02_composition_text_results import _prepared
from vnext.canonical import sha256_file

log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=log)
signal.alarm(100)
rows=[]
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    for company in ('ford_motor_company','salesforce','southwest_airlines'):
        try:
            case=prepare_case(data_root=ROOT,company_id=company,metric_id='C02',c02_composition=True)
            prepared=_prepared(**{k:v for k,v in case['text_arguments'].items() if k != 'compiled_spec'})
            sources=[(sid,p) for sid,p in prepared['proposals'].items() if p.get('metric_id')=='C02']
            assert len(sources)==1
            sid,proposal=sources[0]
            rows.append({'company_id':company,'status':'SOURCE_PROPOSAL_READY',
                         'candidate_count':len(proposal['candidates']),
                         'source_reference_id':sid,
                         'candidate_block_indexes':[v['block_index'] for v in proposal['candidates']],
                         'spec_closure_hash':case['compiled_specs']['C02']['spec_closure_hash']})
        except Exception as exc:
            rows.append({'company_id':company,'status':'PREPARATION_FAILED',
                         'error_type':type(exc).__name__,'error':str(exc)[:300]})
        print(json.dumps(rows[-1],sort_keys=True),flush=True)
assert before==sha256_file(path=log)
body={'record_type':'ISSUE28_C02_ORDINARY_BOUNDED_SOURCE_COUNT','code_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      'rows':rows,'source_log_unchanged':True,'new_real_calls':[0,0,0],
      'limitation':'Counts only under current pinned selector, not content acceptance or a native Run.'}
(HERE/'c02-current-count-probe.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
