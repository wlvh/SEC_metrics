"""Existing historical task: one required upgrade, forbidden repeat and read."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', required=True, type=Path)
parser.add_argument('--state-root', required=True, type=Path)
parser.add_argument('--saved-call-package', required=True, type=Path)
parser.add_argument('--output-root', required=True, type=Path)
args = parser.parse_args()
base = args.output_root.resolve()
base.mkdir(parents=True, exist_ok=False)
state = args.state_root.resolve()
source = args.source_root.resolve()
package = args.saved_call_package.resolve()


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def read_rows(output):
    with (output / 'metrics_matrix.csv').open() as stream:
        return list(csv.DictReader(stream))


def invoke(name, cli, forbidden=False):
    code = '''import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_d04_selection as h,saved_d04_replay as r,calculator
blocked={h.prepare_historical_d04_selection.__code__,r.prepare_selected_saved_d04_case.__code__,r.read_saved_d04_assessment.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('No selection/replay/calculation during repeat or reading')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No real network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
    start = time.perf_counter()
    run = subprocess.run([sys.executable, '-B', '-c', code, json.dumps(cli),
                          '1' if forbidden else '0'], capture_output=True, text=True)
    entry = {'arguments': cli, 'seconds': time.perf_counter() - start,
             'exit': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr}
    (base / (name + '.json')).write_text(json.dumps(entry, indent=2) + '\n')
    assert not run.stderr and run.returncode in (0, 2), (name, run.returncode, run.stderr)
    print(name, round(entry['seconds'], 3), run.returncode, flush=True)
    return entry, json.loads(run.stdout)


package_before = hashlib.sha256(package.read_bytes()).hexdigest()
watch = ['config/company_registry.csv', 'evidence/requests_log.csv',
         'evidence/requests_log_manifest.json']
source_before = {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}
old = hashes(state)
protected = {p: h for p, h in old.items() if '/results/' in p}
read_before, _ = invoke('read-before', ['results', '--company', 'marriott_international',
    '--state-root', str(state), '--output-root', str(base / 'read-before')], forbidden=True)
assert old == hashes(state)
before_rows = read_rows(base / 'read-before')
changes = {}
ROOT = Path(__file__).resolve().parents[4]
for year in (2024,):
    saved = json.loads((state / f'updates/D04/periods/FY{year}/completed-check.json').read_text())
    files = {**saved['configuration'].get('processing_files', {}),
             **saved['configuration'].get('declared_processing_files', {})}
    changes[str(year)] = {'changed_files': [p for p, sha in files.items()
        if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != sha],
        'new_historical_catalog_dependency': 'scripts/vnext/normal_history_catalog.py' not in files}
cli = ['run', '--company', 'marriott_international', '--period', 'fiscal-years',
       '--fiscal-year-start', '2024', '--fiscal-year-end', '2024', '--metric', 'D04',
       '--source-root', str(source), '--saved-call-package', str(package),
       '--work-dir', str(state), '--output-dir', str(base / 'runs')]
upgrade, result = invoke('one-upgrade', cli)
assert all(m['status'] == 'CANDIDATE_WITHHELD' for m in result['metrics'])
assert all(m['result_reason_code'] == 'D04_SAVED_FILING_MEDIA_COVERAGE_NOT_VERIFIED'
           for m in result['metrics'])
assert all(hashes(state).get(p) == sha for p, sha in protected.items())
after_upgrade = {p: h for p, h in hashes(state).items() if '/results/' in p}
repeat, value = invoke('forbidden-repeat', cli, forbidden=True)
assert all(not m['calculation_performed'] and not m['new_candidate_created'] for m in value['metrics'])
assert all(hashes(state).get(p) == sha for p, sha in after_upgrade.items())
before_read = hashes(state)
read, _ = invoke('independent-read', ['results', '--company', 'marriott_international',
    '--state-root', str(state), '--output-root', str(base / 'read')], forbidden=True)
assert before_read == hashes(state)
rows = read_rows(base / 'read')
columns = ('metric_id', 'fiscal_year', 'period_start', 'period_end', 'value', 'unit', 'status', 'result_id')
identity = lambda row: (row['metric_id'], row['fiscal_year'])
assert len(rows) == len({identity(r) for r in rows})
assert {identity(r): {k: r[k] for k in columns} for r in rows} == {identity(r): {k: r[k] for k in columns} for r in before_rows}
assert any(r['fiscal_year'] == '2026' and r['status'] == 'INPUT_OR_EXECUTION_FAILED' for r in rows)
assert package_before == hashlib.sha256(package.read_bytes()).hexdigest()
assert source_before == {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}
summary = {'code_root': str(ROOT), 'state_root': str(state), 'configuration_changes': changes,
           'read_before': read_before, 'upgrade': upgrade, 'repeat': repeat, 'read': read,
           'rows': rows, 'old_result_files_unchanged': len(protected),
           'repeat_result_files_unchanged': len(after_upgrade),
           'independent_read_state_files_unchanged': len(before_read),
           'original_package_sha256_unchanged': package_before,
           'source_metadata_hashes_unchanged': source_before, 'new_calls': [0, 0, 0]}
(base / 'receipt.json').write_text(json.dumps(summary, indent=2) + '\n')
print('Old scoped media holds and missing year preserved; original package/source metadata unchanged')
