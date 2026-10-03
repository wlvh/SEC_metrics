"""Restore recorded native material by its existing index, without new calls."""
from pathlib import Path
import hashlib,json,tarfile,time
source=Path('/workspace/work/sec-company-compute/docs/evidence/issue28_continuous/review-5207290213')
index=json.loads((source/'recorded-native-material-index.json').read_text())
archive=source/index['archive_file'];start=time.monotonic()
assert hashlib.sha256(archive.read_bytes()).hexdigest()==index['archive_sha256']
out=Path('/workspace/work/recorded-d04-restored');out.mkdir()
with tarfile.open(archive) as tar:
 for name,binding in index['files'].items():
  p=Path(name);assert not p.is_absolute() and '..' not in p.parts
  raw=tar.extractfile(name).read();assert hashlib.sha256(raw).hexdigest()==binding['sha256'] and len(raw)==binding['size'],name
  target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
report={'status':'HASH_INDEX_RESTORED','archive_sha256':index['archive_sha256'],'files':len(index['files']),'seconds':time.monotonic()-start,'new_business_calls':[0,0,0],'metric_acceptance':False}
(out/'restore-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
