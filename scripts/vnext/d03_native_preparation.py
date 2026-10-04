"""Complete current D03 request selection before any native or live execution.

This is an offline input boundary. It gives the future native route one exact
effective request per complete saved-source group, but grants no response,
Candidate, Result, Run, or provider-call credit.
"""
from pathlib import Path

from .canonical import content_hash
from .continuous_request_context import FORMAT_VERSION
from .normal_source_authority import ROOT
from .r6_regulatory_semantics import (
    prepare_regulatory_semantic_source, requests_from_source)
from .regulatory_fact_review import VERSION as ANCHOR_VERSION, candidate_request


VERSION = 'D03_NATIVE_PREPARATION_V1'


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def prepare_native_input(*, company_id, repo_root=ROOT):
    """Select the bounded successor only where the old source-fact override exists."""
    _need(Path(repo_root).resolve() == ROOT,
          'D03_NATIVE_PREPARATION_CODE_ROOT_CHANGED')
    source = prepare_regulatory_semantic_source(repo_root=ROOT,
        company_id=company_id, request_context_format=FORMAT_VERSION)
    originals = requests_from_source(source)
    _need(bool(originals) and [unit['unit_id'] for request in originals
        for unit in request['units']] == source['required_unit_ids'],
        'D03_NATIVE_PREPARATION_SOURCE_PARTITION_CHANGED')
    groups = []
    for index, original in enumerate(originals):
        anchored = bool(original['source_statement_facts'])
        effective = (candidate_request(original, source=source)
                     if anchored else original)
        _need(effective['source_id'] == source['semantic_source_id']
              and effective['company_id'] == company_id
              and effective['units'] == original['units']
              and effective['required_candidate_assessments'] ==
                  original['required_candidate_assessments']
              and (not anchored or (
                  'source_statement_facts' not in effective
                  and effective['source_fact_review_contract']['version'] ==
                      ANCHOR_VERSION
                  and effective['source_fact_review_contract'][
                      'original_request_id'] == original['request_id'])),
              'D03_NATIVE_PREPARATION_EFFECTIVE_REQUEST_CHANGED')
        groups.append({'group_index': index,
            'original_request_id': original['request_id'],
            'effective_request_id': effective['request_id'],
            'source_anchor_successor': anchored,
            'unit_ids': [unit['unit_id'] for unit in original['units']],
            'effective_request': effective})
    _need(len({row['original_request_id'] for row in groups}) == len(groups)
          and len({row['effective_request_id'] for row in groups}) == len(groups),
          'D03_NATIVE_PREPARATION_REQUEST_ID_COLLISION')
    body = {'record_type': VERSION, 'company_id': company_id,
        'source_id': source['semantic_source_id'],
        'request_context_format': FORMAT_VERSION,
        'group_mapping': [{key: row[key] for key in (
            'group_index', 'original_request_id', 'effective_request_id',
            'source_anchor_successor', 'unit_ids')} for row in groups],
        'complete_source_unit_ids': source['required_unit_ids'],
        'provider_request_sent': False, 'native_result_created': False,
        'production_authorized': False}
    return {**body, 'input_id': content_hash(value=body),
        'source': source, 'groups': groups}
