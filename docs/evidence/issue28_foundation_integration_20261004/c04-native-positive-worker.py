from pathlib import Path
from unittest.mock import patch
import socket,json,time
from vnext import normal_run_v3 as normal
from vnext.c04_registration_successor import EVENT_FORMS
from vnext.ordinary_projection import render_ordinary_run
start=time.monotonic();root=Path('/private/tmp/issue28-foundation-c04-positive-run')
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')):
 case=normal.install_normal_inputs(data_root=root/'data',company_id='marriott_international',metric_id='C04',c04_event_forms=EVENT_FORMS)
 outcome=normal.create_normal_run(data_root=root/'data',run_dir=root/'run',company_id='marriott_international',metric_id='C04',c04_event_forms=EVENT_FORMS)
 row=render_ordinary_run(data_root=root/'data',run_dir=root/'run')
 assert outcome['result']['publication']=='PUBLISHED'
 (root/'rows').mkdir()
 for name,raw in row['files'].items():(root/'rows'/name).write_bytes(raw)
 print(json.dumps({'status':'PASS_LIMITED_C04_NATIVE_RUN','seconds':time.monotonic()-start,'code_root':str(normal.ROOT),'data_root':str(root/'data'),'requirement_closure_hash':outcome['manifest']['requirement_closure_hash'],'spec_paths':case['spec_paths'],'result':outcome['result'],'run_id':outcome['manifest']['run_id'],'row':row['row'],'calls':[0,0,0],'scope':'Existing saved Marriott FY2025 input; not new financial year discovery or adoption'},indent=2))
