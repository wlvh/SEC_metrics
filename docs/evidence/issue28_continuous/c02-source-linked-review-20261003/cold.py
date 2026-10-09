"""Independent-process reread from actual source; no decisions or current output."""
from pathlib import Path
import json,hashlib,sys,time
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'scripts'))
HERE=Path(__file__).parent
from vnext.c02_model_review_view import read_development_review_view
known=json.loads((HERE/'summary.json').read_text())
# Reject sockets/children; the known input and current code roots remain explicit.
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:raise RuntimeError('NO_NETWORK_OR_CHILD')
sys.addaudithook(guard)
results=[]
for sample in known['samples']:
 folder=Path(sample['output']);parent=Path(sample['parent'])
 before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in (folder,parent) for p in root.rglob('*') if p.is_file()}
 start=time.monotonic()
 out=read_development_review_view(directory=folder,parent_directory=parent,data_root=sample['data_root'],company_id=sample['company_id'],expected_candidate_hash=sample['expected_candidate_hash'],expected_review_unit_hash=sample['expected_parent_unit_hash'],expected_view_hash=sample['new_view_hash'])
 after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in (folder,parent) for p in root.rglob('*') if p.is_file()}
 assert before==after
 assert out['review_unit']['status']=='PENDING' and out['review_unit']['system_approval_eligible'] is False
 results.append({'company_id':sample['company_id'],'seconds':round(time.monotonic()-start,3),'view_hash':out['view_hash'],'source_rebuilt':True,'original_and_view_bytes_unchanged':True,'new_calls':[0,0,0]})
 print(json.dumps(results[-1]),flush=True)
(HERE/'cold-summary.json').write_text(json.dumps(results,indent=2)+'\n')
