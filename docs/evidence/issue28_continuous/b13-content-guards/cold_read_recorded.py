import sys,json
from pathlib import Path
base=Path(sys.argv[1]).resolve();sys.path.insert(0,str(base/'data/scripts'));sys.dont_write_bytecode=True
blocked=[]
def audit(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:
  blocked.append(event);raise RuntimeError('Cold replay forbids network/processes: '+event)
sys.addaudithook(audit)
from vnext import run_store
from vnext.ordinary_projection import render_ordinary_run
assert Path(run_store.__file__).resolve().is_relative_to(base/'data')
m,records,decisions=run_store._mechanically_replay_open_run(run_dir=base/'run',repo_root=base/'data',require_complete_results=True)
r=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
expected=json.loads((base/'summary.json').read_text())
assert m['run_id']==expected['run_id']
assert r['receipt']['result_id']==expected['result_id']
assert r['receipt']['semantic_assessment_mode']=='RECORDED_TEST_ONLY'
assert not blocked
out={'status':'PASS_COPIED_OPEN_RUN_COLD_REPLAY','run_id':m['run_id'],'result_id':r['receipt']['result_id'],'record_count':len(records),'review_decisions':len(decisions),'network_or_process_events':blocked,'real_model_credit':False}
Path(sys.argv[2]).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
