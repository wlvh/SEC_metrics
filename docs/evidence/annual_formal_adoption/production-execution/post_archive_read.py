"""Read the same fixed plan and actual active after the archive commit; never plan again."""
import sys,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');O=Path(__file__).resolve().parent
sys.path[:0]=[str(R),str(R/'scripts')]
from vnext import annual_publication_authority as auth,annual_publication as annual,publication as pub
from vnext.annual_adoption import git,_tree_files
from vnext.canonical import content_hash
plan=json.loads((R/'docs/evidence/annual_formal_adoption/final/pending-production-plan.json').read_text());before=json.loads((O/'production-verification.json').read_text());M=json.loads((O/'merge-and-main-sync.json').read_text())['merge_commit']
head=git('rev-parse','HEAD').decode().strip()
assert git('branch','--show-current').decode().strip()=='main'
assert git('rev-list','--left-right','--count','main...origin/main').decode().split()==['0','0']
assert not git('status','--porcelain=v1','--untracked-files=all').strip()
assert git('merge-base',M,head).decode().strip()==M
assert git('show','-s','--format=%P',M).decode().split()[1]=='36a91de058ac2fe6aee660a090f2b14d8527deb7'
root,manifest,requirement=auth.validate_plan(plan)
assert root==R and manifest['publication_id']==before['active']['publication_id']
assert not git('diff',M,head,'--','scripts','tools','config','catalog','requirements','tests').strip()
result=annual.read_version(publication_root=R)
assert result['status']=='READABLE_COMPLETE_VERSION' and result['publication_id']==plan['binding']['publication_id'] and result['public_row_count']==327
assert json.loads((R/'outputs/active_publication.json').read_text())==before['active']
assert pub._load_switch_intent(pointer_path=R/'outputs/active_publication.json') is None
assert result['selected_rows']==json.loads((O/'read.json').read_text())['selected_rows']
assert result['verified_source_locations']==json.loads((O/'read.json').read_text())['verified_source_locations']
assert not git('status','--porcelain=v1','--untracked-files=all').strip()
for ref in ['task/annual-candidate-formal-adoption','origin/task/annual-candidate-formal-adoption']:
 assert git('rev-parse',ref).decode().strip()=='36a91de058ac2fe6aee660a090f2b14d8527deb7'
record={'status':'PASSED_SAME_PLAN_AND_ACTUAL_PUBLICATION_AFTER_ARCHIVE','verified_at_utc':datetime.now(timezone.utc).isoformat(),'head':head,'merge_commit':M,'branch':'main','upstream':'origin/main','ahead_behind':[0,0],'clean_before_and_after':True,'plan_id':plan['plan_id'],'new_plan_generated':False,'implementation_tree':content_hash(value=git('ls-tree','-r',head,'scripts','tools','config','catalog','requirements').decode()),'test_tree':content_hash(value=git('ls-tree','-r',head,'tests').decode()),'publication_read':result,'pending_intent':None,'new_provider_paid_sec_calls':[0,0,0],'new_github_reads':0,'archive_bytes_unchanged_by_read':True}
assert not (O/'post-archive-read.json').exists();(O/'post-archive-read.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':record['status'],'head':head,'actual_active':result['publication_id'],'clean_main':True}))
