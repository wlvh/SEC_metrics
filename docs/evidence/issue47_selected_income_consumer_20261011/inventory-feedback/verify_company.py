"""Actual company CLI: seven returned coordinates plus one recent-block neighbor."""
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
parser.add_argument('--output-root', required=True, type=Path)
args = parser.parse_args()
source = args.source_root.resolve()
base = args.output_root.resolve()
base.mkdir(parents=True, exist_ok=False)
watch = ['config/company_registry.csv', 'evidence/requests_log.csv',
         'evidence/requests_log_manifest.json']
before_source = {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def invoke(name, cli, forbidden=False):
    code = '''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_b03_case as h,selected_income_calculation as s,calculator
blocked={h.prepare_historical_income_year_case.__code__,h.prepare_selected_income_sources.__code__,s.calculate_selected_income.__code__,calculator.calculate_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('Repeat/read cannot prepare or calculate')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No real network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
    print(name, 'start', flush=True)
    start = time.perf_counter()
    run = subprocess.run([sys.executable, '-B', '-c', code, json.dumps(cli),
                          '1' if forbidden else '0'], capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    (base / (name + '.stdout')).write_text(run.stdout)
    (base / (name + '.stderr')).write_text(run.stderr)
    assert not run.stderr and run.returncode in (0, 2), (name, run.returncode, run.stderr)
    result = json.loads(run.stdout)
    entry = {'arguments': cli, 'seconds': elapsed, 'exit': run.returncode, 'result': result}
    (base / (name + '.json')).write_text(json.dumps(entry, indent=2) + '\n')
    print(name, round(elapsed, 3), run.returncode, flush=True)
    return entry


receipt = []
for company, first_year, last_year in [('marriott_international', 2024, 2024),
                                      ('jpmorgan_chase', 2021, 2024),
                                      ('salesforce', 2021, 2023)]:
    state = base / company / 'state'
    cli = ['run', '--company', company, '--period', 'fiscal-years', '--metric', 'B03',
           '--fiscal-year-start', str(first_year), '--fiscal-year-end', str(last_year),
           '--source-root', str(source), '--work-dir', str(state),
           '--output-dir', str(base / company / 'runs')]
    fresh = invoke(company + '-fresh', cli)
    assert len(fresh['result']['metrics']) == last_year - first_year + 1
    assert all(m['status'] in ('CANDIDATE_READY', 'CANDIDATE_WITHHELD')
               for m in fresh['result']['metrics']), fresh
    old = {p: h for p, h in hashes(state).items() if '/results/' in p}
    repeat = invoke(company + '-repeat', cli, forbidden=True)
    assert all(not m['calculation_performed'] and not m['new_candidate_created']
               for m in repeat['result']['metrics'])
    assert all(hashes(state).get(p) == h for p, h in old.items())
    before = hashes(state)
    output = base / company / 'read'
    read = invoke(company + '-read', ['results', '--company', company, '--state-root', str(state),
                  '--output-root', str(output)], forbidden=True)
    assert before == hashes(state), 'Independent reading changed state'
    with (output / 'metrics_matrix.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    if company == 'marriott_international':
        assert rows[0]['value'] == '0.1653386454183266932270916335'
        assert rows[0]['unit'] == 'ratio' and rows[0]['status'] == 'OK'
    if company == 'jpmorgan_chase':
        assert all(r['status'] == 'N_A_STRUCTURAL' and not r['value'] for r in rows), rows
    assert all(r['status'] != 'INPUT_OR_EXECUTION_FAILED' for r in rows)
    records = []
    for metric in fresh['result']['metrics']:
        manifest = json.loads((Path(metric['result_root']) / 'manifest.json').read_text())
        records.append({'result_root': metric['result_root'], 'manifest': {
            k: manifest[k] for k in ('company_id', 'metric_id', 'result_id', 'target_period')},
            'source_proofs': manifest['source_proofs']})
    receipt.append({'company': company, 'fresh': fresh, 'repeat': repeat,
                    'read': {k: v for k, v in read.items() if k != 'result'},
                    'rows': rows, 'records': records, 'protected_result_files': len(old),
                    'independent_read_state_files_unchanged': len(before)})
    (base / 'partial-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
after_source = {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}
assert before_source == after_source
summary = {'source_root': str(source), 'output_root': str(base), 'records': receipt,
           'before_source': before_source, 'after_source': after_source, 'new_calls': [0, 0, 0]}
(base / 'receipt.json').write_text(json.dumps(summary, indent=2) + '\n')
print('Seven returned coordinates and recent-block neighbor completed; no real calls', flush=True)
