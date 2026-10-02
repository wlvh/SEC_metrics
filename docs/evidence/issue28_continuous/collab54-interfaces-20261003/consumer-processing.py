"""Consume #54's fixed processing adapter with original LIVE 173--178 inputs.

Only export/authentication and the explicit acquired-source refusal are tested.
No provider, SEC, registration, old Run replay or new Result is requested.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
CODE = BASE / 'provider-code'
ORIGINAL = Path('/Users/lyuhongwang/Developer/SEC_metrics')
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
INSTALLED = LEDGER / 'native-candidate-results-20260924/enphase_energy/data'
PACKET = BASE / 'live-processing-packet'
PROGRAM = BASE / 'live-processing-program'
TRUST = BASE / 'live-processing-trust'
STATE = BASE / 'state-enphase_energy'
ORIGINAL_EXPORT_LOG = Path(__file__).resolve().parent / 'processing-live-v1/export.log'
HERE = BASE / 'processing-live-v1-report'
HERE.mkdir(exist_ok=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*') if p.is_file()}


protected = [p for p in LEDGER.iterdir() if p.is_file()] + [
    LEDGER / 'source-inputs/evidence/requests_log.csv', ORIGINAL / 'outputs/active_publication.json',
    INSTALLED / 'config/ordinary_going_concern_assessment.json']
before = {str(p): digest(p) for p in protected}
state_before = inventory(STATE)
start = time.monotonic()
summary = {'consumer_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ORIGINAL, text=True).strip(),
           'provider_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CODE, text=True).strip(),
           'original_installed_root': str(INSTALLED), 'new_business_calls': [0, 0, 0],
           'whole_company_or_content_credit': False}
try:
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    # Controlled preparation may read the authenticated old installation.
    # Reuse the already successful export after the evidence-output guard error.
    # This is a report-path recovery, not another export/native computation.
    assert PACKET.exists() and PROGRAM.exists() and ORIGINAL_EXPORT_LOG.is_file()
    exported = json.loads(ORIGINAL_EXPORT_LOG.read_text())
    assert exported['status'] == 'SAVED_PROCESSING_EXPORTED'
    summary['export_return_code'] = 0
    summary['export_reused_after_evidence_path_failure'] = True
    summary['export'] = exported
    metadata = json.loads((PACKET / 'processing.json').read_text())
    record = json.loads((PACKET / 'config/ordinary_going_concern_assessment.json').read_text())
    assert record['mode'] == 'LIVE' and [r['ordinal'] for r in record['native_requests']] == list(range(173, 179))
    assert record['input_record_id'] == 'sha256:44801106654d1a1fa57ed9120f8238e832c7cfe8ce5072976ff628cb6871f314'
    assert record['new_call_authority'] is False and record['production_authorized'] is False
    assert (PACKET / 'config/ordinary_going_concern_assessment.json').read_bytes() == protected[-1].read_bytes()
    assert not (PROGRAM / 'config/ordinary_going_concern_assessment.json').exists()
    assert not (PROGRAM / 'evidence').exists()
    assert not (PROGRAM / '.git/objects/info/alternates').exists()
    os.environ['SEC_METRICS_PROCESSING_TRUST_ROOT'] = str(TRUST)
    sys.path[:0] = [str(CODE), str(CODE / 'scripts')]
    from vnext.company_worker_guard import install_worker_guards
    from vnext.company_processing import authenticate_processing, compute_saved_processing
    # From here authentication is a consumer read, with original roots denied.
    os.environ['COMPANY_DENY_READ_ROOTS'] = os.pathsep.join((str(ORIGINAL), str(LEDGER)))
    install_worker_guards(PROGRAM)
    assert authenticate_processing(packet_root=PACKET, program_root=PROGRAM,
                                   company_id='enphase_energy') == metadata
    try:
        authenticate_processing(packet_root=PACKET, program_root=PROGRAM, company_id='marriott_international')
    except ValueError as error:
        assert str(error) == 'COMPANY_PROCESSING_WRONG_COMPANY_OR_AUTHORITY'
        summary['wrong_company_refusal'] = str(error)
    else:
        raise AssertionError('WRONG_COMPANY_NOT_REFUSED')
    admission = json.loads((STATE / 'source/config/ordinary_source_checkpoint.json').read_text())
    assert admission['original_checkpoint'] is not None
    try:
        compute_saved_processing(root=STATE, source=STATE / 'source', admission=admission,
            company_id='enphase_energy', packet_root=PACKET, program_root=PROGRAM)
    except ValueError as error:
        assert str(error) == 'COMPANY_PROCESSING_ACQUIRED_SOURCE_ADAPTER_REQUIRED'
        summary['acquired_source_refusal'] = str(error)
    else:
        raise AssertionError('ACQUIRED_SOURCE_NOT_REFUSED')
    summary['processing_id'] = metadata['processing_id']
    summary['program_files'] = len(metadata['runtime_files'])
    summary['packet_members'] = list(metadata['files'])
    summary['input_id'] = record['input_record_id']
    summary['source_id'] = record['source_id']
    summary['mode'] = record['mode']
    summary['state_unchanged'] = inventory(STATE) == state_before
    assert summary['state_unchanged']
    summary['status'] = 'PASS_LIVE_EXPORT_AUTHENTICATION_AND_EXPLICIT_ACQUIRED_SOURCE_BOUNDARY'
except Exception as error:
    summary.update(status='FAILED_CONSUMER_CHECK', error_type=type(error).__name__, error=str(error))
    raise
finally:
    summary['seconds'] = round(time.monotonic() - start, 3)
    # An audit hook intentionally disallows the original roots after preparation.
    # The independent parent verifies the before hash receipt after this exits.
    summary['protected_before'] = before
    (HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'done.json').write_text(json.dumps({'status': summary['status']}) + '\n')
    print(json.dumps({k: summary[k] for k in ('status', 'seconds', 'new_business_calls')}), flush=True)
