"""Offline D03 successor: source anchors are review candidates, not verdicts.

The existing D03 request and its historical source-fact behavior stay exact.
This module deliberately has no provider execution entry. A later explicit
request authority must bind this successor before any real call is possible.
"""
from copy import deepcopy

from .canonical import content_hash, strict_json_loads

VERSION = 'D03_SOURCE_ANCHOR_REVIEW_V1'
OLD_SUFFIX = (
    ' source_statement_facts records bounded source-derived relations. '
    'Keep assertion, source-bound subject, reported time and level of case detail separate. '
    'An affirmative aggregate involvement fact supplies no case identity, count or guilt. '
    'Preserve exceptions and other findings; report conflicts as unresolved instead of erasing the source fact.')
NEW_SUFFIX = (
    ' source_fact_candidates identify exact source locations and registered name bindings only. '
    'They do not establish that a governmental investigation is current, belongs to this registrant, '
    'or remains open. Review each candidate in its full local and surrounding context. '
    'Give each candidate a cited finding, including UNRESOLVED when subject, time or resolution '
    'cannot be established. Never silently place a candidate in context_only_source_indices. '
    'Preserve conflicts and uncertainty; do not infer guilt, case count or an absence conclusion.')


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def candidate_request(original):
    """Replace semantic source-fact credit with exact mechanical anchors."""
    from .r6_semantic_review import _source_items
    _need(type(original) is dict
          and original.get('record_type') == 'D03_INTERPRETATION_REQUEST'
          and original.get('metric_id') == 'D03'
          and original.get('request_id') == content_hash(value={
              key: value for key, value in original.items() if key != 'request_id'})
          and type(original.get('source_statement_facts')) is list
          and bool(original['source_statement_facts'])
          and original['system_prompt'].endswith(OLD_SUFFIX),
          'D03_ANCHOR_ORIGINAL_REQUEST_REQUIRED')
    anchors = []
    for fact in original['source_statement_facts']:
        matching = []
        for unit in original['units']:
            if unit['document_id'] != fact['document_id'] or unit['kind'] != 'VISIBLE_TEXT':
                continue
            _, items = _source_items(unit)
            item = items.get(fact['block_index'])
            if item is not None:
                matching.append((unit, item))
        _need(len(matching) == 1, 'D03_ANCHOR_SOURCE_BLOCK_NOT_UNIQUE')
        unit, block = matching[0]
        _need(all(fact[key] == block[key] for key in
                  ('raw_start_byte', 'raw_end_byte', 'raw_span_sha256'))
              and fact['statement_text'] in block['text'],
              'D03_ANCHOR_ORIGINAL_BYTES_CHANGED')
        body = {'unit_id': unit['unit_id'],
                'document_id': fact['document_id'],
                'source_reference_id': fact['source_reference_id'],
                'block_index': fact['block_index'],
                'raw_start_byte': fact['raw_start_byte'],
                'raw_end_byte': fact['raw_end_byte'],
                'raw_span_sha256': fact['raw_span_sha256'],
                'statement_text': fact['statement_text'],
                'subject_binding': fact['subject_binding'],
                'legacy_diagnostic_source_fact_id': fact['source_fact_id']}
        anchors.append({**body, 'candidate_id': content_hash(value=body)})
    body = {key: deepcopy(value) for key, value in original.items()
            if key not in {'request_id', 'source_statement_facts'}}
    body['system_prompt'] = body['system_prompt'][:-len(OLD_SUFFIX)] + NEW_SUFFIX
    body['source_fact_candidates'] = anchors
    body['source_fact_review_contract'] = {
        'version': VERSION, 'original_request_id': original['request_id'],
        'source_statement_facts_hash': content_hash(value=original['source_statement_facts'])}
    return {**body, 'request_id': content_hash(value=body)}


def validate_candidate_response(*, original_request, request, raw_response):
    """Keep citations strict; unresolved semantics never become a proven fact."""
    _need(request == candidate_request(original_request),
          'D03_ANCHOR_REQUEST_NOT_SOURCE_BOUND')
    response = strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(response) is dict and type(response.get('units')) is list,
          'D03_ANCHOR_RESPONSE_INVALID')
    for anchor in request['source_fact_candidates']:
        matching = [row for row in response['units']
                    if row.get('unit_id') == anchor['unit_id']]
        _need(len(matching) == 1,
              'D03_ANCHOR_RESPONSE_UNIT_MISSING_OR_DUPLICATED')
        row = matching[0]
        _need(anchor['block_index'] not in row.get('context_only_source_indices', []),
              'D03_ANCHOR_CANNOT_BE_CONTEXT_ONLY')
        _need(any(any(evidence.get('kind') == 'VISIBLE_BLOCK'
                      and evidence.get('source_index') == anchor['block_index']
                      for evidence in finding.get('evidence', []))
                  for finding in row.get('findings', [])),
              'D03_ANCHOR_CANDIDATE_UNASSESSED')
    from .r6_regulatory_semantics import validate_response
    checked = validate_response(request=request, raw_response=raw_response)
    uncertain = []
    for anchor in request['source_fact_candidates']:
        matching = [finding for finding in checked['findings']
                    if any(evidence['kind'] == 'VISIBLE_BLOCK'
                           and evidence['source_index'] == anchor['block_index']
                           for evidence in finding['evidence'])]
        _need(bool(matching), 'D03_ANCHOR_RESOLVED_FINDING_MISSING')
        if not any(finding['kind'] == 'CURRENT_REGULATORY_ACTION'
                   and finding['reported_status'] == 'ONGOING_AS_REPORTED'
                   and finding['subject'] == 'TARGET_REGISTRANT'
                   for finding in matching):
            uncertain.append({'candidate_id': anchor['candidate_id'],
                              'reason': 'SUBJECT_TIME_OR_RESOLUTION_REQUIRES_SEMANTIC_REVIEW'})
    return {**checked, 'unresolved': [*checked['unresolved'], *uncertain],
            'source_fact_candidate_review': uncertain,
            'source_fact_current_status_proven_by_program': False,
            'native_result_created': False}
