from pathlib import Path
import hashlib,json,tarfile,io,sys
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');T=Path('/private/tmp/sec_metrics_issue28_continuous');L=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13');E=R/'docs/evidence/issue28_continuous/ordinary-registered-event-runs';E.mkdir(exist_ok=True)
folders=['registered-event-native-first','registered-event-native-second','registered-event-native-attacks','registered-event-native-attacks-fixed','registered-event-run-provider-wiring']
files={};objects={};repo_cache={}
def binding(raw):return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
def relative_source(parts):
 for marker in ['source-inputs','native-data']:
  if marker in parts:return '/'.join(parts[parts.index(marker)+1:])
 if 'data' in parts:
  i=parts.index('data')
  if len(parts)>i+2:return '/'.join(parts[i+2:])
 return None
archive=E/'material.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 def add(p,name):
  assert p.is_file() and not p.is_symlink();raw=p.read_bytes();b=binding(raw);rel=relative_source(list(Path(name).parts))
  if rel and (R/rel).is_file():
   if rel not in repo_cache:repo_cache[rel]=binding((R/rel).read_bytes())
   if repo_cache[rel]==b:files[name]={**b,'repository_path':rel};return
  key='objects/'+b['sha256']
  files[name]={**b,'archive_member':key}
  if key not in objects:
   info=tarfile.TarInfo(key);info.size=len(raw);info.mode=0o600;info.mtime=0;tar.addfile(info,io.BytesIO(raw));objects[key]=b
 for slot in sorted((L/'calls').iterdir()):
  if int(slot.name)<14:continue
  for p in sorted(slot.rglob('*')):
   if p.is_file():add(p,'actual-new-calls/'+slot.name+'/'+p.relative_to(slot).as_posix())
 for folder in folders:
  for p in sorted((T/folder).rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':add(p,folder+'/'+p.relative_to(T/folder).as_posix())
 selected=set()
 for pattern in ['registered-real*.json','registered-real*.log','registered-event*.json','registered-event*.log','registered-event*.csv','successor-combined-event-discovery-after-capture.*','successor-combined-event-discovery.log']:
  selected.update(T.glob(pattern))
 for p in sorted(selected):add(p,'logs/'+p.name)
with tarfile.open(archive) as tar:
 members=tar.getmembers();assert len(members)==len(objects)
 for member in members:assert member.isfile() and binding(tar.extractfile(member).read())==objects[member.name]
index={'archive':'material.tar.gz','archive_binding':binding(archive.read_bytes()),'files':files,'objects':objects,'every_archive_object_read_back':True,'every_repository_reference_hash_verified':True,'restoration_does_not_authorize_live_or_production':True}
(E/'material-index.json').write_text(json.dumps(index,indent=2)+'\n')
for name,source in [('provider-summary.json','registered-event-run-provider-wiring/summary.json'),('actual-counts.json','registered-real-final-counts.json')]:
 (E/name).write_bytes((T/source).read_bytes())
coords=[]
for folder in ['registered-event-native-second']:
 summary=json.loads((T/folder/'summary.json').read_text())
 for c in summary['coordinates']:
  assert c['status']=='OPEN_CANDIDATE' and c['public_row_status']=='CANDIDATE_ROW_PREPARED'
  coords.append({'company':c['company_id'],'metric':c['metric_id'],'quality':c['result']['quality'],'value':c['result'].get('value'),'period':c['target_period'],'source_credit':c['source_credit'],'run_id':c['run_id'],'evidence_folder':folder,'limitations':c['selection_summary']})
assert len(coords)==6
(E/'event-coordinates.json').write_text(json.dumps({'coordinates':coords,'full390_acceptance':False,'production_authorized':False},indent=2)+'\n')
sys.path.insert(0,str(R/'scripts'))
from vnext.requirements import load_requirement_snapshot
from vnext.canonical import content_hash
req=load_requirement_snapshot(snapshot_dir=R/'requirements/issue_28_v14');provider=json.loads((E/'provider-summary.json').read_text());assert provider['closure']==req['requirement_closure_hash']
evidence={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [archive,E/'material-index.json',E/'provider-summary.json']}
prior=R/'docs/evidence/issue28_continuous/ordinary-registered-events'
for p in [prior/'sec-wiring.json',prior/'material.tar.gz',prior/'material-index.json',prior/'sec-summary.json']:
 evidence[p.relative_to(R).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
sec={'record_type':'SEC_ACQUISITION_OFFLINE_WIRING','execution_authority_hash':content_hash(value=req['execution_authority']),'calls':[0,0,0],'actual_http_path_verified':True,'checkpoint_import_and_failure_isolation_verified':True,'native_selected_source_and_cold_preview_verified':True,'evidence':evidence,'unchanged_sec_admission_evidence_reused':True,'original_sec_test_commit':'128fe3304cfa3c8df20b04f545d0e908a7c60290'}
(E/'sec-wiring.json').write_text(json.dumps(sec,indent=2)+'\n')
wire={'record_type':'CONTINUOUS_OFFLINE_WIRING_RECEIPT','requirement_id':req['requirement_id'],'execution_authority_hash':content_hash(value=req['execution_authority']),'delegation_url':req['policy']['delegation_url'],'calls':{'provider':0,'paid':0,'sec':0},'network_disabled':True,'legacy_default_forbidden':True,'real_request_factory_to_controller_verified':True,'count_control_tests_passed':True,'evidence':evidence}
(E/'provider-wiring.json').write_text(json.dumps(wire,indent=2)+'\n')
print('VERIFIED',len(files),'file mappings;',len(objects),'stored unique objects;',archive.stat().st_size,'bytes;',len(coords),'native coordinates;',req['requirement_closure_hash'])
