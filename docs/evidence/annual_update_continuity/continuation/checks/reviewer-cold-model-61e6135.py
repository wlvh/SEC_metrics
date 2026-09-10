from pathlib import Path
import sys,json,hashlib,subprocess,datetime
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');O=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');W=O/'continuation';sys.path[:0]=[str(R),str(R/'scripts')]
from vnext import publication as pub,annual_continuity as flow,annual_publication as annual,ai_adapter as ai,run_store,invocation_control as control
from vnext.canonical import strict_json_file,strict_json_loads,sha256_file

def read(p):return strict_json_file(path=p)
def proof(p):return {'path':str(p),'sha256':sha256_file(path=p),'size':p.stat().st_size}
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head=='61e6135770f2a3c1b6cd36c5c746986628885638'
result={'record_type':'INDEPENDENT_CONFIG_CONTINUATION_COLD_READ','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','reviewer_task':'/root/runtime_boundary_review','head_at_start':head,'source_semantics_scope':'Native cold read only; no new provider, SEC, Run, policy or allowance.','packages':[]}
roots=[('V1_REHEARSAL',Path('/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-publication-close/final-rehearsal-2')),('V2_CURRENT',R),('V3_OLD_S0',O/'live/stage/publication')]
for label,root in roots:
 print('START',label,flush=True)
 before=(root/'outputs/active_publication.json').read_bytes()
 view=pub.PublicationView.open(publication_root=root)
 values={}
 for metric in ('B01','B10'):
  native=view.native_result(company_id='marriott_international',metric_id=metric)
  values[metric]={'result':native['result'],'owner_publication_id':native['owner_publication_id'],'manifest_sha256':hashlib.sha256(native['manifest_raw']).hexdigest(),'records_sha256':hashlib.sha256(native['records_raw']).hexdigest(),'sources':native['sources']}
 assert (root/'outputs/active_publication.json').read_bytes()==before
 result['packages'].append({'label':label,'publication_id':view.publication_id,'manifest':proof(view.bundle_dir/'publication_manifest.json'),'values':values})
 print('PASS',label,view.publication_id,flush=True)
C=O/'live/stage/candidates/6867f54821e36e70159fe83e9ca8abb5d51828c9e151a5819fca048650cd53cc';plan=read(C/'plan.json');data=Path(plan['data_root'])
old_req=flow._requirement(data);new_req=flow._requirement(R)
old_policy=ai.configured_annual_transport_policy(requirement=old_req,repo_root=data);new_policy=ai.configured_annual_transport_policy(requirement=new_req,repo_root=R)
assert old_policy.model=='deepseek-v4-flash' and new_policy.model=='deepseek-flash'
assert run_store._run_transport_policy(requirement=old_req,repo_root=data)==old_policy
assert run_store._run_transport_policy(requirement=new_req,repo_root=R)==new_policy
view=control.prepare_historical_annual_invocation_view(repo_root=data,requirement_id=old_req['requirement_id']);assert view._check()[2]['model']==old_policy.model
m,records,_=run_store.load_run_for_status(run_dir=C/'b10',repo_root=data)
attempt=next(x for x in records if x['record_type']=='AI_EXTRACTION_ATTEMPT')
assert attempt['status']=='FAILED' and attempt['error_class']=='DEEPSEEK_MODEL_IDENTITY_MISMATCH' and attempt['model_requested']=='deepseek-v4-flash' and attempt['model_returned']=='deepseek-flash'
assert not [x for x in records if x['record_type']=='METRIC_RESULT']
prior=read(O/'independent-live-first-source-audit.json')
for relative,expected in prior['candidate_file_proofs'].items():assert proof(C/relative)==expected
closed=read(O/'live/budget/closed.json');assert closed['counts']['provider']==closed['counts']['paid']==1 and closed['counts']['sec_reserved']==0
result.update(old_closed_stage_counts=closed['counts'],old_failed_Run_model_identity_unchanged=True,current_policy_model=new_policy.model,old_record_policy_model=old_policy.model,head_at_end=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),working_status_at_end=subprocess.check_output(['git','status','--porcelain'],cwd=R,text=True),new_provider_paid_sec_calls=[0,0,0],status='PASS')
(W/'reviewer-cold-model-61e6135.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
print('PASS_OLD_RECORD_AND_CLOSED_STAGE',flush=True)
