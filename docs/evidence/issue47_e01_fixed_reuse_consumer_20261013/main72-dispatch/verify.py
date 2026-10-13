"""Observe one actual historical task on an isolated ordinary-state copy."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


worker = '''import copy,json,socket,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_e01_company_case as h,historical_event_items as i,historical_ma_confirmation as m,calculator,ordinary_current_update as updater
from vnext.continuous_call_ledger import CallLedger
from scripts import securegpt_sdk
blocked={h.prepare_historical_e01_year_case.__code__,i.content_confirmation_candidates.__code__,m.confirmation_request.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__,calculator.withheld_metric_result.__code__}
observed={'entered_producers':[],'configuration_comparisons':[]}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:
  observed['entered_producers'].append(frame.f_code.co_name)
  raise AssertionError('UNCHANGED_HISTORY_ATTEMPTED_PRODUCER:'+frame.f_code.co_name)
 if event=='call' and frame.f_code is updater._same_processing_configuration.__code__:
  observed['configuration_comparisons'].append(copy.deepcopy({key:frame.f_locals[key] for key in ('previous','current')}))
def forbidden(*args,**kwargs):raise AssertionError('NO_NETWORK_MODEL_OR_CALL_CLAIM')
sys.setprofile(guard)
try:
 with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden),patch.object(CallLedger,'claim',forbidden),patch.object(securegpt_sdk,'send',forbidden):
  result=main(json.loads(sys.argv[1]))
finally:
 sys.setprofile(None)
 from pathlib import Path
 Path(sys.argv[2]).write_text(json.dumps(observed,indent=2))
raise SystemExit(result)
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original-state', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    original, out = args.original_state.resolve(), args.out.resolve()
    out.mkdir(exist_ok=False)
    state = out / 'state'
    original_before = hashes(original)
    shutil.copytree(original, state)
    assert original_before == hashes(state)
    result_before = {p: digest for p, digest in hashes(state).items() if '/results/' in p}
    source = Path(json.loads((state / 'company-task.json').read_text())['source_root'])
    watch = ['config/company_registry.csv', 'evidence/requests_log.csv',
             'evidence/requests_log_manifest.json']
    source_before = {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}
    phases = {}

    def invoke(name, argv):
        start = time.perf_counter()
        run = subprocess.run([sys.executable, '-B', '-c', worker,
                              json.dumps(argv), str(out / (name + '-observed.json'))],
                             capture_output=True, text=True)
        receipt = {'argv': argv, 'seconds': time.perf_counter() - start,
                   'exit_code': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr}
        (out / (name + '.json')).write_text(json.dumps(receipt, indent=2))
        assert run.returncode in (0, 2) and not run.stderr, receipt
        report = json.loads(run.stdout)
        phases[name] = {k: receipt[k] for k in ('seconds', 'exit_code')}
        return report

    before = hashes(state)
    read_before = invoke('read-before', ['results', '--company', 'pfizer',
        '--state-root', str(state), '--output-root', str(out / 'read-before')])
    assert before == hashes(state)
    run = invoke('repeat', ['run', '--company', 'pfizer', '--period', 'fiscal-years',
        '--fiscal-year-start', '2023', '--fiscal-year-end', '2023', '--metric', 'E01',
        '--source-root', str(source), '--work-dir', str(state), '--output-dir', str(out / 'runs')])
    observed = json.loads((out / 'repeat-observed.json').read_text())
    assert observed['configuration_comparisons']
    comparison = observed['configuration_comparisons'][-1]
    difference = {}
    for key in comparison['previous'].keys() | comparison['current'].keys():
        left, right = comparison['previous'].get(key), comparison['current'].get(key)
        if left == right:
            continue
        if isinstance(left, dict) and isinstance(right, dict):
            difference[key] = {p: {'before': left.get(p), 'after': right.get(p)}
                               for p in left.keys() | right.keys() if left.get(p) != right.get(p)}
        else:
            difference[key] = {'before': left, 'after': right}
    after = hashes(state)
    assert result_before == {p: digest for p, digest in after.items() if '/results/' in p}
    invoke('read-after', ['results', '--company', 'pfizer', '--state-root', str(state),
                        '--output-root', str(out / 'read-after')])
    assert after == hashes(state)
    rows = list(csv.DictReader((out / 'read-after/metrics_matrix.csv').open()))
    assert len(rows) == 1 and rows[0]['value'] == ''
    assert hashes(original) == original_before
    assert source_before == {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}
    receipt = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'isolated_ordinary_state_copy': True, 'phases': phases, 'metric': run['metrics'][0],
        'entered_producers': observed['entered_producers'], 'configuration_difference': difference,
        'state_files_before': len(before), 'state_files_after': len(after),
        'saved_result_files_unchanged': len(result_before),
        'original_task_files_unchanged': len(original_before), 'source_metadata_unchanged': source_before,
        'read_after_csv_row': rows[0], 'new_calls': {'sec': 0, 'provider': 0, 'paid': 0}}
    (out / 'summary.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: receipt[k] for k in ('head', 'phases', 'entered_producers',
        'configuration_difference', 'saved_result_files_unchanged', 'original_task_files_unchanged')}))


if __name__ == '__main__':
    main()
