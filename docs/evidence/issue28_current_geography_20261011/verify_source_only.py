"""New actual bank task with source bodies/proofs only; no copied program rules."""
import hashlib,io,json,shutil,socket,tempfile,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
E=Path(__file__).parent;v=json.loads((E/'actual-company.json').read_text());r=v['results'][0]
manifest=json.loads((Path(r['first']['metrics'][0]['result_root'])/'manifest.json').read_text())
origin=Path(manifest['source_root']);base=Path(tempfile.mkdtemp(prefix='issue28-a13-source-only-'));source=base/'source'
paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for p in manifest['source_proofs']:paths.update((p['request_repo_relative_path'],p['request_headers_repo_relative_path']))
for p in paths:
    target=source/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin/p,target)
assert len(manifest['source_proofs'])==3 and not (source/'catalog').exists()
assert sorted(p.name for p in (source/'config').iterdir())==['company_registry.csv']
before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths}
args=['run','--company','jpmorgan_chase','--source-root',str(source),'--metric','A13',
      '--work-dir',str(base/'state'),'--output-dir',str(base/'out')]
out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):code=main(args)
report=json.loads(out.getvalue());seconds=time.perf_counter()-start
assert code==0 and report['metrics'][0]['status']=='CANDIDATE_READY',report
assert report['metrics'][0]['result_id']==r['first']['metrics'][0]['result_id']
assert before=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths}
result={'args':args,'seconds':seconds,'report':report,'files':len(paths),'copied_rules':False,
        'same_result_id':True,'sources_unchanged':True,'new_calls':[0,0,0]}
(E/'source-only.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS_ACTUAL_CURRENT_A13_SOURCE_ONLY',seconds,len(paths),report['metrics'][0]['result_id'])
