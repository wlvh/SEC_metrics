"""Read the selected original and public scope; no Calculator or company state."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.normal_annual_input_v2 import exact_json_value
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE,YEAR_QUARTER_OR_DATE
import vnext.selected_reported_revenue_v2 as reported
import vnext.selected_revenue_scope_v1 as split


def inspect(source):
    result={'company_id':'enphase_energy','requested_fiscal_year':2021,'selected_role':'prior',
            'source_root':str(source),'new_business_calls':{'provider':0,'paid':0,'sec':0}}
    original=split._statement_scope
    def observe(*args,**kwargs):
        try:return original(*args,**kwargs)
        except ValueError as error:
            tb=error.__traceback__
            while tb:
                if tb.tb_frame.f_code==original.__code__:
                    local=tb.tb_frame.f_locals
                    result['rejected_table']=local['table']['table_id']
                    result['unresolved_cells']=[{k:c[k] for k in ('table_id','row_index','column_index','text','start_byte','end_byte') if k in c}
                        for c in local.get('unknown',[])]
                    result['heading_blocks']=[{k:b[k] for k in ('visible_text','start_byte','end_byte','span_sha256')}
                        for b in local.get('intro',[])]
                tb=tb.tb_next
            raise
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No live network')), \
         patch('vnext.calculator.calculate_metric',side_effect=AssertionError('Source inspection cannot calculate')):
        selection=resolve_period_selection(repo_root=source,company_id='enphase_energy',fiscal_year=2021)
        filing=selection['prior_filing']
        reader=_Sources(source,'enphase_energy','1463101')
        documents=reader.auditor_filing(filing)
        primary=next(s for s in documents if s['raw_blob']['media_type']=='text/html')
        xml=next(s for s in documents if s['raw_blob']['media_type']=='application/xml')
        annual={'company_id':'enphase_energy','entity':'1463101','filing':filing,
            'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1463101',filing=filing)}}
        result.update(filing=filing,actual_period=annual['table_input']['target_period'],
            primary_sha256=hashlib.sha256(primary['raw_bytes']).hexdigest(),
            xml_sha256=hashlib.sha256(xml['raw_bytes']).hexdigest(),source_reference=primary['source_reference'])
        with patch.object(reported,'_statement_scope',side_effect=observe):
            try:
                scope=reported.reported_revenue_scope(primary=primary,xml=xml,annual=annual,
                    approved_concepts=['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
                    namespace_policy=YEAR_OR_DATE_RELEASE,annual_period_reader=annual_period,
                    allow_single_revenue_line=True,allow_statement_group_totals=True,
                    allow_single_segment_revenue=True,dei_release=YEAR_QUARTER_OR_DATE)
            except ValueError as error:
                result.update(status='SOURCE_SCOPE_REJECTED',reason=str(error),exception_type=type(error).__name__)
            else:
                result.update(status='SOURCE_SCOPE_CHECKED',scope=scope)
    return exact_json_value(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=inspect(args.source_root.resolve())
    with args.output.open('x') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('status','reason','unresolved_cells','primary_sha256','xml_sha256') if k in result},indent=2))
