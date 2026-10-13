"""New Macy's D04 task from complete original real answers; no live calls."""
import argparse,csv,hashlib,io,json,socket,subprocess,sys,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def files(root):return {p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file()}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--program-root',required=True,type=Path)
    p.add_argument('--ledger-root',required=True,type=Path)
    p.add_argument('--work-root',required=True,type=Path)
    p.add_argument('--evidence-root',required=True,type=Path)
    args=p.parse_args()
    args.work_root.mkdir(exist_ok=False)
    args.evidence_root.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(args.program_root),str(args.program_root/'scripts'),str(args.program_root/'tools')]
    from tools.vnext_company import main as cli
    from vnext import current_d04_result,calculator
    from vnext.continuous_call_ledger import CallLedger
    from scripts import securegpt_sdk
    watch=[args.ledger_root/'claims.jsonl',args.ledger_root/'binding.json']
    for i in range(165,170):watch.extend(p for p in (args.ledger_root/'calls'/f'{i:04d}').rglob('*') if p.is_file())
    source=args.ledger_root/'source-inputs'
    watch.extend(source/p for p in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'))
    before={str(p):digest(p) for p in watch}
    blocked={current_d04_result.prepare_current_d04_case.__code__,calculator.calculate_text_metric.__code__}
    calls={code.co_name:0 for code in blocked}
    def guard(frame,event,arg):
        if event=='call' and frame.f_code in blocked:
            calls[frame.f_code.co_name]+=1
            raise AssertionError('Unchanged/read path entered D04 processing')
    def forbidden(*args,**kwargs):raise AssertionError('No network, model or new claim')
    state=args.work_root/'state';output=args.work_root/'run-output'
    argv=['run','--company','macys','--source-root',str(source),'--metric','D04',
          '--work-dir',str(state),'--output-dir',str(output)]
    results=[]
    with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'getaddrinfo',forbidden), \
         patch.object(CallLedger,'claim',forbidden),patch.object(securegpt_sdk,'send',forbidden):
        for name,repeated in [('first',False),('repeat',True)]:
            stream=io.StringIO();started=time.perf_counter()
            if repeated:sys.setprofile(guard)
            try:
                with redirect_stdout(stream):rc=cli(argv)
            finally:sys.setprofile(None)
            report=json.loads(stream.getvalue())
            receipt={'phase':name,'seconds':time.perf_counter()-started,'exit_code':rc,'report':report}
            (args.evidence_root/(name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
            results.append(receipt)
            print(json.dumps({'phase':name,'seconds':receipt['seconds'],'exit_code':rc,'metrics':report['metrics']},indent=2),flush=True)
            metric=report['metrics'][0]
            assert metric.get('result_id') and metric['status'] in ('CANDIDATE_WITHHELD','PREVIOUS_INPUT_WITHHELD'),metric
            assert metric['result_reason_code']=='D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE'
            if name=='first':result_before={p:h for p,h in files(state).items() if '/results/' in p}
            else:
                assert not metric['calculation_performed'] and not metric['new_candidate_created']
                assert metric['result_id']==results[0]['report']['metrics'][0]['result_id']
                assert result_before=={p:h for p,h in files(state).items() if '/results/' in p}
        before_read=files(state);readout=args.work_root/'read-output'
        reader_worker="""import json,socket,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import current_d04_result,calculator
from vnext.continuous_call_ledger import CallLedger
from scripts import securegpt_sdk
blocked={current_d04_result.prepare_current_d04_case.__code__,calculator.calculate_text_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('Reader attempted D04 processing')
def forbidden(*a,**kw):raise AssertionError('Reader attempted network/model/claim')
sys.setprofile(guard)
with patch.object(socket.socket,'connect',forbidden),patch.object(CallLedger,'claim',forbidden),patch.object(securegpt_sdk,'send',forbidden):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
        started=time.perf_counter()
        read_args=['results','--company','macys','--state-root',str(state),'--output-root',str(readout)]
        read=subprocess.run([sys.executable,'-B','-c',reader_worker,json.dumps(read_args)],cwd=args.program_root,capture_output=True,text=True)
        reader_seconds=time.perf_counter()-started
        (args.evidence_root/'independent-read.json').write_text(json.dumps({'seconds':reader_seconds,'exit_code':read.returncode,'stdout':read.stdout,'stderr':read.stderr},indent=2)+'\n')
        assert read.returncode==0 and not read.stderr
        assert files(state)==before_read
        rows=list(csv.DictReader((readout/'metrics_matrix.csv').open()));assert len(rows)==1
        row=rows[0]
        assert row['metric_id']=='D04' and row['fiscal_year']=='2025'
        assert row['period_start']=='2025-02-02' and row['period_end']=='2026-01-31'
        assert row['status']=='TEXT_QUAL' and row['value']==''
    assert before=={str(p):digest(p) for p in watch}
    summary={'program_root':str(args.program_root),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.program_root,text=True).strip(),
        'uncommitted_paths':subprocess.check_output(['git','status','--porcelain'],cwd=args.program_root,text=True).splitlines(),
        'original_ordinals':list(range(165,170)),'original_required_units':22,'protected_originals':len(before),
        'protected_unchanged':True,'phase_seconds':{r['phase']:r['seconds'] for r in results},
        'reader_seconds':reader_seconds,'result_files_unchanged':len(result_before),'reader_state_files_unchanged':len(before_read),
        'result_id':row['result_id'],'period':{'fiscal_year':2025,'period_start':row['period_start'],'period_end':row['period_end']},
        'csv_row':row,'forbidden_processing_calls':calls,'new_calls':[0,0,0],
        'defined_source_scope_only':True,'model_omission_not_independently_certified':True,'production_authorized':False}
    (args.evidence_root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
