"""Full saved-source plan cost and recorded context path; no extraction/model."""
import json
import socket
import subprocess
import time
from pathlib import Path

import task_contract as task
from vnext.canonical import sha256_bytes, sha256_file
from vnext.native_unit_index import evidence_json_bytes

HERE = Path(__file__).parent
BASE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence')
SOURCES = [
    ('marriott', BASE/'d03-complete-six-responses-20261004/source.json',
     '5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b'),
    ('jpm', BASE/'d03-jpm-positive-20261004/source.json',
     '11189144bf0bff60c8995086f9fb2bfa253a38a1206d557a059b9c771f8486a9'),
]


def forbidden(*args, **kwargs):
    raise AssertionError('network or child process forbidden')


def main():
    socket.socket = forbidden; subprocess.Popen = forbidden
    ledger = BASE.parent/'issue28-2026-09-13/claims.jsonl'; ledger_before = sha256_file(path=ledger)
    start = time.monotonic(); summaries = []
    for name, path, digest in SOURCES:
        source_raw = path.read_bytes(); assert sha256_bytes(content=source_raw) == digest
        source = json.loads(source_raw)
        began = time.monotonic(); plan = task.scan_plan(source, digest)
        rows = [{'owners': t['payload']['responsibility_unit_ids'], 'request_sha256': t['request_sha256'],
                 'input_tokens': t['measure']['input_tokens'], 'context_tokens': t['measure']['context_tokens'],
                 'request_bytes': t['measure']['request_bytes'], 'fits': t['measure']['fits']} for t in plan['tasks']]
        summary = {'company': name, 'source_path': str(path), 'source_sha256': digest,
            'source_unit_count': len(source['units']), 'complete_ownership_once': True,
            'all_original_owner_and_identity_payloads_roundtrip': True,
            'first_scan_count': plan['first_scan_count'], 'followup_count_ceiling': plan['followup_count_ceiling'],
            'design_total_ceiling': plan['total_request_ceiling'],
            'input_token_sum_first_scan': sum(r['input_tokens'] for r in rows),
            'maximum_context_tokens': max(r['context_tokens'] for r in rows),
            'all_first_scan_fit': all(r['fits'] for r in rows), 'rows': rows,
            'seconds': format(time.monotonic()-began, '.3f'),
            'completion_guaranteed': False, 'actual_model_output4096_verified': False,
            'context_sufficiency_verified': False, 'live_authorized': False,
            'runtime_opportunity_guard_connected': False}
        summaries.append(summary)
        print(json.dumps({k:v for k,v in summary.items() if k!='rows'}), flush=True)
        if name == 'marriott':
            owner = 'sha256:3345ce064f9231ae17b6b0133c01f16d4bc21ed1866bd7c9e1bf22fa7760d5b9'
            t = next(t for t in plan['tasks'] if owner in t['payload']['responsibility_unit_ids'])
            response = {'reviewed_unit_ids': t['payload']['responsibility_unit_ids'],
                'findings': [{'kind': 'UNRESOLVED', 'subject': 'RECORDED_FIXTURE_NOT_ASSESSED',
                    'event_dates': [], 'reported_context_times': [], 'status': 'RECORDED_FIXTURE_NOT_ASSESSED',
                    'description': 'Transport fixture only; no source meaning is asserted.',
                    'evidence': [{'unit_id': owner, 'kind': 'NATIVE_FACT', 'source_index': 418}]}],
                'scope_current_involvement': 'UNRESOLVED', 'unresolved': ['Recorded fixture; actual interpretation remains open'],
                'scan_complete': False, 'context_requests': [{'anchor': {'unit_id': owner, 'kind': 'NATIVE_FACT', 'source_index': 418},
                    'target': {'kind': 'XML_ELEMENT_ID', 'element_id': 'f-408-1'}}]}
            raw = evidence_json_bytes(response); response_digest = sha256_bytes(content=raw)
            (HERE/'recorded-initial-response.json').write_bytes(raw)
            follow = task.prepare_followup(source, digest, t, raw, response_digest)
            follow_answer = {**response, 'context_requests': []}
            answer = evidence_json_bytes(follow_answer); answer_digest = sha256_bytes(content=answer)
            (HERE/'recorded-followup-response.json').write_bytes(answer)
            if follow['status'] == 'OFFLINE_FOLLOWUP_FITS':
                parsed = task.parse_followup(source, digest, t, raw, response_digest, answer, answer_digest,
                    actual_request_body=follow['request_body'], expected_request_sha256=follow['proposed_request_sha256'])
                status = parsed['status']; assert parsed['original_response'] == follow_answer
                assert not parsed['next_execution_prepared'] and not parsed['company_result_created']
            else:
                status = follow['status']
            (HERE/'actual-recorded-path.json').write_bytes(evidence_json_bytes({
                'recorded_fixture_not_model_extraction': True, 'scan_request_sha256': t['request_sha256'],
                'raw_initial_response_sha256': response_digest, 'raw_followup_response_sha256': answer_digest,
                'status': status, 'followup_measure': follow.get('measure'),
                'context_packet': follow['parsed']['located_context'],
                'literal_continuation_trace': follow['parsed']['literal_continuation_trace'],
                'semantic_acceptance': False, 'company_result_created': False, 'business_calls': [0, 0, 0]}))
    assert sha256_file(path=ledger) == ledger_before
    report = {'prototype_code_root': str(HERE), 'product_code_root': str(HERE.parents[3]),
        'prototype_sha256': sha256_file(path=HERE/'task_contract.py'),
        'prompt_sha256': sha256_file(path=HERE/'scan-prompt.txt'), 'samples': summaries,
        'seconds': format(time.monotonic()-start, '.3f'), 'ledger_sha256': ledger_before,
        'ledger_unchanged': True, 'business_calls': [0, 0, 0],
        'actual_model_validation': False, 'complete_company_ready': False}
    (HERE/'measured-plan.json').write_bytes(evidence_json_bytes(report))
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}), flush=True)


if __name__ == '__main__':
    main()
