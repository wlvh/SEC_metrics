"""Replay existing company references and aggregate native projected CSVs."""
import base64
import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

from .canonical import canonical_json_bytes, strict_json_file
from .company_handoff import binding, external, locked_company, recover_import
from .company_result_view import build_company_view, recover_for_read
from .company_source_authority import need

VIEW_FIELDS = ('company_id', 'run_id', 'result_id', 'requirement_id', 'requirement_closure_hash',
               'source_checkpoint_id', 'last_checked_source_checkpoint_id', 'current_source_checkpoint_id',
               'original_source_checkpoint_id', 'current_source_equivalence_id', 'current_input_matches',
               'current_input_status', 'result_validity', 'latest_attempt_status', 'latest_request_status',
               'requested_in_latest_execution', 'source_credit', 'saved_processing_mode', 'native_path',
               'period_role', 'archive_period_start', 'archive_period_end', 'archive_fiscal_year',
               'measurement_period_start', 'measurement_period_end', 'measurement_period_status', 'defect_holds')


def replay_candidate(entry, runtime_roots):
    """No cross-tree imports: a new process verifies the exact creator closure."""
    from .normal_source_authority import ROOT
    roots = [Path(p) for p in runtime_roots] if runtime_roots else [ROOT]
    if entry.get('runtime_root'):
        hinted = Path(entry['runtime_root'])
        if hinted in roots: roots = [hinted, *(p for p in roots if p != hinted)]
    worker = Path(__file__).with_name('company_result_read.py')
    failures = []
    for runtime in roots:
        from git_workspace import first_symlink_in_path
        need(runtime.is_absolute() and first_symlink_in_path(path=runtime) is None,
             'COMPANY_RESULT_RUNTIME_PATH_ALIAS')
        runtime = runtime.resolve()
        if not (runtime/'requirements'/entry['requirement_id']).is_dir(): continue
        if entry['row_layout'] == 'processing':
            from .company_processing import authenticate_processing, verify_saved_equivalence, worker
            work = Path(entry['rows_root']).parent
            try:
                authenticate_processing(packet_root=work/'processing',program_root=runtime,company_id=entry['company_id'])
                verify_saved_equivalence(program_root=runtime, packet_root=work/'processing', work=work,
                                         runtime_roots=roots)
                result = worker('replay',runtime,work/'processing',work/'data',work)
                return {name:base64.b64decode(raw,validate=True) for name,raw in result.items()}, str(runtime)
            except Exception as error:
                failures.append(str(error)); continue
        run = subprocess.run([sys.executable, '-B', str(worker), str(runtime),
            str(Path(entry['rows_root']).parent), entry['metric_id'], entry['row_layout']],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        if run.returncode == 0:
            import json
            return {name: base64.b64decode(raw, validate=True) for name, raw in json.loads(run.stdout).items()}, str(runtime)
        failures.append(run.stderr.strip().splitlines()[-1] if run.stderr.strip() else 'WORKER_FAILED')
    raise ValueError('COMPANY_RESULT_REPLAY_FAILED: '+('; '.join(failures) or 'EXACT_FIXED_RUNTIME_REQUIRED'))


def _rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))


def export_results(*, state_root, output_root, company_id, runtime_roots=(), defects_file=None):
    output = external(output_root)
    need(not output.exists(), 'COMPANY_RESULT_EXPORT_OUTPUT_EXISTS')
    with locked_company(state_root) as root:
        current = recover_for_read(root, runtime_roots)
        need(current and current['company_id'] == company_id, 'COMPANY_RESULT_EXPORT_WRONG_COMPANY')
        need(root not in output.parents and output not in root.parents, 'COMPANY_RESULT_EXPORT_STATE_OVERLAP')
        registry = strict_json_file(path=Path(defects_file)) if defects_file else None
        view = build_company_view(root=root, company_id=company_id, current=current, defect_registry=registry)
        staged = output.parent/('.'+output.name+'.preparing-'+uuid4().hex)
        staged.mkdir(parents=True)
        try:
            native = []; metric_rows = []; evidence_rows = []
            from .csv_output import _csv_bytes, METRIC_FIELDS, EVIDENCE_FIELDS
            for entry in view['metrics']:
                if not entry.get('run_id'):
                    period = entry.get('period_request') or {}
                    metric_rows.append({'company_id':company_id,'metric_id':entry['metric_id'],
                        'period_end':period.get('report_end'),'fiscal_year':period.get('fiscal_year'),
                        'status':entry['latest_attempt_status'],'notes':entry.get('reason'),
                        **{k:entry.get(k) for k in VIEW_FIELDS}})
                    continue
                rows = Path(entry['rows_root']); work = rows.parent
                try:
                    expected, runtime = replay_candidate(entry, runtime_roots)
                    directory = rows if entry['row_layout'] == 'historical' else rows/entry['metric_id']
                    for name, raw in expected.items():
                        need((directory/name).read_bytes() == raw, 'COMPANY_RESULT_ROWS_CHANGED:'+name)
                    need(not any(p.is_symlink() for p in work.rglob('*')), 'COMPANY_RESULT_NATIVE_INPUT_ALIAS')
                    destination = staged/'native'/entry['metric_id']/work.name
                    shutil.copytree(work, destination)
                    entry['native_path'] = destination.relative_to(staged).as_posix()
                    entry['replay_status'] = 'PASSED'; entry['runtime_root'] = runtime
                    projected = _rows(expected['metrics_matrix.csv'])
                    need(len(projected) == 1, 'COMPANY_RESULT_PROJECTED_ROW_SET_CHANGED')
                    entry['measurement_period'] = {k: projected[0].get(k) for k in ('period_start', 'period_end')}
                    entry['measurement_period_status'] = 'NATIVE_REPLAY_VERIFIED'
                    held = entry['result_validity'] in {'CONFIRMED_INVALID', 'CURRENT_RUNTIME_RELEASE_REQUIRED'}
                    if not held: entry['result_validity'] = 'REPLAY_VERIFIED_CONTENT_NOT_ACCEPTED'
                    entry.update(archive_period_start=entry['period'].get('period_start'),
                                 archive_period_end=entry['period'].get('period_end'),
                                 archive_fiscal_year=entry['period'].get('fiscal_year'))
                    measurement = entry.get('measurement_period') or {}
                    entry.update(measurement_period_start=measurement.get('period_start'),
                                 measurement_period_end=measurement.get('period_end'))
                    metadata = {k: entry.get(k) for k in VIEW_FIELDS}
                    metadata['defect_holds'] = canonical_json_bytes(value=entry.get('defect_holds', [])).decode().strip()
                    for row in projected:
                        need(row['metric_id'] == entry['metric_id'] and row['period_end'] == entry['period']['period_end'],
                             'COMPANY_RESULT_PROJECTED_COORDINATE_CHANGED')
                        if held:
                            row = {**row, 'value': '', 'status': 'WITHHELD',
                                   'notes': row.get('notes', '')+'; '+entry['result_validity']+':'+','.join(entry['confirmed_defects'])}
                        metric_rows.append({**row, **metadata})
                    evidence_rows.extend({**row, **metadata} for row in _rows(expected['metric_evidence.csv']))
                    native.append({k: entry.get(k) for k in ('metric_id', 'period', 'attempt_id', 'run_id',
                                  'requirement_id', 'requirement_closure_hash', 'native_path', 'result_validity')})
                except Exception as error:
                    entry.update(replay_status='FAILED', result_validity='REPLAY_FAILED', reason=str(error))
                    metric_rows.append({'company_id': company_id, 'metric_id': entry['metric_id'],
                        **entry['period'], **{k: entry.get(k) for k in VIEW_FIELDS},
                        'status': 'WITHHELD', 'notes': str(error)})
            metric_fields = (*METRIC_FIELDS, *VIEW_FIELDS); evidence_fields = (*EVIDENCE_FIELDS, *VIEW_FIELDS)
            metric_rows = [{k: row.get(k, '') for k in metric_fields} for row in metric_rows]
            evidence_rows = [{k: row.get(k, '') for k in evidence_fields} for row in evidence_rows]
            (staged/'metrics_matrix.csv').write_bytes(_csv_bytes(rows=metric_rows, fieldnames=metric_fields))
            (staged/'metric_evidence.csv').write_bytes(_csv_bytes(rows=evidence_rows, fieldnames=evidence_fields))
            (staged/'company-results.json').write_bytes(canonical_json_bytes(value=view))
            for name in ('latest-execution.json', 'latest_import.json'):
                if (root/name).is_file(): shutil.copyfile(root/name, staged/name)
            files = {p.relative_to(staged).as_posix(): binding(p) for p in sorted(staged.rglob('*')) if p.is_file()}
            index = {'record_type': 'COMPANY_RESULT_EXPORT_V2', 'company_id': company_id,
                     'current_source_checkpoint_id': current['checkpoint_id'], 'native_candidates': native,
                     'files': files, 'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0}, 'production_authorized': False}
            (staged/'export.json').write_bytes(canonical_json_bytes(value=index))
            os.rename(staged, output)
        except Exception:
            shutil.rmtree(staged)
            raise
        failed = [e for e in view['metrics'] if e.get('replay_status') == 'FAILED']
        return {'status': 'EXPORTED_PARTIAL' if failed else 'EXPORTED', 'company_id': company_id,
                'output_root': str(output), 'native_candidates': native, 'failed_candidates': failed,
                'bytes': sum(v['size'] for v in files.values())}
