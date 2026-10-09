"""Bounded, network-disabled profile of one actual Salesforce A05 update."""
import contextlib
import cProfile
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import pstats
import socket
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-update-latency-a05-20261001')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts'), str(ROOT / 'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT /
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


protected = {'claims': ACQUIRED / 'claims.jsonl',
    'source_log': ACQUIRED / 'source-inputs/evidence/requests_log.csv',
    'active': ROOT / 'outputs/active_publication.json'}
before = {key: digest(path) for key, path in protected.items()}
assert not WORK.exists()
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import (
        current_processing_source, verify_processing_source)
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT / 'requirements' / REQUIREMENT_ID)
    source_started = time.monotonic()
    prepared_source = current_processing_source(
        acquisition_root=ACQUIRED / 'source-inputs',
        output_parent=WORK / 'sources', requirement=requirement)
    source_elapsed = time.monotonic() - source_started
    source = prepared_source['data_root']
    verified = verify_processing_source(
        acquisition_root=ACQUIRED / 'source-inputs',
        processing_root=source, requirement=requirement)
    assert verified['snapshot_id'] == prepared_source['snapshot_id']
    import vnext_normal_update
    profiler = cProfile.Profile()
    capture = io.StringIO()
    started = time.monotonic()
    with contextlib.redirect_stdout(capture):
        profiler.enable()
        rc = vnext_normal_update.main(['--process', '--company', 'salesforce',
            '--metric', 'A05', '--data-root', str(source),
            '--state-root', str(WORK / 'state')])
        profiler.disable()
    elapsed = time.monotonic() - started
report = json.loads(capture.getvalue())
company, = report['companies']
metric, = company['metrics']
after = {key: digest(path) for key, path in protected.items()}
summary = {'record_type': 'ISSUE28_SALESFORCE_A05_SINGLE_UPDATE_PROFILE',
    'company_id': company['company_id'], 'metric_id': metric['metric_id'],
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'source_snapshot_id': verified['snapshot_id'], 'elapsed_seconds': elapsed,
    'source_copy_elapsed_seconds': source_elapsed,
    'source_copy_reused': prepared_source['reused'],
    'cli_return_code': rc, 'status': metric['status'],
    'legacy_exports_disabled': disabled,
    'protected_source_ledger_and_active_unchanged': before == after,
    'reported_calls': report['calls'], 'new_real_calls': [0, 0, 0],
    'production_authorized': False}
(HERE / 'result.json').write_text(json.dumps(summary, ensure_ascii=False,
    indent=2) + '\n')
with (HERE / 'profile.txt').open('w') as stream:
    stats = pstats.Stats(profiler, stream=stream).strip_dirs()
    stats.sort_stats('cumulative').print_stats(65)
print(json.dumps({key: summary[key] for key in ('metric_id', 'status',
    'elapsed_seconds', 'protected_source_ledger_and_active_unchanged',
    'reported_calls')}, sort_keys=True), flush=True)
assert metric['metric_id'] == 'A05' and before == after
assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
