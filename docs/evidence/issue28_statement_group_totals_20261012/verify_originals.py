"""Explicit revenue-group proof on saved originals, not a new business call."""
import argparse,json,socket
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from vnext.normal_annual_input_v2 import exact_json_value

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
rows=[]
filings=[{'form':'10-K','accessionNumber':'0001628280-25-004818','primaryDocument':'mar-20241231.htm','reportDate':'2024-12-31','filingDate':'2025-02-11'},
         {'form':'10-K','accessionNumber':'0001628280-24-004372','primaryDocument':'mar-20231231.htm','reportDate':'2023-12-31','filingDate':'2024-02-13'}]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 for filing in filings:
  reader=_Sources(a.source_root,'marriott_international','1048286');items=reader.auditor_filing(filing)
  primary=next(x for x in items if x['raw_blob']['media_type']=='text/html');xml=next(x for x in items if x['raw_blob']['media_type']=='application/xml')
  annual={'company_id':'marriott_international','entity':'1048286','filing':filing,'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1048286',filing=filing)}}
  scope=reported_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=['us-gaap:Revenues'],annual_period_reader=annual_period,namespace_policy=YEAR_OR_DATE_RELEASE,allow_statement_group_totals=True)
  row={'filing':filing,'source':primary['source_reference'],'status':scope['status'],'proof':scope['reported_totals']}
  rows.append(row);a.output.write_text(json.dumps(exact_json_value({'rows':rows,'new_calls':[0,0,0]}),indent=2)+'\n')
  print(filing['reportDate'],scope['status'],[r['total']['value'] for r in scope['reported_totals']],flush=True)
assert len(rows)==2 and all(r['status']=='REPORTED_CONSOLIDATED_TOTAL' for r in rows)
