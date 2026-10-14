import csv,hashlib,io,json,socket,subprocess,sys,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tools'),str(ROOT)]
from vnext_company import main
from vnext import current_d04_result,ordinary_current_update
from vnext.continuous_call_ledger import CallLedger
LEDGER=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13');SOURCE=LEDGER/'source-inputs'
protected=[LEDGER/'claims.jsonl',LEDGER/'binding.json'];packets=[]
for path in (LEDGER/'calls').glob('*/source.json'):
    source=json.loads(path.read_text())
    if source.get('company_id')=='ford_motor_company' and source.get('metric_id')=='D04':
        protected.extend(p for p in path.parent.rglob('*') if p.is_file());packets.append(source)
for packet in packets:
    for proof in packet.get('source_proofs',[]):
        relative=proof.get('request_repo_relative_path')
        if relative:protected.append(SOURCE/relative)
protected=sorted(set(protected))
def hashes(files):return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before=hashes(protected);operations=[]
args=['run','--company','ford_motor_company','--source-root',str(SOURCE),'--metric','D04','--work-dir',str(OUT/'state'),'--output-dir',str(OUT/'output')]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch.object(CallLedger,'claim',side_effect=AssertionError('No claims')):
    for label,forbidden in [('first',False),('repeat-forbidden-factory',True)]:
        stream=io.StringIO();start=time.perf_counter()
        if forbidden:
            with patch.object(current_d04_result,'prepare_current_d04_case',side_effect=AssertionError('No unchanged model reconstruction')),redirect_stdout(stream):code=main(args)
        else:
            with redirect_stdout(stream):code=main(args)
        seconds=time.perf_counter()-start;report=json.loads(stream.getvalue());(OUT/(label+'.json')).write_text(json.dumps(report,indent=2)+'\n')
        operations.append({'phase':label,'seconds':seconds,'exit_code':code,'report':report})
        print(label,code,seconds,report.get('metrics'),flush=True)
        metric=report['metrics'][0]
        if metric.get('status') not in ('CANDIDATE_READY','CANDIDATE_WITHHELD','PREVIOUS_INPUT_WITHHELD','NO_SOURCE_CONTENT_CHANGE'):
            (OUT/'failure-summary.json').write_text(json.dumps({'operations':operations,'originals_unchanged':before==hashes(protected),'calls':[0,0,0]},indent=2)+'\n')
            raise AssertionError('Actual company input not accepted; retained accurate failure, no replacement answer')
        if forbidden:
            assert metric['result_id']==operations[0]['report']['metrics'][0]['result_id']
            assert not metric['calculation_performed'] and not metric['new_candidate_created']
        else:
            result_root=Path(metric['result_root']);first_result_files=hashes([p for p in result_root.rglob('*') if p.is_file()])
            first_result_dirs=sorted(str(p) for p in (OUT/'state/updates/D04/results').iterdir())
    assert first_result_files==hashes([Path(p) for p in first_result_files])
    assert first_result_dirs==sorted(str(p) for p in (OUT/'state/updates/D04/results').iterdir())
runner="""import sys,socket;from pathlib import Path;from unittest.mock import patch
r=Path(sys.argv[1]);sys.path[:0]=[str(r/'scripts'),str(r/'tools'),str(r)]
from vnext_company import main
from vnext import ordinary_current_update,current_d04_result
from vnext.continuous_call_ledger import CallLedger
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch.object(CallLedger,'claim',side_effect=AssertionError('No claims')),patch.object(ordinary_current_update,'run_once',side_effect=AssertionError('No reader update')),patch.object(current_d04_result,'prepare_current_d04_case',side_effect=AssertionError('No reader calculation')):
    raise SystemExit(main(sys.argv[2:]))
"""
state_files=hashes([p for p in (OUT/'state').rglob('*') if p.is_file()]);start=time.perf_counter()
read=subprocess.run([sys.executable,'-c',runner,str(ROOT),'results','--company','ford_motor_company','--state-root',str(OUT/'state'),'--output-root',str(OUT/'independent-results')],capture_output=True,text=True,cwd='/private/tmp')
seconds=time.perf_counter()-start;(OUT/'read.json').write_text(read.stdout);(OUT/'read.stderr').write_text(read.stderr);assert read.returncode==0,(read.returncode,read.stderr)
assert state_files==hashes([Path(p) for p in state_files]);assert before==hashes(protected)
rows=list(csv.DictReader((OUT/'independent-results/metrics_matrix.csv').open()))
assert len(rows)==1 and rows[0]['metric_id']=='D04'
manifest=json.loads((result_root/'manifest.json').read_text());records=[json.loads(s) for s in (result_root/'records.jsonl').read_text().splitlines()]
result=next(r for r in records if r.get('record_type')=='METRIC_RESULT')
summary={'code_root':str(ROOT),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_root':str(SOURCE),'state_root':str(OUT/'state'),'operations':operations,'read_seconds':seconds,'rows':rows,'original_files_preserved':len(protected),'state_files_preserved':len(state_files),'result_files':len(first_result_files),'result_bytes':sum(Path(p).stat().st_size for p in first_result_files),'manifest_period':manifest['target_period'],'result':result,'calls':[0,0,0],'production_authorized':False}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('PASS_FORD_CURRENT_D04',seconds,rows,flush=True)
