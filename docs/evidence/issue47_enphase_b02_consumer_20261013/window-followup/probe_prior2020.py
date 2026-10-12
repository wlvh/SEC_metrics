"""Capture the actual selected FY2020 scope refusal; no Calculator or new task."""
import argparse,json
from pathlib import Path
from unittest.mock import patch
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.normal_annual_input_v2 import exact_json_value
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE,YEAR_QUARTER_OR_DATE
import vnext.selected_reported_revenue_v2 as reported
import vnext.selected_revenue_scope_v1 as split
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
result={'company':'enphase_energy','target_year':2021,'unresolved_role':'prior','new_calls':[0,0,0]}
actual=split._statement_scope
def observed(*args,**kwargs):
 try:return actual(*args,**kwargs)
 except ValueError as e:
  tb=e.__traceback__
  while tb:
   if tb.tb_frame.f_code==actual.__code__:
    loc=tb.tb_frame.f_locals
    table=loc['table'];result['rejected_table']={k:table[k] for k in ['table_id','rows','start_byte','end_byte'] if k in table}
    result['scope_locals']={k:loc[k] for k in ['intro','unknown','label','text','row_index','boundaries','limits'] if k in loc}
   tb=tb.tb_next
  result['reason']=str(e);raise
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
 selection=resolve_period_selection(repo_root=a.source_root,company_id='enphase_energy',fiscal_year=2021)
 filing=selection['prior_filing'];reader=_Sources(a.source_root,'enphase_energy','1463101');sources=reader.auditor_filing(filing)
 primary=next(s for s in sources if s['raw_blob']['media_type']=='text/html');xml=next(s for s in sources if s['raw_blob']['media_type']=='application/xml')
 annual={'company_id':'enphase_energy','entity':'1463101','filing':filing,'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1463101',filing=filing)}}
 result.update(filing=filing,period=annual['table_input']['target_period'],source_reference=primary['source_reference'])
 with patch.object(reported,'_statement_scope',side_effect=observed),patch.object(split,'_statement_scope',side_effect=observed):
  try:scope=reported.reported_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],namespace_policy=YEAR_OR_DATE_RELEASE,annual_period_reader=annual_period,allow_single_revenue_line=True,allow_statement_group_totals=True,allow_single_segment_revenue=True,dei_release=YEAR_QUARTER_OR_DATE)
  except ValueError as e:result['exception_type']=type(e).__name__;result['reason']=str(e)
  else:result['scope']=scope
with a.output.open('x') as f:json.dump(exact_json_value(result),f,indent=2);f.write('\n')
print(json.dumps({k:exact_json_value(result[k]) for k in ['reason','scope_locals','filing'] if k in result},indent=2))

