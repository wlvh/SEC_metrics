import json,time
from pathlib import Path
from unittest.mock import patch
from vnext.historical_statement_cases import prepare_historical_statement_year_case
from vnext.normal_period_selection import resolve_period_selection
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
selected=resolve_period_selection(repo_root=source,company_id='marriott_international',report_end='2022-12-31',rules_root=Path.cwd());ops=[]
for name,choice,year in [('selected-valid',selected,2022),('wrong-accession',{**selected,'current_filing':{**selected['current_filing'],'accessionNumber':'0001628280-00-000001'}},2022),('wrong-requested-year',selected,2023)]:
 start=time.monotonic()
 with patch('vnext.historical_statement_cases.resolve_period_selection',side_effect=AssertionError('No preceding FY search')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
  try:case=prepare_historical_statement_year_case(repo_root=source,company_id='marriott_international',metric_id='B02',fiscal_year=year,period_selection=choice)
  except ValueError as e:
   assert name!='selected-valid';ops.append({'name':name,'seconds':time.monotonic()-start,'error_type':type(e).__name__,'reason':str(e)})
  else:
   assert name=='selected-valid';r=case['results']['B02'];assert r['value']=='0.4990979288446272641985999856' and r['result_id']=='sha256:8929038392f9d4b4016de922ef06cc76c017681219668af81f35e08b7e3a11de';ops.append({'name':name,'seconds':time.monotonic()-start,'result_id':r['result_id'],'value':r['value'],'period_start':r['period_start'],'period_end':r['period_end']})
 print(ops[-1],flush=True)
Path('docs/evidence/issue47_selected_label_20261010/actual-explicit-selection.json').write_text(json.dumps({'source_root':str(source),'preceding_fiscal_search_calls':0,'selection_source_rebuild_preserved':True,'operations':ops,'new_calls':[0,0,0]},indent=2)+'\n')
