"""Cross-check actual run records, Git objects and immutable bundle metadata."""
import hashlib, json, subprocess, sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]
from vnext.canonical import content_hash, strict_json_loads
from vnext.annual_adoption import read, git, check_id, _tree_files
from vnext import annual_publication as annual
def proof(path):
    b=path.read_bytes();return {'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
prepared=read(BASE,'prepare.json')
assert prepared['status']=='PREPARED_ISOLATED_COMPLETE_PUBLICATION'
executions={n:read(BASE,n+'-execution.json') for n in ['prepare','validate-switch-read','integration']}
first=executions['prepare'];root=Path(first['publication_root'])
bundle=root/'outputs/publications'/prepared['publication_id']
manifest=read(bundle,'publication_manifest.json');meta=read(bundle,annual.META)
context=read(bundle,annual.SNAPSHOT+'/context.json');adoption=read(bundle,annual.SNAPSHOT+'/adoption.json')
batch=read(bundle,annual.BATCH)
head=meta['implementation_head']
assert first['code']['git_tree_oid']==git('rev-parse',head+'^{tree}').decode().strip()
for path,expected in first['code']['tests'].items():
    raw=git('show',head+':'+path)
    assert expected=={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}==proof(REPO/path)
impl=content_hash(value=git('ls-tree','-r',head,'scripts','tools','config','catalog','requirements').decode())
assert impl==meta['implementation_tree']==first['code']['implementation_tree']
assert _tree_files(root=bundle/'internal/annual_runtime')==meta['runtime_files']==annual._implementation_files(head)
for name,e in executions.items():
    assert e['exit_status']==0 and e['protection_equal']
    assert e['code']==first['code'] and e['publication_root']==str(root)
    assert proof(Path(e['log']['path']))=={k:e['log'][k] for k in ['sha256','size']}
    assert proof(Path(e['harness']['path']))=={k:e['harness'][k] for k in ['sha256','size']}
    assert e['new_provider_paid_sec_calls']==[0,0,0]
    if name!='prepare':assert e['github_reads']==[]
assert len(first['github_reads'])==1
assert first['code']['head']==head
assert context['candidate_files']==_tree_files(root=Path(context['origin']['candidate_directory']))
assert context['policy']==meta['policy']==annual.policy()
check_id(adoption,'adoption_receipt_id')
assert adoption['snapshot_id']==content_hash(value=context)
assert manifest['annual_adoption_receipt_id']==adoption['adoption_receipt_id']
assert adoption['policy_hash']==content_hash(value=context['policy'])
assert batch['selected_result_count']==2 and batch['inherited_result_count']==238 and batch['public_row_count']==327
assert prepared['publication_id']==manifest['publication_id']==read(BASE,'switch-read.json')['publication_id']
assert len(read(BASE,'switch-read.json')['verified_source_locations'])==2
checks=read(BASE,'integration-checks.json')
assert checks['actual_r3_and_original_candidate_unchanged'] and all(r['status']=='PASS' for r in checks['checks'])
integration_log=(BASE/'integration.log').read_text()
assert 'Ran 2 tests' in integration_log and '\nOK\n' in integration_log and 'skipped' not in integration_log
before=read(BASE,'protection-before.json')
assert all(proof(REPO/name)==value for name,value in before['official_files'].items())
assert _tree_files(root=REPO/'outputs/publications')==before['official_publications']
assert git('stash','list','--format=%H').decode().splitlines()==before['stash']
ci=read(BASE,'ci-implementation.json')
assert ci['actual_module_result']['return_code']==0 and 'Ran 4 tests' in ci['actual_module_result']['stderr_tail']
ci_log=(BASE/'ci-implementation.log').read_text()
suite=next(strict_json_loads(text=line[line.index('{'):]) for line in ci_log.splitlines() if '"evidence_tier": "FAST_LOCAL_ONLY"' in line)
assert ci['suite_status']==suite['status']=='PASSED'
assert ci['actual_module_result']==next(r for r in suite['tests'] if r['test']=='tests.vnext.test_annual_publication')
assert 'refs/remotes/pull/39/merge' in ci_log and ('Merge '+head) in ci_log
import re
merge_line=next(line for line in ci_log.splitlines() if ('Merge '+head) in line)
ci={**ci,'checkout_ref':'refs/pull/39/merge','merge_message_log_line':merge_line,
    'checkout_commit':next(re.search(r'[0-9a-f]{40}',line).group() for line in ci_log.splitlines()
        if re.search(r'Z [0-9a-f]{40}$',line)),
    'log_file':proof(BASE/'ci-implementation.log')}
result={'status':'VERIFIED_CODE_EXECUTION_PACKAGE_BINDING','code':first['code'],
    'executions':executions,'original_archive':read(BASE,'zip-verification.json'),
    'input':{'context_object_id':content_hash(value=context),'candidate_file_set_id':content_hash(value=context['candidate_files']),
        'candidate_file_count':len(context['candidate_files']),'candidate_root':context['origin']['candidate_directory'],
        'original_plan_id':context['origin']['plan']['plan_id'],'native_run_ids':adoption['native_run_ids'],
        'execution_id':adoption['execution_id'],'policy_id':adoption['policy_id'],'policy_hash':adoption['policy_hash'],
        'selected_results':adoption['selected_results']},
    'package':{'directory':str(bundle),'publication_id':manifest['publication_id'],
        'manifest_file':proof(bundle/'publication_manifest.json'),'implementation_metadata_path':annual.META,
        'implementation_metadata_file':proof(bundle/annual.META),'adoption_receipt_object_id':adoption['adoption_receipt_id'],
        'adoption_receipt_file':proof(bundle/annual.SNAPSHOT/'adoption.json'),
        'complete_version_file':proof(bundle/annual.BATCH),'selected_count':2,'inherited_count':238,'public_row_count':327},
    'ci':ci,'integration_checks':checks,
    'identity_definitions':{'object_id':'canonical content_hash excluding the object own id field',
        'file_sha256':'SHA-256 of complete file bytes including whitespace and id',
        'git_tree_oid':'Git tree object identifier, not implementation_tree'},
    'business_calls':[0,0,0],'historical_pr38_calls':[2,2,0],
    'network_scope':'Two real GitHub comment reads: first external logging failure and successful fresh prepare. Integration and cold reads deny all network. GitHub CI/Issue/PR operations are separate from business calls.',
    'historical_failure':'harness-attempt-1/failure-explanation.json',
    'verifier':{'path':str(Path(__file__)),**proof(Path(__file__))}}
(BASE/'run-binding.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'status':result['status'],'head':head,'publication_id':manifest['publication_id']}))
