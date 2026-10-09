"""Use the real new Run to check bound policy tamper and wrong-metric refusal."""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext import normal_run_v3 as normal

first = json.loads((HERE/'result.json').read_text())
attempt = (Path('/private/tmp/issue28-a05-formula-successor-20261002/state')/
    'jpmorgan_chase/metrics/A05-formula-v1/attempts'/first['attempt_id'])
data = attempt/'data'
manifest = json.loads((attempt/'runs/A05/manifest.json').read_text())
key = manifest['run_id'].removeprefix(normal.PREFIX)
binding_path = data/normal.BINDING_DIRECTORY/(key+'.json')
saved = json.loads(binding_path.read_text())
assert saved['presentation_policy'] == normal.A05_FORMULA_POLICY
normal.replay_case(data_root=data, manifest=manifest)
original_read = normal.strict_json_file
checks = []
for name, edit, expected in (
    ('unknown_policy', {'presentation_policy':'A05_UNAUTHORISED'},
     'ORDINARY_A05_FORMULA_REPLAY_POLICY_CHANGED'),
    ('policy_omitted', {'presentation_policy':None},
     'ORDINARY_INTEGRATED_INPUT_BINDING_CHANGED'),
    ('wrong_metric', {'primary_metric_id':'B01'},
     'ORDINARY_A05_FORMULA_REPLAY_POLICY_CHANGED')):
    changed = copy.deepcopy(saved)
    changed.update(edit)
    if name == 'policy_omitted':
        changed.pop('presentation_policy')

    def read(*, path):
        return changed if Path(path) == binding_path else original_read(path=path)

    with patch.object(normal, 'strict_json_file', side_effect=read):
        try:
            normal.replay_case(data_root=data, manifest=manifest)
        except ValueError as error:
            assert str(error) == expected, (name, str(error))
        else:
            raise AssertionError(name+'_TAMPER_ACCEPTED')
    checks.append({'case':name,'rejected_with':expected})
for value in (True, 'yes'):
    try:
        normal.prepare_case(data_root=data,company_id='jpmorgan_chase',
            metric_id='B01' if value is True else 'A05',a05_formula=value)
    except ValueError as error:
        assert str(error) == 'ORDINARY_A05_FORMULA_SCOPE_WRONG_METRIC'
    else:
        raise AssertionError('INVALID_A05_POLICY_SCOPE_ACCEPTED')
checks.append({'case':'wrong_metric_or_non_boolean_flag',
               'rejected_with':'ORDINARY_A05_FORMULA_SCOPE_WRONG_METRIC'})
body = {'record_type':'ISSUE28_A05_FORMULA_REPLAY_NEGATIVES',
        'run_id':manifest['run_id'],'binding_path':str(binding_path),
        'valid_native_replay_passed':True,'checks':checks,
        'saved_binding_modified':False,'new_real_calls':[0,0,0]}
(HERE/'negative.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'valid_native_replay':True,
                  'negative_cases_rejected':len(checks),
                  'saved_binding_unchanged':True}))
