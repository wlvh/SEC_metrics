"""Fixed #54 acquired-source adapter consumes prior LIVE input, zero new calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
CODE = BASE / 'provider-code'
RUNTIME = BASE / 'runtime-303-live-d04'
STATE = BASE / 'state-enphase-live-d04'
TRUST = BASE / 'source-trust-live-d04'
OLD_SOURCE = BASE / 'source-version-enphase-original-live'
CURRENT = BASE / 'source-package-enphase-current-live'
PROCESSING = BASE / 'live-processing-packet'
OLD_PROGRAM = BASE / 'live-processing-program'
PROCESSING_TRUST = BASE / 'live-processing-trust'
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
ORIGINAL = Path('/Users/lyuhongwang/Developer/SEC_metrics')
OLD_INSTALLED = LEDGER / 'native-candidate-results-20260924/enphase_energy/data'
SOURCE = LEDGER / 'source-inputs'
HERE = Path(__file__).resolve().parent / 'consumer-live-d04-v1'
HERE.mkdir(exist_ok=True)


def protected():
    files = [p for p in LEDGER.iterdir() if p.is_file()] + [
        SOURCE / 'evidence/requests_log.csv', ORIGINAL / 'outputs/active_publication.json',
        OLD_INSTALLED / 'config/ordinary_going_concern_assessment.json']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


summary = {'provider_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CODE, text=True).strip(),
           'consumer_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ORIGINAL, text=True).strip(),
           'steps': [], 'new_calls': [0, 0, 0], 'openshift_tested': False,
           'source_versions_not_spliced': True}
before = protected()


def run(name, program, args, guarded=False):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'COMPANY_TEST_RUNTIME': str(program)}
    env['COMPANY_DENY_READ_ROOTS'] = os.pathsep.join((str(ORIGINAL), str(LEDGER), str(CODE))) if guarded else ''
    command = [sys.executable, '-B', str(BASE / 'guarded-cli.py') if guarded else str(program / 'tools/vnext_company.py'), *args]
    start = time.monotonic()
    with (HERE / (name + '.log')).open('w') as log:
        result = subprocess.run(command, env=env, cwd=BASE, stdout=log, stderr=subprocess.STDOUT)
    summary['steps'].append({'name': name, 'exit': result.returncode,
                             'seconds': round(time.monotonic() - start, 3), 'root': str(program), 'guarded': guarded})
    print(json.dumps(summary['steps'][-1]), flush=True)
    assert result.returncode == 0, 'READ_STAGE_LOG:' + name
    return json.loads((HERE / (name + '.log')).read_text())


try:
    assert summary['provider_sha'] == '303d751f29e57dc68ab7848b6b184dc4ab8c4b83'
    summary['runtime'] = run('runtime-install', CODE, ['install-runtime', '--kind', 'ordinary', '--output-root', str(RUNTIME)])
    summary['original_baseline'] = run('original-source-export', CODE, ['export', '--source-root', str(OLD_INSTALLED),
        '--output-root', str(OLD_SOURCE), '--trust-root', str(TRUST), '--company', 'enphase_energy', '--metric', 'D04'])
    summary['current_source'] = run('current-source-export', CODE, ['export', '--source-root', str(SOURCE),
        '--output-root', str(CURRENT), '--trust-root', str(TRUST), '--company', 'enphase_energy', '--metric', 'D04'])
    for packet in (OLD_SOURCE, CURRENT):
        assert not list(packet.rglob('ordinary_going_concern_assessment.json'))
        assert not list(packet.rglob('ordinary_capacity_assessment.json'))
    assert json.loads((OLD_SOURCE / 'config/ordinary_source_checkpoint.json').read_text())['original_checkpoint'] is None
    assert json.loads((CURRENT / 'config/ordinary_source_checkpoint.json').read_text())['original_checkpoint'] is not None
    assert (CURRENT / 'evidence/requests_log.csv').read_bytes() == (SOURCE / 'evidence/requests_log.csv').read_bytes()
    summary['installed'] = run('source-install', RUNTIME, ['install', '--package-root', str(CURRENT), '--state-root', str(STATE),
        '--trust-root', str(TRUST), '--company', 'enphase_energy'], guarded=True)
    arguments = ['compute', '--state-root', str(STATE), '--trust-root', str(TRUST), '--company', 'enphase_energy', '--metric', 'D04',
        '--processing-package', str(PROCESSING), '--processing-runtime', str(OLD_PROGRAM),
        '--processing-trust-root', str(PROCESSING_TRUST), '--processing-source-version', str(OLD_SOURCE)]
    summary['compute'] = run('compute', RUNTIME, arguments, guarded=True)
    row = summary['compute']['metrics'][0]
    assert row['status'] == 'CANDIDATE_READY' and row['saved_processing_mode'] == 'LIVE'
    work = Path(row['last_verified_candidate']['rows_root']).parent
    receipt = json.loads((work / 'processing-receipt.json').read_text())
    assert receipt['mode'] == 'LIVE' and receipt['result_id'] == 'sha256:7bf9ea839cb7ef2c636ebf524fb4305056a048447880bd37e2df81664483f99b'
    assert receipt['run_id'] == 'run:ordinary-integrated:128f6ccad812a47063e47640c3c997ff50d812bb8763135ac822a292b7e9743c'
    summary['processing_receipt'] = receipt
    summary['repeat'] = run('repeat', RUNTIME, arguments, guarded=True)
    repeated = summary['repeat']['metrics'][0]
    assert repeated['status'] == 'NO_SOURCE_CONTENT_CHANGE'
    assert repeated['last_verified_candidate']['attempt_id'] == row['last_verified_candidate']['attempt_id']
    assert len(list(work.parent.glob('*/runs/D04/manifest.json'))) == 1
    summary['one_native_run'] = True
    summary['status'] = 'PASS_COMPANY_ACQUIRED_SOURCE_WITH_SAVED_LIVE_D04_AND_REPEAT'
except Exception as error:
    summary.update(status='FAILED_ACQUIRED_LIVE_D04_CONSUMER', error_type=type(error).__name__, error=str(error))
    raise
finally:
    summary['protected_before'] = before
    summary['protected_after'] = protected()
    summary['protected_unchanged'] = before == summary['protected_after']
    (HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'done.json').write_text(json.dumps({'status': summary['status'], 'protected_unchanged': summary['protected_unchanged']}) + '\n')
