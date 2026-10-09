"""Rebuild each new saved task from its unchanged source in a separate process."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

import task_mapping

HERE = Path(__file__).resolve().parent


def blocked(*a, **kw):
    raise AssertionError('NETWORK_OR_SUBPROCESS_FORBIDDEN')


def run():
    socket.socket = socket.create_connection = subprocess.Popen = blocked
    report = json.loads((HERE/'actual-task-mapping.json').read_text())
    sample = next(x for x in report['samples'] if x['company']=='marriott')
    raw = Path(sample['source_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==sample['source_sha256']
    source=json.loads(raw);m=task_mapping.census(source,sample['source_sha256'])
    owners=[];start=time.monotonic()
    for row in sample['requests']:
        wire=Path(row['request_path']).read_bytes()
        assert hashlib.sha256(wire).hexdigest()==row['request_sha256']
        rebuilt=task_mapping.prepare(source,sample['source_sha256'],m,[tuple(r) for r in row['owned_references']])
        assert wire==rebuilt['request_body']
        assert rebuilt['measure']==row['measure']
        owners.extend(rebuilt['owned_references'])
    assert len(owners)==len(set(owners))==len(m['refs']) and set(owners)==set(m['refs'])
    print(json.dumps({'actual_saved_requests_rebuilt':len(sample['requests']),
        'original_items_owned_exactly_once':len(owners),'seconds':round(time.monotonic()-start,3),
        'no_network_subprocess_or_model':True,'semantic_or_native_company_credit':False,'calls':[0,0,0]}))


if __name__=='__main__':run()
