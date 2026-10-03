"""Small evidence-case adapter; uses the existing response checker unchanged.

New cases supply external request/response digests. There is no live endpoint,
native acceptance, model correction, or automatic merging of company matters.
"""
import json
from pathlib import Path
import postprocess as old


def checked_report(request, response, expected_request_sha256, expected_response_sha256):
    old.need(old.sha(request) == expected_request_sha256, 'CASE_EXTERNAL_REQUEST_CHANGED')
    old.need(old.sha(response) == expected_response_sha256, 'CASE_EXTERNAL_RESPONSE_CHANGED')
    source_bytes = old.SOURCE.read_bytes()
    old.need(old.sha(source_bytes) == old.SOURCE_SHA, 'CASE_EXTERNAL_SOURCE_CHANGED')
    source = old.strict_json_loads(text=source_bytes.decode())
    wire = old.strict_json_loads(text=request.decode())
    payload = old.strict_json_loads(text=wire['messages'][1]['content'])
    old.need(payload['source_id'] == source['semantic_source_id'], 'CASE_SOURCE_ID_CHANGED')
    by_id = {u['unit_id']: u for u in source['units']}
    native = old._restore_units(payload['native_units'], payload['shared_source_dictionaries'])
    owners = payload['responsibility_unit_ids']
    old.need([u['unit_id'] for u in native] == owners
             and len(owners) == len(set(owners)), 'CASE_RESPONSIBILITY_CHANGED')
    for unit in native:
        old.need(old.exact(unit) == old.exact(by_id[unit['unit_id']]), 'CASE_NATIVE_CHANGED')
    visible = [u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT']
    rows = [[b['block_index'], b['html_quotation_context'], b['text']]
            for u in visible for b in u['payload']['blocks']]
    old.need(old.exact(rows) == old.exact(payload['complete_visible_rows'])
             and payload['visible_context_role'] == 'CONTEXT_ONLY', 'CASE_CONTEXT_CHANGED')
    allowed = {u['unit_id']: u for u in [*visible, *native]}
    return {'origin': 'DEVELOPMENT_MODEL', 'request_sha256': expected_request_sha256,
        'response_sha256': expected_response_sha256, 'source_sha256': old.SOURCE_SHA,
        'case_processor_sha256': old.sha(Path(__file__).read_bytes()),
        'existing_response_checker_sha256': old.sha(Path(old.__file__).read_bytes()),
        'responsibility_unit_ids': owners, 'checks': old.check_response(response, payload, allowed),
        'native_credit': False, 'calls': [0, 0, 0]}


def record(folder, request, response, expected_request_sha256, expected_response_sha256):
    report = checked_report(request, response, expected_request_sha256, expected_response_sha256)
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=False)
    old.write_immutable_bytes(path=root/'request-body.bin', content=request)
    old.write_immutable_bytes(path=root/'response.bin', content=response)
    data = old.exact(report)
    old.write_immutable_bytes(path=root/'processing.json', content=data)
    return old.sha(data), report


def read(folder, expected_processing_sha256, expected_request_sha256, expected_response_sha256):
    root = Path(folder)
    old.need({p.name for p in root.iterdir()} == {
        'request-body.bin', 'response.bin', 'processing.json'}, 'CASE_SAVED_FILES_CHANGED')
    data = (root/'processing.json').read_bytes()
    old.need(old.sha(data) == expected_processing_sha256, 'CASE_EXTERNAL_PROCESSING_CHANGED')
    request, response = (root/'request-body.bin').read_bytes(), (root/'response.bin').read_bytes()
    report = checked_report(request, response, expected_request_sha256, expected_response_sha256)
    old.need(old.exact(report) == data, 'CASE_SAVED_METADATA_CHANGED')
    return report
