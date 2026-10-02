"""Install explicit E01 V3 body/header inputs with exact V13 runtime."""
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
WORK=Path('/private/tmp/issue28-e01-layout-v3-installed-20261003')
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
spec=importlib.util.spec_from_file_location('legacy_probe',ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


first=json.loads((ROOT/'docs/evidence/issue28_continuous/collab-e01-item-text-feasibility-20261002/current-source.json').read_text())
source=Path(first['processing_root'])
assert source.is_dir() and not WORK.exists()
expected={row['company_id']:row for row in first['rows']}
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
    from vnext.ordinary_e01_item_text_input_v3 import install_current_e01_item_text
    from vnext.requirements import load_requirement_snapshot
    requirement=load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements/issue_28_v13')
    rows=[]
    for company in ('enphase_energy','pfizer'):
        output=WORK/company
        candidate=install_current_e01_item_text(source_root=source,
            data_root=output,company_id=company)
        prior=expected[company]
        assert candidate['candidate_count']==prior['candidate_count']
        assert [item['item_text']['text_sha256'] for item in candidate['items']]==prior['item_text_sha256']
        rows.append({'company_id':company,'installed_root':str(output),
            'candidate_count':candidate['candidate_count'],
            'old_input_id':prior['input_id'],
            'header_document_checks':len(candidate['header_document_checks']),
            'record_type':candidate['record_type'],
            'guard_source_commit':candidate['header_document_guard']['source_patch_commit'],
            'installed_guard_sha256':digest(output/'scripts/vnext/e01_header_document_guard_28_v2.py'),
            'installed_input_id':candidate['input_id'],
            'item_text_sha256':prior['item_text_sha256'],
            'source_credit':candidate['source_admission']['source_credit'],
            'installed_reader_sha256':digest(output/'scripts/vnext/e01_item_text_28_v2.py'),
            'installed_adapter_sha256':digest(output/'scripts/vnext/ordinary_e01_item_text_input_v3.py')})
elapsed=time.monotonic()-started
after={name:digest(path) for name,path in protected.items()}
summary={'record_type':'ISSUE28_E01_V3_BODY_HEADER_SOURCE_ONLY_RUNTIME_INSTALL',
    'source_root':str(source),
    'source_snapshot_id':first['source_snapshot_id'],
    'installed_requirement_closure_hash':requirement['requirement_closure_hash'],
    'rows':rows,'installed_company_count':len(rows),
    'installed_candidate_items':sum(row['candidate_count'] for row in rows),
    'elapsed_seconds':round(elapsed,3),
    'legacy_exports_disabled':disabled,
    'protected_claims_source_log_active_unchanged':before==after,
    'new_real_calls':[0,0,0],
    'new_result_or_run':False,'production_authorized':False}
(HERE/'installed.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'installed_companies':summary['installed_company_count'],
    'candidate_items':summary['installed_candidate_items'],
    'elapsed_seconds':summary['elapsed_seconds'],
    'new_real_calls':[0,0,0]}),flush=True)
assert before==after
