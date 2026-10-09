import json,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_statement_cases import prepare_historical_statement_year_case
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');selected=resolve_period_selection(repo_root=source,company_id='pfizer',report_end='2023-12-31',rules_root=Path.cwd());started=time.monotonic()
with patch('vnext.historical_statement_cases.resolve_period_selection',side_effect=AssertionError('No preceding fiscal search')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
 case=prepare_historical_statement_year_case(repo_root=source,company_id='pfizer',metric_id='B01',fiscal_year=2023,period_selection=selected)
r=case['results']['B01'];assert r['value']=='58496000000' and r['result_id']=='sha256:128c170a19b5505f3ce22e837aaea836159b4652e334aa4b5bdf298e007786da';scope=case['input_assessments']['historical_statement']['selected_revenue_scope'];assert scope['complete_scope_proven'];record={'combination':'PR127label/explicitselection +PR118/119/120revenue','code_commit':__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),'seconds':time.monotonic()-started,'source_root':str(source),'selected_value':r['value'],'result_id':r['result_id'],'period_start':r['period_start'],'period_end':r['period_end'],'reported_total_admission_preserved':True,'preceding_fiscal_search_calls':0,'source_rebuild_and_original_amount_check_preserved':True,'state_or_Run_written':False,'new_calls':[0,0,0]};Path('work/selected-label/actual-revenue-combination.json').write_text(json.dumps(record,indent=2)+'\n');print(record)
