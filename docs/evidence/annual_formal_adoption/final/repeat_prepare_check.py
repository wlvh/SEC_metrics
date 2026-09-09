"""Repeat the actual v2 input under read-only/network-denied execution."""
import json,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path(__file__).resolve().parent;WORK=BASE/'attempt-02'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import annual_publication as annual,annual_candidate
from vnext.annual_adoption import read,_tree_files,git
from vnext.annual_adoption_policy import V2
plan=read(WORK,'pending-production-plan.json')
bundle=Path(plan['bundle_directory']);context=read(bundle,annual.SNAPSHOT+'/context.json')
publication=WORK/'publication';before=_tree_files(root=publication)
def denied(*args,**kwargs):raise AssertionError('Repeated prepare must not query GitHub')
annual_candidate._github=denied
started=datetime.now(timezone.utc).isoformat()
result=annual.prepare(candidate_dir=Path(context['origin']['candidate_directory']),publication_root=publication,policy_id=V2)
assert result['status']=='REUSED_PREPARED_PUBLICATION' and result['publication_id']==plan['binding']['publication_id']
assert before==_tree_files(root=publication)
report={'status':'REPEATED_V2_PREPARE_NO_WRITES_NO_GITHUB_NO_BUSINESS_CALLS','head':git('rev-parse','HEAD').decode().strip(),
    'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
    'result':result,'publication_tree_file_count':len(before),'github_reads':0,'new_provider_paid_sec_calls':[0,0,0],
    'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(WORK/'repeat-prepare.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
