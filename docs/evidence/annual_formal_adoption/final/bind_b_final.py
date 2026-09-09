"""Cross-check the final code, native execution logs, complete package and inert plan."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.annual_adoption import git,_tree_files,check_id
from vnext.annual_adoption_policy import policy,V2
from vnext.canonical import content_hash
from vnext import annual_publication as annual, annual_publication_authority as auth
work=BASE/sys.argv[1]
def read(path):return json.loads(path.read_text())
def proof(path):
    raw=path.read_bytes();return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
prepared=read(work/'prepare.json');directory=work/'publication/outputs/publications'/prepared['publication_id']
manifest=read(directory/'publication_manifest.json');meta=read(directory/annual.META)
context=read(directory/annual.SNAPSHOT/'context.json');adoption=read(directory/annual.SNAPSHOT/'adoption.json')
batch=read(directory/annual.BATCH);plan=read(work/'pending-production-plan.json');templates=read(work/'approval-templates.json')
head=meta['implementation_head'];code_tree=content_hash(value=git('ls-tree','-r',head,'scripts','tools','config','catalog','requirements').decode())
test_tree=content_hash(value=git('ls-tree','-r',head,'tests').decode())
assert code_tree==meta['implementation_tree']==plan['code']['implementation_tree']
assert plan['code']==auth._code(head) and plan['code']['test_tree']==test_tree
assert _tree_files(root=directory/'internal/annual_runtime')==meta['runtime_files']==annual._implementation_files(head,V2)
for entry in manifest['files']:
    assert proof(directory/entry['path'])=={k:entry[k] for k in ['sha256','size']}
assert context['policy']==meta['policy']==policy(policy_id=V2)
check_id(adoption,'adoption_receipt_id');check_id(plan,'plan_id')
assert adoption['snapshot_id']==content_hash(value=context)==plan['binding']['source_snapshot_id']
assert adoption['selected_results'] and content_hash(value=adoption['selected_results'])==plan['binding']['selected_results_id']
assert manifest['annual_adoption_receipt_id']==adoption['adoption_receipt_id']==plan['binding']['adoption_receipt_id']
assert manifest['publication_id']==plan['binding']['publication_id']
assert proof(directory/'publication_manifest.json')['sha256']==plan['binding']['manifest_sha256']
assert content_hash(value=context['candidate_files'])==plan['binding']['candidate_file_set_id']
assert _tree_files(root=Path(context['origin']['candidate_directory']))==context['candidate_files']
assert templates['status']=='TEMPLATES_ONLY_NO_AUTHORITY' and templates['plan_id']==plan['plan_id']
assert templates['requirement_transition']==auth.expected_activation_approval(plan)
assert templates['publication_decision']==auth.expected_owner_approval(plan)
assert (batch['selected_result_count'],batch['inherited_result_count'],batch['public_row_count'])==(2,238,327)
executions={name:read(work/(name+'-execution.json')) for name in ['prepare','read','integration','deep-negatives']}
for name,e in executions.items():
    assert e['exit_status']==0 and e['protection_equal']
    assert e['code']['head']==head and e['code']['implementation_tree']==code_tree and e['code']['test_tree']==test_tree
    assert e['code']['git_tree_oid']==git('rev-parse',head+'^{tree}').decode().strip()
    assert proof(Path(e['log']['path']))=={k:e['log'][k] for k in ['sha256','size']}
    assert proof(Path(e['harness']['path']))=={k:e['harness'][k] for k in ['sha256','size']}
    for path,expected in e['code']['test_files'].items():
        raw=git('show',head+':'+path)
        assert expected=={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
    assert e['new_business_provider_paid_sec_calls']==[0,0,0]
    if name!='prepare':assert e['github_reads']==[]
assert len(executions['prepare']['github_reads'])==1
integration=(work/'integration.log').read_text();negative=(work/'deep-negatives.log').read_text()
assert 'Ran 2 tests' in integration and '\nOK\n' in integration and 'skipped' not in integration
assert 'Ran 1 test' in negative and '\nOK\n' in negative and 'skipped' not in negative
assert all(c['status']=='PASS' for c in read(work/'integration.json')['checks'])
assert len(read(work/'deep-negatives.json')['checks'])==8
before=read(work/'prepare-protection-before.json')
assert all(proof(ROOT/path)==p for path,p in before['official_files'].items())
assert _tree_files(root=ROOT/'outputs/publications')==before['official_publications']
readback=read(work/'read.json')
assert len(readback['verified_source_locations'])==2
for location in readback['verified_source_locations']:
    assert proof(directory/location['bundle_relative_path'])=={k:location[k] for k in ['sha256','size']}
assert plan['approval_status']=='NOT_ISSUED' and plan['target_root']==str(ROOT)
assert read(ROOT/'outputs/active_publication.json')==plan['predecessor_pointer']
assert not (ROOT/'outputs/annual_publication_authorizations').exists()
prior_log=(BASE/'attempt-01/integration.log').read_text()
prior_execution=read(BASE/'attempt-01/integration-execution.json')
assert prior_execution['exit_status']==1 and prior_execution['protection_equal']
assert prior_execution['code']['implementation_tree']==code_tree
assert 'FAILED (errors=3)' in prior_log
reused_methods=[
 'test_exact_approved_merge_relation_uses_real_git_objects_without_open_pr_rule',
 'test_pre_and_post_pointer_recovery_is_bound_to_the_same_action',
 'test_rebound_plan_and_approval_errors_never_write',
 'test_reserved_action_without_native_intent_preserves_old_and_does_not_retry',
 'test_soft_failure_retains_old_complete_version',
 'test_v1_and_actual_r3_remain_readable_and_v1_cannot_be_adopted']
for method in reused_methods:
    assert any(line.startswith(method+' (') and line.endswith(' ... ok') for line in prior_log.splitlines())
fix=read(BASE/'test-fix-diff.json')
assert fix['new_head']==head and fix['old_head']==prior_execution['code']['head']
assert not git('diff',fix['old_head'],head,'--','scripts','tools','config','catalog','requirements').strip()
assert annual._implementation_files(fix['old_head'],V2)==annual._implementation_files(head,V2)
repeat=read(work/'repeat-prepare.json')
assert repeat['head']==head and repeat['status']=='REPEATED_V2_PREPARE_NO_WRITES_NO_GITHUB_NO_BUSINESS_CALLS'
assert repeat['result']['publication_id']==manifest['publication_id'] and repeat['github_reads']==0
assert repeat['harness_sha256']==proof(BASE/'repeat_prepare_check.py')['sha256']
result={'status':'VERIFIED_IMPLEMENTATION_EXECUTION_PACKAGE_AND_PENDING_PLAN',
    'implementation':executions['prepare']['code'],'executions':executions,
    'package':{'directory':str(directory),'publication_id':manifest['publication_id'],
        'manifest_file':proof(directory/'publication_manifest.json'),'metadata_path':annual.META,
        'metadata_file':proof(directory/annual.META),'adoption_receipt_object_id':adoption['adoption_receipt_id'],
        'adoption_receipt_file':proof(directory/annual.SNAPSHOT/'adoption.json'),'file_count':len(manifest['files']),
        'selected':2,'inherited':238,'public_rows':327},
    'pending_plan':{'path':str(work/'pending-production-plan.json'),'object_id':plan['plan_id'],
        'file':proof(work/'pending-production-plan.json'),'binding':plan['binding'],'target_root':plan['target_root'],
        'predecessor':plan['predecessor'],'operations':plan['operations']},
    'repeat_prepare':repeat,'source_locations':readback['verified_source_locations'],'selected_results':adoption['selected_results'],
    'native_run_ids':adoption['native_run_ids'],'native_requirement_hashes':adoption['native_requirement_hashes'],
    'original_runs':adoption['original_run_status'],'unselected_preserved':adoption['preserved_unselected_results'],
    'ci':read(BASE/'ci-test-fix.json'),'code_review':read(BASE/'core-review-implementation.json'),
    'test_fix':fix,'reused_passed_components':{'methods':reused_methods,'head':prior_execution['code']['head'],
        'package_id':read(BASE/'attempt-01/prepare.json')['publication_id'],'implementation_tree':code_tree,
        'original_suite_status':'FAILED_3_POLICY_TEST_CONSTRUCTION_ERRORS','log':proof(BASE/'attempt-01/integration.log')},
    'content_review':read(BASE/'content-review.json'),
    'safety_incident':read(BASE/'safety/root-write-incident.json'),
    'current_state':{'new_pr':40,'draft':True,'production_requirement_activated':False,'production_grant_issued':False,
        'actual_r3_switched':False,'new_business_calls':[0,0,0],'pr38_historical_calls':[2,2,0]},
    'identity_definitions':{'implementation_tree':'content_hash of exact git ls-tree text over scripts/tools/config/catalog/requirements',
        'test_tree':'content_hash of exact git ls-tree text over tests','object_id':'canonical content_hash excluding own ID',
        'file_sha256':'SHA-256 of every file byte including whitespace and embedded IDs'},
    'verifier':{'path':str(Path(__file__)),**proof(Path(__file__))}}
save_path=work/'run-binding.json';save_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'publication_id':manifest['publication_id'],'plan_id':plan['plan_id']}))
