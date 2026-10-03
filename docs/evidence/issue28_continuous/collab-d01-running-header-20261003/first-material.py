"""Measure the ten saved filings, then exercise the ordinary CLI and cold repeat."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
import socket

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.normal_run_v3 import prepare_case
from vnext import d01_emphasis_results as old
from vnext.d01_running_header_28_v1 import derive_candidate
from vnext import text_results as frozen
from vnext.normal_annual_input import _registry_rows

LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = LEDGER/'source-inputs'
STATE = Path('/private/tmp/issue28-d01-running-header-v3-20261003')
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'


def protected():
    paths = [p for p in LEDGER.iterdir() if p.is_file()]
    paths += [SOURCE/'evidence/requests_log.csv', ROOT/'outputs/active_publication.json']
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


summary = {'base_head_with_uncommitted_patch':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           'companies':[], 'steps':[], 'new_calls':[0,0,0], 'production_authorized':False}
before = protected()


def cli(name):
    # The child CLI gets no network and the same explicit source/state roots.
    code = '''import runpy,socket,sys
from unittest.mock import patch
sys.argv=[sys.argv[1],*sys.argv[2:]]
with patch.object(socket.socket,'connect',side_effect=RuntimeError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=RuntimeError('DNS_FORBIDDEN')):
 runpy.run_path(sys.argv[0],run_name='__main__')
'''
    args=[PYTHON,'-B','-c',code,str(ROOT/'tools/vnext_normal_update.py'),'--process','--data-root',str(SOURCE),
          '--state-root',str(STATE),'--company','jpmorgan_chase','--metric','D01']
    start=time.monotonic()
    with (HERE/(name+'.log')).open('w') as log:
        done=subprocess.run(args,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
    summary['steps'].append({'name':name,'seconds':round(time.monotonic()-start,3),'return_code':done.returncode})
    assert done.returncode==0,'READ_STAGE_LOG:'+name
    report=json.loads((HERE/(name+'.log')).read_text());row=report['companies'][0]['metrics'][0]
    return row


try:
    with patch.object(socket.socket,'connect',side_effect=RuntimeError('NETWORK_FORBIDDEN')), \
         patch.object(socket,'getaddrinfo',side_effect=RuntimeError('DNS_FORBIDDEN')):
        for company in [r['company_id'] for r in _registry_rows(repo_root=ROOT)]:
            start=time.monotonic();case=prepare_case(data_root=SOURCE,company_id=company,metric_id='D01',d01_emphasis=True)
            args=case['text_arguments'];documents,coverages=old.prepare_text_sources(**args)
            shared={k:args[k] for k in ('compiled_spec','target','source_references')}
            shared.update(documents=documents,coverages=coverages)
            a=frozen._derive_deterministic_candidate(**shared);b=derive_candidate(**shared)
            lines=lambda candidate:[x['text'] for x in sorted(candidate['selected'].values(),key=lambda x:x['order'])]
            before_lines,after_lines=lines(a),lines(b)
            assert after_lines==[x for x in before_lines if x!='Parts I and II']
            if company!='jpmorgan_chase':assert a==b
            else:assert len(before_lines)==57 and len(after_lines)==56
            summary['companies'].append({'company_id':company,'old_count':len(before_lines),'new_count':len(after_lines),
                'candidate_unchanged':a==b,'source_docs_unchanged':True,'old_candidate_hash':a['candidate_hash'],
                'new_candidate_hash':b['candidate_hash'],'seconds':round(time.monotonic()-start,3)})
            print(json.dumps(summary['companies'][-1]),flush=True)
    summary['created']=cli('normal-cli')
    assert summary['created']['status']=='CANDIDATE_READY'
    attempt=STATE/'jpmorgan_chase/metrics/D01-header-v3/attempts'/summary['created']['successful_attempt']
    rs=[json.loads(x) for x in (attempt/'runs/D01/records.jsonl').read_text().splitlines()]
    result=next(r for r in rs if r['record_type']=='METRIC_RESULT' and r['metric_id']=='D01')
    assert len(result['text_payload']['items'])==56 and 'Parts I and II' not in result['value'].splitlines()
    binding=json.loads(next((attempt/'data/ordinary_integrated_bindings').glob('*.json')).read_text())
    assert binding['input_binding']['d01_emphasis_policy']=='D01_EMPHASIS_SOURCE_V3_RUNNING_HEADER'
    summary['native_result']=result;summary['native_attempt']=str(attempt)
    summary['repeat']=cli('independent-repeat')
    assert summary['repeat']['status']=='NO_SOURCE_CONTENT_CHANGE'
    assert summary['repeat']['successful_attempt']==summary['created']['successful_attempt']
    assert len(list((attempt.parent).glob('*/runs/D01/manifest.json')))==1
    summary['status']='PASS_TEN_SOURCES_ONLY_JPM_HEADER_MOVES_NORMAL_CLI_AND_REPEAT'
except Exception as error:
    summary.update(status='FAILED_D01_RUNNING_HEADER_MATERIAL',error=str(error))
    raise
finally:
    summary['protected_before']=before;summary['protected_after']=protected()
    summary['protected_unchanged']=before==summary['protected_after']
    (HERE/'material-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (HERE/'material-done.json').write_text(json.dumps({'status':summary['status']})+'\n')
