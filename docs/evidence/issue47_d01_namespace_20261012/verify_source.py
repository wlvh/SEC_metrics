"""One saved original D01 document through the explicit shared namespace API."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
from vnext.historical_risk_heading_case import ROOT
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_governance_input import _Sources
from vnext.d01_emphasis_source import build_text_document_admitting_underline
from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
from vnext.governance_signals import _FactAttributes

p=argparse.ArgumentParser()
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--company',required=True)
p.add_argument('--fiscal-year',type=int,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
    selected=resolve_period_selection(repo_root=a.source_root,company_id=a.company,
        fiscal_year=a.fiscal_year,rules_root=ROOT)
    annual=prepare_historical_annual_input(repo_root=a.source_root,company_id=a.company,
        period_selection=selected,rules_root=ROOT)
    source=_Sources(a.source_root,a.company,annual['entity']).primary(annual['filing'])
    period=annual['table_input']['target_period']
    document=build_text_document_admitting_underline(raw_bytes=source['raw_bytes'],
        raw_blob=source['raw_blob'],source_reference=source['source_reference'],
        expected_company_id=a.company,expected_cik=annual['entity'],
        expected_period_end=period['period_end'],namespace_policy=YEAR_QUARTER_OR_DATE)
    meta=_FactAttributes();meta.feed(source['raw_bytes'].decode('utf-8-sig'));meta.close()
    namespaces=sorted({f['concept'][0] for f in meta.facts.values()
                      if f['concept'][1].casefold() in
                      {'entitycentralindexkey','documentperiodenddate','documenttype'}})
assert document['source_state']=='COMPLETE_LOCAL_DOCUMENT'
report={'company':a.company,'fiscal_year':a.fiscal_year,'filing':annual['filing'],
        'period':period,'source':source['source_reference'],
        'actual_dei_namespaces':namespaces,'source_state':document['source_state'],
        'document_id':document['text_document_id'],
        'scope':'Source identity/period/coverage regression, not a company result',
        'new_calls':[0,0,0]}
with a.output.open('x') as stream:
    json.dump(report,stream,indent=2);stream.write('\n')
