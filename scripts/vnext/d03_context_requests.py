"""Read bounded, literal context from an already authenticated D03 source.

The caller supplies the trusted source digest and responsibility set. This
helper neither authenticates an acquisition nor decides whether an investigation
exists. Context items remain parts of their original units, never new owners.
"""
from copy import deepcopy

from .canonical import content_hash, sha256_bytes
from .native_unit_index import evidence_json_bytes
from .r6_semantic_source import _bytes
from .r6_semantic_review import _source_items

VERSION = 'D03_LITERAL_CONTEXT_V1'


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _source(source, expected_sha256, owners):
    _need(type(source) is dict
          and sha256_bytes(content=evidence_json_bytes(source)) == expected_sha256
          and source.get('metric_id') == 'D03'
          and source.get('source_serialization_complete') is True
          and source.get('semantic_source_id') == content_hash(value={
              k: v for k, v in source.items() if k != 'semantic_source_id'}),
          'D03_CONTEXT_SOURCE_CHANGED')
    units = source['units']
    _need(source['required_unit_ids'] == [u['unit_id'] for u in units]
          and len(set(source['required_unit_ids'])) == len(units),
          'D03_CONTEXT_SOURCE_UNITS_CHANGED')
    documents = {d['document_id'] for d in source['documents']}
    for unit in units:
        raw = _bytes(unit['payload'])
        _need(unit['document_id'] in documents
              and unit['payload_bytes'] == len(raw)
              and unit['payload_sha256'] == sha256_bytes(content=raw)
              and unit['unit_id'] == content_hash(value={
                  k: v for k, v in unit.items() if k != 'unit_id'}),
              'D03_CONTEXT_UNIT_CHANGED')
    by_id = {u['unit_id']: u for u in units}
    _need(type(owners) is list and owners and all(type(x) is str for x in owners)
          and len(owners) == len(set(owners)) and all(x in by_id for x in owners),
          'D03_CONTEXT_HOST_OWNERS_CHANGED')
    return by_id


def _xml_items(unit):
    if unit['kind'] == 'NATIVE_FACTS':
        p = unit['payload']
        for wrapper in p['facts']:
            element_id = wrapper['attributes'].get('id')
            if not element_id:
                continue
            fact = wrapper['fact']
            context_ref, unit_ref = fact['context_ref'], fact['unit_ref']
            env = wrapper['namespace_environment_id']
            _need((not context_ref or context_ref in p['contexts'])
                  and (not unit_ref or unit_ref in p['units'])
                  and env in p['namespace_environments'], 'D03_CONTEXT_FACT_DICTIONARY_MISSING')
            yield element_id, {'original_unit_id': unit['unit_id'], 'kind': 'NATIVE_FACT',
                'source_index': fact['ordinal'], 'element_id': element_id,
                'original_item': wrapper, 'context': p['contexts'].get(context_ref),
                'unit': p['units'].get(unit_ref), 'namespaces': p['namespace_environments'][env]}
    elif unit['kind'] == 'NATIVE_SUPPLEMENTS':
        for index, root in enumerate(unit['payload']['objects']):
            _need(sha256_bytes(content=root['raw_xml'].encode('utf-8')) == root['raw_xml_sha256'],
                  'D03_CONTEXT_XML_ROOT_CHANGED')
            for element in [root, *root['nested_objects']]:
                element_id = element['attributes'].get('id')
                if not element_id:
                    continue
                bounds = None
                raw = root['raw_xml']
                if element is not root:
                    a, b = element['relative_start_character'], element['relative_end_character']
                    _need(type(a) is int and type(b) is int and 0 <= a < b <= len(raw),
                          'D03_CONTEXT_XML_RANGE_CHANGED')
                    bounds = [a, b]
                    raw = raw[a:b]
                _need(sha256_bytes(content=raw.encode('utf-8')) == element['raw_xml_sha256'],
                      'D03_CONTEXT_XML_SLICE_CHANGED')
                yield element_id, {'original_unit_id': unit['unit_id'],
                    'kind': 'NATIVE_SUPPLEMENT', 'source_index': index, 'element_id': element_id,
                    'original_element': {k: v for k, v in element.items()
                                         if k not in {'raw_xml', 'nested_objects'}},
                    'raw_xml': raw, 'root_raw_xml_sha256': root['raw_xml_sha256'],
                    'relative_character_range': bounds}


def resolve_context_requests(*, source, expected_source_sha256, responsibility_unit_ids,
                             requests, max_requests=8, max_visible_blocks=32,
                             max_context_bytes=262144):
    """Resolve exact locations; missing/ambiguous/over-limit context stays unresolved.

    Requests have an owned anchor and either XML_ELEMENT_ID or VISIBLE_BLOCK_RANGE
    target. A block range uses original inclusive indices, in the anchor document.
    Caps apply before any follow-up generation; no provider or ledger is touched.
    """
    _need(all(type(n) is int and n > 0 for n in
              (max_requests, max_visible_blocks, max_context_bytes)), 'D03_CONTEXT_LIMIT_INVALID')
    by_id = _source(source, expected_source_sha256, responsibility_unit_ids)
    _need(type(requests) is list and len(requests) <= max_requests,
          'D03_CONTEXT_REQUEST_LIMIT')
    _need(len({_bytes(r) for r in requests}) == len(requests), 'D03_CONTEXT_DUPLICATE_REQUEST')
    xml, blocks = {}, {}
    for unit in source['units']:
        doc = unit['document_id']
        for key, item in _xml_items(unit):
            xml.setdefault((doc, key), []).append(item)
        if unit['kind'] == 'VISIBLE_TEXT':
            for block in unit['payload']['blocks']:
                blocks.setdefault((doc, block['block_index']), []).append({
                    'original_unit_id': unit['unit_id'], 'kind': 'VISIBLE_BLOCK',
                    'source_index': block['block_index'], 'original_item': block})
    rows, consumed = [], 0
    for request in requests:
        _need(type(request) is dict and set(request) == {'anchor', 'target'},
              'D03_CONTEXT_REQUEST_SHAPE')
        anchor, target = request['anchor'], request['target']
        _need(type(anchor) is dict and set(anchor) == {'unit_id', 'kind', 'source_index'}
              and type(anchor['unit_id']) is str and anchor['unit_id'] in responsibility_unit_ids,
              'D03_CONTEXT_ANCHOR_NOT_OWNED')
        owner = by_id[anchor['unit_id']]
        kind, items = _source_items(owner)
        _need(anchor['kind'] == kind and type(anchor['source_index']) is int
              and anchor['source_index'] in items, 'D03_CONTEXT_ANCHOR_CHANGED')
        _need(type(target) is dict, 'D03_CONTEXT_TARGET_SHAPE')
        doc, reason, found = owner['document_id'], None, []
        if target.get('kind') == 'XML_ELEMENT_ID':
            _need(set(target) == {'kind', 'element_id'} and type(target['element_id']) is str
                  and target['element_id'].strip(), 'D03_CONTEXT_XML_TARGET_SHAPE')
            found = xml.get((doc, target['element_id']), [])
            reason = ('D03_CONTEXT_LOCATION_MISSING' if not found else
                      'D03_CONTEXT_LOCATION_AMBIGUOUS' if len(found) != 1 else None)
        elif target.get('kind') == 'VISIBLE_BLOCK_RANGE':
            _need(set(target) == {'kind', 'first', 'last'}
                  and type(target['first']) is int and type(target['last']) is int
                  and 0 <= target['first'] <= target['last'], 'D03_CONTEXT_VISIBLE_TARGET_SHAPE')
            if target['last'] - target['first'] + 1 > max_visible_blocks:
                reason = 'D03_CONTEXT_BLOCK_LIMIT'
            else:
                for index in range(target['first'], target['last'] + 1):
                    matches = blocks.get((doc, index), [])
                    if len(matches) != 1:
                        reason = ('D03_CONTEXT_LOCATION_MISSING' if not matches else
                                  'D03_CONTEXT_LOCATION_AMBIGUOUS')
                        break
                    found.extend(matches)
        else:
            raise ValueError('D03_CONTEXT_TARGET_KIND')
        size = len(evidence_json_bytes(found)) if reason is None else 0
        if reason is None and consumed + size > max_context_bytes:
            reason = 'D03_CONTEXT_BYTE_LIMIT'
        if reason is None:
            consumed += size
        rows.append({'request': deepcopy(request), 'status': 'UNRESOLVED' if reason else 'LOCATED',
                     'reason': reason, 'context': None if reason else deepcopy(found)})
    return {'version': VERSION, 'source_id': source['semantic_source_id'],
        'source_sha256': expected_source_sha256, 'responsibility_unit_ids': list(responsibility_unit_ids),
        'limits': {'max_requests': max_requests, 'max_visible_blocks': max_visible_blocks,
                   'max_context_bytes': max_context_bytes}, 'context_bytes': consumed, 'rows': rows,
        'semantic_acceptance': False, 'company_result_created': False, 'business_calls': [0, 0, 0]}


def replay_context_packet(*, source, packet, expected_source_sha256, expected_packet_sha256):
    """Cold readers supply external digests and repeat the literal source lookup."""
    _need(sha256_bytes(content=evidence_json_bytes(packet)) == expected_packet_sha256,
          'D03_CONTEXT_PACKET_CHANGED')
    rebuilt = resolve_context_requests(source=source, expected_source_sha256=expected_source_sha256,
        responsibility_unit_ids=packet['responsibility_unit_ids'],
        requests=[row['request'] for row in packet['rows']], **packet['limits'])
    _need(evidence_json_bytes(rebuilt) == evidence_json_bytes(packet), 'D03_CONTEXT_REPLAY_CHANGED')
    return rebuilt
