"""Rebuild the actual existing D02 review request from admitted saved objects.

The normal admission was already executed by the full-source preparer. This
pure question builder does not grant admission, generate an answer, register a
review, create a Run, or call the provider. No executor reference is read.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--prepared-input', type=Path, required=True)
    p.add_argument('--raw-primary', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.code_root / 'scripts'))
    from vnext.historical_text_results import legal_review_request
    from vnext.continuous_semantic_calls import request_body
    from vnext.continuous_request_context import measure_request
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    document = json.loads((args.prepared_input / 'document.json').read_bytes())
    proposal = json.loads((args.prepared_input / 'incomplete-proposal.json').read_bytes())
    full_question = json.loads((args.prepared_input / 'request.json').read_bytes())
    raw = args.raw_primary.read_bytes()
    assert 'sha256:' + sha(raw) == document['raw_asset_id']
    sid = document['source_reference_id']
    source_args = {
        'raw_bytes_by_id': {document['raw_asset_id']: raw},
        'target': {'company_id': full_question['company_id'],
                   'entity': full_question['target_cik'],
                   'period_end': full_question['period_end']},
    }
    with patch('socket.socket', side_effect=AssertionError('NO_NETWORK')):
        question = legal_review_request(
            prepared={'documents': {sid: document}, 'proposals': {sid: proposal}},
            source_arguments=source_args)
        path = args.code_root / 'docs/evidence/issue47_history/model-egress/dev-dry-run/dump_requests.py'
        spec = importlib.util.spec_from_file_location('issue47_fixed_transport_fields', path)
        dry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dry)
        policy = TransportPolicy.from_mapping(value={
            **dry.TRANSPORT_FIELDS, 'endpoint_host': _DEEPSEEK_ENDPOINT_HOST})
        body = request_body(question, policy)
        measurement = measure_request(body, require_reference=True)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'request-body.json').write_bytes(body)
    for name, value in [('request.json', question), ('context-measurement.json', measurement)]:
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    receipt = {
        'record_type': 'ISSUE47_EXISTING_D02_NORMAL_REQUEST_REBUILD_ONLY',
        'request_sha256': measurement['request_sha256'],
        'semantic_request_id': question['request_id'],
        'source_raw_asset_id': document['raw_asset_id'],
        'pool_blocks': len(question['blocks']), 'must_decide': len(question['must_decide']),
        'input_tokens': measurement['input_tokens'],
        'context_tokens': measurement['context_tokens'], 'fits': measurement['fits'],
        'exact_existing_request_function_and_provider_renderer': True,
        'executor_reference_or_old_answer_read': False,
        'admission_or_provider_execution_granted': False,
        'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0,
    }
    (args.out / 'rebuild.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps(receipt, indent=1))


if __name__ == '__main__':
    main()
