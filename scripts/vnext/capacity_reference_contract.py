"""Explicit B13 finding references, independent of model-supplied unit buckets.

Only new requests opt in. Old nested responses are never repaired. A source
reference must have exactly one owner in the supplied, single-document group.
The normal B13 validator still checks every derived finding and source unit.
"""
from copy import deepcopy

from .canonical import canonical_json_bytes, content_hash, strict_json_loads, strict_json_file

VERSION = 'B13_SOURCE_REFERENCES_V1'
COMPACT_VERSION = 'B13_TYPED_COMPACT_REFERENCES_V2'


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


def upgrade_request(base, *, compact=False):
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
    need(type(compact) is bool, 'B13_COMPACT_SELECTION_INVALID')
    if compact:
        _compact_protocol(protocol, base)
    body['source_reference_contract'] = {'version': COMPACT_VERSION if compact else VERSION, 'base_request_id': base['request_id']}
    return {**body, 'request_id': content_hash(value=body)}


def restore_base_request(request):
    from .capacity_semantic_review import review_policy_path
    from .normal_source_authority import ROOT
    need(request.get('request_id') == content_hash(value={k: v for k, v in request.items() if k != 'request_id'}),
         'B13_REFERENCE_REQUEST_CHANGED')
    meta = request.get('source_reference_contract')
    need(type(meta) is dict and set(meta) == {'version', 'base_request_id'}
         and meta['version'] in {VERSION, COMPACT_VERSION}, 'B13_REFERENCE_CONTRACT_CHANGED')
    body = {k: deepcopy(v) for k, v in request.items() if k not in {'request_id', 'source_reference_contract'}}
    body['response_protocol'] = strict_json_file(path=ROOT / review_policy_path(request))['response_protocol']
    base = {**body, 'request_id': content_hash(value=body)}
    need(base['request_id'] == meta['base_request_id'] and upgrade_request(base, compact=meta['version'] == COMPACT_VERSION) == request,
         'B13_REFERENCE_MAPPING_CHANGED')
    return base


def restore_response(*, request, raw_response):
    base = restore_base_request(request)
    owners = _owners(base)
    original = strict_json_loads(text=raw_response.decode('utf-8'))
    wire_original = deepcopy(original)
    if request['source_reference_contract']['version'] == COMPACT_VERSION:
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
        indices = {owners[key] for key in references}
        need(len(indices) == 1, 'B13_REFERENCE_CROSS_UNIT_FINDING')
        identity = content_hash(value=finding)
        need(identity not in seen, 'B13_REFERENCE_DUPLICATE_FINDING')
        seen.add(identity)
        normalized = deepcopy(finding)
        for evidence in normalized['evidence']:
            evidence.pop('source_unit_index', None)
        rows[indices.pop()]['findings'].append(normalized)
    normalized = {'request_id': base['request_id'], 'units': [rows[i] for i in sorted(rows)]}
    return base, canonical_json_bytes(value=normalized), wire_original


def _compact_protocol(protocol, base):
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


def _expand_compact_response(value, request):
    """Decode only explicit typed codes; the V1 owner/semantic checks still run."""
    import re
    need(type(value) is dict and set(value)=={'units','findings'} and type(value['findings']) is list,
         'B13_COMPACT_RESPONSE_FIELDS_CHANGED')
    result=deepcopy(value);findings=[];books=request['response_protocol']['classification_codebooks']
    for row in value['findings']:
        need(type(row) is list and len(row)==5,'B13_COMPACT_FINDING_ARITY')
        finding={}
        for position,key in enumerate(('kind','subject','timing')):
            code=row[position]
            need(type(code) is int and 0<=code<len(books[key]),'B13_COMPACT_CLASSIFICATION_CODE')
            finding[key]=books[key][code]
        need(type(row[3]) is list and row[3] and type(row[4]) is str and 0<len(row[4])<=96,
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
