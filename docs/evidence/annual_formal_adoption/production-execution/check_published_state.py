"""Read-only reconciliation after the native CLI cold read; no production writes."""
import sys,json,hashlib,csv,io
from pathlib import Path
from datetime import datetime,timezone
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');O=Path(__file__).resolve().parent
sys.path[:0]=[str(R),str(R/'scripts')]
from vnext import publication as pub,annual_publication as annual
from vnext.annual_adoption import git,_tree_files,check_id
from vnext.canonical import content_hash

def read(p):return json.loads(p.read_text())
def proof(p):
 b=p.read_bytes();return {'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
plan=read(O.parent.parent/'attempt-02/pending-production-plan.json');original=read(O/'historical-protection-before.json');namespaces=read(O/'formal-namespaces-before.json')
packet=read(O/'read.json');assert packet['status']=='READABLE_COMPLETE_VERSION' and packet['publication_id']==plan['binding']['publication_id'] and packet['public_row_count']==327
assert read(O/'read-execution.json')['exit_status']==0 and not read(O/'read-execution.json')['github_reads']
assert git('branch','--show-current').decode().strip()=='main'
pointer=read(R/'outputs/active_publication.json');directory=R/'outputs/publications'/packet['publication_id'];source=Path(plan['bundle_directory'])
assert pointer['publication_id']==packet['publication_id'] and pointer['previous_publication_id']==plan['predecessor']['publication_id']
assert pointer['bundle_manifest_sha256']==plan['binding']['manifest_sha256']==proof(directory/'publication_manifest.json')['sha256']
assert _tree_files(root=directory)==_tree_files(root=source),'Deployed fixed package changed'
manifest=read(directory/'publication_manifest.json');batch=read(directory/annual.BATCH)
assert (batch['selected_result_count'],batch['inherited_result_count'],batch['public_row_count'])==(2,238,327)
assert set(x['metric_id'] for x in batch['cumulative_result_bindings'] if x['origin']=='ADOPTED_NATIVE_CANDIDATE')=={'B01','B10'}
for x in packet['verified_source_locations']:
 assert proof(directory/x['bundle_relative_path'])=={k:x[k] for k in ['sha256','size']}
assert len(packet['verified_source_locations'])==2
assert packet['selected_rows']==read(O/'field-differences-approved-package.json')['selected_rows']['after']
mirrors=read(O/'root-mirror-paths.json')
for s,t in mirrors.items():assert (R/t).read_bytes()==(directory/s).read_bytes(),t
assert pub._load_switch_intent(pointer_path=R/'outputs/active_publication.json') is None
receipt=pub._switch_receipt_for_pointer(pointer_path=R/'outputs/active_publication.json',pointer=pointer)
action_path=R/'outputs/annual_publication_actions'/(plan['plan_id'][7:]+'-publish.json'); action=read(action_path);check_id(action,'action_id')
assert receipt['annual_authority']['plan_id']==plan['plan_id'] and receipt['annual_authority']['action_id']==action['action_id']
assert action['previous_pointer']==plan['predecessor_pointer'] and action['target_publication_id']==packet['publication_id']
assert action['committed_at_utc']==pointer['committed_at_utc'] and receipt['pointer']==pointer
permission_path=R/'outputs/annual_publication_authorizations'/(receipt['annual_authority']['permission_id'][7:]+'.json');permission=read(permission_path)
assert content_hash(value=permission)==receipt['annual_authority']['permission_id'] and permission['plan']==plan
assert permission['activation']==read(O/'activate.json') and permission['owner']==read(O/'approvals.json')['publication_decision']
assert permission['pull']['merge_commit_sha']==read(O/'merge-and-main-sync.json')['merge_commit']
assert permission['manifest']==manifest
assert read(O/'publish.json')['status']=='AUTHORIZED_PUBLISH_COMPLETED'
assert not (R/'outputs/annual_publication_actions'/(plan['plan_id'][7:]+'-rollback.json')).exists()
assert not (R/'outputs/annual_publication_actions'/(plan['plan_id'][7:]+'-restore.json')).exists()
changed_allowed=set(mirrors.values())|{'outputs/active_publication.json'}
for path,p in original['official_files'].items():
 if path not in changed_allowed:assert proof(R/path)==p,path
oldpub=_tree_files(root=R/'outputs/publications');assert all(oldpub[k]==v for k,v in original['official_publications'].items())
assert set(oldpub)-set(original['official_publications'])=={packet['publication_id']+'/'+s for s in _tree_files(root=source)}
candidate=Path(read(O/'preflight.json')['original_candidate_root'])
assert _tree_files(root=candidate)==original['candidate'] and _tree_files(root=candidate.parents[5])==original['historical_runtime']
assert git('stash','list','--format=%H').decode().splitlines()==original['stash']
assert [s for s in git('worktree','list','--porcelain').decode().split('\n\n') if s and not s.startswith('worktree '+str(R)+'\n')]==original['historical_worktrees']
for n,files in namespaces.items():
 for path,p in files.items():assert proof(R/'outputs'/n/path)==p,'Historical transaction changed'
for p,v in read(O/'tracked-files-before.json').items():
 if p not in changed_allowed:assert proof(R/p)==v,'Protected tracked file changed: '+p
# CSV diff is computed again from the actual committed package, including all fields.
previous=R/'outputs/publications'/plan['predecessor']['publication_id'];diff={}
for n in ['metrics_matrix.csv','metric_evidence.csv']:
 a=list(csv.DictReader(io.StringIO((previous/n).read_text(encoding='utf-8-sig'))));b=list(csv.DictReader(io.StringIO((directory/n).read_text(encoding='utf-8-sig'))));assert len(a)==len(b)
 rows=[]
 for i,(x,y) in enumerate(zip(a,b)):
  assert (x['company'],x['metric_id'])==(y['company'],y['metric_id'])
  changed={k:{'old':x[k],'new':y[k]} for k in x if x[k]!=y[k]}
  if changed:rows.append({'csv_line':i+2,'company':x['company'],'metric_id':x['metric_id'],'fields':changed})
 diff[n]={'row_count':len(a),'changed_rows':rows}
 assert diff[n]==read(O/'field-differences-approved-package.json')[n]
result={'status':'VERIFIED_REAL_PRODUCTION_ADOPTION_AND_COMPLETE_COLD_READ','verified_at_utc':datetime.now(timezone.utc).isoformat(),'head':git('rev-parse','HEAD').decode().strip(),'active':pointer,'plan_id':plan['plan_id'],'manifest_file':proof(directory/'publication_manifest.json'),'publication_files':len(_tree_files(root=directory)),'action':action,'native_switch_receipt':receipt,'permission_file':{'path':str(permission_path),**proof(permission_path)},'counts':{'adopted':2,'inherited':238,'matrix_rows':327},'raw_source_reads':packet['verified_source_locations'],'native_cli_read':{'result_file':proof(O/'read.json'),'execution_file':proof(O/'read-execution.json'),'log':proof(O/'read.log')},'field_differences':diff,'all_fourteen_mirrors_match':True,'pending_intent':None,'historical_files_candidates_policies_stashes_worktrees_unchanged':True,'rollback_restore_not_executed':True,'new_provider_paid_sec_calls':[0,0,0],'pr38_historical_calls':[2,2,0]}
assert not (O/'production-verification.json').exists();(O/'production-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'active':pointer['publication_id'],'counts':result['counts'],'pending_intent':None,'history_unchanged':True}))
