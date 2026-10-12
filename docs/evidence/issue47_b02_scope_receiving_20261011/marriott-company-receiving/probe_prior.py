"""Capture the actual shared reader's rejected FY2022 heading, without a Run."""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE

p=argparse.ArgumentParser()
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
filing={'form':'10-K','accessionNumber':'0001628280-23-003485',
        'primaryDocument':'mar-20221231.htm','reportDate':'2022-12-31',
        'filingDate':'2023-02-14'}
report={'filing':filing,'new_calls':[0,0,0]}
def capture(error):
    tb=error.__traceback__
    while tb:
        frame=tb.tb_frame
        if frame.f_code.co_name=='_statement_scope':
            loc=frame.f_locals
            report['rejected_intro']=loc.get('intro')
            table=loc['table']
            report['table']={k:table[k] for k in ['table_id','order','start_byte','end_byte'] if k in table}
            report['exception']=str(error)
        tb=tb.tb_next
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
    reader=_Sources(a.source_root,'marriott_international','1048286')
    items=reader.auditor_filing(filing)
    primary=next(x for x in items if x['raw_blob']['media_type']=='text/html')
    xml=next(x for x in items if x['raw_blob']['media_type']=='application/xml')
    report['source']=primary['source_reference']
    annual={'company_id':'marriott_international','entity':'1048286','filing':filing,
            'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1048286',filing=filing)}}
    report['period']=annual['table_input']['target_period']
    try:
        reported_revenue_scope(primary=primary,xml=xml,annual=annual,
            approved_concepts=['us-gaap:Revenues'],annual_period_reader=annual_period,
            namespace_policy=YEAR_OR_DATE_RELEASE,allow_single_revenue_line=True,
            allow_statement_group_totals=True)
    except ValueError as e:
        report['reason']=str(e)
        capture(e)
assert report['reason']=='SELECTED_REVENUE_STATEMENT_HEADING_SCOPE_UNRESOLVED'
assert report.get('rejected_intro'), 'The actual reader frame must be captured'
with a.output.open('x') as stream:
    json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps({k:report[k] for k in ['reason','table','rejected_intro']},indent=2))
