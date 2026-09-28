"""Cold-read one installed recorded Marriott B01 attempt."""
import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path('/private/tmp/issue28-b01-crossyear-auto-20260928')
HISTORY = ROOT/'state/marriott_international/metrics/B01'
identity = sys.argv[1]
expected_year = sys.argv[2]
assert identity in {'a12d76356c3f4ad98b4d8694bc870b90',
                    '7580564edd1a4a22948f4fa5e7172b53'}
installed = HISTORY/'attempts'/identity/'data'
sys.path[:0] = [str(installed),str(installed/'scripts')]

from vnext import normal_run_v3 as normal
from vnext import ordinary_update_cycle as cycle
from vnext.canonical import sha256_file
from vnext.requirements import load_requirement_snapshot

assert normal.ROOT == installed.resolve()

def tree():
    return {str(p.relative_to(HISTORY)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in HISTORY.rglob('*') if p.is_file()}

def no_network(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')

before = tree()
started = time.monotonic()
with patch.object(socket.socket, 'connect', side_effect=no_network), \
     patch.object(socket, 'getaddrinfo', side_effect=no_network), \
     patch('sec_http.urlopen', side_effect=no_network):
    config = cycle._read(HISTORY/'configuration.json')
    terminal = cycle._terminal(HISTORY,identity)
    result = cycle._verify_candidate(HISTORY,terminal,config)['B01']
    requirement = load_requirement_snapshot(
        snapshot_dir=installed/'requirements/issue_28_v13')
after = tree()
with (HISTORY/'attempts'/identity/'rows/B01/metrics_matrix.csv').open(
        newline='') as stream:
    row, = list(csv.DictReader(stream))
manifest = json.loads((HISTORY/'attempts'/identity/
    'runs/B01/manifest.json').read_text())
report = {'record_type':'ISSUE28_RECORDED_CROSS_YEAR_B01_INSTALLED_COLD_READ',
    'status':'PASS' if before == after and row['fiscal_year']==expected_year and
        result['result_id'] and manifest['requirement_closure_hash']==
        requirement['requirement_closure_hash'] else 'FAILED',
    'installed_root':str(installed),'attempt_id':identity,
    'fiscal_year':row['fiscal_year'],'value':row['value'],'unit':row['unit'],
    'accession':row['accession'],'result_id':result['result_id'],
    'run_id':manifest['run_id'],'requirement_closure_hash':
        requirement['requirement_closure_hash'],
    'public_row_sha256':sha256_file(path=HISTORY/'attempts'/identity/
        'rows/B01/metrics_matrix.csv'),
    'history_file_count_before_after':[len(before),len(after)],
    'history_bytes_unchanged':before==after,
    'seconds':round(time.monotonic()-started,3),'real_calls':[0,0,0]}
(ROOT/f'cold-{expected_year}.json').write_text(json.dumps(report,
    ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','fiscal_year','value',
    'result_id','run_id','history_file_count_before_after',
    'history_bytes_unchanged','seconds')},ensure_ascii=False),flush=True)
assert report['status']=='PASS'
