"""One existing real incomplete-scope negative at the historical adapter; no Run."""
import argparse,json,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_governance_input import _Sources
from vnext.historical_paired_revenue import revenue_claims_admitted_by_original
from vnext.historical_statement_cases import StatementCaseError
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
start=time.perf_counter()
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
 selection=resolve_period_selection(repo_root=a.source_root,company_id='macys',fiscal_year=2022)
 prepared=prepare_historical_annual_input(repo_root=a.source_root,company_id='macys',period_selection=selection)
 reader=_Sources(a.source_root,'macys',prepared['entity'])
 try:
  revenue_claims_admitted_by_original(reader=reader,prepared=prepared,filing=prepared['filing'],period=prepared['table_input']['target_period'],claims=[],concepts=['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax'],allow_single_revenue_line=True)
 except StatementCaseError as e:
  assert str(e)=='HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN' and not e.revenue_scope['complete_scope_proven']
  result={'seconds':time.perf_counter()-start,'company_id':'macys','fiscal_year':2022,'filing':prepared['filing'],'period':prepared['table_input']['target_period'],'reason':str(e),'category':e.category,'scope':e.revenue_scope,'new_calls':[0,0,0]}
 else:raise AssertionError('True incomplete-scope original must remain refused')
with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(result['reason'],round(result['seconds'],3))
