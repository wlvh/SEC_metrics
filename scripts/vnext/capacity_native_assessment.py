"""B13 per-request Candidate/Evidence on the existing WB-3 acceptance chain.

Acceptance proves complete response coverage, literal source references and
finite source-role checks. It does not certify a whole metric or publish it.
The final B13 route must consume every request and obtain its own Review.
"""
from pathlib import Path

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_loads, strict_json_file
from .capacity_utilization_source import need
from .capacity_semantic_review import validate_response
from .records import validate_record
from .normal_source_authority import ROOT
from .specs import compile_spec_file
from .sources import resolve_repository_file


def build_acceptance(*, prepared, plan, response_body):
    request = strict_json_loads(text=prepared.request_bytes.decode())
    source = strict_json_loads(text=prepared.source_bytes.decode())
    need(request['metric_id'] == 'B13', 'B13_NATIVE_ASSESSMENT_REQUIRED')
    checked = validate_response(request=request, raw_response=response_body)
    need(not checked['unresolved'] and not any(
        f['subject'] == 'UNRESOLVED' or f['timing'] == 'UNRESOLVED' for f in checked['findings']),
        'B13_SOURCE_ASSESSMENT_UNRESOLVED')
    document = next(d for d in source['documents']
                    if d['document_id'] == request['document_context']['document_id'])
    source_ids = [document['source_reference']['source_reference_id']]
    body = {'disclosure_group': 'b13_capacity_source_assessment_v1',
            'source_reference_ids': source_ids, 'derived_asset_ids': [plan['selected_representation_hash']],
            'selected': {'source_assessment': {
                'request_id': request['request_id'], 'unit_ids': [u['unit_id'] for u in request['units']],
                'findings': checked['findings'], 'calculation_limits': checked['calculation_limits']}},
            'competing_candidates': [], 'unresolved_competing_claims': []}
    candidate = validate_record(record={'record_type': 'OBSERVATION_CANDIDATE', **body,
        'candidate_hash': content_hash(value=body), 'attempt_id': 'capacity:' + plan['ai_invocation_plan_id'][7:],
        'assistant_output_sha256': sha256_bytes(content=response_body), 'status': 'CANDIDATE'})
    evidence_body = {'candidate_hash': candidate['candidate_hash'], 'status': 'PASS',
        'normalized_values': candidate['selected'],
        'checks': [
            {'check': 'B13_COMPLETE_REQUEST_UNIT_RESPONSE', 'status': 'PASS',
             'request_id': request['request_id'], 'unit_ids': [u['unit_id'] for u in request['units']]},
            {'check': 'B13_ORIGINAL_SOURCE_REFERENCES_AND_ROLES', 'status': 'PASS',
             'findings': checked['findings']}],
        'reason_codes': [], 'identity_constraints': []}
    evidence = validate_record(record={'record_type': 'EVIDENCE_CHECK', **evidence_body,
        'evidence_check_id': content_hash(value=evidence_body)})
    spec = compile_spec_file(path=ROOT / 'catalog/r5/B13_capacity_disclosures_v1.md', dependency_specs={})
    return {'candidate_hash': candidate['candidate_hash'], 'candidate_record': candidate,
        'derived_asset_id': plan['selected_representation_hash'],
        'evidence_candidate_hash': candidate['candidate_hash'], 'evidence_check_id': evidence['evidence_check_id'],
        'evidence_record': evidence, 'evidence_status': 'PASS',
        'reader_input_manifest_id': plan['source_identity_hash'], 'source_reference_ids': source_ids,
        'spec_semantic_hash': spec['spec_semantic_hash'],
        'task_contract_hash': plan['task_contract_hash'],
        'validator_semantic_hash': content_hash(value={
            'module': sha256_file(path=Path(__file__)),
            'policy': request['policy_sha256']}),
        'validator_semantic_version': 'B13_REQUEST_SOURCE_ASSESSMENT_V1'}


def collect_native_assessments(*, prepared_requests, ledger):
    """Read all current source requests; a diagnostic terminal cannot fill one.

    This uses the existing ledger and native success reader. Missing/failed
    requests remain explicit development/execution gaps, never nondisclosure.
    """
    from . import invocation_control as control
    from .continuous_semantic_calls import build_plan
    need(bool(prepared_requests), 'B13_COMPLETE_REQUEST_SET_REQUIRED')
    source = strict_json_loads(text=prepared_requests[0].source_bytes.decode())
    from .capacity_semantic_review import requests_from_source
    expected = requests_from_source(source)
    by_id = {strict_json_loads(text=p.request_bytes.decode())['request_id']: p for p in prepared_requests}
    need(len(by_id) == len(prepared_requests) and set(by_id) == {r['request_id'] for r in expected}
         and all(p.source_bytes == prepared_requests[0].source_bytes for p in prepared_requests),
         'B13_COMPLETE_REQUEST_SET_CHANGED')
    completed, failures = {}, []
    with ledger.locked():
        state = ledger.snapshot()
        for row in state['rows']:
            if row['channel'] != 'PROVIDER':
                continue
            path = ledger.root / 'calls' / ('%04d' % row['ordinal'])
            request_path = path / 'semantic-request.json'
            if not request_path.exists():
                continue
            saved = strict_json_file(path=resolve_repository_file(repo_root=path,
                                    repo_relative_path='semantic-request.json'))
            identity = saved.get('request_id')
            if identity not in by_id:
                continue
            prepared = by_id[identity]
            need(saved == strict_json_loads(text=prepared.request_bytes.decode()), 'B13_SAVED_REQUEST_CHANGED')
            need(identity not in completed, 'B13_DUPLICATE_NATIVE_ASSESSMENT')
            if row['status'] != 'SUCCEEDED':
                failures.append({'request_id': identity, 'ordinal': row['ordinal'], 'status': row['status']})
                continue
            _, plan = build_plan(prepared)
            intent = strict_json_file(path=path / 'intent.json')
            need(intent['plan_id'] == plan['ai_invocation_plan_id'], 'B13_ASSESSMENT_EXECUTION_BINDING_CHANGED')
            with control._successor_plan_context(repo_root=ROOT, authority=prepared.authority):
                success = control.load_successful_response(workspace_dir=path, plan=plan)
            acceptance = build_acceptance(prepared=prepared, plan=plan, response_body=success['response_body'])
            need(all(success['acceptance_receipt'][key] == value for key, value in acceptance.items()),
                 'B13_NATIVE_ACCEPTANCE_REPLAY_CHANGED')
            terminal = strict_json_file(path=path / 'terminal.json')
            completed[identity] = {'request_id': identity, 'ordinal': row['ordinal'],
                'terminal_id': terminal['terminal_id'], 'acceptance_receipt_id': success['acceptance_receipt_id'],
                'candidate': acceptance['candidate_record'], 'evidence': acceptance['evidence_record']}
    missing = [r['request_id'] for r in expected if r['request_id'] not in completed]
    rows = [completed[r['request_id']] for r in expected if r['request_id'] in completed]
    findings = [f for row in rows for f in row['candidate']['selected']['source_assessment']['findings']]
    current = [f for f in findings if f['subject'] == 'TARGET_REGISTRANT' and f['timing'] == 'CURRENT_REPORT']
    kinds = {f['kind'] for f in current}
    relevant = [f for f in findings if f['kind'] in {
        'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY', 'CAPACITY_QUALITATIVE', 'PLANNED_CAPACITY'}]
    if missing:
        branch = 'INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE'
    elif {'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY'} <= kinds:
        branch = 'COMPARABLE_QUANTITY_PAIR_ASSESSMENT_REQUIRED'
    elif relevant:
        branch = 'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW'
    else:
        branch = 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
    body = {'record_type': 'B13_NATIVE_SOURCE_ASSESSMENT_SET', 'source_id': source['semantic_source_id'],
        'company_id': source['company_id'], 'required_request_ids': [r['request_id'] for r in expected],
        'completed': rows, 'missing_request_ids': missing, 'failed_requests': failures,
        'all_source_requests_accepted': not missing, 'proposed_branch': branch,
        'source_findings': findings, 'mode': 'LIVE' if ledger.live else 'RECORDED_TEST_ONLY',
        'metric_result_created': False, 'review_complete': False, 'production_authorized': False}
    return {**body, 'assessment_set_id': content_hash(value=body)}
