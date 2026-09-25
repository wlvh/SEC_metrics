"""Offline D03 successor: source anchors are review candidates, not verdicts.

The existing D03 request and its historical source-fact behavior stay exact.
This module deliberately has no provider execution entry. A later explicit
request authority must bind this successor before any real call is possible.
"""
from copy import deepcopy

from .canonical import canonical_json_bytes, content_hash, strict_json_file, strict_json_loads
from .normal_source_authority import ROOT

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
    'For each candidate_id return one candidate_reviews row naming the unit and all '
    'finding_indices that assess its exact statement. Do not reuse one finding index for '
    'different candidates. Include every finding citing a candidate block in one review. '
    'Give each candidate a cited finding, including UNRESOLVED when subject, time or resolution '
    'cannot be established. Never silently place a candidate in context_only_source_indices. '
    'Preserve conflicts and uncertainty; do not infer guilt, case count or an absence conclusion.')


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _authenticated_original(*, original, source, repo_root):
    from .r6_regulatory_semantics import (prepare_regulatory_semantic_source,
                                          requests_from_source)
    _need(type(source) is dict and type(source.get('company_id')) is str,
          'D03_ANCHOR_AUTHENTIC_SOURCE_REQUIRED')
    rebuilt = prepare_regulatory_semantic_source(repo_root=repo_root,
        company_id=source['company_id'],
        request_context_format=source.get('request_context_format'))
    _need(source == rebuilt and original in requests_from_source(rebuilt),
          'D03_ANCHOR_AUTHENTIC_ORIGINAL_REQUIRED')


def candidate_request(original, *, source, repo_root=ROOT):
    """Replace semantic source-fact credit with exact mechanical anchors."""
    from .r6_semantic_review import _source_items
    _authenticated_original(original=original, source=source, repo_root=repo_root)
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
    protocol = deepcopy(body['response_protocol'])
    protocol['root_fields'] = [*protocol['root_fields'], 'candidate_reviews']
    protocol['candidate_review_fields'] = ['candidate_id', 'unit_id', 'finding_indices']
    protocol['json_schema']['properties']['candidate_reviews'] = {
        'type': 'array', 'items': {'type': 'object', 'properties': {
            'candidate_id': {'type': 'string'}, 'unit_id': {'type': 'string'},
            'finding_indices': {'type': 'array', 'minItems': 1,
                                'items': {'type': 'integer', 'minimum': 0}}},
            'required': ['candidate_id', 'unit_id', 'finding_indices'],
            'additionalProperties': False}}
    protocol['json_schema']['required'].append('candidate_reviews')
    body['response_protocol'] = protocol
    body['source_fact_review_contract'] = {
        'version': VERSION, 'original_request_id': original['request_id'],
        'source_statement_facts_hash': content_hash(value=original['source_statement_facts'])}
    return {**body, 'request_id': content_hash(value=body)}


def validate_candidate_response(*, original_request, source, request, raw_response,
                                repo_root=ROOT):
    """Keep citations strict; unresolved semantics never become a proven fact."""
    _need(request == candidate_request(original_request, source=source,
                                       repo_root=repo_root),
          'D03_ANCHOR_REQUEST_NOT_SOURCE_BOUND')
    from .r6_regulatory_semantics import POLICY_PATH
    _need(type(raw_response) is bytes and len(raw_response) <=
          strict_json_file(path=ROOT / POLICY_PATH)['max_response_bytes'],
          'D03_ANCHOR_RESPONSE_SIZE_OR_TYPE')
    response = strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(response) is dict and set(response) == {'request_id', 'units', 'candidate_reviews'}
          and type(response['units']) is list and type(response['candidate_reviews']) is list,
          'D03_ANCHOR_RESPONSE_INVALID')
    _need(all(type(row) is dict for row in response['units']),
          'D03_ANCHOR_RESPONSE_UNIT_MISSING_OR_DUPLICATED')
    units = {row.get('unit_id'): row for row in response['units']}
    _need(len(units) == len(response['units']), 'D03_ANCHOR_RESPONSE_UNIT_MISSING_OR_DUPLICATED')
    anchors = {anchor['candidate_id']: anchor for anchor in request['source_fact_candidates']}
    _need(len(anchors) == len(request['source_fact_candidates']),
          'D03_ANCHOR_CANDIDATE_ID_DUPLICATED')
    reviews = {}
    used = set()
    for review in response['candidate_reviews']:
        _need(type(review) is dict and set(review) ==
              {'candidate_id', 'unit_id', 'finding_indices'}
              and type(review['candidate_id']) is str
              and review['candidate_id'] in anchors
              and review['candidate_id'] not in reviews
              and review['unit_id'] == anchors[review['candidate_id']]['unit_id']
              and type(review['finding_indices']) is list
              and bool(review['finding_indices']),
              'D03_ANCHOR_CANDIDATE_REVIEW_INVALID')
        anchor = anchors[review['candidate_id']]
        row = units.get(anchor['unit_id'])
        _need(type(row) is dict and type(row.get('findings')) is list,
              'D03_ANCHOR_RESPONSE_UNIT_MISSING_OR_DUPLICATED')
        _need(anchor['block_index'] not in row.get('context_only_source_indices', []),
              'D03_ANCHOR_CANNOT_BE_CONTEXT_ONLY')
        for index in review['finding_indices']:
            _need(type(index) is int and 0 <= index < len(row['findings'])
                  and (anchor['unit_id'], index) not in used,
                  'D03_ANCHOR_FINDING_REUSED_OR_MISSING')
            finding = row['findings'][index]
            _need(type(finding) is dict and type(finding.get('evidence')) is list
                  and any(type(evidence) is dict
                      and evidence.get('kind') == 'VISIBLE_BLOCK'
                      and evidence.get('source_index') == anchor['block_index']
                      for evidence in finding['evidence']),
                  'D03_ANCHOR_CANDIDATE_UNASSESSED')
            used.add((anchor['unit_id'], index))
        reviews[review['candidate_id']] = review
    _need(set(reviews) == set(anchors), 'D03_ANCHOR_CANDIDATE_UNASSESSED')
    for anchor in anchors.values():
        row = units[anchor['unit_id']]
        cited = {i for i, finding in enumerate(row['findings'])
                 if type(finding) is dict and type(finding.get('evidence')) is list
                 and any(type(evidence) is dict and evidence.get('kind') == 'VISIBLE_BLOCK'
                     and evidence.get('source_index') == anchor['block_index']
                     for evidence in finding['evidence'])}
        _need(all((anchor['unit_id'], index) in used for index in cited),
              'D03_ANCHOR_CITED_FINDING_UNASSIGNED')
    from .r6_regulatory_semantics import validate_response
    checked = validate_response(request=request, raw_response=canonical_json_bytes(
        value={key: value for key, value in response.items()
               if key != 'candidate_reviews'}))
    uncertain = []
    for anchor in request['source_fact_candidates']:
        review = reviews[anchor['candidate_id']]
        row = units[anchor['unit_id']]
        matching = [row['findings'][index] for index in review['finding_indices']]
        if len(matching) != 1 or not all(
                finding['kind'] == 'CURRENT_REGULATORY_ACTION'
                and finding['reported_status'] == 'ONGOING_AS_REPORTED'
                and finding['subject'] == 'TARGET_REGISTRANT'
                for finding in matching):
            uncertain.append({'candidate_id': anchor['candidate_id'],
                              'reason': 'SUBJECT_TIME_OR_RESOLUTION_REQUIRES_SEMANTIC_REVIEW'})
    return {**checked, 'unresolved': [*checked['unresolved'], *uncertain],
            'source_fact_candidate_review': uncertain,
            'candidate_reviews': response['candidate_reviews'],
            'source_fact_current_status_proven_by_program': False,
            'native_result_created': False}
