"""Actual saved Marriott B01 CLI: presentation change, recovery, repeat/read.

Only a pure presentation note and its reported version are changed in memory.
All diagnostic results are isolated; no source or business record is edited.
"""
import argparse
from contextlib import ExitStack,redirect_stdout
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch

from tools.vnext_company import main
from vnext import ordinary_current_update as update,ordinary_saved_result as saved
from vnext import normal_numeric_projection as numeric,ordinary_projection as projection


def files(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    assert not args.work_root.exists() and not args.receipt.exists()
    args.work_root.mkdir(parents=True)
    source=args.source_root.resolve();state=args.work_root/'state'
    source_metadata={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in
        ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')}
    command=['run','--company','marriott_international','--metric','B01',
             '--source-root',str(source),'--work-dir',str(state)]
    def invoke(label):
        started=time.perf_counter();stream=io.StringIO()
        with redirect_stdout(stream),patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')), \
             patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_CLAIM')):
            code=main(command+['--output-dir',str(args.work_root/label)])
        output=json.loads(stream.getvalue());(args.work_root/(label+'.json')).write_text(stream.getvalue())
        return {'exit_code':code,'elapsed_seconds':time.perf_counter()-started,'report':output}
    first=invoke('first');assert first['exit_code']==0,first
    protected={p:h for p,h in files(state).items() if '/results/' in p}
    original_hash=update.sha256_file;original_label=numeric._period_label
    target=Path(numeric.__file__);marker='TEST_ONLY_CHANGED_PRESENTATION_NOTE'
    def changed_hash(*,path):
        return marker if Path(path)==target else original_hash(path=path)
    def changed_label(result,annual):
        label,note=original_label(result,annual)
        return label,note+' '+marker
    with patch.object(update,'sha256_file',side_effect=changed_hash), \
         patch.object(saved,'_ordinary_case',side_effect=AssertionError('TEST_ONLY_CHANGED_FACTORY_ENTERED')):
        failed=invoke('changed-failure')
    assert failed['report']['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED',failed
    assert 'TEST_ONLY_CHANGED_FACTORY_ENTERED' in json.dumps(failed)
    assert all(files(state).get(p)==h for p,h in protected.items())
    with ExitStack() as stack:
        stack.enter_context(patch.object(update,'sha256_file',side_effect=changed_hash))
        stack.enter_context(patch.object(numeric,'_period_label',side_effect=changed_label))
        stack.enter_context(patch.object(projection,'_period_label',side_effect=changed_label))
        recovered=invoke('recovered');assert recovered['exit_code']==0,recovered
        current=recovered['report']['metrics'][0]
        assert current['status']=='CANDIDATE_READY' and current['calculation_performed'],current
        stack.enter_context(patch.object(saved,'_ordinary_case',side_effect=AssertionError('NO_REPEAT_FACTORY')))
        stack.enter_context(patch('vnext.calculator.calculate_metric',side_effect=AssertionError('NO_REPEAT_CALCULATOR')))
        stack.enter_context(patch('vnext.calculator.calculate_observation_metric',side_effect=AssertionError('NO_REPEAT_CALCULATOR')))
        repeat=invoke('repeat');assert repeat['exit_code']==0,repeat
        assert repeat['report']['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE',repeat
    state_before_read=files(state)
    started=time.perf_counter()
    read=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','marriott_international',
        '--state-root',str(state),'--output-root',str(args.work_root/'independent-read')],
        text=True,capture_output=True,timeout=60)
    read_time=time.perf_counter()-started;assert read.returncode==0,read.stdout+read.stderr
    assert files(state)==state_before_read
    rows=[]
    for path in (args.work_root/'independent-read').rglob('*.csv'):
        with path.open() as stream:
            reader=csv.DictReader(stream)
            if {'metric_id','value','result_id'}<=set(reader.fieldnames or ()):
                rows.extend(dict(r) for r in reader if r['metric_id']=='B01')
    assert len(rows)==1 and rows[0]['value']=='26186000000' and rows[0]['unit']=='USD',rows
    assert marker in rows[0]['notes'],rows
    assert all(files(state).get(p)==h for p,h in protected.items())
    assert source_metadata=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in source_metadata}
    receipt={'code_root':str(Path.cwd()),'committed_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'tested_with_uncommitted_dependency_changes':True,'source_root':str(source),'source_metadata':source_metadata,
        'first':first,'changed_failure':failed,'recovered':recovered,'repeat':repeat,
        'independent_read_seconds':read_time,'row':rows[0],
        'old_result_files_preserved':len(protected),'state_files_preserved_during_read':len(state_before_read),
        'isolated_presentation_mutation':marker,'new_calls':[0,0,0]}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'first_seconds':first['elapsed_seconds'],'recovered_seconds':recovered['elapsed_seconds'],
        'repeat_seconds':repeat['elapsed_seconds'],'read_seconds':read_time,
        'value':rows[0]['value'],'unit':rows[0]['unit'],'old_result_files_preserved':len(protected),'new_calls':[0,0,0]}))


if __name__=='__main__':
    run()
