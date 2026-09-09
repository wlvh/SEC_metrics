"""Targeted no-network/no-write compatibility check, no new preparation."""
import json, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone
REPO=Path('/Users/lyuhongwang/Developer/SEC_metrics')
BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
from vnext import publication as pub, annual_publication as annual
from vnext.annual_adoption import read,git,_tree_files
from vnext.canonical import content_hash
def proof(path):
    raw=path.read_bytes();return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
started=datetime.now(timezone.utc).isoformat()
before=read(BASE,'protection-before.json')
assert _tree_files(root=REPO/'outputs/publications')==before['official_publications']
assert all(proof(REPO/p)==v for p,v in before['official_files'].items())
head=git('rev-parse','HEAD').decode().strip()
assert git('branch','--show-current').decode().strip()=='main'
execution=read(BASE,'prepare-execution.json')
assert git('merge-base',execution['code']['head'],head).decode().strip()==execution['code']['head']
assert content_hash(value=git('ls-tree','-r',head,'scripts','tools','config','catalog','requirements').decode())==execution['code']['implementation_tree']
roots=[REPO,BASE.parent/'annual-publication-integration/delivery-rehearsal',Path(execution['publication_root'])]
checks=[]
for root in roots:
    view=pub.PublicationView.open(publication_root=root)
    row={'root':str(root),'publication_id':view.publication_id,'manifest_file':proof(view.bundle_dir/'publication_manifest.json'),
         'matrix_file':{'sha256':hashlib.sha256(view.read_bytes(relative_path='metrics_matrix.csv')).hexdigest()},
         'evidence_file':{'sha256':hashlib.sha256(view.read_bytes(relative_path='metric_evidence.csv')).hexdigest()}}
    if root!=REPO:
        with annual._verified(annual._Verified(annual._FACTORY,view.manifest)):
            result=annual.read_version(publication_root=root)
        assert result['public_row_count']==327 and len(result['verified_source_locations'])==2
        row['sources']=result['verified_source_locations']
    else:
        row['boundary']='Historical R3 read and exact bundle integrity, no recertification. Its inherited B01 source byte availability is not enlarged.'
    checks.append(row)
assert _tree_files(root=REPO/'outputs/publications')==before['official_publications']
assert all(proof(REPO/p)==v for p,v in before['official_files'].items())
assert _tree_files(root=Path(execution['candidate_root']))==before['candidate']
assert not git('status','--porcelain','--untracked-files=all').strip()
result={'status':'PASSED_POST_MERGE_READ_ONLY_COMPATIBILITY','merge_head':head,
        'implementation_head':execution['code']['head'],'implementation_tree':execution['code']['implementation_tree'],
        'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
        'checks':checks,'actual_r3_and_original_candidate_unchanged':True,'new_provider_paid_sec_calls':[0,0,0]}
(BASE/'post-merge-read.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
