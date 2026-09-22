"""Explicit B13 finding references, independent of model-supplied unit buckets.

Only new requests opt in. Old nested responses are never repaired. A source
reference must have exactly one owner in the supplied, single-document group.
The normal B13 validator still checks every derived finding and source unit.
"""
from copy import deepcopy

from .canonical import canonical_json_bytes, content_hash, strict_json_loads, strict_json_file

VERSION = 'B13_SOURCE_REFERENCES_V1'


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
            key = (kind, source_index)
            need(key not in owners, 'B13_REFERENCE_AMBIGUOUS_SOURCE')
            owners[key] = index
    return owners


def upgrade_request(base):
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
    schema['properties'].pop('request_id')
    item['properties'].pop('unit_id')
    item['properties']['unit_index'] = {'type': 'integer', 'minimum': 0, 'maximum': count - 1}
    protocol['root_fields'] = schema['required'] = ['units', 'findings']
    protocol['unit_fields'] = item['required'] = ['unit_index', 'reviewed', 'unresolved', 'calculation_limits']
    unit_schema.update(minItems=count, maxItems=count)
    protocol['finding_reference_scope'] = (
        'Each root findings entry cites exact kind/source_index pairs from the supplied document. '
        'The program resolves their unique source unit. Do not put findings inside units. '
        'All evidence in one finding must belong to the same source unit. '
        'units contains exactly one review status per supplied unit, addressed by its zero-based unit_index. '
        'Every source unit, including empty units, must be reviewed. Unknown or ambiguous references are rejected.')
    body['source_reference_contract'] = {'version': VERSION, 'base_request_id': base['request_id']}
    return {**body, 'request_id': content_hash(value=body)}


def restore_base_request(request):
    from .capacity_semantic_review import review_policy_path
    from .normal_source_authority import ROOT
    need(request.get('request_id') == content_hash(value={k: v for k, v in request.items() if k != 'request_id'}),
         'B13_REFERENCE_REQUEST_CHANGED')
    meta = request.get('source_reference_contract')
    need(type(meta) is dict and set(meta) == {'version', 'base_request_id'}
         and meta['version'] == VERSION, 'B13_REFERENCE_CONTRACT_CHANGED')
    body = {k: deepcopy(v) for k, v in request.items() if k not in {'request_id', 'source_reference_contract'}}
    body['response_protocol'] = strict_json_file(path=ROOT / review_policy_path(request))['response_protocol']
    base = {**body, 'request_id': content_hash(value=body)}
    need(base['request_id'] == meta['base_request_id'] and upgrade_request(base) == request,
         'B13_REFERENCE_MAPPING_CHANGED')
    return base


def restore_response(*, request, raw_response):
    base = restore_base_request(request)
    owners = _owners(base)
    original = strict_json_loads(text=raw_response.decode('utf-8'))
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
            need(type(evidence) is dict and set(evidence) == {'kind', 'source_index'}
                 and type(evidence['kind']) is str and type(evidence['source_index']) is int,
                 'B13_REFERENCE_FIELDS_CHANGED')
            key = (evidence['kind'], evidence['source_index'])
            need(key in owners, 'B13_REFERENCE_OUTSIDE_SUPPLIED_SOURCE')
            references.append(key)
        need(len(set(references)) == len(references), 'B13_REFERENCE_DUPLICATE_EVIDENCE')
        indices = {owners[key] for key in references}
        need(len(indices) == 1, 'B13_REFERENCE_CROSS_UNIT_FINDING')
        identity = content_hash(value=finding)
        need(identity not in seen, 'B13_REFERENCE_DUPLICATE_FINDING')
        seen.add(identity)
        rows[indices.pop()]['findings'].append(deepcopy(finding))
    normalized = {'request_id': base['request_id'], 'units': [rows[i] for i in sorted(rows)]}
    return base, canonical_json_bytes(value=normalized), original
