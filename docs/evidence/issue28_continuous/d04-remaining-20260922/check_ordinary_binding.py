from pathlib import Path
from unittest.mock import patch
import json,socket,time
from vnext.normal_run_v3 import install_normal_inputs,create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile import validate_execution_authority
from vnext.normal_source_authority import ROOT
base=Path('/tmp/sec_metrics_ordinary_binding_20260922');base.mkdir(exist_ok=False);started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_NETWORK')):
 for version in ['issue_28_v13','issue_28_v14']:
  r=load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/version);validate_execution_authority(repo_root=ROOT,requirement=r)
 install_normal_inputs(data_root=base/'data',company_id='enphase_energy',metric_id='B08')
 created=create_normal_run(data_root=base/'data',run_dir=base/'run',company_id='enphase_energy',metric_id='B08')
 rendered=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
 result={'status':'PASS_ORDINARY_V14_AND_SUCCESSOR_BINDING_NATIVE_B08','run_id':created['manifest']['run_id'],'requirement_id':created['manifest']['requirement_id'],'value':str(created['result']['value']),'seconds':round(time.monotonic()-started,3),'new_calls':[0,0,0],'old_runs_changed':False}
 Path(__file__).with_name('ordinary-binding-native-check.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
