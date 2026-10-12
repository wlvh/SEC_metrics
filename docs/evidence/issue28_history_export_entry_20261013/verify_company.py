"""Real saved Marriott source -> public export -> ordinary company run/read.

No network is permitted. Outputs must be fresh external directories; originals,
prior tasks, model responses and the paid/SEC ledger are never written.
"""
import argparse
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from tools.vnext_company import main
from vnext import ordinary_saved_result


def invoke(args):
    start = time.monotonic()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('No live HTTP/provider')), \
         contextlib.redirect_stdout(io.StringIO()) as stream:
        code = main(args)
    return code, json.loads(stream.getvalue()), time.monotonic()-start


def files(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def verify(source, work, package=None):
    work.mkdir(parents=True, exist_ok=False)
    original_log = (source/'evidence/requests_log.csv').read_bytes()
    export_args = ['export', '--company', 'marriott_international', '--metric', 'B01',
        '--source-root', str(source), '--output-root', str(work/'package'),
        '--trust-root', str(work/'unused-legacy-trust'), '--history-years', '5']
    if package is None:
        code, exported, export_time = invoke(export_args)
        assert code == 0 and exported['status'] == 'EXPORTED', exported
        package = work/'package'
    else:
        exported = json.loads((package/'company-source-package.json').read_text())
        export_time = None
    assert exported['source_discovery']['fiscal_range']['fiscal_years'] == [2021, 2022, 2023, 2024, 2025]
    assert (package/'evidence/requests_log.csv').read_bytes() == original_log
    assert not (work/'unused-legacy-trust').exists()
    assert not (package/'config/ordinary_source_checkpoint.json').exists()
    for relative in exported['files']:
        assert (package/relative).read_bytes() == (source/relative).read_bytes(), relative
    run_args = ['run', '--company', 'marriott_international', '--metric', 'B01',
        '--period', 'fiscal-years', '--fiscal-year-start', '2025', '--fiscal-year-end', '2025',
        '--source-root', str(package), '--work-dir', str(work/'task'),
        '--output-dir', str(work/'first')]
    first_code, first, first_time = invoke(run_args)
    assert first_code == 0, first
    before = {k: v for k, v in files(work/'task').items() if '/results/' in k}
    repeat_args = run_args[:-1]+[str(work/'repeat')]
    with patch.object(ordinary_saved_result, '_ordinary_case', side_effect=AssertionError('Repeat must not calculate')):
        repeat_code, repeat, repeat_time = invoke(repeat_args)
    assert repeat_code == 0, repeat
    assert {k: v for k, v in files(work/'task').items() if '/results/' in k} == before
    after_repeat = files(work/'task')
    read_start = time.monotonic()
    child = subprocess.run([sys.executable, str(ROOT/'tools/vnext_company.py'), 'results',
        '--company', 'marriott_international', '--state-root', str(work/'task'),
        '--output-root', str(work/'read')], capture_output=True, text=True, check=True)
    read_time = time.monotonic()-read_start
    read = json.loads(child.stdout)
    with (work/'read/metrics_matrix.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    row = next(r for r in rows if r['metric_id'] == 'B01')
    assert row['value'] == '26186000000' and row['unit'] == 'USD', row
    assert row['fiscal_year'] == '2025' and row['period_end'] == '2025-12-31', row
    assert files(work/'task') == after_repeat
    assert (source/'evidence/requests_log.csv').read_bytes() == original_log
    summary = {'program_root': str(ROOT), 'source_root': str(source), 'work_root': str(work),
        'export': {'status': exported['status'], 'package_id': exported['package_id'],
            'fiscal_years': exported['source_discovery']['fiscal_range']['fiscal_years'],
            'files': len(exported['files']), 'bytes': sum(v['size'] for v in exported['files'].values()),
            'elapsed_seconds': export_time, 'copied_originals_match': True,
            'ledger_unchanged': True, 'ai_processing_state': exported['ai_processing_state']},
        'first': {'status': first['status'], 'elapsed_seconds': first_time},
        'repeat': {'status': repeat['status'], 'elapsed_seconds': repeat_time,
            'calculation_forbidden': True, 'result_files_unchanged': True,
            'new_check_observation_allowed': True},
        'independent_read': {'elapsed_seconds': read_time, 'row': row},
        'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'limits': ['Only B01 FY2025 computed here; export readiness is not acceptance of all five years.',
                   'Saved HTTP sources, not a new online acquisition; no model output included.',
                   'Ordinary run --source-root package; retained native install/compute is unchanged.']}
    (work/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--package-root', type=Path,
                        help='Reuse the already exported exact package; do not re-export large originals')
    args = parser.parse_args()
    print(json.dumps(verify(args.source_root.resolve(), args.work_root.resolve(),
        args.package_root.resolve() if args.package_root else None), ensure_ascii=False, indent=2))
