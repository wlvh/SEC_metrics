"""Evidence harness; invoke under sandbox-exec, with all source/official roots read-only."""
import hashlib,json,os,runpy,socket,sys,traceback,unittest
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.annual_adoption import read,git,_tree_files
from vnext.canonical import content_hash
from vnext import annual_candidate
from vnext.annual_adoption_policy import V2
mode=sys.argv[1];attempt=sys.argv[2];work=BASE/attempt;work.mkdir(exist_ok=True)
candidate=Path(read(ROOT,'docs/evidence/annual_publication/close/run-binding.json')['input']['candidate_root'])
publication_root=work/'publication';output=work/(mode+'.json');log=work/(mode+'.log')
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')
def proof(path):
    raw=path.read_bytes();return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
def now():return datetime.now(timezone.utc).isoformat()
def protected():
    original=read(ROOT,'docs/evidence/annual_publication/close/protection-before.json')
    return {'official_files':{p:proof(ROOT/p) for p in original['official_files']},
        'official_publications':_tree_files(root=ROOT/'outputs/publications'),
        'candidate':_tree_files(root=candidate),
        'historical_runtime':_tree_files(root=candidate.parents[5]),
        'stash':git('stash','list','--format=%H').decode().splitlines(),
        'historical_worktrees':[s for s in git('worktree','list','--porcelain').decode().split('\n\n') if s and not s.startswith('worktree '+str(ROOT)+'\n')]}
for key in list(os.environ):
    if key.endswith('_API_KEY'):os.environ.pop(key)
head=git('rev-parse','HEAD').decode().strip()
assert not git('status','--porcelain','--untracked-files=all').strip()
before=protected();save(work/(mode+'-protection-before.json'),before)
identity={'head':head,'git_tree_oid':git('rev-parse',head+'^{tree}').decode().strip(),
    'implementation_tree':content_hash(value=git('ls-tree','-r',head,'scripts','tools','config','catalog','requirements').decode()),
    'test_tree':content_hash(value=git('ls-tree','-r',head,'tests').decode()),
    'test_files':{p:proof(ROOT/p) for p in ['tests/vnext/test_annual_formal_rehearsal.py','tests/vnext/test_annual_publication_authority.py','tools/run_fast_tests.py']}}
github=[];real_github=annual_candidate._github
def traced(path):
    assert mode=='prepare', 'Real GitHub reads forbidden in integration and cold-read phases'
    value=real_github(path)
    github.append({'path':path,'comment_id':value.get('id'),'url':value.get('html_url'),
        'value_content_id':content_hash(value=value)})
    return value
annual_candidate._github=traced
def deny(*args,**kwargs):raise AssertionError('BUSINESS_SOCKET_FORBIDDEN')
socket.socket.connect=deny
started=now();code=1;command=[]
try:
    if mode=='prepare':
        assert not publication_root.exists()
        command=['tools/vnext_annual_publication.py','prepare','--policy-id',V2,'--candidate-dir',str(candidate),
            '--publication-root',str(publication_root),'--output-json',str(output)]
        sys.argv=command
        try:runpy.run_path(str(ROOT/command[0]),run_name='__main__')
        except SystemExit as status:
            assert status.code in (0,None), 'prepare CLI failed: '+str(status.code)
        assert read(work,'prepare.json')['status']=='PREPARED_COMPLETE_ADOPTION_CANDIDATE'
    elif mode=='read':
        identity_id=read(work,'prepare.json')['publication_id']
        command=['tools/vnext_annual_publication.py','read','--publication-root',str(publication_root),
            '--publication-id',identity_id,'--output-json',str(output)]
        sys.argv=command
        try:runpy.run_path(str(ROOT/command[0]),run_name='__main__')
        except SystemExit as status:assert status.code in (0,None)
        result=read(work,'read.json');assert result['public_row_count']==327 and len(result['verified_source_locations'])==2
    elif mode in ('integration','deep-negatives'):
        identity_id=read(work,'prepare.json')['publication_id']
        post=read(BASE.parent/'annual-publication-close','post-merge-read.json')
        os.environ.update(ANNUAL_FORMAL_TEST_ROOT=str(publication_root),ANNUAL_FORMAL_TEST_ID=identity_id,
            ANNUAL_FORMAL_TEST_REPORT=str(output),ANNUAL_FORMAL_V1_ROOT=post['checks'][1]['root'],
            ANNUAL_FORMAL_PR39_MERGE=post['merge_head'],ANNUAL_PUBLICATION_TEST_ROOT=str(publication_root),
            ANNUAL_PUBLICATION_TEST_ID=identity_id,ANNUAL_PUBLICATION_TEST_REPORT=str(output))
        command=['tests.vnext.test_annual_formal_rehearsal'] if mode=='integration' else [
            'tests.vnext.test_annual_publication_rehearsal.AnnualPublicationRehearsalTest.test_rebound_bundle_counterexamples']
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(command))
        assert result.wasSuccessful() and result.testsRun==(8 if mode=='integration' else 1) and not result.skipped
    else:raise ValueError(mode)
    assert protected()==before
    assert git('rev-parse','HEAD').decode().strip()==head
    assert not git('status','--porcelain','--untracked-files=all').strip()
    code=0
except BaseException:
    traceback.print_exc()
finally:
    sys.stdout.flush();sys.stderr.flush()
    save(work/(mode+'-execution.json'),{'mode':mode,'command':command,'cwd':str(ROOT),'code':identity,
        'started_at_utc':started,'finished_at_utc':now(),'exit_status':code,'github_reads':github,
        'new_business_provider_paid_sec_calls':[0,0,0],'pr38_historical_calls':[2,2,0],
        'log':{'path':str(log),**proof(log)},'harness':{'path':str(Path(__file__)),**proof(Path(__file__))},
        'publication_root':str(publication_root),'candidate_root':str(candidate),'protection_equal':protected()==before})
raise SystemExit(code)
