"""Read review provenance and existing JPM evidence; never launch a review."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess,json,hashlib
out=Path(__file__).resolve().parent
endpoints={'reviews':'repos/wlvh/SEC_metrics/pulls/43/reviews?per_page=100','inline_review_comments':'repos/wlvh/SEC_metrics/pulls/43/comments?per_page=100','pr_comments':'repos/wlvh/SEC_metrics/issues/43/comments?per_page=100','issue_comments':'repos/wlvh/SEC_metrics/issues/28/comments?per_page=100'}
remote={}
for name,endpoint in endpoints.items():
    pages=json.loads(subprocess.check_output(['gh','api',endpoint,'--paginate','--slurp'],text=True))
    rows=[r for page in pages for r in page]
    remote[name]={'endpoint':endpoint,'total_records':len(rows),'records':[{'id':r['id'],'url':r.get('html_url'),'commit_id':r.get('commit_id'),'state':r.get('state'),'submitted_at':r.get('submitted_at'),'updated_at':r.get('updated_at'),'body_sha256':hashlib.sha256(r.get('body','').encode()).hexdigest()} for r in rows]}
base='6e5a85bf96d9086d51fbddeb0ab38f446d3fc19e';versions={}
for path in ['scripts/vnext/regulatory_statement_facts.py','scripts/vnext/r6_regulatory_semantics.py','tests/vnext/test_regulatory_statement_facts.py']:
    old=subprocess.check_output(['git','show',base+':'+path]);new=Path(path).read_bytes()
    versions[path]={'baseline_sha256':hashlib.sha256(old).hexdigest(),'current_sha256':hashlib.sha256(new).hexdigest(),'same_as_baseline':old==new}
fact_path=Path('docs/evidence/issue28_continuous/resume-2026-09-14/d03-source-fact-final.json')
fact=json.loads(fact_path.read_text())['source_fact'];alias=fact['subject_binding']['support']
rawpath=Path('evidence/request_attempts/4d/4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/jpm-20251231.htm');raw=rawpath.read_bytes()
assert 'sha256:'+hashlib.sha256(raw).hexdigest()==alias['raw_asset_id']
assert hashlib.sha256(raw[fact['raw_start_byte']:fact['raw_end_byte']]).hexdigest()==fact['raw_span_sha256']
assert hashlib.sha256(raw[alias['raw_start_byte']:alias['raw_end_byte']]).hexdigest()==alias['raw_span_sha256']
body={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'expected_review_baseline':base,'remote_inventory':remote,'module_versions':versions,'jpm_source':{'fact_material':str(fact_path),'raw_source':str(rawpath),'original_document_sha256_verified':True,'statement_span_sha256_verified':True,'alias_span_sha256_verified':True,'statement':fact['statement_text'],'assertion':'AFFIRMATIVE_AGGREGATE_CURRENT_INVOLVEMENT','case_identity':None,'case_count':None,'guilt_inferred':False,'sample_role':'ALREADY_SEEN_REGRESSION'},'effective_6e5_report_found':False,'code_review_performed':False,'old_codex_task_started_or_retried':False,'provider_paid_sec_calls':[0,0,0]}
(out/'readback.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print({k:v['total_records'] for k,v in remote.items()})
