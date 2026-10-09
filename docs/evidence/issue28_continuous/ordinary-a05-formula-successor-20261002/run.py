"""Private normal A05 update using the explicit formula-presentation successor."""
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

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-a05-formula-successor-20261002')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


protected = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key:digest(path) for key,path in protected.items()}
assert not WORK.exists(), 'A05_EXPLAINED_PRIVATE_ROOT_ALREADY_EXISTS'
head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
changed = ('scripts/vnext/normal_run_v3.py',
    'scripts/vnext/ordinary_projection.py',
    'scripts/vnext/ordinary_update_cycle.py',
    'scripts/vnext/ordinary_a05_formula_update.py',
    'tools/vnext_normal_update.py')
code_hashes = {relative:digest(ROOT/relative) for relative in changed}
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import (
        current_processing_source, verify_processing_source)
    from vnext.requirements import load_requirement_snapshot
    from vnext.ordinary_projection import A05_FORMULA_TEXT
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    prepared = current_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        output_parent=WORK/'sources',requirement=requirement)
    source = prepared['data_root']
    verified = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source,requirement=requirement)
    assert verified['snapshot_id'] == prepared['snapshot_id']
    import vnext_normal_update
    capture = io.StringIO()
    started = time.monotonic()
    with contextlib.redirect_stdout(capture):
        rc = vnext_normal_update.main(['--process','--company','jpmorgan_chase',
            '--metric','A05','--data-root',str(source),
            '--state-root',str(WORK/'state')])
    elapsed = time.monotonic()-started
report = json.loads(capture.getvalue())
company, = report['companies']
metric, = company['metrics']
assert metric['status'] == 'CANDIDATE_READY' and rc == 0
result = metric['last_verified_candidate']['results']['A05']
row_path = Path(metric['last_verified_candidate']['rows_root'])/'A05/metrics_matrix.csv'
row, = list(csv.DictReader(row_path.open()))
assert row['formula'] == A05_FORMULA_TEXT
assert row['value'] == result['value']
assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
assert not (WORK/'state/jpmorgan_chase/metrics/A05').exists()
assert (WORK/'state/jpmorgan_chase/metrics/A05-formula-v1').exists()
old = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'ordinary-jpm-a05-current-20261002/result.json').read_text())
assert result['result_id'] == old['result_id']
after = {key:digest(path) for key,path in protected.items()}
summary = {'record_type':'ISSUE28_A05_FORMULA_PRIVATE_NORMAL_UPDATE',
    'tested_head_before_commit':head,'code_root':str(ROOT),
    'changed_code_file_sha256':code_hashes,
    'acquisition_root':str(ACQUIRED/'source-inputs'),
    'processing_root':str(source),
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'source_snapshot_id':verified['snapshot_id'],
    'elapsed_seconds':round(elapsed,3),'cli_return_code':rc,
    'status':metric['status'],'attempt_id':metric['attempt_id'],
    'result_id':result['result_id'],'result_value':result['value'],
    'formula':row['formula'],'public_row_sha256':digest(row_path),
    'new_versioned_state_root':str(WORK/'state/jpmorgan_chase/metrics/A05-formula-v1'),
    'old_private_result_id_same':True,
    'old_private_run_or_rows_rewritten':False,
    'legacy_exports_disabled':disabled,
    'protected_source_ledger_and_active_unchanged':before==after,
    'reported_calls':report['calls'],'new_real_calls':[0,0,0],
    'current_390_credit':False,'production_authorized':False}
(HERE/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:summary[key] for key in ('status','result_id','formula',
    'elapsed_seconds','protected_source_ledger_and_active_unchanged')}),flush=True)
assert before==after and report['calls']=={'provider':0,'paid':0,'sec':0}
