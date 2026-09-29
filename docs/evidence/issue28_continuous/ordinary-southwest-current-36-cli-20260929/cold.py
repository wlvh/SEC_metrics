"""Reopen every Southwest Run created by the normal CLI in a new process."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-southwest-current-36-cli-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = Path('/private/tmp/issue28-marriott-cli-b01-c04-20260929/sources/'
    'cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228')
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
created = json.loads((HERE/'result.json').read_text())
assert created['metric_count'] == 36 and created['status'] == 'UPDATES_PARTIAL'
assert created['normal_cli_return_code'] == 2
expected = {row['metric_id']: row for row in created['rows']}
assert expected['B06']['status'] == 'CANDIDATE_WITHHELD'
assert all(row['status'] == 'CANDIDATE_READY' for metric, row in expected.items()
           if metric != 'B06')
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext import ordinary_update_cycle as cycle
    from vnext import ordinary_b03_scope_update as b03
    from vnext import c04_update_cycle as c04
    from vnext.canonical import sha256_file, strict_json_file
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_projection import render_ordinary_run
    from vnext.ordinary_processing_source import verify_processing_source
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    verified = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=SOURCE, requirement=requirement)
    assert verified['snapshot_id'] == created['source_snapshot_id']
    rows = []
    for metric in expected:
        root = WORK/'state/southwest_airlines/metrics'/(
            'C04-registration-v3' if metric == 'C04' else metric)
        config = strict_json_file(path=root/'configuration.json')
        state = cycle._state(root, config)
        if metric == 'B06':
            assert state['successful_attempt'] is None
            assert state['latest_attempt'] is not None
            terminal = cycle._terminal(root, state['latest_attempt'])
            assert terminal['status'] == 'CANDIDATE_WITHHELD'
            attempt = cycle._attempt(root, state['latest_attempt'])
            rendered = render_ordinary_run(data_root=attempt/'data',
                run_dir=attempt/'runs/B06', _return_replay_context=True)
            replay = rendered['replay_context']
            result, = [row for row in replay['records']
                if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == 'B06']
            assert result['result_id'] == terminal['metrics']['B06']['result_id']
            assert result['publication'] == 'WITHHELD'
            assert result['value'] is None
            assert result['reason_code'] == 'B06_SOURCE_RELATIONSHIP_UNRESOLVED'
            assert cycle._descriptor({'B06': replay['case']}, config) == terminal['input']
            for name, raw in rendered['files'].items():
                saved = attempt/'rows/B06'/name
                assert saved.read_bytes() == raw
                assert sha256_file(path=saved) == terminal['metrics']['B06']['files'][name]
        else:
            assert state['successful_attempt'] is not None
            terminal = cycle._terminal(root, state['successful_attempt'])
            verifier = (c04._verify_candidate if metric == 'C04' else
                        b03._verify_candidate if metric == 'B03' else
                        cycle._verify_candidate)
            result = verifier(root, terminal, config)[metric]
            assert result['result_id'] == expected[metric]['result_id']
            assert result['publication'] == expected[metric]['publication']
            assert result['reason_code'] == expected[metric]['result_reason']
        if metric == 'C04':
            assert config['route'] == c04.ROUTE
        rows.append({'metric_id': metric, 'result_id': result['result_id'],
            'publication': result['publication'],
            'reason_code': result['reason_code'], 'value': result['value'],
            'unit': result['unit'], 'period_start': result['period_start'],
            'period_end': result['period_end'],
            'quality': result['quality'],
            'applicability': result['applicability']})
        print(metric, result['publication'], result['reason_code'], flush=True)
after = {key: digest(path) for key, path in originals.items()}
assert before == after
assert len(rows) == 36
body = {'record_type': 'ISSUE28_SOUTHWEST_36_NORMAL_CLI_COLD_READ',
    'source_snapshot_id': verified['snapshot_id'],
    'company_id': 'southwest_airlines', 'rows': rows,
    'replayed_metric_count': len(rows),
    'old_semantic_exports_disabled': disabled,
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'formal_adoption': False, 'all390_acceptance': False}
(HERE/'cold.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'replayed': len(rows),
    'reason_counts': {reason: sum(row['reason_code'] == reason for row in rows)
        for reason in sorted({row['reason_code'] for row in rows})},
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
