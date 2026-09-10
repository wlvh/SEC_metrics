"""Read actual isolated complete versions in a fresh network-denied process."""
from pathlib import Path
import argparse,csv,io,json,hashlib,sys
from datetime import datetime,timezone
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import publication as pub,annual_publication as annual,annual_continuity as flow
from vnext.canonical import strict_json_file,strict_json_loads,canonical_json_bytes,sha256_file
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--include-previous',action='store_true');args=p.parse_args()
assert not args.output.exists()
code=flow.code_identity();actual=(ROOT/'outputs/active_publication.json').read_bytes()
view=pub.PublicationView.open(publication_root=args.root);views=[view]
if args.include_previous:
 old=view.manifest['previous_publication_id'];directory=view.bundle_dir.parent/old
 manifest=pub.verify_publication_bundle(bundle_dir=directory)
 assert manifest['publication_id']==old
 views.insert(0,pub.PublicationView(publication_id=old,bundle_dir=directory,manifest=manifest))
items=[]
for view in views:
 matrix=list(csv.DictReader(io.StringIO(view.read_bytes(relative_path='metrics_matrix.csv').decode())))
 evidence=view.read_bytes(relative_path='metric_evidence.csv');batch=strict_json_file(path=view.bundle_dir/annual.BATCH)
 assert len(matrix)==327 and (batch['selected_result_count'],batch['inherited_result_count'],len(batch['cumulative_result_bindings']))==(2,238,240)
 selected={}
 for metric in ('B01','B10'):
  native=view.native_result(company_id='marriott_international',metric_id=metric)
  assert native['owner_publication_id']==view.publication_id
  records=[strict_json_loads(text=x) for x in native['records_raw'].decode().splitlines()];sources=[]
  for source in native['sources']:
   raw=next(x for x in records if x['record_type']=='RAW_BLOB' and x['raw_asset_id']==source['raw_asset_id'])
   path='internal/annual_snapshot/data/'+raw['storage_uri'];body=view.read_bytes(relative_path=path)
   assert hashlib.sha256(body).hexdigest()==raw['raw_asset_id'][7:] and len(body)==raw['byte_length']
   sources.append({'source_reference':source,'raw_blob':raw,'bundle_path':path,'sha256':hashlib.sha256(body).hexdigest()})
  selected[metric]={'result':native['result'],'run_path':native['run_path'],'sources':sources,
                    'records_sha256':hashlib.sha256(native['records_raw']).hexdigest()}
 items.append({'publication_id':view.publication_id,'previous_publication_id':view.manifest['previous_publication_id'],
   'manifest_sha256':sha256_file(path=view.bundle_dir/'publication_manifest.json'),'metadata':strict_json_file(path=view.bundle_dir/annual.META),
   'matrix_rows':len(matrix),'complete':batch,'selected':selected,'evidence_sha256':hashlib.sha256(evidence).hexdigest()})
 print('COLD_READ_PASS',view.publication_id,flush=True)
assert actual==(ROOT/'outputs/active_publication.json').read_bytes() and flow.code_identity()==code
value={'status':'PASS_COLD_NATIVE_READ','code':code,'time':datetime.now(timezone.utc).isoformat(),
       'new_business_calls':[0,0,0],'actual_active_unchanged':True,'versions':items}
with args.output.open('xb') as out:out.write(canonical_json_bytes(value=value))
