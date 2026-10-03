"""One normal CLI pass for B01 and the explicit C04 successor, offline."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-marriott-cli-b01-c04-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT /
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
phase = sys.argv[1]
assert phase in {'create', 'read', 'repeat'}
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import (current_processing_source,
                                                   verify_processing_source)
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    if phase == 'create':
        assert not WORK.exists()
        source = current_processing_source(
            acquisition_root=ACQUIRED/'source-inputs',
            output_parent=WORK/'sources', requirement=requirement)
        source_root = Path(source['data_root'])
        import vnext_normal_update
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            rc = vnext_normal_update.main(['--process', '--company',
                'marriott_international', '--metric', 'B01', '--metric', 'C04',
                '--data-root', str(source_root), '--state-root',
                str(WORK/'state')])
        report = json.loads(capture.getvalue())
        company, = report['companies']
        rows = {row['metric_id']: row for row in company['metrics']}
        assert rc == 0 and company['status'] == 'UPDATES_READY'
        assert set(rows) == {'B01', 'C04'}
        assert all(row['status'] == 'CANDIDATE_READY' for row in rows.values())
        body = {'source_root': str(source_root),
            'source_snapshot_id': source['snapshot_id'],
            'requirement_closure_hash': requirement['requirement_closure_hash'],
            'old_semantic_exports_disabled': disabled,
            'normal_cli_status': company['status'],
            'metric_statuses': {metric: row['status'] for metric, row in rows.items()},
            'result_ids': {metric: row['last_verified_candidate']['results'][metric]['result_id']
                for metric, row in rows.items()},
            'calls': report['calls'],
            'originals_unchanged': before == {key: digest(path) for key, path in originals.items()}}
        assert body['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
        assert body['originals_unchanged']
        (HERE/'create.json').write_text(json.dumps(body, indent=2) + '\n')
        print(json.dumps(body, sort_keys=True), flush=True)
    elif phase == 'read':
        from vnext import ordinary_update_cycle as cycle
        from vnext import c04_update_cycle as c04
        from vnext.canonical import strict_json_file
        saved = json.loads((HERE/'create.json').read_text())
        source_root = Path(saved['source_root'])
        verified = verify_processing_source(
            acquisition_root=ACQUIRED/'source-inputs',
            processing_root=source_root, requirement=requirement)
        assert verified['snapshot_id'] == saved['source_snapshot_id']
        results = {}
        for metric, suffix, validator in (
                ('B01', 'B01', cycle._verify_candidate),
                ('C04', 'C04-registration-v3', c04._verify_candidate)):
            root = WORK/'state/marriott_international/metrics'/suffix
            configuration = strict_json_file(path=root/'configuration.json')
            assert configuration['company_id'] == 'marriott_international'
            state = cycle._state(root, configuration)
            assert state['successful_attempt'] is not None
            terminal = cycle._terminal(root, state['successful_attempt'])
            result = validator(root, terminal, configuration)[metric]
            assert result['result_id'] == saved['result_ids'][metric]
            assert result['publication'] == 'PUBLISHED'
            results[metric] = {'result_id': result['result_id'],
                'publication': result['publication'],
                'reason_code': result['reason_code'],
                'period_end': result['period_end'],
                'value': result['value']}
            if metric == 'C04':
                assert configuration['route'] == c04.ROUTE
        assert results['B01']['value'] == '26186000000'
        assert results['C04']['value'] == '0'
        assert results['B01']['period_end'] == results['C04']['period_end'] == '2025-12-31'
        after = {key: digest(path) for key, path in originals.items()}
        assert before == after
        body = {'source_snapshot_id': saved['source_snapshot_id'],
            'old_semantic_exports_disabled': disabled,
            'cold_results': results, 'originals_unchanged': True,
            'calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'new_complete_business_coordinates': 0}
        (HERE/'read.json').write_text(json.dumps(body, indent=2) + '\n')
        print(json.dumps(body, sort_keys=True), flush=True)
    else:
        from vnext.canonical import strict_json_file
        import vnext_normal_update
        saved = json.loads((HERE/'create.json').read_text())
        roots = {'B01': WORK/'state/marriott_international/metrics/B01',
            'C04': WORK/'state/marriott_international/metrics/C04-registration-v3'}
        previous = {metric: strict_json_file(path=root/'current.json')['successful_attempt']
            for metric, root in roots.items()}
        assert all(previous.values())
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            rc = vnext_normal_update.main(['--process', '--company',
                'marriott_international', '--metric', 'B01', '--metric', 'C04',
                '--data-root', saved['source_root'], '--state-root',
                str(WORK/'state')])
        report = json.loads(capture.getvalue())
        company, = report['companies']
        rows = {row['metric_id']: row for row in company['metrics']}
        current = {metric: strict_json_file(path=root/'current.json')['successful_attempt']
            for metric, root in roots.items()}
        assert rc == 0 and company['status'] == 'UPDATES_READY'
        assert set(rows) == {'B01', 'C04'}
        assert all(row['status'] == 'NO_SOURCE_CONTENT_CHANGE'
                   and not row['new_candidate_created'] for row in rows.values())
        assert previous == current
        after = {key: digest(path) for key, path in originals.items()}
        assert before == after
        body = {'status': company['status'],
            'metric_statuses': {metric: row['status'] for metric, row in rows.items()},
            'successful_attempts_unchanged': previous == current,
            'old_semantic_exports_disabled': disabled,
            'originals_unchanged': True,
            'calls': report['calls']}
        assert body['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
        (HERE/'repeat.json').write_text(json.dumps(body, indent=2) + '\n')
        print(json.dumps(body, sort_keys=True), flush=True)
