"""Install B13 native assessments using the existing private source journal.

Only a factory-owned ledger can register input. A data directory cannot enroll
its own response JSON. Portable replay trusts the installed runtime/input pair,
the same boundary as ordinary_source_authority; it grants no new call rights.
"""
from pathlib import Path

from .canonical import canonical_json_bytes, content_hash, strict_json_file, strict_json_loads
from .capacity_utilization_source import need
from .capacity_native_assessment import collect_native_assessments, build_acceptance
from .normal_source_authority import ROOT
from .sources import resolve_repository_file

EXPORT_PATH = 'config/ordinary_capacity_assessment.json'
EXPORT_PATHS = {'B13': EXPORT_PATH, 'D04': 'config/ordinary_going_concern_assessment.json'}


def _metric(source):
    metric = source['metric_id']
    need(metric in EXPORT_PATHS, 'NATIVE_ASSESSMENT_METRIC_UNSUPPORTED')
    return metric


def _journal(mode, metric='B13'):
    need(mode in {'LIVE', 'RECORDED_TEST_ONLY'}, 'B13_ASSESSMENT_MODE_INVALID')
    from .ordinary_source_authority import _journal as existing_journal
    folder = {'B13': 'capacity-assessments', 'D04': 'going-concern-assessments'}[metric]
    path = existing_journal().parent / folder / mode
    from git_workspace import first_symlink_in_path
    need(first_symlink_in_path(path=path) is None, 'B13_ASSESSMENT_JOURNAL_ALIAS')
    path.mkdir(parents=True, exist_ok=True)
    return path


def input_key(source, requirement):
    return content_hash(value={'source_id': source['semantic_source_id'],
                               'requirement_closure_hash': requirement['requirement_closure_hash']})[7:]


def register_assessment_input(*, prepared_requests, ledger, include_source_snapshot=False):
    """Re-read the complete native set before recording creator-owned input."""
    from .continuous_call_ledger import CallLedger, _FACTORY
    from .native_assessment_replay import replay_native_response
    need(type(ledger) is CallLedger and ledger._factory is _FACTORY, 'B13_LEDGER_FACTORY_REQUIRED')
    assessment = collect_native_assessments(prepared_requests=prepared_requests, ledger=ledger)
    need(assessment['all_source_requests_accepted'] and not assessment['failed_requests'],
         'B13_NATIVE_ASSESSMENT_INCOMPLETE')
    source = strict_json_loads(text=prepared_requests[0].source_bytes.decode())
    metric = _metric(source)
    requirement = prepared_requests[0].requirement
    if ledger.live:
        need(ledger.root == Path(requirement['policy']['budget_root']), 'B13_LIVE_LEDGER_ROOT_CHANGED')
    by_id = {strict_json_loads(text=p.request_bytes.decode())['request_id']: p for p in prepared_requests}
    native = []
    with ledger.locked():
        ledger.snapshot()
        for row in assessment['completed']:
            prepared = by_id[row['request_id']]
            path = ledger.root / 'calls' / ('%04d' % row['ordinal'])
            replay = replay_native_response(prepared=prepared, path=path)
            plan, success = replay['plan'], replay['success']
            native.append({'request_id': row['request_id'], 'ordinal': row['ordinal'], 'plan': plan,
                'semantic_request': strict_json_loads(text=prepared.request_bytes.decode()),
                'assistant_output': success['response_body'].decode('utf-8'),
                'acceptance_receipt': success['acceptance_receipt'],
                'intent': strict_json_file(path=path / 'intent.json'),
                'terminal': strict_json_file(path=path / 'terminal.json'),
                'wire': strict_json_file(path=path / 'wire/journal.json'),
                'source_revalidation': replay['revalidation']})
    body = {'record_type': metric + '_REGISTERED_NATIVE_ASSESSMENT_INPUT', 'schema_version': 1,
        'source_id': source['semantic_source_id'], 'company_id': source['company_id'],
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'mode': 'LIVE' if ledger.live else 'RECORDED_TEST_ONLY', 'assessment': assessment,
        'native_requests': native, 'new_call_authority': False, 'production_authorized': False}
    if include_source_snapshot:
        body.update(schema_version=2,source_snapshot=source)
    for field in ('request_context_format', 'response_contract_version','program_quantity_role_contract_version'):
        if field in source:
            body[field] = source[field]
    value = {**body, 'input_record_id': content_hash(value=body)}
    from .ordinary_source_authority import _immutable
    directory = _journal(value['mode'], metric) / input_key(source, requirement)
    need(not directory.is_symlink(), 'B13_ASSESSMENT_JOURNAL_ALIAS')
    directory.mkdir(exist_ok=True)
    _immutable(directory / (value['input_record_id'][7:] + '.json'), value)
    return value


def load_registered_input(*, data_root, source, requirement, mode=None, input_record_id=None, check_export=True):
    """A caller-rehashed packet cannot replace the installed trusted record."""
    key = input_key(source, requirement)
    metric = _metric(source); export_path = EXPORT_PATHS[metric]
    exported = data_root / export_path
    imported = (strict_json_file(path=resolve_repository_file(repo_root=data_root, repo_relative_path=export_path))
                if check_export and exported.exists() else None)
    if mode is None:
        mode = imported['mode'] if imported is not None else 'LIVE'
    if input_record_id is None and imported is not None:
        input_record_id = imported['input_record_id']
    if (ROOT / '.git').exists():
        directory = _journal(mode, metric) / key
        need(not directory.is_symlink(), 'B13_ASSESSMENT_JOURNAL_ALIAS')
        if input_record_id is None:
            choices = list(directory.glob('*.json')) if directory.exists() else []
            need(len(choices) == 1, 'B13_NATIVE_ASSESSMENT_NOT_REGISTERED_OR_AMBIGUOUS')
            path = choices[0]
        else:
            import re
            need(type(input_record_id) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', input_record_id),
                 'B13_ASSESSMENT_INPUT_ID_INVALID')
            path = directory / (input_record_id[7:] + '.json')
        need(path.is_file(), 'B13_NATIVE_ASSESSMENT_NOT_REGISTERED')
        need(not path.is_symlink(), 'B13_ASSESSMENT_JOURNAL_ALIAS')
    else:
        path = resolve_repository_file(repo_root=ROOT, repo_relative_path=export_path)
    value = strict_json_file(path=path)
    need(value.get('program_quantity_role_contract_version')==source.get('program_quantity_role_contract_version'),
         'B13_REGISTERED_PROGRAM_CONTRACT_CHANGED')
    need(value.get('request_context_format') == source.get('request_context_format'),
         'NATIVE_ASSESSMENT_CONTEXT_FORMAT_CHANGED')
    need(value.get('response_contract_version') == source.get('response_contract_version'),
         'NATIVE_ASSESSMENT_RESPONSE_CONTRACT_CHANGED')
    need(value['record_type'] == metric + '_REGISTERED_NATIVE_ASSESSMENT_INPUT'
         and value['schema_version'] in {1,2} and value['source_id'] == source['semantic_source_id']
         and value['company_id'] == source['company_id']
         and value['mode'] == mode and mode in {'LIVE', 'RECORDED_TEST_ONLY'}
         and value['requirement_closure_hash'] == requirement['requirement_closure_hash']
         and (input_record_id is None or value['input_record_id'] == input_record_id)
         and value['input_record_id'] == content_hash(value={k: v for k, v in value.items() if k != 'input_record_id'})
         and value['new_call_authority'] is False and value['production_authorized'] is False,
         'B13_REGISTERED_ASSESSMENT_INPUT_CHANGED')
    if value['schema_version']==2:
        need(value.get('source_snapshot')==source,'NATIVE_REGISTERED_SOURCE_SNAPSHOT_CHANGED')
    else:
        need('source_snapshot' not in value,'NATIVE_REGISTERED_SOURCE_SNAPSHOT_ON_OLD_SCHEMA')
    if check_export and exported.exists():
        need(strict_json_file(path=resolve_repository_file(repo_root=data_root, repo_relative_path=export_path)) == value,
             'B13_IMPORTED_ASSESSMENT_CHANGED')
    from .native_unit_index import reconstruct_requests
    from .continuous_semantic_calls import request_body
    from .continuous_call_policy import configured_transport_policy
    from . import invocation_control as control
    from types import SimpleNamespace
    expected = reconstruct_requests(source, value['assessment'].get('native_request_variants'))
    acceptor = build_acceptance
    if metric == 'D04':
        from .d04_native_assessment import build_acceptance as acceptor
    need([r['request_id'] for r in value['native_requests']] == [r['request_id'] for r in expected]
         and value['assessment']['mode'] == value['mode'], 'B13_NATIVE_INPUT_REQUEST_SET_CHANGED')
    policy = configured_transport_policy(requirement=requirement, repo_root=ROOT)
    source_bytes = canonical_json_bytes(value=source)
    from .canonical import sha256_bytes
    for row, request, summary in zip(value['native_requests'], expected, value['assessment']['completed']):
        need(row['semantic_request'] == request and row['request_id'] == summary['request_id']
             and row['terminal']['terminal_id'] == summary['terminal_id']
             and row['terminal']['status'] == 'SUCCEEDED' and not row['terminal']['stop_reason']
             and row['wire']['mode'] == value['mode'] and not row['wire']['error_class'],
             'B13_NATIVE_INPUT_TERMINAL_CHANGED')
        raw = row['assistant_output'].encode('utf-8')
        need(row['wire']['assistant_output_sha256'] == sha256_bytes(content=raw)
             and row['plan']['provider_request_body_sha256'] == sha256_bytes(content=request_body(request, policy)),
             'B13_NATIVE_INPUT_WIRE_CHANGED')
        need(row['intent']['plan_id'] == row['plan']['ai_invocation_plan_id']
             and row['intent']['requirement_closure_hash'] == row['plan']['requirement_closure_hash']
             and row['terminal']['intent_id'] == row['intent']['intent_id'], 'NATIVE_INPUT_ORIGINAL_PLAN_CHANGED')
        prepared = SimpleNamespace(source_bytes=source_bytes, request_bytes=canonical_json_bytes(value=request),
                                   requirement=requirement)
        acceptance = acceptor(prepared=prepared, plan=row['plan'], response_body=raw)
        if 'source_revalidation' in row:
            from .native_assessment_replay import revalidation_receipt
            checked = revalidation_receipt(prepared=prepared, plan=row['plan'],
                original=row['acceptance_receipt'], expected=acceptance)
            need(row['source_revalidation'] == checked == summary['source_revalidation'],
                 'NATIVE_INPUT_SOURCE_REVALIDATION_CHANGED')
        else:
            need(row['plan']['requirement_closure_hash'] == requirement['requirement_closure_hash']
                 and all(row['acceptance_receipt'][k] == v for k, v in acceptance.items()),
                 'B13_NATIVE_INPUT_EVIDENCE_CHANGED')
        need(acceptance['candidate_record'] == summary['candidate']
             and acceptance['evidence_record'] == summary['evidence'], 'B13_NATIVE_INPUT_EVIDENCE_CHANGED')
        control._validate_acceptance_receipt(value=row['acceptance_receipt'], plan=row['plan'], response_body=raw)
    need(len(value['native_requests']) == len(value['assessment']['completed']), 'B13_NATIVE_INPUT_SUMMARY_SET_CHANGED')
    return value
