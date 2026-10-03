"""Check whether the current explicit grouped C02 proposal still selects block 3367."""
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.normal_run_v3 import prepare_case
from vnext.c02_composition_text_results import _prepared

case = prepare_case(data_root=ROOT, company_id='jpmorgan_chase', metric_id='C02',
                    c02_composition=True, c02_grouped=True)
args = {key:value for key,value in case['text_arguments'].items()
        if key != 'compiled_spec'}
prepared = _prepared(**args)
proposal = next(value for value in prepared['proposals'].values()
                if value.get('metric_id') == 'C02')
matches = [row for row in proposal['candidates']
           if 3367 in row.get('selected_source_blocks', [])]
assert len(matches) == 1
row, = matches
assert row['selected_source_blocks'] == [3367]
assert row['context_source_blocks'] == []
assert 'continued retention of PwC as the Firm’s independent external auditor' in row['text']
body = {'record_type':'ISSUE28_CURRENT_C02_GROUPED_JPM_AUDITOR_SCOPE_CHECK',
    'selection_policy':case['input_binding']['c02_selection_policy'],
    'original_selected_block_index':3367,
    'grouped_view_block_index':row['block_index'],
    'selected_source_blocks':row['selected_source_blocks'],
    'context_source_blocks':row['context_source_blocks'],
    'grouped_proposal_id':proposal['proposal_id'],
    'candidate_created':False,'native_result_created':False,
    'content_acceptance':False,'new_real_calls':[0,0,0],
    'scope_limit':'Current explicit proposal still selects this out-of-target original block; no complete C02 source audit.'}
(HERE/'v3-impact.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'policy':body['selection_policy'],
    'selected_source_blocks':body['selected_source_blocks'],
    'native_result_created':False,'new_real_calls':[0,0,0]}))
