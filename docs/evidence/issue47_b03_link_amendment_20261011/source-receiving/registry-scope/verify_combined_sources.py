"""Combined 168/169 source CLI, authentic saved bytes, no financial processing."""
import csv
import hashlib
import io
import json
import socket
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from tools.vnext_company import main
from vnext import company_fiscal_range as ranges
from vnext import selected_source_requirements as selected

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
SOURCE = Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
WATCH = ['config/company_registry.csv', 'evidence/requests_log.csv',
         'evidence/requests_log_manifest.json']


def hashes():
    return {p: hashlib.sha256((SOURCE / p).read_bytes()).hexdigest() for p in WATCH}


def execute(args):
    capture = io.StringIO()
    start = time.perf_counter()
    with patch('sys.stdout', capture):
        code = main(args)
    return {'arguments': args, 'exit_code': code,
            'seconds': time.perf_counter() - start,
            'result': json.loads(capture.getvalue())}


def plan(row):
    return {k: v for k, v in row['result'].items() if k != 'elapsed_seconds'}


def registry_variant(destination, company, field, value):
    path = ROOT / 'config/company_registry.csv'
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    target = [r for r in rows if r['company_id'] == company]
    assert len(target) == 1
    target[0][field] = value
    with destination.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


before = hashes()
rows = []
summary_path = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/b03-link-amendment-20261011-47/summary.json')
saved = json.loads(summary_path.read_text())
manifest = json.loads((Path(saved['rows'][0]['record_root']) / 'manifest.json').read_text())
expected = {p['source_url'] for p in manifest['source_proofs']}
assert len(expected) == 6
with tempfile.TemporaryDirectory(prefix='history-source-registry-') as directory:
    program = Path(directory)
    (program / 'config').mkdir()
    registry = program / 'config/company_registry.csv'
    policy = 'config/normal_period_selection_v1.json'
    (program / policy).write_bytes((ROOT / policy).read_bytes())
    with (patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')),
          patch('vnext.calculator.calculate_metric', side_effect=AssertionError('No calculation'))):
        for scope in (['--report-end', '2025-12-31'],
                      ['--fiscal-year-start', '2025', '--fiscal-year-end', '2025']):
            args = ['sources', '--company', 'southwest_airlines', '--source-root', str(SOURCE),
                    '--metric', 'B03', *scope]
            baseline = execute(args)
            registry_variant(registry, 'pfizer', 'display_name', 'Pfizer unrelated program display')
            with patch.object(selected, 'ROOT', program), patch.object(ranges, 'ROOT', program):
                altered = execute(args)
            assert baseline['exit_code'] == altered['exit_code'] == 0
            assert plan(baseline) == plan(altered), 'Unrelated registry row changed source plan'
            prepared = baseline['result']
            if 'tasks' in prepared:
                prepared = prepared['tasks'][0]['source_preflight']
            assert {r['source_url'] for r in prepared['requirements']} == expected
            assert not prepared['metric_executed'] and not prepared['metric_acceptance_proven']
            rows.append({'baseline': baseline, 'unrelated_program_row': altered})
        mixed = execute(['sources', '--company', 'southwest_airlines', '--source-root', str(SOURCE),
                         '--report-end', '2025-12-31', '--metric', 'B01', '--metric', 'B03'])
        assert mixed['exit_code'] == 0
        assert {r['source_url'] for r in mixed['result']['requirements']} >= expected
        rejections = []
        for company, field, value in [('southwest_airlines', 'primary_cik', '1'),
                                       ('pfizer', 'primary_cik', 'invalid')]:
            registry_variant(registry, company, field, value)
            with patch.object(selected, 'ROOT', program), patch.object(ranges, 'ROOT', program):
                start = time.perf_counter()
                try:
                    execute(rows[0]['baseline']['arguments'])
                except ValueError as error:
                    rejection = {'seconds': time.perf_counter() - start,
                                 'exception_type': type(error).__name__, 'reason': str(error)}
                else:
                    raise AssertionError('Invalid registry must reject before source planning')
            expected_reason = ('SELECTED_SOURCE_COMPANY_REGISTRY_CHANGED'
                               if company == 'southwest_airlines'
                               else 'CURRENT_UPDATE_COMPANY_REGISTRY_ROW_INVALID')
            assert rejection['reason'] == expected_reason, rejection
            rejections.append({'constructed_program_registry': [company, field, value], **rejection})
assert before == hashes(), 'Saved source registry or actual request ledger changed'
summary = {'code_root': str(ROOT), 'source_root': str(SOURCE), 'runs': rows,
           'mixed_selection': mixed, 'constructed_rejection_controls': rejections,
           'actual_b03_source_proofs': sorted(expected), 'before': before, 'after': hashes(),
           'new_calls': {'sec': 0, 'provider': 0, 'paid': 0},
           'metric_executed': False, 'business_acceptance': False}
local = ROOT / 'work/source-registry-combination'
local.mkdir(parents=True, exist_ok=True)
(local / 'complete-plans.json').write_text(json.dumps(summary, indent=2) + '\n')


def compact(row):
    result = row['result']
    prepared = result['tasks'][0]['source_preflight'] if 'tasks' in result else result
    return {k: row[k] for k in ('arguments', 'exit_code', 'seconds')} | {
        'status': result['status'], 'metric_executed': result['metric_executed'],
        'metric_acceptance_proven': result['metric_acceptance_proven'],
        'plan_sha256_without_elapsed': hashlib.sha256(
            json.dumps(plan(row), sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'source_urls': sorted(r['source_url'] for r in prepared['requirements'])}


receipt = {k: v for k, v in summary.items() if k not in ('runs', 'mixed_selection')}
receipt['runs'] = [{'baseline': compact(r['baseline']),
                    'unrelated_program_row': compact(r['unrelated_program_row'])} for r in rows]
receipt['mixed_selection'] = compact(mixed)
(OUT / 'combined-sources.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'runs': [{'baseline_seconds': r['baseline']['seconds'],
                          'unrelated_seconds': r['unrelated_program_row']['seconds'],
                          'status': r['baseline']['result']['status']} for r in rows],
                  'mixed_seconds': mixed['seconds'], 'rejection_reasons': [r['reason'] for r in rejections],
                  'exact_b03_source_urls': len(expected), 'source_files_unchanged': True,
                  'new_calls': summary['new_calls']}, indent=2))
