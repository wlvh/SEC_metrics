"""Offline evidence check, not a production acceptance or authority gate."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from build import HERE, SOURCE, OUTPUT, _bytes, _restore_units


def restore(source, payloads, side):
    visible = [u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT']
    first = payloads[0]
    rows = first['complete_visible_rows']
    bounds = first['visible_unit_bounds']
    assert first['visible_context_role'] == 'RESPONSIBILITY'
    assert len(side) == len(rows)
    assert [b['unit_id'] for b in bounds] == [u['unit_id'] for u in visible]
    restored, end = [], 0
    for unit, bound in zip(visible, bounds):
        assert bound['start_row'] == end
        end = bound['end_row_exclusive']
        assert type(end) is int and end <= len(rows)
        blocks = [{**side[i], 'block_index': rows[i][0],
                   'html_quotation_context': rows[i][1], 'text': rows[i][2]}
                  for i in range(bound['start_row'], end)]
        u = deepcopy(unit)
        u['payload']['blocks'] = blocks
        restored.append(u)
    assert end == len(rows)
    owners = []
    for i, p in enumerate(payloads):
        assert p['source_id'] == source['semantic_source_id']
        assert p['company_id'] == source['company_id']
        assert p['target_period'] == source['prepared_annual_input']['table_input']['target_period']
        assert p['source_filing'] == source['documents'][0]['filing']
        assert p['visible_columns'] == ['source_index', 'html_quotation_context', 'text']
        assert _bytes(p['complete_visible_rows']) == _bytes(rows)
        assert p['visible_unit_bounds'] == bounds
        native = (_restore_units(p['native_units'], p['shared_source_dictionaries'])
                  if p['native_units'] else [])
        assert p['responsibility_unit_ids'] == [u['unit_id'] for u in (visible if i == 0 else native)]
        assert (not native) if i == 0 else (native and p['visible_context_role'] == 'CONTEXT_ONLY')
        owners.extend(p['responsibility_unit_ids'])
        restored.extend(native)
    assert owners == source['required_unit_ids'] and len(owners) == len(set(owners))
    assert _bytes(restored) == _bytes(source['units'])
    return restored


if __name__ == '__main__':
    plan = json.loads((HERE / 'plan.json').read_text())
    raw_source = SOURCE.read_bytes()
    assert hashlib.sha256(raw_source).hexdigest() == plan['source_json_sha256']
    source = json.loads(raw_source)
    payloads = []
    for item in plan['requests']:
        folder = OUTPUT / str(item['index'])
        raw = (folder / 'request-body.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['request_sha256']
        body = json.loads(raw)
        assert hashlib.sha256(body['messages'][0]['content'].encode()).hexdigest() == plan['prompt_sha256']
        payload = json.loads(body['messages'][1]['content'])
        assert payload == json.loads((folder / 'input.json').read_text())
        payloads.append(payload)
    side = json.loads((OUTPUT / 'visible-side-metadata.json').read_text())
    restored = restore(source, payloads, side)
    results = [{'case': 'all17units_exact_lossless_restore_and_unique_ownership', 'passed': True}]

    def rejected(name, mutate):
        changed = deepcopy(payloads)
        mutate(changed)
        try:
            restore(source, changed, side)
        except (AssertionError, KeyError, ValueError, IndexError):
            results.append({'case': name, 'passed': True, 'meaning': 'rejected_without_native_credit'})
        else:
            raise AssertionError('Accepted modified representation: ' + name)

    rejected('visible_row_removed', lambda p: p[0]['complete_visible_rows'].pop())
    rejected('repeated_context_text_changed', lambda p: p[1]['complete_visible_rows'][416].__setitem__(2, 'changed'))
    rejected('owner_duplicated', lambda p: p[-1]['responsibility_unit_ids'].append(p[1]['responsibility_unit_ids'][0]))
    rejected('native_unit_removed', lambda p: p[-1]['native_units'].clear())
    rejected('native_metadata_dictionary_missing', lambda p: p[1]['shared_source_dictionaries']['contexts'].clear())
    rejected('source_identity_substituted', lambda p: p[1].__setitem__('source_id', 'sha256:' + '0' * 64))
    rejected('numeric_block_id_changed_to_bool', lambda p: p[0]['complete_visible_rows'][0].__setitem__(0, False))
    # This compares UTF-8 evidence bytes, rather than Unicode-normalized identities.
    report = {'checks': results, 'restored_units_sha256': hashlib.sha256(_bytes(restored)).hexdigest(),
              'request_count': len(payloads), 'native_business_credit': False,
              'model_semantic_validation': False, 'new_calls': [0, 0, 0]}
    (HERE / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
