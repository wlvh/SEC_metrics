"""Finite reference/shape controls; semantic mistakes are not auto-certified."""
import copy
import json
from pathlib import Path
from vnext import d03_model_processing as m

HERE=Path(__file__).parent
summary=json.loads((HERE/'time-input-summary.json').read_text());payload=json.loads((Path(summary['input_root'])/'input.json').read_text());units={u['unit_id']:u for u in payload['source_units']};answer=json.loads((HERE/'independent-time-input/response.log').read_text());rows=[]
for label,edit in [('reference_boolean',lambda a:a['findings'][0]['evidence'][0].update(source_index=True)),('reference_kind',lambda a:a['findings'][0]['evidence'][0].update(kind='NATIVE_FACT')),('exact_duplicate',lambda a:a['findings'].append(copy.deepcopy(a['findings'][0]))),('wrong_reviewed_owner',lambda a:a.update(reviewed_unit_ids=payload['context_only_unit_ids']))]:
 value=copy.deepcopy(answer);edit(value)
 try:m._response(m._bytes(value),payload,units)
 except ValueError as e:rows.append({'case':label,'structural':'REFUSED','reason':str(e),'semantic_credit':False})
 else:raise AssertionError(label+' not refused')
# Existing structure checks do not claim model meaning is true. Retain these
# explicit countercontrols rather than add another semantic regex checker.
for label,edit in [('removed_amrapali_investigation',lambda a:a['findings'].pop(1)),('current_action_cites_financial_table',lambda a:a['findings'][0]['evidence'][0].update(source_index=10021))]:
 value=copy.deepcopy(answer);edit(value);m._response(m._bytes(value),payload,units);rows.append({'case':label,'structural':'PASS_ONLY','semantic_credit':False,'original_comparison_required':True,'full_company_entry_still_refused':True})
(HERE/'negative-controls.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rows))
