"""Read saved originals through the formal sources CLI; forbid calls/calculation."""
import argparse
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import socket
import time
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_e01_company_case as event_case


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--company', required=True)
    parser.add_argument('--report-end', required=True)
    parser.add_argument('--metric', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('REPRODUCTION_OUTPUT_ALREADY_EXISTS')
    source = args.source_root.resolve()
    observed = ('config/company_registry.csv', 'evidence/requests_log.csv',
                'evidence/requests_log_manifest.json')
    before = {path: digest(source / path) for path in observed}
    capture = io.StringIO()
    command = ['sources', '--company', args.company, '--source-root', str(source),
               '--report-end', args.report_end]
    for metric in args.metric:
        command += ['--metric', metric]
    started = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, 'connect',
            side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',
            side_effect=AssertionError('BUSINESS_CLAIM_FORBIDDEN')))
        for name in ('calculate_metric', 'calculate_observation_metric', 'withheld_metric_result'):
            stack.enter_context(patch('vnext.calculator.' + name,
                side_effect=AssertionError('CALCULATOR_FORBIDDEN')))
        for name in ('calculate_observation_metric', 'withheld_metric_result'):
            stack.enter_context(patch.object(event_case, name,
                side_effect=AssertionError('METRIC_RESULT_FORBIDDEN')))
        stack.enter_context(redirect_stdout(capture))
        return_code = main(command)
    elapsed = time.perf_counter() - started
    result = json.loads(capture.getvalue())
    after = {path: digest(source / path) for path in observed}
    assert before == after, 'SAVED_SOURCE_METADATA_CHANGED'
    assert not result['metric_executed'] and not result['metric_acceptance_proven']
    assert result['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
    assert not result['fetch_authorized'] and not result['production_authorized']
    event = result.get('event_source_context')
    if event is not None:
        assert event['complete_annual_count'] is None
        assert not event['matching_response_available'] and not event['metric_executed']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'command': command, 'exit_code': return_code,
        'elapsed_seconds': elapsed, 'source_metadata_before': before,
        'source_metadata_after': after, 'result': result}, ensure_ascii=False,
        indent=2) + '\n')
    print(json.dumps({'company': args.company, 'metrics': args.metric,
        'exit_code': return_code, 'status': result['status'],
        'source_graph_known': result['complete_known_source_graph'],
        'requirements': len(result['requirements']),
        'event_request_id': None if event is None else event['request_id'],
        'elapsed_seconds': elapsed, 'limitations': result['limitations']}))


if __name__ == '__main__':
    run()
