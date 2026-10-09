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
import fcntl

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.normal_run_v3 import prepare_case
from vnext import d01_emphasis_results as old
from vnext.d01_running_header_28_v1 import derive_candidate
from vnext import text_results as frozen
from vnext.normal_annual_input import _registry_rows

LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
ACQUISITION = LEDGER/'source-inputs'
SOURCE = ACQUISITION
STATE = Path('/private/tmp/issue28-d01-running-header-v3-20261003-final')
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'


def protected():
    paths = [p for p in LEDGER.iterdir() if p.is_file()]
    paths += [ACQUISITION/'evidence/requests_log.csv', ROOT/'outputs/active_publication.json']
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
    from vnext.ordinary_processing_source import current_processing_source
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
    lock = os.open(LEDGER, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        selected = current_processing_source(acquisition_root=ACQUISITION,
            output_parent=Path('/private/tmp/issue28-d01-running-header-processing-20261003'),
            requirement=requirement)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN);os.close(lock)
    SOURCE = selected['data_root']
    summary['current_processing_snapshot'] = {**selected, 'data_root':str(SOURCE)}
    with patch.object(socket.socket,'connect',side_effect=RuntimeError('NETWORK_FORBIDDEN')), \
         patch.object(socket,'getaddrinfo',side_effect=RuntimeError('DNS_FORBIDDEN')):
        passed=json.loads((HERE/'second-material-summary.json').read_text())['companies']
        assert len(passed)==10 and all(row['candidate_unchanged'] for row in passed if row['company_id']!='jpmorgan_chase')
        summary['companies']=passed
        summary['reused_passed_census']=True
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
