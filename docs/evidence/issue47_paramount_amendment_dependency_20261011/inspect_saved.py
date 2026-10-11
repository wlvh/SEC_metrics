import json,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_governance_input import _Sources
from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
from vnext.canonical import sha256_bytes
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');company='paramount_skydance_paramount_global';start=time.monotonic()
with patch('socket.socket.connect',side_effect=AssertionError('Saved sources only')):
 selection=resolve_period_selection(repo_root=source,company_id=company,fiscal_year=2024)
 prepared=prepare_historical_annual_input(repo_root=source,company_id=company,period_selection=selection)
 reader=_Sources(source,company,prepared['entity']);old=reader.primary(prepared['filing']);checks=[]
 for filing in prepared['amendments']:
  amended=reader.primary(filing)
  result=inspect_annual_amendment_scope(original={'raw':old['raw_bytes'],'blob':old['raw_blob'],'reference':old['source_reference'],'filing':prepared['filing']},amendment={'raw':amended['raw_bytes'],'blob':amended['raw_blob'],'reference':amended['source_reference'],'filing':filing},company_id=company,cik=prepared['entity'],note_layout='inline-paragraphs-v2')
  checks.append({'scope_id':result['scope_id'],'classification':result['classification'],'issues':result['issues'],'fiscal_window_unchanged':result['fiscal_window_unchanged'],'unchanged_input_classes':result['unchanged_input_classes'],'further_review':result['original_statement_admission_requires_further_review'],'note':result['explanatory_note'],'details':result['details'],'original_filing':prepared['filing'],'amendment_filing':filing,'source_sha':{'original':sha256_bytes(content=old['raw_bytes']),'amendment':sha256_bytes(content=amended['raw_bytes'])}})
out={'seconds':time.monotonic()-start,'company_id':company,'entity':prepared['entity'],'period':prepared['table_input']['target_period'],'checks':checks,'new_calls':[0,0,0]};Path('work/paramount-amendment-diagnostic/result.json').write_text(json.dumps(out,indent=2)+'\n');print(out['seconds'],len(checks))
for c in checks:print(c['classification'],c['issues'],c['unchanged_input_classes'],c['further_review']);print(c['note']['text'])
