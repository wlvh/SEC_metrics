"""Recheck a complete D03 response set without granting native result credit.

The source and effective requests are rebuilt before any response is read.
Recorded or unbound response bytes can establish parser behavior, never a
provider execution, business conclusion, or native Run.
"""
from pathlib import Path

from .canonical import content_hash, sha256_bytes, strict_json_loads
from .d03_native_preparation import prepare_native_input
from .normal_source_authority import ROOT
from .r6_regulatory_semantics import requests_from_source, validate_response
from .regulatory_fact_review import validate_candidate_response


VERSION = 'D03_COMPLETE_INTERPRETATION_PROPOSAL_V1'
RECORDED_BRIDGE_VERSION = 'D03_RECORDED_COMPLETE_INTERPRETATION_V1'


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _finding_needs_review(finding, context_only):
    # V6 materializes context_only_source_indices as OTHER_MEANING findings.
    # Their subject/time placeholders do not describe an action. An explicit
    # unresolved item or an action whose subject/time is unknown still blocks.
    if finding['kind'] == 'UNRESOLVED':
        return True
    if (finding['kind'] == 'OTHER_MEANING'
            and finding.get('reported_status') == 'NOT_AN_ACTION_STATEMENT'
            and len(finding['evidence']) == 1):
        reference = finding['evidence'][0]
        if (finding['unit_id'], reference['source_index']) in context_only:
            return False
    return finding['subject'] == 'UNRESOLVED' or finding['timing'] == 'UNRESOLVED'


def validate_complete_interpretation(*, prepared_input, response_bytes_by_request,
                                     repo_root=ROOT):
    """Return source-linked model proposals; do not create Candidate/Result/Run."""
    _need(Path(repo_root).resolve() == ROOT
          and type(prepared_input) is dict
          and type(response_bytes_by_request) is dict,
          'D03_COMPLETE_INTERPRETATION_INPUT_INVALID')
    _need(type(prepared_input.get('company_id')) is str,
          'D03_COMPLETE_INTERPRETATION_INPUT_INVALID')
    responses = dict(response_bytes_by_request)
    expected = prepare_native_input(company_id=prepared_input['company_id'])
    _need(prepared_input == expected,
          'D03_COMPLETE_INTERPRETATION_PREPARATION_CHANGED')
    groups = expected['groups']
    ids = {row['effective_request_id'] for row in groups}
    _need(set(responses) == ids
          and all(type(raw) is bytes
                  for raw in responses.values()),
          'D03_COMPLETE_INTERPRETATION_RESPONSE_SET_CHANGED')
    originals = requests_from_source(expected['source'])
    _need(len(originals) == len(groups),
          'D03_COMPLETE_INTERPRETATION_GROUP_SET_CHANGED')
    rows = []
    context_only_by_group = []
    for original, group in zip(originals, groups):
        _need(original['request_id'] == group['original_request_id'],
              'D03_COMPLETE_INTERPRETATION_ORIGINAL_REQUEST_CHANGED')
        request = group['effective_request']
        raw = responses[group['effective_request_id']]
        if group['source_anchor_successor']:
            checked = validate_candidate_response(
                original_request=original, source=expected['source'],
                request=request, raw_response=raw, repo_root=ROOT)
            _need(checked['source_fact_current_status_proven_by_program'] is False,
                  'D03_COMPLETE_INTERPRETATION_OLD_FACT_CREDIT_RESTORED')
        else:
            _need(not original['source_statement_facts'] and request == original,
                  'D03_COMPLETE_INTERPRETATION_UNSAFE_ORIGINAL_REQUEST')
            checked = validate_response(request=request, raw_response=raw)
        context_only = {(unit['unit_id'], index)
            for unit in checked.get('provider_response', {}).get('units', [])
            for index in unit.get('context_only_source_indices', [])}
        context_only_by_group.append(context_only)
        rows.append({'group_index': group['group_index'],
            'request_id': request['request_id'],
            'unit_ids': group['unit_ids'],
            'response_sha256': sha256_bytes(content=raw),
            'source_anchor_successor': group['source_anchor_successor'],
            'findings': checked['findings'],
            'unresolved': checked['unresolved']})
    unresolved = [row['group_index'] for row, context_only in
        zip(rows, context_only_by_group) if row['unresolved']
        or any(_finding_needs_review(finding, context_only)
               for finding in row['findings'])]
    proposals = [finding for row in rows for finding in row['findings']
        if finding['kind'] == 'CURRENT_REGULATORY_ACTION'
        and finding['subject'] == 'TARGET_REGISTRANT'
        and finding['reported_status'] == 'ONGOING_AS_REPORTED']
    body = {'record_type': VERSION, 'company_id': expected['company_id'],
        'source_id': expected['source_id'], 'input_id': expected['input_id'],
        'group_rows': rows, 'unresolved_group_indices': unresolved,
        'proposed_current_findings': proposals,
        'proposed_branch': ('UNRESOLVED_REQUIRES_REVIEW' if unresolved else
            'CURRENT_DISCLOSURE_REQUIRES_NATIVE_REVIEW' if proposals else
            'ABSENCE_RULE_NOT_APPROVED'),
        'provider_execution_identity_verified': False,
        'native_candidate_or_evidence_created': False,
        'native_result_or_run_created': False,
        'production_authorized': False}
    return {**body, 'proposal_id': content_hash(value=body)}


def replay_recorded_complete_interpretation(*, packet_root, expected_packet_id,
                                            company_id, repo_root=ROOT):
    """Bind an authenticated offline response set to the complete proposal.

    The packet indexes raw bytes by original request ID. Current preparation
    may use a distinct successor request for a group with old source facts, so
    the one-to-one mapping is rechecked before interpretation. This is never a
    provider receipt or native Candidate/Result/Run.
    """
    from .d03_recorded_response_set import replay_offline_set

    _need(Path(repo_root).resolve() == ROOT and type(company_id) is str
          and bool(company_id) and type(expected_packet_id) is str
          and bool(expected_packet_id),
          'D03_RECORDED_INTERPRETATION_INPUT_INVALID')
    packet = replay_offline_set(packet_root=packet_root,
                                expected_packet_id=expected_packet_id)
    metadata = strict_json_loads(text=(Path(packet_root) / 'packet.json')
                                 .read_text(encoding='utf-8'))
    prepared = prepare_native_input(company_id=company_id)
    groups = prepared['groups']
    original_ids = [row['original_request_id'] for row in groups]
    effective_ids = [row['effective_request_id'] for row in groups]
    _need(metadata['packet_id'] == packet['packet_id'] == expected_packet_id
          and metadata['company_id'] == company_id
          and metadata['source_id'] == prepared['source_id']
          and packet['request_count'] == len(groups)
          and len(set(original_ids)) == len(original_ids)
          and len(set(effective_ids)) == len(effective_ids)
          and set(packet['raw_response_bytes']) == set(original_ids),
          'D03_RECORDED_INTERPRETATION_PACKET_OR_REQUEST_CHANGED')
    responses = {group['effective_request_id']:
                 packet['raw_response_bytes'][group['original_request_id']]
                 for group in groups}
    checked = validate_complete_interpretation(prepared_input=prepared,
        response_bytes_by_request=responses)
    _need(checked['source_id'] == prepared['source_id']
          and checked['input_id'] == prepared['input_id']
          and checked['provider_execution_identity_verified'] is False
          and checked['native_candidate_or_evidence_created'] is False
          and checked['native_result_or_run_created'] is False
          and packet['calls'] == [0, 0, 0]
          and packet['native_result_created'] is False,
          'D03_RECORDED_INTERPRETATION_CREDIT_CHANGED')
    body = {'record_type': RECORDED_BRIDGE_VERSION,
        'recorded_packet_id': expected_packet_id,
        'company_id': company_id, 'source_id': prepared['source_id'],
        'prepared_input_id': prepared['input_id'],
        'request_mapping': [{key: group[key] for key in (
            'group_index', 'original_request_id', 'effective_request_id',
            'source_anchor_successor')} for group in groups],
        'interpretation_proposal_id': checked['proposal_id'],
        'group_count': len(groups),
        'unresolved_group_indices': checked['unresolved_group_indices'],
        'proposed_branch': checked['proposed_branch'],
        'provider_execution_identity_verified': False,
        'native_result_or_run_created': False,
        'calls': [0, 0, 0], 'production_authorized': False}
    return {**body, 'record_id': content_hash(value=body),
            'interpretation': checked}
