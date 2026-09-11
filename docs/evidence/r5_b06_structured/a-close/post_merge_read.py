from pathlib import Path
import sys,json,subprocess,hashlib
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');B=Path(__file__).parents[1];G=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity/group-ownership');sys.path[:0]=[str(R),str(R/'scripts')]
from vnext import publication as p,annual_continuity as f
from vnext.canonical import strict_json_file
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();parents=subprocess.check_output(['git','show','-s','--format=%P','HEAD'],text=True).split();assert parents[1]=='437d438dbfbca65ff34be2dab453ac77c425a97f';code=f.code_identity();assert code['runtime_tree']=='sha256:b91cb13afc0fc6cdb5abecf562e4f0ca78550effc47b60a9865a41f45a7a8ef1'
checks=[]
for root in [R,G/'live/stage/publication']:
 view=p.PublicationView.open(publication_root=root); views=[view]
 if root!=R:
  prev=view.manifest['previous_publication_id'];bd=view.bundle_dir.parent/prev;m=p.verify_publication_bundle(bundle_dir=bd);views.append(p.PublicationView(publication_id=prev,bundle_dir=bd,manifest=m))
 for v in views:
  matrix=v.read_bytes(relative_path='metrics_matrix.csv');ev=v.read_bytes(relative_path='metric_evidence.csv');native={}
  for metric in ['B01','B10']:
   n=v.native_result(company_id='marriott_international',metric_id=metric);native[metric]={'result':n['result'],'source_ids':[s['source_reference_id'] for s in n['sources']]}
  checks.append({'publication_id':v.publication_id,'matrix_sha256':hashlib.sha256(matrix).hexdigest(),'evidence_sha256':hashlib.sha256(ev).hexdigest(),'native':native});print('READ_PASS',v.publication_id,flush=True)
closed=[]
for root in [G.parent/'live',G.parent/'continuation/live',G/'live']:
 binding=strict_json_file(path=root/'stage/stage-binding.json');stage=binding['stage']
 try:f.validate_stage(stage,execution=True)
 except ValueError as e:assert str(e)=='CONTINUITY_STAGE_CLOSED';closed.append({'root':str(root),'rejection':str(e)})
 else:raise AssertionError('closed stage accepted')
baseline=json.loads((B/'a-close/baseline.json').read_text());assert hashlib.sha256((R/'outputs/active_publication.json').read_bytes()).hexdigest()==baseline['active_bytes_sha256'];assert subprocess.check_output(['git','stash','list'],text=True)==baseline['stash']
(B/'a-close/post-merge-read.json').write_text(json.dumps({'status':'PASS_MERGE_COMPATIBILITY_READ_ONLY','head':head,'parents':parents,'code':code,'views':checks,'closed_stages':closed,'actual_active_unchanged':True,'calls':[0,0,0]},indent=2)+'\n')
