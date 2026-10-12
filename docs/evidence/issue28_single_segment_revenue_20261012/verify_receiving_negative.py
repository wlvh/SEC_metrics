"""Existing Macy FY2022 negative through the actual public route, no Run."""
import argparse
import functools
import json
import time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_governance_input import _Sources
from vnext.historical_paired_revenue import revenue_claims_admitted_by_original
from vnext.historical_statement_cases import StatementCaseError
import vnext.selected_reported_revenue_v2 as public

parser=argparse.ArgumentParser()
parser.add_argument('--source-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();started=time.perf_counter()
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
    selection=resolve_period_selection(repo_root=args.source_root,company_id='macys',fiscal_year=2022)
    prepared=prepare_historical_annual_input(repo_root=args.source_root,company_id='macys',period_selection=selection)
    reader=_Sources(args.source_root,'macys',prepared['entity'])
    # Only choose the new option. Parsing, source checks and actual return
    # values are not mocked; the historical production caller remains owned
    # by #47 and is not edited by this diagnostic.
    with patch.object(public,'reported_revenue_scope',new=functools.partial(
            public.reported_revenue_scope,allow_single_segment_revenue=True)):
        try:
            revenue_claims_admitted_by_original(reader=reader,prepared=prepared,filing=prepared['filing'],
                period=prepared['table_input']['target_period'],claims=[],
                concepts=['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax'],allow_single_revenue_line=True)
        except StatementCaseError as error:
            assert str(error)=='HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN'
            assert not error.revenue_scope['complete_scope_proven']
            result={'seconds':format(time.perf_counter()-started,'.6f'),'company_id':'macys',
                'fiscal_year':2022,'filing':prepared['filing'],'period':prepared['table_input']['target_period'],
                'reason':str(error),'category':error.category,'scope':error.revenue_scope,'new_calls':[0,0,0],
                'option_selection':'explicit partial wrapper; all production source functions and returns real'}
        else:
            raise AssertionError('Incomplete real scope must remain unproved')
args.output.write_text(json.dumps(result,indent=2)+'\n')
print(result['reason'],result['seconds'])
