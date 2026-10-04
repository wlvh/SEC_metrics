"""Offline literal continuation closure, not a live task or semantic rule.

Each original physical segment remains counted and carries its original source
identity and bytes. Completing an XML chain is not completing an investigation
assessment or covering the other original source responsibilities.
"""
from copy import deepcopy

from vnext.canonical import sha256_bytes
from vnext.d03_context_requests import _source, _xml_items
from vnext.native_unit_index import evidence_json_bytes


def need(ok, reason):
    if not ok:
        raise ValueError('D03_LOGICAL_' + reason)


def assemble(source, digest, anchors):
    """Resolve finite, same-document continuedat chains without interpreting text."""
    need(type(anchors) is list and anchors, 'ANCHORS_REQUIRED')
    need(all(type(a) is dict and set(a) == {'unit_id', 'kind', 'source_index'}
             and a['kind'] == 'NATIVE_FACT' and type(a['source_index']) is int
             and type(a['unit_id']) is str for a in anchors), 'ANCHOR_SHAPE')
    need(len({evidence_json_bytes(a) for a in anchors}) == len(anchors), 'ANCHOR_DUPLICATE')
    owners = list(dict.fromkeys(a['unit_id'] for a in anchors))
    by_id = _source(source, digest, owners)
    index, facts = {}, {}
    for unit in source['units']:
        for key, item in _xml_items(unit):
            index.setdefault((unit['document_id'], key), []).append(item)
            if item['kind'] == 'NATIVE_FACT':
                facts.setdefault((unit['unit_id'], item['source_index']), []).append(item)

    rows = []
    for anchor in anchors:
        matches = facts.get((anchor['unit_id'], anchor['source_index']), [])
        need(len(matches) == 1, 'ANCHOR_MISSING_OR_AMBIGUOUS')
        first = matches[0]
        wrapper = first['original_item']
        tag = wrapper['fact']['tag']
        prefix, separator, local = tag.partition(':')
        need(separator and local.lower() == 'nonnumeric'
             and prefix in first['namespaces'], 'ANCHOR_NOT_INLINE_NONNUMERIC')
        inline_namespace = first['namespaces'][prefix]
        document = by_id[anchor['unit_id']]['document_id']
        segments, seen = [], {first['element_id']}
        pending = wrapper['attributes'].get('continuedat')
        reason = None
        while pending:
            if pending in seen:
                reason = 'CONTINUATION_CYCLE'
                break
            seen.add(pending)
            found = index.get((document, pending), [])
            if len(found) != 1:
                reason = 'CONTINUATION_MISSING' if not found else 'CONTINUATION_AMBIGUOUS'
                break
            item = found[0]
            element = item.get('original_element', {})
            if (item['kind'] != 'NATIVE_SUPPLEMENT'
                    or element.get('local_name') != 'continuation'
                    or element.get('namespace') != inline_namespace):
                reason = 'CONTINUATION_WRONG_ELEMENT'
                break
            segments.append(deepcopy(item))
            pending = element['attributes'].get('continuedat')
        rows.append({'anchor': deepcopy(anchor), 'document_id': document,
                     'original_anchor_item': deepcopy(first),
                     'physical_continuation_count': len(segments),
                     'physical_xml_bytes': sum(len(s['raw_xml'].encode('utf-8')) for s in segments),
                     'segments': segments, 'status': 'UNRESOLVED' if reason else 'COMPLETE_XML_CHAIN',
                     'unresolved_reason': reason, 'pending_element_id': pending if reason else None})
    return {'record_type': 'D03_OFFLINE_LOGICAL_CONTINUATION_CLOSURE',
            'source_id': source['semantic_source_id'], 'source_sha256': digest,
            'original_required_unit_ids': deepcopy(source['required_unit_ids']),
            'selected_anchors': deepcopy(anchors), 'rows': rows,
            'physical_segments_total': sum(r['physical_continuation_count'] for r in rows),
            'full_original_scope_covered': False, 'semantic_acceptance': False,
            'old_eight_location_contract_changed': False, 'live_task_authorized': False,
            'business_calls': [0, 0, 0]}


def replay(source, digest, packet, packet_digest):
    need(sha256_bytes(content=evidence_json_bytes(packet)) == packet_digest, 'PACKET_CHANGED')
    rebuilt = assemble(source, digest, packet['selected_anchors'])
    need(evidence_json_bytes(rebuilt) == evidence_json_bytes(packet), 'REPLAY_CHANGED')
    return rebuilt
