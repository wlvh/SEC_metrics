"""Read the new C02 Run in another process using its installed code."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch


sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
first=json.loads((HERE/'run.json').read_text())
data=Path(first['installed_data_root']);run=Path(first['run_dir'])
state=Path(first['state_root']);work=state/'attempts'/first['attempt_id']
ACQUIRED=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
spec=importlib.util.spec_from_file_location('legacy_probe',ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
sys.path[:0]=[str(data),str(data/'scripts'),str(ROOT),str(ROOT/'scripts')]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blocked(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


protected={'run_records':run/'records.jsonl','run_manifest':run/'manifest.json',
    'state_pointer':state/'current.json','claims':ACQUIRED/'claims.jsonl',
    'source_log':ROOT/'evidence/requests_log.csv','active':ROOT/'outputs/active_publication.json'}
before={key:digest(path) for key,path in protected.items()}
started=time.monotonic()
with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked),
      probe.legacy_disabled() as disabled):
    from vnext import ordinary_projection as installed
    from vnext import c02_board_composition_28_v4 as selector
    from vnext.requirements import load_requirement_snapshot
    from vnext.requirement_profile_v1 import validate_execution_authority
    assert Path(installed.__file__).is_relative_to(data)
    assert Path(selector.__file__).is_relative_to(data)
    requirement=load_requirement_snapshot(snapshot_dir=data/'requirements/issue_28_v13')
    assert requirement['requirement_closure_hash']==first['requirement_closure_hash']
    validate_execution_authority(repo_root=data,requirement=requirement)
    rendered=installed.render_ordinary_run(data_root=data,run_dir=run)
    assert rendered['receipt']['result_id']==first['result_id']
    for name,raw in rendered['files'].items():
        assert raw==(work/'rows/C02'/name).read_bytes()
elapsed=time.monotonic()-started
after={key:digest(path) for key,path in protected.items()}
assert before==after
body={'record_type':'ISSUE28_C02_MEMBER_SUCCESSOR_INSTALLED_COLD_READ',
    'installed_data_root':str(data),'installed_projector':str(installed.__file__),
    'installed_selector':str(selector.__file__),
    'installed_selector_sha256':digest(Path(selector.__file__)),
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'result_id':first['result_id'],'public_row_sha256':hashlib.sha256(
        rendered['files']['metrics_matrix.csv']).hexdigest(),
    'elapsed_seconds':round(elapsed,3),'legacy_exports_disabled':disabled,
    'protected_unchanged':True,'new_real_calls':[0,0,0],
    'whole_content_accepted':False,'current_390_credit':False,'production_authorized':False}
(HERE/'cold-installed.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'result_id':body['result_id'],'same_rows':True,
    'installed_selector':body['installed_selector'],'elapsed_seconds':body['elapsed_seconds'],
    'calls':[0,0,0]}),flush=True)
