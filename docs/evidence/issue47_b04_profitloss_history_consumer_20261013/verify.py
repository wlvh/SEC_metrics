"""One affected historical B04 migration using the public renderer."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


worker = '''import json,socket,sys
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import calculator,historical_statement_cases as statement,historical_d02_case as legal
from vnext.continuous_call_ledger import CallLedger
from scripts import securegpt_sdk
codes={statement.prepare_historical_statement_year_case.__code__:'statement',calculator.calculate_metric.__code__:'calculate_metric',calculator.calculate_observation_metric.__code__:'calculate_observation_metric',calculator.calculate_text_metric.__code__:'calculate_text_metric',legal.prepare_historical_legal_sources.__code__:'legal_source',legal.finish_historical_legal_case.__code__:'legal_finish'}
counts={name:0 for name in codes.values()}
def profile(frame,event,arg):
 if event=='call' and frame.f_code in codes:
  name=codes[frame.f_code];counts[name]+=1
  if sys.argv[2]!='first':raise AssertionError('REPEAT_READ_ENTERED_PRODUCER:'+name)
def forbidden(*args,**kwargs):raise AssertionError('NO_NETWORK_MODEL_OR_CLAIM')
sys.setprofile(profile)
try:
 with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden),patch.object(CallLedger,'claim',forbidden),patch.object(securegpt_sdk,'send',forbidden):
  rc=main(json.loads(sys.argv[1]))
finally:
 sys.setprofile(None);Path(sys.argv[3]).write_text(json.dumps(counts,indent=2))
raise SystemExit(rc)
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    state, out = args.state_root.resolve(), args.out.resolve()
    out.mkdir(exist_ok=False)
    before = hashes(state)
    old_results = {p: value for p, value in before.items() if '/results/' in p}
    source = Path(json.loads((state / 'company-task.json').read_text())['source_root'])
    watch = ['config/company_registry.csv', 'evidence/requests_log.csv', 'evidence/requests_log_manifest.json']
    source_before = {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}
    phases = {}

    def invoke(name, argv):
        start = time.perf_counter()
        run = subprocess.run([sys.executable, '-B', '-c', worker, json.dumps(argv),
                              name, str(out / (name + '-calls.json'))], capture_output=True, text=True)
        receipt = {'argv': argv, 'seconds': time.perf_counter() - start,
                   'exit_code': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr}
        (out / (name + '.json')).write_text(json.dumps(receipt, indent=2))
        assert run.returncode == 0 and not run.stderr, receipt
        phases[name] = {k: receipt[k] for k in ('seconds', 'exit_code')}
        return json.loads(run.stdout)

    invoke('read-before', ['results', '--company', 'ford_motor_company', '--state-root', str(state),
                          '--output-root', str(out / 'read-before')])
    old_rows = list(csv.DictReader((out / 'read-before/metrics_matrix.csv').open()))
    assert hashes(state) == before
    argv = ['run', '--company', 'ford_motor_company', '--period', 'fiscal-years',
            '--fiscal-year-start', '2025', '--fiscal-year-end', '2025', '--metric', 'B04',
            '--source-root', str(source), '--work-dir', str(state), '--output-dir', str(out / 'runs')]
    first = invoke('first', argv)['metrics'][0]
    first_calls = json.loads((out / 'first-calls.json').read_text())
    assert first['calculation_performed'] and first['new_candidate_created'], first
    assert first['result_reason_code'] == 'PASS'
    assert first_calls['statement'] == 1 and first_calls['calculate_observation_metric'] > 0
    assert first_calls['legal_source'] == first_calls['legal_finish'] == 0
    after = hashes(state)
    assert all(after[p] == digest for p, digest in old_results.items())
    current_results = {p: digest for p, digest in after.items() if '/results/' in p}
    repeated = invoke('repeat', argv)['metrics'][0]
    assert repeated['status'] == 'NO_SOURCE_CONTENT_CHANGE'
    assert not repeated['calculation_performed'] and not repeated['new_candidate_created']
    assert repeated['result_id'] == first['result_id']
    assert all(value == 0 for value in json.loads((out / 'repeat-calls.json').read_text()).values())
    assert current_results == {p: digest for p, digest in hashes(state).items() if '/results/' in p}
    read_before = hashes(state)
    invoke('read', ['results', '--company', 'ford_motor_company', '--state-root', str(state),
                    '--output-root', str(out / 'read')])
    assert read_before == hashes(state)
    rows = list(csv.DictReader((out / 'read/metrics_matrix.csv').open()))
    row = next(r for r in rows if r['metric_id'] == 'B04' and r['fiscal_year'] == '2025')
    assert row['value'] == '-8162000000' and row['unit'] == 'USD'
    assert row['period_start'] == '2025-01-01' and row['period_end'] == '2025-12-31'
    assert row['cik'] == '37996' and row['result_id'] == first['result_id']
    assert 'ProfitLoss' in row['notes'] and 'non-controlling interest' in row['notes']
    def identity(r):
        return r['metric_id'], r['fiscal_year']
    selected = ('B04', '2025')
    keep = ('value', 'unit', 'period_start', 'period_end', 'result_id', 'status')
    old_other = {identity(r): {k: r[k] for k in keep} for r in old_rows if identity(r) != selected}
    new_other = {identity(r): {k: r[k] for k in keep} for r in rows if identity(r) != selected}
    assert old_other == new_other
    assert source_before == {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}
    receipt = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'phases': phases, 'first_metric': first, 'repeat_metric': repeated,
        'first_calls': first_calls, 'repeat_calls': json.loads((out / 'repeat-calls.json').read_text()),
        'csv_row': row, 'other_saved_rows_unchanged': len(old_other),
        'old_result_files_unchanged': len(old_results), 'new_result_file_count': len(current_results),
        'reader_state_files_unchanged': len(read_before), 'source_metadata_unchanged': source_before,
        'new_calls': {'sec': 0, 'provider': 0, 'paid': 0}}
    (out / 'summary.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: receipt[k] for k in ('head', 'phases', 'first_calls',
        'repeat_calls', 'other_saved_rows_unchanged', 'old_result_files_unchanged')}))


if __name__ == '__main__':
    main()
