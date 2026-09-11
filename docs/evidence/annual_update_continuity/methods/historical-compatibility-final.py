from pathlib import Path,PurePosixPath
import sys,json,zipfile,hashlib,stat,csv,io
r=Path('/Users/lyuhongwang/Developer/SEC_metrics');w=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');sys.path[:0]=[str(r),str(r/'scripts')]
from vnext.canonical import strict_json_file,canonical_json_bytes,sha256_file
from vnext import publication as pub,annual_continuity as c
record=strict_json_file(path=r/'docs/evidence/annual_publication/close/run-binding.json')['original_archive'];archive=Path(record['path']);assert sha256_file(path=archive)==record['sha256'] and archive.stat().st_size==record['size']
root=w/'historical-v1-final';assert not root.exists();root.mkdir()
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for info in z.infolist():
  path=PurePosixPath(info.filename);assert not path.is_absolute() and '..' not in path.parts and not stat.S_ISLNK(info.external_attr>>16)
 z.extractall(root)
code=c.code_identity();result={'record_type':'CURRENT_CODE_NETWORK_DENIED_V1_R3_COMPATIBILITY','code':code,'verified_original_archive':record,'views':[]}
view=pub.PublicationView.open(publication_root=root)
for label,directory in [('OLD_V1',view.bundle_dir),('ORIGINAL_R3',r/'outputs/publications'/json.loads((r/'outputs/active_publication.json').read_text())['previous_publication_id'])]:
 m=pub.verify_publication_bundle(bundle_dir=directory);v=pub.PublicationView(publication_id=m['publication_id'],bundle_dir=directory,manifest=m);matrix=list(csv.DictReader(io.StringIO(v.read_bytes(relative_path='metrics_matrix.csv').decode())));assert len(matrix)==327
 evidence=v.read_bytes(relative_path='metric_evidence.csv');selected={}
 for metric in ('B01','B10'):
  try:n=v.native_result(company_id='marriott_international',metric_id=metric)
  except ValueError as e:
   assert label=='ORIGINAL_R3' and metric=='B01' and 'NATIVE_CONTENT_NOT_EMBEDDED' in str(e);selected[metric]={'status':'EXPLICIT_NATIVE_UNAVAILABLE','reason':str(e)};continue
  sources=[]
  for source in n['sources']:
   paths=[x['path'] for x in m['files'] if x['sha256']==source['raw_asset_id'][7:]];assert paths
   for path in paths:assert hashlib.sha256(v.read_bytes(relative_path=path)).hexdigest()==source['raw_asset_id'][7:]
   sources.append({'reference':source,'matching_raw_bundle_paths':paths})
  selected[metric]={'status':'PASS_NATIVE_READ','result':n['result'],'owner_publication_id':n['owner_publication_id'],'sources':sources}
 result['views'].append({'label':label,'publication_id':v.publication_id,'manifest_sha256':sha256_file(path=directory/'publication_manifest.json'),'matrix_rows':len(matrix),'evidence_sha256':hashlib.sha256(evidence).hexdigest(),'selected':selected});print(label,'PASS',flush=True)
assert c.code_identity()==code;result.update(status='PASS_HISTORICAL_READ_ONLY',new_provider_paid_sec_calls=[0,0,0])
with (w/'historical-compatibility-final.json').open('xb') as out:out.write(canonical_json_bytes(value=result))
