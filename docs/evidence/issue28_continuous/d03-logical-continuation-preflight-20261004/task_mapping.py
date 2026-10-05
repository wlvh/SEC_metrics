"""Offline source-item ownership with shared complete visible context.

Explicit partial native views refer to unchanged original source units; they
are never relabelled as those complete units. No model, ledger or native writer.
"""
from copy import deepcopy
from pathlib import Path
from html.parser import HTMLParser

import logical_source
from vnext.d03_context_requests import _source
from vnext.capacity_semantic_review import _shared_units, _restore_units
from vnext.continuous_request_context import measure_request
from vnext.native_unit_index import evidence_json_bytes

HERE = Path(__file__).parent


def need(ok, reason):
    if not ok:
        raise ValueError('D03_MAPPING_' + reason)


class _XMLDependencies(HTMLParser):
    """Collect literal dictionary references, never classify source meaning."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.required = {'contexts': set(), 'units': set()}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for attr, kind in [('contextref', 'contexts'), ('unitref', 'units')]:
            if values.get(attr):
                self.required[kind].add(values[attr])


def _complete_xml_dictionaries(source, parts):
    """Add explicit dictionary-only partial views from the same admitted source."""
    parser = _XMLDependencies()
    present = {'contexts': {}, 'units': {}}
    for part in parts:
        if part['kind'] == 'NATIVE_FACTS':
            for kind in present:
                present[kind].update(part['payload'][kind])
        else:
            for obj in part['payload']['objects']:
                parser.feed(obj['raw_xml'])
    parser.close()
    donors = {}
    for kind, keys in parser.required.items():
        for key in sorted(keys):
            matches = [(ui, u['payload'][kind][key]) for ui, u in enumerate(source['units'])
                       if u['kind'] == 'NATIVE_FACTS' and key in u['payload'][kind]]
            need(matches, 'XML_DICTIONARY_DEPENDENCY_MISSING')
            first_ui, definition = matches[0]
            need(all(v == definition for _, v in matches), 'XML_DICTIONARY_DEPENDENCY_CONFLICT')
            unit = source['units'][first_ui]
            env = definition['namespace_environment_id']
            need(env in unit['payload']['namespace_environments'], 'XML_DICTIONARY_NAMESPACE_MISSING')
            if key in present[kind]:
                need(present[kind][key] == definition, 'XML_DICTIONARY_PRESENT_CHANGED')
                continue
            part = donors.setdefault(first_ui, {'kind': 'NATIVE_FACTS', 'document_id': unit['document_id'],
                'parent_source_unit_id': unit['unit_id'], 'original_indices': [],
                'dictionary_context_only': True,
                'payload': {'facts': [], 'contexts': {}, 'units': {}, 'namespace_environments': {}}})
            part['payload'][kind][key] = deepcopy(definition)
            part['payload']['namespace_environments'][env] = deepcopy(unit['payload']['namespace_environments'][env])
            present[kind][key] = definition
    parts.extend(donors[i] for i in sorted(donors))


def census(source, digest):
    _source(source, digest, source['required_unit_ids'])
    need(len(source['documents']) == 1, 'SINGLE_DOCUMENT_REQUIRED')
    refs, items, units = [], {}, {}
    for ui, unit in enumerate(source['units']):
        if unit['kind'] == 'VISIBLE_TEXT':
            kind, rows = 'VISIBLE_BLOCK', [(b['block_index'], b) for b in unit['payload']['blocks']]
        elif unit['kind'] == 'NATIVE_FACTS':
            kind, rows = 'NATIVE_FACT', [(f['fact']['ordinal'], f) for f in unit['payload']['facts']]
        else:
            need(unit['kind'] == 'NATIVE_SUPPLEMENTS', 'SOURCE_KIND_UNSUPPORTED')
            kind, rows = 'NATIVE_SUPPLEMENT', list(enumerate(unit['payload']['objects']))
        units[unit['unit_id']] = ui
        for index, item in rows:
            need(type(index) is int and index >= 0, 'SOURCE_INDEX_INVALID')
            ref = (ui, kind, index)
            need(ref not in items, 'DUPLICATE_SOURCE_ITEM')
            refs.append(ref); items[ref] = item
    anchors = [{'unit_id': source['units'][r[0]]['unit_id'], 'kind': r[1], 'source_index': r[2]}
               for r in refs if r[1] == 'NATIVE_FACT' and items[r]['attributes'].get('continuedat')]
    packet = logical_source.assemble(source, digest, anchors) if anchors else {'rows': []}
    need(all(r['status'] == 'COMPLETE_XML_CHAIN' for r in packet['rows']), 'SOURCE_CHAIN_UNRESOLVED')
    chains = {}; root_owner = {}
    for row in packet['rows']:
        a = row['anchor']; anchor = (units[a['unit_id']], 'NATIVE_FACT', a['source_index'])
        chains[anchor] = row
        for segment in row['segments']:
            root_ref = (units[segment['original_unit_id']], 'NATIVE_SUPPLEMENT', segment['source_index'])
            need(root_ref in items, 'CHAIN_ROOT_MISSING')
            if items[root_ref]['raw_xml'] == segment['raw_xml']:
                root_owner.setdefault(root_ref, anchor)
    fact_ids = {}; xml_ids = {}
    for ref, item in items.items():
        ident = item['attributes'].get('id') if ref[1] != 'VISIBLE_BLOCK' else None
        if ident:
            target = fact_ids if ref[1] == 'NATIVE_FACT' else xml_ids
            target.setdefault(ident, []).append(ref)
    relations = []
    for ref, item in items.items():
        if ref[1] != 'NATIVE_SUPPLEMENT' or item.get('local_name') != 'relationship':
            continue
        attrs = item['attributes']; from_ids = attrs.get('fromrefs', '').split(); to_ids = attrs.get('torefs', '').split()
        need(from_ids and to_ids, 'RELATION_ENDPOINTS_REQUIRED')
        need(all(len(fact_ids.get(k, [])) == 1 for k in from_ids)
             and all(len(xml_ids.get(k, [])) == 1 for k in to_ids), 'RELATION_ENDPOINT_MISSING_OR_AMBIGUOUS')
        relations.append((ref, [fact_ids[k][0] for k in from_ids], [xml_ids[k][0] for k in to_ids]))
    return {'refs': refs, 'items': items, 'units': units, 'chains': chains,
            'root_owner': root_owner, 'relations': relations}


def prepare(source, digest, mapping, owned):
    need(mapping == census(source, digest), 'MAPPING_CHANGED')
    need(type(owned) is list and all(type(r) is tuple and len(r) == 3
         and type(r[0]) is int and type(r[1]) is str and type(r[2]) is int for r in owned), 'OWNER_REFERENCE_SHAPE')
    need(owned and len(owned) == len(set(owned)) and all(r in mapping['items'] for r in owned), 'OWNER_SET_CHANGED')
    context = set(owned); paths = []
    while True:
        before = len(context)
        for ref in list(context):
            chain = mapping['chains'].get(ref)
            if chain:
                context.update((mapping['units'][s['original_unit_id']], 'NATIVE_SUPPLEMENT', s['source_index'])
                               for s in chain['segments'])
        for relation, from_refs, to_refs in mapping['relations']:
            if context.intersection([relation, *from_refs, *to_refs]):
                context.update([relation, *from_refs, *to_refs])
        if len(context) == before:
            break
    for ref in sorted(context):
        chain = mapping['chains'].get(ref)
        if chain:
            path = []
            for segment in chain['segments']:
                root_ref = (mapping['units'][segment['original_unit_id']], 'NATIVE_SUPPLEMENT', segment['source_index'])
                path.append({'root_reference': list(root_ref), 'element_id': segment['element_id'],
                             'relative_character_range': segment['relative_character_range']})
            paths.append({'anchor_reference': list(ref), 'anchor_is_owned': ref in owned, 'segments': path})
    native = sorted(r for r in context if r[1] != 'VISIBLE_BLOCK')
    parts = []
    for ui in sorted({r[0] for r in native}):
        unit = source['units'][ui]; payload = deepcopy(unit['payload'])
        field = 'facts' if unit['kind'] == 'NATIVE_FACTS' else 'objects'
        indices = {r[2] for r in native if r[0] == ui}
        payload[field] = [deepcopy(mapping['items'][r]) for r in mapping['refs'] if r[0] == ui and r[2] in indices]
        parts.append({'kind': unit['kind'], 'document_id': unit['document_id'],
                      'parent_source_unit_id': unit['unit_id'], 'original_indices': sorted(indices),
                      'payload': payload})
    _complete_xml_dictionaries(source, parts)
    packed, shared = _shared_units(parts)
    need(_restore_units(packed, shared) == parts, 'NATIVE_PART_ROUNDTRIP_CHANGED')
    visible = [[r[0], r[2], mapping['items'][r]['text'], mapping['items'][r]['html_quotation_context']]
               for r in mapping['refs'] if r[1] == 'VISIBLE_BLOCK']
    payload = {'source_id': source['semantic_source_id'], 'source_sha256': digest,
               'company_id': source['company_id'],
               'original_document': {k: deepcopy(v) for k, v in source['documents'][0].items()
                                     if k in {'document_id', 'filing', 'raw_blob', 'source_reference', 'registrant_name_binding'}},
               'original_unit_descriptors': [{k: u[k] for k in ['unit_id', 'document_id', 'kind', 'payload_sha256', 'payload_bytes']}
                                             for u in source['units']],
               'owned_references': [list(r) for r in owned],
               'visible_context_columns': ['unit_position', 'block_index', 'text', 'html_quotation_context'],
               'complete_visible_context': visible,
               'native_context_references': [list(r) for r in native],
               'native_partial_views': packed, 'shared_native_dictionaries': shared,
               'complete_native_chain_paths': paths,
               'semantic_acceptance': False}
    body = evidence_json_bytes({'model': 'deepseek-flash', 'messages': [
        {'role': 'system', 'content': (HERE/'mapping-prompt.txt').read_text()},
        {'role': 'user', 'content': evidence_json_bytes(payload).decode('utf-8')}],
        'response_format': {'type': 'json_object'}, 'temperature': 0, 'max_tokens': 4096,
        'stream': False, 'thinking': {'type': 'disabled'}})
    return {'payload': payload, 'request_body': body,
            'measure': measure_request(body, require_reference=True),
            'owned_references': list(owned)}


def plan(source, digest, *, maximum_fact_bundle=128, grouping_context_target=150000):
    need(type(maximum_fact_bundle) is int and maximum_fact_bundle > 0
         and type(grouping_context_target) is int and 4096 < grouping_context_target <= 200000, 'GROUPING_SETTING')
    m = census(source, digest)
    visible = [r for r in m['refs'] if r[1] == 'VISIBLE_BLOCK']
    need(visible, 'VISIBLE_CONTEXT_REQUIRED')
    native = [r for r in m['refs'] if r[1] == 'NATIVE_FACT']
    bundles = [[r, *[x for x, owner in m['root_owner'].items() if owner == r]] for r in native]
    orphan = [r for r in m['refs'] if r[1] == 'NATIVE_SUPPLEMENT' and r not in m['root_owner']]
    tasks, stopped = [], []

    def add(batches):
        owned = [r for b in batches for r in b]
        t = prepare(source, digest, m, owned)
        if t['measure']['fits'] and (t['measure']['context_tokens'] <= grouping_context_target or len(batches) == 1):
            tasks.append(t)
        elif len(batches) > 1:
            middle = len(batches)//2
            add(batches[:middle]); add(batches[middle:])
        else:
            stopped.append({'owned_references': [list(r) for r in owned], 'measure': t['measure'],
                            'reason': 'ONE_COMPLETE_RESPONSIBILITY_WITH_FULL_CONTEXT_EXCEEDS_RESOURCE'})

    if visible:
        add([visible])  # One complete visible responsibility, not arbitrarily clipped.
    # An oversized complete global context invalidates this method for this source.
    if stopped:
        return {'source_sha256': digest, 'status': 'STOP_SHARED_VISIBLE_CONTEXT_RESOURCE',
                'original_reference_count': len(m['refs']), 'tasks': tasks, 'stopped': stopped,
                'proposed_initial_request_count': None, 'complete_owner_mapping': False,
                'live_permission': False, 'business_calls': [0, 0, 0]}
    for i in range(0, len(bundles), maximum_fact_bundle):
        add(bundles[i:i+maximum_fact_bundle])
    if orphan:
        add([orphan])
    owned = [r for t in tasks for r in t['owned_references']]
    owned.extend(tuple(r) for t in stopped for r in t['owned_references'])
    need(len(owned) == len(set(owned)) and set(owned) == set(m['refs']), 'COMPLETE_OWNER_MAP_CHANGED')
    return {'source_sha256': digest, 'status': 'ALL_INPUTS_FIT' if not stopped else 'STOP_COMPLETE_RESPONSIBILITY_RESOURCE',
            'original_reference_count': len(m['refs']), 'tasks': tasks, 'stopped': stopped,
            'proposed_initial_request_count': len(tasks) if not stopped else None,
            'complete_owner_mapping': True, 'whole_source_semantics_proven': False,
            'automatic_retries': 0, 'additional_call_opportunities_granted': 0,
            'live_permission': False, 'business_calls': [0, 0, 0]}
