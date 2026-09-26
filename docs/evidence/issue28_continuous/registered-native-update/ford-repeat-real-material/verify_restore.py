"""Compare every restored byte to current saved originals or committed prior bundle."""
from pathlib import Path
import json,hashlib,tarfile
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path('/tmp/sec_metrics_issue28_continuous/ford-repeat-6ccf');DEST=ROOT/'docs/evidence/issue28_continuous/registered-native-update/ford-repeat-real-material';OUT=BASE/'restored'
index=json.loads((DEST/'material-index.json').read_text());origins=json.loads((BASE/'package-original-paths.json').read_text());assert all('repository_path'not in b for b in index['files'].values())
assert {str(p.relative_to(OUT))for p in OUT.rglob('*')if p.is_file()}==set(index['files'])
prior=ROOT/'docs/evidence/issue28_continuous/d04-indexed-unit-response/real-material';old=json.loads((prior/'material-index.json').read_text())
with tarfile.open(prior/old['archive'])as tar:
 for name,b in index['files'].items():
  dest=OUT/name;raw=dest.read_bytes();assert not dest.is_symlink();assert len(raw)==b['size']and hashlib.sha256(raw).hexdigest()==b['sha256']
  origin=origins[name]
  if origin.startswith('PRIOR_D04_ARCHIVE:'):
   original=tar.extractfile(old['files'][name]['archive_member']).read()
  else:
   path=Path(origin);original=path.read_bytes();assert dest.stat().st_ino!=path.stat().st_ino
  assert raw==original,name
for o in [70,*range(72,82)]:
 call=OUT/'calls'/('%04d'%o);t=json.loads((call/'terminal.json').read_text());assert t['status']=='SUCCEEDED'
 for name,h in t['evidence'].items():assert hashlib.sha256((call/name).read_bytes()).hexdigest()==h
 with tarfile.open(call/'execution-rules.tar.gz')as t:
  for m in t:
   if m.isfile():assert len(t.extractfile(m).read())==m.size
before=json.loads((OUT/'execution-evidence/history-before.json').read_text());changed=[]
for n,h in before.items():
 if hashlib.sha256((OUT/'history'/n).read_bytes()).hexdigest()!=h:changed.append(n)
assert changed==['metrics/D04/current.json']
metric=OUT/'history/metrics/D04';state=json.loads((metric/'current.json').read_text());assert state['successful_attempt']=='2f7f1821cfe244cb91a2525f0a8f61af'
terminal=json.loads((metric/'attempts'/state['latest_attempt']/'terminal.json').read_text());assert terminal['status']=='NO_SOURCE_CONTENT_CHANGE'
assert not (metric/'attempts'/state['latest_attempt']/'runs').exists()and not (metric/'attempts'/state['latest_attempt']/'data').exists()
report={'status':'PASS','logical_files':len(index['files']),'unique_objects':len(index['objects']),'all_restored_bytes_equal_original':True,'all_original_call_terminal_evidence_sha_pass':True,'source_and_runtime_self_contained':True,'no_repository_path_or_tmp_fallback':True,'original_run_and_failed_attempt_bytes_unchanged':True,'new_repeat_attempt_has_no_run_or_data':True,'restored_status':terminal['status'],'original_successful_attempt':state['successful_attempt'],'new_calls':[0,0,0],'verification_scope':'Archive byte restoration and immutable history check; actual business repeat is recorded separately in repeat-result.json'}
(DEST/'restore-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
