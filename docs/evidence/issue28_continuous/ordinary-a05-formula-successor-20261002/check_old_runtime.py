"""Cold-read the old A05 Run using its own installed pre-successor code."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
old = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'ordinary-jpm-a05-current-20261002/result.json').read_text())
attempt = (Path('/private/tmp/issue28-jpm-a05-current-20261002/state')/
    'jpmorgan_chase/metrics/A05/attempts'/old['attempt_id'])
data, run = attempt/'data', attempt/'runs/A05'
assert (data/'scripts/vnext/normal_run_v3.py').is_file()
code = '''import csv,io,json,hashlib,socket,sys
from pathlib import Path
from unittest.mock import patch
data,run=map(Path,sys.argv[1:])
import vnext
assert str(vnext.__file__).startswith(str(data/'scripts'))
from vnext.ordinary_projection import render_ordinary_run
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
    rendered=render_ordinary_run(data_root=data,run_dir=run)
rows=list(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
assert len(rows)==1 and rows[0]['metric_id']=='A05' and rows[0]['formula']==''
for name,raw in rendered['files'].items():
    assert raw==(run.parents[1]/'rows/A05'/name).read_bytes()
print(json.dumps({'loaded_module':str(vnext.__file__),'formula':rows[0]['formula'],
  'row_sha256':hashlib.sha256(rendered['files']['metrics_matrix.csv']).hexdigest(),
  'result_value':rows[0]['value']}))'''
environment = {**os.environ, 'PYTHONPATH': str(data/'scripts')}
completed = subprocess.run([sys.executable,'-c',code,str(data),str(run)],
    cwd='/private/tmp',env=environment,stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,text=True,timeout=180)
(HERE/'old-runtime.stderr').write_text(completed.stderr)
assert completed.returncode == 0, completed.stderr[-1500:]
result = json.loads(completed.stdout)
assert result['result_value'] == '0.01353819078340816975991354239'
body = {'record_type':'ISSUE28_A05_OLD_INSTALLED_RUNTIME_COLD_READ',
    'old_installed_code_root':str(data),
    'old_normal_run_v3_sha256':hashlib.sha256(
        (data/'scripts/vnext/normal_run_v3.py').read_bytes()).hexdigest(),
    'old_run_id':json.loads((run/'manifest.json').read_text())['run_id'],
    'old_result_id':old['result_id'],
    'old_row_formula':result['formula'],
    'old_row_sha256':result['row_sha256'],
    'old_row_bytes_match_saved':True,
    'old_installed_module_path':result['loaded_module'],
    'new_real_calls':[0,0,0],
    'production_authorized':False}
(HERE/'old-runtime.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'old_installed_run_read':True,
                  'old_row_bytes_unchanged':True,
                  'old_formula_blank_preserved':True}))
