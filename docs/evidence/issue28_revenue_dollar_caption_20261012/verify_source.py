"""One real original dollar-caption source, no Run or new requests."""
import argparse,json,socket,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from vnext.normal_annual_input_v2 import exact_json_value
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expect',choices=('rejected','proved','diagnose'),required=True);a=p.parse_args()
filing={'form':'10-K','accessionNumber':'0001628280-23-003485','primaryDocument':'mar-20221231.htm','reportDate':'2022-12-31','filingDate':'2023-02-14'}
report={'filing':filing,'new_calls':[0,0,0]};t=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 items=_Sources(a.source_root,'marriott_international','1048286').auditor_filing(filing)
 primary=next(x for x in items if x['raw_blob']['media_type']=='text/html');xml=next(x for x in items if x['raw_blob']['media_type']=='application/xml')
 report['source_reference']=primary['source_reference']
 annual={'company_id':'marriott_international','entity':'1048286','filing':filing,'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1048286',filing=filing)}}
 report['period']=annual['table_input']['target_period']
 try:
  scope=reported_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=['us-gaap:Revenues'],annual_period_reader=annual_period,namespace_policy=YEAR_OR_DATE_RELEASE,allow_single_revenue_line=True,allow_statement_group_totals=True)
 except ValueError as error:
  report['reason']=str(error)
  tb=error.__traceback__
  while tb:
   if tb.tb_frame.f_code.co_name=='_statement_scope':
    loc=tb.tb_frame.f_locals
    report['unresolved_local_scope']=loc.get('unknown')
    report['intro']=loc.get('intro')
   tb=tb.tb_next
  assert a.expect=='diagnose' or a.expect=='rejected' and report['reason']=='SELECTED_REVENUE_STATEMENT_HEADING_SCOPE_UNRESOLVED'
 else:
  assert a.expect=='proved' and scope['complete_scope_proven']
  report.update(status=scope['status'],scope_id=scope['scope_id'],reported_totals=exact_json_value(scope['reported_totals']))
 report['seconds']=str(time.perf_counter()-t)
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='reported_totals'}))
 if 'reported_totals' in report:print('Reported USD totals',[r['total']['value'] for r in report['reported_totals']])
