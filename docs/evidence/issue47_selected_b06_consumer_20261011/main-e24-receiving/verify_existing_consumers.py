"""Only affected B06 configurations migrate; old results remain byte-identical."""
import hashlib
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
SOURCE = Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
OLD = json.loads((OUT.parent / 'main-969-receiving/existing-consumers.json').read_text())
LOCAL = ROOT / 'work/b06-main-e24'
LOCAL.mkdir(parents=True, exist_ok=True)


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def invoke(name, arguments, forbid=True):
    checkpoint = LOCAL / (name + '.checkpoint.json')
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text())
        # Documentation changes do not invalidate a completed recording phase.
        # Changed processing code/config requires an actual new observation.
        assert subprocess.run(['git', 'diff', '--quiet', saved['production_commit'],
                               'HEAD', '--', 'scripts', 'tools', 'config', 'catalog']).returncode == 0
        print(name, 'reuse completed phase', saved['run']['seconds'], flush=True)
        return saved['run']
    code = '''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_b06_case as h,current_b06_case as b,calculator
blocked={h.prepare_historical_b06_year_case.__code__,h.prepare_selected_debt_sources.__code__,b.prepare_selected_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('Repeat/read cannot prepare or calculate')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
    start = time.perf_counter()
    run = subprocess.run([sys.executable, '-B', '-c', code, json.dumps(arguments),
                          '1' if forbid else '0'], text=True, capture_output=True)
    elapsed = time.perf_counter() - start
    (LOCAL / (name + '.stdout')).write_text(run.stdout)
    (LOCAL / (name + '.stderr')).write_text(run.stderr)
    assert not run.stderr and run.returncode in (0, 2), (name, run.returncode, run.stderr)
    result = json.loads(run.stdout)
    print(name, round(elapsed, 3), run.returncode, flush=True)
    entry = {'arguments': arguments, 'seconds': elapsed, 'exit': run.returncode, 'result': result}
    checkpoint.write_text(json.dumps({'production_commit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip(), 'run': entry}, indent=2) + '\n')
    return entry


def row_summary(row):
    return {k: row.get(k) for k in ('company_id', 'metric_id', 'fiscal_year', 'period_start',
            'period_end', 'value', 'unit', 'status', 'result_id', 'local_metric_status', 'requested')}


receipt = []
for old in OLD['records']:
    company = old['company']
    state = Path(old['rows'][0]['record_root'].split('/updates/')[0])
    before = hashes(state)
    protected = {p: h for p, h in before.items() if '/results/' in p}
    completed = json.loads((state / 'updates/B06/periods/FY2024/completed-check.json').read_text())
    saved_files = completed['configuration']['declared_processing_files']
    changed = {p: {'saved_sha256': sha,
                   'current_sha256': hashlib.sha256((ROOT / p).read_bytes()).hexdigest()}
               for p, sha in saved_files.items()
               if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != sha}
    entry = {'company': company, 'changed_declared_processing_files': changed}
    args = ['run', '--company', company, '--period', 'fiscal-years', '--fiscal-year-start', '2024',
            '--fiscal-year-end', '2024', '--metric', 'B06', '--source-root', str(SOURCE),
            '--work-dir', str(state), '--output-dir', str(state.parent / ('main-e24-run-' + str(time.time_ns())))]
    # One positive and one unresolved-interest consumer exercise changed
    # selection/reader dependencies. The nonpositive-equity result is read only.
    if company in ('enphase_energy', 'macys'):
        migration = invoke(company + '-migration', args, forbid=not bool(changed))
        repeat = invoke(company + '-repeat', args)
        assert not repeat['result']['metrics'][0]['calculation_performed']
        assert not repeat['result']['metrics'][0]['new_candidate_created']
        entry['migration'] = migration
        entry['repeat'] = repeat
    else:
        entry['migration_not_run'] = 'Unchanged business evidence reused; only independent read required here'
    after_run = hashes(state)
    assert all(after_run.get(p) == h for p, h in protected.items()), 'Old result bytes changed'
    read = invoke(company + '-read', ['results', '--company', company, '--state-root', str(state),
                  '--output-root', str(state.parent / ('main-e24-read-' + str(time.time_ns())))])
    assert after_run == hashes(state), 'Independent read mutated state'
    # The old reference is the actual exported CSV. JSON view entries have
    # integer fiscal years and no CSV status column; compare like with like.
    with (Path(read['result']['output_root']) / 'metrics_matrix.csv').open() as stream:
        current_rows = [row_summary(r) for r in csv.DictReader(stream)]
    old_rows = [row_summary(r) for r in old['rows']]
    # Request flags differ between CLI run and all-results view; business,
    # period and original Result identity must not differ.
    keys = ('metric_id', 'fiscal_year', 'period_start', 'period_end', 'value', 'unit', 'status', 'result_id')
    assert [{k: r[k] for k in keys} for r in current_rows] == [{k: r[k] for k in keys} for r in old_rows]
    entry['read'] = {k: v for k, v in read.items() if k != 'result'}
    entry['rows'] = current_rows
    entry['protected_old_result_files'] = len(protected)
    entry['independent_read_state_files_unchanged'] = len(after_run)
    receipt.append(entry)
summary = {'code_root': str(ROOT), 'records': receipt, 'new_calls': [0, 0, 0]}
(LOCAL / 'complete-results.json').write_text(json.dumps(summary, indent=2) + '\n')
for entry in receipt:
    for phase in ('migration', 'repeat'):
        if phase in entry:
            result = entry[phase].pop('result')
            entry[phase]['metrics'] = result['metrics']
(OUT / 'existing-consumers.json').write_text(json.dumps(summary, indent=2) + '\n')
print('Old positive, nonpositive equity, stable interest hold, unrequested neighbor and true missing year preserved')
