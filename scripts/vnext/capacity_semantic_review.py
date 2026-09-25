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

POLICY_PATH = 'catalog/r5/capacity_semantic_review_v5.json'
PROGRAM_POLICY_PATH = 'catalog/r5/capacity_semantic_review_v6.json'

def review_policy_path(value):
    version=value.get('program_quantity_role_contract_version')
    if version is None:return POLICY_PATH
    from .capacity_program_roles import VERSION
    need(version in {None,VERSION},'B13_PROGRAM_CONTRACT_VERSION_UNSUPPORTED')
    return PROGRAM_POLICY_PATH if version else POLICY_PATH

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
    indices = [row['block_index'] if name == 'blocks' else row['fact']['ordinal'] for row in rows]
    layout = {'columns': columns, 'source_order': indices}
    if name == 'facts':
        fact_columns = sorted(rows[0]['fact'])
        if all(set(row['fact']) == set(fact_columns) for row in rows):
            layout['fact_columns'] = fact_columns
            for row in rows:
                row['fact'] = [row['fact'][key] for key in fact_columns]
    need(len(indices) == len(set(indices)) and all(type(i) is int and i >= 0 for i in indices),
         'B13_PACKED_SOURCE_INDEX_INVALID')
    payload[name] = {str(index): [row[key] for key in columns] for index, row in zip(indices, rows)}
    payload['row_layout'] = layout


def _restore_rows(unit):
    payload = unit['payload']
    layout = payload.pop('row_layout', None)
    if layout is None:
        return
    name = 'blocks' if unit['kind'] == 'VISIBLE_TEXT' else 'facts'
    columns = layout['columns']
    packed = payload[name]
    need(type(packed) is dict and all(re.fullmatch(r'0|[1-9][0-9]*', key) for key in packed),
         'B13_PACKED_SOURCE_INDEX_INVALID')
    indices = [str(i) for i in layout['source_order']]
    need(len(indices) == len(set(indices)) and set(indices) == set(packed),
         'B13_PACKED_SOURCE_INDEX_CHANGED')
    need(len(columns) == len(set(columns)) and all(len(row) == len(columns) for row in packed.values()),
         'B13_PACKED_ROW_FIELDS_CHANGED')
    payload[name] = [dict(zip(columns, packed[index])) for index in indices]
    if 'fact_columns' in layout:
        columns = layout['fact_columns']
        need(len(columns) == len(set(columns)) and all(len(row['fact']) == len(columns) for row in payload[name]),
             'B13_PACKED_FACT_FIELDS_CHANGED')
        for row in payload[name]:
            row['fact'] = dict(zip(columns, row['fact']))
    need(all(int(index) == (row['block_index'] if name == 'blocks' else row['fact']['ordinal'])
             for index, row in zip(indices, payload[name])), 'B13_PACKED_SOURCE_INDEX_CHANGED')


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


def shared_source_groups(units, maximum_bytes):
    """Share representation fields without changing any source unit or order."""
    groups, current = [], []
    for unit in units:
        if current and unit['document_id'] != current[0]['document_id']:
            groups.append(current)
            current = []
        trial = current + [unit]
        packed, shared = _shared_units(trial)
        if current and len(_bytes([packed, shared])) > maximum_bytes:
            groups.append(current)
            current = [unit]
        else:
            current = trial
    if current:
        groups.append(current)
    return groups


def requests_from_source(source):
    policy_path=review_policy_path(source)
    rules = strict_json_file(path=ROOT / policy_path)
    need(source['record_type'] == 'B13_COMPLETE_SEMANTIC_SOURCE'
         and source['source_serialization_complete'] is True
         and source['semantic_source_id'] == content_hash(value={
             k: v for k, v in source.items() if k != 'semantic_source_id'}),
         'B13_COMPLETE_SOURCE_REQUIRED')
    need(source['required_unit_ids'] == [u['unit_id'] for u in source['units']]
         and len(set(source['required_unit_ids'])) == len(source['units']),
         'B13_SOURCE_UNIT_SET_CHANGED')
    documents = {d['document_id']: d for d in source['documents']}
    annual = source['prepared_annual_input']
    from .continuous_request_context import FORMAT_VERSION, measured_groups
    context_format = source.get('request_context_format')
    need(context_format in {None, FORMAT_VERSION}, 'B13_CONTEXT_FORMAT_UNSUPPORTED')

    program_complete=None
    if policy_path==PROGRAM_POLICY_PATH:
        from .capacity_program_roles import quantity_contract
        program_complete=quantity_contract(units=source['units'],period=annual['table_input']['target_period'],
            scope=source.get('quantity_scope_context'))

    def request_for_group(group):
        packed, shared = _shared_units(group)
        if context_format is None:
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
                'policy_sha256': sha256_file(path=ROOT / policy_path),
                'provider_request_sent': False, 'provider_tokens_measured': False,
                'production_authorized': False}
        if context_format is not None:
            body['request_context_format'] = context_format
        if 'quantity_scope_context' in source:
            from .capacity_quantity_scope import check_scope_shape
            scope = source['quantity_scope_context']
            check_scope_shape(scope)
            did = document['document_id']
            need(did in scope['documents'], 'B13_QUANTITY_SCOPE_DOCUMENT_MISSING')
            body['quantity_scope_context'] = {'format': scope['format'], 'documents': {did: scope['documents'][did]}}
            body['quantity_scope_instructions'] = ('The supplied quantity_scope_context preserves original HTML h1-h6 headings and their byte ranges. '
                'A heading remains in scope until a heading of the same or higher level. Bold text does not close it. '
                'Unstructured explicit hypothetical introductions have unproved extent within the current genuine section; retain that uncertainty. '
                'A hypothetical or illustrative section and explicit same-paragraph statements that preceding quantities are not actual '
                'do not establish actual production or available capacity. Keep distinct actual sections and preserve unproved relationships as unresolved.')
        if policy_path==PROGRAM_POLICY_PATH:
            from .capacity_program_roles import VERSION,request_contract
            body['program_quantity_role_contract_version']=VERSION
            body['program_quantity_contract'],_=request_contract(units=group,period=body['target_period'],
                scope=body.get('quantity_scope_context'),complete=program_complete)
        return {**body, 'request_id': content_hash(value=body)}

    groups = (shared_source_groups(source['units'], rules['max_group_source_bytes']) if context_format is None else
              measured_groups(source['units'], request_for_group))
    requests = [request_for_group(group) for group in groups]
    need([u['unit_id'] for r in requests for u in r['units']] == source['required_unit_ids'],
         'B13_REQUEST_COVERAGE_CHANGED')
    return requests


def validate_response(*, request, raw_response, source=None):
    if 'source_reference_contract' in request:
        from .capacity_reference_contract import restore_response
        need(type(raw_response) is bytes and len(raw_response) <= strict_json_file(path=ROOT / review_policy_path(request))['max_response_bytes'],
             'B13_RESPONSE_TOO_LARGE')
        base, normalized, original = restore_response(
            request=request, raw_response=raw_response)
        checked = validate_response(request=base, raw_response=normalized, source=source)
        checked.update(request_id=request['request_id'], response=original)
        return checked
    if 'indexed_unit_contract' in request:
        from .native_unit_index import restore_response
        need(type(raw_response) is bytes and len(raw_response) <= strict_json_file(path=ROOT / review_policy_path(request))['max_response_bytes'],
             'B13_RESPONSE_TOO_LARGE')
        base, normalized, original = restore_response(request=request, raw_response=raw_response)
        checked = validate_response(request=base, raw_response=normalized,source=source)
        checked.update(request_id=request['request_id'], response=original)
        return checked
    """Restore source bytes and reuse the established exact quotation checks."""
    need(request['request_id'] == content_hash(value={
        k: v for k, v in request.items() if k != 'request_id'}), 'B13_REQUEST_CHANGED')
    policy_path=review_policy_path(request)
    rules = strict_json_file(path=ROOT / policy_path)
    need(type(raw_response) is bytes and len(raw_response) <= rules['max_response_bytes'],
         'B13_RESPONSE_SIZE_OR_TYPE')
    need(request['policy_sha256'] == sha256_file(path=ROOT / policy_path)
         and request['response_protocol'] == rules['response_protocol'], 'B13_REVIEW_POLICY_CHANGED')
    units = _restore_units(request['units'], request['shared_source_dictionaries'])
    program=None;program_complete=None
    if policy_path==PROGRAM_POLICY_PATH:
        from .capacity_program_roles import verify_request_contract
        program,program_complete=verify_request_contract(request,units,source)
    # The generic checker binds the restored host request. Preserve the actual
    # request identity when checking the provider's original response first.
    from .canonical import strict_json_loads
    response = strict_json_loads(text=raw_response.decode('utf-8'))
    need(type(response) is dict and response.get('request_id') == request['request_id'], 'B13_RESPONSE_REQUEST_CHANGED')
    resolved = deepcopy(response)
    from .r6_semantic_review import _source_items
    by_id = {u['unit_id']: u for u in units}
    calculation_limits = []
    need(type(resolved.get('units')) is list, 'B13_RESPONSE_UNITS_REQUIRED')
    for row in resolved['units']:
        need(type(row) is dict and row.get('unit_id') in by_id and type(row.get('findings')) is list,
             'B13_REFERENCE_UNIT_CHANGED')
        limits = row.pop('calculation_limits', None)
        need(type(limits) is list and all(type(code) is str and code in rules['calculation_limit_codes'] for code in limits)
             and len(limits) == len(set(limits)), 'B13_CALCULATION_LIMIT_FIELDS')
        current = {f.get('kind') for f in row['findings'] if type(f) is dict
                   and f.get('subject') == 'TARGET_REGISTRANT' and f.get('timing') == 'CURRENT_REPORT'}
        need(not ('ACTUAL_PRODUCTION' in current and 'TARGET_CURRENT_PRODUCTION_NOT_PRESENT_IN_THIS_UNIT' in limits)
             and not ('AVAILABLE_CAPACITY' in current and 'TARGET_CURRENT_CAPACITY_NOT_PRESENT_IN_THIS_UNIT' in limits),
             'B13_CALCULATION_LIMIT_CONTRADICTS_FINDING')
        calculation_limits.append({'unit_id': row['unit_id'], 'codes': limits})
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
    if program is not None:
        checked['findings'].extend(program['program_findings'])
        checked['unresolved'].extend(program['implementation_unresolved'])
        checked['program_quantity_contract']={'contract_id':request['program_quantity_contract']['contract_id'],
            'program_quantity_proofs':program['program_quantity_proofs'],
            'verified_nonphysical_native_roles':program['verified_nonphysical_native_roles']}
    required = {(r['unit_id'], r['kind'], r['source_index'])
                for r in request['required_candidate_assessments']}
    accounted = {(f['unit_id'], e['kind'], e['source_index'])
                 for f in checked['findings'] for e in f['resolved_evidence']}
    if program is not None:
        accounted.update((r['unit_id'],'NATIVE_FACT',r['source_index']) for r in program['verified_nonphysical_native_roles'])
    need(required <= accounted, 'B13_KNOWN_SOURCE_CANDIDATE_NOT_ASSESSED')
    monetary = {(r['unit_id'], r['source_index']) for r in request['native_capacity_role_assessments']
                if r['role'] == 'MONETARY_CREDIT_FACILITY_CAPACITY'}
    for finding in checked['findings']:
        if finding['kind'] == 'MONETARY_CREDIT_CAPACITY':
            evidence = finding['resolved_evidence']
            _, source_items = _source_items(by_id[finding['unit_id']])
            if evidence and all(e['kind'] == 'NATIVE_FACT' and
                    source_items[e['source_index']].get('tag', '').lower().endswith('nonfraction')
                    for e in evidence):
                need(all((finding['unit_id'], e['source_index']) in monetary for e in evidence),
                     'B13_NUMERIC_CREDIT_FACILITY_ROLE_NOT_ESTABLISHED')
        # A production incentive is not manufacturing capability, and a tax
        # credit is not borrowing headroom. Reject this observed conflict;
        # passing the check does not positively establish any other role.
        texts = [e['text'] for e in finding['resolved_evidence']]
        if texts and all(_tax_credit_without_capacity(text) for text in texts):
            need(finding['kind'] not in {'CAPACITY_QUALITATIVE', 'MONETARY_CREDIT_CAPACITY',
                                        'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY'},
                 'B13_TAX_CREDIT_IS_NOT_PRODUCTION_OR_BORROWING_CAPACITY')
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
    from .capacity_utilization_source import validate_explicit_quantity_classifications
    from .capacity_quantity_roles import validate_quantity_role_findings, validate_visible_source_label_roles
    checked['unresolved'].extend(validate_visible_source_label_roles(findings=checked['findings']))
    role_units=source['units'] if program is not None else units
    role_findings=([f for f in checked['findings'] if f not in program['program_findings']]+program_complete['program_findings']
                   if program is not None else checked['findings'])
    role_scope=source.get('quantity_scope_context') if program is not None else request.get('quantity_scope_context')
    checked['unresolved'].extend(validate_explicit_quantity_classifications(units=role_units,findings=role_findings,
        period=request['target_period'],quantity_scope=role_scope))
    checked['unresolved'].extend(validate_quantity_role_findings(units=role_units,findings=role_findings,
        period=request['target_period'],quantity_scope=role_scope))
    checked['request_id'] = request['request_id']
    checked['response'] = response
    checked['calculation_limits'] = calculation_limits
    return checked


def _tax_credit_without_capacity(text):
    """A narrow negative for tax incentives with no capacity assertion.

    This neither admits other statements nor establishes filing-wide absence.
    Mixed statements retain their capacity/quantity assessment obligations.
    """
    tax = re.search(r'\b(?:tax\s+credits?|advanced\s+manufacturing\s+production\s+tax\s+credit|AMPTC)\b', text, re.I)
    capacity = re.search(r'\b(?:capacit(?:y|ies)|utilization|utilisation|throughput|'
                         r'production\s+(?:volumes?|quantit(?:y|ies)|units?|output)|'
                         r'(?:produced|manufactured)\s+[\d,.]+|'
                         r'credit\s+(?:facility|facilities|line)|borrowing)\b', text, re.I)
    return tax is not None and capacity is None
