"""Build only the new pending proposal. Never rewrite an existing historical revision."""
import json,sys,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import requirement_profile_v1 as v1, requirement_profile_v8 as engine
from vnext.annual_adoption_policy import policy,V2,pending_decision
from vnext.canonical import content_hash,sha256_file
from vnext.requirements import load_requirement_snapshot
def read(path):return json.loads(path.read_text())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def proof(path):return {'sha256':sha256_file(path=path),'size':path.stat().st_size}
parent_dir=ROOT/'requirements'/engine.PARENT_ID;destination=ROOT/'requirements'/engine.REQUIREMENT_ID
destination.mkdir(exist_ok=True)
parent=load_requirement_snapshot(snapshot_dir=parent_dir);chosen=policy(policy_id=V2)
(destination/'CONTRACT.md').write_text('''# Issue #28 v7: pending candidate-specific annual adoption

This frozen proposal defines content checks for the exact saved native candidate
named by annual_candidate_adoption_v2. It does not approve a Rule, activate a
Requirement, issue a production grant, alter an original Run, or call a provider.
The new S-ANNUAL-ADOPTION Decision remains PENDING_EXTERNAL_APPROVAL.

Original B01 foundation and B10 issue_28_v6 execution, immutable inputs, their
complete native graph, source period/unit/subject/business scope, and the bound
independent content audit must all agree. Original OPEN statuses, B03, failed
responses and consumed grants remain unchanged. Historical repair-slot checks
describe the actual old execution; they are not a rule for future annual inputs.
No prior qualification credit or future unseen-source publication qualification
is transferred by this adoption. The 238 inherited coordinates preserve their
existing evidence tier and periods; two native projections retain all 327 rows.

The complete immutable package and exact plan precede external approval. Real
unedited repository-owner GitHub comments separately activate this Requirement
and authorize the plan's candidate, implementation, complete package, actual
root, exact predecessor and finite publish/rollback/restore/recover scope.
Production execution requires the reviewed implementation to survive the named
PR merge with identical implementation and test content. New SEC/provider/paid
calls are zero. Test permissions are restricted to explicitly isolated roots.

Content validation and publication permissions are different facts. No local
JSON, proposal flag, old model-execution approval, or adopted Result ID grants
production authority. A reserved interrupted switch may be completed or undone
only through its same native intent; consumption cannot mint a different edge.
The fixed rule and proposal files never change when external approval arrives.

The actual R3 already has these fiscal-year values. A later authorized switch is
same-year source/execution-version adoption, not a new-year discovery or 39-metric
completion. Subsequent normal-input permission/trigger work remains separate;
this one candidate review is not a permanent per-filing development-PR design.
''')
register=read(parent_dir/'decision_register.json');register.update(requirement_id=engine.REQUIREMENT_ID,issue_contract_revision='annual-candidate-adoption-v2')
register['pending_decisions'].append(pending_decision(chosen));save(destination/'decision_register.json',register)
profile=read(parent_dir/'invariant_profile.json');profile.update(requirement_id=engine.REQUIREMENT_ID,profile_semantic_version='8');save(destination/'invariant_profile.json',profile)
files={p:proof(parent_dir/p) for p in sorted(v1.PROFILE_SNAPSHOT_FILES)}
transfer=read(parent_dir/'transfer_manifest.json');transfer.update(requirement_id=engine.REQUIREMENT_ID,parent_requirement_id=parent['requirement_id'],parent_requirement_closure_hash=parent['requirement_closure_hash'],parent_snapshot_files=files,parent_snapshot_binding_hash=content_hash(value=files))
fragments=[]
for key,decision in sorted(parent['effective_decisions'].items()):
    if decision['status']!='APPROVED':continue
    for path,value in sorted(v1.choice_fragments(value=decision['choice']).items()):
        fragments.append({'decision_id':key,'disposition':'CARRY_FORWARD','parent_effective_record_hash':v1.decision_record_hash(decision=decision),
            'rationale':'Historical obligations remain exact; pending candidate adoption owns no execution credit.',
            'source_path':path,'source_value_hash':content_hash(value=value),'successor_decision_id':key,'successor_path':path,'transfer_mode':'EXACT_VALUE'})
transfer['fragments']=fragments;transfer['fragment_classification_counts']={'CARRY_FORWARD':len(fragments),'HISTORICAL_ONLY':0,'SUPERSEDED':0}
transfer['pending_decision_transfers']=[{'decision_id':k,'disposition':'CARRY_FORWARD','parent_record_hash':v1.decision_record_hash(decision=d),'qualification_credit':'NONE'} for k,d in parent['effective_decisions'].items() if d['status']!='APPROVED']
save(destination/'transfer_manifest.json',transfer)
baseline=read(parent_dir/'baseline_manifest.json');baseline.update(requirement_id=engine.REQUIREMENT_ID,requirement_generation=engine.PROFILE_REQUIREMENT_GENERATION,contract_revision='annual-candidate-adoption-v2')
baseline['created_at_utc']=datetime.now(timezone.utc).isoformat()
baseline['parent']={'requirement_id':parent['requirement_id'],'requirement_closure_hash':parent['requirement_closure_hash'],'hashes':parent['hashes'],
    'snapshot_files':files,'snapshot_git_tree':subprocess.check_output(['git','rev-parse','HEAD:requirements/'+engine.PARENT_ID],cwd=ROOT,text=True).strip(),'snapshot_binding_hash':content_hash(value=files)}
baseline['supersedes_requirement']={'requirement_id':parent['requirement_id'],'requirement_closure_hash':parent['requirement_closure_hash']}
baseline['snapshot_files']={p:proof(destination/p) for p in sorted(v1.PROFILE_BOUND_FILES)}
baseline['validator']={'path':'scripts/vnext/requirement_profile_v8.py','semantic_version':'8','sha256':sha256_file(path=Path(engine.__file__)),
    'dependencies':{str(p.relative_to(ROOT)):proof(p) for p in engine.DEPENDENCIES}}
paths=set(baseline['execution_authority']['files']) | {
    engine.POLICY_PATH,chosen['content_review']['path'],'scripts/vnext/annual_adoption_policy.py','scripts/vnext/annual_adoption.py',
    'scripts/vnext/annual_projection.py','scripts/vnext/annual_publication.py','scripts/vnext/annual_publication_authority.py',
    'scripts/vnext/requirement_profile_v8.py','tools/vnext_annual_publication.py'}
baseline['execution_authority']['files']={p:proof(ROOT/p) for p in sorted(paths)}
save(destination/'baseline_manifest.json',baseline)
loaded=load_requirement_snapshot(snapshot_dir=destination)
print(loaded['requirement_id'],loaded['requirement_closure_hash'],loaded['pending_decision_ids'])
