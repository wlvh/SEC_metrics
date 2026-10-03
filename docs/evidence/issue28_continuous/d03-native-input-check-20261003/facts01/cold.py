import json
import socket
import subprocess
import time
import check


def forbidden(*args, **kwargs):
    raise AssertionError('NETWORK_AND_SUBPROCESS_FORBIDDEN')


socket.socket = forbidden
socket.create_connection = forbidden
subprocess.Popen = forbidden
subprocess.run = forbidden
saved = json.loads((check.HERE/'checked-output.json').read_text())
start = time.monotonic()
report = check.read(saved['processing_root'], saved['processing_sha256'])
assert report == saved['report']
out = {'processing_sha256': saved['processing_sha256'], 'report_equal': True,
       'seconds': round(time.monotonic()-start, 3), 'native_credit': False, 'calls': [0, 0, 0]}
(check.HERE/'cold-output.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(out))
