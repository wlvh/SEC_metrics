"""Read original historical D04 calls without a caller, ledger or new authority.

This explicit input adapter reads an existing package. It preserves the old
intent/plan/terminal identity and rechecks the original response with the
current D04 acceptor. It cannot execute a provider request or create a Result.
"""
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
import tarfile

from .canonical import content_hash, sha256_bytes, strict_json_loads
from .capacity_utilization_source import need
from .d04_native_assessment import build_acceptance, CURRENT_KINDS
from .native_unit_index import validate_request_partition
from . import invocation_control as control


def _identity(value, field):
    need(value.get(field) == content_hash(value={k: v for k, v in value.items()
                                               if k != field}),
         'SAVED_D04_ORIGINAL_IDENTITY_CHANGED:' + field)


def _coordinate(annual):
    period = annual['table_input']['target_period']
    return (annual['company_id'], str(int(annual['entity'])),
            annual['filing']['accessionNumber'],
            *(period[k] for k in ('fiscal_year', 'period_start', 'period_end')))


def read_saved_d04_assessment(*, saved_call_package, original_source,
                             original_call_members, prepared_annual_input):
    """Read a complete original call group at its explicitly selected coordinate.

    Annual discovery/source admission and whole-company acceptance belong to
    the selected-source producer. This function gives neither fresh-source nor
    media/absence credit. It requires exact original source/request bytes and
    every original response; missing/failed calls are not empty findings.
    """
    need(original_source.get('record_type') == 'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE'
         and original_source.get('metric_id') == 'D04',
         'SAVED_D04_NATIVE_SOURCE_REQUIRED')
    _identity(original_source, 'semantic_source_id')
    need(_coordinate(original_source['prepared_annual_input'])
         == _coordinate(prepared_annual_input), 'SAVED_D04_SELECTED_COORDINATE_CHANGED')
    need(bool(original_call_members), 'SAVED_D04_ORIGINAL_CALL_GROUP_REQUIRED')
    requests, completed = [], []
    with tarfile.open(Path(saved_call_package), 'r:gz') as archive:
        members = {}
        for member in archive.getmembers():
            need(member.name not in members, 'SAVED_D04_DUPLICATE_PACKAGE_MEMBER')
            members[member.name] = member

        def read(name):
            path = PurePosixPath(name)
            need(not path.is_absolute() and '..' not in path.parts
                 and str(path) == name and name in members
                 and members[name].isfile(), 'SAVED_D04_PACKAGE_MEMBER_UNAVAILABLE:' + name)
            return archive.extractfile(members[name]).read()

        def json(name):
            return strict_json_loads(text=read(name).decode('utf-8'))

        binding = json('root/binding.json')
        _identity(binding, 'binding_id')
        need(binding['record_type'] == 'ISSUE_47_HISTORICAL_MODEL_ALLOWANCE',
             'SAVED_D04_ORIGINAL_BINDING_TYPE_UNSUPPORTED')
        seen = set()
        for call in original_call_members:
            ordinal = call['ordinal']
            need(type(ordinal) is int and ordinal > 0 and ordinal not in seen,
                 'SAVED_D04_DUPLICATE_OR_INVALID_ORDINAL')
            seen.add(ordinal)
            root = 'root/calls/' + f'{ordinal:04d}'
            need(call['source_member'] == root + '/source.json'
                 and call['request_member'] == root + '/semantic-request.json',
                 'SAVED_D04_ORIGINAL_MEMBER_COORDINATE_CHANGED')
            source_bytes, request_bytes = read(call['source_member']), read(call['request_member'])
            need(strict_json_loads(text=source_bytes.decode('utf-8')) == original_source,
                 'SAVED_D04_ORIGINAL_SOURCE_CHANGED')
            request = strict_json_loads(text=request_bytes.decode('utf-8'))
            requests.append(request)
            intent = json(root + '/intent.json')
            terminal = json(root + '/terminal.json')
            _identity(intent, 'intent_id'); _identity(terminal, 'terminal_id')
            need(intent['record_type'] == 'ISSUE_47_HISTORICAL_MODEL_CALL_INTENT'
                 and intent['ordinal'] == ordinal
                 and intent['allowance_binding_id'] == binding['binding_id']
                 and intent['purpose'] in binding['purposes']
                 and intent['automatic_retry_count'] == 0
                 and intent['execution_mode'] == binding['execution_mode']
                 and terminal['record_type'] == 'ISSUE_47_HISTORICAL_MODEL_CALL_TERMINAL'
                 and terminal['intent_id'] == intent['intent_id']
                 and terminal['status'] == 'SUCCEEDED' and not terminal['stop_reason'],
                 'SAVED_D04_ORIGINAL_CALL_NOT_SUCCESSFUL')
            for name, expected in terminal['evidence'].items():
                need(sha256_bytes(content=read(root + '/' + name)) == expected,
                     'SAVED_D04_ORIGINAL_CALL_BYTES_CHANGED:' + name)
            plan = json(root + '/invocation_control/plans/' + intent['plan_id'][7:] + '.json')
            _identity(plan, 'ai_invocation_plan_id')
            need(plan['ai_invocation_plan_id'] == intent['plan_id']
                 and plan['requirement_id'] == intent['requirement_id']
                 and plan['source_identity_hash'] == original_source['semantic_source_id']
                 and plan['selected_representation_hash'] == request['request_id']
                 and plan['output_schema_hash'] == content_hash(value=request['response_protocol']),
                 'SAVED_D04_ORIGINAL_PLAN_BINDING_CHANGED')
            key = intent['request_identity'][7:]
            wire_request = read(root + '/invocation_control/requests/' + key + '.bin')
            wire_hash = sha256_bytes(content=wire_request)
            need(intent['request_digest'] == 'sha256:' + wire_hash
                 and wire_hash == plan['provider_request_body_sha256'],
                 'SAVED_D04_ORIGINAL_WIRE_CHANGED')
            need(plan['provider_request_identity'] == intent['request_identity']
                 == content_hash(value={'provider_request_body_sha256': wire_hash,
                     'provider': plan['provider'], 'model': plan['model'], 'api': plan['api']}),
                 'SAVED_D04_ORIGINAL_PROVIDER_IDENTITY_CHANGED')
            payload = strict_json_loads(text=wire_request.decode('utf-8'))
            expected_payload = {k: v for k, v in request.items() if k not in {
                'system_prompt', 'provider_request_sent', 'provider_tokens_measured', 'production_authorized'}}
            need(payload['model'] == plan['model']
                 and payload['messages'][0] == {'role': 'system', 'content': request['system_prompt']}
                 and len(payload['messages']) == 2 and payload['messages'][1]['role'] == 'user'
                 and strict_json_loads(text=payload['messages'][1]['content']) == expected_payload,
                 'SAVED_D04_ORIGINAL_REQUEST_PAYLOAD_CHANGED')
            response = read(root + '/invocation_control/responses/' + key + '/response.bin')
            success = json(root + '/invocation_control/responses/' + key + '/receipt.json')
            _identity(success, 'success_response_receipt_id')
            need(success['ai_invocation_plan_id'] == plan['ai_invocation_plan_id']
                 and success['provider_request_identity'] == intent['request_identity']
                 and success['provider_request_body_sha256'] == plan['provider_request_body_sha256']
                 and success['response_body_sha256'] == sha256_bytes(content=response)
                 and success['response_body_size'] == len(response),
                 'SAVED_D04_ORIGINAL_RESPONSE_BINDING_CHANGED')
            execution_paths = [p for p in terminal['evidence']
                if p.startswith('invocation_control/executions/') and p.endswith('.json')]
            need(len(execution_paths) == 1, 'SAVED_D04_ORIGINAL_EXECUTION_REQUIRED')
            execution = json(root + '/' + execution_paths[0])
            _identity(execution, 'execution_receipt_id')
            need(execution['execution_receipt_id'] == terminal['execution_receipt_id']
                 and execution['ai_invocation_plan_id'] == plan['ai_invocation_plan_id']
                 and execution['provider_request_identity'] == intent['request_identity']
                 and execution['status'] == 'SUCCEEDED'
                 and execution['success_response_receipt_id'] == success['success_response_receipt_id'],
                 'SAVED_D04_ORIGINAL_EXECUTION_BINDING_CHANGED')
            acceptance = json(root + '/invocation_control/acceptances/' + key + '/receipt.json')
            validated = control._validate_acceptance_receipt(value=acceptance, plan=plan,
                                                            response_body=response)
            need(validated['acceptance_receipt_id'] == success['acceptance_receipt_id'],
                 'SAVED_D04_ORIGINAL_ACCEPTANCE_CHANGED')
            current = build_acceptance(prepared=SimpleNamespace(source_bytes=source_bytes,
                request_bytes=request_bytes), plan=plan, response_body=response)
            need(all(acceptance.get(k) == v for k, v in current.items()
                     if k != 'validator_semantic_hash'), 'SAVED_D04_CURRENT_SEMANTICS_CHANGED')
            completed.append({'request_id': request['request_id'], 'ordinal': ordinal,
                'terminal_id': terminal['terminal_id'],
                'acceptance_receipt_id': acceptance['acceptance_receipt_id'],
                'candidate': acceptance['candidate_record'], 'evidence': acceptance['evidence_record'],
                'original_counts': terminal['counts'], 'original_usage': success['usage'],
                'original_requirement_id': plan['requirement_id'],
                'original_requirement_closure_hash': plan['requirement_closure_hash'],
                'current_validator_semantic_hash': current['validator_semantic_hash']})
        variants = validate_request_partition(original_source, requests)
    findings = [f for row in completed for f in row['candidate']['selected']['source_assessment']['findings']]
    kinds = {f['kind'] for f in findings if f['subject'] == 'TARGET_REGISTRANT'
             and f['timing'] == 'CURRENT_REPORT' and f['kind'] in CURRENT_KINDS}
    branch = ('CROSS_REQUEST_GOING_CONCERN_RECONCILIATION_REQUIRED' if len(kinds) > 1 else
              'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW' if kinds else
              'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW')
    body = {'record_type': 'D04_NATIVE_SOURCE_ASSESSMENT_SET',
        'source_id': original_source['semantic_source_id'], 'company_id': original_source['company_id'],
        'required_request_ids': [r['request_id'] for r in requests], 'completed': completed,
        'missing_request_ids': [], 'failed_requests': [], 'all_source_requests_accepted': True,
        'proposed_branch': branch, 'source_findings': findings, 'mode': binding['execution_mode'],
        'native_request_variants': variants, 'original_allowance_binding': binding,
        'metric_result_created': False, 'review_complete': False, 'production_authorized': False,
        'filing_media_coverage_verified': False,
        'new_calls': {'provider': 0, 'paid': 0, 'sec': 0}}
    return {**body, 'assessment_set_id': content_hash(value=body)}


def prepare_selected_saved_d04_case(*, source_root, selection):
    """Deliver a checked old text group with its explicit media limitation.

    No image interpretation is supplied by the saved model-input package.
    Until that responsibility is separately fulfilled, this input cannot
    establish whole-filing absence, even when all original calls pass.
    """
    from sec_urls import accession_document_url
    from .ordinary_source_authority import verify_ordinary_source_proofs
    from .normal_source_authority import ROOT
    from .sources import raw_blob_record, source_reference_record
    from .specs import compile_spec_file
    from .calculator import withheld_metric_result
    from .d04_native_assessment import SPEC_PATH
    source = selection['original_source']
    annual = selection['prepared_annual_input']
    assessment = read_saved_d04_assessment(saved_call_package=selection['saved_call_package'],
        original_source=source, original_call_members=selection['original_call_members'],
        prepared_annual_input=annual)
    proofs = annual['source_proofs']
    admission = verify_ordinary_source_proofs(data_root=Path(source_root), proofs=proofs)
    filings = [annual['filing'], *annual.get('amendments', [])]
    wanted = {f['accessionNumber'] for f in filings}
    need({d['filing']['accessionNumber'] for d in source['documents']} == wanted,
         'SAVED_D04_SELECTED_FILING_SET_CHANGED')
    for d in source['documents']:
        ref, blob = d['source_reference'], d['raw_blob']
        url = accession_document_url(cik=int(annual['entity']),
            accession=ref['accession'], document_name=d['filing']['primaryDocument'])
        need(ref['company_id'] == annual['company_id'] and ref['source_url'] == url
             and any(p['source_url'] == url and p['content_sha256'] == blob['raw_asset_id'][7:]
                     for p in proofs), 'SAVED_D04_SELECTED_DOCUMENT_BYTES_CHANGED')
    spec = compile_spec_file(path=ROOT / SPEC_PATH, dependency_specs={})
    period = annual['table_input']['target_period']
    target = {'company_id': annual['company_id'],
        'period_start': period['period_start'], 'period_end': period['period_end'],
        'scope': spec['compiled']['required_claims'],
        'scope_key': content_hash(value=spec['compiled']['required_claims'])}
    result, trace = withheld_metric_result(compiled_spec=spec, target=target,
        reason_code='D04_SAVED_FILING_MEDIA_COVERAGE_NOT_VERIFIED')
    records, references = [], []
    for proof in proofs:
        blob = raw_blob_record(repo_root=Path(source_root),
            repo_relative_path=proof['request_repo_relative_path'],
            media_type='application/json' if proof['document_name'].endswith('.json') else 'text/html')
        ref = source_reference_record(raw_blob=blob, company_id=annual['company_id'],
            source_url=proof['source_url'], accession=proof['accession'] or 'SUBMISSIONS-' + annual['entity'],
            document_name=proof['document_name'], source_role='supporting_input',
            request_attempt_id=proof['request_attempt_id'])
        records.extend([blob, ref]); references.append(ref)
    limitation = {'record_type': 'D04_SAVED_INPUT_SCOPE_ASSESSMENT',
        'status': 'COMPLETE_ORIGINAL_MODEL_GROUPS_MEDIA_UNVERIFIED',
        'source_id': source['semantic_source_id'],
        'original_call_ordinals': [r['ordinal'] for r in assessment['completed']],
        'original_allowance_binding': assessment['original_allowance_binding'],
        'response_assessment': assessment,
        'original_documents': [{k: d[k] for k in ('document_id', 'source_reference',
            'raw_blob', 'source_unit_ids')} for d in source['documents']],
        'filing_media_coverage_verified': False, 'absence_conclusion_authorized': False,
        'new_calls': {'provider': 0, 'paid': 0, 'sec': 0}}
    return {'kind': 'STRUCTURED', 'primary_metric_id': 'D04',
        'input_binding': limitation,
        'input_assessments': {'D04': limitation},
        'compiled_specs': {'D04': spec}, 'spec_paths': {'D04': SPEC_PATH},
        'target_period': period, 'prepared_annual_input': annual,
        'references': references, 'source_proofs': proofs, 'admission': admission,
        'expected_records': [*records, trace, result],
        'results': {'D04': result}, 'traces': {'D04': trace},
        'selection': {'status': 'WITHHELD', 'source_replay_only': True,
                      'filing_media_coverage_verified': False}, 'rules_root': str(ROOT)}
