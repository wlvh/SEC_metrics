import hashlib,json,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from vnext import text_business_candidates as c
from vnext.r6_semantic_source import prepare_d04_semantic_source
from vnext.capacity_update_input import source_equivalence
from vnext.continuous_semantic_calls import source_requests
SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
start=time.perf_counter()
with patch.object(c,'_financial_report_boundary',side_effect=lambda b:b.get('emphasized') and c._FINANCIAL_HEADING.match(b['text'])):
 before=prepare_d04_semantic_source(repo_root=SOURCE,company_id='lumen_technologies',ordinary_registered=True)
before_seconds=time.perf_counter()-start;start=time.perf_counter()
after=prepare_d04_semantic_source(repo_root=SOURCE,company_id='lumen_technologies',ordinary_registered=True);after_seconds=time.perf_counter()-start
assert before['units']==after['units'] and before['documents']==after['documents']
proof=source_equivalence(current=after,original=before)
old_requests=source_requests(before);new_requests=source_requests(after)
assert [{k:v for k,v in r.items() if k not in ('source_id','request_id')} for r in old_requests]==[{k:v for k,v in r.items() if k not in ('source_id','request_id')} for r in new_requests]
summary={'code_root':str(ROOT),'code_state':'named uncommitted financial boundary helper','company_id':'lumen_technologies','current_period':after['prepared_annual_input']['table_input']['target_period'],'before_seconds':before_seconds,'after_seconds':after_seconds,'before_source_id':before['semantic_source_id'],'after_source_id':after['semantic_source_id'],'changed_fields':[k for k in after if before.get(k)!=after[k]],'documents_and_complete_units_equal':True,'request_count':len(new_requests),'substantive_request_bodies_equal':True,'equivalence':proof,'old_saved_answer_credit':'not assessed; no response replay or company result','new_calls':[0,0,0]}
(OUT/'d04-input-equivalence.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:summary[k] for k in ['before_seconds','after_seconds','current_period','changed_fields','request_count','substantive_request_bodies_equal']}))
