"""Fresh D04 source interpretations; old feasibility responses stay diagnostic."""
from copy import deepcopy
import re

from .canonical import content_hash, strict_json_file, strict_json_loads, sha256_file
from .capacity_semantic_review import shared_source_groups, _shared_units, _restore_units
from .capacity_utilization_source import need
from .normal_source_authority import ROOT
from .r6_semantic_review import _source_items, _validate_source_response
from .r6_semantic_source import _bytes

POLICY_PATH = 'catalog/r6/semantic_review_v4.json'
SPEC_PATH = 'catalog/r6/D04_going_concern_assessment_v1.md'
CURRENT_KINDS = {'DOUBT_DISCLOSED', 'DOUBT_ALLEVIATED', 'NO_DOUBT_DECLARATION'}


def native_source(source, *, historical_control=False):
    """A new input identity, retaining the exact complete original source set."""
    expected = 'D04_HISTORICAL_PRIMARY_CONTROL_SOURCE' if historical_control else 'D04_COMPLETE_SEMANTIC_SOURCE'
    need(source['record_type'] == expected
         and source['semantic_source_id'] == content_hash(value={
             k: v for k, v in source.items() if k != 'semantic_source_id'}), 'D04_NATIVE_COMPLETE_SOURCE_REQUIRED')
    body = {k: v for k, v in source.items() if k != 'semantic_source_id'}
    if historical_control:
        need(source['normal_update_input'] is False and source['control_scope'] ==
             'EXACT_HISTORICAL_PRIMARY_AND_HEADER_ONLY_NOT_LATEST_ANNUAL_OR_WHOLE_FILING',
             'D04_NATIVE_CONTROL_SCOPE_CHANGED')
    body.update(record_type='D04_NATIVE_HISTORICAL_CONTROL_SOURCE' if historical_control else 'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE',
                original_complete_source_id=source['semantic_source_id'],
                source_check_scope=source['control_scope'] if historical_control else
                    'SAVED_ANNUAL_PRIMARY_AND_ALL_CURRENT_ANNUAL_AMENDMENTS_VISIBLE_AND_NATIVE')
    return {**body, 'semantic_source_id': content_hash(value=body)}


def requests_from_source(source):
    rules = strict_json_file(path=ROOT / POLICY_PATH)
    need(source['record_type'] in {'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE', 'D04_NATIVE_HISTORICAL_CONTROL_SOURCE'}
         and source['source_serialization_complete'] is True
         and source['semantic_source_id'] == content_hash(value={
             k: v for k, v in source.items() if k != 'semantic_source_id'}), 'D04_NATIVE_COMPLETE_SOURCE_REQUIRED')
    need(source['required_unit_ids'] == [u['unit_id'] for u in source['units']]
         and len(set(source['required_unit_ids'])) == len(source['units']), 'D04_NATIVE_UNIT_SET_CHANGED')
    documents = {d['document_id']: d for d in source['documents']}
    annual = source['prepared_annual_input']; requests = []
    for group in shared_source_groups(source['units'], rules['max_group_source_bytes']):
        packed, shared = _shared_units(group)
        need(len(_bytes([packed, shared])) <= rules['max_group_source_bytes'], 'D04_NATIVE_SOURCE_GROUP_EXCEEDS_BOUND')
        doc = documents[group[0]['document_id']]; required = []
        for unit in group:
            kind, items = _source_items(unit)
            indices = (doc['language_candidate_block_indices'] if kind == 'VISIBLE_BLOCK' else
                       doc['native_candidate_ordinals'] if kind == 'NATIVE_FACT' else [])
            required.extend({'unit_id': unit['unit_id'], 'kind': kind, 'source_index': i}
                            for i in indices if i in items)
        body = {'record_type': 'D04_NATIVE_INTERPRETATION_REQUEST', 'metric_id': 'D04',
            'native_evidence_requested': True, 'source_id': source['semantic_source_id'],
            'company_id': source['company_id'], 'target_cik': annual['entity'],
            'target_period': annual['table_input']['target_period'],
            'fiscal_label_context': {k: annual['fiscal_year_label_resolution'][k] for k in
                ('selected_fiscal_year', 'basis', 'original_dei_fiscal_year',
                 'original_companyfacts_fiscal_year_values', 'metadata_conflict_retained')},
            'document_context': {k: doc[k] for k in ('document_id', 'filing', 'registrant_name_binding')},
            'system_prompt': rules['system_prompt'], 'units': packed, 'shared_source_dictionaries': shared,
            'category_definitions': rules['category_definitions'], 'required_candidate_assessments': required,
            'response_protocol': rules['response_protocol'], 'policy_sha256': sha256_file(path=ROOT / POLICY_PATH),
            'provider_request_sent': False, 'provider_tokens_measured': False, 'production_authorized': False}
        if source['record_type'] == 'D04_NATIVE_HISTORICAL_CONTROL_SOURCE':
            body.update(historical_control=source['control'], control_source_scope=source['control_scope'])
            body['system_prompt'] += (' This request is a historical primary/header-only control. CURRENT_REPORT refers '
                'to the supplied historical report. It cannot establish current-company status or whole-filing absence.')
        requests.append({**body, 'request_id': content_hash(value=body)})
    need([u['unit_id'] for r in requests for u in r['units']] == source['required_unit_ids'],
         'D04_NATIVE_REQUEST_CENSUS_CHANGED')
    return requests


def validate_response(*, request, raw_response):
    rules = strict_json_file(path=ROOT / POLICY_PATH)
    need(request['request_id'] == content_hash(value={k: v for k, v in request.items() if k != 'request_id'})
         and request['policy_sha256'] == sha256_file(path=ROOT / POLICY_PATH)
         and request['response_protocol'] == rules['response_protocol'], 'D04_NATIVE_REQUEST_POLICY_CHANGED')
    need(type(raw_response) is bytes and len(raw_response) <= rules['max_response_bytes'], 'D04_NATIVE_RESPONSE_SIZE')
    original = strict_json_loads(text=raw_response.decode('utf-8'))
    need(type(original) is dict and original.get('request_id') == request['request_id'], 'D04_NATIVE_RESPONSE_REQUEST_CHANGED')
    resolved = deepcopy(original)
    units = _restore_units(request['units'], request['shared_source_dictionaries'])
    by_id = {u['unit_id']: u for u in units}
    need(type(resolved.get('units')) is list, 'D04_NATIVE_RESPONSE_UNITS_REQUIRED')
    for row in resolved['units']:
        need(type(row) is dict and row.get('unit_id') in by_id and type(row.get('findings')) is list,
             'D04_NATIVE_REFERENCE_UNIT_CHANGED')
        kind, items = _source_items(by_id[row['unit_id']])
        for finding in row['findings']:
            need(type(finding) is dict and type(finding.get('evidence')) is list, 'D04_NATIVE_REFERENCE_FIELDS')
            for evidence in finding['evidence']:
                need(type(evidence) is dict and set(evidence) == {'kind', 'source_index'}
                     and evidence['kind'] == kind and type(evidence['source_index']) is int
                     and evidence['source_index'] in items, 'D04_NATIVE_REFERENCE_OUTSIDE_SOURCE')
                item = items[evidence['source_index']]
                evidence['text'] = item['raw_xml'] if kind == 'NATIVE_SUPPLEMENT' else item['text']
    body = {k: v for k, v in request.items() if k != 'request_id'}
    body.update(units=units, document_context={**body['document_context'],
                'language_candidate_block_indices': [], 'native_candidate_ordinals': []})
    restored = {**body, 'request_id': content_hash(value=body)}
    checked = _validate_source_response(request=restored,
        raw_response=_bytes({**resolved, 'request_id': restored['request_id']}),
        policy={**rules, 'current_target_kinds': [], 'max_response_bytes': rules['host_reference_max_bytes'],
                'max_quote_characters': rules['host_reference_max_quote_characters']})
    required = {(r['unit_id'], r['kind'], r['source_index']) for r in request['required_candidate_assessments']}
    accounted = {(f['unit_id'], e['kind'], e['source_index']) for f in checked['findings'] for e in f['resolved_evidence']}
    need(required <= accounted, 'D04_NATIVE_KNOWN_CANDIDATE_NOT_ASSESSED')
    for finding in checked['findings']:
        if (finding['kind'] not in CURRENT_KINDS or finding['subject'] != 'TARGET_REGISTRANT'
                or finding['timing'] != 'CURRENT_REPORT'):
            continue
        _, items = _source_items(by_id[finding['unit_id']])
        need(not any(e['kind'] == 'VISIBLE_BLOCK' and items[e['source_index']]['html_quotation_context']
                     for e in finding['resolved_evidence']), 'D04_QUOTED_TEXT_CANNOT_ALONE_ESTABLISH_CURRENT_ASSERTION')
        # This is a necessary content check, never positive semantic proof.
        # A clean opinion, valuation uncertainty or absence of a cyber risk is
        # not itself an explicit going-concern assessment.
        text = ' '.join(e['text'] for e in finding['resolved_evidence'])
        need(re.search(r'\bgoing[\s-]+concern\b|\bcontinu(?:e|ing|ation)\b.{0,80}\b(?:operat\w*|business)\b',
                       text, re.I | re.S) is not None, 'D04_EXPLICIT_GOING_CONCERN_ASSERTION_NOT_ESTABLISHED')
    checked.update(request_id=request['request_id'], response=original,
        current_target_findings=[f for f in checked['findings'] if f['kind'] in CURRENT_KINDS
                                 and f['subject'] == 'TARGET_REGISTRANT' and f['timing'] == 'CURRENT_REPORT'])
    return checked


def build_acceptance(*, prepared, plan, response_body):
    from pathlib import Path
    from .capacity_native_assessment import _build_acceptance
    request = strict_json_loads(text=prepared.request_bytes.decode())
    need(request['record_type'] == 'D04_NATIVE_INTERPRETATION_REQUEST'
         and request['metric_id'] == 'D04' and request['native_evidence_requested'] is True,
         'D04_FRESH_NATIVE_REQUEST_REQUIRED')
    return _build_acceptance(prepared=prepared, plan=plan, response_body=response_body,
        checked=validate_response(request=request, raw_response=response_body), metric_id='D04',
        group='d04_going_concern_source_assessment_v1', spec_path=SPEC_PATH, validator_path=Path(__file__))
