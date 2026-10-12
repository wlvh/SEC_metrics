"""Actual saved schedule refusal; no synthetic financial operand or network."""
import argparse,inspect,json,socket
from pathlib import Path
from unittest.mock import patch
from vnext.historical_b06_case import prepare_selected_debt_sources
from vnext import b06_bond_leases as bond
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
source=args.source_root.resolve();output=args.output.resolve();assert not output.exists(),'Output exists; choose a new path'
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')):
 selected=prepare_selected_debt_sources(repo_root=source,company_id='macys',fiscal_year=2024)
 preparation=selected['preparation'];annual=preparation['input_binding']['prepared_annual_input']
 notes=bond._notes(preparation['primary'],preparation['xml'],annual)
 reports=bond._balance_reports(preparation['primary'],preparation['xml'],annual,dei_release='YEAR_QUARTER_OR_DATE',namespace_policy='YEAR_OR_DATE_RELEASE')
 captured={};original=bond._need
 def observe(condition,reason):
  if not condition and reason=='BOND_MEMBER_DUPLICATED':
   frame=inspect.currentframe().f_back
   while frame and frame.f_code.co_name!='_bond_schedule':frame=frame.f_back
   assert frame is not None
   for key in ('parts','totals','adjustments'):captured[key]=frame.f_locals[key]
   captured['table_id']=frame.f_locals['table']['table_id'];captured['current_column']=frame.f_locals['col'];captured['year_header_row']=frame.f_locals['header']
  return original(condition,reason)
 with patch.object(bond,'_need',side_effect=observe):
  try:bond._bond_schedule(notes['schedule'],annual['filing']['reportDate'],reports)
  except bond.BondLeaseError as error:captured['reason']=str(error)
 captured.update(filing=annual['filing'],period=annual['table_input']['target_period'],source_references={k:preparation[k]['source_reference'] for k in ('primary','xml')},new_calls=[0,0,0])
 labels={}
 for section,rows in captured.get('parts',{}).items():
  for row in rows:labels.setdefault(row['label'],[]).append({'section':section,'value':row['value'],'row_index':row['row']['row_index']})
 captured['cross_section_duplicates']={k:v for k,v in labels.items() if len(v)>1}
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(captured,indent=2)+'\n')
 assert captured['reason']=='BOND_LEASE_BOND_MEMBER_DUPLICATED',captured
 print(json.dumps({'table_id':captured['table_id'],'reason':captured['reason'],'duplicates':captured['cross_section_duplicates'],'period':captured['period']},indent=2))
