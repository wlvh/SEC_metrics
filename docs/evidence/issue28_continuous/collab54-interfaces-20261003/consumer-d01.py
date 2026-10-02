"""One actual company D01 route, from saved mixed captures, plus cold repeat."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
CODE = BASE / 'provider-code'
RUNTIME = BASE / 'runtime-8a-d01'
PACKAGE = BASE / 'package-marriott-d01'
STATE = BASE / 'state-marriott-d01'
TRUST = BASE / 'source-trust-d01'
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = LEDGER / 'source-inputs'
ORIGINAL = Path('/Users/lyuhongwang/Developer/SEC_metrics')
EVIDENCE = Path(__file__).resolve().parent / 'consumer-d01-v1'
EVIDENCE.mkdir(exist_ok=True)


def protected():
    paths = [p for p in LEDGER.iterdir() if p.is_file()]
    paths += [SOURCE / 'evidence/requests_log.csv', ORIGINAL / 'outputs/active_publication.json']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


summary = {'provider_code_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CODE, text=True).strip(),
           'consumer_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ORIGINAL, text=True).strip(),
           'steps': [], 'new_calls': [0, 0, 0], 'openshift_tested': False,
           'source_kind': 'ORIGINAL_52_CAPTURE_MIXED_SAVED_HISTORY_COMPANY_SCOPE_D01'}
before = protected()


def run(name, root, args, guarded=False):
    command = [sys.executable, '-B', str(BASE / 'guarded-cli.py') if guarded else str(root / 'tools/vnext_company.py'), *args]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'COMPANY_TEST_RUNTIME': str(root)}
    start = time.monotonic()
    with (EVIDENCE / (name + '.log')).open('w') as log:
        done = subprocess.run(command, cwd=BASE, env=env, stdout=log, stderr=subprocess.STDOUT)
    summary['steps'].append({'name': name, 'exit': done.returncode, 'seconds': round(time.monotonic() - start, 3),
                             'root': str(root), 'guarded': guarded})
    print(json.dumps(summary['steps'][-1]), flush=True)
    assert done.returncode == 0, 'READ_STAGE_LOG:' + name
    return json.loads((EVIDENCE / (name + '.log')).read_text())


try:
    assert summary['provider_code_sha'] == '8a521e32204866021955f8330080a024db5f1b3c'
    summary['runtime'] = run('runtime-install', CODE, ['install-runtime', '--kind', 'ordinary', '--output-root', str(RUNTIME)])
    assert not (RUNTIME / '.git/objects/info/alternates').exists() and not (RUNTIME / 'evidence').exists()
    summary['package'] = run('source-export', CODE, ['export', '--source-root', str(SOURCE),
        '--output-root', str(PACKAGE), '--trust-root', str(TRUST), '--company', 'marriott_international', '--metric', 'D01'])
    assert not list(PACKAGE.rglob('ordinary_going_concern_assessment.json'))
    assert not list(PACKAGE.rglob('ordinary_capacity_assessment.json'))
    assert (PACKAGE / 'evidence/requests_log.csv').read_bytes() == (SOURCE / 'evidence/requests_log.csv').read_bytes()
    summary['installed'] = run('source-install', RUNTIME, ['install', '--package-root', str(PACKAGE),
        '--state-root', str(STATE), '--trust-root', str(TRUST), '--company', 'marriott_international'], guarded=True)
    args = ['compute', '--state-root', str(STATE), '--trust-root', str(TRUST), '--company', 'marriott_international', '--metric', 'D01']
    summary['computed'] = run('compute', RUNTIME, args, guarded=True)
    row = summary['computed']['metrics'][0]
    assert row['status'] == 'CANDIDATE_READY'
    attempt = STATE / 'updates/metrics/D01/attempts' / row['successful_attempt']
    if not attempt.exists():
        attempts = list((STATE / 'updates').glob('**/attempts/' + row['successful_attempt']))
        assert len(attempts) == 1
        attempt = attempts[0]
    records = [json.loads(line) for line in (attempt / 'runs/D01/records.jsonl').read_text().splitlines()]
    result = next(r for r in records if r.get('record_type') == 'METRIC_RESULT' and r['metric_id'] == 'D01')
    binding = json.loads(next((attempt / 'data/config/ordinary_run_inputs').glob('*.json')).read_text()) if (attempt / 'data/config/ordinary_run_inputs').exists() else None
    summary['native_result'] = result
    expected_delta = json.loads((ORIGINAL / 'docs/evidence/issue28_continuous/current-390-d01-integration-20261003/delta.json').read_text())
    expected = next(x for x in expected_delta['changed_coordinates'] if x['company_id'] == 'marriott_international')['native_result']
    assert result['value'] == expected['value'] and result['text_payload']['items'] == expected['text_payload']['items']
    assert len(result['text_payload']['items']) == 38
    summary['input_binding'] = binding
    summary['same_reviewed_38_titles'] = True
    summary['repeat'] = run('repeat', RUNTIME, args, guarded=True)
    repeated = summary['repeat']['metrics'][0]
    assert repeated['status'] == 'NO_SOURCE_CONTENT_CHANGE' and repeated['successful_attempt'] == row['successful_attempt']
    summary['status'] = 'PASS_COMPANY_D01_SUCCESSOR_NATIVE_AND_INDEPENDENT_PROCESS_REPEAT'
except Exception as error:
    summary.update(status='FAILED_COMPANY_D01_CONSUMER', error_type=type(error).__name__, error=str(error))
    raise
finally:
    summary['protected_before'] = before
    summary['protected_after'] = protected()
    summary['protected_unchanged'] = before == summary['protected_after']
    (EVIDENCE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (EVIDENCE / 'done.json').write_text(json.dumps({'status': summary['status'], 'protected_unchanged': summary['protected_unchanged']}) + '\n')
