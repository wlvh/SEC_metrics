"""Affected saved-source company checks; references never enter production.

Run after receiving the shared numeric-note source fix. All output belongs to
a new external directory. Keep partial results on any failure; do not restart
the completed phases just to fix this verification driver.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from decimal import Decimal, localcontext


def digests(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--ford-only', action='store_true',
        help='The existing Macy negative task can be migrated separately without a duplicate fresh run')
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, 'PYTHONPATH': 'scripts:tools:.', 'PYTHONDONTWRITEBYTECODE': '1'}
    source_files = [args.source_root/'evidence/requests_log.csv',
                    args.source_root/'evidence/requests_log_manifest.json']
    source_before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}

    def invoke(name, command, *, forbid=False, exit_code=0):
        code = '''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
'''
        if forbid:
            code += '''from vnext import historical_statement_cases as cases,calculator
blocked={cases.prepare_historical_statement_year_case.__code__,calculator.calculate_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
sys.setprofile(guard)
'''
        code += '''with patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
        started = time.monotonic()
        process = subprocess.run([sys.executable, '-B', '-c', code, json.dumps(list(map(str, command)))],
            env=env, capture_output=True, text=True)
        report = {'seconds': time.monotonic()-started, 'exit_code': process.returncode,
            'arguments': list(map(str, command)), 'stdout': process.stdout, 'stderr': process.stderr}
        (args.output_root/(name+'.json')).write_text(json.dumps(report, indent=2)+'\n')
        print(name, report['seconds'], process.returncode, flush=True)
        assert process.returncode == exit_code and not process.stderr, report
        return json.loads(process.stdout), report

    summary = []
    cases = [('ford_motor_company',2023,2024,0)]
    if not args.ford_only:
        cases.append(('macys',2022,2022,2))
    for company, start, end, expected_exit in cases:
        state = args.output_root/company/'state'
        command = ['run','--company',company,'--period','fiscal-years',
            '--fiscal-year-start',start,'--fiscal-year-end',end,'--metric','B02',
            '--source-root',args.source_root,'--work-dir',state,
            '--output-dir',args.output_root/company/'runs']
        first, timing = invoke(company+'-first', command, exit_code=expected_exit)
        before = digests(state)
        result_files = {name: sha for name,sha in before.items()
            if '/results/' in name or name.endswith(('current-result.json','completed-check.json'))
            or name == 'company-task.json'}
        result_directories = {str(p.relative_to(state)) for p in state.glob('updates/B02/periods/*/results/*')}
        repeat, repeated = invoke(company+'-repeat', command, forbid=True, exit_code=expected_exit)
        assert all(not metric['calculation_performed'] for metric in repeat['metrics'])
        assert all(digests(state).get(name) == sha for name,sha in result_files.items())
        assert result_directories == {str(p.relative_to(state)) for p in state.glob('updates/B02/periods/*/results/*')}
        # A normal repeat logs a new check and latest-execution. Immutable
        # results/pointers remain protected; a read must change no state at all.
        before_read = digests(state)
        read, read_timing = invoke(company+'-read', ['results','--company',company,
            '--state-root',state,'--output-root',args.output_root/company/'read'], forbid=True)
        assert digests(state) == before_read
        rows = list(csv.DictReader((args.output_root/company/'read/metrics_matrix.csv').open(encoding='utf-8-sig')))
        assert len(rows) == end-start+1
        if company == 'ford_motor_company':
            originals = {2023:(176191,158057),2024:(184992,176191)}
            for row in rows:
                fy = int(row['fiscal_year']); current, prior = originals[fy]
                with localcontext() as context:
                    context.prec = 28
                    assert Decimal(row['value']) == (Decimal(current)-Decimal(prior))/Decimal(prior)
                assert row['unit'] == 'ratio' and row['cik'] == '37996'
                assert row['period_start'] == f'{fy}-01-01' and row['period_end'] == f'{fy}-12-31'
                record = Path(row['record_root'])
                assessment = json.loads((record/'input-assessments.json').read_text())['assessments']['historical_statement']
                assert set(assessment['paired_revenue_scopes']) == {'current','prior'}
                assert all(scope['complete_scope_proven'] for scope in assessment['paired_revenue_scopes'].values())
                records = [json.loads(line) for line in (record/'records.jsonl').read_text().splitlines()]
                claims = [r for r in records if r['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM']
                assert {r['value'] for r in claims} == {str(current*1000000),str(prior*1000000)}
        else:
            assert rows[0]['value'] == '' and rows[0]['status'] == 'WITHHELD'
            assessment = json.loads((Path(rows[0]['record_root'])/'input-assessments.json').read_text())['assessments']['historical_statement']
            assert assessment['unresolved_revenue_role'] == 'current'
            assert not assessment['paired_revenue_scopes']['current']['complete_scope_proven']
        evidence = args.output_root/company/'read/metric_evidence.csv'
        assert evidence.exists() and evidence.stat().st_size > 0
        summary.append({'company':company,'first_seconds':timing['seconds'],
            'repeat_seconds':repeated['seconds'],'read_seconds':read_timing['seconds'],
            'rows':rows,'unchanged_result_files':len(result_files),
            'unchanged_state_files_on_read':len(before_read)})
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p,sha in source_before.items())
    (args.output_root/'summary.json').write_text(json.dumps({'code_commit':subprocess.check_output(
        ['git','rev-parse','HEAD'],text=True).strip(),'cases':summary,'new_calls':[0,0,0]},indent=2)+'\n')


if __name__ == '__main__':
    main()
