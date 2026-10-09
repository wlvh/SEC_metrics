"""Measure saved source relationships only; no model or provider invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

import logical_source
from vnext.continuous_request_context import measure_request
from vnext.native_unit_index import evidence_json_bytes

HERE = Path(__file__).resolve().parent
SOURCE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-complete-six-responses-20261004/source.json')
DIGEST = '5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b'
PRIVATE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-logical-continuation-preflight-20261004')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blocked(*a, **kw):
    raise AssertionError('NETWORK_AND_SUBPROCESS_FORBIDDEN')


def run(check=False):
    socket.socket = socket.create_connection = subprocess.Popen = blocked
    start = time.monotonic()
    raw = SOURCE.read_bytes()
    assert sha(raw) == DIGEST
    source = json.loads(raw)
    anchors = [{'unit_id': u['unit_id'], 'kind': 'NATIVE_FACT', 'source_index': f['fact']['ordinal']}
               for u in source['units'] if u['kind'] == 'NATIVE_FACTS'
               for f in u['payload']['facts'] if f['attributes'].get('continuedat')]
    packet = logical_source.assemble(source, DIGEST, anchors)
    if check:
        report = json.loads((HERE / 'actual-preflight.json').read_text())
        saved = (PRIVATE / 'all-started-chains.json').read_bytes()
        assert sha(saved) == report['packet_sha256']
        logical_source.replay(source, DIGEST, json.loads(saved), report['packet_sha256'])
        assert saved == evidence_json_bytes(packet)
        print(json.dumps({'independent_process_literal_replay': True,
                          'chains': len(packet['rows']), 'seconds': round(time.monotonic()-start, 3),
                          'full_scope_or_semantic_credit': False, 'calls': [0, 0, 0]}))
        return
    PRIVATE.mkdir(parents=True, exist_ok=True)
    destination = PRIVATE / 'all-started-chains.json'
    data = evidence_json_bytes(packet)
    if destination.exists():
        assert destination.read_bytes() == data
    else:
        with destination.open('xb') as f:
            f.write(data)
    selected = [r for r in packet['rows'] if r['anchor']['source_index'] in (389, 394, 418, 507)]
    assert len(selected) == 4
    assert all(r['status'] == 'COMPLETE_XML_CHAIN' for r in selected)
    identity = next(u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT')
    prompt = ('Offline D03 source-responsibility preflight, not authorized execution. '
              'Read only the explicitly owned fact anchors with their entire original '
              'continuedat chains and the same-filing identity context. Physical segments '
              'are source parts, not separate semantic claims. Interpret actual subjects, '
              'status and reported event times in the source; the XBRL accounting interval '
              'does not establish an investigation event date or current involvement. '
              'Retain uncertainty and conflicts. These selected anchors do not cover '
              'the other original source responsibilities. No model is invoked here.')
    measures = []
    for name, rows in [(str(r['anchor']['source_index']), [r]) for r in selected] + [('four-original-anchors', selected)]:
        payload = {'source_id': source['semantic_source_id'], 'source_sha256': DIGEST,
                   'company_id': source['company_id'], 'owned_anchor_chains': rows,
                   'original_identity_context_unit': identity,
                   'original_required_unit_ids': source['required_unit_ids'],
                   'full_original_scope_covered': False}
        request = {'model': 'deepseek-flash', 'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': evidence_json_bytes(payload).decode('utf-8')}],
            'response_format': {'type': 'json_object'}, 'temperature': 0,
            'max_tokens': 4096, 'stream': False, 'thinking': {'type': 'disabled'}}
        body = evidence_json_bytes(request)
        measures.append({'sample': name, 'physical_segments': sum(r['physical_continuation_count'] for r in rows),
                         'measurement': measure_request(body, require_reference=True)})
    out = {'record_type': 'D03_LITERAL_LOGICAL_SOURCE_RESOURCE_PREFLIGHT',
           'source_path': str(SOURCE), 'source_sha256': DIGEST,
           'source_unit_count': len(source['units']), 'original_native_fact_count': sum(
               len(u['payload']['facts']) for u in source['units'] if u['kind'] == 'NATIVE_FACTS'),
           'literal_started_chains': len(packet['rows']),
           'complete_chains': sum(r['status'] == 'COMPLETE_XML_CHAIN' for r in packet['rows']),
           'unresolved_chains': [{'anchor': r['anchor'], 'reason': r['unresolved_reason'],
                                  'pending_element_id': r['pending_element_id']}
                                 for r in packet['rows'] if r['status'] != 'COMPLETE_XML_CHAIN'],
           'packet_path': str(destination), 'packet_sha256': sha(data),
           'physical_segments_all_started_chains': packet['physical_segments_total'],
           'four_anchor_physical_segments': sum(r['physical_continuation_count'] for r in selected),
           'samples': measures, 'seconds': round(time.monotonic()-start, 3),
           'scope': 'Complete literal chains from preserved source, not semantic answers. Measured envelopes own only four selected anchors, with existing identity context. Not all17 units/1229 facts, no company plan or complete production response protocol.',
           'old_eight_location_contract_changed': False, 'new_model_answer': False,
           'native_or_company_credit': False, 'live_permission': False,
           'business_calls': [0, 0, 0]}
    (HERE / 'actual-preflight.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['literal_started_chains','complete_chains','physical_segments_all_started_chains','four_anchor_physical_segments','seconds']}))
    print(json.dumps([{'sample': m['sample'], 'context_tokens': m['measurement']['context_tokens'],
                       'fits': m['measurement']['fits']} for m in measures]))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    run(p.parse_args().check)
