"""New exact input case through the existing development response checker.

Only an evidence exercise: no execution controller, permission or native credit.
The earlier case4 processor and raw processing packet remain byte-identical.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import postprocess as old

SOURCE_SHA = old.SOURCE_SHA
REQUEST_SHA = '7d47c99294d05d67ac3ce5b6c5f741357a84e5062302d9e14d025d66b401c32b'
RESPONSE_SHA = 'e20c682f259eb7e30d8f7c0f62c11a14c5d624c1d041aea81a7f4b88fb67de83'
OUTPUT = Path('/private/tmp/issue28-d03-native-facts01-processing-20261003')


def source_input(raw):
    old.need(old.sha(raw) == REQUEST_SHA, 'FACTS01_EXTERNAL_REQUEST_CHANGED')
    original = old.SOURCE.read_bytes()
    old.need(old.sha(original) == SOURCE_SHA, 'FACTS01_EXTERNAL_SOURCE_CHANGED')
    source = old.strict_json_loads(text=original.decode())
    request = old.strict_json_loads(text=raw.decode())
    payload = old.strict_json_loads(text=request['messages'][1]['content'])
    old.need(payload['source_id'] == source['semantic_source_id'], 'FACTS01_SOURCE_ID_CHANGED')
    by_id = {u['unit_id']: u for u in source['units']}
    native = old._restore_units(payload['native_units'], payload['shared_source_dictionaries'])
    owners = payload['responsibility_unit_ids']
    old.need([u['unit_id'] for u in native] == owners
             and len(owners) == len(set(owners)), 'FACTS01_RESPONSIBILITY_CHANGED')
    for unit in native:
        old.need(old.exact(unit) == old.exact(by_id[unit['unit_id']]), 'FACTS01_NATIVE_CHANGED')
    visible = [u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT']
    rows = [[b['block_index'], b['html_quotation_context'], b['text']]
            for u in visible for b in u['payload']['blocks']]
    old.need(old.exact(rows) == old.exact(payload['complete_visible_rows'])
             and payload['visible_context_role'] == 'CONTEXT_ONLY', 'FACTS01_CONTEXT_CHANGED')
    return payload, {u['unit_id']: u for u in [*visible, *native]}


def checked_report(request, response):
    old.need(old.sha(response) == RESPONSE_SHA, 'FACTS01_EXTERNAL_RESPONSE_CHANGED')
    payload, units = source_input(request)
    checks = old.check_response(response, payload, units)
    return {'origin': 'DEVELOPMENT_MODEL', 'source_sha256': SOURCE_SHA,
        'request_sha256': REQUEST_SHA, 'response_sha256': RESPONSE_SHA,
        'case_processor_sha256': old.sha(Path(__file__).read_bytes()),
        'existing_response_checker_sha256': old.sha(Path(old.__file__).read_bytes()),
        'responsibility_unit_ids': payload['responsibility_unit_ids'], 'checks': checks,
        'native_result_created': False, 'calls': [0, 0, 0]}


def record(root, request, response):
    report = checked_report(request, response)
    folder = Path(root)
    folder.mkdir(parents=True, exist_ok=False)
    old.write_immutable_bytes(path=folder/'request-body.bin', content=request)
    old.write_immutable_bytes(path=folder/'response.bin', content=response)
    data = old.exact(report)
    old.write_immutable_bytes(path=folder/'processing.json', content=data)
    return old.sha(data), report


def read(root, expected_processing_sha256):
    folder = Path(root)
    old.need({p.name for p in folder.iterdir()} == {
        'request-body.bin', 'response.bin', 'processing.json'}, 'FACTS01_SAVED_FILES_CHANGED')
    data = (folder/'processing.json').read_bytes()
    old.need(old.sha(data) == expected_processing_sha256, 'FACTS01_EXTERNAL_PROCESSING_CHANGED')
    expected = checked_report((folder/'request-body.bin').read_bytes(), (folder/'response.bin').read_bytes())
    old.need(old.exact(expected) == data, 'FACTS01_SAVED_METADATA_CHANGED')
    return expected


if __name__ == '__main__':
    import shutil
    import tempfile
    import time
    from copy import deepcopy

    start = time.monotonic()
    request = Path('/private/tmp/issue28-d03-complete-context-plan-20261003-checked/1/request-body.json').read_bytes()
    response = (HERE/'independent-input/response.log').read_bytes()
    identity, report = record(OUTPUT, request, response)
    assert read(OUTPUT, identity) == report
    payload, units = source_input(request)
    value = json.loads(response)
    controls = [{'case': 'actual_exact_raw_response_roundtrip', 'passed': True}]

    def reject(name, mutate):
        changed = deepcopy(value)
        mutate(changed)
        try:
            old.check_response(old.exact(changed), payload, units)
        except ValueError as error:
            controls.append({'case': name, 'rejected': str(error)})
        else:
            raise AssertionError(name+' accepted')

    reject('missing_owner', lambda x: x['reviewed_unit_ids'].pop())
    reject('wrong_native_reference_kind', lambda x: x['findings'][0]['evidence'][0].__setitem__('kind', 'NATIVE_SUPPLEMENT'))
    reject('bool_fact_ordinal', lambda x: x['findings'][0]['evidence'][0].__setitem__('source_index', False))
    reject('foreign_fact_ordinal', lambda x: x['findings'][0]['evidence'][0].__setitem__('source_index', 800))
    reject('context_only_finding_without_owner', lambda x: x['findings'][1]['evidence'].pop(0))
    reject('duplicate_no_cleanup', lambda x: x['findings'].append(deepcopy(x['findings'][0])))

    for attack in ['response_changed', 'metadata_self_resealed']:
        with tempfile.TemporaryDirectory(prefix='issue28-d03-facts01-negative-') as tmp:
            copy = Path(tmp)/'packet'
            shutil.copytree(OUTPUT, copy)
            expected = identity
            if attack == 'response_changed':
                (copy/'response.bin').write_bytes(response+b' ')
            else:
                altered = {**report, 'native_result_created': True}
                raw = old.exact(altered)
                (copy/'processing.json').write_bytes(raw)
                expected = old.sha(raw)
            try:
                read(copy, expected)
            except ValueError as error:
                controls.append({'case': attack, 'rejected': str(error), 'actual_saved_copy': True})
            else:
                raise AssertionError(attack+' accepted')

    out = {'tested_base_sha': 'edda3b2903090417e00cecda858487b036ca4e74',
        'uncommitted_evidence_case': True, 'processing_sha256': identity,
        'processing_root': str(OUTPUT), 'report': report, 'controls': controls,
        'seconds': round(time.monotonic()-start, 3)}
    (HERE/'checked-output.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(out, ensure_ascii=False))
