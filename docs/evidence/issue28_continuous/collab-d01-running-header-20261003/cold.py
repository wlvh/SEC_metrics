"""Read only the installed D01 successor after leaving the source checkout."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
summary=json.loads((HERE/'material-summary.json').read_text())
attempt=Path(summary['native_attempt']);data=attempt/'data';run=attempt/'runs/D01'
sys.dont_write_bytecode=True;sys.path[:0]=[str(data),str(data/'scripts')]
original=Path('/Users/lyuhongwang/Developer/SEC_metrics')
def guard(event,args):
    if event=='open' and isinstance(args[0],(str,bytes,Path)):
        path=Path(args[0]).absolute()
        if path==original or original in path.parents:
            raise RuntimeError('ORIGINAL_CHECKOUT_READ_FORBIDDEN')
    if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:
        raise RuntimeError('NETWORK_OR_CHILD_FORBIDDEN')
sys.addaudithook(guard)
from vnext.ordinary_projection import render_ordinary_run
before={p.relative_to(attempt).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in attempt.rglob('*') if p.is_file()}
start=time.monotonic()
rendered=render_ordinary_run(data_root=data,run_dir=run)
for name,raw in rendered['files'].items():
    assert raw==(attempt/'rows/D01'/name).read_bytes()
assert rendered['receipt']['result_id']==summary['native_result']['result_id']
assert 'Parts I and II' not in rendered['row']['value'].splitlines()
after={p.relative_to(attempt).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
       for p in attempt.rglob('*') if p.is_file()}
assert before==after
print(json.dumps({'status':'PASS_INSTALLED_D01_V3_INDEPENDENT_COLD_READ','seconds':round(time.monotonic()-start,3),
    'receipt':rendered['receipt'],'original_source_checkout_forbidden':True,'row_files_equal':True,
    'attempt_bytes_unchanged':True,'new_calls':[0,0,0]},indent=2))
