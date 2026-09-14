"""B13 source excerpts reuse the native TEXT_V1 Review/Observation/Calculator.

The supplied assessment is input, not self-issued authority. The Run adapter
must independently recover it from registered native executions before calling
these pure record builders. A partial assessment never becomes nondisclosure.
"""
from .canonical import content_hash, sha256_bytes
from .capacity_utilization_source import need
from .records import validate_record
from .text_results import text_policy, text_claim_from_block
from .text_review import build_text_review_unit

METHOD = 'PRODUCTION_CAPACITY_DISCLOSURE_EXCERPTS_V1'
_QUALITATIVE = {'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY', 'CAPACITY_QUALITATIVE', 'PLANNED_CAPACITY'}


def validate_deterministic_candidate_shape(*, candidate):
    # The derivative is deterministic; source-role judgments remain explicitly
    # bound model inputs in proposal_id and the complete Evidence coverage.
    need(candidate['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE'
         and candidate['method'] == METHOD and candidate['status'] == 'CANDIDATE'
         and not candidate['derived_asset_ids'] and not candidate['competing_candidates']
         and not candidate['unresolved_competing_claims'], 'B13_TEXT_CANDIDATE_SHAPE')
    target = candidate['calculation_target']
    need(set(target) == {'company_id', 'entity', 'accession', 'period_start', 'period_end', 'scope', 'scope_key'}
         and target['scope_key'] == content_hash(value=target['scope']), 'B13_TEXT_TARGET_CHANGED')
    ids = candidate['source_reference_ids']
    need(bool(ids) and len(ids) == len(set(ids)) and set(candidate['document_bindings']) == set(ids),
         'B13_TEXT_SOURCE_SET_CHANGED')
    import re
    digest = re.compile(r'sha256:[0-9a-f]{64}')
    need(all(type(value) is str and digest.fullmatch(value) for value in [
        *ids, candidate['spec_semantic_hash'], candidate['spec_closure_hash'], candidate['source_set_hash']]),
        'B13_TEXT_CANDIDATE_HASH_INVALID')
    for binding in candidate['document_bindings'].values():
        need(set(binding) == {'document_id', 'coverage_hash', 'proposal_id'}
             and all(type(v) is str and digest.fullmatch(v) for v in binding.values()),
             'B13_TEXT_DOCUMENT_BINDING_CHANGED')


def _prepare(*, compiled_spec, target, source, assessment, source_references, raw_bytes_by_id):
    policy = text_policy(compiled_spec)
    need(compiled_spec['compiled']['metric_id'] == 'B13'
         and compiled_spec['compiled']['quality_rule']['deterministic_text_method'] == METHOD
         and target['scope'] == compiled_spec['compiled']['required_claims'], 'B13_TEXT_SPEC_CHANGED')
    need(source['semantic_source_id'] == content_hash(value={k: v for k, v in source.items() if k != 'semantic_source_id'})
         and assessment['assessment_set_id'] == content_hash(value={k: v for k, v in assessment.items() if k != 'assessment_set_id'})
         and assessment['source_id'] == source['semantic_source_id']
         and assessment['company_id'] == source['company_id'] == target['company_id'],
         'B13_TEXT_ASSESSMENT_SOURCE_CHANGED')
    need(assessment['all_source_requests_accepted'] is True and not assessment['missing_request_ids']
         and not assessment['failed_requests'], 'B13_TEXT_COMPLETE_ASSESSMENT_REQUIRED')
    from .capacity_semantic_review import requests_from_source
    requests = requests_from_source(source)
    request_ids = [r['request_id'] for r in requests]
    need(assessment['required_request_ids'] == request_ids
         and [row['request_id'] for row in assessment['completed']] == request_ids,
         'B13_TEXT_REQUEST_COVERAGE_CHANGED')
    # Derive findings from the native candidates, never from an editable
    # convenience summary. The caller separately replays native wire/Evidence.
    findings = [f for row in assessment['completed']
                for f in row['candidate']['selected']['source_assessment']['findings']]
    need(findings == assessment['source_findings'], 'B13_TEXT_FINDING_SUMMARY_CHANGED')
    current_kinds = {f['kind'] for f in findings
                     if f['subject'] == 'TARGET_REGISTRANT' and f['timing'] == 'CURRENT_REPORT'}
    need(not {'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY'} <= current_kinds,
         'B13_COMPARABLE_PAIR_ASSESSMENT_REQUIRED')
    absent = not any(f['kind'] in _QUALITATIVE for f in findings)
    expected_branch = ('DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW' if absent else
                       'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW')
    need(assessment['proposed_branch'] == expected_branch,
         'B13_TEXT_BRANCH_NOT_ESTABLISHED')
    annual = source['prepared_annual_input']
    period = annual['table_input']['target_period']
    need(target['entity'] == annual['entity'] and target['accession'] == annual['filing']['accessionNumber']
         and target['period_start'] == period['period_start'] and target['period_end'] == period['period_end']
         and target['scope_key'] == content_hash(value=target['scope']), 'B13_TEXT_ANNUAL_COORDINATE_CHANGED')
    documents = {}
    units = {u['unit_id']: u for u in source['units']}
    selected = set()
    for finding in findings:
        if finding['kind'] not in _QUALITATIVE:
            continue
        unit = units[finding['unit_id']]
        for evidence in finding['resolved_evidence']:
            if evidence['kind'] == 'VISIBLE_BLOCK':
                selected.add((unit['document_id'], evidence['source_index']))
    need(bool(selected) or absent, 'B13_VISIBLE_CAPACITY_EXCERPT_NOT_ESTABLISHED')
    need(source_references == [d['source_reference'] for d in source['documents']], 'B13_TEXT_SOURCE_SET_CHANGED')
    coverages, claims, bindings = [], {}, {}
    for original in source['documents']:
        did = original['document_id']; ref = original['source_reference']; sid = ref['source_reference_id']
        blocks = [b for u in source['units'] if u['document_id'] == did and u['kind'] == 'VISIBLE_TEXT'
                  for b in u['payload']['blocks']]
        need([b['block_index'] for b in blocks] == list(range(len(blocks))), 'B13_TEXT_BLOCK_CENSUS_CHANGED')
        document = {'text_document_id': did, 'source_reference_id': sid, 'blocks': blocks}
        raw = raw_bytes_by_id[original['raw_blob']['raw_asset_id']]
        need(sha256_bytes(content=raw) == original['raw_blob']['raw_asset_id'][7:], 'B13_TEXT_ORIGINAL_BYTES_CHANGED')
        coverage = {'source_reference_id': sid, 'document_id': did,
            'assessment_set_id': assessment['assessment_set_id'], 'source_check_scope': source['source_check_scope'],
            'source_filing': original['filing'], 'scope': target['scope'],
            'ranges': [{'section_id': 'CAPACITY_DISCLOSURES', 'start_block': 0, 'end_block_exclusive': len(blocks)}],
            'required_unit_ids': original['source_unit_ids'], 'assessment_mode': assessment['mode'],
            'numeric_utilization_inferred': False}
        coverage['coverage_hash'] = content_hash(value=coverage)
        coverages.append(coverage); documents[did] = document
        bindings[sid] = {'document_id': did, 'coverage_hash': coverage['coverage_hash'],
                         'proposal_id': assessment['assessment_set_id']}
        for _, index in sorted(pair for pair in selected if pair[0] == did):
            block = blocks[index]
            need(sha256_bytes(content=raw[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256'],
                 'B13_TEXT_RAW_SPAN_CHANGED')
            order = len(claims)
            claims['excerpt_' + str(order)] = text_claim_from_block(document=document,
                section_id='CAPACITY_DISCLOSURES', block_index=index, order=order)
    need((0 if absent else 1) <= len(claims) <= policy['max_items'] and
         sum(len(c['text']) for c in claims.values()) + len(claims) - 1 <= policy['max_text_chars'],
         'B13_COMPLETE_TEXT_EXCERPTS_EXCEED_BOUND')
    return claims, bindings, coverages


def create_deterministic_text_candidate(*, compiled_spec, target, source, assessment, source_references, raw_bytes_by_id):
    selected, bindings, _ = _prepare(compiled_spec=compiled_spec, target=target, source=source,
        assessment=assessment, source_references=source_references, raw_bytes_by_id=raw_bytes_by_id)
    body = {'record_type': 'DETERMINISTIC_TEXT_CANDIDATE', 'method': METHOD,
        'spec_semantic_hash': compiled_spec['spec_semantic_hash'], 'spec_closure_hash': compiled_spec['spec_closure_hash'],
        'source_set_hash': content_hash(value=source_references), 'document_bindings': bindings,
        'calculation_target': target, 'disclosure_group': compiled_spec['compiled']['disclosure_group'],
        'source_reference_ids': [s['source_reference_id'] for s in source_references], 'derived_asset_ids': [],
        'selected': selected, 'competing_candidates': [], 'unresolved_competing_claims': []}
    return validate_record(record={**body, 'candidate_hash': content_hash(value=body), 'status': 'CANDIDATE'})


def build_text_evidence(*, compiled_spec, candidate, **arguments):
    expected = create_deterministic_text_candidate(compiled_spec=compiled_spec, **arguments)
    need(validate_record(record=candidate) == expected, 'B13_TEXT_CANDIDATE_REPLAY_CHANGED')
    _, _, coverage = _prepare(compiled_spec=compiled_spec, **arguments)
    body = {'candidate_hash': candidate['candidate_hash'], 'status': 'PASS',
        'normalized_values': {role: claim['text'] for role, claim in candidate['selected'].items()},
        'checks': [{'check': 'B13_COMPLETE_NATIVE_SOURCE_ASSESSMENT', 'status': 'PASS', 'coverage': coverage}],
        'reason_codes': [], 'identity_constraints': [], 'normalized_scope': arguments['target']['scope'],
        'system_approval_eligible': True, 'unresolved_scope_dimensions': []}
    return validate_record(record={'record_type': 'EVIDENCE_CHECK', **body, 'evidence_check_id': content_hash(value=body)})


def replay_text_result(*, compiled_spec, target, company_traits, candidate, evidence_check,
                       review_unit, review_decisions, **arguments):
    from .review import effective_review_decision
    from .observations import _build_text_observation
    from .calculator import calculate_text_metric
    expected = build_text_evidence(compiled_spec=compiled_spec, candidate=candidate, target=target, **arguments)
    need(validate_record(record=evidence_check) == expected, 'B13_TEXT_EVIDENCE_REPLAY_CHANGED')
    expected_unit, _ = build_text_review_unit(compiled_spec=compiled_spec, candidate=candidate,
        evidence_check=expected, source_bindings=arguments['source_references'])
    need(validate_record(record=review_unit) == expected_unit, 'B13_TEXT_REVIEW_CHANGED')
    decision = effective_review_decision(review_unit=review_unit, decisions=review_decisions)
    need(decision['decision'] == 'APPROVE' and decision['approved_claims'] == target['scope'],
         'B13_TEXT_EFFECTIVE_REVIEW_REQUIRED')
    if not candidate['selected']:
        from .text_results import build_text_result_and_trace
        result, trace = build_text_result_and_trace(compiled_spec=compiled_spec, target=target,
            reason_code='B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE')
        return result, trace, []
    references = {s['source_reference_id']: s for s in arguments['source_references']}
    coverage = {r['source_reference_id']: r for r in expected['checks'][0]['coverage']}
    observations = []
    for role, claim in sorted(candidate['selected'].items(), key=lambda pair: pair[1]['order']):
        ref = references[claim['source_reference_id']]
        binding = {key: ref[key] for key in ('raw_asset_id', 'source_reference_id', 'accession', 'document_name', 'source_role')}
        binding['text_binding'] = {'protocol': 'TEXT_V1', 'spec_closure_hash': compiled_spec['spec_closure_hash'],
            'candidate_hash': candidate['candidate_hash'], 'review_unit_hash': review_unit['review_unit_hash'],
            'coverage_hash': coverage[ref['source_reference_id']]['coverage_hash'],
            **{key: claim[key] for key in ('extent', 'document_id', 'section_id', 'block_index', 'raw_start_byte',
                                          'raw_end_byte', 'raw_span_sha256', 'order')}}
        observations.append(_build_text_observation(metric_id='B13', semantic_role=role, company_id=target['company_id'],
            period_start=target['period_start'], period_end=target['period_end'], scope=target['scope'],
            value=claim['text'], source_binding=binding, approval_effect_hash=decision['approval_effect_hash']))
    result, trace = calculate_text_metric(compiled_spec=compiled_spec, target=target,
        company_traits=company_traits, observations=observations)
    return result, trace, observations
