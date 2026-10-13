"""Current shared reader against full saved notes; no financing completeness credit."""
import argparse,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.historical_b06_case import prepare_selected_debt_sources
from vnext import b06_bond_leases as bond
from vnext.normal_annual_input_v2 import exact_json_value

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args();start=time.monotonic()
assert not a.output.exists(), 'Choose a new output'
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')):
    selected=prepare_selected_debt_sources(repo_root=a.source_root,company_id='macys',fiscal_year=2024)
    prep=selected['preparation'];annual=prep['input_binding']['prepared_annual_input']
    options={'dei_release':'YEAR_QUARTER_OR_DATE','namespace_policy':'YEAR_OR_DATE_RELEASE'}
    notes=bond._notes(prep['primary'],prep['xml'],annual)
    reports=bond._balance_reports(prep['primary'],prep['xml'],annual,**options)
    bonds=bond._bond_schedule(notes['schedule'],annual['filing']['reportDate'],reports)
    members=bond._native_bond_members(prep['primary'],prep['xml'],annual,bonds,**options)
    label='7.60% Senior debentures due 2025'
    amounts={section:row['value'] for section,rows in bonds['members'].items()
             for row in rows if row['label']==label}
    assert amounts=={'current':'6000000','noncurrent':'0'}, amounts
    assert len(members)==sum(map(len,bonds['members'].values()))==21
    actual=[m for m in members if any(r['source_row']['label']==label for r in m['primary_reports'])]
    assert {m['classification']:m['value'] for m in actual}==amounts
    result=exact_json_value({'elapsed_seconds':str(time.monotonic()-start),'filing':annual['filing'],
        'period':annual['table_input']['target_period'],'bonds':bonds,'native_members':members,
        'source_references':{k:prep[k]['source_reference'] for k in ('primary','xml')},
        'complete_financing_scope_proven':False,'company_result_created':False,'calls':[0,0,0]})
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'bonds','native_members','source_references'}},indent=2))
print('members',len(members),'cross-section amounts',amounts)
