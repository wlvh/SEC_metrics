import json,time,hashlib,socket,gzip
from pathlib import Path
from unittest.mock import patch
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
from vnext.deterministic_router import shared_xbrl_parses
root=Path.cwd();base=root/'docs/evidence/issue47_history/historical-income-receiving-2026-10-08'
company='paramount_skydance_paramount_global'
ledger=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-sec-ledger-resume-20261006/claims.jsonl');before=ledger.read_bytes()
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')), shared_xbrl_parses():
 selection=resolve_period_selection(repo_root=root,company_id=company,fiscal_year=2025)
 out={}
 for m in ['B01','B03']:
  target=base/(m+'-component.json.gz')
  if target.exists():out[m]=json.loads(gzip.decompress(target.read_bytes()))
  else:
   out[m]=resolve_historical_zero_ai_metric(repo_root=root,company_id=company,metric_id=m,period_selection=selection)
   target.write_bytes(gzip.compress((json.dumps(out[m],ensure_ascii=False,indent=2)+'\n').encode(),mtime=0))
for m,c in out.items():
 assert c['result']['publication']=='WITHHELD' and c['result']['value'] is None,(m,c['result'])
 assert c['result']['reason_code']=='ORDINARY_INCOME_VISIBLE_PERIOD_CONFLICT',c['selection']
 assert c['selection']['category']=='SOURCE_PERIOD_CONFLICT'
 evidence=c['selection']['income_period_evidence']
 assert evidence['native_period']==['2025-08-08','2025-12-31'] and ['2025-08-07','2025-12-31'] in evidence['visible_periods'],evidence
assert ledger.read_bytes()==before
record={'source_root':str(root),'selection_accession':out['B01']['prepared_input']['filing']['accessionNumber'],'seconds':time.monotonic()-start,'metrics':{m:{'publication':c['result']['publication'],'value':c['result']['value'],'reason':c['result']['reason_code'],'coordinate':c['pinned_target_period'],'evidence_count':len(c['selection']['income_period_evidence'])} for m,c in out.items()},'new_calls':{'sec':0,'provider':0,'paid':0},'ledger_sha256':hashlib.sha256(before).hexdigest(),'old_results_or_runs_modified':False,'B01_saved_component_reused_after_record_writer_error':True,'seconds_scope':'B03 necessary completion and record checks only; earlier full pair time not saved'}
(base/'saved-source-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record))
