import argparse,inspect,json,time
from pathlib import Path
from unittest.mock import patch
from vnext import selected_revenue_scope_v1 as scope
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_governance_input import _Sources
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.historical_dei import annual_period
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from vnext.canonical import sha256_bytes
parser=argparse.ArgumentParser();parser.add_argument('--year',required=True,type=int);parser.add_argument('--source-root',required=True,type=Path);parser.add_argument('--output-file',required=True,type=Path);a=parser.parse_args();year=a.year;source=a.source_root.resolve();observations=[];old=scope._need

def capture(condition,reason):
 if not condition and 'STATEMENT_LOCAL_SCOPE_UNRESOLVED' in reason:
  frame=inspect.currentframe().f_back
  while frame and frame.f_code.co_name != '_statement_scope':frame=frame.f_back
  assert frame is not None
  local=frame.f_locals;observations.append({'reason':reason,'unknown_cells':local.get('unknown'),'table_id':local.get('table',{}).get('table_id'),'source_sha256':sha256_bytes(content=local['raw'])})
 return old(condition,reason)
t=time.monotonic()
with patch('socket.socket.connect',side_effect=AssertionError('Saved only')):
 selection=resolve_period_selection(repo_root=source,company_id='lumen_technologies',fiscal_year=year);prepared=prepare_historical_annual_input(repo_root=source,company_id='lumen_technologies',period_selection=selection);reader=_Sources(source,'lumen_technologies',prepared['entity']);sources=reader.auditor_filing(prepared['filing']);primary=next(x for x in sources if x['raw_blob']['media_type']=='text/html');xml=next(x for x in sources if x['raw_blob']['media_type']=='application/xml')
 with patch.object(scope,'_need',side_effect=capture):
  try:reported_revenue_scope(primary=primary,xml=xml,annual=prepared.get('original_input',prepared),approved_concepts=['us-gaap:Revenues','us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax','us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax','us-gaap:SalesRevenueNet'],namespace_policy=YEAR_OR_DATE_RELEASE,annual_period_reader=annual_period,fiscal_label_resolution=prepared.get('fiscal_year_label_resolution'),allow_single_revenue_line=True)
  except ValueError as e:error=str(e)
  else:raise AssertionError('Original reported failure did not reproduce')
assert observations
out={'seconds':time.monotonic()-t,'original_filing':prepared['filing'],'period':prepared['table_input']['target_period'],'error':error,'source_bound_unknown_cells':observations,'new_calls':[0,0,0]};a.output_file.write_text(json.dumps(out,indent=2)+'\n');print(out['seconds'],error)
for o in observations:print(o['table_id'],[(c.get('row_index'),c.get('column_index'),c.get('text')) for c in o.get('unknown_cells',[])])
