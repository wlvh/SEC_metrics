"""Repeat the normal CLI: same sources retain the successful C02 Run."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch


sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
first=json.loads((HERE/'run.json').read_text());state=Path(first['state_root'])
work=state/'attempts'/first['attempt_id']
ACQUIRED=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0]=[str(ROOT),str(ROOT/'scripts'),str(ROOT/'tools')]
spec=importlib.util.spec_from_file_location('legacy_probe',ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    return {str(p.relative_to(path)):digest(p) for p in path.rglob('*') if p.is_file()}


def blocked(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


before=tree(work)
protected={'claims':ACQUIRED/'claims.jsonl','source_log':ROOT/'evidence/requests_log.csv',
           'active':ROOT/'outputs/active_publication.json'}
protected_before={key:digest(path) for key,path in protected.items()}
capture=io.StringIO();started=time.monotonic()
with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked),
      probe.legacy_disabled() as disabled):
    import vnext_normal_update
    with contextlib.redirect_stdout(capture):
        rc=vnext_normal_update.main(['--process','--company','jpmorgan_chase',
            '--metric','C02','--data-root',str(ROOT),'--state-root',
            str(state.parents[2])])
elapsed=time.monotonic()-started
(HERE/'repeat-report-repaired.json').write_text(capture.getvalue())
report=json.loads(capture.getvalue());company,=report['companies'];metric,=company['metrics']
assert rc==0 and metric['status']=='NO_SOURCE_CONTENT_CHANGE'
assert not metric['new_candidate_created'] and metric['successful_attempt']==first['attempt_id']
assert metric['last_verified_candidate']['results']['C02']['result_id']==first['result_id']
assert tree(work)==before
assert {key:digest(path) for key,path in protected.items()}==protected_before
body={'record_type':'ISSUE28_C02_MEMBER_SUCCESSOR_REPEAT_CURRENT_INPUT',
    'status':metric['status'],'result_id':first['result_id'],
    'new_candidate_created':False,'successful_attempt_retained':first['attempt_id'],
    'successful_package_file_count':len(before),'successful_package_unchanged':True,
    'elapsed_seconds':round(elapsed,3),'legacy_exports_disabled':disabled,
    'protected_unchanged':True,'new_real_calls':[0,0,0],
    'whole_content_accepted':False,'current_390_credit':False,'production_authorized':False}
(HERE/'repeat-current.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:body[key] for key in ('status','result_id',
    'new_candidate_created','elapsed_seconds')}),flush=True)
