"""Restore verified source-test material using exact already-versioned bytes."""
from pathlib import Path,PurePosixPath
import argparse,json,hashlib,tarfile

def check(raw,binding):
 assert {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}=={k:binding[k] for k in ['sha256','size']}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--repository',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--prefix',default='');a=parser.parse_args()
 out=a.output.resolve();assert not out.exists();out.mkdir(parents=True)
 index=json.loads((a.evidence/'material-index.json').read_text());archive=a.evidence/'offline-sec-material.tar.gz'
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==index['archive_sha256']
 def write(name,raw,binding):
  if not name.startswith(a.prefix):return
  parts=PurePosixPath(name);assert not parts.is_absolute() and '..' not in parts.parts
  check(raw,binding);p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('xb') as file:file.write(raw)
 with tarfile.open(archive) as tar:
  members=tar.getmembers();assert {m.name for m in members}==set(index['included_members'])
  for m in members:
   assert m.isfile();write(m.name,tar.extractfile(m).read(),index['included_members'][m.name])
 for name,binding in index['reused_repository_files'].items():
  p=a.repository/binding['repository_path'];assert p.is_file() and not p.is_symlink()
  write(name,p.read_bytes(),binding)
 print('VERIFIED_RESTORE',out)
if __name__=='__main__':main()
