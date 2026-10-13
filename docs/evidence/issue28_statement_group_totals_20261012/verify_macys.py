"""The saved Macy FY2022 original stays unproved with the new option."""
import argparse,json,socket,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.historical_fiscal_labels import resolve_selected_fiscal_year_label
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from vnext.canonical import sha256_bytes
from sec_urls import companyfacts_url
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
filing={'form':'10-K','accessionNumber':'0001628280-23-009154','primaryDocument':'m-20230128.htm','reportDate':'2023-01-28','filingDate':'2023-03-24'}
t=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 reader=_Sources(a.source_root,'macys','794367');items=reader.auditor_filing(filing)
 primary=next(x for x in items if x['raw_blob']['media_type']=='text/html');xml=next(x for x in items if x['raw_blob']['media_type']=='application/xml')
 annual={'company_id':'macys','entity':'794367','filing':filing,'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='794367',filing=filing)}}
 facts=reader.read(companyfacts_url(cik=794367),accession=filing['accessionNumber'],role='companyfacts',media_type='application/json')
 label=resolve_selected_fiscal_year_label(primary_bytes=primary['raw_bytes'],companyfacts_bytes=facts['raw_bytes'],expected_primary_sha256=sha256_bytes(content=primary['raw_bytes']),expected_companyfacts_sha256=sha256_bytes(content=facts['raw_bytes']),expected_cik='794367',filing=filing)
 scope=reported_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=['us-gaap:Revenues','us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax','us-gaap:SalesRevenueNet'],annual_period_reader=annual_period,namespace_policy=YEAR_OR_DATE_RELEASE,fiscal_label_resolution=label,allow_single_revenue_line=True,allow_statement_group_totals=True)
 assert not scope['complete_scope_proven']
 report={'filing':filing,'source_reference':primary['source_reference'],'period':annual['table_input']['target_period'],'status':scope['status'],'complete_scope_proven':False,'reported_total_count':len(scope['reported_totals']),'new_calls':[0,0,0],'seconds':str(time.perf_counter()-t)}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
