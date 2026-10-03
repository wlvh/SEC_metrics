from pathlib import Path
import hashlib,tarfile,json,shutil,sys
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');T=Path('/private/tmp/sec_metrics_issue28_continuous');E=R/'docs/evidence/issue28_continuous/ordinary-continuity-policy';E.mkdir(exist_ok=True)
folders=['continuity-policy-native-first','continuity-policy-native-second','continuity-native-attacks-first','continuity-wiring-first','continuity-wiring-second','continuity-native-ci-test','continuity-instant-ci-test']
files=sorted({*T.glob('continuity-*.log'),*T.glob('continuity-*.json'),*T.glob('continuity-*.csv'),T/'jpm-salesforce-current-source-dependencies.json',T/'jpm-salesforce-current-source-dependencies.log'})
index={};archive=E/'native-continuity-material.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in files:
  if not p.is_file():continue
  raw=p.read_bytes();name='logs-and-inspection/'+p.name;index[name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)};tar.add(p,arcname=name,recursive=False)
 for folder in folders:
  for p in sorted((T/folder).rglob('*')):
   if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
   assert not p.is_symlink();raw=p.read_bytes();name=folder+'/'+p.relative_to(T/folder).as_posix()
   index[name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)};tar.add(p,arcname=name,recursive=False)
with tarfile.open(archive) as tar:
 members=tar.getmembers();assert len(members)==len(index) and {m.name for m in members}==set(index)
 for member in members:
  assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
  raw=tar.extractfile(member).read();assert index[member.name]=={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
(E/'archive-members.json').write_text(json.dumps({'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'members':index,'all_members_read_and_verified':True},indent=2)+'\n')
summary=json.loads((T/'continuity-wiring-second/summary.json').read_text());(E/'offline-wiring-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
sys.path.insert(0,str(R/'scripts'))
from vnext.canonical import content_hash
from vnext.requirements import load_requirement_snapshot
r=load_requirement_snapshot(snapshot_dir=R/'requirements/issue_28_v14');assert summary['closure']==r['requirement_closure_hash']
receipt={'record_type':'CONTINUOUS_OFFLINE_WIRING_RECEIPT','requirement_id':r['requirement_id'],'execution_authority_hash':content_hash(value=r['execution_authority']),
'delegation_url':r['policy']['delegation_url'],'calls':{'provider':0,'paid':0,'sec':0},'network_disabled':True,'legacy_default_forbidden':True,
'real_request_factory_to_controller_verified':True,'count_control_tests_passed':True,
'evidence':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [archive,E/'archive-members.json',E/'offline-wiring-summary.json']}}
(E/'offline-wiring.json').write_text(json.dumps(receipt,indent=2)+'\n')
from vnext.continuous_call_wiring import validate_wiring_receipt
assert validate_wiring_receipt(requirement=r)==receipt
for name in ['refresh-continuity-binding.py','refresh-continuity-binding-second.py','build_v15_continuity.py','check-continuity-native.py','cold-continuity.py']:
 shutil.copy2(T/name,E/name)
print('verified',len(index),'members;',archive.stat().st_size,'compressed bytes; closure',r['requirement_closure_hash'])
