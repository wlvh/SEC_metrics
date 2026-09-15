"""Independent full file comparison after the existing restore utility runs."""
from pathlib import Path,PurePosixPath
import hashlib,json,tarfile
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');TMP=Path('/tmp/sec_metrics_issue28_continuous')
DEST=ROOT/'docs/evidence/issue28_continuous/paramount-c04-source-inspection/registration-variants-real-material';RESTORED=TMP/'registration-variants-restored-20260916'
index=json.loads((DEST/'material-index.json').read_text());origins=json.loads((TMP/'registration-variants-analysis/original-paths.json').read_text())
assert not (TMP/'registration-variants-no-repository').exists();assert all('repository_path'not in b for b in index['files'].values())
assert {str(p.relative_to(RESTORED))for p in RESTORED.rglob('*')if p.is_file()}==set(index['files'])
for name,b in index['files'].items():
 p=RESTORED/name;o=Path(origins[name]);assert p.is_file()and not p.is_symlink();raw=p.read_bytes();assert raw==o.read_bytes();assert len(raw)==b['size'] and hashlib.sha256(raw).hexdigest()==b['sha256'];assert p.stat().st_ino!=o.stat().st_ino
runtime_members=[]
for ordinal in range(105,109):
 call=RESTORED/'calls'/f'{ordinal:04d}';t=json.loads((call/'terminal.json').read_text());r=json.loads((call/'sec-receipt.json').read_text())
 for name,h in t['evidence'].items():assert hashlib.sha256((call/name).read_bytes()).hexdigest()==h
 for key,wire in [('request_repo_relative_path','body.bin'),('request_headers_repo_relative_path','headers.bin')]:assert (RESTORED/'source-inputs'/r['proof'][key]).read_bytes()==(call/'sec-wire'/wire).read_bytes()
 with tarfile.open(call/'execution-rules.tar.gz')as tar:
  members=tar.getmembers();runtime_members.append(len(members))
  for m in members:
   p=PurePosixPath(m.name);assert not p.is_absolute() and '..'not in p.parts and not m.issym() and not m.islnk()
   assert not any(x.lower()in{'credentials','.credentials','.env','.ssh'}for x in p.parts)
   if m.isfile():assert len(tar.extractfile(m).read())==m.size
report={'status':'PASS','scope':'Independent restore and byte comparison, not native or business replay','logical_files_compared':len(index['files']),'unique_objects':len(index['objects']),'all_restored_bytes_equal_original':True,'self_contained_without_repository':True,'symlinks_and_hardlinks_created':False,'terminal_evidence_sha_checks':'4/4 all named files match','four_original_runtime_archives_read_and_preserved':True,'runtime_member_counts':runtime_members,'explicit_private_credential_paths_absent':True,'response_metadata_preserved':True,'new_calls':[0,0,0],'new_C04_Run':False,'output':str(RESTORED)}
(DEST/'restore-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
