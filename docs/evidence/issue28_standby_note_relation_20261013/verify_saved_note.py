"""Check actual other financing notes; no manual debt value or live call."""
import argparse,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.historical_b06_case import prepare_selected_debt_sources
from vnext import b06_bond_leases as bond
from vnext.normal_annual_input_v2 import exact_json_value

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--full-scope',action='store_true')
p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    prep=prepare_selected_debt_sources(repo_root=a.source_root,company_id='macys',fiscal_year=2024)['preparation']
    annual=prep['input_binding']['prepared_annual_input'];notes=bond._notes(prep['primary'],prep['xml'],annual)
    partial=shared_scope=None
    try:
        other=bond._reported_other_natures(notes,annual)
        assert other['standby_current']=='144000000'
        assert other['unused_capacity'] is other['facility_limit'] is None
        assertions=bond._current_borrowing_assertions(notes,annual,other);next_refusal=None
        if a.full_scope:
            proof=bond.inspect_bond_debt_scope(primary=prep['primary'],xml=prep['xml'],prepared=annual,
                dei_release='YEAR_QUARTER_OR_DATE',namespace_policy='YEAR_OR_DATE_RELEASE')
            shared_scope={'record_type':proof['record_type'],'legacy_complete_b06_proven_field':proof['complete_b06_proven'],
                'native_members':len(proof['native_bond_members']),
                'inventory_rows':{kind:len(rows) for kind,rows in proof['independent_financing_inventory'].items()},
                'reported_borrowing':proof['bonds']['reported_borrowing']}
    except bond.BondLeaseError as error:
        other=assertions=None;next_refusal=str(error);trace=error.__traceback__
        while trace:
            if trace.tb_frame.f_code.co_name=='_reported_other_natures':
                values=trace.tb_frame.f_locals;standby=values.get('standby')
                assert standby is not None and standby[1]=='144' and standby[3] is None
                partial={'actual_matched_standby':standby[0],'standby_current':str(values['amount'](standby[1])),
                    'unused_capacity':values['unused_capacity'],'facility_limit':values['facility_limit']}
            trace=trace.tb_next
    result=exact_json_value({'elapsed_seconds':str(time.monotonic()-start),'other':other,
        'next_borrowing_assertion_refusal':next_refusal,'assertions':assertions,'partial_not_scope_credit':partial,
        'shared_component_proof_not_current_acceptance':shared_scope,
        'debt_note':notes['debt']['text'],'commitment_note':notes['commitments']['text'],
        'filing':annual['filing'],'period':annual['table_input']['target_period'],
        'source_references':{k:prep[k]['source_reference'] for k in ('primary','xml')},
        'complete_scope_proven':False,'calls':[0,0,0]})
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'debt_note','commitment_note','source_references','assertions'}},indent=2))
