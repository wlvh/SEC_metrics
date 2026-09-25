"""Explicit B13 finding references, independent of model-supplied unit buckets.

Only new requests opt in. Old nested responses are never repaired. A source
reference must have exactly one owner in the supplied, single-document group.
The normal B13 validator still checks every derived finding and source unit.
"""
from copy import deepcopy

from .canonical import canonical_json_bytes, content_hash, strict_json_loads, strict_json_file

VERSION = 'B13_SOURCE_REFERENCES_V1'
COMPACT_VERSION = 'B13_TYPED_COMPACT_REFERENCES_V2'
ROLE_VERSION = 'B13_MEANINGFUL_ROLE_REFERENCES_V3'
RELEVANCE_VERSION = 'B13_REQUIRED_FIRST_RELEVANCE_V4'
SCANNED_VERSION = 'B13_SCANNED_INTERPRETATION_V5'
ROLE_LABELS = {
    'physical_capacity_context': 'CAPACITY_QUALITATIVE',
    'sales_or_shipments': 'SALES_OR_SHIPMENTS',
    'product_or_installed_capacity': 'PRODUCT_STORAGE_OR_INSTALLED_CAPACITY',
    'planned_physical_capacity': 'PLANNED_CAPACITY',
    'monetary_credit_capacity': 'MONETARY_CREDIT_CAPACITY',
    'other_entity': 'OTHER_ENTITY',
    'historical_statement': 'HISTORICAL_STATEMENT',
    'conditional_statement': 'CONDITIONAL_OR_BOILERPLATE',
    'other_context': 'OTHER_CONTEXT',
}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _owners(base):
    from .capacity_semantic_review import _restore_units
    from .r6_semantic_review import _source_items
    units = _restore_units(base['units'], base['shared_source_dictionaries'])
    need(units and len({u['document_id'] for u in units}) == 1,
         'B13_REFERENCE_SINGLE_DOCUMENT_REQUIRED')
    owners = {}
    for index, unit in enumerate(units):
        kind, items = _source_items(unit)
        for source_index in items:
            # Supplemental objects are enumerated inside each source unit;
            # visible block and native fact ordinals belong to the document.
            key = (kind, index, source_index) if kind == 'NATIVE_SUPPLEMENT' else (kind, source_index)
            need(key not in owners, 'B13_REFERENCE_AMBIGUOUS_SOURCE')
            owners[key] = index
    return owners


def upgrade_request(base, *, compact=False, role_labels=False, relevance_scope=False):
    from .capacity_semantic_review import review_policy_path
    from .normal_source_authority import ROOT
    need(base.get('record_type') == 'B13_INTERPRETATION_REQUEST'
         and base.get('program_quantity_role_contract_version') is not None
         and 'indexed_unit_contract' not in base and 'source_reference_contract' not in base,
         'B13_REFERENCE_BASE_REQUEST_REQUIRED')
    need(base['request_id'] == content_hash(value={k: v for k, v in base.items() if k != 'request_id'}),
         'B13_REFERENCE_BASE_CHANGED')
    _owners(base)
    body = {k: deepcopy(v) for k, v in base.items() if k != 'request_id'}
    protocol = body['response_protocol']
    need(protocol == strict_json_file(path=ROOT / review_policy_path(base))['response_protocol'],
         'B13_REFERENCE_BASE_PROTOCOL_CHANGED')
    schema = protocol['json_schema']
    unit_schema = schema['properties']['units']
    item = unit_schema['items']
    need(protocol['root_fields'] == ['request_id', 'units']
         and protocol['unit_fields'] == ['unit_id', 'reviewed', 'findings', 'unresolved', 'calculation_limits'],
         'B13_REFERENCE_BASE_PROTOCOL_UNSUPPORTED')
    count = len(body['units'])
    schema['properties']['findings'] = item['properties'].pop('findings')
    evidence_schema = schema['properties']['findings']['items']['properties']['evidence']
    ordinary = deepcopy(evidence_schema['items'])
    ordinary['properties']['kind'] = {'enum': ['VISIBLE_BLOCK', 'NATIVE_FACT']}
    supplement = deepcopy(ordinary)
    supplement['properties']['kind'] = {'enum': ['NATIVE_SUPPLEMENT']}
    supplement['properties']['source_unit_index'] = {'type': 'integer', 'minimum': 0, 'maximum': len(body['units']) - 1}
    supplement['required'] = ['kind', 'source_index', 'source_unit_index']
    evidence_schema['items'] = {'oneOf': [ordinary, supplement]}
    protocol['supplement_evidence_fields'] = ['kind', 'source_index', 'source_unit_index']
    schema['properties'].pop('request_id')
    item['properties'].pop('unit_id')
    item['properties']['unit_index'] = {'type': 'integer', 'minimum': 0, 'maximum': count - 1}
    protocol['root_fields'] = schema['required'] = ['units', 'findings']
    protocol['unit_fields'] = item['required'] = ['unit_index', 'reviewed', 'unresolved', 'calculation_limits']
    unit_schema.update(minItems=count, maxItems=count)
    protocol['finding_reference_scope'] = (
        'Each root findings entry cites exact kind/source_index pairs from the supplied document. '
        'NATIVE_SUPPLEMENT indices are local to a source unit: also include source_unit_index, '
        'its zero-based position in supplied units. Other evidence kinds must omit source_unit_index. '
        'The program resolves their unique source unit. Do not put findings inside units. '
        'All evidence in one finding must belong to the same source unit. '
        'units contains exactly one review status per supplied unit, addressed by its zero-based unit_index. '
        'Every source unit, including empty units, must be reviewed. Unknown or ambiguous references are rejected.')
    need(type(compact) is bool and type(role_labels) is bool and (not role_labels or compact)
         and type(relevance_scope) is bool and (not relevance_scope or (compact and role_labels)),
         'B13_COMPACT_SELECTION_INVALID')
    if compact:
        _compact_protocol(protocol, base, role_labels=role_labels)
    if relevance_scope:
        _relevance_protocol(protocol)
    version = (RELEVANCE_VERSION if relevance_scope else ROLE_VERSION if role_labels
               else COMPACT_VERSION if compact else VERSION)
    body['source_reference_contract'] = {'version': version, 'base_request_id': base['request_id']}
    return {**body, 'request_id': content_hash(value=body)}


def restore_base_request(request):
    from .capacity_semantic_review import review_policy_path
    from .normal_source_authority import ROOT
    need(request.get('request_id') == content_hash(value={k: v for k, v in request.items() if k != 'request_id'}),
         'B13_REFERENCE_REQUEST_CHANGED')
    meta = request.get('source_reference_contract')
    if type(meta) is dict and meta.get('version') == SCANNED_VERSION:
        from .capacity_two_stage import restore_prior_interpretation_request
        return restore_base_request(restore_prior_interpretation_request(request))
    need(type(meta) is dict and set(meta) == {'version', 'base_request_id'}
         and meta['version'] in {VERSION, COMPACT_VERSION, ROLE_VERSION, RELEVANCE_VERSION},
         'B13_REFERENCE_CONTRACT_CHANGED')
    body = {k: deepcopy(v) for k, v in request.items() if k not in {'request_id', 'source_reference_contract'}}
    body['response_protocol'] = strict_json_file(path=ROOT / review_policy_path(request))['response_protocol']
    base = {**body, 'request_id': content_hash(value=body)}
    need(base['request_id'] == meta['base_request_id'] and upgrade_request(base,
         compact=meta['version'] in {COMPACT_VERSION, ROLE_VERSION, RELEVANCE_VERSION},
         role_labels=meta['version'] in {ROLE_VERSION, RELEVANCE_VERSION},
         relevance_scope=meta['version'] == RELEVANCE_VERSION) == request,
         'B13_REFERENCE_MAPPING_CHANGED')
    return base


def restore_response(*, request, raw_response):
    base = restore_base_request(request)
    owners = _owners(base)
    version = request['source_reference_contract']['version']
    scanned_exclusion_refs = (frozenset(request['two_stage_scan']['response']['candidate_refs'])
                              if version == SCANNED_VERSION else frozenset())
    def typed_ref(key):
        return ('B' + str(key[-1]) if key[0] == 'VISIBLE_BLOCK' else
                'F' + str(key[-1]) if key[0] == 'NATIVE_FACT' else
                'S' + str(key[1]) + ':' + str(key[2]))
    original = strict_json_loads(text=raw_response.decode('utf-8'))
    wire_original = deepcopy(original)
    if version in {COMPACT_VERSION, ROLE_VERSION, RELEVANCE_VERSION, SCANNED_VERSION}:
        original = _expand_compact_response(original, request)
    need(type(original) is dict and set(original) == {'units', 'findings'}
         and type(original['units']) is list and type(original['findings']) is list
         and len(original['units']) == len(base['units']), 'B13_REFERENCE_RESPONSE_CENSUS_CHANGED')
    rows = {}
    for row in original['units']:
        need(type(row) is dict and set(row) == {'unit_index', 'reviewed', 'unresolved', 'calculation_limits'}
             and type(row['unit_index']) is int and 0 <= row['unit_index'] < len(base['units'])
             and row['unit_index'] not in rows, 'B13_REFERENCE_RESPONSE_UNIT_CHANGED')
        index = row['unit_index']
        rows[index] = {k: deepcopy(v) for k, v in row.items() if k != 'unit_index'}
        rows[index].update(unit_id=base['units'][index]['unit_id'], findings=[])
    seen = set()
    required_keys = set()
    if version in {RELEVANCE_VERSION, SCANNED_VERSION}:
        unit_indices = {unit['unit_id']: index for index, unit in enumerate(base['units'])}
        for required in base['required_candidate_assessments']:
            kind, source_index = required['kind'], required['source_index']
            required_keys.add((kind, unit_indices[required['unit_id']], source_index))
    for finding in original['findings']:
        need(type(finding) is dict and set(finding) == set(base['response_protocol']['finding_fields'])
             and type(finding['evidence']) is list and finding['evidence'], 'B13_REFERENCE_FINDING_FIELDS_CHANGED')
        references = []
        for evidence in finding['evidence']:
            need(type(evidence) is dict
                 and type(evidence.get('kind')) is str and type(evidence.get('source_index')) is int,
                 'B13_REFERENCE_FIELDS_CHANGED')
            if evidence['kind'] == 'NATIVE_SUPPLEMENT':
                need(set(evidence) == {'kind', 'source_index', 'source_unit_index'}
                     and type(evidence['source_unit_index']) is int,
                     'B13_REFERENCE_SUPPLEMENT_SCOPE_REQUIRED')
                key = (evidence['kind'], evidence['source_unit_index'], evidence['source_index'])
            else:
                need(set(evidence) == {'kind', 'source_index'}, 'B13_REFERENCE_FIELDS_CHANGED')
                key = (evidence['kind'], evidence['source_index'])
            need(key in owners, 'B13_REFERENCE_OUTSIDE_SUPPLIED_SOURCE')
            references.append(key)
        need(len(set(references)) == len(references), 'B13_REFERENCE_DUPLICATE_EVIDENCE')
        if version == SCANNED_VERSION:
            need(all(typed_ref(key) in scanned_exclusion_refs for key in references),
                 'B13_TWO_STAGE_FINDING_OUTSIDE_SCAN')
        indices = {owners[key] for key in references}
        need(len(indices) == 1, 'B13_REFERENCE_CROSS_UNIT_FINDING')
        if version in {RELEVANCE_VERSION, SCANNED_VERSION} and \
                finding['kind'] in request['response_protocol']['required_only_exclusion_kinds']:
            need(any((key[0], owners[key], key[-1]) in required_keys
                     or (version == SCANNED_VERSION
                         and typed_ref(key) in scanned_exclusion_refs)
                     for key in references),
                 'B13_V4_NONREQUIRED_BACKGROUND_FINDING')
        identity = content_hash(value=finding)
        need(identity not in seen, 'B13_REFERENCE_DUPLICATE_FINDING')
        seen.add(identity)
        normalized = deepcopy(finding)
        for evidence in normalized['evidence']:
            evidence.pop('source_unit_index', None)
        rows[indices.pop()]['findings'].append(normalized)
    normalized = {'request_id': base['request_id'], 'units': [rows[i] for i in sorted(rows)]}
    return base, canonical_json_bytes(value=normalized), wire_original


def _compact_protocol(protocol, base, *, role_labels=False):
    """Short typed references and enum codes; identical required source census."""
    finding = protocol['json_schema']['properties']['findings']['items']
    books = {key: deepcopy(finding['properties'][key]['enum']) for key in ('kind','subject','timing')}
    protocol['compact_finding_fields'] = ['kind_code','subject_code','timing_code','source_refs','reason']
    protocol['finding_fields'] = protocol['compact_finding_fields']
    protocol['classification_codebooks'] = books
    protocol['max_compact_reason_characters'] = 96
    protocol['compact_instructions'] = (
        'Findings are five-element arrays: [kind_code,subject_code,timing_code,source_refs,reason]. '
        'Each code is the ZERO-BASED index in its classification_codebooks array. '
        'References are typed strings: B followed by the exact visible block index; '
        'F followed by the exact native fact index; S followed by unit_index:local_object_index. '
        'B449 and F449 are different references. Never change a prefix to guess a source. '
        'Use the supplied reference_inventory to check type, unit ownership and index. '
        'Preserve every finding, source unit, required assessment, unresolved item and calculation limit. '
        'Give a concise source-specific reason of at most96 characters; the original semantic definitions apply. '
        'Do not merge findings across source units or replace an unresolved fact with an exclusion.')
    fields = [{'type':'integer','minimum':0,'maximum':len(books[key])-1} for key in ('kind','subject','timing')]
    if role_labels:
        need(set(ROLE_LABELS.values()) == set(books['kind']), 'B13_ROLE_LABEL_BOOK_CHANGED')
        protocol['role_labels'] = dict(ROLE_LABELS)
        protocol['classification_codebooks'] = {key: books[key] for key in ('subject', 'timing')}
        protocol['compact_finding_fields'] = ['role_label','subject_code','timing_code','source_refs','reason']
        protocol['finding_fields'] = protocol['compact_finding_fields']
        protocol['compact_instructions'] = (
            'Findings are five-element arrays: [role_label,subject_code,timing_code,source_refs,reason]. '
            'Use an exact role_labels key, mapped to the unchanged category definitions; subject_code and timing_code '
            'remain zero-based indices in classification_codebooks. A plan for shares, debt, tax, governance or '
            'restructuring is not planned_physical_capacity. Manufacturing facility utilization used for inventory '
            'cost allocation is not product_or_installed_capacity. Do not classify a source from a shared word alone. '
            'Review every supplied unit and account for every required candidate; an irrelevant required candidate '
            'can be other_context, while an uncertain relation must remain unresolved. Unrelated nonrequired blocks '
            'need no finding. Emit each distinct finding once; never repeat it to fill the response. '
            'Typed references are B for exact visible block, F for exact native fact, S for unit_index:local_object_index. '
            'Check the reference_inventory and never guess a type or owner or merge findings across units. '
            'Preserve all source units and required '
            'assessments; reasons remain source-specific and at most96 characters.')
        fields[0] = {'type':'string','enum':list(ROLE_LABELS)}
    fields += [{'type':'array','minItems':1,'items':{'type':'string','pattern':r'^(B[0-9]+|F[0-9]+|S[0-9]+:[0-9]+)$'}},
               {'type':'string','minLength':1,'maxLength':96}]
    protocol['json_schema']['properties']['findings']['items'] = {'type':'array','prefixItems':fields,'minItems':5,'maxItems':5,'items':False}
    groups = {}
    for key,unit in _owners(base).items():
        kind=key[0];index=key[-1];prefix={'VISIBLE_BLOCK':'B','NATIVE_FACT':'F','NATIVE_SUPPLEMENT':'S'}[kind]
        if prefix=='S':prefix+=str(unit)+':'
        groups.setdefault((unit,prefix),[]).append(index)
    inventory=[]
    for (unit,prefix),indices in sorted(groups.items()):
        ranges=[]
        for index in sorted(indices):
            if ranges and index==ranges[-1][1]+1:ranges[-1][1]=index
            else:ranges.append([index,index])
        inventory.append({'unit_index':unit,'prefix':prefix,'inclusive_index_ranges':ranges})
    protocol['reference_inventory']=inventory


def _relevance_protocol(protocol):
    """Bound optional background without losing a unit or required candidate."""
    protocol['required_only_exclusion_kinds'] = [
        'MONETARY_CREDIT_CAPACITY', 'PRODUCT_STORAGE_OR_INSTALLED_CAPACITY',
        'SALES_OR_SHIPMENTS', 'OTHER_CONTEXT']
    protocol['max_compact_reason_characters'] = 128
    protocol['json_schema']['properties']['findings']['items']['prefixItems'][4]['maxLength'] = 128
    need(protocol['compact_instructions'].count('at most96 characters.') == 1,
         'B13_V4_REASON_BASE_CHANGED')
    protocol['compact_instructions'] = protocol['compact_instructions'].replace(
        'at most96 characters.', 'at most128 characters.')
    protocol['compact_instructions'] += (
        ' V4 response order: finish every required candidate not already proved by the program before optional findings. '
        'The program-owned roles need no duplicate model row. Keep one reviewed entry for every supplied unit. '
        'Optional findings may report physical manufacturing capacity, production, expansion plans or operational '
        'constraints; do not enumerate ordinary monetary credit, product storage/installed capacity, sales/shipment '
        'or other background as findings unless its exact reference is a required candidate. '
        'For a first-person registrant statement using we or our, use TARGET_REGISTRANT subject; reserve '
        'UNRESOLVED for a genuinely unidentified subject, not a known registrant accounting policy. '
        'Source content and required candidates remain unchanged; do not infer absence from an omitted background row.')


def _expand_compact_response(value, request):
    """Decode only explicit typed codes; the V1 owner/semantic checks still run."""
    import re
    need(type(value) is dict and set(value)=={'units','findings'} and type(value['findings']) is list,
         'B13_COMPACT_RESPONSE_FIELDS_CHANGED')
    result=deepcopy(value);findings=[];books=request['response_protocol']['classification_codebooks']
    roles=request['response_protocol'].get('role_labels')
    for row in value['findings']:
        need(type(row) is list and len(row)==5,'B13_COMPACT_FINDING_ARITY')
        finding={}
        if roles is not None:
            need(type(row[0]) is str and row[0] in roles, 'B13_ROLE_LABEL_INVALID')
            finding['kind'] = roles[row[0]]
        for position,key in enumerate(('kind','subject','timing')):
            if position == 0 and roles is not None:
                continue
            code=row[position]
            need(type(code) is int and 0<=code<len(books[key]),'B13_COMPACT_CLASSIFICATION_CODE')
            finding[key]=books[key][code]
        maximum = request['response_protocol']['max_compact_reason_characters']
        need(type(row[3]) is list and row[3] and type(row[4]) is str and 0<len(row[4])<=maximum,
             'B13_COMPACT_REFERENCE_OR_REASON')
        refs=[]
        for token in row[3]:
            need(type(token) is str,'B13_COMPACT_TYPED_REFERENCE')
            match=re.fullmatch(r'([BF])(0|[1-9][0-9]*)|S(0|[1-9][0-9]*):(0|[1-9][0-9]*)',token)
            need(match is not None,'B13_COMPACT_TYPED_REFERENCE')
            if match.group(1):refs.append({'kind':'VISIBLE_BLOCK' if match.group(1)=='B' else 'NATIVE_FACT','source_index':int(match.group(2))})
            else:refs.append({'kind':'NATIVE_SUPPLEMENT','source_unit_index':int(match.group(3)),'source_index':int(match.group(4))})
        finding.update(evidence=refs,reason=row[4]);findings.append(finding)
    result['findings']=findings
    return result
