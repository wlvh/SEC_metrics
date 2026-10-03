"""Visible-responsibility fixture through the existing response checker.

No native fact/supplement is silently injected, and no old response is rebound.
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import postprocess as old

REQUEST_SHA = 'c74e22c1dbe6f7e25249b7048c4d53b8490dd22fd1c51417f4f9f8308c848acc'
RESPONSE_SHA = '4e5aef5388f6ad64f1e41224015a6a3f083c10c31cccdaea17c4d7ea1fb01c55'
OUTPUT = Path('/private/tmp/issue28-d03-visible0-processing-20261004')


def checked_report(request, response):
    old.need(old.sha(request) == REQUEST_SHA and old.sha(response) == RESPONSE_SHA,
             'VISIBLE_EXTERNAL_WIRE_CHANGED')
    raw = old.SOURCE.read_bytes()
    old.need(old.sha(raw) == old.SOURCE_SHA, 'VISIBLE_EXTERNAL_SOURCE_CHANGED')
    source = old.strict_json_loads(text=raw.decode())
    wire = old.strict_json_loads(text=request.decode())
    payload = old.strict_json_loads(text=wire['messages'][1]['content'])
    visible = [u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT']
    rows, bounds = [], []
    for unit in visible:
        start = len(rows)
        rows.extend([[b['block_index'], b['html_quotation_context'], b['text']]
                     for b in unit['payload']['blocks']])
        bounds.append({'unit_id': unit['unit_id'], 'start_row': start, 'end_row_exclusive': len(rows)})
    old.need(payload['source_id'] == source['semantic_source_id']
             and payload['native_units'] == [] and payload['shared_source_dictionaries'] == {}
             and payload['visible_context_role'] == 'RESPONSIBILITY'
             and payload['responsibility_unit_ids'] == [u['unit_id'] for u in visible]
             and old.exact(payload['complete_visible_rows']) == old.exact(rows)
             and payload['visible_unit_bounds'] == bounds, 'VISIBLE_INPUT_OR_OWNER_CHANGED')
    return {'origin': 'DEVELOPMENT_MODEL', 'request_sha256': REQUEST_SHA,
        'response_sha256': RESPONSE_SHA, 'source_sha256': old.SOURCE_SHA,
        'processor_sha256': old.sha(Path(__file__).read_bytes()),
        'existing_response_checker_sha256': old.sha(Path(old.__file__).read_bytes()),
        'checks': old.check_response(response, payload, {u['unit_id']: u for u in visible}),
        'responsibility_unit_ids': payload['responsibility_unit_ids'],
        'native_credit': False, 'calls': [0, 0, 0]}


def record(request, response):
    report = checked_report(request, response)
    OUTPUT.mkdir(parents=True, exist_ok=False)
    old.write_immutable_bytes(path=OUTPUT/'request-body.bin', content=request)
    old.write_immutable_bytes(path=OUTPUT/'response.bin', content=response)
    data = old.exact(report)
    old.write_immutable_bytes(path=OUTPUT/'processing.json', content=data)
    return old.sha(data), report


def read(expected_processing_sha256):
    old.need({p.name for p in OUTPUT.iterdir()} == {
        'request-body.bin', 'response.bin', 'processing.json'}, 'VISIBLE_SAVED_FILES_CHANGED')
    raw = (OUTPUT/'processing.json').read_bytes()
    old.need(old.sha(raw) == expected_processing_sha256, 'VISIBLE_EXTERNAL_PROCESSING_CHANGED')
    report = checked_report((OUTPUT/'request-body.bin').read_bytes(), (OUTPUT/'response.bin').read_bytes())
    old.need(old.exact(report) == raw, 'VISIBLE_SAVED_METADATA_CHANGED')
    return report


def forbidden(*args, **kwargs):
    raise AssertionError('NETWORK_AND_SUBPROCESS_FORBIDDEN')


if __name__ == '__main__':
    start = time.monotonic()
    if len(sys.argv) > 1 and sys.argv[1] == 'cold':
        socket.socket = forbidden
        socket.create_connection = forbidden
        subprocess.Popen = forbidden
        subprocess.run = forbidden
        saved = json.loads((HERE/'checked-output.json').read_text())
        report = read(saved['processing_sha256'])
        assert report == saved['report']
        out = {'report_equal': True, 'native_credit': False, 'seconds': round(time.monotonic()-start, 3)}
        (HERE/'cold-output.json').write_text(json.dumps(out, indent=2)+'\n')
    else:
        request = Path('/private/tmp/issue28-d03-complete-context-plan-20261003-checked/0/request-body.json').read_bytes()
        response = (HERE/'independent-input/response.log').read_bytes()
        identity, report = record(request, response)
        assert read(identity) == report
        out = {'tested_base_sha': '02f4fbc0d2687bec7dc427cefa2a4187784e973f',
            'uncommitted_evidence_callsite': True, 'processing_sha256': identity,
            'report': report, 'seconds': round(time.monotonic()-start, 3)}
        (HERE/'checked-output.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(out, ensure_ascii=False))
