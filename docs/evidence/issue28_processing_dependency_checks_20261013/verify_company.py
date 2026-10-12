"""Actual B04 CLI source/code change, failed revalidation and zero-compute repeat."""
import argparse
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('--source-root',type=Path,required=True)
parser.add_argument('--state-root',type=Path,required=True)
parser.add_argument('--output-root',type=Path,required=True)
parser.add_argument('--receipt',type=Path,required=True)
parser.add_argument('--resume',action='store_true')
args=parser.parse_args();assert args.resume or not args.state_root.exists()
args.output_root.mkdir(parents=True,exist_ok=args.resume)
spec=importlib.util.spec_from_file_location('real_company_cli',Path('tools/vnext_company.py'))
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
argv=['run','--company','enphase_energy','--metric','B04','--source-root',str(args.source_root),
    '--work-dir',str(args.state_root),'--output-dir',str(args.output_root/'run')]

def run(label):
    started=time.perf_counter();output=io.StringIO()
    with contextlib.redirect_stdout(output),patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')):
        code=cli.main(argv)
    body=json.loads(output.getvalue());(args.output_root/(label+'.json')).write_text(output.getvalue())
    return {'seconds':format(time.perf_counter()-started,'.6f'),'code':code,'report':body}

first=run('first' if not args.resume else 'resumed-first');assert first['code']==0,first
protected={str(p.relative_to(args.state_root)):hashlib.sha256(p.read_bytes()).hexdigest()
    for p in args.state_root.rglob('*') if p.is_file() and '/results/' in str(p)}
from vnext import ordinary_current_update as update
from vnext import text_coverage,ordinary_saved_result
normal_hash=update.sha256_file
target=Path(text_coverage.__file__)
def changed_hash(*,path):
    return 'TEST_ONLY_BUSINESS_PARSER_CHANGE' if Path(path)==target else normal_hash(path=path)
with patch.object(update,'sha256_file',side_effect=changed_hash),patch.object(
        ordinary_saved_result,'_ordinary_case',side_effect=AssertionError('TEST_ONLY_CHANGED_FACTORY_ACTUALLY_ENTERED')):
    failed=run('changed-parser-failure')
assert failed['report']['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED',failed
assert 'TEST_ONLY_CHANGED_FACTORY_ACTUALLY_ENTERED' in json.dumps(failed)
after={str(p.relative_to(args.state_root)):hashlib.sha256(p.read_bytes()).hexdigest()
    for p in args.state_root.rglob('*') if p.is_file() and '/results/' in str(p)}
assert all(after.get(path)==digest for path,digest in protected.items())
with patch.object(update,'sha256_file',side_effect=changed_hash):
    recovered=run('recovered');assert recovered['code']==0,recovered
    with patch.object(ordinary_saved_result,'_ordinary_case',side_effect=AssertionError('REPEAT_CALCULATION_FORBIDDEN')):
        repeat=run('repeat-forbidden');assert repeat['code']==0,repeat
command=[sys.executable,'tools/vnext_company.py','results','--company','enphase_energy',
    '--state-root',str(args.state_root),'--output-root',str(args.output_root/'read')]
started=time.perf_counter();done=subprocess.run(command,text=True,capture_output=True,timeout=60)
read_seconds=format(time.perf_counter()-started,'.6f');assert done.returncode==0,done.stdout+done.stderr
rows=[]
for path in (args.output_root/'read').rglob('*.csv'):
    with path.open() as stream:
        reader=csv.DictReader(stream)
        if {'metric_id','value','result_id'}<=set(reader.fieldnames or []):
            rows.extend(dict(row) for row in reader if row['metric_id']=='B04')
assert len(rows)==1 and rows[0]['value']=='172133000',rows
receipt={'tested_base':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'tested_state':'base plus uncommitted processing-dependency patch','code_root':str(Path.cwd()),
    'source_root':str(args.source_root),'first':first,'failed':failed,'recovered':recovered,
    'repeat':repeat,'independent_read_seconds':read_seconds,'row':rows[0],
    'old_result_files_preserved_after_failure':len(protected),'new_calls':[0,0,0],
    'test_mutation':'changed parser version hash plus factory-entry failure injection; actual parser execution is separately traced; no source/program file edit'}
args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({key:value for key,value in receipt.items() if key not in {'first','failed','recovered','repeat'}}))
