from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import c02_board_composition_28_v3 as old
from vnext import c02_board_composition_28_v4 as current
own=frozenset({'audit','compensation'})
text='The members of the Audit Committee are responsible for supervising Mr. Smith, our external auditor.'
a=old.statement_labels(text,own,period_start='2025-01-01');b=current.statement_labels(text,own,period_start='2025-01-01')
assert 'COMMITTEE_COMPOSITION_STATEMENT' in a and 'COMMITTEE_COMPOSITION_STATEMENT' in b
body={'record_type':'ISSUE28_C02_MEMBER_ROLE_SYNTHETIC_REMAINING_LIMIT','text':text,'old_labels':a,'new_labels':b,'expected_scope':'COMMITTEE_DUTY_AND_OUTSIDE_AUDITOR_NOT_COMPOSITION','own_contract':'catalog/r6/C02_board_disclosures_v5.md','material_type':'SYNTHETIC; NOT_OBSERVED_IN_CURRENT_SOURCE','native_result_affected_by_this_sentence':'NOT_ESTABLISHED','whole_selector_readiness':False,'new_real_calls':[0,0,0]}
Path(__file__).with_suffix('.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n');print(json.dumps(body,ensure_ascii=False))
