"""One bounded D03 development plan; existing units and packer stay unchanged.

Every native batch receives complete visible context, avoiding the demonstrated
cross-group closure problem. This is not a live request or an absence grant.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.canonical import content_hash
from vnext.capacity_semantic_review import _shared_units, _restore_units
from vnext.continuous_request_context import measure_request
from vnext.r6_semantic_source import _bytes

SOURCE = Path('/private/tmp/issue28-d03-registered-full-review-20260929-retry/ledger/calls/0001/source.json')
OUTPUT = Path('/private/tmp/issue28-d03-complete-context-plan-20261003-checked')
HERE = Path(__file__).parent



def make_plan(source, prompt):
    units = source['units']
    assert source['semantic_source_id'] == content_hash(value={k: v for k, v in source.items()
                                                             if k != 'semantic_source_id'})
    assert source['required_unit_ids'] == [u['unit_id'] for u in units]
    for u in units:
        raw = _bytes(u['payload'])
        assert len(raw) == u['payload_bytes'] and hashlib.sha256(raw).hexdigest() == u['payload_sha256']
        assert u['unit_id'] == content_hash(value={k: v for k, v in u.items() if k != 'unit_id'})
    visible = [u for u in units if u['kind'] == 'VISIBLE_TEXT']
    native = [u for u in units if u['kind'] != 'VISIBLE_TEXT']
    assert len({u['document_id'] for u in units}) == 1, 'This bounded prototype is one document'
    rows, side, bounds = [], [], []
    for u in visible:
        start = len(rows)
        for b in u['payload']['blocks']:
            rows.append([b['block_index'], b['html_quotation_context'], b['text']])
            side.append({k: v for k, v in b.items()
                         if k not in {'block_index', 'html_quotation_context', 'text'}})
        bounds.append({'unit_id': u['unit_id'], 'start_row': start, 'end_row_exclusive': len(rows)})
    # Side metadata remains owned by the host, not guessed back from text.
    restored = []
    for u, bound in zip(visible, bounds):
        blocks = [{**side[i], 'block_index': rows[i][0], 'html_quotation_context': rows[i][1],
                   'text': rows[i][2]} for i in range(bound['start_row'], bound['end_row_exclusive'])]
        r = deepcopy(u); r['payload']['blocks'] = blocks; restored.append(r)
    assert restored == visible

    def request(group, visible_owner=False):
        packed, dictionaries = _shared_units(group) if group else ([], {})
        assert not group or _restore_units(packed, dictionaries) == group
        payload = {'source_id': source['semantic_source_id'], 'company_id': source['company_id'],
            'target_period': source['prepared_annual_input']['table_input']['target_period'],
            'source_filing': source['documents'][0]['filing'],
            'visible_columns': ['source_index', 'html_quotation_context', 'text'],
            'complete_visible_rows': rows, 'visible_unit_bounds': bounds,
            'native_units': packed, 'shared_source_dictionaries': dictionaries,
            'responsibility_unit_ids': [u['unit_id'] for u in (visible if visible_owner else group)],
            'visible_context_role': 'RESPONSIBILITY' if visible_owner else 'CONTEXT_ONLY'}
        body = {'model': 'deepseek-flash',
            'messages': [{'role': 'system', 'content': prompt},
                         {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}],
            'response_format': {'type': 'json_object'}, 'temperature': 0, 'max_tokens': 4096,
            'stream': False, 'thinking': {'type': 'disabled'}}
        wire = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
        return payload, wire, measure_request(wire, require_reference=True)

    requests = [request([], True)]
    assert requests[0][2]['fits']
    group = []
    for u in native:
        trial = request(group + [u])
        if group and not trial[2]['fits']:
            requests.append(request(group)); group = [u]
            assert request(group)[2]['fits'], 'Native unit plus context exceeds limit; no clipping'
        else:
            group.append(u)
            assert trial[2]['fits']
    if group:
        requests.append(request(group))
    owners = [i for payload, _, _ in requests for i in payload['responsibility_unit_ids']]
    assert owners == source['required_unit_ids'] and len(owners) == len(set(owners))
    native_restored = [u for payload, _, _ in requests if payload['native_units']
                       for u in _restore_units(payload['native_units'], payload['shared_source_dictionaries'])]
    assert _bytes(restored + native_restored) == _bytes(units)
    return requests, side


if __name__ == '__main__':
    source = json.loads(SOURCE.read_text())
    prompt = (HERE / 'input-prompt.txt').read_text()
    requests, side = make_plan(source, prompt)
    OUTPUT.mkdir(exist_ok=False)
    summary = {'source_json_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        'output_root': str(OUTPUT),
        'source_id': source['semantic_source_id'], 'source_unit_ids': source['required_unit_ids'],
        'original_units_unchanged_and_exactly_restored': True,
        'old_group_count': 5, 'candidate_request_count': len(requests),
        'model_correctness_or_output_fit_verified': False, 'live_authorized': False,
        'new_business_calls': [0, 0, 0], 'requests': []}
    (OUTPUT / 'visible-side-metadata.json').write_text(json.dumps(side, ensure_ascii=False, indent=2) + '\n')
    for i, (payload, wire, measured) in enumerate(requests):
        folder = OUTPUT / str(i); folder.mkdir()
        (folder / 'request-body.json').write_bytes(wire)
        (folder / 'input.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
        (folder / 'measurement.json').write_text(json.dumps(measured, indent=2) + '\n')
        summary['requests'].append({'index': i, 'responsibility_unit_ids': payload['responsibility_unit_ids'],
            'complete_visible_rows': len(payload['complete_visible_rows']),
            'native_unit_count': len(payload['native_units']),
            **{k: measured[k] for k in ['request_sha256', 'input_tokens', 'context_tokens', 'fits']}})
    (HERE / 'plan.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))
