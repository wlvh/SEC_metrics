"""Directed company-entry receiving check; originals and old tasks stay in place."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--state-parent', type=Path, required=True)
parser.add_argument('--source-only', action='store_true',
                    help='Only verify the existing B04 producer cannot read rules from the source package')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[4]
base = Path(__file__).resolve().parent
if args.source_only:
    from unittest.mock import patch
    from vnext.historical_saved_case import prepare_historical_deterministic_year_case
    source = args.source_root.resolve()
    original = Path.open

    def guarded(path, *a, **kw):
        path = Path(path).resolve()
        if source in path.parents:
            relative = path.relative_to(source)
            if (relative.parts[0] in ('scripts', 'tools', 'catalog', 'config')
                    and relative.as_posix() != 'config/company_registry.csv'):
                raise AssertionError('No source-package program rules: '+str(relative))
        return original(path, *a, **kw)

    started = time.monotonic()
    with patch.object(Path, 'open', guarded), \
         patch('socket.socket.connect', side_effect=AssertionError('No business network')):
        case = prepare_historical_deterministic_year_case(repo_root=source, company_id='macys',
                                                        metric_id='B04', fiscal_year=2023)
    assert case['results']['B04']['value'] == '105000000'
    value = {'source_root': str(source), 'metric': 'B04', 'fiscal_year': 2023,
        'source_program_config_reads_forbidden': True, 'only_source_company_registry_permitted': True,
        'source_or_program_tree_copy_count': 0, 'seconds': time.monotonic()-started,
        'result_id': case['results']['B04']['result_id'], 'new_calls': {'sec': 0, 'provider': 0, 'paid': 0}}
    (base/'catalog-source-only-check.json').write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(value)); raise SystemExit(0)
task = args.state_parent.resolve()/'historical-catalog-cli-20261008'
for n in range(100):
    candidate = task if n == 0 else task.with_name(task.name+'-'+str(n))
    if not candidate.exists():
        task = candidate; task.mkdir(parents=True); break
else:
    raise ValueError('No unused task path')
source = args.source_root.resolve()
operations = []


def invoke(label, arguments, *, forbid=False, prior_failure=False, expected_code=0):
    code = ('import json,sys;from unittest.mock import patch;from contextlib import ExitStack;'
            'from tools.vnext_company import main\n'
            'with ExitStack() as stack:\n'
            ' stack.enter_context(patch("socket.socket.connect",side_effect=AssertionError("No business network")))\n')
    if forbid:
        for name in ('vnext.normal_period_selection.resolve_period_selection',
                     'vnext.historical_results.resolve_historical_companyfacts_metrics',
                     'vnext.historical_zero_ai_results.resolve_historical_zero_ai_metric'):
            code += (' stack.enter_context(patch('+repr(name)+','
                     'side_effect=AssertionError("Unchanged sources must not select or calculate")))\n')
    if prior_failure:
        code += (' from vnext.normal_companyfacts_results import NormalCompanyfactsError\n'
                 ' stack.enter_context(patch("vnext.historical_results.prior_filing",'
                 'side_effect=NormalCompanyfactsError("CONSTRUCTED_CONTROL_PRIOR_SOURCE_UNAVAILABLE")))\n')
    code += ' raise SystemExit(main(json.loads(sys.argv[1])))'
    started = time.monotonic()
    completed = subprocess.run([sys.executable, '-c', code, json.dumps(arguments)], cwd=repo,
        env={**os.environ, 'PYTHONPATH': 'scripts:.'}, capture_output=True, text=True, timeout=120)
    elapsed = time.monotonic()-started
    (base/(label+'.json')).write_text(completed.stdout)
    (base/(label+'.stderr')).write_text(completed.stderr)
    if completed.returncode != expected_code:
        raise AssertionError((label, completed.returncode, completed.stderr, completed.stdout[:1200]))
    value = json.loads(completed.stdout)
    operations.append({'label': label, 'seconds': elapsed, 'status': value.get('status'),
                       'exit_code': completed.returncode})
    return value


def rows(value):
    return list(csv.DictReader(io.StringIO((Path(value['output_root'])/'metrics_matrix.csv')
                                          .read_text(encoding='utf-8-sig'))))


def protect(state):
    return {str(p.relative_to(state)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in state.rglob('*') if p.is_file()
            and ('/results/' in str(p) or p.name in ('current-result.json', 'completed-check.json'))}


def run_arguments(state, output):
    return ['run', '--company', 'macys', '--source-root', str(source), '--work-dir', str(state),
        '--output-dir', str(output), '--period', 'fiscal-years', '--fiscal-year-start', '2023',
        '--fiscal-year-end', '2023', '--metric', 'B02', '--metric', 'B04', '--metric', 'B05']


state = task/'state'
first = invoke('catalog-cli-first', run_arguments(state, task/'outputs'))
actual = {r['metric_id']: (r['value'], r['unit']) for r in rows(first)}
expected = {'B02': ('-0.0552327960068734146141886916', 'ratio'),
            'B04': ('105000000', 'USD'), 'B05': ('674000000', 'USD')}
assert actual == expected, actual
assert all((r['fiscal_year'], r['period_start'], r['period_end']) ==
           ('2023', '2023-01-29', '2024-02-03') for r in rows(first))
before = protect(state)
repeat = invoke('catalog-cli-repeat', run_arguments(state, task/'outputs'), forbid=True)
assert protect(state) == before
assert all(m['status'] == 'NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed']
           for m in repeat['metrics'])
read = invoke('catalog-cli-independent-read', ['results', '--company', 'macys',
    '--state-root', str(state), '--output-root', str(task/'daily')], forbid=True)
assert protect(state) == before
assert {r['metric_id']: (r['value'], r['unit']) for r in rows(read)} == actual

# A constructed dependency failure tests isolation; it is not a conclusion
# about the real saved Macy's source, whose prior was successfully read above.
controlled = task/'constructed-missing-prior'
failure = invoke('catalog-cli-constructed-prior-failure',
    run_arguments(controlled, task/'controlled-outputs'), prior_failure=True, expected_code=2)
values = {r['metric_id']: (r['value'], r['unit']) for r in rows(failure)}
assert values['B02'][0] == '' and values['B04'] == expected['B04'] and values['B05'] == expected['B05']
held = protect(controlled)
held_repeat = invoke('catalog-cli-constructed-hold-repeat',
    run_arguments(controlled, task/'controlled-outputs'), forbid=True, expected_code=2)
assert protect(controlled) == held
assert {m['metric_id']: m['status'] for m in held_repeat['metrics']} == {
    'B02': 'PREVIOUS_INPUT_WITHHELD', 'B04': 'NO_SOURCE_CONTENT_CHANGE', 'B05': 'NO_SOURCE_CONTENT_CHANGE'}
record = {'task_root': str(task), 'source_root': str(source), 'operations': operations,
    'actual_values': actual, 'actual_period': ['2023-01-29', '2024-02-03'], 'actual_fiscal_year': 2023,
    'protected_file_count': len(before), 'constructed_protected_file_count': len(held),
    'protected_bytes_unchanged_on_repeat_and_read': True,
    'repeat_and_read_factory_forbidden': True, 'source_and_program_tree_copies': 0,
    'constructed_control': 'Prior source reader failure; not a Macy financial finding',
    'calls': {'sec': 0, 'provider': 0, 'paid': 0},
    'scope': 'Three saved-source historical catalog consumers; not the full five-year business acceptance',
    'already_completed_pilot_or_two_year_B01_not_recomputed': True}
(base/'catalog-cli-verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(record, ensure_ascii=False))
