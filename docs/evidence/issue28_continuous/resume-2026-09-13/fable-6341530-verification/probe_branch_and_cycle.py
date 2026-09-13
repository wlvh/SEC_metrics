"""Independent probe (Claude): novel history mutations not in Codex's ten-case list.
Runs against the state left by the local OrdinaryUpdateCycleTest run.
Each case mutates one record, re-signs its record_id, calls run_once, expects rejection, then restores bytes."""
import json,os,socket,sys,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'scripts')
from vnext import normal_run_v3 as normal, ordinary_update_cycle as cycle
root=Path(os.environ['ORDINARY_UPDATE_MATERIAL_ROOT']).resolve()
state=root/'state';source=root/'source'
def check():return cycle.run_once(state_root=state,source_root=source,company_id='marriott_international',metric_ids=['B01'])
def resign(obj):
    obj['record_id']=cycle.content_hash(value={k:v for k,v in obj.items() if k!='record_id'});return obj
current=json.loads((state/'current.json').read_text())
attempts=sorted(p for p in (state/'attempts').iterdir() if p.is_dir())
intents={p.name:json.loads((p/'intent.json').read_text()) for p in attempts if (p/'intent.json').exists()}
# reconstruct linear chain order
order=[];cur=None
succ={}
for k,v in intents.items():succ.setdefault(v['previous_attempt'],[]).append(k)
while succ.get(cur):cur=succ[cur][0];order.append(cur)
print('attempts',len(attempts),'chain',len(order),'latest',current['latest_attempt'],'success',current['successful_attempt'])
results=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
     patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')), \
     patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')), \
     patch.dict(os.environ,{'SEC_CONTACT_EMAIL':'sec-tests@wlvh.com'}):
    base=check();print('baseline status:',base['status'],'new_run:',base['new_candidate_created'])
    latest=json.loads((state/'current.json').read_text())['latest_attempt']
    order=order+[latest] if latest not in order else order
    mid=order[len(order)//2];last=order[-1];first=order[0]
    cases=[
      ('latest-intent-points-to-older-parent (branch)', state/'attempts'/last/'intent.json', lambda o:o.__setitem__('previous_attempt',order[0])),
      ('older-intent-previous-attempt-cycle', state/'attempts'/mid/'intent.json', lambda o:o.__setitem__('previous_attempt',last)),
      ('older-intent-configuration-id-changed', state/'attempts'/mid/'intent.json', lambda o:o.__setitem__('configuration_id','sha256:'+'1'*64)),
      ('older-terminal-status-flipped-to-ready', state/'attempts'/[a for a in order if json.loads((state/'attempts'/a/'terminal.json').read_text())['status']!='CANDIDATE_READY'][0]/'terminal.json', lambda o:o.__setitem__('status','CANDIDATE_READY')),
      ('current-json-success-pointer-to-nonready', state/'current.json', lambda o:o.__setitem__('successful_attempt',[a for a in order if json.loads((state/'attempts'/a/'terminal.json').read_text())['status']!='CANDIDATE_READY'][0])),
    ]
    for name,path,mut in cases:
        saved={path:path.read_bytes()}
        # for intent mutations also re-sign the paired terminal so hash-only checks cannot catch it
        obj=json.loads(saved[path]);mut(obj)
        if path.name!='current.json':resign(obj)
        path.write_text(json.dumps(obj,indent=2)+'\n')
        if path.name=='intent.json':
            t=path.parent/'terminal.json';saved[t]=t.read_bytes();to=json.loads(saved[t]);to['intent_id']=obj['record_id'];resign(to);t.write_text(json.dumps(to,indent=2)+'\n')
        try:
            out=check();verdict=f"ACCEPTED status={out['status']} new_run={out['new_candidate_created']}"
        except cycle.OrdinaryUpdateError as e:verdict=f"REJECTED {e}"
        except Exception as e:verdict=f"OTHER {type(e).__name__}: {e}"
        finally:
            for p,raw in saved.items():p.write_bytes(raw)
        results.append((name,verdict));print(f"{name:52s} -> {verdict}")
    after=check();print('after restore status:',after['status'],'new_run:',after['new_candidate_created'])
json.dump(results,open(root.parent/'probe_results.json','w'),indent=1)
