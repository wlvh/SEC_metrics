import sys,json,hashlib,csv,io
from pathlib import Path
from datetime import datetime,timezone
R=Path('/Users/lyuhongwang/Developer/SEC_metrics'); O=Path(__file__).resolve().parent
sys.path[:0]=[str(R),str(R/'scripts')]
from vnext import annual_publication as annual,annual_publication_authority as auth,publication as pub
from vnext.annual_adoption import git,_tree_files
from vnext.canonical import content_hash

def read(p):return json.loads(p.read_text())
def proof(p):
 b=p.read_bytes();return {'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
def save(n,v):
 data=json.dumps(v,ensure_ascii=False,indent=2)+'\n'; p=O/n
 if p.exists():assert json.loads(p.read_text())==v, 'Existing evidence differs: '+n
 else:p.write_text(data)
started=datetime.now(timezone.utc).isoformat()
review=R/'docs/evidence/annual_formal_adoption/final'; execution=O.parent.parent/'attempt-02'
for n in ['pending-production-plan.json','PENDING_EXECUTION_PLAN.md','approval-templates.json']:
 assert (review/n).read_bytes()==(execution/n).read_bytes(),n
plan=read(execution/'pending-production-plan.json'); templates=read(review/'approval-templates.json')
assert plan['plan_id']=='sha256:6b6c9d2a552fe39392ecf1c72afb0b9b6fe36a61b1a1fd406106b115cc7f0339'
assert templates['requirement_transition']==auth.expected_activation_approval(plan) and templates['publication_decision']==auth.expected_owner_approval(plan)
root,manifest,req=auth.validate_plan(plan)
assert root==R and read(R/'outputs/active_publication.json')==plan['predecessor_pointer']
assert manifest['publication_id']=='publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59'
assert proof(Path(plan['bundle_directory'])/'publication_manifest.json')['sha256']=='ce8b2c3fe7ac9b94ed721287c23948503a87b59e3b471bd285cc569a2d2336ec'
view=pub.PublicationView.open(publication_root=R)
assert view.publication_id==plan['predecessor']['publication_id']
assert proof(view.bundle_dir/'publication_manifest.json')['sha256']==plan['predecessor']['manifest_sha256']
assert pub._load_switch_intent(pointer_path=R/'outputs/active_publication.json') is None
original=read(R/'docs/evidence/annual_publication/close/protection-before.json')
candidate=Path(read(R/'docs/evidence/annual_publication/close/run-binding.json')['input']['candidate_root'])
protected={'official_files':{p:proof(R/p) for p in original['official_files']},'official_publications':_tree_files(root=R/'outputs/publications'),'candidate':_tree_files(root=candidate),'historical_runtime':_tree_files(root=candidate.parents[5]),'stash':git('stash','list','--format=%H').decode().splitlines(),'historical_worktrees':[s for s in git('worktree','list','--porcelain').decode().split('\n\n') if s and not s.startswith('worktree '+str(R)+'\n')]}
assert protected==original
save('historical-protection-before.json',protected)
mirrors=pub.ROOT_MIRROR_RELATIVE_PATHS
expected=['README_RUN.md','REPORT_十公司财务指标.md']+['outputs/'+n for n in ['coverage_matrix.csv','golden_results.csv','legacy_invariant_migration_receipt.json','metric_evidence.csv','metrics_matrix.csv','projection_manifest.json','publication_validation_receipt.json','repair_validation_results.csv','scalability_audit.csv','semantic_audit_receipt.json','stratified_audit.csv','validation_run_manifest.json']]
assert set(mirrors.values())==set(expected) and len(mirrors)==14
for a,b in mirrors.items():assert (R/b).read_bytes()==view.read_bytes(relative_path=a)
save('root-mirror-paths.json',mirrors)
tracked=git('ls-files','-z').decode().split('\0');save('tracked-files-before.json',{p:proof(R/p) for p in tracked if p and (R/p).is_file()})
save('formal-namespaces-before.json',{n:_tree_files(root=R/'outputs'/n) if (R/'outputs'/n).exists() and any(p.is_file() for p in (R/'outputs'/n).rglob('*')) else {} for n in ['annual_publication_authorizations','annual_publication_actions','publication_switch_intents','publication_switch_receipts']})
for n in ['annual_publication_authorizations','annual_publication_actions']:
 assert not (R/'outputs'/n).exists(), 'Existing execution requires state inspection: '+n
assert not (R/'outputs/publications'/manifest['publication_id']).exists()
bundle=Path(plan['bundle_directory']);diffs={}
for name in ['metrics_matrix.csv','metric_evidence.csv']:
 old=list(csv.DictReader(io.StringIO(view.read_bytes(relative_path=name).decode('utf-8-sig')))); new=list(csv.DictReader(io.StringIO((bundle/name).read_text(encoding='utf-8-sig'))))
 assert len(old)==len(new)
 changes=[]
 for i,(a,b) in enumerate(zip(old,new)):
  assert (a['company'],a['metric_id'])==(b['company'],b['metric_id'])
  delta={k:{'old':a[k],'new':b[k]} for k in a if a[k]!=b[k]}
  if delta:
   assert a['metric_id'] in ['B01','B10'] and a['cik']=='1048286'
   changes.append({'csv_line':i+2,'company':a['company'],'metric_id':a['metric_id'],'fields':delta})
 diffs[name]={'row_count':len(old),'changed_rows':changes}
 if name=='metrics_matrix.csv':
  assert len(old)==327
  b10old=next(x for x in old if x['cik']=='1048286' and x['metric_id']=='B10');b10new=next(x for x in new if x['cik']=='1048286' and x['metric_id']=='B10')
  assert b10old['filed_date']=='2026-02-10' and b10new['filed_date']==''
  assert next(x for x in new if x['cik']=='1048286' and x['metric_id']=='B01')['filed_date']=='2026-02-10'
  diffs['selected_rows']={'before':[x for x in old if x['cik']=='1048286' and x['metric_id'] in ['B01','B10']],'after':[x for x in new if x['cik']=='1048286' and x['metric_id'] in ['B01','B10']]}
save('field-differences-approved-package.json',diffs)
save('preflight.json',{'status':'PASSED_FIXED_PLAN_COMPLETE_PACKAGE_AND_R3_PREDECESSOR','started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'head':git('rev-parse','HEAD').decode().strip(),'plan_id':plan['plan_id'],'plan_file':proof(execution/'pending-production-plan.json'),'template_file':proof(review/'approval-templates.json'),'publication_id':manifest['publication_id'],'manifest_file':proof(bundle/'publication_manifest.json'),'original_candidate_root':str(candidate),'protection_matches_original':True,'root_mirrors':mirrors,'pending_intent':None,'new_provider_paid_sec_calls':[0,0,0]})
print('PASS fixed plan, full package, original R3, history, 14 mirrors and field differences')
