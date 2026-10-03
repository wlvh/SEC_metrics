import contextlib
import io
import json
import socket
import subprocess
import time
from pathlib import Path

import vnext_d03_model_review as cli
HERE=Path(__file__).resolve().parent

def blocked(*a,**k): raise AssertionError('NETWORK_SUBPROCESS_FORBIDDEN')
socket.socket=blocked;socket.create_connection=blocked
subprocess.Popen=blocked;subprocess.run=blocked
saved=json.loads((HERE/'exercise-summary.json').read_text());capture=io.StringIO();start=time.monotonic()
with contextlib.redirect_stdout(capture):
 rc=cli.main(['read','--data-root',saved['data_root'],'--output-root',saved['output_root'],
 '--company','marriott_international','--candidate-hash',saved['candidate_hash'],
 '--review-unit-hash',saved['review_unit_hash']])
report=json.loads(capture.getvalue());assert rc==0 and report['status']=='PENDING'
assert report['candidate_hash']==saved['candidate_hash'] and report['review_unit_hash']==saved['review_unit_hash']
assert not report['native_result_created'] and not report['native_run_created']
report['seconds']=round(time.monotonic()-start,3);report['network_subprocess_forbidden']=True
(HERE/'cold-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report))
