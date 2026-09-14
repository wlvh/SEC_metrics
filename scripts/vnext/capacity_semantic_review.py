"""Complete B13 interpretation with shared, losslessly restored XML metadata.

Grouping changes neither the source set nor its meaning. All original units,
including units without navigation hits, must be assessed. This module only
checks proposals; native Evidence and the effective Review own result credit.
"""
from copy import deepcopy
from collections import Counter
import re

from .canonical import content_hash, sha256_file, strict_json_file
from .capacity_utilization_source import need
from .normal_source_authority import ROOT
from .r6_semantic_source import _bytes
from .r6_semantic_review import _validate_source_response

POLICY_PATH = 'catalog/r5/capacity_semantic_review_v3.json'
_MAPS = ('contexts', 'units', 'namespace_environments')
_STYLE = re.compile(r'\bstyle=(?:"[^"]*"|\x27[^\x27]*\x27)', re.I)
_STYLE_REF = re.compile(r'data-b13-style-ref="(\d+)"')


def _xml_values(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'raw_xml' and isinstance(child, str):
                yield value, key
            elif isinstance(child, (dict, list)):
                yield from _xml_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _xml_values(child)


def _share_xml_styles(packed, shared):
    """Replace repeated literal style attributes, retaining every CSS byte."""
    locations = list(_xml_values([packed, shared]))
    counts = Counter(match.group() for obj, key in locations for match in _STYLE.finditer(obj[key]))
    styles = sorted(text for text, count in counts.items() if count > 1 and len(text) > 48)
    by_text = {text: str(i) for i, text in enumerate(styles)}
    for obj, key in locations:
        need('data-b13-style-ref=' not in obj[key], 'B13_SOURCE_RESERVED_STYLE_MARKER')
        obj[key] = _STYLE.sub(lambda m: 'data-b13-style-ref="' + by_text[m.group()] + '"'
                             if m.group() in by_text else m.group(), obj[key])
    shared['xml_style_attributes'] = {str(i): text for i, text in enumerate(styles)}


def _pack_rows(unit):
    """Declare repeated field names once; preserve every original field value."""
    payload = unit['payload']
    name = 'blocks' if unit['kind'] == 'VISIBLE_TEXT' else 'facts' if unit['kind'] == 'NATIVE_FACTS' else None
    if name is None or not payload[name]:
        return
    rows = payload[name]
    columns = sorted(rows[0])
    if not all(set(row) == set(columns) for row in rows):
        return
    layout = {'columns': columns}
    if name == 'facts':
        fact_columns = sorted(rows[0]['fact'])
        if all(set(row['fact']) == set(fact_columns) for row in rows):
            layout['fact_columns'] = fact_columns
            for row in rows:
                row['fact'] = [row['fact'][key] for key in fact_columns]
    payload[name] = [[row[key] for key in columns] for row in rows]
    payload['row_layout'] = layout


def _restore_rows(unit):
    payload = unit['payload']
    layout = payload.pop('row_layout', None)
    if layout is None:
        return
    name = 'blocks' if unit['kind'] == 'VISIBLE_TEXT' else 'facts'
    columns = layout['columns']
    need(len(columns) == len(set(columns)) and all(len(row) == len(columns) for row in payload[name]),
         'B13_PACKED_ROW_FIELDS_CHANGED')
    payload[name] = [dict(zip(columns, row)) for row in payload[name]]
    if 'fact_columns' in layout:
        columns = layout['fact_columns']
        need(len(columns) == len(set(columns)) and all(len(row['fact']) == len(columns) for row in payload[name]),
             'B13_PACKED_FACT_FIELDS_CHANGED')
        for row in payload[name]:
            row['fact'] = dict(zip(columns, row['fact']))


def _shared_units(units):
    """Share exact namespace/context/unit dictionaries within one document."""
    shared = {kind: {} for kind in _MAPS}
    packed = [deepcopy(unit) for unit in units]

    def add(kind, key, value):
        need(key not in shared[kind] or shared[kind][key] == value,
             'B13_SHARED_SOURCE_ID_COLLISION')
        shared[kind][key] = value

    for unit in packed:
        payload = unit['payload']
        if unit['kind'] == 'NATIVE_FACTS':
            for kind in _MAPS:
                values = payload[kind]
                for key, value in values.items():
                    add(kind, key, value)
                payload[kind] = sorted(values)
        elif unit['kind'] == 'NATIVE_SUPPLEMENTS':
            for outer in payload['objects']:
                for obj in [outer, *outer['nested_objects']]:
                    key = obj['namespace_environment_id']
                    add('namespace_environments', key, obj.pop('namespaces'))
    _share_xml_styles(packed, shared)
    for unit in packed:
        _pack_rows(unit)
    need(_restore_units(packed, shared) == units, 'B13_PACKED_SOURCE_ROUNDTRIP_CHANGED')
    return packed, shared


def _restore_units(packed, shared):
    units = deepcopy(packed)
    shared = deepcopy(shared)
    styles = shared['xml_style_attributes']
    for obj, key in _xml_values([units, shared]):
        obj[key] = _STYLE_REF.sub(lambda m: styles[m.group(1)], obj[key])
    for unit in units:
        _restore_rows(unit)
        payload = unit['payload']
        if unit['kind'] == 'NATIVE_FACTS':
            for kind in _MAPS:
                payload[kind] = {key: shared[kind][key] for key in payload[kind]}
        elif unit['kind'] == 'NATIVE_SUPPLEMENTS':
            for outer in payload['objects']:
                for obj in [outer, *outer['nested_objects']]:
                    obj['namespaces'] = shared['namespace_environments'][obj['namespace_environment_id']]
    return units


def requests_from_source(source):
    rules = strict_json_file(path=ROOT / POLICY_PATH)
    need(source['record_type'] == 'B13_COMPLETE_SEMANTIC_SOURCE'
         and source['source_serialization_complete'] is True
         and source['semantic_source_id'] == content_hash(value={
             k: v for k, v in source.items() if k != 'semantic_source_id'}),
         'B13_COMPLETE_SOURCE_REQUIRED')
    need(source['required_unit_ids'] == [u['unit_id'] for u in source['units']]
         and len(set(source['required_unit_ids'])) == len(source['units']),
         'B13_SOURCE_UNIT_SET_CHANGED')
    groups, current = [], []
    for unit in source['units']:
        if current and unit['document_id'] != current[0]['document_id']:
            groups.append(current)
            current = []
        trial = current + [unit]
        packed, shared = _shared_units(trial)
        if current and len(_bytes([packed, shared])) > rules['max_group_source_bytes']:
            groups.append(current)
            current = [unit]
        else:
            current = trial
    if current:
        groups.append(current)
    documents = {d['document_id']: d for d in source['documents']}
    annual = source['prepared_annual_input']
    requests = []
    for group in groups:
        packed, shared = _shared_units(group)
        need(len(_bytes([packed, shared])) <= rules['max_group_source_bytes'],
             'B13_SOURCE_GROUP_EXCEEDS_BOUND')
        document = documents[group[0]['document_id']]
        ids = {u['unit_id'] for u in group}
        body = {'record_type': 'B13_INTERPRETATION_REQUEST', 'metric_id': 'B13',
                'source_id': source['semantic_source_id'], 'company_id': source['company_id'],
                'target_cik': annual['entity'], 'target_period': annual['table_input']['target_period'],
                'fiscal_label_context': {k: annual['fiscal_year_label_resolution'][k] for k in
                    ('selected_fiscal_year', 'basis', 'original_dei_fiscal_year',
                     'original_companyfacts_fiscal_year_values', 'metadata_conflict_retained')},
                'document_context': {k: document[k] for k in
                    ('document_id', 'filing', 'registrant_name_binding')},
                'system_prompt': rules['system_prompt'], 'units': packed,
                'shared_source_dictionaries': shared,
                'category_definitions': rules['category_definitions'],
                'required_candidate_assessments': [r for r in source['capacity_navigation'] if r['unit_id'] in ids],
                'native_capacity_role_assessments': [r for r in source['native_capacity_role_assessments'] if r['unit_id'] in ids],
                'response_protocol': rules['response_protocol'],
                'policy_sha256': sha256_file(path=ROOT / POLICY_PATH),
                'provider_request_sent': False, 'provider_tokens_measured': False,
                'production_authorized': False}
        requests.append({**body, 'request_id': content_hash(value=body)})
    need([u['unit_id'] for r in requests for u in r['units']] == source['required_unit_ids'],
         'B13_REQUEST_COVERAGE_CHANGED')
    return requests


def validate_response(*, request, raw_response):
    """Restore source bytes and reuse the established exact quotation checks."""
    need(request['request_id'] == content_hash(value={
        k: v for k, v in request.items() if k != 'request_id'}), 'B13_REQUEST_CHANGED')
    rules = strict_json_file(path=ROOT / POLICY_PATH)
    need(type(raw_response) is bytes and len(raw_response) <= rules['max_response_bytes'],
         'B13_RESPONSE_SIZE_OR_TYPE')
    need(request['policy_sha256'] == sha256_file(path=ROOT / POLICY_PATH)
         and request['response_protocol'] == rules['response_protocol'], 'B13_REVIEW_POLICY_CHANGED')
    units = _restore_units(request['units'], request['shared_source_dictionaries'])
    # The generic checker binds the restored host request. Preserve the actual
    # request identity when checking the provider's original response first.
    from .canonical import strict_json_loads
    response = strict_json_loads(text=raw_response.decode('utf-8'))
    need(type(response) is dict and response.get('request_id') == request['request_id'], 'B13_RESPONSE_REQUEST_CHANGED')
    resolved = deepcopy(response)
    from .r6_semantic_review import _source_items
    by_id = {u['unit_id']: u for u in units}
    need(type(resolved.get('units')) is list, 'B13_RESPONSE_UNITS_REQUIRED')
    for row in resolved['units']:
        need(type(row) is dict and row.get('unit_id') in by_id and type(row.get('findings')) is list,
             'B13_REFERENCE_UNIT_CHANGED')
        kind, items = _source_items(by_id[row['unit_id']])
        for finding in row['findings']:
            need(type(finding) is dict and type(finding.get('evidence')) is list, 'B13_REFERENCE_FIELDS_CHANGED')
            for evidence in finding['evidence']:
                need(type(evidence) is dict and set(evidence) == {'kind', 'source_index'}
                     and evidence['kind'] == kind and type(evidence['source_index']) is int
                     and evidence['source_index'] in items, 'B13_REFERENCE_OUTSIDE_SUPPLIED_SOURCE')
                item = items[evidence['source_index']]
                evidence['text'] = item['raw_xml'] if kind == 'NATIVE_SUPPLEMENT' else item['text']
    body = {k: v for k, v in request.items() if k != 'request_id'}
    body['units'] = units
    body['document_context'] = {**body['document_context'],
        'language_candidate_block_indices': [], 'native_candidate_ordinals': []}
    restored = {**body, 'request_id': content_hash(value=body)}
    # These larger bounds apply only to host-recovered originals. The provider
    # response above retains its existing 262144-byte limit and 4096 tokens.
    host_rules = {**rules, 'max_response_bytes': rules['host_reference_max_bytes'],
                  'max_quote_characters': rules['host_reference_max_quote_characters']}
    checked = _validate_source_response(request=restored,
        raw_response=_bytes({**resolved, 'request_id': restored['request_id']}), policy=host_rules)
    # Restore the externally observed identity in the derived check. The raw
    # response and original request are never changed on disk.
    required = {(r['unit_id'], r['kind'], r['source_index'])
                for r in request['required_candidate_assessments']}
    accounted = {(f['unit_id'], e['kind'], e['source_index'])
                 for f in checked['findings'] for e in f['resolved_evidence']}
    need(required <= accounted, 'B13_KNOWN_SOURCE_CANDIDATE_NOT_ASSESSED')
    monetary = {(r['unit_id'], r['source_index']) for r in request['native_capacity_role_assessments']
                if r['role'] == 'MONETARY_CREDIT_FACILITY_CAPACITY'}
    for finding in checked['findings']:
        if finding['kind'] in {'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY'}:
            need(not any(e['kind'] == 'NATIVE_FACT' and (finding['unit_id'], e['source_index']) in monetary
                         for e in finding['resolved_evidence']), 'B13_MONETARY_CAPACITY_NOT_PHYSICAL')
        if finding['kind'] == 'ACTUAL_PRODUCTION':
            visible = [e['text'] for e in finding['resolved_evidence'] if e['kind'] == 'VISIBLE_BLOCK']
            if visible and len(visible) == len(finding['resolved_evidence']):
                text = ' '.join(visible)
                sales = re.search(r'\b(?:sold|shipped|shipments?|sales|wholesale\s+volume)\b', text, re.I)
                production = re.search(r'\b(?:produced|manufactur(?:e|es|ed|ing)|production|output)\b', text, re.I)
                need(not sales or production is not None, 'B13_SALES_ONLY_SOURCE_IS_NOT_ACTUAL_PRODUCTION')
    checked['request_id'] = request['request_id']
    checked['response'] = response
    return checked
