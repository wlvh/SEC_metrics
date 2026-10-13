"""Use the ordinary company CLI with an existing selected Salesforce task.

All first/repeat/read phases are explicit. Sources stay read-only and output
directories must be new. This is not a second company controller.
"""
import argparse
from contextlib import ExitStack, redirect_stdout
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_statement_cases, calculator, batch_workflow
from vnext.normal_source_requirements import _Requirements


def hashes(root, result_only=False):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file()
        and (not result_only or '/results/' in str(p.relative_to(root)))}


parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['first', 'repeat', 'read'])
parser.add_argument('--state', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
task = json.loads((args.state / 'company-task.json').read_text())
assert task['company_id'] == 'salesforce'
source = Path(task['source_root'])
before_state, before_results = hashes(args.state), hashes(args.state, True)
source_paths = [source / 'config/company_registry.csv', source / 'evidence/requests_log.csv',
                source / 'evidence/requests_log_manifest.json']
before_source = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
source_calls = []
blocked = {f.__code__ for f in (historical_statement_cases.prepare_historical_statement_year_case,
    calculator.calculate_metric, batch_workflow.calculate_metric)}
previous = sys.getprofile()


def profile(frame, event, arg):
    if event == 'call':
        if frame.f_code == _Requirements.require.__code__:
            source_calls.append({k: frame.f_locals.get(k) for k in ('url', 'role', 'accession')})
        if args.phase != 'first' and frame.f_code in blocked:
            raise AssertionError('PROCESSING_FORBIDDEN:' + frame.f_code.co_name)
    if previous is not None:
        previous(frame, event, arg)


command = (['results', '--company', 'salesforce', '--state-root', str(args.state),
            '--output-root', str(args.output / 'csv')] if args.phase == 'read' else
           ['run', '--company', 'salesforce', '--metric', 'B01', '--period', 'fiscal-years',
            '--fiscal-year-start', '2026', '--fiscal-year-end', '2026',
            '--source-root', str(source), '--work-dir', str(args.state),
            '--output-dir', str(args.output / 'run')])
stream = io.StringIO()
started = perf_counter()
with ExitStack() as stack:
    stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')))
    sys.setprofile(profile)
    stack.callback(sys.setprofile, previous)
    with redirect_stdout(stream):
        code = main(command)
elapsed = perf_counter() - started
after_state, after_results = hashes(args.state), hashes(args.state, True)
payload = json.loads(stream.getvalue())
receipt = {'phase': args.phase, 'arguments': command, 'exit_code': code,
    'seconds': elapsed, 'stdout': stream.getvalue(), 'source_requirement_calls': source_calls,
    'old_results_preserved': all(after_results.get(k) == v for k, v in before_results.items()),
    'result_files_before_after': [len(before_results), len(after_results)],
    'state_files_before_after': [len(before_state), len(after_state)],
    'results_unchanged': before_results == after_results, 'state_unchanged': before_state == after_state,
    'source_registration_and_ledger_unchanged': before_source == {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
    'new_calls': [0, 0, 0]}
(args.output / 'execution.json.gz').write_bytes(gzip.compress(
    (json.dumps(receipt, indent=2) + '\n').encode(), mtime=0))
summary = {k: v for k, v in receipt.items() if k not in ('stdout', 'arguments')}
summary['metrics'] = payload['metrics']
(args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k != 'metrics'}, indent=2))
assert receipt['old_results_preserved'] and receipt['source_registration_and_ledger_unchanged']
if args.phase == 'first':
    assert source_calls
    assert all(m['calculation_performed'] for m in payload['metrics'])
elif args.phase == 'repeat':
    assert not source_calls and receipt['results_unchanged']
    assert all(m['status'] == 'NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed']
               for m in payload['metrics'])
else:
    assert not source_calls and receipt['state_unchanged']
