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
    need(request['metric_id'] == 'B13', 'B13_NATIVE_ASSESSMENT_REQUIRED')
    checked = validate_response(request=request, raw_response=response_body)
    return _build_acceptance(prepared=prepared, plan=plan, response_body=response_body, checked=checked,
        metric_id='B13', group='b13_capacity_source_assessment_v1',
        spec_path='catalog/r5/B13_capacity_disclosures_v1.md', validator_path=Path(__file__))


def _build_acceptance(*, prepared, plan, response_body, checked, metric_id, group, spec_path, validator_path):
    """Shared native records; each metric's wrapper owns its source checks."""
    request = strict_json_loads(text=prepared.request_bytes.decode())
    source = strict_json_loads(text=prepared.source_bytes.decode())
    need(not checked['unresolved'] and not any(
        f['kind'] == 'UNRESOLVED' or f['subject'] == 'UNRESOLVED' or f['timing'] == 'UNRESOLVED'
        for f in checked['findings']), metric_id + '_SOURCE_ASSESSMENT_UNRESOLVED')
    document = next(d for d in source['documents']
                    if d['document_id'] == request['document_context']['document_id'])
    source_ids = [document['source_reference']['source_reference_id']]
    body = {'disclosure_group': group,
            'source_reference_ids': source_ids, 'derived_asset_ids': [plan['selected_representation_hash']],
            'selected': {'source_assessment': {
                'request_id': request['request_id'], 'unit_ids': [u['unit_id'] for u in request['units']],
                'findings': checked['findings'], 'calculation_limits': checked.get('calculation_limits', [])}},
            'competing_candidates': [], 'unresolved_competing_claims': []}
    candidate = validate_record(record={'record_type': 'OBSERVATION_CANDIDATE', **body,
        'candidate_hash': content_hash(value=body), 'attempt_id': ('capacity:' if metric_id == 'B13' else 'going-concern:') + plan['ai_invocation_plan_id'][7:],
        'assistant_output_sha256': sha256_bytes(content=response_body), 'status': 'CANDIDATE'})
    evidence_body = {'candidate_hash': candidate['candidate_hash'], 'status': 'PASS',
        'normalized_values': candidate['selected'],
        'checks': [
            {'check': metric_id + '_COMPLETE_REQUEST_UNIT_RESPONSE', 'status': 'PASS',
             'request_id': request['request_id'], 'unit_ids': [u['unit_id'] for u in request['units']]},
            {'check': metric_id + '_ORIGINAL_SOURCE_REFERENCES_AND_ROLES', 'status': 'PASS',
             'findings': checked['findings']}],
        'reason_codes': [], 'identity_constraints': []}
    evidence = validate_record(record={'record_type': 'EVIDENCE_CHECK', **evidence_body,
        'evidence_check_id': content_hash(value=evidence_body)})
    spec = compile_spec_file(path=ROOT / spec_path, dependency_specs={})
    return {'candidate_hash': candidate['candidate_hash'], 'candidate_record': candidate,
        'derived_asset_id': plan['selected_representation_hash'],
        'evidence_candidate_hash': candidate['candidate_hash'], 'evidence_check_id': evidence['evidence_check_id'],
        'evidence_record': evidence, 'evidence_status': 'PASS',
        'reader_input_manifest_id': plan['source_identity_hash'], 'source_reference_ids': source_ids,
        'spec_semantic_hash': spec['spec_semantic_hash'],
        'task_contract_hash': plan['task_contract_hash'],
        'validator_semantic_hash': content_hash(value={
            'module': sha256_file(path=validator_path),
            'policy': request['policy_sha256']}),
        'validator_semantic_version': metric_id + '_REQUEST_SOURCE_ASSESSMENT_V1'}


def collect_native_assessments(*, prepared_requests, ledger):
    """Read all current source requests; a diagnostic terminal cannot fill one.

    This uses the existing ledger and native success reader. Missing/failed
    requests remain explicit development/execution gaps, never nondisclosure.
    """
    from . import invocation_control as control
    from .native_unit_index import validate_request_partition
    from .native_assessment_replay import replay_native_response
    need(bool(prepared_requests), 'B13_COMPLETE_REQUEST_SET_REQUIRED')
    source = strict_json_loads(text=prepared_requests[0].source_bytes.decode())
    metric_id = source['metric_id']
    need(metric_id in {'B13', 'D04'}, 'NATIVE_SOURCE_METRIC_UNSUPPORTED')
    if metric_id == 'D04':
        need(source['record_type'] == 'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE', 'D04_FRESH_NATIVE_SOURCE_REQUIRED')
    expected = [strict_json_loads(text=p.request_bytes.decode()) for p in prepared_requests]
    need(all(p.source_bytes == prepared_requests[0].source_bytes for p in prepared_requests),
         'B13_COMPLETE_REQUEST_SET_CHANGED')
    variants = validate_request_partition(source, expected)
    by_id = {request['request_id']: prepared for request, prepared in zip(expected, prepared_requests)}
    need(len(by_id) == len(prepared_requests), 'B13_COMPLETE_REQUEST_SET_CHANGED')
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
            replay = replay_native_response(prepared=prepared, path=path)
            success = replay['success']; acceptance = success['acceptance_receipt']
            terminal = strict_json_file(path=path / 'terminal.json')
            completed[identity] = {'request_id': identity, 'ordinal': row['ordinal'],
                'terminal_id': terminal['terminal_id'], 'acceptance_receipt_id': success['acceptance_receipt_id'],
                'candidate': acceptance['candidate_record'], 'evidence': acceptance['evidence_record'],
                'source_revalidation': replay['revalidation']}
    missing = [r['request_id'] for r in expected if r['request_id'] not in completed]
    rows = [completed[r['request_id']] for r in expected if r['request_id'] in completed]
    findings = [f for row in rows for f in row['candidate']['selected']['source_assessment']['findings']]
    current = [f for f in findings if f['subject'] == 'TARGET_REGISTRANT' and f['timing'] == 'CURRENT_REPORT']
    kinds = {f['kind'] for f in current}
    relevant = [f for f in findings if f['kind'] in {
        'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY', 'CAPACITY_QUALITATIVE', 'PLANNED_CAPACITY'}]
    if metric_id == 'D04':
        from .d04_native_assessment import CURRENT_KINDS
        relevant = [f for f in current if f['kind'] in CURRENT_KINDS]
    if missing:
        branch = 'INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE'
    elif metric_id == 'D04' and len(kinds & CURRENT_KINDS) > 1:
        branch = 'CROSS_REQUEST_GOING_CONCERN_RECONCILIATION_REQUIRED'
    elif metric_id == 'B13' and {'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY'} <= kinds:
        branch = 'COMPARABLE_QUANTITY_PAIR_ASSESSMENT_REQUIRED'
    elif relevant:
        branch = 'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW'
    else:
        branch = 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
    body = {'record_type': metric_id + '_NATIVE_SOURCE_ASSESSMENT_SET', 'source_id': source['semantic_source_id'],
        'company_id': source['company_id'], 'required_request_ids': [r['request_id'] for r in expected],
        'completed': rows, 'missing_request_ids': missing, 'failed_requests': failures,
        'all_source_requests_accepted': not missing, 'proposed_branch': branch,
        'source_findings': findings, 'mode': 'LIVE' if ledger.live else 'RECORDED_TEST_ONLY',
        'metric_result_created': False, 'review_complete': False, 'production_authorized': False}
    if 'INDEXED_UNITS_V1' in variants:
        body['native_request_variants'] = variants
    return {**body, 'assessment_set_id': content_hash(value=body)}
