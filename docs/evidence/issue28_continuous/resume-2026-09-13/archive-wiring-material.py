from pathlib import Path
import hashlib,json,sys,tarfile
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext.canonical import content_hash
from vnext.requirements import load_requirement_snapshot
T=Path('/private/tmp/sec_metrics_issue28_continuous');E=R/'docs/evidence/issue28_continuous/resume-2026-09-13'
folders=['resume-v15-wire-first','resume-v15-wire-second','resume-native-wiring-first','resume-native-wiring-second','resume-native-wiring-third','resume-native-wiring-fourth','resume-native-wiring-fifth']
files=[p for p in T.glob('resume-*.log') if p.is_file()]+[T/'resume-semantics-current.json',T/'resume-provider-egress-current.json',T/'resume-company-literals-current.csv']
files=[p for p in files if p.exists()]
index={}
archive=E/'offline-wiring-material.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in files:
  raw=p.read_bytes();name='logs/'+p.name;index[name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)};tar.add(p,arcname=name,recursive=False)
 for folder in folders:
  for p in sorted((T/folder).rglob('*')):
   if not p.is_file():continue
   assert not p.is_symlink();raw=p.read_bytes();name=folder+'/'+p.relative_to(T/folder).as_posix()
   index[name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)};tar.add(p,arcname=name,recursive=False)
with tarfile.open(archive) as tar:
 members=tar.getmembers();assert len(members)==len(index) and {m.name for m in members}==set(index)
 for m in members:
  assert m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts
  raw=tar.extractfile(m).read();assert index[m.name]=={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
(E/'offline-wiring-members.json').write_text(json.dumps({'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'members':index,'all_members_read_and_verified':True},indent=2)+'\n')
summary=json.loads((T/'resume-native-wiring-fifth/summary.json').read_text())
(E/'offline-wiring-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
requirement=load_requirement_snapshot(snapshot_dir=R/'requirements/issue_28_v14')
assert summary['closure']==requirement['requirement_closure_hash']
receipt={'record_type':'CONTINUOUS_OFFLINE_WIRING_RECEIPT','requirement_id':requirement['requirement_id'],
 'execution_authority_hash':content_hash(value=requirement['execution_authority']),
 'delegation_url':requirement['policy']['delegation_url'],
 'calls':{'provider':0,'paid':0,'sec':0},'network_disabled':True,'legacy_default_forbidden':True,
 'real_request_factory_to_controller_verified':True,'count_control_tests_passed':True,
 'evidence':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [archive,E/'offline-wiring-members.json',E/'offline-wiring-summary.json']}}
(E/'offline-wiring.json').write_text(json.dumps(receipt,indent=2)+'\n')
from vnext.continuous_call_wiring import validate_wiring_receipt
assert validate_wiring_receipt(requirement=requirement)==receipt
print('verified',len(index),'archive members',archive.stat().st_size,'bytes; closure',requirement['requirement_closure_hash'])
