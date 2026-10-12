"""Current C04 receives a minimal saved source package, without copied rules."""
import hashlib,io,json,socket,tempfile,time,shutil
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
E=Path(__file__).parent;v=json.loads((E/'actual-company.json').read_text());r=v['results'][0];origin=Path(v['results'][0]['args'][v['results'][0]['args'].index('--source-root')+1]);record=Path(r['first']['metrics'][0]['result_root']);manifest=json.loads((record/'manifest.json').read_text());base=Path(tempfile.mkdtemp(prefix='issue28-current-c04-source-only-'));source=base/'source';paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for p in manifest['source_proofs']:paths.update((p['request_repo_relative_path'],p['request_headers_repo_relative_path']))
for p in paths:
 target=source/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin/p,target)
assert not (source/'catalog').exists() and sorted(p.name for p in (source/'config').iterdir())==['company_registry.csv']
before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths};out=io.StringIO();start=time.perf_counter();args=['run','--company','marriott_international','--source-root',str(source),'--metric','C04','--work-dir',str(base/'state'),'--output-dir',str(base/'out')]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):code=main(args)
value=json.loads(out.getvalue());assert code==0 and value['metrics'][0]['status']=='CANDIDATE_READY',value;assert value['metrics'][0]['result_id']==r['first']['metrics'][0]['result_id'];assert before=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths};report={'args':args,'seconds':time.perf_counter()-start,'exit_code':code,'report':value,'copied_source_files':len(paths),'copied_rules':False,'same_result_id':True,'source_files_unchanged':True,'new_calls':[0,0,0]};(E/'source-only.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'seconds':report['seconds'],'status':value['metrics'][0]['status'],'result_id':value['metrics'][0]['result_id'],'files':len(paths),'no_copied_rules':True}))
