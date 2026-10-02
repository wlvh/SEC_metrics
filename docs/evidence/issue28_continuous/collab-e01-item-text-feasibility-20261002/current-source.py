"""Exercise the new #28 E01 source-only input on its cumulative processing copy."""
import contextlib
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
WORK = Path('/private/tmp/issue28-e01-current-item-bound-20261002')
sys.path[:0] = [str(ROOT),str(ROOT/'scripts')]
spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


protected = {'claims':ACQUIRED/'claims.jsonl',
    'source_log':ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json'}
before = {name:digest(path) for name,path in protected.items()}
assert not WORK.exists(), 'E01_PRIVATE_PROCESSING_ROOT_ALREADY_EXISTS'
companies = ('marriott_international','southwest_airlines','ford_motor_company',
    'pfizer','jpmorgan_chase','salesforce','lumen_technologies','macys',
    'paramount_skydance_paramount_global','enphase_energy')


def blocked(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


start = time.monotonic()
with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked),
      probe.legacy_disabled() as disabled):
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import (
        current_processing_source, verify_processing_source)
    from vnext.requirements import load_requirement_snapshot
    from vnext.ordinary_e01_item_text_input import (
        prepare_current_e01_item_text, verify_current_e01_item_text)
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    copied = current_processing_source(acquisition_root=ACQUIRED/'source-inputs',
        output_parent=WORK/'sources',requirement=requirement)
    source = Path(copied['data_root'])
    verified = verify_processing_source(acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source,requirement=requirement)
    assert verified['snapshot_id'] == copied['snapshot_id']
    rows = []
    for company in companies:
        try:
            item_set = prepare_current_e01_item_text(repo_root=source,
                                                      company_id=company)
            if company in ('pfizer','paramount_skydance_paramount_global'):
                verify_current_e01_item_text(candidate=item_set,
                    repo_root=source,company_id=company)
            rows.append({'company_id':company,'status':'PREPARED',
                'candidate_count':item_set['candidate_count'],
                'input_id':item_set['input_id'],
                'source_credit':item_set['source_admission']['source_credit'],
                'item_text_sha256':[item['item_text']['text_sha256']
                                    for item in item_set['items']],
                'semantic_confirmation_status':item_set['semantic_confirmation_status'],
                'new_result':item_set['metric_result_created']})
        except Exception as error:
            rows.append({'company_id':company,'status':'STOP',
                         'error_type':type(error).__name__,
                         'reason':str(error)[:350]})
elapsed = time.monotonic()-start
after = {name:digest(path) for name,path in protected.items()}
summary = {'record_type':'ISSUE28_CURRENT_E01_ITEM_TEXT_PROCESSING_SOURCE',
    'code_root':str(ROOT),'acquisition_root':str(ACQUIRED/'source-inputs'),
    'processing_root':str(source),
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'source_snapshot_id':verified['snapshot_id'],
    'rows':rows,'prepared':sum(row['status']=='PREPARED' for row in rows),
    'stopped':sum(row['status']=='STOP' for row in rows),
    'total_items':sum(row.get('candidate_count',0) for row in rows),
    'elapsed_seconds':round(elapsed,3),
    'legacy_exports_disabled':disabled,
    'protected_claims_source_log_active_unchanged':before==after,
    'new_real_calls':[0,0,0], 'new_result_or_run':False,
    'current_390_credit':False,'production_authorized':False}
(HERE/'current-source.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'prepared':summary['prepared'],'stopped':summary['stopped'],
    'total_items':summary['total_items'],
    'elapsed_seconds':summary['elapsed_seconds'],
    'new_real_calls':[0,0,0]}),flush=True)
assert before==after
