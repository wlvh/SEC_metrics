"""Current saved-source calculation and ordinary records, without old proof chains.

Existing deterministic Spec routes share this record writer. Native Runs keep their own readers.
Sources remain at the supplied root; this record owns only its result and rows.
"""
import fcntl
import json
from pathlib import Path
import subprocess
import time

from sec_http import write_immutable_bytes
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file, strict_json_loads
from .normal_run_inputs import prepare_ordinary_zero_ai_run_input
from .normal_zero_ai_results import SUPPORTED_METRICS
from .normal_run_specs import installed_ordinary_spec_documents
from .records import validate_record

METRIC_IDS = frozenset(installed_ordinary_spec_documents())
LODGING_METRIC_IDS = frozenset({'B10','B11'})
SAVED_METRIC_IDS = METRIC_IDS | LODGING_METRIC_IDS
EXPLICIT_CASE_METRICS = frozenset({'A03','A04','A09','A11','A12','A13','E01'})
CURRENT_E01_SPEC_PATH = 'catalog/r6/E01_content_confirmed_ma_v1.md'


def current_e01_scope(saved):
    """Saved item-code results do not acquire the successor's meaning.

    The existing reader verifies the saved Spec/result relationship; this
    marker is written only for the explicitly selected successor case.
    """
    return saved['manifest'].get('selected_spec_path') == CURRENT_E01_SPEC_PATH


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


def _ordinary_case(source, company, metric):
    program = Path(__file__).resolve().parents[2]
    original = prepare_ordinary_zero_ai_run_input(repo_root=source, company_id=company, metric_id=metric,
        **({'validate_depreciation_scope':True} if metric=='B03' else {}),
        rules_root=program)
    income_binding = original['component'].get('input_binding',{})
    detail = original['component']
    if 'metrics' in detail:
        detail = detail['metrics'][metric]
    selection = detail.get('selection') or {}
    assessments = {}
    if metric == 'B03' and selection.get('depreciation_scope') is not None:
        assessments['depreciation_scope'] = selection['depreciation_scope']
    if selection.get('income_period') is not None:
        assessments['income_period'] = selection['income_period']
    return {'primary_metric_id': metric, 'kind': 'STRUCTURED', 'input_binding': original,
        'compiled_specs': original['compiled_specs'], 'spec_paths': original['spec_paths'],
        'references': original['source_references'], 'source_proofs': original['source_proofs'],
        'admission': original['source_admission'], 'target_period': original['target_period'],
        'expected_records': original['records'], 'results': {metric: original['primary_result']},
        'rules_root':str(program),
        **({'input_assessments':assessments} if assessments else {}),
        'prepared_annual_input': original['component'].get('prepared_input'),
        **({'prepared_income_input':income_binding['current_income_input'],
            'income_observation_checks':income_binding['income_observation_checks']}
           if income_binding.get('current_income_input') is not None else {}),
        'selection': detail.get('selection', detail.get('inspection'))}


def create_saved_result(*, source_root, output_root, company_id, metric_id, shared_input_root=None):
    """Prepare through the existing Calculator and save its actual records."""
    _need(metric_id in SAVED_METRIC_IDS, 'SAVED_RESULT_ROUTE_NOT_IMPLEMENTED')
    def prepare(source):
        if metric_id in LODGING_METRIC_IDS:
            from .normal_lodging_results import prepare_ordinary_lodging_case
            return prepare_ordinary_lodging_case(repo_root=source,company_id=company_id,metric_id=metric_id,
                rules_root=Path(__file__).resolve().parents[2])
        return _ordinary_case(source,company_id,metric_id)
    return _save_case(source_root=source_root, output_root=output_root, company_id=company_id,
        metric_id=metric_id, factory=prepare,
        calculation_performed=True, shared_input_root=shared_input_root)


def save_calculated_case(*, source_root, output_root, company_id, metric_id, case, shared_input_root=None):
    """Persist an already calculated case; do not select sources or calculate again.

    The case's business producer owns extraction and calculation correctness.
    This writer checks records, actual source proofs and Spec/period/unit/trace
    consistency and preserves its original input/result identities. It grants
    no new model execution, source acquisition or business acceptance.
    """
    return _save_case(source_root=source_root, output_root=output_root, company_id=company_id,
        metric_id=metric_id, factory=lambda source: case, calculation_performed=False,
        shared_input_root=shared_input_root)


def _save_case(*, source_root, output_root, company_id, metric_id, factory, calculation_performed, shared_input_root):
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
            case = factory(source_root)
            calculated = time.monotonic()
            _need(case['primary_metric_id'] == metric_id, 'SAVED_CASE_METRIC_CHANGED')
            records, result = case['expected_records'], case['results'][metric_id]
            checked = _validate_records(records, company_id, metric_id, result['result_id'])
            _need(checked == result, 'SAVED_CASE_RESULT_DIFFERS_FROM_RECORD')
            spec, period = case['compiled_specs'][metric_id], case['target_period']
            _need(result['spec_closure_hash'] == spec['spec_closure_hash'], 'SAVED_RESULT_SPEC_CHANGED')
            _need(result['unit'] == spec['compiled']['canonical_unit'] or
                  result['unit'] is None and result['value'] is None, 'SAVED_RESULT_UNIT_CHANGED')
            _need(all(result[k] == period[k] for k in ('period_start', 'period_end')), 'SAVED_RESULT_PERIOD_CHANGED')
            trace = next(r for r in records if r['record_type'] == 'EXECUTION_TRACE' and r['trace_id'] == result['trace_id'])
            _need(trace['metric_id'] == metric_id and trace['spec_closure_hash'] == result['spec_closure_hash']
                  and all(trace['calculation_target'][k] == result[k] for k in
                          ('company_id','period_start','period_end','scope_key')), 'SAVED_CASE_TRACE_TARGET_CHANGED')
            from .specs import compile_spec_files
            from .sources import resolve_repository_file
            actual_specs = compile_spec_files(paths=[resolve_repository_file(repo_root=Path(case.get('rules_root',source_root)),
                repo_relative_path=p) for p in case['spec_paths'].values()])
            _need(all(actual_specs[m]['spec_closure_hash'] == s['spec_closure_hash']
                      for m,s in case['compiled_specs'].items()), 'SAVED_CASE_INSTALLED_SPEC_DIFFERS')
            from .ordinary_source_authority import verify_ordinary_source_proofs
            verify_ordinary_source_proofs(data_root=source_root, proofs=case['source_proofs'])
            input_id = case['input_binding'].get('input_id') or content_hash(value=case['input_binding'])
            identity = content_hash(value={'input_id': input_id, 'result_id': result['result_id']})
            manifest = {'record_type': 'ORDINARY_SAVED_RESULT_V1', 'run_id': 'ordinary:'+identity[7:],
                'status': 'CALCULATED', 'company_id': company_id, 'metric_id': metric_id,
                'target_period': period, 'result_id': result['result_id'],
                'source_root': str(source_root), 'rules_root':case.get('rules_root',str(source_root)), 'source_proofs': case['source_proofs'],
                'source_references': case['references'], 'input_id': input_id,
                'program_root': str(Path(__file__).resolve().parents[2]),
                'program_version': _program_version(Path(__file__).resolve().parents[2]),
                'compiled_specs': case['compiled_specs'],
                'calculation_performed_by_writer': calculation_performed,
                'new_calls': {'provider': 0, 'paid': 0, 'sec': 0}, 'production_authorized': False}
            if metric_id == 'E01' and case['spec_paths'][metric_id] == CURRENT_E01_SPEC_PATH:
                manifest['selected_spec_path'] = CURRENT_E01_SPEC_PATH
            from .ordinary_projection import render_ordinary_records
            rendered = render_ordinary_records(data_root=source_root, manifest=manifest,
                records=records, case=case, receipt_status='CALCULATED_SAVED_SOURCE' if calculation_performed else 'SAVED_PRECALCULATED_CASE',
                source_validation='SOURCE_CALCULATOR_AND_RECORD_CHECKS' if calculation_performed else 'SOURCE_PROOFS_AND_PRECALCULATED_RECORD_CHECKS',
                prepared_annual_input=case.get('prepared_annual_input') or case['input_binding'].get('prepared_input'))
            rows_at = time.monotonic()
            persisted, shared = [], {}
            for record in records:
                if record['record_type'] != 'DERIVED_ASSET' or shared_input_root is None:
                    persisted.append(record)
                    continue
                shared_root = Path(shared_input_root).resolve()
                for protected in (source_root, output_root, Path(__file__).resolve().parents[2]):
                    _need(shared_root != protected and protected not in shared_root.parents
                          and shared_root not in protected.parents, 'SAVED_SHARED_INPUT_ROOT_OVERLAP')
                shared_root.mkdir(parents=True, exist_ok=True)
                raw = _json(record); digest = sha256_bytes(content=raw)
                path = shared_root/(digest+'.json')
                write_immutable_bytes(path=path, content=raw)
                shared[digest] = {'path':str(path),'sha256':digest,'derived_asset_id':record['derived_asset_id']}
                persisted.append({'record_type':'ORDINARY_SHARED_DERIVED_ASSET_REFERENCE', 'sha256':digest})
            if shared:
                manifest['shared_records'] = shared
            files = {**rendered['files'], 'records.jsonl': b''.join(_json(r) for r in persisted),
                     'receipt.json': _json(rendered['receipt'])}
            if case.get('input_assessments'):
                files['input-assessments.json'] = _json({'record_type':'ORDINARY_INPUT_ASSESSMENTS_V1',
                    'company_id':company_id,'metric_id':metric_id,'input_id':input_id,
                    'result_id':result['result_id'],'target_period':period,
                    'assessments':case['input_assessments']})
            for name, raw in files.items():
                write_immutable_bytes(path=output_root/name, content=raw)
            manifest['files'] = {name: sha256_file(path=output_root/name) for name in files}
            manifest['timings_seconds'] = {'prepare_and_calculate' if calculation_performed else 'accept_precalculated_case': format(calculated-started, '.6f'),
                'check_and_project': format(rows_at-calculated, '.6f'), 'save': format(time.monotonic()-rows_at, '.6f')}
            write_immutable_bytes(path=output_root/'manifest.json', content=_json(manifest))
            return {**read_saved_result(output_root=output_root), 'source_admission': case['admission']}
        except Exception as error:
            write_immutable_bytes(path=output_root/'failure.json',
                content=_json({'status': 'FAILED', 'error_type': type(error).__name__, 'error': str(error)}))
            raise


def read_saved_result(*, output_root, shared_record_cache=None):
    """Read saved values and rows, checking ordinary damage without recomputing."""
    root = Path(output_root)
    manifest = strict_json_file(path=root/'manifest.json')
    _need(manifest['record_type'] == 'ORDINARY_SAVED_RESULT_V1'
          and manifest['status'] == 'CALCULATED', 'SAVED_RESULT_NOT_COMPLETE')
    base_files = {'records.jsonl', 'receipt.json','metrics_matrix.csv', 'metric_evidence.csv'}
    _need(base_files <= set(manifest['files'])
          and set(manifest['files'])-base_files <= {'input-assessments.json'}, 'SAVED_RESULT_FILES_MISSING')
    for name, expected in manifest['files'].items():
        _need(sha256_file(path=root/name) == expected, 'SAVED_RESULT_FILE_CHANGED:'+name)
    records = []
    for line in (root/'records.jsonl').read_text().splitlines():
        record = strict_json_loads(text=line)
        if record['record_type'] == 'ORDINARY_SHARED_DERIVED_ASSET_REFERENCE':
            digest = record['sha256']; details = manifest.get('shared_records', {}).get(digest)
            _need(details is not None and details['sha256'] == digest, 'SAVED_SHARED_RECORD_REFERENCE_MISSING')
            path = Path(details['path']); key=(str(path),digest)
            _need(path.is_file(), 'SAVED_SHARED_RECORD_MISSING')
            if shared_record_cache is not None and key in shared_record_cache:
                record = shared_record_cache[key]
            else:
                _need(sha256_file(path=path) == digest, 'SAVED_SHARED_RECORD_CHANGED')
                record = strict_json_file(path=path)
                if shared_record_cache is not None:shared_record_cache[key]=record
            _need(record['record_type'] == 'DERIVED_ASSET' and
                  record['derived_asset_id'] == details['derived_asset_id'], 'SAVED_SHARED_RECORD_ID_CHANGED')
        records.append(record)
    result = _validate_records(records, manifest['company_id'], manifest['metric_id'], manifest['result_id'])
    _need(result['spec_closure_hash'] == manifest['compiled_specs'][manifest['metric_id']]['spec_closure_hash'],
          'SAVED_RESULT_SPEC_CHANGED')
    _need(result['unit'] == manifest['compiled_specs'][manifest['metric_id']]['compiled']['canonical_unit']
          or result['unit'] is None and result['value'] is None,
          'SAVED_RESULT_UNIT_CHANGED')
    _need(all(result[key] == manifest['target_period'][key] for key in ('period_start', 'period_end')),
          'SAVED_RESULT_PERIOD_CHANGED')
    assessment = None
    if 'input-assessments.json' in manifest['files']:
        assessment = strict_json_file(path=root/'input-assessments.json')
        _need(assessment['record_type']=='ORDINARY_INPUT_ASSESSMENTS_V1'
              and all(assessment[k]==manifest[k] for k in
                      ('company_id','metric_id','input_id','result_id','target_period'))
              and type(assessment['assessments']) is dict, 'SAVED_INPUT_ASSESSMENT_COORDINATE_CHANGED')
    return {'manifest': manifest, 'result': result,
            'files': {name: (root/name).read_bytes() for name in ('metrics_matrix.csv', 'metric_evidence.csv')},
            'receipt': strict_json_file(path=root/'receipt.json'),
            **({} if assessment is None else {'input_assessments':assessment['assessments']})}
