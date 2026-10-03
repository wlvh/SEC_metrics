"""Cold-read the 36 private Runs while old semantic producers are blocked."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-marriott-current-36-20260929')
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
OLD_PROBE = ROOT/'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py'
spec = importlib.util.spec_from_file_location('issue28_legacy_exit_probe', OLD_PROBE)
old_probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old_probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


prior = json.loads((HERE/'result.json').read_text())
assert prior['status'] == 'UPDATES_READY' and len(prior['metric_rows']) == 36
originals = {'claims': LEDGER/'claims.jsonl',
    'source_log': LEDGER/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
rows = []
with old_probe.legacy_disabled() as disabled:
    from vnext import ordinary_update_cycle as ordinary
    from vnext import ordinary_b03_scope_update as guarded
    for entry in prior['metric_rows']:
        metric = entry['metric_id']
        path = WORK/'state/metrics'/metric
        try:
            config = ordinary._config(path, LEDGER/'source-inputs',
                'marriott_international', [metric], 'LIVE')
            state = ordinary._state(path, config)
            assert state['successful_attempt'] is not None
            terminal = ordinary._terminal(path, state['successful_attempt'])
            verify = guarded._verify_candidate if metric == 'B03' else \
                ordinary._verify_candidate
            result = verify(path, terminal, config)[metric]
            assert result['result_id'] == entry['result_id']
            rows.append({'metric_id': metric, 'status': 'PASS',
                'result_id': result['result_id'],
                'publication': result['publication'],
                'reason_code': result['reason_code']})
        except Exception as error:
            rows.append({'metric_id': metric, 'status': 'FAIL',
                'error_type': type(error).__name__, 'reason': str(error),
                'traceback_tail': traceback.format_exc()[-2000:]})
        print(metric, rows[-1]['status'], flush=True)
after = {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_MARRIOTT_36_LEGACY_DISABLED_COLD_READ',
    'company_id': 'marriott_international',
    'source_snapshot_id': prior['source_snapshot_id'],
    'old_semantic_producers_disabled': disabled,
    'rows': rows, 'pass_count': sum(row['status'] == 'PASS' for row in rows),
    'fail_count': sum(row['status'] == 'FAIL' for row in rows),
    'original_claims_source_and_active_unchanged': before == after,
    'calls': [0, 0, 0], 'formal_old_entrypoints_retired': False,
    'all390_acceptance': False}
(HERE/'legacy-cold.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'pass_count': body['pass_count'],
    'fail_count': body['fail_count'],
    'original_files_unchanged': before == after,
    'disabled_old_exports': disabled}, sort_keys=True), flush=True)
assert before == after and body['pass_count'] == 36
