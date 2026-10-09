"""Two real saved source versions, one stable C04 journal, no new captures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
RUNTIME = BASE / 'runtime'  # Already installed fixed 2a642e56; unchanged C04.
OLD_PACKAGE = BASE / 'package-marriott-c04-original-baseline'
NEW_PACKAGE = BASE / 'package-marriott_international'
STATE = BASE / 'state-marriott-c04-source-switch'
TRUST = BASE / 'source-trust'
ORIGINAL = Path('/Users/lyuhongwang/Developer/SEC_metrics')
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
HERE = Path(__file__).resolve().parent / 'consumer-c04-source-switch-v1'
HERE.mkdir(exist_ok=True)


def protected():
    paths = [p for p in LEDGER.iterdir() if p.is_file()]
    paths += [LEDGER / 'source-inputs/evidence/requests_log.csv',
              ORIGINAL / 'outputs/active_publication.json']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


summary = {'provider_consumed_sha': '2a642e56a8e2f88c884c92cd350cf742f5dd8cfa',
           'provider_latest_read_sha': '303d751f29e57dc68ab7848b6b184dc4ab8c4b83',
           'consumer_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ORIGINAL, text=True).strip(),
           'steps': [], 'new_calls': [0, 0, 0], 'openshift_tested': False,
           'source_versions_spliced': False, 'new_financial_year': False}
before = protected()


def run(name, args, *, guarded=True):
    command = [sys.executable, '-B', str(BASE / 'guarded-cli.py') if guarded
               else str(RUNTIME / 'tools/vnext_company.py'), *args]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'COMPANY_TEST_RUNTIME': str(RUNTIME)}
    start = time.monotonic()
    with (HERE / (name + '.log')).open('w') as log:
        done = subprocess.run(command, cwd=BASE, env=env, stdout=log, stderr=subprocess.STDOUT)
    summary['steps'].append({'name': name, 'exit': done.returncode,
        'seconds': round(time.monotonic() - start, 3), 'guarded': guarded})
    print(json.dumps(summary['steps'][-1]), flush=True)
    assert done.returncode == 0, 'READ_STAGE_LOG:' + name
    return json.loads((HERE / (name + '.log')).read_text())


def installed(name, package):
    return run(name, ['install', '--package-root', str(package), '--state-root', str(STATE),
                     '--trust-root', str(TRUST), '--company', 'marriott_international'])


def compute(name):
    return run(name, ['compute', '--state-root', str(STATE), '--trust-root', str(TRUST),
                     '--company', 'marriott_international', '--metric', 'C04'])


def attempt(row):
    hits = list(STATE.glob('updates/**/attempts/' + row['successful_attempt']))
    assert len(hits) == 1
    return hits[0]


def file_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


try:
    pin = json.loads((BASE / 'source-pin.json').read_text())
    assert pin['provider_sha'] == summary['provider_consumed_sha']
    assert not (RUNTIME / '.git/objects/info/alternates').exists()
    summary['baseline_package'] = run('baseline-export', ['export', '--source-root', str(ORIGINAL),
        '--output-root', str(OLD_PACKAGE), '--trust-root', str(TRUST),
        '--company', 'marriott_international', '--metric', 'C04'], guarded=False)
    summary['baseline_log_sha256'] = hashlib.sha256((OLD_PACKAGE / 'evidence/requests_log.csv').read_bytes()).hexdigest()
    summary['current_log_sha256'] = hashlib.sha256((NEW_PACKAGE / 'evidence/requests_log.csv').read_bytes()).hexdigest()
    assert (NEW_PACKAGE / 'evidence/requests_log.csv').read_bytes() == (LEDGER / 'source-inputs/evidence/requests_log.csv').read_bytes()
    assert summary['baseline_log_sha256'] != summary['current_log_sha256']
    for package in (OLD_PACKAGE, NEW_PACKAGE):
        assert not list(package.rglob('ordinary_capacity_assessment.json'))
        assert not list(package.rglob('ordinary_going_concern_assessment.json'))
        assert not list(package.rglob('records.jsonl'))
    summary['baseline_install'] = installed('baseline-install', OLD_PACKAGE)
    summary['baseline_compute'] = compute('baseline-compute')
    first = summary['baseline_compute']['metrics'][0]
    assert first['status'] == 'CANDIDATE_READY'
    first_attempt = attempt(first)
    old_files = file_hashes(first_attempt)
    summary['current_install'] = installed('current-install', NEW_PACKAGE)
    summary['current_compute'] = compute('current-compute')
    current = summary['current_compute']['metrics'][0]
    assert current['status'] == 'CANDIDATE_READY'
    assert first['successful_attempt'] != current['successful_attempt']
    assert file_hashes(first_attempt) == old_files
    summary['repeat'] = compute('current-repeat')
    repeated = summary['repeat']['metrics'][0]
    assert repeated['status'] == 'NO_SOURCE_CONTENT_CHANGE'
    assert repeated['successful_attempt'] == current['successful_attempt']
    summary['baseline_attempt'] = str(first_attempt)
    summary['current_attempt'] = str(attempt(current))
    summary['stable_source_root'] = str(STATE / 'source')
    summary['old_attempt_hashes'] = old_files
    summary['old_attempt_bytes_unchanged'] = True
    summary['two_native_runs'] = len(list(STATE.glob('updates/**/runs/C04/manifest.json'))) == 2
    assert summary['two_native_runs']
    summary['status'] = 'PASS_C04_STABLE_SOURCE_ROOT_TWO_REAL_SAVED_VERSIONS'
except Exception as error:
    summary.update(status='FAILED_C04_SOURCE_VERSION_SWITCH', error_type=type(error).__name__, error=str(error))
    raise
finally:
    summary['protected_before'] = before
    summary['protected_after'] = protected()
    summary['protected_unchanged'] = before == summary['protected_after']
    (HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'done.json').write_text(json.dumps({'status': summary['status'],
        'protected_unchanged': summary['protected_unchanged']}) + '\n')
