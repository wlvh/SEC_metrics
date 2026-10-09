"""One task's original call material, lossless SHA256 blob dedup; no result credit."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,io,json,tarfile,tempfile,os
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');L=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ordinals',required=True);p.add_argument('--result-root',type=Path,required=True);p.add_argument('--log',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
assert a.output_root.is_absolute() and not a.output_root.exists();a.output_root.mkdir(parents=True)
logical={};blobs={};sources={};states=[]
def add(name,data):
 assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
 digest=hashlib.sha256(data).hexdigest();entry={'sha256':digest,'bytes':len(data)}
 assert name not in logical or logical[name]==entry;logical[name]=entry
 if digest not in blobs:blobs[digest]=data
 else:assert blobs[digest]==data
for ordinal in [int(x) for x in a.ordinals.split(',')]:
 slot=L/'calls'/('%04d'%ordinal);assert slot.is_dir() and not slot.is_symlink()
 for file in sorted(slot.rglob('*')):
  assert not file.is_symlink()
  if file.is_file():
   data=file.read_bytes();add('fixed-ledger/calls/'+slot.name+'/'+str(file.relative_to(slot)),data);sources[str(file)]=hashlib.sha256(data).hexdigest()
 state=json.loads((slot/'terminal.json').read_text()) if (slot/'terminal.json').exists() else {'status':'UNKNOWN_NO_TERMINAL'}
 states.append({'ordinal':ordinal,'status':state['status'],'stop_reason':state.get('stop_reason'),'credit_assigned_by_archive':False})
 if (slot/'source.json').exists():
  source=json.loads((slot/'source.json').read_text())
  assert source['metric_id']=='B13' and source.get('program_quantity_role_contract_version')=='B13_PROGRAM_QUANTITY_ROLES_V1'
  for proof in source['source_proofs']:
   for pathkey,hashkey in [('request_repo_relative_path','request_body_sha256'),('request_headers_repo_relative_path','request_headers_sha256')]:
    if pathkey in proof:
     rel=proof[pathkey];assert not PurePosixPath(rel).is_absolute() and '..' not in PurePosixPath(rel).parts
     file=R/rel;data=file.read_bytes();assert hashlib.sha256(data).hexdigest()==proof[hashkey]
     add('source-originals/'+rel,data);sources[str(file)]=hashlib.sha256(data).hexdigest()
 if (slot/'execution-rules.tar.gz').exists():
  rules=json.loads((slot/'execution-rules.json').read_text())['files']
  with tarfile.open(slot/'execution-rules.tar.gz') as tar:
   assert {m.name for m in tar.getmembers()}==set(rules)
   for member in tar.getmembers():
    assert member.isfile();data=tar.extractfile(member).read();assert rules[member.name]=={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
    add('execution-runtime/'+slot.name+'/'+member.name,data)
for file in sorted(a.result_root.rglob('*')):
 assert not file.is_symlink()
 if file.is_file():
  data=file.read_bytes();add('task-result/'+str(file.relative_to(a.result_root)),data);sources[str(file)]=hashlib.sha256(data).hexdigest()
if a.log.exists():
 data=a.log.read_bytes();add('task-execution.log',data);sources[str(a.log)]=hashlib.sha256(data).hexdigest()
# Pin original counter/allowance evidence as a point-in-time view, without
# overwriting, truncating or treating this copied ledger as live authority.
for name in ['binding.json','claims.jsonl']:
 file=L/name;data=file.read_bytes();add('fixed-ledger/'+name,data);sources[str(file)]=hashlib.sha256(data).hexdigest()
manifest={'record_type':'TASK_ORIGINAL_BYTES_DEDUP_ARCHIVE','schema_version':1,'original_calls':states,'files':logical,
 'source_paths_and_hashes':sources,'logical_bytes':sum(x['bytes'] for x in logical.values()),'unique_bytes':sum(map(len,blobs.values())),
 'new_calls':[0,0,0],'production_authorized':False,'business_acceptance_inferred':False}
rawmanifest=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode();archive=a.output_root/'original-material.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for name,data in [('manifest.json',rawmanifest)]+[('blobs/'+k,v) for k,v in sorted(blobs.items())]:
  member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;member.mtime=0;tar.addfile(member,io.BytesIO(data))
# Read every saved blob and reconstruct every logical path under a disposable
# directory. This checks full recovery rather than only the outer archive hash.
with tempfile.TemporaryDirectory(prefix='b13-original-restore-') as directory:
 restored=Path(directory)
 with tarfile.open(archive) as tar:
  assert {m.name for m in tar.getmembers()}=={'manifest.json'}|{'blobs/'+key for key in blobs}
  assert tar.extractfile('manifest.json').read()==rawmanifest
  for digest,expected in blobs.items():
   data=tar.extractfile('blobs/'+digest).read();assert data==expected and hashlib.sha256(data).hexdigest()==digest
   file=restored/'blobs'/digest;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
 for name,meta in logical.items():
  target=restored/'logical'/name;target.parent.mkdir(parents=True,exist_ok=True);os.link(restored/'blobs'/meta['sha256'],target)
  assert target.stat().st_size==meta['bytes'] and hashlib.sha256(target.read_bytes()).hexdigest()==meta['sha256']
# Calls and sources must still match their snapshots; ongoing source mutation
# is a reason to refuse a completed archive, not silently accept mixed bytes.
for path,digest in sources.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,'ORIGINAL_CHANGED_DURING_ARCHIVE'
(a.output_root/'manifest.json').write_bytes(rawmanifest)
summary={'status':'ORIGINAL_BYTES_ARCHIVE_FULL_RESTORE_VERIFIED','original_calls':states,'logical_files':len(logical),'unique_blobs':len(blobs),
 'logical_bytes':manifest['logical_bytes'],'unique_bytes':manifest['unique_bytes'],'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
 'new_calls':[0,0,0],'failed_calls_retained_without_credit':True}
(a.output_root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
