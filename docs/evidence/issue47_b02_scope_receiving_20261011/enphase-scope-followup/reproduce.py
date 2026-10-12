"""The actual selected original through the existing native income reader."""
import argparse,json
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_source_authority import ROOT
from vnext.historical_dei import annual_period
from vnext.selected_income_source_v1 import native_income_reports
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
p=argparse.ArgumentParser()
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
    selection=resolve_period_selection(repo_root=a.source_root,company_id='enphase_energy',
        fiscal_year=2024,rules_root=ROOT)
    annual=prepare_historical_annual_input(repo_root=a.source_root,company_id='enphase_energy',
        period_selection=selection,rules_root=ROOT)
    original=annual.get('original_input',annual)
    primary=_Sources(a.source_root,'enphase_energy',annual['entity']).primary(annual['filing'])
    rows=native_income_reports(primary,original,
        ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax','us-gaap:CostOfRevenue',
         'us-gaap:GrossProfit','us-gaap:OperatingIncomeLoss','us-gaap:NetIncomeLoss'],
        namespace_policy=YEAR_OR_DATE_RELEASE,annual_period_reader=annual_period)
report={'filing':annual['filing'],'period':annual['table_input']['target_period'],
        'source_reference':primary['source_reference'],
        'current_native_reports':[r for r in rows if r['period_start']=='2024-01-01'],
        'note':'The dimensional statement revenue is excluded before scope inspection; note totals remain distinct',
        'new_calls':[0,0,0]}
with a.output.open('x') as stream:
    json.dump(report,stream,indent=2);stream.write('\n')
