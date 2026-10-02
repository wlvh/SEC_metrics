"""Independent-process read of all ten bound E01 source-only inputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
first = json.loads((HERE/'current-source.json').read_text())
assert first['prepared'] == 10 and first['stopped'] == 0
source = Path(first['processing_root'])
assert (source/'scripts/vnext/e01_item_text_28_v1.py').is_file()
assert (source/'scripts/vnext/ordinary_e01_item_text_input.py').is_file()
sys.path[:0] = [str(source),str(source/'scripts')]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
protected = {'claims':ACQUIRED/'claims.jsonl',
    'source_log':ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json'}
before = {name:digest(path) for name,path in protected.items()}


def blocked(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


start = time.monotonic()
with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked),
      probe.legacy_disabled() as disabled):
    from vnext import ordinary_e01_item_text_input as module
    from vnext.requirements import load_requirement_snapshot
    from vnext.requirement_profile_v1 import validate_execution_authority
    from vnext.ordinary_processing_source import verify_processing_source
    assert Path(module.__file__).is_relative_to(source)
    requirement = load_requirement_snapshot(
        snapshot_dir=source/'requirements/issue_28_v14')
    assert requirement['requirement_closure_hash'] == first['requirement_closure_hash']
    validate_execution_authority(repo_root=source,requirement=requirement)
    receipt = verify_processing_source(acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source,requirement=requirement)
    assert receipt['snapshot_id'] == first['source_snapshot_id']
    for expected in first['rows']:
        value = module.prepare_current_e01_item_text(
            repo_root=source,company_id=expected['company_id'])
        assert expected['status']=='PREPARED'
        assert value['input_id']==expected['input_id']
        assert value['candidate_count']==expected['candidate_count']
        assert [item['item_text']['text_sha256'] for item in value['items']] == expected['item_text_sha256']
        assert not value['metric_result_created']
elapsed = time.monotonic()-start
after = {name:digest(path) for name,path in protected.items()}
summary = {'record_type':'ISSUE28_BOUND_E01_ITEM_TEXT_INSTALLED_COLD_READ',
    'processing_root':str(source),
    'installed_module_path':str(Path(module.__file__)),
    'requirement_closure_hash':first['requirement_closure_hash'],
    'source_snapshot_id':first['source_snapshot_id'],
    'companies_rebuilt':len(first['rows']),
    'candidate_items_rebuilt':sum(row['candidate_count'] for row in first['rows']),
    'all_input_ids_and_item_sha256_equal':True,
    'elapsed_seconds':round(elapsed,3),
    'legacy_exports_disabled':disabled,
    'protected_claims_source_log_active_unchanged':before==after,
    'new_real_calls':[0,0,0],
    'new_result_or_run':False,'current_390_credit':False,
    'production_authorized':False}
(HERE/'current-source-cold.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'companies':summary['companies_rebuilt'],
    'items':summary['candidate_items_rebuilt'],
    'same_input_ids':True,'elapsed_seconds':summary['elapsed_seconds'],
    'new_real_calls':[0,0,0]}),flush=True)
assert before==after
