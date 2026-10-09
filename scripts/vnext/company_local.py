"""Thin local orchestration; acquisition and compute use different processes."""
from datetime import datetime, timezone
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from .canonical import content_hash, strict_json_file
from .company_handoff import external, locked_company, _atomic_json
from .company_source_authority import need
from .normal_source_authority import ROOT


def absolute(path):
    from git_workspace import first_symlink_in_path
    path = Path(os.path.abspath(os.path.expanduser(str(path))))
    need(first_symlink_in_path(path=path) is None, 'LOCAL_PATH_ALIAS')
    return path


def native_run(manifest):
    """Existing native specs select their existing reader in the local tree.

    Run validation still authenticates the exact spec hash, compiled metric,
    input binding, records and original source. This only selects the reader.
    """
    paths = set(manifest.get('spec_file_hashes', {}))
    return len(paths) == 1 and paths <= {
        'catalog/r5/B13_capacity_disclosures_v1.md',
        'catalog/r5/B13_production_capacity_v1.md',
        'catalog/r6/D04_going_concern_assessment_v1.md'}


def configured_scope(company_id):
    from .normal_annual_input import _registry_rows
    companies = {c['company_id'] for c in _registry_rows(repo_root=ROOT)}
    need(company_id in companies, 'LOCAL_COMPANY_NOT_CONFIGURED')
    metrics = strict_json_file(path=ROOT/'config/source_strategy_registry.json')['metrics']
    need(type(metrics) in (list, dict) and len(metrics) == len(set(metrics)), 'LOCAL_METRIC_SCOPE_INVALID')
    return sorted(metrics)


def _invoke(program, args, *, report_file, environment=None):
    """Archive full child output before interpreting its status."""
    started = time.monotonic()
    process = subprocess.run([sys.executable, str(program/'tools/vnext_company.py'), *map(str, args)],
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', **(environment or {})},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.with_suffix('.stdout.log').write_text(process.stdout)
    report_file.with_suffix('.stderr.log').write_text(process.stderr)
    try:
        parsed = json.loads(process.stdout, parse_float=str)
    except ValueError:
        parsed = {'status': 'STAGE_FAILED', 'reason': process.stderr[-4000:] or process.stdout[-4000:]}
    result = {'returncode': process.returncode, 'elapsed_seconds': format(time.monotonic()-started, '.6f'),
              'command': [str(program/'tools/vnext_company.py'), *map(str, args)],
              'report_file': str(report_file), 'result': parsed}
    _atomic_json(report_file, result)
    return result


def prepare_program(work):
    """Install once and keep each prior program/Run version for native readback."""
    from .company_runtime_install import SUCCESSOR_MODULES
    from .company_retained_local import install_retained_local, RETAINED_MAIN
    from .company_handoff import binding
    configuration = work/'local-company.json'
    if configuration.exists():
        saved = strict_json_file(path=configuration).get('program_root')
        if saved:
            program = absolute(saved)
            need(program.parent == work/'programs' and (program/'requirements/issue_54_v4').is_dir(),
                 'LOCAL_FIXED_PROGRAM_MISSING_OR_CHANGED')
            return program
    paths = ['tools/vnext_company.py','scripts/vnext/company_retained_local.py', *('scripts/vnext/'+m+'.py' for m in SUCCESSOR_MODULES)]
    code = content_hash(value={'retained_main_commit':RETAINED_MAIN,
                               'entry_files':{p:binding(ROOT/p) for p in paths}})[7:]
    program = work/'programs'/code
    if not program.exists():
        staging = program.with_name('.'+code+'-'+uuid4().hex)
        install_retained_local(repo_root=ROOT,output_root=staging)
        # Only the newly installed private program is sealed. Captures, trust,
        # update journals and results live in separate writable directories.
        for path in [*staging.rglob('*'), staging]:
            path.chmod(path.stat().st_mode & ~0o222)
        os.rename(staging, program)
    return program


def configure_task(work, company_id, sec_allowance):
    """Pin one company's allowance and program for acquire and run alike."""
    need(type(sec_allowance) is int and 0 < sec_allowance <= 120, 'LOCAL_SEC_ALLOWANCE_INVALID')
    configuration = work/'local-company.json'
    identity = {'company_id': company_id, 'sec_allowance': sec_allowance}
    saved = {}
    if configuration.exists():
        saved = strict_json_file(path=configuration)
        need(all(saved.get(k) == v for k, v in identity.items()), 'LOCAL_WORK_COMPANY_OR_ALLOWANCE_CHANGED')
    else:
        _atomic_json(configuration, identity)
    program = prepare_program(work)
    from .company_retained_local import RETAINED_MAIN
    compatibility={} if saved.get('program_root') else {'retained_main_commit':RETAINED_MAIN}
    _atomic_json(configuration, {**saved, **identity, **compatibility, 'program_root': str(program)})
    return program


def _status_tables(output, company, rows, summary):
    """Unavailable acquisition still yields an explicit full-scope state table."""
    from .publication import METRIC_FIELDS, EVIDENCE_FIELDS, _csv_bytes
    from .normal_annual_input import _registry_rows
    display = next(c['display_name'] for c in _registry_rows(repo_root=ROOT) if c['company_id'] == company)
    table = output/'metrics_matrix.csv'
    if table.exists():
        reader = csv.DictReader(io.StringIO(table.read_text(encoding='utf-8-sig')))
        fields = reader.fieldnames
        matrix = list(reader)
    else:
        fields, matrix = METRIC_FIELDS, []
    present = {row['metric_id'] for row in matrix}
    matrix.extend({**{f: '' for f in fields}, 'company': display,
            'metric_id': metric, 'status': row['status'], 'notes': row.get('reason', '')}
            for metric, row in rows.items() if metric not in present)
    extras = ('company_id', 'local_run_id', 'local_run_status', 'local_metric_status',
              'requested_in_local_run', 'local_source_status')
    fields = (*fields, *(f for f in extras if f not in fields))
    for row in matrix:
        need(not row.get('company_id') or row['company_id'] == company, 'LOCAL_OUTPUT_WRONG_COMPANY')
        row.update(company_id=company, local_run_id=summary['run_id'], local_run_status=summary['status'],
            local_metric_status=rows[row['metric_id']]['status'],
            requested_in_local_run=row['metric_id'] in summary['selected_metrics'],
            local_source_status=summary.get('source_status', 'ACQUISITION_STAGE_FAILED'))
    table.write_bytes(_csv_bytes(rows=matrix, fieldnames=fields))
    if not (output/'metric_evidence.csv').exists():
        (output/'metric_evidence.csv').write_bytes(_csv_bytes(rows=[], fieldnames=EVIDENCE_FIELDS))


def _export_current(program, work, output, company, key, environment, processing):
    """Existing native readback also serves failed acquisition's old results."""
    destination = work/'result-exports'/key
    args = ['export-results', '--state-root', work/'company-state', '--output-root', destination,
            '--trust-root', work/'trust/company', '--company', company]
    for runtime in sorted((work/'programs').iterdir()):
        if not runtime.name.startswith('.'):
            args.extend(['--runtime-root', runtime])
    for field in ('runtime_root', 'source_runtime'):
        if processing.get(field):
            args.extend(['--runtime-root', absolute(processing[field])])
    if processing.get('trust_root'):
        args.extend(['--processing-trust-root', absolute(processing['trust_root'])])
    controller = strict_json_file(path=work/'local-company.json').get('preparation_program_root')
    exported = _invoke(absolute(controller) if controller else program, args,
        report_file=output/'stages/export-results.json', environment=environment)
    if destination.is_dir():
        import shutil
        for name in ('metrics_matrix.csv', 'metric_evidence.csv', 'company-results.json'):
            shutil.copyfile(destination/name, output/name)
    return exported, destination


def run_local(*, company_id, work_dir, output_dir, period='latest-complete-fy',
              metric_ids=None, max_sec_requests=120, sec_allowance=120, source_root=None,
              fiscal_year_start=None, fiscal_year_end=None):
    """One finite invocation, not a scheduler or authorization to publish."""
    if period == 'fiscal-years':
        return _run_saved_history(company_id=company_id, source_root=source_root,
            work_dir=work_dir, output_dir=output_dir, metric_ids=metric_ids,
            fiscal_year_start=fiscal_year_start, fiscal_year_end=fiscal_year_end)
    need(period == 'latest-complete-fy', 'LOCAL_PERIOD_NOT_IMPLEMENTED')
    need(fiscal_year_start is None and fiscal_year_end is None,
         'LOCAL_HISTORY_ARGUMENTS_REQUIRE_FISCAL_YEARS')
    if source_root is not None:
        from .company_current_records import run_saved_company
        return run_saved_company(company_id=company_id, source_root=source_root,
            work_dir=work_dir, output_dir=output_dir, metric_ids=metric_ids)
    configured = configured_scope(company_id)
    selected = configured if metric_ids is None else list(metric_ids)
    need(selected and len(selected) == len(set(selected)) and set(selected) <= set(configured),
         'LOCAL_METRIC_SCOPE_INVALID')
    from .normal_run_v3 import update_metric_ids
    supported = [m for m in selected if m in update_metric_ids()]
    work, outputs = external(absolute(work_dir)), external(absolute(output_dir))
    need(work != outputs and work not in outputs.parents and outputs not in work.parents,
         'LOCAL_WORK_OUTPUT_OVERLAP')
    need(type(max_sec_requests) is int and 0 <= max_sec_requests <= 120
         and type(sec_allowance) is int and 0 < sec_allowance <= 120, 'LOCAL_SEC_LIMIT_INVALID')
    key = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    output = outputs/key
    output.mkdir(parents=True)
    start = time.monotonic()
    summary = {'record_type': 'LOCAL_COMPANY_RUN_SUMMARY_V1', 'company_id': company_id,
        'run_id': key, 'period_request': period, 'selected_metrics': selected,
        'configured_metrics': configured, 'configured_metric_count': len(configured),
        'output_root': str(output), 'calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'production_authorized': False, 'stages': {},
        'processing': {'saved_d04_configured': False, 'new_provider_paid_calls_authorized': False,
                       'new_local_model_entry': None, 'pending_owner_interfaces': {'B13': 28, 'D03': 28}}}
    rows = {m: {'metric_id': m, 'status': 'NOT_REQUESTED' if m not in selected else 'SOURCE_INPUT_REQUIRED',
                'business_metric_completed': False} for m in configured}
    for metric in set(selected)-set(supported):
        rows[metric].update(status='IMPLEMENTATION_GAP', owner_issue=28,
            reason='No complete ordinary company processing/Run interface is implemented for '+metric)
    with locked_company(work):
        program, processing = None, {}
        try:
            program = configure_task(work, company_id, sec_allowance)
            summary['program_root'] = str(program)
            retained = strict_json_file(path=work/'local-company.json').get('retained_main_commit')
            if retained:summary['retained_native_main_commit']=retained
            # A bounded repair may advance preparation while preserving the
            # original acquisition binding and all existing computing Runs.
            preparation = strict_json_file(path=work/'local-company.json').get('preparation_program_root')
            preparation_program = absolute(preparation) if preparation else program
            if preparation:
                need(preparation_program.parent == work/'programs'
                     and (preparation_program/'requirements/issue_54_v4').is_dir(),
                     'LOCAL_PREPARATION_PROGRAM_MISSING_OR_CHANGED')
            summary['preparation_program_root'] = str(preparation_program)
            common_env = {'SEC_METRICS_ACQUISITION_TRUST_ROOT': str(work/'trust/acquisition'),
                          'SEC_METRICS_SOURCE_TRUST_ROOT': str(work/'trust/company')}
            acquisition = _invoke(program, ['acquire', '--company', company_id,
                '--work-dir', work, '--max-sec-requests', max_sec_requests, '--sec-allowance', sec_allowance],
                report_file=output/'stages/acquire.json', environment=common_env)
            summary['stages']['acquire'] = acquisition
            captured = acquisition['result'].get('result', acquisition['result'])
            summary['calls'] = captured.get('calls', {'provider': 0, 'paid': 0, 'sec': None})
            need(captured.get('record_type') == 'LOCAL_COMPANY_ACQUISITION_V1',
                 'LOCAL_SOURCE_ACQUISITION_STAGE_FAILED')
            summary['source_status'] = captured.get('status')
            summary['source_execution_mode'] = captured.get('execution_mode')
            summary['new_downloads'] = [dict(source_url=c['source_url'], roles=c['roles'],
                status=c['result']['status'], receipt_id=c['result']['receipt']['receipt_id'],
                execution_mode=c['result']['receipt']['execution_mode'])
                for c in captured.get('captures', [])]
            summary['reused_source_urls'] = captured.get('reused_source_urls', [])
            summary['unresolved_source_dependencies'] = captured.get('unresolved', [])
            discovery = captured.get('discovery', {})
            summary['source_discovery'] = {k: discovery.get(k) for k in
                ('company_id', 'status', 'discovery_id', 'limitations') if k in discovery}
            summary['source_discovery']['requirement_count'] = len(discovery.get('requirements', []))
            prepared = discovery.get('prepared_annual_input') or {}
            summary['actual_period'] = prepared.get('table_input', {}).get('target_period')
            summary['filing'] = (discovery.get('metadata_declared_annual_selection') or {}).get('filing')
            source = work/'acquisition/source-inputs'
            package = work/'handoffs'/key
            export_args = ['export', '--source-root', source, '--output-root', package,
                '--trust-root', work/'trust/company', '--company', company_id]
            for metric in supported:
                export_args.extend(['--metric', metric])
            handoff = _invoke(preparation_program, export_args, report_file=output/'stages/handoff.json', environment=common_env)
            summary['stages']['handoff'] = handoff
            need(handoff['returncode'] == 0, 'LOCAL_SOURCE_HANDOFF_FAILED')
            state = work/'company-state'
            install = _invoke(program, ['install', '--package-root', package, '--state-root', state,
                '--trust-root', work/'trust/company', '--company', company_id],
                report_file=output/'stages/install.json', environment=common_env)
            summary['stages']['install'] = install
            need(install['returncode'] == 0, 'LOCAL_SOURCE_INSTALL_FAILED')
            processing = strict_json_file(path=work/'processing.json') if (work/'processing.json').exists() else {}
            summary['processing'] = {'saved_d04_configured': bool(processing),
                'new_provider_paid_calls_authorized': False,
                'new_local_model_entry': None,
                'pending_owner_interfaces': {'B13': 28, 'D03': 28}}
            compute_args = ['compute', '--state-root', state, '--trust-root', work/'trust/company', '--company', company_id]
            for metric in supported:
                compute_args.extend(['--metric', metric])
            for field, option in [('package_root', '--processing-package'), ('runtime_root', '--processing-runtime'),
                ('trust_root', '--processing-trust-root'), ('source_version', '--processing-source-version'),
                ('source_runtime', '--processing-source-runtime'), ('source_trust_root', '--processing-source-trust-root')]:
                if processing.get(field) and 'D04' in selected:
                    compute_args.extend([option, absolute(processing[field])])
            denied = os.pathsep.join(map(str, (ROOT/'evidence', source, work/'trust/acquisition')))
            compute = _invoke(program, compute_args, report_file=output/'stages/compute.json',
                environment={**common_env, 'COMPANY_DENY_READ_ROOTS': denied})
            summary['stages']['compute'] = compute
            executed = compute['result'].get('result', compute['result'])
            for row in executed.get('metrics', []):
                error = (row.get('terminal') or {}).get('error') or {}
                rows[row['metric_id']] = {**row, **({'reason': error.get('reason')}
                    if not row.get('reason') and error.get('reason') else {})}
            exported, destination = _export_current(program, work, output, company_id, key, common_env, processing)
            summary['stages']['export-results'] = exported
            if destination.is_dir():
                summary['native_result_export'] = str(destination)
                summary['source_checkpoint_id'] = strict_json_file(path=destination/'company-results.json').get('source_checkpoint_id')
                summary['result_view'] = [{k: entry.get(k) for k in (
                    'metric_id', 'result_id', 'run_id', 'period', 'period_role', 'measurement_period',
                    'requirement_id', 'requirement_closure_hash', 'source_checkpoint_id',
                    'current_input_matches', 'result_validity', 'replay_status')}
                    for entry in strict_json_file(path=destination/'company-results.json').get('metrics', [])]
            if compute['returncode'] != 0 and not executed.get('metrics'):
                raise ValueError('LOCAL_COMPANY_COMPUTE_FAILED')
        except Exception as error:
            summary['failure'] = {'reason': str(error), 'error_type': type(error).__name__}
            for metric in selected:
                if rows[metric]['status'] == 'SOURCE_INPUT_REQUIRED':
                    rows[metric]['reason'] = str(error)
            # No failed acquisition/import may erase previously readable Runs.
            # Native replay remains mandatory; no old report is blindly merged.
            if program is not None and (work/'company-state/current_source.json').exists() \
                    and not (output/'company-results.json').exists():
                try:
                    preserved, destination = _export_current(program, work, output,
                        company_id, key+'-preserved', common_env, processing)
                    summary['stages']['preserved-results'] = preserved
                    summary['preserved_result_export'] = str(destination)
                except Exception as old_error:
                    summary['preserved_result_error'] = str(old_error)
        # The full authoritative reports live in stages/*.json. Keep the
        # user summary bounded instead of embedding financial source units,
        # update terminal records and all candidate receipts a second time.
        summary['metrics'] = [{k: row[k] for k in (
            'metric_id', 'status', 'reason', 'owner_issue', 'attempt_id',
            'latest_attempt', 'successful_attempt', 'new_candidate_created',
            'business_metric_completed', 'saved_processing_mode', 'native_assessment_completed')
            if k in row} for row in (rows[m] for m in configured)]
        for name, stage in summary['stages'].items():
            full = stage.get('result', {})
            result = full.get('result', full)
            summary['stages'][name] = {**{k: stage[k] for k in (
                'returncode', 'elapsed_seconds', 'command', 'recorded_http_only') if k in stage},
                'status': result.get('status'),
                'report_file': stage.get('report_file', str(output/'stages'/(name+'.json')))}
        summary['flow_completed'] = not summary.get('failure') and (output/'company-results.json').exists()
        limited = summary.get('source_status') != 'SOURCES_READY' or any(
            rows[m]['status'] not in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'} for m in selected)
        limited = limited or any(e.get('replay_status') == 'FAILED' or e.get('result_validity') in {
            'CONFIRMED_INVALID', 'CURRENT_RUNTIME_RELEASE_REQUIRED'} for e in summary.get('result_view', []))
        summary['status'] = ('FLOW_COMPLETED_WITH_LIMITATIONS' if limited else 'FLOW_COMPLETED') \
            if summary['flow_completed'] else 'FLOW_INCOMPLETE'
        summary['all_configured_business_metrics_completed'] = False
        summary['elapsed_seconds'] = format(time.monotonic()-start, '.6f')
        _status_tables(output, company_id, rows, summary)
        summary['outputs'] = {name: str(output/name) for name in ('metrics_matrix.csv', 'metric_evidence.csv', 'run_summary.json')}
        _atomic_json(output/'run_summary.json', summary)
    return summary


def _run_saved_history(*, company_id, source_root, work_dir, output_dir, metric_ids,
                       fiscal_year_start, fiscal_year_end):
    """Select saved issuer years; the shared company controller owns processing.

    Historical acquisition and unsupported families retain their existing
    entry. No source installation or old native-task mutation occurs here.
    """
    need(type(fiscal_year_start) is int and type(fiscal_year_end) is int
         and 1900 <= fiscal_year_start <= fiscal_year_end <= 9998
         and fiscal_year_end-fiscal_year_start < 5, 'COMPANY_HISTORY_FISCAL_RANGE_INVALID')
    need(source_root is not None, 'LOCAL_HISTORY_PREPARED_SOURCE_REQUIRED')
    from .historical_lodging_results import (SUPPORTED_METRICS,
        prepare_historical_lodging_year_case, HISTORICAL_LODGING_PROCESSING_FILES)
    from .historical_statement_cases import (METRICS as statement_metrics,
        prepare_historical_statement_year_case, PROCESSING_FILES as statement_files,
        INCOME_PROCESSING_FILES as income_files)
    from .historical_statement_cases import prepare_historical_current_annual_year_case
    from .historical_liquidity_cases import (METRICS as liquidity_metrics,
        prepare_historical_liquidity_year_case, PROCESSING_FILES as liquidity_files)
    from .historical_event_cases import (METRICS as event_metrics,
        prepare_historical_event_year_case, PROCESSING_FILES as event_files)
    from .historical_capital_cases import (METRICS as capital_metrics,
        prepare_historical_capital_year_case, PROCESSING_FILES as capital_files)
    from .historical_bank_performance_cases import (METRICS as bank_metrics,
        prepare_historical_bank_year_case, PROCESSING_FILES as bank_files)
    selected = configured_scope(company_id) if metric_ids is None else list(metric_ids)
    need(selected and len(selected) == len(set(selected))
         and set(selected) <= set(SUPPORTED_METRICS) | set(statement_metrics) | set(liquidity_metrics) | set(capital_metrics) | set(bank_metrics) | set(event_metrics) | {'B07'},
         'LOCAL_HISTORY_SAVED_FAMILY_NOT_IMPLEMENTED: select received saved families; other history uses its original entry')
    from .company_current_records import run_saved_company
    if not set(selected) <= set(SUPPORTED_METRICS):
        return run_saved_company(company_id=company_id, source_root=source_root,
            work_dir=work_dir, output_dir=output_dir, metric_ids=selected,
            fiscal_years=list(range(fiscal_year_start, fiscal_year_end+1)),
            case_factories={m: (prepare_historical_event_year_case if m in event_metrics else
                               prepare_historical_current_annual_year_case if m == 'B07' else
                               prepare_historical_bank_year_case if m in bank_metrics else
                               prepare_historical_capital_year_case if m in capital_metrics else
                               prepare_historical_liquidity_year_case if m in liquidity_metrics else
                               prepare_historical_lodging_year_case if m in SUPPORTED_METRICS
                               else prepare_historical_statement_year_case) for m in selected},
            processing_files_by_metric={m: (event_files if m in event_metrics else
                                            statement_files if m == 'B07' else
                                            bank_files if m in bank_metrics else
                                            capital_files if m in capital_metrics else
                                            liquidity_files if m in liquidity_metrics else
                                            HISTORICAL_LODGING_PROCESSING_FILES if m in SUPPORTED_METRICS
                                            else income_files if m == 'B01'
                                            else statement_files) for m in selected})
    return run_saved_company(company_id=company_id, source_root=source_root,
        work_dir=work_dir, output_dir=output_dir, metric_ids=selected,
        fiscal_years=list(range(fiscal_year_start, fiscal_year_end+1)),
        case_factory=prepare_historical_lodging_year_case,
        processing_files=HISTORICAL_LODGING_PROCESSING_FILES)
