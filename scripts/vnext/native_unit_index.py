"""Machine-owned identities with strict small source-unit response indices.

Original requests and receipts remain exact. A successor request changes only
the response identity format; it retains the original source grouping. No
misspelled hash or failed response is repaired or reinterpreted here.
"""
from copy import deepcopy

from .canonical import content_hash, strict_json_loads, canonical_json_bytes

VERSION = 'INDEXED_UNITS_V1'
BASE = 'BASE'
SUFFIX = ('\nOUTPUT IDENTITY CONTRACT: Return only the root object {"units":[...]}. '
    'For EVERY supplied source unit, return one entry with unit_index equal to its '
    'zero-based position in the supplied units array. unit_index_requirements lists each index and '
    'all mandatory evidence references. The per-unit fields are specified in response_protocol. '
    'Do not echo request_id or unit_id hashes; the calling program binds them to the original HTTP '
    'request and source. Evidence source_index still means the exact original block/fact index '
    'WITHIN that unit, not unit_index. Each index must appear exactly once; response array order '
    'does not matter because the program restores canonical source order. Never omit an empty '
    'unit or a required candidate.')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def upgrade_request(base):
    """Derive an exact indexed request from one original native source group."""
    need(base.get('record_type') in {'B13_INTERPRETATION_REQUEST','D04_NATIVE_INTERPRETATION_REQUEST'}
         and 'indexed_unit_contract' not in base and 'unit_index_requirements' not in base,
         'NATIVE_INDEX_BASE_REQUEST_REQUIRED')
    need(base['request_id'] == content_hash(value={k:v for k,v in base.items() if k!='request_id'}),
         'NATIVE_INDEX_BASE_ID_CHANGED')
    body = {k:deepcopy(v) for k,v in base.items() if k!='request_id'}
    protocol = body['response_protocol']; schema = protocol['json_schema']
    unit_schema = schema['properties']['units']; item = unit_schema['items']
    need(protocol['root_fields'] == ['request_id','units']
         and schema['required'] == ['request_id','units']
         and 'unit_id' in protocol['unit_fields'] and 'unit_index' not in protocol['unit_fields'],
         'NATIVE_INDEX_BASE_PROTOCOL_UNSUPPORTED')
    meta = {'version':VERSION, 'base_request_id':base['request_id'],
        'request_id_schema':schema['properties'].pop('request_id'),
        'unit_id_schema':item['properties'].pop('unit_id'),
        'unit_count_bounds':{k:unit_schema[k] for k in ('minItems','maxItems') if k in unit_schema}}
    protocol['root_fields'] = ['units']; schema['required'] = ['units']
    protocol['unit_fields'] = ['unit_index' if k=='unit_id' else k for k in protocol['unit_fields']]
    item['required'] = ['unit_index' if k=='unit_id' else k for k in item['required']]
    count = len(body['units']); need(count > 0, 'NATIVE_INDEX_EMPTY_SOURCE')
    item['properties']['unit_index'] = {'type':'integer','minimum':0,'maximum':count-1}
    unit_schema.update(minItems=count,maxItems=count)
    body['indexed_unit_contract'] = meta
    body['unit_index_requirements'] = [{'unit_index':i, 'required_evidence_references':[
        {k:r[k] for k in ('kind','source_index')} for r in base['required_candidate_assessments']
        if r['unit_id']==unit['unit_id']]} for i,unit in enumerate(base['units'])]
    body['system_prompt'] += SUFFIX
    return {**body,'request_id':content_hash(value=body)}


def restore_base_request(request):
    """Invert only the defined format transformation, then verify its hash."""
    need(request.get('request_id') == content_hash(value={k:v for k,v in request.items() if k!='request_id'}),
         'NATIVE_INDEX_REQUEST_ID_CHANGED')
    meta = request.get('indexed_unit_contract')
    need(type(meta) is dict and set(meta)=={'version','base_request_id','request_id_schema','unit_id_schema','unit_count_bounds'}
         and meta['version']==VERSION and request['system_prompt'].endswith(SUFFIX),
         'NATIVE_INDEX_CONTRACT_CHANGED')
    body = {k:deepcopy(v) for k,v in request.items()
            if k not in {'request_id','indexed_unit_contract','unit_index_requirements'}}
    body['system_prompt'] = body['system_prompt'][:-len(SUFFIX)]
    protocol = body['response_protocol']; schema = protocol['json_schema']
    unit_schema = schema['properties']['units']; item = unit_schema['items']
    need(protocol['root_fields']==['units'] and schema['required']==['units']
         and 'request_id' not in schema['properties'] and 'unit_id' not in item['properties'],
         'NATIVE_INDEX_PROTOCOL_CHANGED')
    protocol['root_fields'] = ['request_id','units']; schema['required'] = ['request_id','units']
    schema['properties']['request_id'] = deepcopy(meta['request_id_schema'])
    protocol['unit_fields'] = ['unit_id' if k=='unit_index' else k for k in protocol['unit_fields']]
    item['required'] = ['unit_id' if k=='unit_index' else k for k in item['required']]
    item['properties'].pop('unit_index',None); item['properties']['unit_id'] = deepcopy(meta['unit_id_schema'])
    for key in ('minItems','maxItems'):
        unit_schema.pop(key,None)
    unit_schema.update(meta['unit_count_bounds'])
    base = {**body,'request_id':content_hash(value=body)}
    need(base['request_id']==meta['base_request_id'] and upgrade_request(base)==request,
         'NATIVE_INDEX_BASE_OR_MAPPING_CHANGED')
    return base


def restore_response(*, request, raw_response):
    """Resolve integer indices exactly; never infer a missing unit or ID."""
    base = restore_base_request(request)
    original = strict_json_loads(text=raw_response.decode('utf-8'))
    need(type(original) is dict and set(original)=={'units'} and type(original['units']) is list
         and len(original['units'])==len(base['units']), 'NATIVE_INDEX_RESPONSE_CENSUS_CHANGED')
    expected_fields = set(request['response_protocol']['unit_fields'])
    indexed={}
    for row in original['units']:
        need(type(row) is dict and set(row)==expected_fields and type(row.get('unit_index')) is int
             and 0 <= row['unit_index'] < len(base['units']) and row['unit_index'] not in indexed,
             'NATIVE_INDEX_RESPONSE_UNIT_CHANGED')
        indexed[row['unit_index']] = row
    rows=[]
    for index,row in sorted(indexed.items()):
        rows.append({**{k:deepcopy(v) for k,v in row.items() if k!='unit_index'},
                     'unit_id':base['units'][index]['unit_id']})
    restored={'request_id':base['request_id'],'units':rows}
    return base,canonical_json_bytes(value=restored),original


def reconstruct_requests(source, variants=None):
    from .continuous_semantic_calls import source_requests
    base = source_requests(source)
    if variants is None:
        return base
    from .capacity_reference_contract import VERSION as REFERENCE_VERSION, COMPACT_VERSION, upgrade_request as reference_request
    need(type(variants) is list and len(variants)==len(base)
         and all(type(v) is str and v in {BASE,VERSION,REFERENCE_VERSION,COMPACT_VERSION} for v in variants),
         'NATIVE_REQUEST_VARIANT_CENSUS_CHANGED')
    return [request if version==BASE else reference_request(request, compact=version==COMPACT_VERSION) if version in {REFERENCE_VERSION,COMPACT_VERSION} else upgrade_request(request)
            for request,version in zip(base,variants)]


def validate_request_partition(source, actual_requests):
    base = reconstruct_requests(source)
    need(type(actual_requests) is list and len(actual_requests)==len(base), 'NATIVE_REQUEST_PARTITION_INCOMPLETE')
    variants=[]
    for original,actual in zip(base,actual_requests):
        if actual==original:
            variants.append(BASE)
        elif 'source_reference_contract' in actual:
            from .capacity_reference_contract import VERSION as REFERENCE_VERSION, COMPACT_VERSION, upgrade_request as reference_request
            version=actual['source_reference_contract'].get('version')
            need(version in {REFERENCE_VERSION,COMPACT_VERSION} and
                 actual==reference_request(original,compact=version==COMPACT_VERSION), 'NATIVE_REQUEST_VARIANT_NOT_SOURCE_BOUND')
            variants.append(version)
        else:
            need(actual==upgrade_request(original), 'NATIVE_REQUEST_VARIANT_NOT_SOURCE_BOUND')
            variants.append(VERSION)
    return variants


def evidence_json_bytes(value):
    """Keep source strings exact with unchanged canonical JSON framing.

    Semantic hashes still use the historical canonicalizer. Evidence payloads
    use the already validated lossless source serializer and its newline frame.
    """
    from .r6_semantic_source import _bytes
    return _bytes(value) + b'\n'
