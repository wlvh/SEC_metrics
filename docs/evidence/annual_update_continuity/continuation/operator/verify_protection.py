from pathlib import Path
import sys,json,hashlib,subprocess
from datetime import datetime,timezone
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');N=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import annual_continuity as flow
from vnext.annual_adoption import _tree_files
from vnext.canonical import strict_json_file,canonical_json_bytes,sha256_file
out=Path(sys.argv[1]);assert not out.exists()
base=strict_json_file(path=N/'baseline.json');files=strict_json_file(path=N/'tracked-baseline.json')
changed=set(subprocess.check_output(['git','diff','--name-only',base['head'],'HEAD'],cwd=ROOT,text=True).splitlines())
checked=0
for relative,proof in files.items():
 if relative in changed:continue
 p=ROOT/relative;assert {'sha256':sha256_file(path=p),'size':p.stat().st_size}==proof,relative
 checked+=1
old=strict_json_file(path=N/'original-live-file-proofs.json');old_root=Path(old['root'])
assert _tree_files(root=old_root)==old['files'],'Original live file set or bytes changed'
binding=strict_json_file(path=old_root/'stage/stage-binding.json');proof=flow._previous_stage_proof(binding)
seed=binding['stage']['seed']
for name in ('b01','b10'):
 assert _tree_files(root=Path(seed[name+'_directory']))==seed[name+'_files'],name+' original seed changed'
assert strict_json_file(path=ROOT/'outputs/active_publication.json')==base['active']
result={'status':'PASS_PROTECTED_ORIGINAL_BYTES','time':datetime.now(timezone.utc).isoformat(),
 'code':flow.code_identity(),'unchanged_tracked_files':checked,'changed_tracked_paths':sorted(changed),
 'original_live_file_count':len(old['files']),'original_seed_runs_unchanged':True,
 'previous_stage_proof':proof,'actual_active':base['active'],'new_business_calls':[0,0,0]}
with out.open('xb') as f:f.write(canonical_json_bytes(value=result))
print(result['status'],checked,len(old['files']))
