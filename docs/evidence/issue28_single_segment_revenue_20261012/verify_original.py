"""Bounded saved-original scope checks; no new company or external calls."""
import argparse
import json
import socket
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

from vnext.canonical import sha256_bytes
from vnext.historical_dei import annual_period
from vnext.normal_governance_input import _Sources
from vnext.normal_annual_input_v2 import exact_json_value
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
import vnext.selected_reported_revenue_v2 as revenue


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',required=True)
    parser.add_argument('--prior-output',type=Path)
    args=parser.parse_args()
    old=dict(revenue.__dict__)
    exec(subprocess.check_output(['git','show',args.baseline+':scripts/vnext/selected_reported_revenue_v2.py'],text=True),old)
    filing={'form':'10-K','reportDate':'2024-12-31','filingDate':'2025-02-10',
        'accessionNumber':'0001463101-25-000024','primaryDocument':'enph-20241231.htm'}
    started=time.perf_counter()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
        items=_Sources(args.source_root,'enphase_energy','1463101').auditor_filing(filing)
        primary=next(item for item in items if item['raw_blob']['media_type']=='text/html')
        xml=next(item for item in items if item['raw_blob']['media_type']=='application/xml')
        annual={'company_id':'enphase_energy','entity':'1463101','filing':filing,
            'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1463101',filing=filing)}}
        kwargs={'primary':primary,'xml':xml,'annual':annual,
            'approved_concepts':['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
            'annual_period_reader':annual_period,'namespace_policy':YEAR_OR_DATE_RELEASE}
        before=old['reported_revenue_scope'](**kwargs)
        default=revenue.reported_revenue_scope(**kwargs)
        assert exact_json_value(before)==exact_json_value(default)
        assert not default['complete_scope_proven']
        current=revenue.reported_revenue_scope(**kwargs,allow_single_segment_revenue=True)
        assert current['complete_scope_proven'] and len(current['reported_totals'])==1
        total=current['reported_totals'][0]['total']
        assert total['value']=='1330383000' and total['context_ref']=='c-6'
        assert total['context']['dimensions']=={'us-gaap:StatementBusinessSegmentsAxis':'enph:ReportableSegmentMember'}
        assert current['reported_totals'][0]['xml_check']=='MATCH'
        assert total['single_segment_scope']['status']=='ONE_OPERATING_AND_REPORTABLE_SEGMENT'
        assert all(row['value']=='1' for rows in total['single_segment_scope']['counts'].values() for row in rows)
        assert current['reported_totals'][0]['consolidated_statement_rows']
    result={'baseline':args.baseline,'code_root':str(Path.cwd()),'source_root':str(args.source_root.resolve()),
        'default_proof_identical':True,'primary_sha256':sha256_bytes(content=primary['raw_bytes']),
        'xml_sha256':sha256_bytes(content=xml['raw_bytes']),'source_scope':current,
        'elapsed_seconds':format(time.perf_counter()-started,'.6f'),'new_calls':[0,0,0],
        'scope':'source proof only; native dimensional fact is not a Calculator operand or a company Result'}
    args.output.write_text(json.dumps(exact_json_value(result),ensure_ascii=False,indent=2)+'\n')
    print(current['status'],total['value'],total['context_ref'],result['elapsed_seconds'],flush=True)
    if args.prior_output:
        started=time.perf_counter()
        prior_filing={'form':'10-K','reportDate':'2023-12-31','filingDate':'2024-02-09',
            'accessionNumber':'0001463101-24-000024','primaryDocument':'enph-20231231.htm'}
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            prior_items=_Sources(args.source_root,'enphase_energy','1463101').auditor_filing(prior_filing)
            primary=next(item for item in prior_items if item['raw_blob']['media_type']=='text/html')
            xml=next(item for item in prior_items if item['raw_blob']['media_type']=='application/xml')
            prior_annual={'company_id':'enphase_energy','entity':'1463101','filing':prior_filing,
                'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1463101',filing=prior_filing)}}
            kwargs={**kwargs,'primary':primary,'xml':xml,'annual':prior_annual}
            before=old['reported_revenue_scope'](**kwargs,allow_single_revenue_line=True)
            assert not before['complete_scope_proven']
            current=revenue.reported_revenue_scope(**kwargs,allow_single_revenue_line=True,
                allow_single_segment_revenue=True)
            assert current['complete_scope_proven'] and len(current['reported_totals'])==1
            total=current['reported_totals'][0]['total']
            assert total['value']=='2290786000' and not total['context']['dimensions']
            assert 'single_segment_scope' not in total
            assert current['reported_totals'][0]['xml_check']=='MATCH'
        result={'baseline':args.baseline,'primary_sha256':sha256_bytes(content=primary['raw_bytes']),
            'xml_sha256':sha256_bytes(content=xml['raw_bytes']),'source_scope':current,
            'elapsed_seconds':format(time.perf_counter()-started,'.6f'),'new_calls':[0,0,0],
            'before_status':before['status'],'scope':'own prior nondimensional source proof; not a company B02 Result'}
        args.prior_output.write_text(json.dumps(exact_json_value(result),ensure_ascii=False,indent=2)+'\n')
        print(prior_filing['reportDate'],current['status'],total['value'],result['elapsed_seconds'],flush=True)


if __name__=='__main__':
    main()
