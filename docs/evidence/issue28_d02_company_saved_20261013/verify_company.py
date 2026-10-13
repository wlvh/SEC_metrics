"""Offline public CLI check using separately retained original D02 answers.

This is a developer reproducer, not a model execution or business approval.
The external network is forbidden; source selection, computation and storage
use the real implementation. Repeat/read fail if the producer is invoked.
"""
import argparse
import contextlib
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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshots(root):
    return {p.relative_to(root).as_posix(): digest(p)
            for p in root.rglob('*') if p.is_file()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--program-root',required=True,type=Path)
    parser.add_argument('--source-root',required=True,type=Path)
    parser.add_argument('--answer-root',required=True,type=Path)
    parser.add_argument('--work-root',required=True,type=Path)
    parser.add_argument('--phase',choices=['prepare','first','repeat','read','missing','read-failed','restore'],required=True)
    args=parser.parse_args()
    code=args.program_root.resolve();base=args.work_root.resolve()
    sys.path[:0]=[str(code),str(code/'scripts'),str(code/'tools')]
    from vnext import d02_reviewed_source as source
    from vnext import historical_d02_case as public
    from vnext import saved_legal_review as reader
    from vnext import calculator
    from vnext.continuous_call_ledger import CallLedger
    from scripts import securegpt_sdk
    from tools.vnext_company import main as cli
    from vnext.ordinary_saved_result import read_saved_result
    answer_before=snapshots(args.answer_root)
    state=base/'state';out=base/'run-output'
    readout=base/('independent-read-failed' if args.phase=='read-failed' else 'independent-read')
    result_before=snapshots(state/'updates'/'D02'/'periods'/'FY2025'/'results')
    protected=[source.prepare_historical_legal_sources,source.finish_historical_legal_case,
        calculator.calculate_text_metric,
        public.historical_d02_factory(saved_review_root=args.answer_root)]
    codes={f.__code__:f.__qualname__ for f in protected}
    counts={name:0 for name in codes.values()};modules=set()
    scripts_prefix=str(code/'scripts')+'/'
    def profile(frame,event,arg):
        if event=='call':
            filename=frame.f_code.co_filename
            if filename.startswith(scripts_prefix):
                modules.add('scripts/'+filename[len(scripts_prefix):])
            if frame.f_code in codes:
                name=codes[frame.f_code];counts[name]+=1
                if args.phase in ('repeat','read','read-failed','restore'):
                    raise AssertionError('Unchanged/read path entered producer: '+name)
                if args.phase=='missing' and name in ('finish_historical_legal_case','calculate_text_metric'):
                    raise AssertionError('Missing answer entered aggregation/calculation: '+name)
    def forbidden(*unused,**kwargs):
        raise AssertionError('Offline verification attempted network/model/claim')
    stdout=io.StringIO();start=time.monotonic()
    with patch.object(socket.socket,'connect',forbidden), \
         patch.object(socket,'create_connection',forbidden), \
         patch.object(CallLedger,'claim',forbidden), \
         patch.object(securegpt_sdk,'send',forbidden):
        # Production timing excludes a full Python-call profiler. Only the
        # unchanged/read paths need the narrow producer execution guard.
        if args.phase in ('repeat','read','missing','read-failed','restore'):sys.setprofile(profile)
        try:
            if args.phase=='prepare':
                bundle=source.prepare_historical_legal_sources(repo_root=args.source_root,
                    company_id='ford_motor_company',fiscal_year=2025)
                indexed=public._answer_roots(args.answer_root)
                reviews=[reader.read_saved_legal_review(call_root=indexed[r['request_id']],request=r)
                         for r in bundle['requests']]
                report={'request_ids':[r['request_id'] for r in bundle['requests']],
                    'target_period':bundle['target_period'],'source_proofs':bundle['source_proofs'],
                    'original_execution_ids':[r['original_execution_id'] for r in reviews],
                    'original_usage':[r['usage'] for r in reviews],
                    'original_counts':[r['original_counts'] for r in reviews],
                    'complete_company_result':False,'new_business_calls':{'provider':0,'paid':0,'sec':0}}
                exit_code=0
            else:
                if args.phase=='first':
                    assert not state.exists(),'First run requires a new state directory'
                if args.phase in ('read','read-failed'):
                    argv=['results','--company','ford_motor_company','--state-root',str(state),
                          '--output-root',str(readout)]
                else:
                    selected_answers=args.answer_root
                    if args.phase=='missing':
                        selected_answers=base/'missing-answers'
                        selected_answers.mkdir(exist_ok=True)
                        assert not list(selected_answers.iterdir())
                    argv=['run','--company','ford_motor_company','--period','fiscal-years',
                        '--fiscal-year-start','2025','--fiscal-year-end','2025','--metric','D02',
                        '--source-root',str(args.source_root),'--saved-legal-reviews',str(selected_answers),
                        '--work-dir',str(state),'--output-dir',str(out)]
                with contextlib.redirect_stdout(stdout):exit_code=cli(argv)
                report=json.loads(stdout.getvalue())
        finally:sys.setprofile(None)
    elapsed=time.monotonic()-start
    assert snapshots(args.answer_root)==answer_before,'Original answer bytes changed'
    receipt={'phase':args.phase,'elapsed_seconds':elapsed,'exit_code':exit_code,
        'tested_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=code,text=True).strip(),
        'uncommitted_paths':subprocess.check_output(['git','status','--porcelain'],cwd=code,text=True).splitlines(),
        'program_root':str(code),'source_root':str(args.source_root.resolve()),
        'answer_root':str(args.answer_root.resolve()),
        'producer_calls':counts if args.phase in ('repeat','read','missing','read-failed','restore') else None,
        'executed_modules':sorted(modules),'answer_hashes':answer_before,'report':report}
    if args.phase!='prepare':
        pointer=json.loads((state/'updates/D02/periods/FY2025/current-result.json').read_text())
        record=state/'updates/D02/periods/FY2025/results'/pointer['version']
        saved=read_saved_result(output_root=record);result=saved['result']
        assert result['company_id']=='ford_motor_company' and result['metric_id']=='D02'
        assert result['period_start']=='2025-01-01'
        assert result['period_end']=='2025-12-31'
        assert result['unit']=='text' and result['quality']=='EXACT'
        value=result['value'];assert isinstance(value,str) and value
        original=subprocess.check_output(['git','show',
            'bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786:docs/evidence/issue47_history/model-live-round-9a368413/d02/ford_motor_company-d02-2025-12-31/run-ford_motor_company-d02-2025-12-31-D02/records.jsonl'],cwd=code,text=True)
        old=next(json.loads(line) for line in original.splitlines()
                 if json.loads(line).get('record_type')=='METRIC_RESULT')
        assert value==old['value'],'Compare only after current source computation'
        result_after=snapshots(state/'updates/D02/periods/FY2025/results')
        if args.phase in ('repeat','read','missing','read-failed','restore'):assert result_after==result_before
        records=[json.loads(line) for line in (record/'records.jsonl').read_text().splitlines()]
        candidate=next(r for r in records if r['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
        selected=sorted(candidate['selected'].values(),key=lambda c:c['order'])
        evidence=list(csv.DictReader((record/'metric_evidence.csv').open()))
        assert len(selected)==len(evidence)==45
        raw_files={}
        for item,row in zip(selected,evidence):
            path=args.source_root/row['repo_relative_path']
            if path not in raw_files:raw_files[path]=path.read_bytes()
            raw=raw_files[path]
            assert hashlib.sha256(raw).hexdigest()==row['content_sha256']
            assert hashlib.sha256(raw[item['raw_start_byte']:item['raw_end_byte']]).hexdigest()==item['raw_span_sha256']
            assert row['evidence_quote']==row['value_raw']==item['text']
            assert row['cik']=='37996' and row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31'
        receipt['source_span_and_quote_checks']=len(selected)
        matrix=readout/'metrics_matrix.csv' if args.phase in ('read','read-failed') else Path(report['output_root'])/'metrics_matrix.csv'
        rows=list(csv.DictReader(matrix.open()));assert len(rows)==1
        assert rows[0]['metric_id']=='D02' and rows[0]['fiscal_year']=='2025'
        if args.phase=='read-failed':
            assert rows[0]['value']=='' and rows[0]['unit']==''
            assert rows[0]['result_validity']=='PREVIOUS_RESULT_CURRENT_CHECK_FAILED'
            assert rows[0]['period_role']=='PREVIOUS_RESULT'
            assert report['metrics'][0]['value'] is None
            assert report['metrics'][0]['previous_result_value']==value
        else:
            assert rows[0]['value']==value and rows[0]['unit']=='text'
            assert rows[0]['result_validity']=='SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED'
        if args.phase=='missing':
            observation=report['metrics'][0]
            assert exit_code==2 and observation['status']=='INPUT_OR_EXECUTION_FAILED'
            assert 'D02_COMPLETE_SAVED_REVIEW_SET_MISSING' in observation['reason']
            assert observation['error_category']=='MODEL_RESPONSE_REQUIRED'
            assert rows[0]['period_role']=='PREVIOUS_RESULT'
            assert rows[0]['source_observation_status']=='FAILED_CURRENT_CHECK'
        receipt.update(result_id=result['result_id'],value_length=len(value),
            value_sha256=hashlib.sha256(value.encode()).hexdigest(),result_files=len(result_after),
            result_bytes=sum((state/'updates/D02/periods/FY2025/results'/p).stat().st_size for p in result_after),
            matrix=rows)
    base.mkdir(parents=True,exist_ok=True)
    (base/(args.phase+'.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('report','matrix','answer_hashes','executed_modules')},indent=2))


if __name__=='__main__':main()
