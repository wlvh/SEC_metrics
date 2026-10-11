import json,sys,time
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal
from vnext.b06_note_carrying import inspect_note_carrying
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_governance_input import _Sources
from vnext.normal_source_authority import ROOT
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args()
assert not args.receipt.exists(), 'Receipt path must be new'
source=args.source_root.resolve()
t=time.monotonic()
with patch('socket.socket.connect',side_effect=AssertionError('No new network')):
 selection=resolve_period_selection(repo_root=source,company_id='enphase_energy',fiscal_year=2024,rules_root=ROOT)
 annual=prepare_historical_annual_input(repo_root=source,company_id='enphase_energy',period_selection=selection,rules_root=ROOT)
 original=annual['original_input'];reader=_Sources(source,'enphase_energy',original['entity'])
 sources=reader.auditor_filing(original['filing'])
 preparation={kind:next(item for item in sources if item['raw_blob']['media_type']==media) for kind,media in [('primary','text/html'),('xml','application/xml')]}
 proof=inspect_note_carrying(primary=preparation['primary'],xml=preparation['xml'],prepared=original)
assert proof['composition']['balances']=={'total':'1302380000','current':'101291000','noncurrent':'1201089000'}
assert proof['reports']['equity']['chosen']['value']=='833016000'
assert proof['finance_lease_absence']['basis']=='EXPLICIT_CURRENT_ISSUER_POLICY'
ratio=Decimal(proof['composition']['balances']['total'])/Decimal(proof['reports']['equity']['chosen']['value'])
assert str(ratio)=='1.563451362278755750189672227'
r={'code_commit':'dded207e','company_id':'enphase_energy','fiscal_year':2024,'filing':original['filing'],'entity':original['entity'],'seconds':time.monotonic()-t,'ratio':str(ratio),'proof':proof,'scope':'Actual source inspector only; no company case/store/Run/acceptance','new_calls':[0,0,0]}
args.receipt.write_text(json.dumps(r,indent=2)+'\n')
print('Enphase FY2024 complete note/equity/explicit lease absence matches retained reference',r['seconds'],str(ratio))
