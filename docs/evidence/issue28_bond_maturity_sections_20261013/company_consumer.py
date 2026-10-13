"""Actual public saved-source CLI, stable failure reuse and separate results process."""
import argparse,contextlib,hashlib,io,json,runpy,socket,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from tools.vnext_company import main
from vnext import historical_b06_case,current_b06_case,calculator

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--resume',action='store_true')
p.add_argument('--work-root',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
a=p.parse_args();assert a.resume or not a.work_root.exists();a.work_root.mkdir(exist_ok=True);a.evidence.mkdir(exist_ok=True)
state=a.work_root/'state';out=a.work_root/'first'
args=['run','--company','macys','--metric','B06','--period','fiscal-years',
      '--fiscal-year-start','2024','--fiscal-year-end','2024','--source-root',str(a.source_root),
      '--work-dir',str(state),'--output-dir',str(out)]
def invoke(argv):
    stream=io.StringIO();start=time.monotonic()
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):rc=main(argv)
    return rc,time.monotonic()-start,stream.getvalue()
def files(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}
@contextlib.contextmanager
def reject_execution(function,code):
    original=function.__code__
    try:
        function.__code__=code.replace(co_filename=original.co_filename)
        yield
    finally:function.__code__=original
with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')):
    if a.resume:
        body=(a.evidence/'company-first.json').read_text();first=json.loads(body)
        rc=2;elapsed=first['elapsed_seconds']
    else:
        rc,elapsed,body=invoke(args);(a.evidence/'company-first.json').write_text(body)
    result_files={k:v for k,v in files(state).items() if 'results/' in k or 'runs/' in k}
    assert result_files, 'No saved company result'
    args[-1]=str(a.work_root/'repeat')
    def forbidden(*args,**kwargs):raise AssertionError('Recalculated')
    with contextlib.ExitStack() as stack:
        # Keep real function metadata/source-file identity for configuration;
        # replace only in-memory code to fail if the producer is invoked.
        for function in (historical_b06_case.prepare_historical_b06_year_case,
                         current_b06_case.prepare_selected_b06_case,
                         calculator.calculate_metric,calculator.calculate_observation_metric):
            stack.enter_context(reject_execution(function,forbidden.__code__))
        repeat_rc,repeat_time,repeat_body=invoke(args)
    repeated=json.loads(repeat_body)['metrics'][0]
    assert repeated['status']=='PREVIOUS_INPUT_WITHHELD' and repeated['raw_input_unchanged'],repeated
    assert not repeated['calculation_performed'] and not repeated['new_candidate_created'],repeated
    (a.evidence/'company-repeat.json').write_text(repeat_body)
    assert {k:v for k,v in files(state).items() if 'results/' in k or 'runs/' in k}==result_files
before=files(state);readout=a.work_root/'read-verified'
cli=['tools/vnext_company.py','results','--company','macys','--state-root',str(state),'--output-root',str(readout)]
bootstrap='import runpy,socket,sys;from unittest.mock import patch;sys.argv='+repr(cli)+'\nwith patch.object(socket.socket,"connect",side_effect=AssertionError("No network")):runpy.run_path(sys.argv[0],run_name="__main__")'
start=time.monotonic();proc=subprocess.run([sys.executable,'-c',bootstrap],cwd=ROOT,text=True,capture_output=True);readtime=time.monotonic()-start
(a.evidence/'company-read.json').write_text(proc.stdout+proc.stderr)
assert proc.returncode==0,proc.stderr
assert files(state)==before
summary={'first_exit':rc,'first_seconds':elapsed,'repeat_exit':repeat_rc,'repeat_seconds':repeat_time,
         'read_seconds':readtime,'state_files_preserved':len(before),'result_files_preserved':len(result_files),
         'work_root':str(a.work_root),'calls':[0,0,0]}
(a.evidence/'company-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
