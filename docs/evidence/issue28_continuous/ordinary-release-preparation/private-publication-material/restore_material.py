"""Restore a review packet into a new external directory; no execution credit."""
import argparse,hashlib,json,tarfile
from pathlib import Path,PurePosixPath

def digest(raw):return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
def safe(root,name):
 p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts
 return root.joinpath(*p.parts)
def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--repository',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--prefix',default='');p.add_argument('--index',default='material-index.json');p.add_argument('--supplement',type=Path);a=p.parse_args()
 out=a.output.resolve();assert not out.exists() and a.repository.resolve() not in out.parents;out.mkdir(parents=True)
 index=json.loads((a.evidence/a.index).read_text());archive=a.evidence/index['archive'];assert digest(archive.read_bytes())==index['archive_binding'];count=0
 with tarfile.open(archive) as tar:
  members={m.name:m for m in tar.getmembers()};assert set(members)==set(index['objects'])
  for name,b in index['files'].items():
   if not name.startswith(a.prefix):continue
   if 'repository_path' in b:
    source=safe(a.repository,b['repository_path'])
    expected={k:b[k] for k in ['sha256','size']}
    if not source.is_file() or source.is_symlink() or digest(source.read_bytes())!=expected:
     assert a.supplement is not None;source=safe(a.supplement,b['repository_path'])
    assert source.is_file() and not source.is_symlink();raw=source.read_bytes()
   else:
    member=members[b['archive_member']];assert member.isfile();raw=tar.extractfile(member).read()
   assert digest(raw)=={k:b[k] for k in ['sha256','size']};dest=safe(out,name);dest.parent.mkdir(parents=True,exist_ok=True)
   with dest.open('xb') as stream:stream.write(raw)
   count+=1
 print(json.dumps({'status':'VERIFIED_RESTORE','file_count':count,'output':str(out),'new_calls':[0,0,0]}))
if __name__=='__main__':main()
