"""Independent process; no networking or subprocess help for actual replay."""
import json
import socket
import subprocess
import time

import postprocess as p


def forbidden(*args, **kwargs):
    raise AssertionError('NETWORK_AND_SUBPROCESS_FORBIDDEN')


socket.create_connection = forbidden
socket.socket = forbidden
subprocess.Popen = forbidden
subprocess.run = forbidden
saved = json.loads((p.HERE/'checked-output.json').read_text())
start = time.monotonic()
report = p.read(saved['processing_root'], saved['processing_sha256'])
assert report == saved['report']
out = {'processing_sha256': saved['processing_sha256'], 'seconds': round(time.monotonic()-start, 3),
       'report_equal': True, 'native_credit': False, 'new_calls': [0, 0, 0]}
(p.HERE/'cold-output.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(out))
