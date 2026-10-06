"""Current saved-source calculation and ordinary records, without old proof chains.

The first integrated route is B01. Existing native Runs keep their own readers.
Sources remain at the supplied root; this record owns only its result and rows.
"""
import fcntl
import json
from pathlib import Path
import subprocess
import time

from sec_http import write_immutable_bytes
from .canonical import content_hash, sha256_file, strict_json_file, strict_json_loads
from .normal_run_inputs import prepare_ordinary_zero_ai_run_input
from .records import validate_record

METRIC_IDS = frozenset({'B01'})


def _program_version(root):
    """Version information for diagnosis, never a clean-tree admission gate."""
    def git(*args):
        completed = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
        return completed.stdout.strip() if completed.returncode == 0 else None
    return {'commit': git('rev-parse', 'HEAD'),
            'has_uncommitted_changes': bool(git('status', '--porcelain'))}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _json(value):
    # Evidence strings retain their original Unicode representation.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()


def _validate_records(records, company_id, metric_id, result_id):
    for record in records:
        validate_record(record=record)
    results = [r for r in records if r['record_type'] == 'METRIC_RESULT'
               and r['metric_id'] == metric_id]
    _need(len(results) == 1 and results[0]['company_id'] == company_id
          and results[0]['result_id'] == result_id, 'SAVED_RESULT_COORDINATE_CHANGED')
    traces = [r for r in records if r['record_type'] == 'EXECUTION_TRACE'
              and r['trace_id'] == results[0]['trace_id']]
    _need(len(traces) == 1, 'SAVED_RESULT_TRACE_MISSING')
    return results[0]


def create_saved_result(*, source_root, output_root, company_id, metric_id):
    """Calculate through the existing source/Calculator, then commit a small record."""
    _need(metric_id in METRIC_IDS, 'SAVED_RESULT_ROUTE_NOT_IMPLEMENTED')
    source_root, output_root = Path(source_root).resolve(), Path(output_root).resolve()
    _need(source_root.is_dir() and source_root != output_root
          and source_root not in output_root.parents and output_root not in source_root.parents,
          'SAVED_RESULT_SOURCE_OUTPUT_OVERLAP_OR_MISSING')
    _need(not output_root.exists(), 'SAVED_RESULT_OUTPUT_EXISTS')
    output_root.mkdir(parents=True)
    with (output_root/'write.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.monotonic()
        try:
            original = prepare_ordinary_zero_ai_run_input(repo_root=source_root,
                company_id=company_id, metric_id=metric_id)
            calculated = time.monotonic()
            records, result = original['records'], original['primary_result']
            _validate_records(records, company_id, metric_id, result['result_id'])
            from .ordinary_source_authority import verify_ordinary_source_proofs
            verify_ordinary_source_proofs(data_root=source_root, proofs=original['source_proofs'])
            detail = original['component']
            case = {'primary_metric_id': metric_id, 'kind': 'STRUCTURED',
                'input_binding': original, 'compiled_specs': original['compiled_specs'],
                'spec_paths': original['spec_paths'], 'references': original['source_references'],
                'admission': original['source_admission'],
                'selection': detail.get('selection', detail.get('inspection'))}
            identity = content_hash(value={'input_id': original['input_id'],
                'result_id': result['result_id']})
            manifest = {'record_type': 'ORDINARY_SAVED_RESULT_V1', 'run_id': 'ordinary:'+identity[7:],
                'status': 'CALCULATED', 'company_id': company_id, 'metric_id': metric_id,
                'target_period': original['target_period'], 'result_id': result['result_id'],
                'source_root': str(source_root), 'source_proofs': original['source_proofs'],
                'source_references': original['source_references'],
                'input_id': original['input_id'], 'program_root': str(Path(__file__).resolve().parents[2]),
                'program_version': _program_version(Path(__file__).resolve().parents[2]),
                'compiled_specs': original['compiled_specs'],
                'new_calls': {'provider': 0, 'paid': 0, 'sec': 0}, 'production_authorized': False}
            from .ordinary_projection import render_ordinary_records
            rendered = render_ordinary_records(data_root=source_root, manifest=manifest,
                records=records, case=case, receipt_status='CALCULATED_SAVED_SOURCE',
                source_validation='SOURCE_CALCULATOR_AND_RECORD_CHECKS')
            rows_at = time.monotonic()
            files = {**rendered['files'], 'records.jsonl': b''.join(_json(r) for r in records),
                     'receipt.json': _json(rendered['receipt'])}
            for name, raw in files.items():
                write_immutable_bytes(path=output_root/name, content=raw)
            manifest['files'] = {name: sha256_file(path=output_root/name) for name in files}
            manifest['timings_seconds'] = {'prepare_and_calculate': format(calculated-started, '.6f'),
                'check_and_project': format(rows_at-calculated, '.6f'),
                'save': format(time.monotonic()-rows_at, '.6f')}
            # Completion is written last; interruption cannot advertise success.
            write_immutable_bytes(path=output_root/'manifest.json', content=_json(manifest))
            return {**read_saved_result(output_root=output_root), 'source_admission': original['source_admission']}
        except Exception as error:
            write_immutable_bytes(path=output_root/'failure.json',
                content=_json({'status': 'FAILED', 'error_type': type(error).__name__, 'error': str(error)}))
            raise


def read_saved_result(*, output_root):
    """Read saved values and rows, checking ordinary damage without recomputing."""
    root = Path(output_root)
    manifest = strict_json_file(path=root/'manifest.json')
    _need(manifest['record_type'] == 'ORDINARY_SAVED_RESULT_V1'
          and manifest['status'] == 'CALCULATED', 'SAVED_RESULT_NOT_COMPLETE')
    _need(set(manifest['files']) == {'records.jsonl', 'receipt.json',
          'metrics_matrix.csv', 'metric_evidence.csv'}, 'SAVED_RESULT_FILES_MISSING')
    for name, expected in manifest['files'].items():
        _need(sha256_file(path=root/name) == expected, 'SAVED_RESULT_FILE_CHANGED:'+name)
    records = [strict_json_loads(text=line) for line in (root/'records.jsonl').read_text().splitlines()]
    result = _validate_records(records, manifest['company_id'], manifest['metric_id'], manifest['result_id'])
    _need(result['spec_closure_hash'] == manifest['compiled_specs'][manifest['metric_id']]['spec_closure_hash'],
          'SAVED_RESULT_SPEC_CHANGED')
    _need(result['unit'] == manifest['compiled_specs'][manifest['metric_id']]['compiled']['canonical_unit'],
          'SAVED_RESULT_UNIT_CHANGED')
    _need(all(result[key] == manifest['target_period'][key] for key in ('period_start', 'period_end')),
          'SAVED_RESULT_PERIOD_CHANGED')
    return {'manifest': manifest, 'result': result,
            'files': {name: (root/name).read_bytes() for name in ('metrics_matrix.csv', 'metric_evidence.csv')},
            'receipt': strict_json_file(path=root/'receipt.json')}
