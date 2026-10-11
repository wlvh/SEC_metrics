"""Saved Paramount original plus a small complete-expense statement control."""
from pathlib import Path
import json,socket
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.selected_revenue_scope_v1 import selected_revenue_scope
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from tests.vnext.test_single_revenue_line import single_statement
from tests.vnext.test_selected_reported_revenue_v2 import changed
from tests.vnext.test_selected_revenue_scope_v1 import APPROVED
from vnext.normal_run_specs import installed_ordinary_spec_documents
import argparse
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
root=args.source_root;company='paramount_skydance_paramount_global';filing={'form':'10-K','reportDate':'2024-12-31','filingDate':'2025-02-26','accessionNumber':'0000813828-25-000005','primaryDocument':'para-20241231.htm'}
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 reader=_Sources(root,company,'813828');originals=reader.auditor_filing(filing);primary=next(s for s in originals if s['raw_blob']['media_type']=='text/html');xml=next(s for s in originals if s['raw_blob']['media_type']=='application/xml');period=annual_period(raw=primary['raw_bytes'],cik='813828',filing=filing);annual={'company_id':company,'entity':'813828','filing':filing,'table_input':{'target_period':period}}
 concepts=installed_ordinary_spec_documents()['B01']['compiled_spec']['compiled']['inputs']['revenue']['structured_role']['approved_concepts']
 options={'primary':primary,'xml':xml,'annual':annual,'approved_concepts':concepts,'namespace_policy':YEAR_OR_DATE_RELEASE,'annual_period_reader':annual_period}
 real=reported_revenue_scope(**options,allow_single_revenue_line=True);fallback=selected_revenue_scope(**options)
 synthetic,synthetic_annual=single_statement();raw=synthetic['raw_bytes'].replace(b'Cost of sales',b'Total costs and expenses').replace(b'CostOfGoodsAndServicesSold',b'CostsAndExpenses');control=changed(synthetic,raw)
 small=reported_revenue_scope(primary=control,xml=control,annual=synthetic_annual,approved_concepts=APPROVED,allow_single_revenue_line=True)
 result={'actual_source':primary['source_reference'],'actual_period':period,'real_reported':{k:real[k] for k in ['scope_id','status','complete_scope_proven']},'real_fallback':{k:fallback[k] for k in ['scope_id','status','complete_scope_proven']},'constructed_complete_expense_control':{k:small[k] for k in ['scope_id','status','complete_scope_proven']},'not_a_financial_result':True,'new_calls':0}
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
