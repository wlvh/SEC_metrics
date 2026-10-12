import contextlib,io,json,socket,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 for company in ('pfizer','jpmorgan_chase','salesforce'):
  started=time.monotonic()
  before=resolve_ordinary_companyfacts_metrics(repo_root=source,company_id=company,rules_root=Path.cwd())
  after=resolve_ordinary_companyfacts_metrics(repo_root=source,company_id=company,rules_root=Path.cwd(),validate_revenue_scope=True,allow_single_revenue_line=True)
  for metric in before['metrics']:
   assert before['metrics'][metric]['result']==after['metrics'][metric]['result'],(company,metric,before['metrics'][metric]['result'],after['metrics'][metric]['result'],after['metrics'][metric]['selection'])
  row={'company':company,'elapsed_seconds':time.monotonic()-started,'B02':after['metrics']['B02']['result'],'other_ten_metrics_unchanged':True,'scope_statuses':{k:{'status':s['status'],'complete_scope_proven':s['complete_scope_proven']} for k,s in (after['metrics']['B02']['selection'] or {}).get('paired_revenue_scopes',{}).items()}}
  rows.append(row);print(json.dumps(row),flush=True)
Path('docs/evidence/issue28_current_complete_revenue_20261011/unaffected-consumers.json').write_text(json.dumps(rows,indent=2)+'\n')
