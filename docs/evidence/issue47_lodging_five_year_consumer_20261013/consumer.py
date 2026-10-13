import argparse
from contextlib import ExitStack, redirect_stdout
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from tools.vnext_company import main as company_main


def hashes(root, result_only=False):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()
            and (not result_only or '/results/' in str(p.relative_to(root)))}


def execute(argv, forbidden=False):
    output = io.StringIO()
    started = perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')))
        if forbidden:
            from vnext import historical_lodging_results, normal_lodging_results, calculator, batch_workflow
            blocked = {f.__code__ for f in (
                historical_lodging_results.prepare_historical_lodging_year_case,
                normal_lodging_results.calculate_selected_lodging_metric,
                calculator.calculate_metric, batch_workflow.calculate_metric)}
            previous = sys.getprofile()
            def profile(frame, event, arg):
                if event == 'call' and frame.f_code in blocked:
                    raise AssertionError('PROCESSING_FORBIDDEN:' + frame.f_code.co_name)
                if previous is not None:
                    previous(frame, event, arg)
            sys.setprofile(profile)
            stack.callback(sys.setprofile, previous)
        with redirect_stdout(output):
            code = company_main(argv)
    return {'arguments': argv, 'exit_code': code, 'seconds': perf_counter() - started,
            'stdout': output.getvalue()}


args = argparse.ArgumentParser()
args.add_argument('phase', choices=['first', 'repeat', 'read'])
args.add_argument('--output', required=True, type=Path)
args.add_argument('--state', required=True, type=Path)
args.add_argument('--source-root', type=Path)
args.add_argument('--year-start', type=int, default=2021)
args.add_argument('--year-end', type=int, default=2023)
options = args.parse_args()
options.output.mkdir(parents=True, exist_ok=False)
state = options.state
source = options.source_root or Path(json.loads((state / 'company-task.json').read_text())['source_root'])
before_state = hashes(state)
before_results = hashes(state, result_only=True)
source_paths = [source / 'config/company_registry.csv', source / 'evidence/requests_log.csv',
                source / 'evidence/requests_log_manifest.json']
before_source = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
if options.phase == 'read':
    command = ['results', '--company', 'marriott_international', '--state-root', str(state),
               '--output-root', str(options.output / 'csv')]
else:
    command = ['run', '--company', 'marriott_international', '--period', 'fiscal-years',
               '--fiscal-year-start', str(options.year_start), '--fiscal-year-end', str(options.year_end),
               '--metric', 'B10', '--metric', 'B11', '--source-root', str(source),
               '--work-dir', str(state), '--output-dir', str(options.output / 'run')]
result = execute(command, forbidden=options.phase != 'first')
after_state, after_results = hashes(state), hashes(state, result_only=True)
result['old_result_files_preserved'] = all(after_results.get(k) == v for k, v in before_results.items())
result['result_files_before_after'] = [len(before_results), len(after_results)]
result['state_files_before_after'] = [len(before_state), len(after_state)]
result['old_and_new_results_unchanged'] = before_results == after_results
result['all_state_unchanged'] = before_state == after_state
result['source_registration_and_ledger_unchanged'] = before_source == {
    str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
result['new_calls'] = [0, 0, 0]
(options.output / 'execution.json.gz').write_bytes(gzip.compress(
    (json.dumps(result, indent=2) + '\n').encode(), mtime=0))
payload = json.loads(result['stdout'])
summary = {k: v for k, v in result.items() if k not in ('stdout', 'arguments')}
summary['payload_keys'] = list(payload)
summary['status'] = payload.get('status')
summary['metrics'] = payload.get('metrics')
summary['returned_metric_count'] = len(payload.get('metrics', []))
(options.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k != 'metrics'}, indent=2))
assert result['old_result_files_preserved'] and result['source_registration_and_ledger_unchanged']
if options.phase == 'repeat':
    assert result['old_and_new_results_unchanged']
    assert all(m['status'] in ('NO_SOURCE_CONTENT_CHANGE', 'PREVIOUS_INPUT_WITHHELD')
               and m.get('calculation_performed') is False for m in payload['metrics'])
if options.phase == 'read':
    assert result['all_state_unchanged']
