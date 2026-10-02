"""Bounded #28 consumer test of fixed #54 code, without new business calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
CODE = BASE / 'provider-code'
RUNTIME = BASE / 'runtime'
ORIGINAL = Path('/Users/lyuhongwang/Developer/SEC_metrics')
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = LEDGER / 'source-inputs'
EVIDENCE = Path(__file__).resolve().parent / 'consumer-v1'
PYTHON = Path('/private/tmp/issue28-tokenizers-venv/bin/python')
EVIDENCE.mkdir(exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected():
    paths = [p for p in LEDGER.iterdir() if p.is_file()]
    paths += [SOURCE / 'evidence/requests_log.csv', ORIGINAL / 'outputs/active_publication.json']
    return {str(p): sha(p) for p in paths if p.is_file()}


def run(name, root, args, *, guarded=False, expected_exit=0):
    started = time.monotonic()
    command = [str(PYTHON), str(BASE / 'guarded-cli.py') if guarded else str(root / 'tools/vnext_company.py'), *args]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    env['COMPANY_TEST_RUNTIME'] = str(root)
    with (EVIDENCE / (name + '.log')).open('w') as output:
        completed = subprocess.run(command, cwd=root, env=env, stdout=output, stderr=subprocess.STDOUT)
    record = {'name': name, 'command': command, 'exit': completed.returncode,
              'seconds': round(time.monotonic() - started, 3), 'guarded': guarded,
              'expected_exit': expected_exit}
    result['steps'].append(record)
    print(json.dumps(record), flush=True)
    assert completed.returncode == expected_exit, name
    return json.loads((EVIDENCE / (name + '.log')).read_text())


result = {'record_type': 'ISSUE28_FIXED_COMPANY_CONSUMER_PROBE',
          'source_pin': json.loads((BASE / 'source-pin.json').read_text()),
          'steps': [], 'new_business_calls': [0, 0, 0], 'whole_business_acceptance': False,
          'openshift_or_dynamic_uid_tested': False}
before = protected()
try:
    # The preparation process validates the complete original history. Its
    # owner-journal copy is setup, not the computing trust or a new approval.
    installed = run('runtime-install', CODE, ['install-runtime', '--kind', 'ordinary', '--output-root', str(RUNTIME)])
    assert installed['requirement_id'] == 'issue_54_v1'
    assert not (RUNTIME / '.git/objects/info/alternates').exists()
    assert not (RUNTIME / 'evidence').exists()
    result['runtime'] = installed
    for company, metric in [('enphase_energy', 'D04'), ('marriott_international', 'C04')]:
        package = BASE / ('package-' + company)
        state = BASE / ('state-' + company)
        trust = BASE / 'source-trust'
        exported = run('export-' + company, CODE, ['export', '--source-root', str(SOURCE),
            '--output-root', str(package), '--trust-root', str(trust), '--company', company, '--metric', metric])
        assert exported['ai_processing_state'] == 'NOT_INCLUDED'
        assert not list(package.rglob('ordinary_going_concern_assessment.json'))
        assert not list(package.rglob('ordinary_capacity_assessment.json'))
        admission = json.loads((package / 'config/ordinary_source_checkpoint.json').read_text())
        assert (package / 'evidence/requests_log.csv').read_bytes() == (SOURCE / 'evidence/requests_log.csv').read_bytes()
        assert admission['original_checkpoint']['captures'] == json.loads(
            Path(result['source_pin']['preparation_journal_setup']['original_path']).read_text())['captures']
        imported = run('install-' + company, RUNTIME, ['install', '--package-root', str(package),
            '--state-root', str(state), '--trust-root', str(trust), '--company', company], guarded=True)
        computed = run('compute-' + company, RUNTIME, ['compute', '--state-root', str(state),
            '--trust-root', str(trust), '--company', company, '--metric', metric],
            guarded=True, expected_exit=2 if metric == 'D04' else 0)
        result[company] = {'package': exported, 'admission_id': admission['checkpoint_id'],
                           'source_credit': admission['source_credit'], 'import': imported, 'compute': computed}
        row = computed['metrics'][0]
        if metric == 'D04':
            assert row['status'] == 'AI_PROCESSING_INPUT_REQUIRED'
            assert row['business_metric_completed'] is False
            assert not (state / 'updates').exists()
        else:
            assert row['status'] == 'CANDIDATE_READY'
            repeated = run('repeat-' + company, RUNTIME, ['compute', '--state-root', str(state),
                '--trust-root', str(trust), '--company', company, '--metric', metric], guarded=True)
            assert repeated['metrics'][0]['status'] == 'NO_SOURCE_CONTENT_CHANGE'
            assert repeated['metrics'][0]['successful_attempt'] == row['successful_attempt']
            result[company]['repeat'] = repeated
    result['status'] = 'PASS_BOUNDED_CONSUMER_INTERFACE'
except Exception as error:
    result.update(status='FAILED_BOUNDED_CONSUMER_INTERFACE', error_type=type(error).__name__, error=str(error))
    raise
finally:
    result['original_protected_hashes_before'] = before
    result['original_protected_hashes_after'] = protected()
    result['original_protected_bytes_unchanged'] = result['original_protected_hashes_after'] == before
    (EVIDENCE / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (EVIDENCE / 'done.json').write_text(json.dumps({'status': result['status'], 'protected_unchanged': result['original_protected_bytes_unchanged']}) + '\n')
