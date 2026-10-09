"""Unmocked saved-source/native chain using an explicit program-only response."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

from vnext import c02_table_model_processing as m
from vnext.c02_model_processing import build_development_assessment as old_plain_mapper
from vnext.review import _system_approved_claims

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
INPUT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/c02-table-input-reception-20261004')


def blocked(*a, **k):
    raise AssertionError('NETWORK_OR_SUBPROCESS_FORBIDDEN')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main(action, output, candidate=None, unit=None):
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip() if action == 'save' else None
    socket.socket = blocked
    socket.create_connection = blocked
    subprocess.Popen = blocked
    task = (ROOT/'docs/evidence/issue28_continuous/c02-model-input-pilot-20261003/prompt.txt').read_text()
    task = task[task.index('Extract the registrant'):]
    request = (INPUT/'request-body.json').read_bytes()
    # This response is written by the program-test author from prior original
    # reads, never labelled as an independent/model/DeepSeek answer.
    response = m._bytes({'facts': [
        {'kind': 'board_leadership', 'statement': 'James Dimon is JPMorgan Chase Chairman and Chief Executive Officer.',
         'source_blocks': [766, 767], 'stated_time': 'CURRENT_IN_FILING'},
        {'kind': 'committee_structure', 'statement': 'The filing describes the Stock Committee and Executive Committee.',
         'source_blocks': [1244, 1245], 'stated_time': 'CURRENT_IN_FILING'}],
        'unresolved': [{'source_blocks': [1252, 1253, 1276],
                        'reason': 'Membership image marks are not interpreted by the text/header view; empty text is not non-membership.'}]})
    args = dict(data_root=ROOT, company_id='jpmorgan_chase', task_text=task,
        request_body=request, response_body=response, expected_request_sha256=digest(request),
        expected_response_sha256=digest(response), origin='RECORDED_PROGRAM_TEST')
    timings = {}
    if action == 'save':
        before = time.monotonic(); out = m.save_table_development_assessment(directory=output, **args)
        timings['save_seconds'] = round(time.monotonic()-before, 3)
        original = {str(p.relative_to(output)): digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
        before = time.monotonic(); again = m.save_table_development_assessment(directory=output, **args)
        timings['repeat_seconds'] = round(time.monotonic()-before, 3)
        assert out['records'] == again['records']
        assert original == {str(p.relative_to(output)): digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
        before = time.monotonic()
        try:
            old_plain_mapper(data_root=ROOT, company_id='jpmorgan_chase',
                request_body=request, response_body=response,
                source_reference_id=out['processing']['source_reference_id'],
                expected_request_sha256=digest(request), expected_response_sha256=digest(response))
        except ValueError as e:
            assert str(e) == 'C02_MODEL_REQUEST_SOURCE_OR_RESOURCE_CHANGED', e
        else:
            raise AssertionError('TABLE_REQUEST_ACCEPTED_AS_OLD_PLAIN_WIRE')
        timings['old_mapper_refusal_seconds'] = round(time.monotonic()-before, 3)
    else:
        before = time.monotonic()
        out = m.read_table_development_assessment(directory=output, data_root=ROOT,
            company_id='jpmorgan_chase', expected_candidate_hash=candidate, expected_review_unit_hash=unit)
        timings['read_seconds'] = round(time.monotonic()-before, 3)
    assert out['records'][5]['status'] == 'PENDING'
    try:
        _system_approved_claims(review_unit=out['records'][5])
    except ValueError:
        pass
    else:
        raise AssertionError('SYSTEM_APPROVAL_NOT_REFUSED')
    context = json.loads(out['review_context_bytes'])
    assert context['source_linked_review']['entries'][-1]['entry_kind'] == 'UNRESOLVED'
    assert 'SOURCE_IMAGES_NOT_INTERPRETED' in out['processing']['rendering_limitations']
    expected = {k: digest((ROOT/k).read_bytes()) for k in [
        'scripts/vnext/c02_model_processing.py', 'scripts/vnext/c02_model_review_view.py',
        'catalog/r6/C02_model_source_development_v1.md']}
    result = {'action': action, 'base_head': head, 'tested_uncommitted_paths': [
        'scripts/vnext/c02_table_model_processing.py', 'catalog/r6/C02_model_table_development_v1.md'],
        'code_root': str(ROOT), 'source_data_root': str(ROOT), 'processing_root': str(output),
        'origin': 'RECORDED_PROGRAM_TEST', 'request_sha256': digest(request), 'response_sha256': digest(response),
        'candidate_hash': out['records'][2]['candidate_hash'], 'review_unit_hash': out['records'][5]['review_unit_hash'],
        'grid_id': out['records'][0]['derived_asset_id'],
        'facts': 2, 'unresolved': 1, 'record_types': [r['record_type'] for r in out['records']],
        'request_context': out['processing']['request_context'], 'timings': timings,
        'old_plain_mapper_and_spec_hashes': expected,
        'files': {str(p.relative_to(output)): digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()},
        'native_result_created': False, 'model_answer_tested': False, 'system_approval_refused': True,
        'semantic_acceptance': False, 'calls': [0, 0, 0]}
    (HERE/(action+'-result.json')).write_bytes(m._bytes(result))
    print(json.dumps({k: result[k] for k in ['action', 'origin', 'candidate_hash', 'review_unit_hash',
        'facts', 'unresolved', 'timings', 'system_approval_refused', 'calls']}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--action', choices=['save', 'read'], required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--candidate')
    p.add_argument('--unit')
    args = p.parse_args()
    main(args.action, args.output, args.candidate, args.unit)
