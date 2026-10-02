"""The N/A repair must still reject a wrong numeric branch in the real Run."""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import ordinary_projection as projection

first=json.loads((HERE/'na-repair-numeric.json').read_text())
attempt=(Path('/private/tmp/issue28-a05-formula-na-repair-20261002/state')/
    'jpmorgan_chase/metrics/A05-formula-v1/attempts'/first['attempt_id'])
data,run=attempt/'data',attempt/'runs/A05'
valid=projection.render_ordinary_run(data_root=data,run_dir=run,
                                      _return_replay_context=True)
assert valid['row']['formula']==first['formula']
observations=[r for r in valid['replay_context']['records']
              if r['record_type']=='VERIFIED_OBSERVATION' and r['metric_id']=='A05']
assert len(observations)==1
wrong=copy.deepcopy(observations[0])
wrong['source_binding']['selected_branch_id']='wrong_branch'
with patch.object(projection.projector,'_ordered_observations',
                  return_value=([wrong],None)):
    try:
        projection.render_ordinary_run(data_root=data,run_dir=run)
    except ValueError as error:
        assert str(error)=='ORDINARY_A05_SELECTED_BRANCH_CHANGED'
    else:
        raise AssertionError('WRONG_A05_NUMERIC_BRANCH_ACCEPTED')
body={'record_type':'ISSUE28_A05_FORMULA_NA_REPAIR_NUMERIC_NEGATIVE',
    'valid_private_result_id':first['result_id'],
    'valid_formula':first['formula'],
    'wrong_selected_branch_rejected':'ORDINARY_A05_SELECTED_BRANCH_CHANGED',
    'run_or_source_modified':False,'new_real_calls':[0,0,0]}
(HERE/'na-repair-numeric-negative.json').write_text(json.dumps(body,
    ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'valid_numeric_render':True,
    'wrong_branch_rejected':True}))
