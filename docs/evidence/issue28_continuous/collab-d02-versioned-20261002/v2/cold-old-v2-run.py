"""Read the pre-gate private v2 Run with its own installed runtime only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
ACQUIRED=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
prior=json.loads((HERE/'run-final.json').read_text())
state=Path('/private/tmp/issue28-d02-versioned-v2-final-20261002/state/lumen_technologies/metrics/D02-item8-v2')
work=state/'attempts'/prior['attempt_id']
data=work/'data'
run=work/'runs/D02'
spec=importlib.util.spec_from_file_location('legacy_probe',ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
sys.path[:0]=[str(data),str(data/'scripts'),str(ROOT),str(ROOT/'scripts')]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blocked(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


protected={'prior_current':state/'current.json',
    'prior_run_manifest':run/'manifest.json',
    'prior_run_records':run/'records.jsonl',
    'claims':ACQUIRED/'claims.jsonl',
    'source_log':ROOT/'evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json'}
before={key:digest(path) for key,path in protected.items()}
with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked),
      probe.legacy_disabled() as disabled):
    from vnext import ordinary_projection as installed
    assert Path(installed.__file__).is_relative_to(data)
    rendered=installed.render_ordinary_run(data_root=data,run_dir=run)
    assert rendered['receipt']['result_id']==prior['new_private_result_id']
after={key:digest(path) for key,path in protected.items()}
assert before==after
result={'record_type':'ISSUE28_D02_V2_PRE_GATE_PRIVATE_RUN_OWN_RUNTIME_COLD_READ',
    'installed_module_path':str(installed.__file__),
    'result_id':prior['new_private_result_id'],
    'public_row_sha256':hashlib.sha256(rendered['files']['metrics_matrix.csv']).hexdigest(),
    'protected_prior_run_ledger_active_unchanged':True,
    'legacy_exports_disabled':disabled,'new_real_calls':[0,0,0],
    'current_result_credit':False}
(HERE/'cold-old-v2-run.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'result_id':result['result_id'],
    'installed_module':result['installed_module_path'],
    'protected_unchanged':True,'calls':[0,0,0]}))
