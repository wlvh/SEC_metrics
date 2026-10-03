"""Bounded mechanical checks, not semantic acceptance or a fake native Run."""
from copy import deepcopy
import json
import shutil
import tempfile
import time
from pathlib import Path

import postprocess as p

START = time.monotonic()
ROOT = Path('/private/tmp/issue28-d03-native-checked-response-20261003')
request = Path('/private/tmp/issue28-d03-complete-context-plan-20261003-checked/4/request-body.json').read_bytes()
raw = (p.HERE/'independent-input/response.log').read_bytes()
identity, report = p.record(ROOT, request, raw)
assert p.read(ROOT, identity) == report
payload, units = p.authenticate_input(request)
value = json.loads(raw)
results = [{'case': 'actual_raw_response_exact_save_read', 'passed': True}]


def rejected(name, mutate):
    changed = deepcopy(value)
    mutate(changed)
    try:
        p.check_response(p.exact(changed), payload, units)
    except ValueError as error:
        results.append({'case': name, 'rejected': str(error)})
    else:
        raise AssertionError('Accepted control: '+name)


rejected('missing_owner', lambda x: x['reviewed_unit_ids'].pop())
rejected('foreign_source_unit', lambda x: x['findings'][0]['evidence'][0].__setitem__('unit_id', 'foreign'))
rejected('wrong_kind', lambda x: x['findings'][0]['evidence'][0].__setitem__('kind', 'VISIBLE_BLOCK'))
rejected('bool_index', lambda x: x['findings'][0]['evidence'][0].__setitem__('source_index', False))
rejected('outside_original_object', lambda x: x['findings'][0]['evidence'][0].__setitem__('source_index', 999))
rejected('context_only_has_no_owner', lambda x: x['findings'][0]['evidence'].pop(0))
rejected('exact_duplicate', lambda x: x['findings'].append(deepcopy(x['findings'][0])))
rejected('resource_overflow', lambda x: x['findings'][0].__setitem__('description', ' repeated'*6000))

# Separate assertions may genuinely share a native/context citation. This is
# a synthetic shape control, not an added fact or a revised model response.
shared = deepcopy(value)
shared['findings'].append({**deepcopy(shared['findings'][0]), 'description': 'Synthetic separate assertion'})
assert p.check_response(p.exact(shared), payload, units)['findings'] == 6
results.append({'case': 'shared_context_with_different_assertion', 'passed': True, 'synthetic': True})

for attack in ['response_changed', 'credit_changed', 'credit_changed_self_resealed',
               'owner_metadata_self_resealed']:
    with tempfile.TemporaryDirectory(prefix='issue28-d03-negative-') as tmp:
        copy = Path(tmp)/'copy'
        shutil.copytree(ROOT, copy)
        expected = identity
        if attack == 'response_changed':
            (copy/'response.bin').write_bytes(raw+b' ')
        else:
            saved = json.loads((copy/'processing.json').read_text())
            if attack == 'owner_metadata_self_resealed':
                saved['responsibility_unit_ids'] = ['foreign']
            else:
                saved['native_result_created'] = True
            altered = p.exact(saved)
            (copy/'processing.json').write_bytes(altered)
            if attack.endswith('self_resealed'):
                expected = p.sha(altered)
        try:
            p.read(copy, expected)
        except ValueError as error:
            results.append({'case': attack, 'rejected': str(error), 'actual_saved_copy': True})
        else:
            raise AssertionError('Accepted saved attack: '+attack)

out = {'tested_base_sha': '94b3c904825a65be75ef66c0bbc2843855d548f3',
    'uncommitted_evidence_processor': True, 'processing_sha256': identity,
    'processing_root': str(ROOT), 'report': report, 'controls': results,
    'seconds': round(time.monotonic()-START, 3), 'new_calls': [0, 0, 0]}
(p.HERE/'checked-output.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(out, ensure_ascii=False))
