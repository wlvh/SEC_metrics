"""Actual blind development answer, unchanged, through reviewed table mapper."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

from vnext.c02_table_model_processing import (
    save_table_development_assessment, read_table_development_assessment)
from vnext.continuous_request_context import _load_tokenizer
from vnext.review import _system_approved_claims

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
INPUT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/c02-table-input-reception-20261004')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blocked(*a, **k):
    raise AssertionError('NETWORK_OR_SUBPROCESS_FORBIDDEN')


def run(action, output, candidate=None, unit=None):
    socket.socket = blocked
    socket.create_connection = blocked
    subprocess.Popen = blocked
    wire = (INPUT/'request-body.json').read_bytes()
    response = (HERE/'independent-input/response.log').read_bytes()
    task = (ROOT/'docs/evidence/issue28_continuous/c02-model-input-pilot-20261003/prompt.txt').read_text()
    task = task[task.index('Extract the registrant'):]
    start = time.monotonic()
    if action == 'save':
        out = save_table_development_assessment(directory=output, data_root=ROOT,
            company_id='jpmorgan_chase', task_text=task, request_body=wire,
            response_body=response, expected_request_sha256=sha(wire),
            expected_response_sha256=sha(response), origin='DEVELOPMENT_MODEL')
    else:
        out = read_table_development_assessment(directory=output, data_root=ROOT,
            company_id='jpmorgan_chase', expected_candidate_hash=candidate,
            expected_review_unit_hash=unit)
    elapsed = round(time.monotonic()-start, 3)
    tokenizer, _ = _load_tokenizer()
    tokens = len(tokenizer.encode(response.decode('utf-8'), add_special_tokens=False).ids)
    assert tokens <= 4096
    assert out['response_body'] == response and out['request_body'] == wire
    assert out['processing']['origin'] == 'DEVELOPMENT_MODEL'
    assert out['records'][5]['status'] == 'PENDING'
    try:
        _system_approved_claims(review_unit=out['records'][5])
    except ValueError:
        pass
    else:
        raise AssertionError('SYSTEM_APPROVAL_ALLOWED')
    result = {'action': action, 'seconds': elapsed, 'code_root': str(ROOT),
        'source_data_root': str(ROOT), 'processing_root': str(output),
        'mapper_sha256': out['processing']['mapper_sha256'],
        'request_sha256': sha(wire), 'response_sha256': sha(response),
        'response_reference_tokens': tokens,
        'facts': len(out['processing']['model_facts_and_unresolved']['facts']),
        'unresolved': len(out['processing']['model_facts_and_unresolved']['unresolved']),
        'candidate_hash': out['records'][2]['candidate_hash'],
        'review_unit_hash': out['records'][5]['review_unit_hash'],
        'native_status': out['records'][5]['status'], 'system_approval_refused': True,
        'file_sha256': {str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()},
        'reference_sha256_unchanged': sha((HERE/'reference-before-blind.json').read_bytes()),
        'deepseek_verified': False, 'complete_company_result': False, 'calls': [0, 0, 0]}
    (HERE/(action+'-native-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['action','seconds','response_reference_tokens','facts',
        'unresolved','candidate_hash','review_unit_hash','native_status','calls']}))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--action', choices=['save','read'], required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--candidate')
    p.add_argument('--unit')
    a=p.parse_args()
    run(a.action,a.output,a.candidate,a.unit)
