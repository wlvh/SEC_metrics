"""Corrupt answer pack + real saved-source B04 through the public CLI."""
import argparse,csv,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-root',required=True,type=Path)
    p.add_argument('--original-answer-root',required=True,type=Path)
    p.add_argument('--output-root',required=True,type=Path)
    p.add_argument('--resume',action='store_true',help='Continue from the retained actual first-run receipt')
    args=p.parse_args();root=args.output_root.resolve()
    if not args.resume:root.mkdir(exist_ok=False)
    original_before=hashes(args.original_answer_root)
    answers=root/'broken-answers'
    if not args.resume:
        shutil.copytree(args.original_answer_root,answers)
        terminal=answers/'call0009/terminal.json';assert terminal.is_file();terminal.unlink()
    state=root/'state'
    worker="""import json,sys,socket
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as h,calculator
from vnext.continuous_call_ledger import CallLedger
from scripts import securegpt_sdk
blocked={h.prepare_historical_statement_year_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('Repeated/reader path entered B04 producer')
def forbidden(*args,**kwargs):raise AssertionError('No network/model/claim')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden),patch.object(CallLedger,'claim',forbidden),patch.object(securegpt_sdk,'send',forbidden):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
    def invoke(name,argv,forbidden):
        start=time.perf_counter();r=subprocess.run([sys.executable,'-B','-c',worker,json.dumps(argv),'1' if forbidden else '0'],capture_output=True,text=True)
        receipt={'argv':argv,'seconds':time.perf_counter()-start,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
        (root/(name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
        assert r.returncode in (0,2) and not r.stderr,(name,receipt)
        return receipt,json.loads(r.stdout)
    cli=['run','--company','ford_motor_company','--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2025','--metric','D02','--metric','B04',
         '--source-root',str(args.source_root),'--saved-legal-reviews',str(answers),'--work-dir',str(state),'--output-dir',str(root/'runs')]
    if args.resume:
        first=json.loads((root/'first.json').read_text());report=json.loads(first['stdout'])
    else:first,report=invoke('first',cli,False)
    by={m['metric_id']:m for m in report['metrics']}
    assert by['D02']['status']=='INPUT_OR_EXECUTION_FAILED' and by['D02']['error_type']=='CanonicalError'
    assert 'terminal.json' in by['D02']['reason']
    assert by['B04']['status']=='CANDIDATE_READY',by
    assert report['status']=='FLOW_COMPLETED_WITH_LIMITATIONS' and report['calls']=={'provider':0,'paid':0,'sec':0}
    assert not list((state/'updates/D02').rglob('manifest.json'))
    results_before={p:h for p,h in hashes(state).items() if '/results/' in p}
    again,repeated=invoke('repeat',cli,True)
    by2={m['metric_id']:m for m in repeated['metrics']}
    assert by2['D02']['status']=='INPUT_OR_EXECUTION_FAILED'
    assert by2['B04']['status']=='NO_SOURCE_CONTENT_CHANGE'
    assert by2['B04']['result_id']==by['B04']['result_id']
    assert results_before=={p:h for p,h in hashes(state).items() if '/results/' in p}
    before_read=hashes(state)
    read,view=invoke('read',['results','--company','ford_motor_company','--state-root',str(state),'--output-root',str(root/'read')],True)
    assert hashes(state)==before_read
    rows={row['metric_id']:row for row in csv.DictReader((root/'read/metrics_matrix.csv').open())}
    assert rows['D02']['value']=='' and rows['D02']['result_validity']=='NO_CURRENT_RESULT'
    assert rows['B04']['value'] and rows['B04']['cik']=='37996'
    assert rows['B04']['period_start']=='2025-01-01' and rows['B04']['period_end']=='2025-12-31'
    assert rows['B04']['result_id']==by['B04']['result_id']
    assert hashes(args.original_answer_root)==original_before
    receipt={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'uncommitted_paths':subprocess.check_output(['git','status','--porcelain'],text=True).splitlines(),
        'phases':{name:{k:v for k,v in item.items() if k not in ('stdout','stderr')}
                  for name,item in [('first',first),('repeat',again),('read',read)]},
        'first_metrics':report['metrics'],'repeat_metrics':repeated['metrics'],'rows':rows,
        'original_answer_files_unchanged':len(original_before),'result_files_unchanged':len(results_before),
        'reader_state_files_unchanged':len(before_read),'new_calls':[0,0,0]}
    (root/'summary.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
