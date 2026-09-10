from pathlib import Path
import sys,json,csv,io,hashlib,subprocess
from datetime import datetime,timezone
r=Path('/Users/lyuhongwang/Developer/SEC_metrics');w=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');sys.path[:0]=[str(r),str(r/'scripts')]
from vnext.publication import PublicationView,ROOT_MIRROR_RELATIVE_PATHS
from vnext.canonical import strict_json_loads,strict_json_file,sha256_file,canonical_json_bytes
from vnext import annual_continuity as c,annual_publication as annual
code=c.code_identity();initial=strict_json_file(path=w/'baseline.json')['active'];assert strict_json_file(path=r/'outputs/active_publication.json')==initial
result={'record_type':'NEW_PROCESS_NETWORK_DENIED_ACTUAL_AND_S0_COLD_READ','code':code,'time':datetime.now(timezone.utc).isoformat(),'packages':[]}
for label,root in [('ACTUAL_UNCHANGED',r),('ISOLATED_HISTORICAL_S0',w/'live/stage/publication')]:
 view=PublicationView.open(publication_root=root);matrix=list(csv.DictReader(io.StringIO(view.read_bytes(relative_path='metrics_matrix.csv').decode())));evidence=view.read_bytes(relative_path='metric_evidence.csv')
 complete=strict_json_file(path=view.bundle_dir/annual.BATCH);assert len(matrix)==327 and complete['selected_result_count']==2 and complete['inherited_result_count']==238 and len(complete['cumulative_result_bindings'])==240
 selected={}
 for metric in ('B01','B10'):
  native=view.native_result(company_id='marriott_international',metric_id=metric);records=[strict_json_loads(text=x) for x in native['records_raw'].decode().splitlines()];sources=[]
  for source in native['sources']:
   raw=next(x for x in records if x['record_type']=='RAW_BLOB' and x['raw_asset_id']==source['raw_asset_id']);path='internal/annual_snapshot/data/'+raw['storage_uri'];body=view.read_bytes(relative_path=path);assert hashlib.sha256(body).hexdigest()==raw['raw_asset_id'][7:] and len(body)==raw['byte_length']
   sources.append({'reference':source,'bundle_path':path,'sha256':hashlib.sha256(body).hexdigest(),'size':len(body)})
  selected[metric]={'result':native['result'],'owner_publication_id':native['owner_publication_id'],'run_path':native['run_path'],'sources':sources}
 mirrors={target:sha256_file(path=root/target)==sha256_file(path=view.bundle_dir/source) for source,target in ROOT_MIRROR_RELATIVE_PATHS.items()};assert all(mirrors.values())
 result['packages'].append({'label':label,'root':str(root),'publication_id':view.publication_id,'manifest_sha256':sha256_file(path=view.bundle_dir/'publication_manifest.json'),'previous_publication_id':view.manifest['previous_publication_id'],'matrix_rows':len(matrix),'evidence_sha256':hashlib.sha256(evidence).hexdigest(),'complete_coordinates':240,'selected':selected,'mirrors_match':mirrors})
 print(label,view.publication_id,'cold PASS',flush=True)
assert strict_json_file(path=r/'outputs/active_publication.json')==initial
stage=strict_json_file(path=w/'live-logs/stage-proposal-02.json');result['actual_business_counts']=c.budget_counts(stage);assert result['actual_business_counts']['provider']==result['actual_business_counts']['paid']==1 and result['actual_business_counts']['sec_reserved']==0
assert not (w/'live/stage/successful-candidate.json').exists()
intents=list((w/'live/stage/publication/outputs/publication_switch_intents').glob('*.json'));result['pending_intents']=[str(p) for p in intents];assert not intents
result.update(status='PASS_READ_ONLY',success_reference_absent=True,new_process_provider_calls=0,new_process_SEC_calls=0,actual_active_unchanged=True);assert c.code_identity()==code
with (w/'live-logs/cold-read-final.json').open('xb') as out:out.write(canonical_json_bytes(value=result))
