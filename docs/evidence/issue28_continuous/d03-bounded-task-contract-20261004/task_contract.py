"""Offline task prototype. No provider, attempt, Candidate, Result or Run.

The finite two-execution ceiling is a design bound, not a durable opportunity
guard or a live grant. Existing mapper/default/runtime identities are untouched.
"""
from pathlib import Path

from vnext.canonical import sha256_bytes, strict_json_loads
from vnext.capacity_semantic_review import _shared_units, _restore_units
from vnext.continuous_request_context import measure_request, _load_tokenizer
from vnext.d03_context_requests import _source, resolve_context_requests
from vnext.d03_model_processing import _response
from vnext.native_unit_index import evidence_json_bytes

HERE = Path(__file__).parent
ROOT = HERE.parents[3]
BASE_FIELDS = {'reviewed_unit_ids', 'findings', 'scope_current_involvement', 'unresolved'}
FIELDS = BASE_FIELDS | {'scan_complete', 'context_requests'}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def wire(payload):
    prompt = (HERE/'scan-prompt.txt').read_text()
    return evidence_json_bytes({'model': 'deepseek-flash', 'messages': [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': evidence_json_bytes(payload).decode()}],
        'response_format': {'type': 'json_object'}, 'temperature': 0,
        'max_tokens': 4096, 'stream': False, 'thinking': {'type': 'disabled'}})


def prepare_scan(source, digest, owners):
    by_id = _source(source, digest, owners)
    return _prepare_scan(source, digest, owners, by_id)


def _prepare_scan(source, digest, owners, by_id):
    owned = [by_id[key] for key in owners]
    docs = {u['document_id'] for u in owned}
    need(len(docs) == 1, 'D03_TASK_MIXED_DOCUMENT')
    doc = next(iter(docs))
    identity = next((u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT'
                     and u['document_id'] == doc), None)
    need(identity is not None, 'D03_TASK_IDENTITY_CONTEXT_MISSING')
    context = [] if identity['unit_id'] in owners else [identity]
    provided = owned + context
    packed, shared = _shared_units(provided)
    need(_restore_units(packed, shared) == provided, 'D03_TASK_PACKING_CHANGED')
    policy = strict_json_loads(text=(ROOT/'catalog/r6/regulatory_semantic_review_v5.json').read_text())
    payload = {'source_id': source['semantic_source_id'], 'source_sha256': digest,
        'company_id': source['company_id'], 'source_unit_count': len(source['units']),
        'source_filing': next(d['filing'] for d in source['documents'] if d['document_id'] == doc),
        'target_period': source['prepared_annual_input']['table_input']['target_period'],
        'stage': 'SCAN', 'responsibility_unit_ids': list(owners),
        'context_only_unit_ids': [u['unit_id'] for u in context],
        'source_units': packed, 'shared_source_dictionaries': shared,
        'source_extent': 'FIRST_OWNER_SCAN_RELATED_CONTEXT_NOT_GUARANTEED',
        'category_definitions': policy['category_definitions']}
    raw = wire(payload)
    return {'payload': payload, 'request_body': raw,
        'request_sha256': sha256_bytes(content=raw), 'measure': measure_request(raw, require_reference=True),
        'provided_units': {u['unit_id']: u for u in provided}}


def scan_plan(source, digest, *, grouping_input_target=190000, max_owner_units=4):
    need(type(grouping_input_target) is int and 0 < grouping_input_target <= 195904
         and type(max_owner_units) is int and max_owner_units > 0, 'D03_TASK_GROUPING_LIMIT')
    by_id = _source(source, digest, source['required_unit_ids'])
    groups, current = [], []
    for unit in source['units']:
        if current and by_id[current[0]]['document_id'] != unit['document_id']:
            groups.append(_prepare_scan(source, digest, current, by_id)); current = []
        trial = _prepare_scan(source, digest, current + [unit['unit_id']], by_id)
        split = (not trial['measure']['fits'] or trial['measure']['input_tokens'] > grouping_input_target
                 or len(current) >= max_owner_units)
        if current and split:
            groups.append(_prepare_scan(source, digest, current, by_id)); current = [unit['unit_id']]
        else:
            current.append(unit['unit_id'])
    if current:
        groups.append(_prepare_scan(source, digest, current, by_id))
    need(all(t['measure']['fits'] for t in groups), 'D03_TASK_INDIVISIBLE_OWNER_EXCEEDS_SERVICE_LIMIT')
    flattened = [x for t in groups for x in t['payload']['responsibility_unit_ids']]
    need(flattened == source['required_unit_ids'] and len(set(flattened)) == len(flattened),
         'D03_TASK_COMPLETE_OWNERSHIP_CHANGED')
    _source(source, digest, source['required_unit_ids'])
    return {'tasks': groups, 'first_scan_count': len(groups),
        'followup_count_ceiling': len(groups), 'total_request_ceiling': 2 * len(groups),
        'max_context_requests_per_scan': 8, 'max_followups_per_scan': 1,
        'completion_guaranteed': False, 'runtime_opportunity_guard_connected': False,
        'live_authorized': False, 'business_calls': [0, 0, 0]}


def parse_scan(source, digest, task, raw, response_digest):
    need(type(raw) is bytes and sha256_bytes(content=raw) == response_digest, 'D03_TASK_RESPONSE_CHANGED')
    canonical_task = prepare_scan(source, digest, task['payload']['responsibility_unit_ids'])
    need(task['request_body'] == canonical_task['request_body']
         and task['request_sha256'] == canonical_task['request_sha256']
         and task['payload'] == canonical_task['payload']
         and task['provided_units'] == canonical_task['provided_units'], 'D03_TASK_INPUT_CHANGED')
    need(canonical_task['measure']['fits'], 'D03_TASK_SCAN_RESOURCE_LIMIT')
    value = _shape(raw)
    # Internal finding-shape projection only. The actual new response remains
    # unchanged and bound below; it is never registered as an old D03 execution.
    _response(evidence_json_bytes({k: value[k] for k in BASE_FIELDS}),
              canonical_task['payload'], canonical_task['provided_units'])
    context, trace, pending = _context(source, digest,
        canonical_task['payload']['responsibility_unit_ids'], value['context_requests'])
    return {'original_response': value, 'raw_response_sha256': response_digest,
        'located_context': context, 'literal_continuation_trace': trace,
        'unresolved_continuations': pending, 'semantic_acceptance': False, 'company_result_created': False}


def _context(source, digest, owners, original_requests):
    """Only forward literal continuedat, within the same eight-location cap.

    A model need not know the next continuation's id before seeing its parent.
    This is not a footnote/matter graph or semantic relationship inference.
    """
    requests = list(original_requests) if type(original_requests) is list else original_requests
    edges, trace, pending = {}, [], []
    while True:
        packet = resolve_context_requests(source=source, expected_source_sha256=digest,
            responsibility_unit_ids=owners, requests=requests)
        extra = []
        for row in packet['rows']:
            if row['status'] != 'LOCATED' or row['request']['target']['kind'] != 'XML_ELEMENT_ID':
                continue
            item = row['context'][0]
            original = item.get('original_item', item.get('original_element'))
            next_id = original['attributes'].get('continuedat')
            if not next_id:
                continue
            next_request = {'anchor': row['request']['anchor'],
                            'target': {'kind': 'XML_ELEMENT_ID', 'element_id': next_id}}
            before, after = evidence_json_bytes(row['request']), evidence_json_bytes(next_request)
            if before not in edges:
                edges[before] = after
                trace.append({'from_request': row['request'], 'to_request': next_request,
                              'relation': 'ORIGINAL_CONTINUEDAT_ATTRIBUTE'})
            seen, node = set(), before
            while node in edges and node not in seen:
                seen.add(node); node = edges[node]
            if node in seen:
                if not pending:
                    pending.append({'request': next_request, 'reason': 'D03_TASK_CONTINUATION_CYCLE'})
                continue
            if next_request in requests or next_request in extra:
                continue
            if len(requests) + len(extra) >= 8:
                pending.append({'request': next_request, 'reason': 'D03_TASK_CONTINUATION_LOCATION_CEILING'})
            else:
                extra.append(next_request)
        if not extra or pending:
            return packet, trace, pending
        requests = requests + extra


def _shape(raw):
    tokenizer, _ = _load_tokenizer()
    need(tokenizer is not None, 'D03_TASK_RESPONSE_TOKENIZER_REQUIRED')
    need(len(tokenizer.encode(raw.decode(), add_special_tokens=False).ids) <= 4096,
         'D03_TASK_RESPONSE_OUTPUT_LIMIT')
    value = strict_json_loads(text=raw.decode())
    need(type(value) is dict and set(value) == FIELDS and type(value['scan_complete']) is bool,
         'D03_TASK_RESPONSE_SHAPE')
    need(value['scan_complete'] or value['unresolved'], 'D03_TASK_INCOMPLETE_REASON_MISSING')
    return value


def prepare_followup(source, digest, task, raw, response_digest):
    parsed = parse_scan(source, digest, task, raw, response_digest)
    context = parsed['located_context']
    if not context['rows']:
        return {'status': 'NO_CONTEXT_REQUESTED', 'parsed': parsed, 'request_body': None}
    if parsed['unresolved_continuations'] or any(row['status'] != 'LOCATED' for row in context['rows']):
        return {'status': 'STOP_UNRESOLVED_CONTEXT', 'parsed': parsed, 'request_body': None}
    payload = {**task['payload'], 'stage': 'FOLLOWUP',
        'initial_request_sha256': task['request_sha256'],
        'original_scan_response_utf8': raw.decode(), 'context_packet': context,
        'literal_continuation_trace': parsed['literal_continuation_trace']}
    body = wire(payload); measured = measure_request(body, require_reference=True)
    return {'status': 'OFFLINE_FOLLOWUP_FITS' if measured['fits'] else 'STOP_UNRESOLVED_RESOURCE',
        'parsed': parsed, 'measure': measured, 'request_body': body if measured['fits'] else None,
        'proposed_request_sha256': sha256_bytes(content=body), 'followups_per_task_ceiling': 1,
        'payload': payload, 'live_authorized': False}


def parse_followup(source, digest, task, initial_raw, initial_digest, followup_raw, followup_digest,
                   *, actual_request_body, expected_request_sha256):
    proposed = prepare_followup(source, digest, task, initial_raw, initial_digest)
    need(proposed['status'] == 'OFFLINE_FOLLOWUP_FITS', 'D03_TASK_FOLLOWUP_NOT_PREPARED')
    need(type(actual_request_body) is bytes
         and sha256_bytes(content=actual_request_body) == expected_request_sha256
         and actual_request_body == proposed['request_body'], 'D03_TASK_ACTUAL_FOLLOWUP_REQUEST_CHANGED')
    need(type(followup_raw) is bytes and sha256_bytes(content=followup_raw) == followup_digest,
         'D03_TASK_FOLLOWUP_RESPONSE_CHANGED')
    value = _shape(followup_raw)
    by_id = _source(source, digest, task['payload']['responsibility_unit_ids'])
    units = dict(task['provided_units']); added_refs = set()
    for row in proposed['parsed']['located_context']['rows']:
        for item in row['context']:
            unit_id = item['original_unit_id']; units[unit_id] = by_id[unit_id]
            added_refs.add((unit_id, item['kind'], item['source_index']))
    _response(evidence_json_bytes({k: value[k] for k in BASE_FIELDS}), task['payload'], units)
    for finding in value['findings']:
        for ref in finding['evidence']:
            need(ref['unit_id'] in task['provided_units']
                 or (ref['unit_id'], ref['kind'], ref['source_index']) in added_refs,
                 'D03_TASK_UNSUPPLIED_CONTEXT_REFERENCE')
    # Validate further requests, but never prepare another execution for them.
    remaining = resolve_context_requests(source=source, expected_source_sha256=digest,
        responsibility_unit_ids=task['payload']['responsibility_unit_ids'],
        requests=value['context_requests'])
    need(not remaining['rows'] or not value['scan_complete'], 'D03_TASK_MORE_CONTEXT_CANNOT_BE_COMPLETE')
    return {'original_response': value, 'raw_response_sha256': followup_digest,
        'request_sha256': expected_request_sha256,
        'status': 'STOP_FOLLOWUP_CEILING' if remaining['rows'] else 'FOLLOWUP_STRUCTURE_READ',
        'remaining_context_requests': remaining, 'semantic_acceptance': False,
        'company_result_created': False, 'next_execution_prepared': False}
