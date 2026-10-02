"""Read one installed E01 input with only its own pinned runtime/source files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
ACQUIRED=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
company=sys.argv[1]
summary=json.loads((HERE/'installed.json').read_text())
expected=next(row for row in summary['rows'] if row['company_id']==company)
data=Path(expected['installed_root'])


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


spec=importlib.util.spec_from_file_location('legacy_probe',ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
sys.path[:0]=[str(data),str(data/'scripts')]
protected={'claims':ACQUIRED/'claims.jsonl',
    'source_log':ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json'}
before={name:digest(path) for name,path in protected.items()}


def blocked(*args,**kwargs):raise AssertionError('NETWORK_FORBIDDEN')


started=time.monotonic()
with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked),
      probe.legacy_disabled() as disabled):
    from vnext import ordinary_e01_item_text_input_v2 as module
    from vnext.requirements import load_requirement_snapshot
    from vnext.requirement_profile_v1 import validate_execution_authority
    assert Path(module.__file__).is_relative_to(data)
    requirement=load_requirement_snapshot(
        snapshot_dir=data/'requirements/issue_28_v13')
    assert requirement['requirement_closure_hash']==summary['installed_requirement_closure_hash']
    validate_execution_authority(repo_root=data,requirement=requirement)
    candidate=module.prepare_current_e01_item_text(repo_root=data,
                                                     company_id=company)
    assert module.verify_current_e01_item_text(candidate=candidate,
        repo_root=data,company_id=company)==candidate
    assert candidate['input_id']==expected['installed_input_id']
    assert candidate['candidate_count']==expected['candidate_count']
    assert len(candidate['header_document_checks'])==expected['header_document_checks']
    from vnext import e01_header_document_guard_28_v1 as guard
    assert Path(guard.__file__).is_relative_to(data)
    assert digest(Path(guard.__file__))==expected['installed_guard_sha256']
    assert [item['item_text']['text_sha256'] for item in candidate['items']]==expected['item_text_sha256']
elapsed=time.monotonic()-started
after={name:digest(path) for name,path in protected.items()}
body={'record_type':'ISSUE28_E01_V2_BODY_HEADER_INSTALLED_COLD_READ',
    'company_id':company,'installed_root':str(data),
    'installed_module_path':str(Path(module.__file__)),
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'input_id':candidate['input_id'],
    'candidate_count':candidate['candidate_count'],
    'header_document_checks':len(candidate['header_document_checks']),
    'installed_guard_path':str(Path(guard.__file__)),
    'elapsed_seconds':round(elapsed,3),
    'legacy_exports_disabled':disabled,
    'protected_claims_source_log_active_unchanged':before==after,
    'new_real_calls':[0,0,0],'metric_result_created':False,
    'production_authorized':False}
(HERE/('installed-cold-'+company+'.json')).write_text(
    json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'company':company,'candidate_count':candidate['candidate_count'],
    'same_input_id':True,'elapsed_seconds':body['elapsed_seconds'],
    'new_real_calls':[0,0,0]}),flush=True)
assert before==after
