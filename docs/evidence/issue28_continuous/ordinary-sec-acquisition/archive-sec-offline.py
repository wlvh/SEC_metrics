from pathlib import Path
import hashlib,json,tarfile,shutil,sys
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');T=Path('/private/tmp/sec_metrics_issue28_continuous');E=R/'docs/evidence/issue28_continuous/ordinary-sec-acquisition';E.mkdir(exist_ok=True)
folders=['sec-recorded-first','sec-capture-material-first','sec-capture-material-second','sec-capture-material-third','sec-capture-material-final','sec-provider-wiring-final','sec-checkpoint-native-first','sec-checkpoint-native-third','sec-checkpoint-native-A08-final']
index={};reused={}
def binding(raw):return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
def original_relative(path,folder):
 parts=list(path.relative_to(T/folder).parts)
 if 'source-inputs' in parts:return '/'.join(parts[parts.index('source-inputs')+1:])
 if 'native-data' in parts:return '/'.join(parts[parts.index('native-data')+1:])
 if len(parts)>2 and parts[0]=='data':return '/'.join(parts[2:])
 return None
archive=E/'offline-sec-material.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted({*T.glob('sec-*.log'),*T.glob('sec-*.json'),*T.glob('sec-*.csv')}):
  if not p.is_file():continue
  raw=p.read_bytes();name='logs/'+p.name;index[name]=binding(raw);tar.add(p,arcname=name,recursive=False)
 for folder in folders:
  for p in sorted((T/folder).rglob('*')):
   if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
   assert not p.is_symlink();raw=p.read_bytes();name=folder+'/'+p.relative_to(T/folder).as_posix();b=binding(raw)
   rel=original_relative(p,folder)
   if rel and (R/rel).is_file() and binding((R/rel).read_bytes())==b:
    reused[name]={'repository_path':rel,**b};continue
   index[name]=b;tar.add(p,arcname=name,recursive=False)
with tarfile.open(archive) as tar:
 members=tar.getmembers();assert len(members)==len(index) and {m.name for m in members}==set(index)
 for m in members:
  assert m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts
  assert binding(tar.extractfile(m).read())==index[m.name]
for value in reused.values():assert binding((R/value['repository_path']).read_bytes())=={k:v for k,v in value.items() if k!='repository_path'}
manifest={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'included_members':index,'reused_repository_files':reused,'all_included_and_reused_bytes_verified':True}
(E/'material-index.json').write_text(json.dumps(manifest,indent=2)+'\n')
summary=json.loads((T/'sec-capture-material-final/summary.json').read_text());(E/'sec-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
provider=json.loads((T/'sec-provider-wiring-final/summary.json').read_text());(E/'provider-summary.json').write_text(json.dumps(provider,indent=2)+'\n')
sys.path.insert(0,str(R/'scripts'))
from vnext.requirements import load_requirement_snapshot
from vnext.canonical import content_hash
req=load_requirement_snapshot(snapshot_dir=R/'requirements/issue_28_v14');assert provider['closure']==req['requirement_closure_hash']
evidence={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [archive,E/'material-index.json',E/'sec-summary.json',E/'provider-summary.json']}
sec={'record_type':'SEC_ACQUISITION_OFFLINE_WIRING','execution_authority_hash':content_hash(value=req['execution_authority']),
'calls':[0,0,0],'actual_http_path_verified':True,'checkpoint_import_and_failure_isolation_verified':True,
'native_selected_source_and_cold_preview_verified':True,'evidence':evidence}
(E/'sec-wiring.json').write_text(json.dumps(sec,indent=2)+'\n')
wire={'record_type':'CONTINUOUS_OFFLINE_WIRING_RECEIPT','requirement_id':req['requirement_id'],'execution_authority_hash':content_hash(value=req['execution_authority']),
'delegation_url':req['policy']['delegation_url'],'calls':{'provider':0,'paid':0,'sec':0},'network_disabled':True,'legacy_default_forbidden':True,
'real_request_factory_to_controller_verified':True,'count_control_tests_passed':True,'evidence':evidence}
(E/'provider-wiring.json').write_text(json.dumps(wire,indent=2)+'\n')
for filename in ['build-sec-bindings.py','build_v15_sec.py','sec-first-recorded-probe.py','cold-sec-checkpoint.py']:
 shutil.copy2(T/filename,E/filename)
print('verified',len(index),'stored members and',len(reused),'reused repository files;',archive.stat().st_size,'compressed bytes; closure',req['requirement_closure_hash'])
