"""Exercise the actual current A05 CLI on a lawful nonfinancial N/A."""
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
WORK=Path('/private/tmp/issue28-a05-formula-na-cli-20261002')
ACQUIRED=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0]=[str(ROOT),str(ROOT/'scripts'),str(ROOT/'tools')]
spec=importlib.util.spec_from_file_location('legacy_probe',ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


assert not WORK.exists(),'A05_NA_CLI_PRIVATE_ROOT_ALREADY_EXISTS'
protected={'claims':ACQUIRED/'claims.jsonl',
    'source_log':ROOT/'evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json'}
before={k:digest(p) for k,p in protected.items()}
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
projection_sha=digest(ROOT/'scripts/vnext/ordinary_projection.py')
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    import vnext_normal_update
    outputs=[]
    for _ in range(2):
        captured=io.StringIO();started=time.monotonic()
        with contextlib.redirect_stdout(captured):
            code=vnext_normal_update.main(['--process','--company',
                'marriott_international','--metric','A05','--data-root',
                str(ROOT),'--state-root',str(WORK/'state')])
        elapsed=time.monotonic()-started
        report=json.loads(captured.getvalue());company,=report['companies']
        metric,=company['metrics']
        assert code==0 and report['calls']=={'provider':0,'paid':0,'sec':0}
        outputs.append({'status':metric['status'],'attempt_id':metric['attempt_id'],
            'successful_attempt':metric['successful_attempt'],
            'new_candidate_created':metric['new_candidate_created'],
            'elapsed_seconds':round(elapsed,3),
            'result_id':metric['last_verified_candidate']['results']['A05']['result_id'],
            'result':metric['last_verified_candidate']['results']['A05'],
            'rows_root':metric['last_verified_candidate']['rows_root']})
after={k:digest(p) for k,p in protected.items()}
first,second=outputs
assert first['status']=='CANDIDATE_READY'
assert second['status']=='NO_SOURCE_CONTENT_CHANGE'
assert not second['new_candidate_created']
assert first['successful_attempt']==second['successful_attempt']==first['attempt_id']
assert first['result_id']==second['result_id']
result=first['result']
assert result['publication']=='PUBLISHED' and result['applicability']=='N_A_STRUCTURAL'
assert result['quality']=='NONE' and result['value'] is None
assert result['reason_code']=='TRAIT_NOT_APPLICABLE'
row_path=Path(first['rows_root'])/'A05/metrics_matrix.csv'
row,=list(csv.DictReader(row_path.open()))
assert row['formula']=='' and row['value']==''
assert not (WORK/'state/marriott_international/metrics/A05').exists()
assert (WORK/'state/marriott_international/metrics/A05-formula-v1').exists()
body={'record_type':'ISSUE28_A05_FORMULA_NA_CURRENT_NORMAL_CLI',
    'tested_head_before_commit':head,'projection_sha256':projection_sha,
    'source_root':str(ROOT),'company_id':'marriott_international',
    'first_status':first['status'],'repeat_status':second['status'],
    'first_seconds':first['elapsed_seconds'],
    'repeat_seconds':second['elapsed_seconds'],
    'result_id':first['result_id'],'result_applicability':result['applicability'],
    'result_reason':result['reason_code'],'result_value':result['value'],
    'public_formula':row['formula'],'public_value':row['value'],
    'public_row_sha256':digest(row_path),'no_second_run':True,
    'old_a05_journal_absent':True,'legacy_exports_disabled':disabled,
    'protected_claims_source_log_active_unchanged':before==after,
    'new_real_calls':[0,0,0],'production_authorized':False}
(HERE/'na-repair-nonfinancial.json').write_text(json.dumps(body,ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'first':body['first_status'],'repeat':body['repeat_status'],
    'result_id':body['result_id'],'formula_blank':body['public_formula']=='',
    'no_second_run':True}),flush=True)
assert before==after
