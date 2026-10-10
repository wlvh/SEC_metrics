"""Read fixed peer selection code; exercise public C04, save/repeat/results offline.

Only the saved historical input preparer is loaded from the fixed peer commit.
The public four-form resolver, Calculator, company store and reader come from
this checkout; the source root stays read-only. No provider/SEC calls.
"""
import argparse,csv,hashlib,importlib.util,json,os,pathlib,socket,subprocess,sys,time,types
from unittest.mock import patch
sys.path[:0]=[str(pathlib.Path(__file__).resolve().parents[3]/'scripts'),str(pathlib.Path(__file__).resolve().parents[3])]
from vnext.c04_registration_successor import prepare_c04_registration_case,EVENT_FORMS,SELECTED_PROCESSING_FILES
from vnext.company_current_records import run_saved_company
from vnext.canonical import sha256_file


def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.name not in {'update.lock','company.lock','write.lock','latest-execution.json','latest-check.json'}}

def main():
    a=argparse.ArgumentParser();a.add_argument('--source-root',required=True,type=pathlib.Path)
    a.add_argument('--output-root',required=True,type=pathlib.Path);a.add_argument('--peer-sha',required=True);a.add_argument('--resume-only',action='store_true')
    args=a.parse_args();program=pathlib.Path(__file__).resolve().parents[3]
    args.output_root.mkdir(parents=True,exist_ok=args.resume_only)
    raw=subprocess.check_output(['git','show',args.peer_sha+':scripts/vnext/historical_governance_input.py'],cwd=program)
    module=types.ModuleType('vnext._fixed_peer_c04_preparation');module.__package__='vnext'
    exec(compile(raw,args.peer_sha+':historical_governance_input.py','exec'),module.__dict__)
    calls=[]; forbid_factory=False
    def factory(*,repo_root,company_id,metric_id,fiscal_year):
        if forbid_factory:raise AssertionError('REPEAT_FACTORY_ENTERED')
        calls.append([company_id,metric_id,fiscal_year])
        prepared=module.prepare_selected_auditor_base(repo_root=repo_root,company_id=company_id,fiscal_year=fiscal_year)
        return prepare_c04_registration_case(repo_root=repo_root,company_id=company_id,event_forms=EVENT_FORMS,
            selected_base=prepared['base'],labelled_annual=prepared['labelled_annual'],dei_release='YEAR_QUARTER_OR_DATE')
    times={};source_before=sha256_file(path=args.source_root/'evidence/requests_log.csv')
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
        if args.resume_only:
            first=json.loads((args.output_root/'first-summary.json').read_text())
            times['first']=None
        else:
            t=time.perf_counter();first=run_saved_company(company_id='ford_motor_company',source_root=args.source_root,
                work_dir=args.output_root/'state',output_dir=args.output_root/'first',metric_ids=['C04'],fiscal_years=[2022],
                case_factories={'C04':factory},processing_files_by_metric={'C04':SELECTED_PROCESSING_FILES})
            times['first']=time.perf_counter()-t
            (args.output_root/'first-times.json').write_text(json.dumps(times))
            (args.output_root/'first-summary.json').write_text(json.dumps(first,ensure_ascii=False,indent=2))
            assert first['metrics'][0]['status'] in {'CANDIDATE_READY','CANDIDATE_WITHHELD'}, first['metrics']
        files=snapshot(args.output_root/'state')
        forbid_factory=True
        t=time.perf_counter();repeat=run_saved_company(company_id='ford_motor_company',source_root=args.source_root,
            work_dir=args.output_root/'state',output_dir=args.output_root/'repeat',metric_ids=['C04'],fiscal_years=[2022],
            case_factories={'C04':factory},processing_files_by_metric={'C04':SELECTED_PROCESSING_FILES})
        times['repeat']=time.perf_counter()-t
        assert repeat['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE', repeat['metrics']
    after=snapshot(args.output_root/'state')
    for p,h in files.items():assert after[p]==h,('OLD_STATE_CHANGED',p)
    cli=[sys.executable,str(program/'tools/vnext_company.py'),'results','--company','ford_motor_company',
        '--state-root',str(args.output_root/'state'),'--output-root',str(args.output_root/'read')]
    t=time.perf_counter();read=subprocess.run(cli,cwd=program,capture_output=True,text=True,
        env={**os.environ,'PYTHONPATH':str(program/'scripts')+':'+str(program),'TMPDIR':'/private/tmp'})
    times['independent_results']=time.perf_counter()-t
    (args.output_root/'reader.log').write_text(read.stdout+'\n'+read.stderr)
    assert read.returncode==0,(read.returncode,read.stderr)
    assert sha256_file(path=args.source_root/'evidence/requests_log.csv')==source_before
    csvpath=next((args.output_root/'read').rglob('*matrix*.csv'))
    rows=list(csv.DictReader(csvpath.open()))
    report={'program_root':str(program),'tested_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=program).decode().strip(),
        'uncommitted_diff':subprocess.check_output(['git','diff','--stat'],cwd=program).decode(),
        'source_root':str(args.source_root),'peer_sha':args.peer_sha,'peer_preparer_sha256':hashlib.sha256(raw).hexdigest(),
        'seconds':times,'factory_calls':calls,'first':first,'repeat':repeat,'rows':rows,
        'protected_files':len(files),'post_files':len(after),'source_ledger_unchanged_during_this_resume_or_run':True,'resume_only':args.resume_only,'first_wall_time_missing_reason':'original driver failed after successful first calculation at mutable latest-check snapshot; not recomputed' if args.resume_only else None,'new_calls':[0,0,0],
        'public_code_sha256':{p:sha256_file(path=program/p) for p in SELECTED_PROCESSING_FILES}}
    (args.output_root/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'seconds':times,'factory_calls':calls,'rows':[{k:r[k] for k in ('metric_id','value','unit','status','period_start','period_end','fiscal_year','cik','result_id')} for r in rows],'protected_files':len(files),'post_files':len(after)},ensure_ascii=False))
if __name__=='__main__':main()
