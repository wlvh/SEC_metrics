import hashlib,json,os,subprocess,time
from pathlib import Path
w=Path('/workspace/work'); runtime=w/'company-runtime-release'; state=w/'company-recovery-release-state'; trust=w/'company-trust'; company='jpmorgan_chase'
env=dict(os.environ,SEC_METRICS_SOURCE_TRUST_ROOT=str(trust),COMPANY_DENY_READ_ROOTS='/workspace/SEC_metrics:/workspace/work/probe-b/ledger:/workspace/work/sec-company-compute/evidence',PYTHONDONTWRITEBYTECODE='1')
base=['python',str(w/'isolated_company_cli.py'),str(runtime)]
results=[]
def cli(command,extra,name):
 start=time.monotonic()
 args=base+[command,'--state-root',str(state),'--trust-root',str(trust),'--company',company]+extra
 with (w/name).open('w') as f:p=subprocess.run(args,env=env,stdout=f,stderr=subprocess.STDOUT)
 d={'operation':command,'exit_code':p.returncode,'seconds':time.monotonic()-start,'log':name}
 results.append(d);print(json.dumps(d),flush=True)
 assert p.returncode==0,(name,(w/name).read_text()[-3000:])
 return json.loads((w/name).read_text())
cli('install',['--package-root',str(w/'product-b-source')],'company-recovery-release-first-install.log')
first=cli('compute',['--metric','A08'],'company-recovery-release-first-compute.log')
assert first['metrics'][0]['status']=='CANDIDATE_READY'
current=(state/'current_source.json').read_bytes(); old=first['metrics'][0]['last_verified_candidate']; old_work=Path(old['rows_root']).parent
def files_hash(root):
 return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
old_files=files_hash(old_work); previous_report=(state/'company-results.json').read_bytes()
code='''import os,sys
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[1]+'/scripts']
from vnext.company_handoff import install_company
def fault(step):
 if step=='after_new_source_move': os._exit(91)
install_company(package_root=Path(sys.argv[2]),state_root=Path(sys.argv[3]),company_id='jpmorgan_chase',fault=fault)
'''
start=time.monotonic(); p=subprocess.run(['python','-c',code,str(runtime),str(w/'product-b-source-v2'),str(state)],env=env,capture_output=True,text=True)
assert p.returncode==91,p.stderr
assert (state/'current_source.json').read_bytes()==current
assert (state/'company-results.json').read_bytes()==previous_report
results.append({'operation':'abrupt_exit_after_new_source_move','exit_code':91,'seconds':time.monotonic()-start,'committed_pointer_unchanged':True,'old_report_unchanged':True})
recovered=cli('compute',['--metric','A08'],'company-recovery-release-restart-compute.log')
assert recovered['source_checkpoint_id']==first['source_checkpoint_id']
assert recovered['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
assert recovered['metrics'][0]['last_verified_candidate']['attempt_id']==old['attempt_id']
assert files_hash(old_work)==old_files
cli('install',['--package-root',str(w/'product-b-source-v2')],'company-recovery-release-retry-install.log')
updated=cli('compute',['--metric','A08'],'company-recovery-release-update-compute.log')
assert updated['source_checkpoint_id']!=first['source_checkpoint_id']
assert updated['source_root']==first['source_root']
assert updated['metrics'][0]['status']=='CANDIDATE_READY'
assert files_hash(old_work)==old_files
results.append({'operation':'verify_old_run_bytes_after_update','files':len(old_files),'unchanged':True})
(w/'company-material-import-recovery.json').write_text(json.dumps({'status':'PASSED','uid':os.getuid(),'runtime_read_only':not any(p.stat().st_mode&0o222 for p in runtime.rglob('*')),'denied_roots':env['COMPANY_DENY_READ_ROOTS'].split(':'),'stable_source_root':first['source_root'],'first_checkpoint':first['source_checkpoint_id'],'updated_checkpoint':updated['source_checkpoint_id'],'results':results,'new_business_calls':[0,0,0]},indent=2))
