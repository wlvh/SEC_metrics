"""Explicit C02 successor over the frozen text-record and Review machinery.

The source, period and coverage proof remain in text_results_v2. Only the
governance proposal comes from the shared composition reader. This module
rebuilds the candidate and Evidence from that proposal on every read; the
frozen C02/D02 default is never patched or rebound in process.
"""
from . import text_results_v2 as old
from .canonical import content_hash, sha256_bytes
from .historical_board_composition import board_composition_facts
from .records import validate_record


build_text_review_unit = old.build_text_review_unit
validate_deterministic_candidate_shape = old.validate_deterministic_candidate_shape


def _successor(compiled_spec):
    return (compiled_spec['compiled']['metric_id'] == 'C02'
            and compiled_spec['compiled']['disclosure_group'] in
            {'c02_composition_facts_v1', 'c02_composition_grouped_v2'})


def _require_spec_policy_pair(*, compiled_spec, source_arguments):
    expected = {
        'c02_composition_facts_v1': 'COMPOSITION_FACTS_V1',
        'c02_composition_grouped_v2': 'COMPOSITION_GROUPED_V2',
    }[compiled_spec['compiled']['disclosure_group']]
    old._need(source_arguments.get('c02_selection_policy') == expected,
              'C02_COMPOSITION_SPEC_POLICY_MISMATCH')


def _prepared(*, c02_selection_policy, **source_arguments):
    old._need(c02_selection_policy in {'COMPOSITION_FACTS_V1', 'COMPOSITION_GROUPED_V2'},
              'C02_COMPOSITION_SELECTION_POLICY_REQUIRED')
    prepared = old.prepare_business_text_sources(metric_id='C02', **source_arguments)
    proposals = dict(prepared['proposals'])
    governance_ids = [sid for sid, proposal in proposals.items()
                      if proposal.get('metric_id') == 'C02']
    old._need(len(governance_ids) == 1, 'C02_COMPOSITION_GOVERNANCE_SOURCE_REQUIRED')
    sid = governance_ids[0]
    document = prepared['documents'][sid]
    if c02_selection_policy == 'COMPOSITION_GROUPED_V2':
        # This explicit grouped route consumes the pinned period-aware shared
        # reader. The earlier V2 and default C02 routes keep their own bytes.
        from .historical_board_composition_v2 import board_composition_facts as current_facts
        successor = current_facts(
            document=document, period_start=source_arguments['target']['period_start'])
    else:
        successor = board_composition_facts(document=document)
    old._need(successor['document_id'] == document['text_document_id']
              and successor['source_reference_id'] == sid
              and successor['source_filing'] == proposals[sid]['source_filing']
              and successor['coverage_status'] == proposals[sid]['coverage_status'],
              'C02_COMPOSITION_SOURCE_BINDING_CHANGED')
    if c02_selection_policy == 'COMPOSITION_GROUPED_V2':
        from .c02_grouped_source import grouped_governance_source
        document, successor, coverage = grouped_governance_source(
            document=document, proposal=successor,
            coverage=prepared['coverages'][sid],
            raw_bytes=source_arguments['raw_bytes_by_id'][document['raw_asset_id']])
        return {**prepared, 'documents': {**prepared['documents'], sid: document},
                'coverages': {**prepared['coverages'], sid: coverage},
                'proposals': {**proposals, sid: successor}}
    proposals[sid] = successor
    return {**prepared, 'proposals': proposals}


def create_deterministic_text_candidate(*, compiled_spec, **source_arguments):
    if not _successor(compiled_spec):
        return old.create_deterministic_text_candidate(
            compiled_spec=compiled_spec, **source_arguments)
    old._need(compiled_spec['compiled']['metric_id'] == 'C02'
              and compiled_spec['compiled']['disclosure_group'] in
              {'c02_composition_facts_v1', 'c02_composition_grouped_v2'}
              and compiled_spec['compiled']['text_policy']['max_items'] == 64,
              'C02_COMPOSITION_SPEC_REQUIRED')
    _require_spec_policy_pair(compiled_spec=compiled_spec,
                              source_arguments=source_arguments)
    return old._derive_candidate(compiled_spec=compiled_spec,
                                 target=source_arguments['target'],
                                 prepared=_prepared(**source_arguments))


def build_text_evidence(*, compiled_spec, candidate, **source_arguments):
    """Rebuild the successor set and independently check every raw excerpt."""
    if not _successor(compiled_spec):
        return old.build_text_evidence(compiled_spec=compiled_spec,
                                       candidate=candidate, **source_arguments)
    _require_spec_policy_pair(compiled_spec=compiled_spec,
                              source_arguments=source_arguments)
    prepared = _prepared(**source_arguments)
    expected = old._derive_candidate(compiled_spec=compiled_spec,
                                     target=source_arguments['target'], prepared=prepared)
    old._need(validate_record(record=candidate) == expected,
              'C02_COMPOSITION_CANDIDATE_REPLAY_CHANGED')
    checks, normalized, seen = [], {}, set()
    grouped = compiled_spec['compiled']['disclosure_group'] == 'c02_composition_grouped_v2'
    for role, claim in sorted(candidate['selected'].items(),
                              key=lambda pair: pair[1]['order']):
        sid = claim['source_reference_id']
        document = prepared['documents'][sid]
        index = claim['block_index']
        old._need((sid, index) not in seen, 'TEXT_V2_DUPLICATE_EXCERPT')
        seen.add((sid, index))
        old._need(any(r['section_id'] == claim['section_id']
                      and r['start_block'] <= index < r['end_block_exclusive']
                      for r in prepared['coverages'][sid]['ranges']),
                  'TEXT_V2_EXCERPT_OUTSIDE_SOURCE_RANGE')
        raw = source_arguments['raw_bytes_by_id'][document['raw_asset_id']]
        old._need(sha256_bytes(content=raw[claim['raw_start_byte']:claim['raw_end_byte']])
                  == claim['raw_span_sha256'], 'TEXT_V2_RAW_SPAN_REPLAY_CHANGED')
        normalized[role] = claim['text']
        check = {'check': 'TEXT_EXACT_EXCERPT:' + role,
                 'status': 'PASS', 'claim_hash': content_hash(value=claim)}
        if grouped:
            block = document['blocks'][index]
            old._need(block['raw_start_byte'] == claim['raw_start_byte']
                      and block['raw_end_byte'] == claim['raw_end_byte']
                      and block['raw_span_sha256'] == claim['raw_span_sha256']
                      and block['text'] == claim['text']
                      and block['selected_source_blocks'],
                      'C02_GROUPED_EXCERPT_SOURCE_MAP_CHANGED')
            check.update(original_text_document_id=document['original_text_document_id'],
                         source_block_range=list(block['source_block_range']),
                         selected_source_blocks=list(block['selected_source_blocks']),
                         context_source_blocks=list(block['context_source_blocks']),
                         complete_source_partition_hash=prepared['coverages'][sid]['complete_source_partition_hash'])
        checks.append(check)
    target = source_arguments['target']
    body = {'candidate_hash': candidate['candidate_hash'], 'status': 'PASS',
            'normalized_values': normalized,
            'checks': [{'check': 'TEXT_V2_SOURCE_COVERAGE_AND_TIME', 'status': 'PASS',
                        'coverage': list(prepared['coverages'].values())}] + checks,
            'reason_codes': [], 'identity_constraints': [],
            'normalized_scope': dict(target['scope']),
            'system_approval_eligible': True, 'unresolved_scope_dimensions': []}
    return validate_record(record={'record_type': 'EVIDENCE_CHECK',
                                   'evidence_check_id': content_hash(value=body), **body})


def reviewed_text_observations(*, compiled_spec, target, candidate,
                               evidence_check, review_unit, review_decisions,
                               **source_arguments):
    from .observations import _build_text_observation
    from .review import effective_review_decision

    expected = build_text_evidence(compiled_spec=compiled_spec, target=target,
                                   candidate=candidate, **source_arguments)
    old._need(validate_record(record=evidence_check) == expected,
              'C02_COMPOSITION_EVIDENCE_REPLAY_CHANGED')
    unit = validate_record(record=review_unit)
    expected_unit, _ = build_text_review_unit(
        compiled_spec=compiled_spec, candidate=candidate,
        evidence_check=expected, source_bindings=source_arguments['source_references'])
    old._need(unit == expected_unit, 'TEXT_V2_REVIEW_BINDING_CHANGED')
    decision = effective_review_decision(review_unit=unit, decisions=review_decisions)
    old._need(decision['decision'] == 'APPROVE'
              and decision['reviewer_type'] in {'HUMAN', 'SYSTEM'}
              and decision['approved_claims'] == target['scope'],
              'TEXT_V2_EFFECTIVE_APPROVAL_REQUIRED')
    sources = {s['source_reference_id']: s for s in source_arguments['source_references']}
    coverages = {r['source_reference_id']: r
                 for r in expected['checks'][0]['coverage']}
    observations = []
    for role, claim in sorted(candidate['selected'].items(),
                              key=lambda pair: pair[1]['order']):
        source = sources[claim['source_reference_id']]
        binding = {k: source[k] for k in (
            'raw_asset_id', 'source_reference_id', 'accession',
            'document_name', 'source_role')}
        binding['text_binding'] = {
            'protocol': 'TEXT_V1', 'spec_closure_hash': compiled_spec['spec_closure_hash'],
            'candidate_hash': candidate['candidate_hash'],
            'review_unit_hash': unit['review_unit_hash'],
            'coverage_hash': coverages[source['source_reference_id']]['coverage_hash'],
            **{key: claim[key] for key in (
                'extent', 'document_id', 'section_id', 'block_index',
                'raw_start_byte', 'raw_end_byte', 'raw_span_sha256', 'order')}}
        observations.append(_build_text_observation(
            metric_id='C02', semantic_role=role,
            company_id=target['company_id'],
            period_start=target['period_start'], period_end=target['period_end'],
            scope=target['scope'], value=claim['text'], source_binding=binding,
            approval_effect_hash=decision['approval_effect_hash']))
    return observations


def replay_text_result(*, compiled_spec, target, company_traits, candidate,
                       evidence_check, review_unit, review_decisions,
                       **source_arguments):
    if not _successor(compiled_spec):
        return old.replay_text_result(
            compiled_spec=compiled_spec, target=target,
            company_traits=company_traits, candidate=candidate,
            evidence_check=evidence_check, review_unit=review_unit,
            review_decisions=review_decisions, **source_arguments)
    _require_spec_policy_pair(compiled_spec=compiled_spec,
                              source_arguments=source_arguments)
    from .calculator import calculate_text_metric
    observations = reviewed_text_observations(
        compiled_spec=compiled_spec, target=target, candidate=candidate,
        evidence_check=evidence_check, review_unit=review_unit,
        review_decisions=review_decisions, **source_arguments)
    result, trace = calculate_text_metric(
        compiled_spec=compiled_spec, target=target,
        company_traits=company_traits, observations=observations)
    return result, trace, observations


def verify_text_result(*, result, trace, observations, **replay_arguments):
    if not _successor(replay_arguments['compiled_spec']):
        return old.verify_text_result(result=result, trace=trace,
                                      observations=observations, **replay_arguments)
    expected_result, expected_trace, expected_observations = replay_text_result(
        **replay_arguments)
    actual = {o['observation_id']: o for o in observations}
    expected = {o['observation_id']: o for o in expected_observations}
    old._need(len(actual) == len(observations) and actual == expected
              and result == expected_result and trace == expected_trace,
              'C02_COMPOSITION_NATIVE_REPLAY_CHANGED')
    return expected_result, expected_trace, expected_observations
