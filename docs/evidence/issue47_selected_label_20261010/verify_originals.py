import json,hashlib,time
from pathlib import Path
from unittest.mock import patch
from vnext.historical_fiscal_labels import resolve_selected_fiscal_year_label
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
receipt=json.loads(__import__('subprocess').check_output(['git','show','ebf6d877:docs/evidence/issue47_selected_source_consumer_20261010/actual-cli.json'],text=True));outputs=[]
for scene in receipt['scenes'][:2]:
 plan=json.loads(Path(scene['output_file']).read_text());filing=plan['filing_selection']['current_filing'];cik=plan['filing_selection']['reporting_cik'];primary=next(r for r in plan['requirements'] if 'target_annual_primary' in r['roles']);cf=next(r for r in plan['requirements'] if 'selected_companyfacts' in r['roles']);pb=(source/primary['proof']['request_repo_relative_path']).read_bytes();fb=(source/cf['proof']['request_repo_relative_path']).read_bytes();start=time.monotonic()
 with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('vnext.historical_annual_input.prepare_historical_annual_input',side_effect=AssertionError('No full annual preparation')):
  result=resolve_selected_fiscal_year_label(primary_bytes=pb,companyfacts_bytes=fb,expected_primary_sha256=primary['proof']['content_sha256'],expected_companyfacts_sha256=cf['proof']['content_sha256'],expected_cik=cik,filing=filing)
 elapsed=time.monotonic()-start;outputs.append({'company_id':scene['company_id'],'seconds':elapsed,'resolution':result,'primary_path':primary['proof']['request_repo_relative_path'],'companyfacts_path':cf['proof']['request_repo_relative_path']});print(scene['company_id'],elapsed,result['selected_fiscal_year'],result['original_dei_fiscal_year'],flush=True)
 if scene['company_id']=='salesforce':assert result['selected_fiscal_year']==2026 and result['original_dei_fiscal_year']==2025 and result['metadata_conflict_retained']
 else:assert result['selected_fiscal_year']==2023 and result['actual_period']=={'period_start':'2023-01-29','period_end':'2024-02-03'}
Path('docs/evidence/issue47_selected_label_20261010/actual-originals.json').write_text(json.dumps({'caller_source_admission':'Previously verified public preflight proof bytes; no new admission grant','source_root':str(source),'scenes':outputs,'full_annual_preparation_calls':0,'new_calls':[0,0,0]},indent=2)+'\n')
