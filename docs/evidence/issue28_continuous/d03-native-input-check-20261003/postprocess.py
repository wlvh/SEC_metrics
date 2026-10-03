"""One development response: existing source resolver, exact raw persistence.

Evidence prototype only. No provider claim, native decision, Result or Run.
The current five-group production request and its old responses are untouched.
"""
import hashlib
import json
from pathlib import Path

from sec_http import write_immutable_bytes
from vnext.canonical import strict_json_loads
from vnext.capacity_semantic_review import _restore_units
from vnext.continuous_request_context import _load_tokenizer
from vnext.r6_semantic_review import _source_items

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE = Path('/private/tmp/issue28-d03-registered-full-review-20260929-retry/ledger/calls/0001/source.json')
SOURCE_SHA = '5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b'
REQUEST_SHA = '6d1fbe971d46a3c5fac136e5547362a17e056efd238c6c579f04e27cf43dc26e'
RESPONSE_SHA = '59ccfeb447d76555c14537816940be01aac3e804b7afb6c1d38245e721894097'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def exact(value):
    # Evidence strings remain byte-preserving; this is not historical canonical.
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def authenticate_input(request_bytes):
    need(sha(request_bytes) == REQUEST_SHA, 'EXTERNAL_REQUEST_CHANGED')
    raw = SOURCE.read_bytes()
    need(sha(raw) == SOURCE_SHA, 'EXTERNAL_SOURCE_CHANGED')
    source = strict_json_loads(text=raw.decode())
    request = strict_json_loads(text=request_bytes.decode())
    payload = strict_json_loads(text=request['messages'][1]['content'])
    by_id = {u['unit_id']: u for u in source['units']}
    need(payload['source_id'] == source['semantic_source_id'], 'SOURCE_ID_CHANGED')
    native = _restore_units(payload['native_units'], payload['shared_source_dictionaries'])
    owners = payload['responsibility_unit_ids']
    need([u['unit_id'] for u in native] == owners
         and len(owners) == len(set(owners)), 'RESPONSIBILITY_CHANGED')
    for unit in native:
        need(exact(unit) == exact(by_id[unit['unit_id']]), 'NATIVE_PAYLOAD_CHANGED')
    visible = [u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT']
    rows = [[b['block_index'], b['html_quotation_context'], b['text']]
            for u in visible for b in u['payload']['blocks']]
    need(exact(rows) == exact(payload['complete_visible_rows'])
         and payload['visible_context_role'] == 'CONTEXT_ONLY', 'VISIBLE_CONTEXT_CHANGED')
    return payload, {u['unit_id']: u for u in [*visible, *native]}


def check_response(raw, payload, units):
    tokenizer, _ = _load_tokenizer()
    tokens = len(tokenizer.encode(raw.decode(), add_special_tokens=False).ids)
    need(tokens <= 4096, 'OUTPUT_LIMIT')
    value = strict_json_loads(text=raw.decode())
    need(type(value) is dict and set(value) == {
        'reviewed_unit_ids', 'findings', 'scope_current_involvement', 'unresolved'}, 'ROOT_SHAPE')
    need(value['reviewed_unit_ids'] == payload['responsibility_unit_ids'], 'MISSING_EXTRA_OWNER')
    need(type(value['findings']) is list and len(value['findings']) <= 64, 'FINDING_BOUND')
    need(value['scope_current_involvement'] in {'EXPLICIT_PRESENT', 'EXPLICIT_NONE', 'UNRESOLVED'}, 'SCOPE_ENUM')
    need(type(value['unresolved']) is list
         and all(type(s) is str and s.strip() for s in value['unresolved']), 'UNRESOLVED_SHAPE')
    kinds = json.loads((REPO/'catalog/r6/regulatory_semantic_review_v5.json').read_text())['kinds']
    seen, references = set(), []
    for finding in value['findings']:
        need(type(finding) is dict and set(finding) == {
            'kind', 'subject', 'event_dates', 'reported_context_times',
            'status', 'evidence', 'description'}, 'FINDING_SHAPE')
        need(finding['kind'] in kinds, 'CATEGORY_CHANGED')
        for field in ['subject', 'status', 'description']:
            need(type(finding[field]) is str and finding[field].strip(), 'EMPTY_TEXT')
        for field in ['event_dates', 'reported_context_times']:
            need(type(finding[field]) is list
                 and all(type(s) is str and s.strip() for s in finding[field]), 'TIME_SHAPE')
        key = exact(finding)
        need(key not in seen, 'EXACT_DUPLICATE_NO_CLEANUP')
        seen.add(key)
        need(type(finding['evidence']) is list and finding['evidence'], 'NO_EVIDENCE')
        owned = False
        for reference in finding['evidence']:
            need(type(reference) is dict and set(reference) == {
                'unit_id', 'kind', 'source_index'}, 'REFERENCE_SHAPE')
            need(type(reference['unit_id']) is str and reference['unit_id'] in units,
                 'REFERENCE_UNIT_OUTSIDE_INPUT')
            kind, items = _source_items(units[reference['unit_id']])
            need(reference['kind'] == kind and type(reference['source_index']) is int
                 and reference['source_index'] in items, 'REFERENCE_KIND_OR_INDEX')
            owned |= reference['unit_id'] in payload['responsibility_unit_ids']
            references.append(reference)
        need(owned, 'CONTEXT_ONLY_FINDING_NOT_OWNED')
    return {'findings': len(value['findings']), 'unresolved': len(value['unresolved']),
        'reference_tokens': tokens, 'references': references,
        'scope_current_involvement': value['scope_current_involvement'],
        'semantic_approval': False, 'native_credit': False}


def checked_report(request_bytes, response_bytes):
    need(sha(response_bytes) == RESPONSE_SHA, 'EXTERNAL_RESPONSE_CHANGED')
    payload, units = authenticate_input(request_bytes)
    checks = check_response(response_bytes, payload, units)
    report = {'origin': 'DEVELOPMENT_MODEL', 'request_sha256': REQUEST_SHA,
        'response_sha256': RESPONSE_SHA, 'source_sha256': SOURCE_SHA,
        'processor_sha256': sha(Path(__file__).read_bytes()), 'checks': checks,
        'responsibility_unit_ids': payload['responsibility_unit_ids'],
        'calls': [0, 0, 0], 'native_result_created': False}
    return report


def record(folder, request_bytes, response_bytes):
    report = checked_report(request_bytes, response_bytes)
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=False)
    write_immutable_bytes(path=root/'request-body.bin', content=request_bytes)
    write_immutable_bytes(path=root/'response.bin', content=response_bytes)
    report_bytes = exact(report)
    write_immutable_bytes(path=root/'processing.json', content=report_bytes)
    return sha(report_bytes), report


def read(folder, expected_processing_sha256):
    root = Path(folder)
    need(set(p.name for p in root.iterdir()) == {
        'request-body.bin', 'response.bin', 'processing.json'}, 'SAVED_FILES_CHANGED')
    raw_report = (root/'processing.json').read_bytes()
    need(sha(raw_report) == expected_processing_sha256, 'EXTERNAL_PROCESSING_CHANGED')
    report = strict_json_loads(text=raw_report.decode())
    need(report['processor_sha256'] == sha(Path(__file__).read_bytes()), 'PROCESSOR_CHANGED')
    request, response = (root/'request-body.bin').read_bytes(), (root/'response.bin').read_bytes()
    need(sha(response) == RESPONSE_SHA and report['response_sha256'] == RESPONSE_SHA,
         'EXTERNAL_RESPONSE_CHANGED')
    need(report['origin'] == 'DEVELOPMENT_MODEL' and report['calls'] == [0, 0, 0]
         and report['native_result_created'] is False, 'CREDIT_CHANGED')
    need(exact(checked_report(request, response)) == raw_report, 'SAVED_PROCESSING_CHANGED')
    return report
