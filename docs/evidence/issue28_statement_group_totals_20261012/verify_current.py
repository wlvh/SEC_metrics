"""Compare the unchanged default on a saved current filing, zero new calls."""
import argparse,json,socket,subprocess,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',required=True);a=p.parse_args()
original=subprocess.check_output(['git','show',a.baseline+':scripts/vnext/selected_reported_revenue_v2.py'],text=True)
old={'__package__':'vnext','__name__':'vnext.baseline_reported_revenue'};exec(compile(original,'baseline_source','exec'),old)
filing={'form':'10-K','accessionNumber':'0001048286-26-000007','primaryDocument':'mar-20251231.htm','reportDate':'2025-12-31','filingDate':'2026-02-10'}
t=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 items=_Sources(a.source_root,'marriott_international','1048286').auditor_filing(filing)
 primary=next(x for x in items if x['raw_blob']['media_type']=='text/html');xml=next(x for x in items if x['raw_blob']['media_type']=='application/xml')
 annual={'company_id':'marriott_international','entity':'1048286','filing':filing,'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1048286',filing=filing)}}
 args={'primary':primary,'xml':xml,'annual':annual,'approved_concepts':['us-gaap:Revenues'],'annual_period_reader':annual_period,'namespace_policy':YEAR_OR_DATE_RELEASE,'allow_single_revenue_line':True}
 before=old['reported_revenue_scope'](**args);after=reported_revenue_scope(**args)
 assert before==after
 explicit=reported_revenue_scope(**args,allow_statement_group_totals=True)
 values=[r['total']['value'] for r in explicit['reported_totals']]
 assert values==['26186000000']
 report={'source_reference':primary['source_reference'],'filing':filing,'period':annual['table_input']['target_period'],'baseline':a.baseline,'default_unchanged':True,'default_status':after['status'],'explicit_values':values,'scope_id_before':before['scope_id'],'scope_id_after':after['scope_id'],'company_result_recomputed':False,'new_calls':[0,0,0],'seconds':str(time.perf_counter()-t)}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
