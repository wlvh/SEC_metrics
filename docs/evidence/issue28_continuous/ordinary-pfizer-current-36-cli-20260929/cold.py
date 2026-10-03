"""Independently reopen Pfizer's existing private normal-CLI outcomes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-pfizer-current-36-cli-20260929')
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
expected = {row['metric_id']: row for row in created['rows']}
assert created['metric_count'] == len(expected) == 36
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
    for metric, expected_row in expected.items():
        root = WORK/'state/pfizer/metrics'/(
            'C04-registration-v3' if metric == 'C04' else metric)
        config = strict_json_file(path=root/'configuration.json')
        state = cycle._state(root, config)
        if expected_row['status'] == 'CANDIDATE_READY':
            assert state['successful_attempt'] is not None
            terminal = cycle._terminal(root, state['successful_attempt'])
            verifier = (c04._verify_candidate if metric == 'C04' and
                        config.get('route') == c04.ROUTE else
                        b03._verify_candidate if metric == 'B03' else
                        cycle._verify_candidate)
            result = verifier(root, terminal, config)[metric]
            assert result['result_id'] == expected_row['result_id']
            assert result['publication'] == expected_row['publication']
            assert result['reason_code'] == expected_row['result_reason']
            rows.append({'metric_id': metric, 'status': expected_row['status'],
                'result_id': result['result_id'], 'publication': result['publication'],
                'reason_code': result['reason_code'], 'value': result['value'],
                'unit': result['unit'], 'period_start': result['period_start'],
                'period_end': result['period_end'], 'quality': result['quality'],
                'applicability': result['applicability']})
        elif expected_row['status'] == 'CANDIDATE_WITHHELD':
            assert state['successful_attempt'] is None
            assert state['latest_attempt'] is not None
            terminal = cycle._terminal(root, state['latest_attempt'])
            assert terminal['status'] == 'CANDIDATE_WITHHELD'
            attempt = cycle._attempt(root, state['latest_attempt'])
            rendered = render_ordinary_run(data_root=attempt/'data',
                run_dir=attempt/'runs'/metric, _return_replay_context=True)
            replay = rendered['replay_context']
            result, = [row for row in replay['records']
                if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == metric]
            assert result['result_id'] == terminal['metrics'][metric]['result_id']
            assert result['publication'] == 'WITHHELD' and result['value'] is None
            prior_rows = json.loads((ROOT/'docs/evidence/issue28_continuous/'
                'd04-remaining-20260922/current-390.json').read_text())['rows']
            prior_reason, = [row['reason_code'] for row in prior_rows
                if row['company_id'] == 'pfizer' and row['metric_id'] == metric]
            assert result['reason_code'] == prior_reason == 'B06_SOURCE_RELATIONSHIP_UNRESOLVED'
            assert cycle._descriptor({metric: replay['case']}, config) == terminal['input']
            for name, raw in rendered['files'].items():
                saved = attempt/'rows'/metric/name
                assert saved.read_bytes() == raw
                assert sha256_file(path=saved) == terminal['metrics'][metric]['files'][name]
            rows.append({'metric_id': metric, 'status': expected_row['status'],
                'result_id': result['result_id'], 'publication': result['publication'],
                'reason_code': result['reason_code'], 'value': result['value'],
                'unit': result['unit'], 'period_start': result['period_start'],
                'period_end': result['period_end'], 'quality': result['quality'],
                'applicability': result['applicability']})
        else:
            assert state['latest_attempt'] is not None
            terminal = cycle._terminal(root, state['latest_attempt'])
            assert terminal['status'] == expected_row['status']
            rows.append({'metric_id': metric, 'status': terminal['status'],
                'result_id': None, 'terminal_id': terminal['record_id'],
                'reason_code': expected_row['reason']})
        print(metric, rows[-1]['status'], flush=True)
after = {key: digest(path) for key, path in originals.items()}
assert before == after and len(rows) == 36
body = {'record_type': 'ISSUE28_PFIZER_36_NORMAL_CLI_COLD_READ',
    'source_snapshot_id': verified['snapshot_id'],
    'company_id': 'pfizer', 'rows': rows,
    'replayed_metric_count': len(rows),
    'old_semantic_exports_disabled': disabled,
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'formal_adoption': False, 'all390_acceptance': False}
(HERE/'cold.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'replayed': len(rows),
    'status_counts': {status: sum(row['status'] == status for row in rows)
        for status in sorted({row['status'] for row in rows})},
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
