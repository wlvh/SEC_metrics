import sys,json,hashlib
from pathlib import Path
base=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve()
sys.path.insert(0,str(base/'data/scripts')); sys.dont_write_bytecode=True
blocked=[]
def audit(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:
  blocked.append(event);raise RuntimeError('Portable cold replay forbids network and processes: '+event)
sys.addaudithook(audit)
from vnext import run_store
from vnext.canonical import content_hash
assert Path(run_store.__file__).resolve().is_relative_to(base/'data')
manifest,records,decisions=run_store.load_frozen_run(run_dir=base/'run',repo_root=base/'data')
expected=json.loads((base/'before-freeze.json').read_text())
assert content_hash(value=records)==expected['record_graph_hash']
assert next(r for r in records if r['record_type']=='METRIC_RESULT')==expected['result']
assert decisions==expected['review_decisions']
assert not list((base/'data').rglob('.git'))
result={'status':'PASS_COPIED_RUNTIME_COLD_REPLAY','run_id':manifest['run_id'],'module_file':run_store.__file__,'record_graph_hash':content_hash(value=records),'network_or_process_events':blocked,'data_root_has_git':False}
out.write_text(json.dumps(result,indent=2));print(json.dumps(result))
